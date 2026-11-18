"""
Job 4: icnCsrToMccaJob — FACTS ICN & CSR Monthly / Weekly / Daily Batch Job.
Direct port of:
  - jobs/icnCsrBatchJob.xml (<batch:job id="icnCsrToMccaJob">)
  - BatchTypeDecider.java:
      * batchType = 'w' (WEEKLY): Runs only updateRptdColumn
      * batchType = 'd' (DAILY): Runs step8, step9, updateRptdColumn
      * batchType = 'm' (MONTHLY, default): Runs Steps 1..9, updateRptdColumn, clearIcnTempTables, icnCsrMail
  - Step 1: IPMFactsMappingUtil.java (jobType='icn_csr')
  - Step 2: CopyIcnProcessor.java & CopyIcnWriter.java
  - Step 3: IcnDetailProcessor.java & IcnDetailWriter.java
  - Step 4: CsrDetailProcessor.java & CsrDetailWriter.java
  - Step 5: OthrInjClmtsWriter.java
  - Step 6: UpdateIcnTmpClaimProcessor.java & UpdateIcnTmpClaimDetailWriter.java
  - Step 7: UpdateIcnCsrClaimProcessor.java & UpdateIcnCsrClaimDetailWriter.java
  - Step 8: CsrAmountUpdateWriter.java
  - Step 9: AmountUpdateProcessor.java
  - Step 9b: MccaClaimRptdProcessor.java & MccaClaimRptdWriter.java
  - Step 10: DBUtils.java (clearIcnTempTables)
  - Step 11: MailImpl.java (icnCsrMail)
"""

import argparse
import logging
import os
import smtplib
from email.message import EmailMessage
import psycopg2

