"""
Job 1: bisCpsToMccaJob — CPS RFR Monthly Batch Job (All 10 Steps).
Direct port of:
  - jobs/rfrBatchJob.xml (<batch:job id="bisCpsToMccaJob">)
  - RfrHeaderFieldSetMapper.java (19 semicolon-delimited columns)
  - RfrDetailFieldSetMapper.java (43 fields from 66-column detail file for BIL* rows)
  - RfrDetailCptFieldSetMapper.java (29 fields from 66-column detail file for CPT* rows)
  - RfrHeaderBisToDbProcessor.java
  - RfrDetailBisToDbProcessor.java
  - RfrDetailCptBisToDbProcessor.java
  - FileValidator.java
  - RfrHeaderProcessor.java
  - MailImpl.java
"""

import argparse
import csv
import logging
import os
import smtplib
from datetime import date, datetime
from email.message import EmailMessage
from typing import Any, Dict, List, Optional
import psycopg2

from dao import CpsRfrDao
from mms_client import MMSRestClient, RfrJsonBuilder
from validators import FileValidator, RFRValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("bisCpsToMccaJob")


def parse_rfr_date(val: Optional[str]) -> Optional[date]:
    if not val or not val.strip():
        return None
    return datetime.strptime(val.strip(), "%Y-%m-%d").date()


def parse_float(val: Optional[str]) -> float:
    if not val or not val.strip():
        return 0.00
    return float(val.strip())


def parse_long(val: Optional[str]) -> int:
    if not val or not val.strip():
        return 0
    return int(val.strip())


def map_header_row(cols: List[str]) -> Dict[str, Any]:
    """Port of RfrHeaderFieldSetMapper.java (19 columns: 0..18)."""
    while len(cols) < 19:
        cols.append("")
    adj_first = cols[8].strip()
    adj_last = cols[9].strip()
    adjuster_name = f"{adj_first} {adj_last}".strip() if (adj_first or adj_last) else ""

    return {
        "line_type": cols[0].strip(),
        "carrier_id": parse_long(cols[1]),
        "carrier_claim_number": cols[2].strip(),
        "mcca_claim_number": cols[3].strip(),
        "bill_sequence_number": cols[4].strip(),
        "insured_first_name": cols[5].strip(),
        "insured_middle_init": cols[6].strip(),
        "insured_last_name": cols[7].strip(),
        "adjuster_name": adjuster_name,
        "date_of_loss": parse_rfr_date(cols[10]),
        "claimant_first_name": cols[11].strip(),
        "claimant_middle_init": cols[12].strip(),
        "claimant_last_name": cols[13].strip(),
        "total_amt_billed": parse_float(cols[14]),
        "total_bill_review_fees": parse_float(cols[15]),
        "total_mcca_payment_req": parse_float(cols[16]),
        "unique_key": cols[17].strip(),
        "deductible_amount": parse_float(cols[18]),
        "cross_companion_indicator": "N",
        "cross_companion_claim_number": None,
        "transaction_sent_date": None,
        "status_indicator": "OK",
        "status": None,
        "pending_status": False,
        "submit_err_msg": None,
    }


def map_detail_bil_row(cols: List[str]) -> Dict[str, Any]:
    """Port of RfrDetailFieldSetMapper.java (Columns 0..42 of 66-column Detail File)."""
    while len(cols) < 66:
        cols.append("")
    line_type = cols[0].strip()
    alphabet_key = line_type[3] if len(line_type) > 3 else ""
    payee = cols[7].strip()
    if len(payee) > 50:
        payee = payee[:50]

    return {
        "line_type": line_type,
        "alphabet_key": alphabet_key,
        "service_start_date": parse_rfr_date(cols[1]),
        "service_end_date": parse_rfr_date(cols[2]),
        "pay_code": cols[3].strip(),
        "number_of_hours": parse_long(cols[4]),
        "check_number": cols[5].strip(),
        "check_number_key": cols[5].strip(),
        "check_date": parse_rfr_date(cols[6]),
        "payee_or_provider": payee,
        "federal_tin": cols[8].strip(),
        "cost_share_amount": parse_float(cols[9]),
        "repriced_paid_amt": parse_float(cols[10]),
        "bill_review_fees": parse_float(cols[11]),
        "ppo_fees": parse_float(cols[12]),
        "total_mcca_payment_req": parse_float(cols[13]),
        "bill_amount": parse_float(cols[14]),
        "ppo_or_other_negotiated_discount": parse_float(cols[15]),
        "service_description": cols[16].strip(),
        "carrier_check_total": parse_float(cols[17]),
        "unique_key": cols[18].strip(),
        "rx_indicator": cols[19].strip(),
        "ndc_number": cols[20].strip(),
        "days_supply": parse_long(cols[21]),
        "quantity": parse_long(cols[22]),
        "dispense_as_written_code": cols[23].strip(),
        "prescriber_npi": cols[24].strip(),
        "drg_code": cols[25].strip(),
        "patient_status": cols[26].strip(),
        "admit_date": parse_rfr_date(cols[27]),
        "discharge_date": parse_rfr_date(cols[28]),
        "ub_bill_type": cols[29].strip(),
        "service_facility_zipcode": cols[30].strip(),
        "admission_source": cols[31].strip(),
        "icd1": cols[32].strip(),
        "icd2": cols[33].strip(),
        "icd3": cols[34].strip(),
        "icd4": cols[35].strip(),
        "icd5": cols[36].strip(),
        "icd6": cols[37].strip(),
        "icd7": cols[38].strip(),
        "eob_id": cols[39].strip(),
        "bill_type": cols[40].strip(),
        "eob_revision_num": parse_long(cols[41]),
        "admission_type": cols[42].strip(),
        "corrections_indicator": "N",
    }


