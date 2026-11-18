"""
Job 3: factsToMccaJob — FACTS RFR Monthly Batch Job (All 8 Steps).
Direct port of:
  - jobs/rfrBatchJob.xml (<batch:job id="factsToMccaJob">)
  - Step 1: IPMFactsMappingUtil.java (jobType='rfr') & IPMFactsMappingUpdateDaoImpl.java
  - Step 2: rfrFactsPreLoadStep (RFRFactsPayLogPreRowMapper.java)
  - Step 3: rfrFactsMissingDatesStep (MissingDatesBatchReportMapper.java)
  - Step 4: rfrFactsHeaderStep (RfrFactsHeaderProcessor.java)
  - Step 5: rfrFactsDetailCptStep (RfrFactsDetailCptProcessor.java)
  - Step 6: rfrFactsPostStep (RfrFactsPaylogPostProcessor.java & RFRFactsPayLogPostRowMapper.java)
  - Step 7: rfrMail (RFRReportAttachedMailImpl.java)
  - Step 8: clearTempTables (DBUtils.java)
"""

import argparse
import logging
import os
from datetime import date, datetime
from typing import Any, Dict, List
import psycopg2

from dao import FactsRfrDao
from excel_reports import RFRReportAttachedMailImpl
from ipm_facts_mapping_util import IPMFactsMappingUtilRfr
from mms_client import MMSRestClient, RfrJsonBuilder
from validators import DataValidator, RFRValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("factsToMccaJob")


