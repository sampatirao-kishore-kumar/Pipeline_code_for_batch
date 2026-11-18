"""
RFR Business Validators for CPS & Meemic Batch Jobs.
Direct port of:
  - com.acg.mcca.batch.util.RFRValidator
  - com.acg.mcca.batch.util.DataValidator
  - com.acg.mcca.batch.util.BatchConstants
  - com.acg.mcca.batch.processor.FileValidator
"""

import logging
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ==============================================================================
# BatchConstants.java Constants
# ==============================================================================
INITIAL_BILL_SEQ_NUM = "001"
FACTS_INITIAL_BILL_SEQ_NUM = "1"
PAYEE_CORRECTIONS = "CORRECTIONS"
PAYEE_SAL_SUB_RECEIPT = "SAL/SUB RECEIPT"

BILL_TYPE_MISC = "MISC"
BILL_TYPE_1500 = "1500"
BILL_TYPE_UB04 = "UB04"
BILL_TYPE_LIST = {BILL_TYPE_MISC, BILL_TYPE_1500, BILL_TYPE_UB04}

UB_PAYCODE_LIST = {"HOSP", "DRLB", "REHA", "ACAG", "RESI"}
CMS1500_PAYCODE_LIST = {
    "HOSP", "DRLB", "EQUP", "PROS", "RXSP",
    "REHA", "TRAN", "CSMT", "ACAG", "RESI",
}
UB_NPI_PAYCODE_LIST = {"HOSP", "DRLB", "REHA", "ACAG"}
CMS1500_NPI_PAYCODE_LIST = {"HOSP", "DRLB", "EQUP", "PROS", "REHA"}
NPI_EXEMPT_CPT_CODES = {"97124", "97140", "97537", "97113", "97530", "G0176"}

UB_MANDATORY_CPT_PAYCODE_LIST = {"DRLB", "REHA", "ACAG"}
CMS1500_MANDATORY_CPT_PAYCODE_LIST = {
    "HOSP", "DRLB", "EQUP", "PROS", "REHA",
    "TRAN", "CSMT", "ACAG", "RESI",
}
UB_NON_MANDATORY_CPT_PAYCODE_LIST = {"HOSP", "RESI"}
CMS1500_NON_MANDATORY_CPT_PAYCODE_LIST = {"RXSP"}

UB_EXCLUDED_PAYCODE_LIST = {
    "HOME", "VEHI", "EQUP", "PROS", "RXSP",
    "TRAN", "CSMT", "WLSL", "SERV", "OTHR", "ACFM",
}
CMS1500_EXCLUDED_PAYCODE_LIST = {"HOME", "VEHI", "WLSL", "SERV", "OTHR", "ACFM"}
MISC_EXCLUDED_PAYCODE_LIST = {"HOSP", "DRLB", "ACAG", "RESI"}


class DataValidator:
    """Port of com.acg.mcca.batch.util.DataValidator."""

    @staticmethod
    def is_null(val: Optional[str]) -> bool:
        return val is None or len(str(val).strip()) == 0

    @staticmethod
    def is_numeric(val: Optional[str]) -> bool:
        if val is None or len(str(val)) == 0:
            return False
        return bool(re.match(r"^[0-9]*$", str(val)))

    @staticmethod
    def is_alphanumeric(val: Optional[str]) -> bool:
        if val is None or len(str(val)) == 0:
            return False
        return bool(re.match(r"^[a-zA-Z0-9]*$", str(val)))