def map_detail_cpt_row(cols: List[str]) -> Dict[str, Any]:
    """Port of RfrDetailCptFieldSetMapper.java (Columns 0, 5, 18, 39, 40, 41, 43..65)."""
    while len(cols) < 66:
        cols.append("")
    line_type = cols[0].strip()
    alphabet_key = line_type[3] if len(line_type) > 3 else ""

    return {
        "line_type": line_type,
        "alphabet_key": alphabet_key,
        "check_number_key": cols[5].strip(),
        "unique_key": cols[18].strip(),
        "eob_id": cols[39].strip(),
        "bill_type": cols[40].strip(),
        "eob_revision_num": parse_long(cols[41]),
        "service_start_date": parse_rfr_date(cols[43]),
        "service_end_date": parse_rfr_date(cols[44]),
        "service_location": cols[45].strip(),
        "cpt_code": cols[46].strip(),
        "modifier1": cols[47].strip(),
        "modifier2": cols[48].strip(),
        "modifier3": cols[49].strip(),
        "modifier4": cols[50].strip(),
        "service_units": parse_long(cols[51]),
        "total_charges": parse_float(cols[52]),
        "total_charges_carrier_approved": parse_float(cols[53]),
        "revenue_code": cols[54].strip(),
        "prescriber_npi": cols[55].strip(),
        "icd1": cols[56].strip(),
        "icd2": cols[57].strip(),
        "icd3": cols[58].strip(),
        "icd4": cols[59].strip(),
        "icd5": cols[60].strip(),
        "icd6": cols[61].strip(),
        "icd7": cols[62].strip(),
        "icd8": cols[63].strip(),
        "icd9": cols[64].strip(),
        "icd10": cols[65].strip(),
    }


def send_email_notification(subject: str, body: str) -> None:
    """Port of MailImpl.java."""
    smtp_host = os.getenv("SMTP_HOST", "")
    if not smtp_host:
        logger.info("SMTP_HOST not set; skipping email send. Subject='%s'", subject)
        return
    msg = EmailMessage()
    msg["From"] = os.getenv("CPS_MAIL_FROM", "mcca-batch@acg.aaa.com")
    msg["To"] = os.getenv("CPS_MAIL_TO", "mcca-support@acg.aaa.com")
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(smtp_host, int(os.getenv("SMTP_PORT", "25"))) as server:
        server.send_message(msg)