def run_facts_to_mcca_job(
    conn,
    rfr_cpt_eff_date: date,
    report_output_dir: str = "./reports",
    schema: str = "mcca",
) -> None:
    dao = FactsRfrDao(conn, schema=schema)
    mms_client = MMSRestClient()
    mapping_util = IPMFactsMappingUtilRfr(conn, schema=schema)

    # ==========================================================================
    # STEP 1: ipmFactsMappingUpdateStep (IPMFactsMappingUtil [jobType='rfr'])
    # ==========================================================================
    logger.info("Step 1: Running IPM-to-FACTS mapping sanity checks and updates...")
    if not mapping_util.execute_step1():
        raise RuntimeError(
            "factsToMccaJob halted at Step 1 (ipmFactsMappingUpdateStep FAILED sanity checks)."
        )

    # ==========================================================================
    # STEP 2: rfrFactsPreLoadStep (RFRFactsPayLogPreRowMapper)
    # ==========================================================================
    logger.info("Step 2: Loading pre-processing RFR batch report totals...")
    batch_report = dao.fetch_preload_batch_report()
    logger.info("Step 2 completed: %d claims loaded into batchReport.", len(batch_report))

    # ==========================================================================
    # STEP 3: rfrFactsMissingDatesStep (MissingDatesBatchReportMapper)
    # ==========================================================================
    logger.info("Step 3: Querying paylogs with missing service dates...")
    missing_dates_report = dao.fetch_missing_dates_report()
    logger.info("Step 3 completed: %d missing-date paylogs found.", len(missing_dates_report))

    # ==========================================================================
    # STEP 4: rfrFactsHeaderStep (RfrFactsHeaderProcessor.java)
    # ==========================================================================
    logger.info("Step 4: Processing MCCA_FAC_TMP_RFR headers, paylogs, CPTs, and MMS REST API...")
    date_suffix = datetime.now().strftime("%Y%m%d")
    headers = dao.fetch_all_fac_tmp_headers()

    for rfr in headers:
        clm_num = str(rfr["carrier_claim_number"]).strip()
        clmt_num = int(rfr.get("carrier_claimant_number") or 0)
        unq_key = f"{clm_num}{date_suffix}"

        rfr["unique_key"] = unq_key
        rfr["claim_type"] = "FACTS"
        rfr["record_type"] = rfr.get("record_type") or "RFR"
        rfr["pending_status"] = False
        rfr["submit_err_msg"] = None

        # Auto-billing exception check (MCCA_EXCEPTION code '3' == 'Y')
        if dao.get_auto_billing_exception(clm_num, clmt_num):
            rfr["pending_status"] = True

        # Previous RFR submitted check (MCCA_RFR max TXN_ID status == 'PN')
        if dao.is_previous_rfr_submitted(clm_num):
            rfr["pending_status"] = True

        # Header-level RFRValidator.validate
        RFRValidator.validate(rfr)

        # FACTS-specific header checks in RfrFactsHeaderProcessor
        if DataValidator.is_null(rfr.get("mcca_claim_number")):
            RFRValidator.append_error(rfr, "mccaClaimNumber")
            rfr["pending_status"] = True

        if DataValidator.is_null(rfr.get("insured_first_name")) and DataValidator.is_null(
            rfr.get("insured_last_name")
        ):
            RFRValidator.append_error(rfr, "insuredFirstName,insuredLastName")
            rfr["pending_status"] = True

        # Fetch paylogs for claim
        paylogs = dao.fetch_fac_tmp_paylogs_by_claim(clm_num)
        cpt_by_paylog_id: Dict[int, List[Dict[str, Any]]] = {}

        if paylogs:
            for detail in paylogs:
                detail["unique_key"] = unq_key
                detail["claim_type"] = "FACTS"
                detail["corrections_indicator"] = detail.get("corrections_indicator") or "N"

                paylog_uid = int(detail.get("paylog_unique_id") or 0)
                cpt_list = dao.fetch_fac_tmp_cpts_by_claim_and_paylog(clm_num, paylog_uid)
                cpt_by_paylog_id[paylog_uid] = cpt_list

                if RFRValidator.is_bill_amount_valid(detail):
                    RFRValidator.append_error(rfr, "billedAmt,totalMccaPaymentReq")
                    rfr["pending_status"] = True

                if RFRValidator.is_correction(detail):
                    detail["corrections_indicator"] = "Y"
                    RFRValidator.append_error(rfr, "payeeOrProvider")
                    rfr["pending_status"] = True

                date_err = RFRValidator.is_service_dates_valid(detail)
                if date_err:
                    RFRValidator.append_error(rfr, date_err)
                    rfr["pending_status"] = True

                if DataValidator.is_null(detail.get("check_number")):
                    RFRValidator.append_error(rfr, "checkNumber")
                    rfr["pending_status"] = True

                if DataValidator.is_null(detail.get("pay_code")):
                    RFRValidator.append_error(rfr, "payCode")
                    rfr["pending_status"] = True

                if DataValidator.is_null(detail.get("payee_or_provider")):
                    RFRValidator.append_error(rfr, "payeeOrProvider")
                    rfr["pending_status"] = True

                if DataValidator.is_null(detail.get("service_description")):
                    RFRValidator.append_error(rfr, "serviceDescription")
                    rfr["pending_status"] = True

                if not RFRValidator.is_bill_type_valid(detail, rfr_cpt_eff_date):
                    RFRValidator.append_error(rfr, "billType")
                    rfr["pending_status"] = True

                if not RFRValidator.is_service_facility_zip_valid(detail):
                    RFRValidator.append_error(rfr, "serviceFacilityZipcode")
                    rfr["pending_status"] = True

                if RFRValidator.is_cpt_required(detail):
                    if not RFRValidator.is_cpt_list_valid(detail, cpt_list):
                        RFRValidator.append_error(rfr, "rfrDetailCpt")
                        rfr["pending_status"] = True

                # March 2022 Validations
                RFRValidator.validate_tin_npi(detail, rfr, cpt_list)
                RFRValidator.validate_ub_bill_type_field(detail, rfr)
                RFRValidator.validate_cpt_codes(detail, cpt_list, rfr)
                RFRValidator.validate_non_mandatory_cpt_codes(detail, cpt_list, rfr)
                RFRValidator.validate_revenue_codes(detail, cpt_list, rfr)
                RFRValidator.validate_pay_code_bill_type(detail, rfr, rfr_cpt_eff_date)

        # Submit to MMS API if valid
        if rfr["pending_status"]:
            rfr["status_indicator"] = "PN"
        else:
            payload = RfrJsonBuilder.build_rfr_payload(
                rfr, paylogs, cpt_by_paylog_id, rfr_cpt_eff_date
            )
            ok, err_msg = mms_client.submit_rfr(payload)
            if ok:
                rfr["status_indicator"] = "SB"
                rfr["transaction_sent_date"] = datetime.now()
            else:
                rfr["status_indicator"] = "PN"
                rfr["submit_err_msg"] = err_msg

        # Update MCCA_LAST_BILL_DATE and insert MCCA_REMARKS if 'Fall Below'
        chng_rsn = str(rfr.get("change_reason_description") or "").strip()
        is_fall_below = chng_rsn.lower() == "fall below"
        dao.update_last_billing_date(clm_num, clmt_num, fall_below=is_fall_below)
        if is_fall_below:
            dao.insert_remarks(f"{clm_num}-{clmt_num}", "RFR Fall Below")

        # Write paylogs to MCCA_RFR_PAYLOG and header to MCCA_RFR
        for detail in paylogs:
            dao.insert_main_rfr_paylog(detail)
        dao.insert_main_rfr_header(rfr)

    conn.commit()
    logger.info("Step 4 completed: %d FACTS RFR headers processed.", len(headers))

    # ==========================================================================
    # STEP 5: rfrFactsDetailCptStep (RfrFactsDetailCptProcessor.java)
    # ==========================================================================
    copied_cpts = dao.copy_fac_tmp_cpts_to_main(date_suffix=date_suffix)
    conn.commit()
    logger.info("Step 5 completed: %d FACTS CPT records copied to MCCA_RFR_PAYLOG_CPT.", copied_cpts)

    # ==========================================================================
    # STEP 6: rfrFactsPostStep (RfrFactsPaylogPostProcessor.java)
    # ==========================================================================
    logger.info("Step 6: Updating batchReport with post-processing totals and SB/RJ/PN status...")
    dao.update_postload_batch_report(batch_report)

    # ==========================================================================
    # STEP 7: rfrMail (RFRReportAttachedMailImpl.java)
    # ==========================================================================
    logger.info("Step 7: Generating Excel reports and sending FACTS RFR email...")
    RFRReportAttachedMailImpl.send_reports_email(
        batch_report=batch_report,
        missing_dates_list=missing_dates_report,
        output_dir=report_output_dir,
    )

    # ==========================================================================
    # STEP 8: clearTempTables (DBUtils.java)
    # ==========================================================================
    logger.info("Step 8: Clearing MCCA_FAC_TMP_RFR* tables...")
    dao.clear_fac_temp_tables()
    logger.info("factsToMccaJob completed all 8 steps successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Job 3: factsToMccaJob (FACTS RFR Batch Job)")
    parser.add_argument(
        "--cpt-effective-date",
        default=os.getenv("RFR_CPT_EFFECTIVE_DATE", "2019-01-01"),
        help="RFR CPT effective date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--report-dir",
        default=os.getenv("REPORT_OUTPUT_DIR", "./reports"),
        help="Directory to write rfrProcessingReport.xlsx and missingDatesReport.xlsx",
    )
    parser.add_argument("--schema", default=os.getenv("DB_SCHEMA", "mcca"))
    args = parser.parse_args()

    eff_date = datetime.strptime(args.cpt_effective_date, "%Y-%m-%d").date()
    conn = psycopg2.connect(
        host=os.getenv("ALLOYDB_HOST", "localhost"),
        port=int(os.getenv("ALLOYDB_PORT", "5432")),
        dbname=os.getenv("ALLOYDB_DB", "mcca"),
        user=os.getenv("ALLOYDB_USER", "postgres"),
        password=os.getenv("ALLOYDB_PASSWORD", ""),
    )
    try:
        run_facts_to_mcca_job(
            conn=conn,
            rfr_cpt_eff_date=eff_date,
            report_output_dir=args.report_dir,
            schema=args.schema,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