class RFRValidator:
    """Port of com.acg.mcca.batch.util.RFRValidator."""

    @staticmethod
    def append_error(rfr: Dict[str, Any], field_name: str) -> None:
        current = rfr.get("status") or ""
        fields = [f for f in current.split(",") if f]
        if field_name not in fields:
            rfr["status"] = f"{current},{field_name}" if current else field_name

    @classmethod
    def validate(cls, rfr: Dict[str, Any]) -> Dict[str, Any]:
        """Header-level validation (RFRValidator.validate)."""
        pending_status = bool(rfr.get("pending_status", False))

        if cls.is_total_bill_amount_valid(rfr):
            cls.append_error(rfr, "totalAmtBilled,totalMccaPaymentReq")
            pending_status = True

        if cls.is_cross_companion_claim(rfr):
            rfr["cross_companion_indicator"] = "Y"
            cls.append_error(rfr, "crossCompanionClaimNumber")
            pending_status = True
        else:
            rfr["cross_companion_indicator"] = "N"

        if cls.is_initial(rfr):
            cls.append_error(rfr, "billSequenceNumber")
            pending_status = True

        rfr["pending_status"] = pending_status
        rfr["status_indicator"] = "PN" if pending_status else "OK"
        return rfr

    @staticmethod
    def is_total_bill_amount_valid(rfr: Dict[str, Any]) -> bool:
        tot_req = float(rfr.get("total_mcca_payment_req") or 0.0)
        tot_billed = float(rfr.get("total_amt_billed") or 0.0)
        tot_fees = float(rfr.get("total_bill_review_fees") or 0.0)
        return tot_req > (tot_billed + tot_fees)

    @staticmethod
    def is_cross_companion_claim(rfr: Dict[str, Any]) -> bool:
        val = rfr.get("cross_companion_claim_number")
        return val is not None and str(val).strip() != ""

    @staticmethod
    def is_initial(rfr: Dict[str, Any]) -> bool:
        seq = str(rfr.get("bill_sequence_number") or "").strip()
        return seq in (INITIAL_BILL_SEQ_NUM, FACTS_INITIAL_BILL_SEQ_NUM)

    @staticmethod
    def is_bill_amount_valid(detail: Dict[str, Any]) -> bool:
        bill_amt = float(detail.get("bill_amount") or 0.0)
        tot_req = float(detail.get("total_mcca_payment_req") or 0.0)
        return bill_amt > 0.0 and tot_req > bill_amt

    @staticmethod
    def is_correction(detail: Dict[str, Any]) -> bool:
        payee = str(detail.get("payee_or_provider") or "").strip().upper()
        return payee in (PAYEE_CORRECTIONS, PAYEE_SAL_SUB_RECEIPT)

    @staticmethod
    def is_service_dates_valid(detail: Dict[str, Any]) -> str:
        start_dt = detail.get("service_start_date")
        end_dt = detail.get("service_end_date")
        if start_dt is None or end_dt is None:
            return "serviceStartDate,serviceEndDate"
        if start_dt > end_dt:
            return "serviceStartDate"
        return ""

    @staticmethod
    def is_bill_type_valid(detail: Dict[str, Any], rfr_cpt_eff_date: date) -> bool:
        bill_type = str(detail.get("bill_type") or "").strip()
        if DataValidator.is_null(bill_type) or bill_type not in BILL_TYPE_LIST:
            return False
        end_dt = detail.get("service_end_date")
        if end_dt is not None and end_dt < rfr_cpt_eff_date and bill_type != BILL_TYPE_MISC:
            return False
        return True

    @staticmethod
    def is_service_facility_zip_valid(detail: Dict[str, Any]) -> bool:
        bill_type = str(detail.get("bill_type") or "").strip()
        if not DataValidator.is_null(bill_type) and bill_type in (BILL_TYPE_1500, BILL_TYPE_UB04):
            if DataValidator.is_null(detail.get("service_facility_zipcode")):
                return False
        return True

    @staticmethod
    def is_cpt_required(detail: Dict[str, Any]) -> bool:
        bill_type = str(detail.get("bill_type") or "").strip()
        return bill_type in (BILL_TYPE_1500, BILL_TYPE_UB04)

    @classmethod
    def is_cpt_list_valid(cls, detail: Dict[str, Any], cpt_list: List[Dict[str, Any]]) -> bool:
        if not cpt_list:
            return False
        bill_type = str(detail.get("bill_type") or "").strip()
        for cpt in cpt_list:
            if not cls.is_cpt_valid(bill_type, cpt):
                return False
        return True

    @staticmethod
    def is_cpt_valid(bill_type: str, cpt: Dict[str, Any]) -> bool:
        if bill_type == BILL_TYPE_UB04 and DataValidator.is_null(cpt.get("revenue_code")):
            return False
        if bill_type in (BILL_TYPE_UB04, BILL_TYPE_1500):
            if (
                cpt.get("service_start_date") is None
                or float(cpt.get("total_charges") or 0.0) == 0.0
                or float(cpt.get("total_charges_carrier_approved") or 0.0) == 0.0
            ):
                return False
        if bill_type == BILL_TYPE_1500:
            if DataValidator.is_null(cpt.get("service_location")):
                return False
            start_dt = cpt.get("service_start_date")
            end_dt = cpt.get("service_end_date")
            if start_dt is not None and end_dt is not None:
                if start_dt != end_dt and int(cpt.get("service_units") or 0) == 0:
                    return False
        return True

    # ==========================================================================
    # March 2022 Validations
    # ==========================================================================
    @classmethod
    def validate_tin_npi(cls, detail: Dict[str, Any], rfr: Dict[str, Any], cpt_list: List[Dict[str, Any]]) -> None:
        bill_type = str(detail.get("bill_type") or "").strip()
        pay_code = str(detail.get("pay_code") or "").strip()
        if (bill_type == BILL_TYPE_UB04 and pay_code in UB_PAYCODE_LIST) or (
            bill_type == BILL_TYPE_1500 and pay_code in CMS1500_PAYCODE_LIST
        ):
            fed_tin = str(detail.get("federal_tin") or "")
            parts = fed_tin.split(",")
            tin = parts[0].strip() if len(parts) > 0 else ""
            npi = parts[1].strip() if len(parts) > 1 else ""

            if DataValidator.is_null(tin) or not DataValidator.is_numeric(tin) or len(tin) != 9:
                cls.append_error(rfr, "tin")
                rfr["pending_status"] = True

            if (bill_type == BILL_TYPE_UB04 and pay_code in UB_NPI_PAYCODE_LIST) or (
                bill_type == BILL_TYPE_1500 and pay_code in CMS1500_NPI_PAYCODE_LIST
            ):
                if pay_code == "REHA" and cls.is_npi_validation_exempt(cpt_list):
                    return
                if DataValidator.is_null(npi) or not DataValidator.is_numeric(npi) or len(npi) != 10:
                    cls.append_error(rfr, "npi")
                    rfr["pending_status"] = True

    @staticmethod
    def is_npi_validation_exempt(cpt_list: List[Dict[str, Any]]) -> bool:
        if not cpt_list:
            return False
        for cpt in cpt_list:
            code = str(cpt.get("cpt_code") or "").strip()
            if code and code not in NPI_EXEMPT_CPT_CODES:
                return False
        return True

    @classmethod
    def validate_ub_bill_type_field(cls, detail: Dict[str, Any], rfr: Dict[str, Any]) -> None:
        bill_type = str(detail.get("bill_type") or "").strip()
        pay_code = str(detail.get("pay_code") or "").strip()
        if bill_type == BILL_TYPE_UB04 and pay_code in UB_PAYCODE_LIST:
            ub = str(detail.get("ub_bill_type") or "").strip()
            valid = (
                not DataValidator.is_null(ub)
                and DataValidator.is_numeric(ub)
                and (len(ub) == 3 or (len(ub) == 4 and ub.startswith("0")))
            )
            if not valid:
                cls.append_error(rfr, "ubBillType")
                rfr["pending_status"] = True

    @classmethod
    def validate_cpt_codes(
        cls, detail: Dict[str, Any], cpt_list: List[Dict[str, Any]], rfr: Dict[str, Any]
    ) -> None:
        bill_type = str(detail.get("bill_type") or "").strip()
        pay_code = str(detail.get("pay_code") or "").strip()
        if (bill_type == BILL_TYPE_UB04 and pay_code in UB_MANDATORY_CPT_PAYCODE_LIST) or (
            bill_type == BILL_TYPE_1500 and pay_code in CMS1500_MANDATORY_CPT_PAYCODE_LIST
        ):
            if not cpt_list:
                return
            for cpt in cpt_list:
                code = str(cpt.get("cpt_code") or "").strip()
                if DataValidator.is_null(code) or len(code) != 5:
                    cls.append_error(rfr, "cptCode")
                    rfr["pending_status"] = True
                    break

    @classmethod
    def validate_non_mandatory_cpt_codes(
        cls, detail: Dict[str, Any], cpt_list: List[Dict[str, Any]], rfr: Dict[str, Any]
    ) -> None:
        bill_type = str(detail.get("bill_type") or "").strip()
        pay_code = str(detail.get("pay_code") or "").strip()
        if (bill_type == BILL_TYPE_UB04 and pay_code in UB_NON_MANDATORY_CPT_PAYCODE_LIST) or (
            bill_type == BILL_TYPE_1500 and pay_code in CMS1500_NON_MANDATORY_CPT_PAYCODE_LIST
        ):
            if not cpt_list:
                return
            for cpt in cpt_list:
                code = str(cpt.get("cpt_code") or "").strip()
                if not DataValidator.is_null(code):
                    if bill_type == BILL_TYPE_UB04 and pay_code == "RESI":
                        if len(code) > 13:
                            cls.append_error(rfr, "cptCode")
                            rfr["pending_status"] = True
                            break
                    elif (bill_type == BILL_TYPE_UB04 and pay_code == "HOSP") or (
                        bill_type == BILL_TYPE_1500 and pay_code == "RXSP"
                    ):
                        if len(code) != 5:
                            cls.append_error(rfr, "cptCode")
                            rfr["pending_status"] = True
                            break

    @classmethod
    def validate_revenue_codes(
        cls, detail: Dict[str, Any], cpt_list: List[Dict[str, Any]], rfr: Dict[str, Any]
    ) -> None:
        bill_type = str(detail.get("bill_type") or "").strip()
        pay_code = str(detail.get("pay_code") or "").strip()
        if bill_type == BILL_TYPE_UB04 and pay_code in UB_PAYCODE_LIST:
            if not cpt_list:
                return
            for cpt in cpt_list:
                rev = str(cpt.get("revenue_code") or "").strip()
                if DataValidator.is_null(rev) or not DataValidator.is_alphanumeric(rev) or len(rev) > 4:
                    cls.append_error(rfr, "revenueCode")
                    rfr["pending_status"] = True
                    break

    @classmethod
    def validate_pay_code_bill_type(
        cls, detail: Dict[str, Any], rfr: Dict[str, Any], rfr_cpt_eff_date: date
    ) -> None:
        if cls.is_pay_code_bill_type_validation_exempt(detail, rfr_cpt_eff_date):
            return
        bill_type = str(detail.get("bill_type") or "").strip()
        pay_code = str(detail.get("pay_code") or "").strip()
        eob_id = detail.get("eob_id")
        eob_str = str(eob_id).strip() if eob_id is not None else None

        invalid = (
            (bill_type == BILL_TYPE_UB04 and pay_code in UB_EXCLUDED_PAYCODE_LIST)
            or (bill_type == BILL_TYPE_1500 and pay_code in CMS1500_EXCLUDED_PAYCODE_LIST)
            or (bill_type == BILL_TYPE_MISC and pay_code in MISC_EXCLUDED_PAYCODE_LIST)
            or (bill_type == BILL_TYPE_MISC and pay_code == "REHA" and not (eob_str is None or eob_str == "0"))
        )
        if invalid:
            cls.append_error(rfr, "paycodeBillType")
            rfr["pending_status"] = True

    @classmethod
    def is_pay_code_bill_type_validation_exempt(
        cls, detail: Dict[str, Any], rfr_cpt_eff_date: date
    ) -> bool:
        bill_amt = float(detail.get("bill_amount") or 0.0)
        rep_paid = float(detail.get("repriced_paid_amt") or 0.0)
        end_dt = detail.get("service_end_date")
        if bill_amt == 0.0 and rep_paid == 0.0:
            return True
        if end_dt is not None and end_dt < rfr_cpt_eff_date:
            return True
        if cls.is_correction(detail):
            return True
        return False


