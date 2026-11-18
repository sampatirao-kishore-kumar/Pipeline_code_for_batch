"""
MCCA MMS REST API Client & JSON Builder for RFR Submissions.
Direct port of:
  - com.acg.mcca.batch.processor.restClient.OAuthClient
  - com.acg.mcca.batch.processor.restClient.RfrRestMapper
  - com.acg.mcca.batch.processor.restClient.RfrJsonBuilder
  - com.acg.mcca.batch.processor.restClient.RfrRestClient
"""

import logging
import os
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)


def fmt_currency(val: Any) -> str:
    """Formats currency to 2 decimal places matching DecimalFormat('0.00')."""
    if val is None or val == "":
        return "0.00"
    d = Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return str(d)


def fmt_date(val: Any) -> str:
    """Formats date as yyyy-MM-dd."""
    if val is None:
        return ""
    if isinstance(val, (date, datetime)):
        return val.strftime("%Y-%m-%d")
    return str(val).strip()


def split_tin_npi(federal_tin: Optional[str]) -> Tuple[str, str]:
    """Port of RfrJsonBuilder.splitTinNpi: splits 'TIN,NPI' on comma."""
    if not federal_tin:
        return "", ""
    parts = str(federal_tin).split(",")
    tin = parts[0].strip() if len(parts) > 0 else ""
    npi = parts[1].strip() if len(parts) > 1 else ""
    return tin, npi


class RfrJsonBuilder:
    """Port of RfrRestMapper.java and RfrJsonBuilder.java."""

    @staticmethod
    def build_rfr_payload(
        rfr: Dict[str, Any],
        paylogs: List[Dict[str, Any]],
        cpt_by_paylog_id: Dict[int, List[Dict[str, Any]]],
        rfr_cpt_eff_date: date,
    ) -> Dict[str, Any]:
        payments_json: List[Dict[str, Any]] = []
        for detail in paylogs:
            tin, npi = split_tin_npi(detail.get("federal_tin"))
            end_dt = detail.get("service_end_date")
            raw_bill_type = str(detail.get("bill_type") or "").strip()

            # RfrRestMapper conditional BillType assignment
            mapped_bill_type: Optional[str] = None
            if end_dt is not None:
                if end_dt >= rfr_cpt_eff_date:
                    mapped_bill_type = raw_bill_type
            else:
                mapped_bill_type = "MISC"

            pmt_obj: Dict[str, Any] = {
                "ServiceStartDt": fmt_date(detail.get("service_start_date")),
                "ServiceEndDt": fmt_date(detail.get("service_end_date")),
                "PayCode": str(detail.get("pay_code") or "").strip(),
                "NumberOfHours": str(int(detail.get("number_of_hours") or 0)),
                "CheckNumber": str(detail.get("check_number") or "").strip(),
                "CheckDt": fmt_date(detail.get("check_date")),
                "PayeeProvider": str(detail.get("payee_or_provider") or "").strip(),
                "TIN": tin,
                "NPI": npi,
                "CostShareAmount": fmt_currency(detail.get("cost_share_amount")),
                "BilledAmount": fmt_currency(detail.get("bill_amount")),
                "RepricedPaidAmount": fmt_currency(detail.get("repriced_paid_amt")),
                "BillReviewFees": fmt_currency(detail.get("bill_review_fees")),
                "PpoFees": fmt_currency(detail.get("ppo_fees")),
                "NegotiatedDiscount": fmt_currency(detail.get("ppo_or_other_negotiated_discount")),
                "DescriptionOfService": str(detail.get("service_description") or "").strip(),
                "CarrierCheckTotal": fmt_currency(detail.get("carrier_check_total")),
                "RxInd": str(detail.get("rx_indicator") or "").strip(),
                "NDCNumber": str(detail.get("ndc_number") or "").strip(),
                "DaysSupply": str(int(detail.get("days_supply") or 0)),
                "Quantity": str(int(detail.get("quantity") or 0)),
                "DAWCode": str(detail.get("dispense_as_written_code") or "").strip(),
                "PrescriberNPI": str(detail.get("prescriber_npi") or "").strip(),
                "DRGCode": str(detail.get("drg_code") or "").strip(),
                "PatientStatus": str(detail.get("patient_status") or "").strip(),
                "AdmissionDt": fmt_date(detail.get("admit_date")),
                "DischargeDt": fmt_date(detail.get("discharge_date")),
                "ServiceFacilityPostalCode": str(detail.get("service_facility_zipcode") or "").strip(),
                "AdmissionSource": str(detail.get("admission_source") or "").strip(),
                "AdmissionType": str(detail.get("admission_type") or "").strip(),
                "ICD1": str(detail.get("icd1") or "").strip(),
                "ICD2": str(detail.get("icd2") or "").strip(),
                "ICD3": str(detail.get("icd3") or "").strip(),
                "ICD4": str(detail.get("icd4") or "").strip(),
                "ICD5": str(detail.get("icd5") or "").strip(),
                "ICD6": str(detail.get("icd6") or "").strip(),
                "ICD7": str(detail.get("icd7") or "").strip(),
            }

            if mapped_bill_type:
                pmt_obj["BillType"] = mapped_bill_type
                if mapped_bill_type == "UB04":
                    pmt_obj["BillTypeUB04"] = str(detail.get("ub_bill_type") or "").strip()

                if mapped_bill_type in ("1500", "UB04"):
                    paylog_uid = detail.get("paylog_unique_id")
                    cpt_rows = cpt_by_paylog_id.get(paylog_uid, [])
                    proc_codes: List[Dict[str, Any]] = []
                    for cpt in cpt_rows:
                        proc_codes.append({
                            "ServiceStartDate": fmt_date(cpt.get("service_start_date")),
                            "ServiceEndDate": fmt_date(cpt.get("service_end_date")),
                            "PlaceOfService": str(cpt.get("service_location") or "").strip(),
                            "CPTCode": str(cpt.get("cpt_code") or "").strip(),
                            "Modifier1": str(cpt.get("modifier1") or "").strip(),
                            "Modifier2": str(cpt.get("modifier2") or "").strip(),
                            "Modifier3": str(cpt.get("modifier3") or "").strip(),
                            "Modifier4": str(cpt.get("modifier4") or "").strip(),
                            "UnitsOfService": str(int(cpt.get("service_units") or 0)),
                            "TotalChargesBilled": fmt_currency(cpt.get("total_charges")),
                            "TotalChargesApproved": fmt_currency(cpt.get("total_charges_carrier_approved")),
                            "RevenueCode": str(cpt.get("revenue_code") or "").strip(),
                            "RenderingProviderNPI": str(cpt.get("prescriber_npi") or "").strip(),
                            "ICD1": str(cpt.get("icd1") or "").strip(),
                            "ICD2": str(cpt.get("icd2") or "").strip(),
                            "ICD3": str(cpt.get("icd3") or "").strip(),
                            "ICD4": str(cpt.get("icd4") or "").strip(),
                            "ICD5": str(cpt.get("icd5") or "").strip(),
                            "ICD6": str(cpt.get("icd6") or "").strip(),
                            "ICD7": str(cpt.get("icd7") or "").strip(),
                            "ICD8": str(cpt.get("icd8") or "").strip(),
                            "ICD9": str(cpt.get("icd9") or "").strip(),
                            "ICD10": str(cpt.get("icd10") or "").strip(),
                        })
                    pmt_obj["ProcedureCodes"] = proc_codes

            payments_json.append(pmt_obj)

        return {
            "dataClaim": {
                "MCCAClaimNumber": str(rfr.get("mcca_claim_number") or "").strip(),
                "CarrierClaimNumber": str(rfr.get("carrier_claim_number") or "").strip(),
                "TotalBilledAmount": fmt_currency(rfr.get("total_amt_billed")),
                "TotalBillReviewFees": fmt_currency(rfr.get("total_bill_review_fees")),
                "TotalMCCAPaymentRequested": fmt_currency(rfr.get("total_mcca_payment_req")),
                "DeductibleAppliedAmount": fmt_currency(rfr.get("deductible_amount")),
                "CarrierAdjusterName": str(rfr.get("adjuster_name") or "").strip(),
                "Insured": {
                    "FirstName": str(rfr.get("insured_first_name") or "").strip(),
                    "MiddleName": str(rfr.get("insured_middle_init") or "").strip(),
                    "LastName": str(rfr.get("insured_last_name") or "").strip(),
                },
                "Claimant": {
                    "FirstName": str(rfr.get("claimant_first_name") or "").strip(),
                    "MiddleName": str(rfr.get("claimant_middle_init") or "").strip(),
                    "LastName": str(rfr.get("claimant_last_name") or "").strip(),
                },
                "CarrierGroup": {
                    "Carriers": [
                        {"CarrierID": str(rfr.get("carrier_id") or "").strip()}
                    ]
                },
                "Payments": payments_json,
            }
        }


