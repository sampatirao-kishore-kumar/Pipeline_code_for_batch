"""
Main Orchestrator for icnCsrToMccaJob.
Exact 1:1 port of:
- jobs/icnCsrToMccaJob.xml
- jobs/beanInfo.xml (lines 937-1503)
- com.acg.mcca.batch.util.BatchTypeDecider
- com.acg.mcca.batch.util.DBUtils (table="ICN")
- com.acg.mcca.mail.MailImpl (sourceSystem="ICNCSR")

Usage Examples:
  # Monthly Run (runs Step 1 -> Step 2 -> Step 3 -> Step 4 -> Step 5 -> Step 6 -> Step 7 -> Step 8 -> Step 9 -> updateRptdColumn -> Step 10 -> icnCsrMail)
  python main.py --batch-type m --batch-date 2026/11/19

  # Daily Run (runs Step 8 -> Step 9 -> updateRptdColumn -> END)
  python main.py --batch-type d --batch-date 2026/11/19

  # Weekly Run (runs updateRptdColumn -> END)
  python main.py --batch-type w --batch-date 2026/11/19
"""

import argparse
import logging
import smtplib
import sys
from email.message import EmailMessage
from typing import Any, Callable, List

from config import JobConfig
from dao.base_dao import BaseJdbcDao
from dao.csr_dao import CsrJdbcDaoImpl
from dao.icn_dao import IcnJdbcDaoImpl
from dao.ipm_facts_mapping_dao import IPMFactsMappingUpdateDaoImpl, IPMFactsMappingUtil
from dao.mcca_claim_dao import MccaClaimDaoImpl
from dao.othr_inj_clmts_dao import OthrInjClmtsDaoImpl
from dao.update_icn_csr_dao import UpdateIcnCsrJdbcDaoImpl
from processors import (
    AmountUpdateProcessor,
    CopyIcnProcessor,
    CsrDetailProcessor,
    IcnDetailProcessor,
    MccaClaimRptdProcessor,
    UpdateIcnCsrClaimProcessor,
    UpdateIcnTmpClaimProcessor,
)
from reader_queries import (
    get_step2_copy_icn_sql,
    get_step3_icn_detail_sql,
    get_step4_csr_detail_sql,
    get_step5_update_icn_tmp_claim_sql,
    get_step6_update_icn_claim_sql,
    get_step7_update_csr_claim_sql,
    get_step8_pending_icn_sql,
    get_step9_csrs_to_update_sql,
    get_update_rptd_detail_sql,
    map_csr_amount_update_row,
    map_csr_claim_detail_row,
    map_csr_row,
    map_icn_csr_claim_detail_row,
    map_icn_csr_row,
    map_icn_incurred_amount_row,
    map_tmp_claim_detail_row,
    map_update_rptd_row,
)
from writers import (
    AlInjrdClmntCmbndWriter,
    CopyIcnWriter,
    CsrAmountUpdateWriter,
    CsrDetailWriter,
    IcnDetailWriter,
    MccaClaimRptdWriter,
    UpdateIcnCsrClaimDetailWriter,
    UpdateIcnTmpClaimDetailWriter,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("icnCsrToMccaJob")


class BatchTypeDecider:
    """
    Exact 1:1 port of com.acg.mcca.batch.util.BatchTypeDecider.
    Maps batchTypeParameter ('m', 'd', 'w') to FlowExecutionStatus ('MONTHLY', 'DAILY', 'WEEKLY').
    """

    @staticmethod
    def decide(batch_type_parameter: str) -> str:
        bt = (batch_type_parameter or "m").strip().lower()
        if bt in ("w", "weekly"):
            return "WEEKLY"
        if bt in ("d", "daily"):
            return "DAILY"
        return "MONTHLY"


class DBUtilsTasklet:
    """
    Exact 1:1 port of com.acg.mcca.batch.util.DBUtils configured with table="ICN"
    (bean id="clearIcnTempTables" in beanInfo.xml lines 939-944).
    """

    def __init__(self, icn_dao: IcnJdbcDaoImpl, csr_dao: CsrJdbcDaoImpl, table: str = "ICN"):
        self.icn_dao = icn_dao
        self.csr_dao = csr_dao
        self.table = table

    def execute(self) -> None:
        if not self.table:
            return
        for table_type in self.table.split(","):
            if table_type.strip().upper() == "ICN":
                logger.info("Executing Step 10 (clearIcnTempTables): backing up and clearing MCCA_TMP_CLM & MCCA_TMP_CLMNT")
                self.icn_dao.create_backup_log()
                self.csr_dao.create_backup_log()
                self.icn_dao.delete_all("MCCA_TMP_CLM")
                self.csr_dao.delete_all("MCCA_TMP_CLMNT")


class MailImplTasklet:
    """
    Exact 1:1 port of com.acg.mcca.mail.MailImpl configured for icnCsrMailImpl
    (sourceSystem="ICNCSR" in beanInfo.xml lines 1493-1501).
    """

    def __init__(self, config: JobConfig, source_system: str = "ICNCSR"):
        self.config = config
        self.source_system = source_system

    def execute(self) -> None:
        logger.info("Executing Step icnCsrMail (sourceSystem=%s)", self.source_system)
        msg = EmailMessage()
        msg["From"] = self.config.mail_from
        msg["To"] = self.config.mail_to
        msg["Subject"] = self.config.icn_csr_subject
        source = "TCS" if self.source_system in ("CPS", "IPM") else self.source_system
        msg.set_content(
            f"MCCA Batch Job Completed.\nSource System: {self.source_system}\nSource: {source}\n"
        )
        try:
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=10) as smtp:
                smtp.send_message(msg)
            logger.info("Notification email sent to %s", self.config.mail_to)
        except Exception as exc:
            logger.warning("SMTP notification skipped/failed (%s)", exc)

        if self.config.icn_csr_subject and self.config.icn_csr_subject.startswith("Action Required"):
            raise RuntimeError("Mcca Batch Process Failed : See above logs for more info")