class FileValidator:
    """Port of com.acg.mcca.batch.processor.FileValidator (Step 5)."""

    @staticmethod
    def validate_staging_tables(
        header_unq_list: List[str],
        detail_pairs: List[Tuple[str, int]],
        cpt_pairs: List[Tuple[str, int]],
    ) -> bool:
        is_valid = True
        if not header_unq_list or not detail_pairs:
            logger.error("Empty Header file or Detail file in staging tables.")
            return False

        header_set = set(header_unq_list)
        detail_unq_set = {u for u, _ in detail_pairs}
        paylog_id_set = {pid for _, pid in detail_pairs}

        for h_unq in header_unq_list:
            if h_unq not in detail_unq_set:
                logger.error("Missed Detail record for the Header Unique Key: %s", h_unq)
                is_valid = False

        for d_unq in detail_unq_set:
            if d_unq not in header_set:
                logger.error("Missed Header record for the Detail Unique Key: %s", d_unq)
                is_valid = False

        for c_unq, carrier_paylog_id in cpt_pairs:
            if carrier_paylog_id not in paylog_id_set:
                logger.error(
                    "Missed Detail record for CPT Unique Key: %s and Carrier Paylog ID: %s",
                    c_unq,
                    carrier_paylog_id,
                )
                is_valid = False

        return is_valid