class MMSRestClient:
    """Port of OAuthClient.java and RfrRestClient.java."""

    def __init__(self) -> None:
        self.token_url = os.getenv(
            "MMS_TOKEN_URL", "https://adfs.micatastrophic.com/adfs/oauth2/token"
        )
        self.rfr_submit_url = os.getenv(
            "MMS_RFR_SUBMIT_URL", "https://carrierservices.hft2.mccatest.com/api/v1/Claim/Rfr"
        )
        self.client_id = os.getenv("MMS_CLIENT_ID", "64f2df60-0ea9-4def-befc-77e99ab6892d")
        self.client_secret = os.getenv(
            "MMS_CLIENT_SECRET", "I1Do7yxl7AWdhAvo1pMhipQcB5b70DHxHtzRTUia"
        )
        self.grant_type = os.getenv("MMS_GRANT_TYPE", "client_credentials")

    def get_token(self) -> str:
        payload = {
            "grant_type": self.grant_type,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        resp = requests.post(self.token_url, data=payload, verify=False, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"OAuth2 token generation failed ({resp.status_code}): {resp.text}")
        return resp.json()["access_token"]

    def submit_rfr(self, payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Submits RFR JSON payload to MMS REST API.
        Returns (is_success, submit_err_msg_truncated_to_740_chars).
        """
        try:
            token = self.get_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            resp = requests.post(
                self.rfr_submit_url, json=payload, headers=headers, verify=False, timeout=60
            )
            body = resp.json() if resp.text else {}
            errors = body.get("errors")
            if resp.status_code in (200, 201) and not errors:
                return True, None

            # Concatenate error descriptions per RfrHeaderProcessor.process
            err_parts: List[str] = []
            if isinstance(errors, dict):
                for val in errors.values():
                    if isinstance(val, list):
                        err_parts.extend(str(x) for x in val)
                    else:
                        err_parts.append(str(val))
            elif isinstance(errors, list):
                err_parts.extend(str(x) for x in errors)
            else:
                err_parts.append(resp.text or f"HTTP {resp.status_code}")

            err_msg = " ".join(err_parts).strip()
            if len(err_msg) > 740:
                err_msg = err_msg[:740]
            return False, err_msg
        except Exception as exc:
            logger.exception("Exception submitting RFR to MMS REST API")
            msg = str(exc)
            return False, msg[:740]