class IcnCsrToMccaJobRunner:
    """
    Executes the exact Spring Batch flow defined in jobs/icnCsrToMccaJob.xml.
    """

    def __init__(self, connection: Any, config: JobConfig, batch_type_param: str, batch_date_param: str):
        self.connection = connection
        self.config = config
        self.batch_type_param = batch_type_param
        self.batch_date_param = batch_date_param

        # Initialize DAOs
        self.base_dao = BaseJdbcDao(connection, config.db_dialect)
        self.ipm_mapping_dao = IPMFactsMappingUpdateDaoImpl(connection, config.db_dialect)
        self.icn_dao = IcnJdbcDaoImpl(connection, config.db_dialect)
        self.csr_dao = CsrJdbcDaoImpl(connection, config.db_dialect)
        self.othr_inj_dao = OthrInjClmtsDaoImpl(connection, config.db_dialect)
        self.update_icn_csr_dao = UpdateIcnCsrJdbcDaoImpl(connection, config.db_dialect)
        self.mcca_claim_dao = MccaClaimDaoImpl(connection, config.db_dialect)

        # Shared helper writer
        self.al_injrd_clmnt_cmbnd_writer = AlInjrdClmntCmbndWriter(self.csr_dao)

    def _run_chunk_step(
        self,
        step_name: str,
        reader_sql: str,
        row_mapper: Callable[[dict], Any],
        processor: Any,
        writer: Any,
    ) -> None:
        logger.info("Starting %s ...", step_name)
        items = self.base_dao.query(reader_sql, row_mapper)
        logger.info("%s: Read %d rows", step_name, len(items))

        chunk: List[Any] = []
        processed_count = 0
        for item in items:
            result = processor.process(item)
            if result is not None:
                chunk.append(result)
                processed_count += 1
                if len(chunk) >= self.config.commit_interval:
                    writer.write(chunk)
                    chunk.clear()

        if chunk:
            writer.write(chunk)
            chunk.clear()

        logger.info("Finished %s: Wrote %d items", step_name, processed_count)

    def run_step1(self) -> None:
        """step1: updateAndApplyIpmFactsMappingICNCSR"""
        tasklet = IPMFactsMappingUtil(self.ipm_mapping_dao, job_type="icncsr")
        tasklet.execute()

    def run_step2(self) -> None:
        """step2: copyIcnJdbcReader -> copyIcnProcessor -> copyIcnJdbcWriter"""
        processor = CopyIcnProcessor(self.icn_dao, self.batch_date_param)
        writer = CopyIcnWriter(self.icn_dao)
        self._run_chunk_step(
            "step2 (copyIcn)",
            get_step2_copy_icn_sql(),
            map_icn_incurred_amount_row,
            processor,
            writer,
        )

    def run_step3(self) -> None:
        """step3: icnDetailJdbcReader -> icnDetailProcessor -> icnJdbcWriter"""
        processor = IcnDetailProcessor(self.icn_dao, self.othr_inj_dao, self.batch_date_param)
        writer = IcnDetailWriter(self.icn_dao)
        self._run_chunk_step(
            "step3 (icnDetail)",
            get_step3_icn_detail_sql(self.batch_date_param),
            map_icn_csr_row,
            processor,
            writer,
        )

    def run_step4(self) -> None:
        """step4: csrDetailJdbcReader -> csrDetailProcessor -> csrJdbcWriter"""
        processor = CsrDetailProcessor(self.csr_dao, self.icn_dao)
        writer = CsrDetailWriter(
            self.csr_dao, self.al_injrd_clmnt_cmbnd_writer, self.batch_date_param
        )
        self._run_chunk_step(
            "step4 (csrDetail)",
            get_step4_csr_detail_sql(),
            map_csr_row,
            processor,
            writer,
        )

    def run_step5(self) -> None:
        """step5: updateIcnTmpClaimDetailJdbcReader -> updateIcnTmpClaimProcessor -> updateIcnTmpClaimDetailJdbcWriter"""
        processor = UpdateIcnTmpClaimProcessor(self.icn_dao)
        writer = UpdateIcnTmpClaimDetailWriter(self.update_icn_csr_dao)
        self._run_chunk_step(
            "step5 (updateIcnTmpClaimDetail)",
            get_step5_update_icn_tmp_claim_sql(),
            map_tmp_claim_detail_row,
            processor,
            writer,
        )

    def run_step6(self) -> None:
        """step6: updateIcnClaimDetailJdbcReader -> updateIcnCsrClaimProcessor -> updateIcnClaimDetailJdbcWriter (recType='ICN')"""
        processor = UpdateIcnCsrClaimProcessor(
            self.icn_dao, self.othr_inj_dao, self.batch_date_param
        )
        writer = UpdateIcnCsrClaimDetailWriter(self.update_icn_csr_dao, rec_type="ICN")
        self._run_chunk_step(
            "step6 (updateIcnClaimDetail)",
            get_step6_update_icn_claim_sql(),
            map_icn_csr_claim_detail_row,
            processor,
            writer,
        )

    def run_step7(self) -> None:
        """step7: updateCsrClaimDetailJdbcReader -> updateIcnCsrClaimProcessor -> updateCsrClaimDetailJdbcWriter (recType='CSR')"""
        processor = UpdateIcnCsrClaimProcessor(
            self.icn_dao, self.othr_inj_dao, self.batch_date_param
        )
        writer = UpdateIcnCsrClaimDetailWriter(self.update_icn_csr_dao, rec_type="CSR")
        self._run_chunk_step(
            "step7 (updateCsrClaimDetail)",
            get_step7_update_csr_claim_sql(),
            map_csr_claim_detail_row,
            processor,
            writer,
        )

    def run_step8(self) -> None:
        """step8: pendingIcnJdbcReader -> amountUpdateProcessor -> csrsToUpdateJdbcWriter"""
        processor = AmountUpdateProcessor(
            self.icn_dao, self.csr_dao, self.othr_inj_dao, self.batch_date_param
        )
        writer = CsrAmountUpdateWriter(self.csr_dao, self.al_injrd_clmnt_cmbnd_writer)
        self._run_chunk_step(
            "step8 (pendingIcnAmountUpdate)",
            get_step8_pending_icn_sql(),
            map_csr_amount_update_row,
            processor,
            writer,
        )

    def run_step9(self) -> None:
        """step9: csrsToUpdateJdbcReader -> amountUpdateProcessor -> csrsToUpdateJdbcWriter"""
        processor = AmountUpdateProcessor(
            self.icn_dao, self.csr_dao, self.othr_inj_dao, self.batch_date_param
        )
        writer = CsrAmountUpdateWriter(self.csr_dao, self.al_injrd_clmnt_cmbnd_writer)
        self._run_chunk_step(
            "step9 (csrsToUpdateAmountUpdate)",
            get_step9_csrs_to_update_sql(),
            map_csr_amount_update_row,
            processor,
            writer,
        )

    def run_update_rptd_column(self) -> None:
        """updateRptdColumn: updateRptdDetailJdbcReader -> mccaClaimRptdProcessor -> mccaClaimRptdWriter"""
        processor = MccaClaimRptdProcessor(self.mcca_claim_dao, self.batch_date_param)
        writer = MccaClaimRptdWriter(self.mcca_claim_dao)
        self._run_chunk_step(
            "updateRptdColumn",
            get_update_rptd_detail_sql(self.batch_date_param),
            map_update_rptd_row,
            processor,
            writer,
        )

    def run_step10(self) -> None:
        """step10: clearIcnTempTables (DBUtils with table='ICN')"""
        tasklet = DBUtilsTasklet(self.icn_dao, self.csr_dao, table="ICN")
        tasklet.execute()

    def run_icn_csr_mail(self) -> None:
        """icnCsrMail: icnCsrMailImpl"""
        mail_tasklet = MailImplTasklet(self.config, source_system="ICNCSR")
        mail_tasklet.execute()

    def execute_job(self) -> None:
        """
        Executes the exact decision tree in jobs/icnCsrToMccaJob.xml:
        1. decider (BatchTypeDecider):
           - MONTHLY -> step1 -> step2 -> step3 -> step4 -> step5 -> step6 -> step7 -> step8 -> step9 -> updateRptdColumn
           - DAILY   -> step8 -> step9 -> updateRptdColumn
           - WEEKLY  -> updateRptdColumn
        2. mailStepDecider (BatchTypeDecider):
           - MONTHLY -> step10 (clearIcnTempTables) -> icnCsrMail
           - DAILY   -> end
           - WEEKLY  -> end
        """
        flow_status = BatchTypeDecider.decide(self.batch_type_param)
        logger.info(
            "Starting icnCsrToMccaJob | batchTypeParameter=%s (%s) | batchDateParameter=%s",
            self.batch_type_param,
            flow_status,
            self.batch_date_param,
        )

        if flow_status == "MONTHLY":
            self.run_step1()
            self.run_step2()
            self.run_step3()
            self.run_step4()
            self.run_step5()
            self.run_step6()
            self.run_step7()
            self.run_step8()
            self.run_step9()
            self.run_update_rptd_column()
        elif flow_status == "DAILY":
            self.run_step8()
            self.run_step9()
            self.run_update_rptd_column()
        elif flow_status == "WEEKLY":
            self.run_update_rptd_column()

        # Second decision node: mailStepDecider
        mail_decision = BatchTypeDecider.decide(self.batch_type_param)
        if mail_decision == "MONTHLY":
            self.run_step10()
            self.run_icn_csr_mail()
        else:
            logger.info(
                "mailStepDecider=%s: Skipping step10 (clearIcnTempTables) and icnCsrMail per icnCsrToMccaJob.xml",
                mail_decision,
            )

        logger.info("Completed icnCsrToMccaJob (%s) successfully.", flow_status)