def run_bis_cps_to_mcca_job(
    conn,
    header_file_path: str,
    detail_file_path: str,
    rfr_cpt_eff_date: date,
    schema: str = "mcca",
) -> None:
    dao = CpsRfrDao(conn, schema=schema)
    mms_client = MMSRestClient()

    header_map: Dict[str, Dict[str, Any]] = {}
    paylog_map: Dict[str, int] = {}

    # ==========================================================================
    # STEP 1: clearCpsTempTablesBeforeProcess
    # ==========================================================================
    logger.info("Step 1: Clearing MCCA_CPS_TMP_RFR* tables before processing...")
    dao.clear_cps_temp_tables()

    # ==========================================================================
    # STEP 2: rfrHeaderBisCpsToDbStep (RfrHeaderBisToDbProcessor)
    # ==========================================================================
    logger.info("Step 2: Loading CPS Header file '%s' into MCCA_CPS_TMP_RFR...", header_file_path)
    with open(header_file_path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader, None)  # linesToSkip = 1
        for cols in reader:
            if not cols or not any(c.strip() for c in cols):
                continue
            rfr = map_header_row(cols)
            rfr["record_type"] = "RFR"
            rfr["claim_type"] = "CPS"
            RFRValidator.validate(rfr)

            if rfr["carrier_id"] == 0 or not rfr["carrier_claim_number"]:
                raise ValueError(
                    f"Failed to process Header record for the Unique Key :{rfr['unique_key']}"
                )
            header_map[rfr["unique_key"]] = rfr
            dao.insert_tmp_rfr_header(rfr)
    conn.commit()
    logger.info("Step 2 completed: %d CPS header rows inserted.", len(header_map))

    # ==========================================================================
    # STEP 3: rfrDetailBisCpsToDbStep (RfrDetailBisToDbProcessor)
    # ==========================================================================
    logger.info("Step 3: Loading CPS Detail 'BIL*' rows from '%s'...", detail_file_path)
    with open(detail_file_path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader, None)  # linesToSkip = 1
        for cols in reader:
            if not cols or not cols[0].strip().startswith("BIL"):
                continue
            detail = map_detail_bil_row(cols)
            unq = detail["unique_key"]
            if unq not in header_map:
                raise ValueError(f"Missed Header information for the Unique Key :{unq}")

            parent = header_map[unq]
            detail["carrier_claim_number"] = parent["carrier_claim_number"]
            detail["carrier_id"] = parent["carrier_id"]
            detail["claim_type"] = "CPS"

            paylog_uid = dao.get_next_paylog_unique_id()
            detail["paylog_unique_id"] = paylog_uid

            comp_key = (
                f"{unq}-{detail['eob_id']}-{detail['bill_type']}-"
                f"{detail['eob_revision_num']}-{detail['check_number_key']}-{detail['alphabet_key']}"
            )
            paylog_map[comp_key] = paylog_uid
            dao.insert_tmp_rfr_paylog(detail)
    conn.commit()
    logger.info("Step 3 completed: %d CPS paylog rows inserted.", len(paylog_map))

    # ==========================================================================
    # STEP 4: rfrDetailCptBisCpsToDbStep (RfrDetailCptBisToDbProcessor)
    # ==========================================================================
    logger.info("Step 4: Loading CPS Detail 'CPT*' rows from '%s'...", detail_file_path)
    cpt_count = 0
    with open(detail_file_path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader, None)  # linesToSkip = 1
        for cols in reader:
            if not cols or not cols[0].strip().startswith("CPT"):
                continue
            cpt = map_detail_cpt_row(cols)
            unq = cpt["unique_key"]
            if unq not in header_map:
                raise ValueError(f"Missed Header information for the Unique Key :{unq}")

            parent = header_map[unq]
            cpt["carrier_claim_number"] = parent["carrier_claim_number"]
            cpt["carrier_id"] = parent["carrier_id"]

            comp_key = (
                f"{unq}-{cpt['eob_id']}-{cpt['bill_type']}-"
                f"{cpt['eob_revision_num']}-{cpt['check_number_key']}-{cpt['alphabet_key']}"
            )
            if comp_key not in paylog_map:
                raise ValueError(f"Missed Paylog detail information for the key :{comp_key}")

            cpt["carrier_paylog_id"] = paylog_map[comp_key]
            dao.insert_tmp_rfr_paylog_cpt(cpt)
            cpt_count += 1
    conn.commit()
    logger.info("Step 4 completed: %d CPS CPT rows inserted.", cpt_count)

    # ==========================================================================
    # STEP 5: validateCpsFiles (FileValidator.java)
    # ==========================================================================
    logger.info("Step 5: Running FileValidator across CPS staging tables...")
    h_keys, d_pairs, c_pairs = dao.fetch_validation_keys()
    if not FileValidator.validate_staging_tables(h_keys, d_pairs, c_pairs):
        logger.error("Step 5 FAILED: File cross-validation failed. Sending cpsRejectMail...")
        send_email_notification(
            subject=os.getenv("CPS_REJECT_MAIL_SUBJECT", "CPS RFR Batch Job Failed - File Validation"),
            body=os.getenv("CPS_REJECT_MAIL_BODY", "CPS RFR Flat File Cross-Validation Failed."),
        )
        raise RuntimeError("bisCpsToMccaJob halted at Step 5 (validateCpsFiles FAILED).")

    # ==========================================================================
    # STEP 6: rfrHeaderStep (RfrHeaderProcessor.java)
    # ==========================================================================
    logger.info("Step 6: Validating CPS RFR headers/paylogs/CPTs and submitting to MMS REST API...")
    tmp_headers = dao.fetch_all_tmp_headers()
    for rfr in tmp_headers:
        rfr["pending_status"] = False
        rfr["submit_err_msg"] = None

        # V1: Previous RFR pending check
        if dao.is_previous_rfr_submitted(rfr["carrier_claim_number"]):
            rfr["pending_status"] = True

        # V2: Header-level RFRValidator.validate
        RFRValidator.validate(rfr)

        paylogs = dao.fetch_tmp_paylogs_by_unique_key(rfr["unique_key"])
        cpt_by_paylog_id: Dict[int, List[Dict[str, Any]]] = {}

        if paylogs:
            for detail in paylogs:
                paylog_uid = int(detail["paylog_unique_id"])
                cpt_list = dao.fetch_tmp_cpts_by_paylog(rfr["unique_key"], paylog_uid)
                cpt_by_paylog_id[paylog_uid] = cpt_list

                # V3: Bill amount valid
                if RFRValidator.is_bill_amount_valid(detail):
                    RFRValidator.append_error(rfr, "billedAmt,totalMccaPaymentReq")
                    rfr["pending_status"] = True

                # V4: Correction check
                if RFRValidator.is_correction(detail):
                    RFRValidator.append_error(rfr, "payeeOrProvider")
                    rfr["pending_status"] = True
                    detail["corrections_indicator"] = "Y"
                    dao.update_tmp_paylog_correction(detail)

                # V5: Bill type valid
                if not RFRValidator.is_bill_type_valid(detail, rfr_cpt_eff_date):
                    RFRValidator.append_error(rfr, "billType")
                    rfr["pending_status"] = True

                # V6: Service facility zip valid
                if not RFRValidator.is_service_facility_zip_valid(detail):
                    RFRValidator.append_error(rfr, "serviceFacilityZipcode")
                    rfr["pending_status"] = True

                # V7: CPT required & valid
                if RFRValidator.is_cpt_required(detail):
                    if not RFRValidator.is_cpt_list_valid(detail, cpt_list):
                        RFRValidator.append_error(rfr, "rfrDetailCpt")
                        rfr["pending_status"] = True

                # V8 - V12: March 2022 Validations
                RFRValidator.validate_tin_npi(detail, rfr, cpt_list)
                RFRValidator.validate_ub_bill_type_field(detail, rfr)
                RFRValidator.validate_cpt_codes(detail, cpt_list, rfr)
                RFRValidator.validate_non_mandatory_cpt_codes(detail, cpt_list, rfr)
                RFRValidator.validate_revenue_codes(detail, cpt_list, rfr)
                RFRValidator.validate_pay_code_bill_type(detail, rfr, rfr_cpt_eff_date)

        # Submit to MMS API if all validations passed
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

        dao.insert_main_rfr_header(rfr)
    conn.commit()

    # ==========================================================================
    # STEP 7: rfrDetailStep
    # ==========================================================================
    copied_paylogs = dao.copy_tmp_paylogs_to_main()
    conn.commit()
    logger.info("Step 7 completed: Copied %d paylogs to MCCA_RFR_PAYLOG.", copied_paylogs)

    # ==========================================================================
    # STEP 8: rfrDetailCptStep
    # ==========================================================================
    copied_cpts = dao.copy_tmp_cpts_to_main()
    conn.commit()
    logger.info("Step 8 completed: Copied %d CPT rows to MCCA_RFR_PAYLOG_CPT.", copied_cpts)

    # ==========================================================================
    # STEP 9: cpsSuccessMailStep (MailImpl.java)
    # ==========================================================================
    logger.info("Step 9: Sending cpsSuccessMail notification...")
    send_email_notification(
        subject=os.getenv("CPS_SUCCESS_MAIL_SUBJECT", "CPS RFR Batch Job Completed Successfully"),
        body=os.getenv("CPS_SUCCESS_MAIL_BODY", "CPS RFR Monthly Batch Job completed successfully."),
    )

    # ==========================================================================
    # STEP 10: clearCpsTempTables (DBUtils.java)
    # ==========================================================================
    logger.info("Step 10: Clearing MCCA_CPS_TMP_RFR* tables...")
    dao.clear_cps_temp_tables()
    logger.info("bisCpsToMccaJob completed all 10 steps successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Job 1: bisCpsToMccaJob (CPS RFR Batch Job)")
    parser.add_argument("--header-file", required=True, help="Path to CPS RFR Header flat file")
    parser.add_argument("--detail-file", required=True, help="Path to CPS RFR Detail flat file")
    parser.add_argument(
        "--cpt-effective-date",
        default=os.getenv("RFR_CPT_EFFECTIVE_DATE", "2019-01-01"),
        help="RFR CPT effective date in YYYY-MM-DD format",
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
        run_bis_cps_to_mcca_job(
            conn=conn,
            header_file_path=args.header_file,
            detail_file_path=args.detail_file,
            rfr_cpt_eff_date=eff_date,
            schema=args.schema,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