from dao import IcnCsrDao
from ipm_facts_mapping_util import IPMFactsMappingUtilIcnCsr
from validators import (
    CSRValidator,
    ICNValidator,
    build_injury_description,
    detect_closed_head_injury,
    format_phone_number,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("icnCsrToMccaJob")


def send_icn_csr_email() -> None:
    """Port of MailImpl.java (icnCsrMail)."""
    smtp_host = os.getenv("SMTP_HOST", "")
    if not smtp_host:
        logger.info("SMTP_HOST not set; skipping icnCsrMail send.")
        return
    msg = EmailMessage()
    msg["From"] = os.getenv("ICN_CSR_MAIL_FROM", "mcca-batch@acg.aaa.com")
    msg["To"] = os.getenv("ICN_CSR_MAIL_TO", "mcca-support@acg.aaa.com")
    msg["Subject"] = os.getenv("ICN_CSR_MAIL_SUBJECT", "ICN/CSR Monthly Batch Job Completed")
    msg.set_content(
        os.getenv("ICN_CSR_MAIL_BODY", "FACTS ICN/CSR Monthly Batch Job completed successfully.")
    )
    with smtplib.SMTP(smtp_host, int(os.getenv("SMTP_PORT", "25"))) as server:
        server.send_message(msg)


def decide_batch_type(batch_type_param: str) -> str:
    """Port of BatchTypeDecider.java."""
    val = (batch_type_param or "m").strip().lower()
    if val == "w":
        return "WEEKLY"
    if val == "d":
        return "DAILY"
    return "MONTHLY"


def run_icn_csr_to_mcca_job(
    conn,
    batch_type_param: str = "m",
    schema: str = "mcca",
) -> None:
    mode = decide_batch_type(batch_type_param)
    logger.info("Starting icnCsrToMccaJob in %s mode (batchType='%s')...", mode, batch_type_param)

    dao = IcnCsrDao(conn, schema=schema)

    # ==========================================================================
    # WEEKLY FLOW: Only executes updateRptdColumn
    # ==========================================================================
    if mode == "WEEKLY":
        updated = dao.update_rptd_to_mcca_column()
        conn.commit()
        logger.info("WEEKLY flow completed: Updated RPTD_TO_MCCA='Y' on %d rows.", updated)
        return

    # ==========================================================================
    # DAILY FLOW: Executes Step 8 -> Step 9 -> updateRptdColumn
    # ==========================================================================
    if mode == "DAILY":
        s8 = dao.update_amounts_from_incurred_sum()
        s9 = dao.update_companion_claim_amounts()
        rptd = dao.update_rptd_to_mcca_column()
        conn.commit()
        logger.info(
            "DAILY flow completed: Step8=%d rows, Step9=%d rows, updateRptdColumn=%d rows.",
            s8,
            s9,
            rptd,
        )
        return

    # ==========================================================================
    # MONTHLY FLOW: Executes Steps 1 through 11
    # ==========================================================================
    # STEP 1: ipmFactsMappingUpdateStep (IPMFactsMappingUtil [jobType='icn_csr'])
    logger.info("Step 1: Running IPM-to-FACTS mapping sanity checks and updates...")
    mapping_util = IPMFactsMappingUtilIcnCsr(conn, schema=schema)
    if not mapping_util.execute_step1():
        raise RuntimeError("icnCsrToMccaJob halted at Step 1 (ipmFactsMappingUpdateStep FAILED).")

    # STEP 2: step2 (CopyIcnProcessor & CopyIcnWriter)
    max_txn_id = dao.get_max_txn_id()
    logger.info("Step 2: Captured baseline maxTxnId=%d. Copying eligible SB/MN claims to CSR...", max_txn_id)
    copy_candidates = dao.fetch_copy_icn_candidates()
    copied_cnt = 0
    for clm in copy_candidates:
        if dao.is_exception_claim(clm["carrier_clm_num"], int(clm["carrier_clmt_num"])):
            continue
        dao.clone_icn_to_csr(clm)
        copied_cnt += 1
    conn.commit()
    logger.info("Step 2 completed: Cloned %d existing claims as CSR transactions.", copied_cnt)

    # STEP 3: step3 (IcnDetailProcessor & IcnDetailWriter)
    logger.info("Step 3: Processing new ICN claims from MCCA_TMP_CLM...")
    new_icns = dao.fetch_new_icn_candidates()
    icn_cnt = 0
    for icn in new_icns:
        clm_num = str(icn["carrier_clm_num"]).strip()
        clmt_num = int(icn["carrier_clmt_num"])
        if dao.is_exception_claim(clm_num, clmt_num):
            continue
        icn["unique_id"] = f"{clm_num}-{clmt_num}"
        icn["adj_phn_num"] = format_phone_number(icn.get("adj_phn_num"))
        ICNValidator.validate(icn)
        dao.insert_new_icn(icn)
        icn_cnt += 1
    conn.commit()
    logger.info("Step 3 completed: Inserted %d new ICN claims into MCCA_CLM.", icn_cnt)

    # STEP 4: step4 (CsrDetailProcessor & CsrDetailWriter)
    logger.info("Step 4: Processing CSR updates from MCCA_TMP_CLM...")
    csr_candidates = dao.fetch_csr_candidates()
    csr_cnt = 0
    for csr in csr_candidates:
        clm_num = str(csr["carrier_clm_num"]).strip()
        clmt_num = int(csr["carrier_clmt_num"])
        if dao.is_exception_claim(clm_num, clmt_num):
            continue
        csr["adj_phn_num"] = format_phone_number(csr.get("adj_phn_num"))
        csr["mcca_clm_num"] = csr.get("mcca_clm_num") or csr.get("clm_mcca_clm_num")

        chng_rsn = str(csr.get("chng_rsn_desc") or "").strip()
        if chng_rsn:
            dao.insert_remarks(csr["clm_unique_id"], chng_rsn)

        CSRValidator.validate(csr)
        dao.update_csr_detail(csr)
        csr_cnt += 1
    conn.commit()
    logger.info("Step 4 completed: Updated %d CSR transactions in MCCA_CLM.", csr_cnt)

    # STEP 5: step5 (OthrInjClmtsWriter)
    othr_cnt = dao.copy_other_injured_claimants()
    conn.commit()
    logger.info("Step 5 completed: Copied %d other injured claimant payment records.", othr_cnt)

    # STEP 6: step6 (UpdateIcnTmpClaimProcessor & UpdateIcnTmpClaimDetailWriter)
    logger.info("Step 6: Enriching newly created claims (TXN_ID > %d) from MCCA_TMP_CLM_DTLS...", max_txn_id)
    step6_rows = dao.fetch_step6_tmp_claim_details(max_txn_id)
    for row in step6_rows:
        for col in (
            "pol_num", "pol_eff_dt", "pol_exp_dt", "loss_dt",
            "ins_fst_name", "ins_midl_init", "ins_lst_name",
            "clmt_fst_name", "clmt_midl_init", "clmt_lst_name",
            "clmt_birth_dt", "clmt_gndr_cd", "accd_dt", "accd_desc",
        ):
            if row.get(f"d_{col}") is not None:
                row[col] = row[f"d_{col}"]

        inj_desc = build_injury_description(row)
        if inj_desc:
            row["inj_desc"] = inj_desc

        if row.get("rec_type") == "ICN":
            row["brain_inj_cd"] = detect_closed_head_injury(row)
            ICNValidator.validate(row)
        else:
            CSRValidator.validate(row)

        dao.update_claim_from_details(row)
    conn.commit()
    logger.info("Step 6 completed: Enriched %d new claims from MCCA_TMP_CLM_DTLS.", len(step6_rows))

    # STEP 7: step7 (UpdateIcnCsrClaimProcessor & UpdateIcnCsrClaimDetailWriter)
    logger.info("Step 7: Updating open IC/PN claims not in MCCA_TMP_CLM from MCCA_TMP_CLM_DTLS...")
    step7_rows = dao.fetch_step7_existing_claim_details(max_txn_id)
    for row in step7_rows:
        for col in (
            "pol_num", "pol_eff_dt", "pol_exp_dt", "loss_dt",
            "ins_fst_name", "ins_midl_init", "ins_lst_name",
            "clmt_fst_name", "clmt_midl_init", "clmt_lst_name",
            "clmt_birth_dt", "clmt_gndr_cd", "accd_dt", "accd_desc",
        ):
            if row.get(col) is None and row.get(f"d_{col}") is not None:
                row[col] = row[f"d_{col}"]

        if not row.get("inj_desc"):
            row["inj_desc"] = build_injury_description(row)

        if row.get("rec_type") == "ICN":
            ICNValidator.validate(row)
        else:
            CSRValidator.validate(row)

        dao.update_claim_from_details(row)
    conn.commit()
    logger.info("Step 7 completed: Updated %d existing open claims.", len(step7_rows))

    # STEP 8: step8 (CsrAmountUpdateWriter)
    s8_cnt = dao.update_amounts_from_incurred_sum()
    conn.commit()
    logger.info("Step 8 completed: Updated incurred amounts on %d claims.", s8_cnt)

    # STEP 9: step9 (AmountUpdateProcessor - Companion Claims)
    s9_cnt = dao.update_companion_claim_amounts()
    conn.commit()
    logger.info("Step 9 completed: Updated companion claim amounts on %d claims.", s9_cnt)

    # STEP 9b: updateRptdColumn (MccaClaimRptdProcessor)
    rptd_cnt = dao.update_rptd_to_mcca_column()
    conn.commit()
    logger.info("Step 9b (updateRptdColumn) completed: Marked %d claims RPTD_TO_MCCA='Y'.", rptd_cnt)

    # STEP 10: clearIcnTempTables (DBUtils.java)
    logger.info("Step 10: Clearing ICN/CSR staging tables...")
    dao.clear_icn_temp_tables()

    # STEP 11: icnCsrMail (MailImpl.java)
    logger.info("Step 11: Sending icnCsrMail completion notification...")
    send_icn_csr_email()
    logger.info("icnCsrToMccaJob MONTHLY pipeline completed all steps successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Job 4: icnCsrToMccaJob (FACTS ICN/CSR Batch Job)")
    parser.add_argument(
        "--batch-type",
        default=os.getenv("BATCH_TYPE", "m"),
        choices=["m", "M", "d", "D", "w", "W"],
        help="Batch execution mode: 'm' (Monthly), 'd' (Daily), or 'w' (Weekly)",
    )
    parser.add_argument("--schema", default=os.getenv("DB_SCHEMA", "mcca"))
    args = parser.parse_args()

    conn = psycopg2.connect(
        host=os.getenv("ALLOYDB_HOST", "localhost"),
        port=int(os.getenv("ALLOYDB_PORT", "5432")),
        dbname=os.getenv("ALLOYDB_DB", "mcca"),
        user=os.getenv("ALLOYDB_USER", "postgres"),
        password=os.getenv("ALLOYDB_PASSWORD", ""),
    )
    try:
        run_icn_csr_to_mcca_job(
            conn=conn,
            batch_type_param=args.batch_type,
            schema=args.schema,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