def create_db_connection(config: JobConfig) -> Any:
    """Creates a DB-API connection for AlloyDB (PostgreSQL) or Oracle."""
    if config.db_dialect.lower() == "oracle":
        import oracledb  # type: ignore

        dsn = f"{config.db_host}:{config.db_port}/{config.db_name}"
        return oracledb.connect(user=config.db_user, password=config.db_password, dsn=dsn)
    else:
        import psycopg2  # type: ignore

        conn = psycopg2.connect(
            host=config.db_host,
            port=config.db_port,
            dbname=config.db_name,
            user=config.db_user,
            password=config.db_password,
            sslmode=config.db_sslmode,
            options=f"-c search_path={config.db_schema},public",
        )
        return conn


ALL_JOB_TABLES = [
    # Staging / Temp Tables
    "MCCA_TMP_CLM",
    "MCCA_TMP_CLMNT",
    "STG_MCCA_RESERVES",
    "STG_MCCA_LOSS_EXPENSE_DETAILS",
    "MCCA_FAC_TMP_RFR",
    # Main Transaction Tables
    "MCCA_CLAIM",
    "MCCA_ICN",
    "MCCA_CSR",
    "MCCA_OTHR_INJ_CLMTS_PYMT",
    "MCCA_PROJECTIONS",
    # Financial & Reference Tables
    "MCCA_LOSS_EXPENSE_DETAILS",
    "MCCA_RESERVES",
    "D_FISCAL_MONTH",
    "MCCA_THRESHOLD",
    "MCCA_EXCEPTION",
    "MCCA_CODES_DECODE",
    # IPM Conversion Tables
    "IPM_FACTS_CLAIM_MAPPING_TABLE",
    "IPM_FACTS_CLID_MAPPING_TABLE",
]


def verify_alloydb_tables(conn: Any, config: JobConfig) -> None:
    """Verifies AlloyDB connectivity and prints current row counts of all job tables."""
    dao = BaseJdbcDao(conn, config.db_dialect)
    logger.info(
        "Connected to AlloyDB (%s:%s/%s, schema=%s). Checking job tables...",
        config.db_host,
        config.db_port,
        config.db_name,
        config.db_schema,
    )
    for tbl in ALL_JOB_TABLES:
        try:
            cnt = dao.query_for_long(f"SELECT COUNT(*) FROM {tbl}")
            logger.info("  [OK] %-32s : %d rows", tbl, cnt)
        except Exception as exc:
            conn.rollback()
            logger.warning("  [MISSING/ERROR] %-21s : %s", tbl, exc)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MCCA Batch Job 4: icnCsrToMccaJob (1:1 Verified Python Port for AlloyDB)"
    )
    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Only test AlloyDB connection and check row counts for all icnCsrToMccaJob tables",
    )
    parser.add_argument(
        "-t",
        "--batch-type",
        dest="batch_type",
        required=False,
        default="m",
        choices=["m", "d", "w", "M", "D", "W", "MONTHLY", "DAILY", "WEEKLY"],
        help="Spring Batch batchTypeParameter: 'm' (MONTHLY), 'd' (DAILY), or 'w' (WEEKLY)",
    )
    parser.add_argument(
        "-d",
        "--batch-date",
        dest="batch_date",
        required=False,
        help="Spring Batch batchDateParameter in YYYY/MM/DD format (e.g., 2026/11/20)",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    config = JobConfig()
    conn = create_db_connection(config)
    try:
        if args.test_connection:
            verify_alloydb_tables(conn, config)
            return 0
        if not args.batch_date:
            raise ValueError("--batch-date (YYYY/MM/DD) is required when running the batch job.")
        runner = IcnCsrToMccaJobRunner(
            connection=conn,
            config=config,
            batch_type_param=args.batch_type,
            batch_date_param=args.batch_date,
        )
        runner.execute_job()
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
