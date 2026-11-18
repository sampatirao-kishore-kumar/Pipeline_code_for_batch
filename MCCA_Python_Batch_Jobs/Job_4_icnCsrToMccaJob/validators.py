"""
ICN & CSR Business Validators for Job 4: icnCsrToMccaJob.
Direct port of:
  - com.acg.mcca.batch.util.ICNValidator
  - com.acg.mcca.batch.util.CSRValidator
  - com.acg.mcca.batch.util.DataValidator
  - com.acg.mcca.batch.util.BatchConstants (CLOSED_HEAD_INJURY_CODES)
"""

import re
from typing import Any, Dict, List, Optional

CLOSED_HEAD_INJURY_CODES = {
    "854.0", "854.00", "854.01", "854.02", "854.03",
    "854.04", "854.05", "854.06", "854.09",
    "S06.9X9A", "S06.2X9A",
}


def format_phone_number(phone: Optional[str]) -> str:
    """Port of formatPhoneNumber in IcnDetailProcessor / CsrDetailProcessor."""
    if not phone:
        return ""
    digits = re.sub(r"[^0-9]", "", str(phone).strip())
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return str(phone).strip()


def build_injury_description(row: Dict[str, Any]) -> str:
    """Port of injuryDescription concatenation from ICD1..ICD3 codes and descriptions."""
    parts: List[str] = []
    for i in (1, 2, 3):
        code = str(row.get(f"icd{i}_cd") or "").strip()
        desc = str(row.get(f"icd{i}_desc") or "").strip()
        if code and desc:
            parts.append(f"{code} - {desc}")
        elif code:
            parts.append(code)
        elif desc:
            parts.append(desc)
    combined = ", ".join(parts)
    return combined[:200] if len(combined) > 200 else combined


def detect_closed_head_injury(row: Dict[str, Any]) -> Optional[str]:
    """Port of CLOSED_HEAD_INJURY_CODES check in UpdateIcnTmpClaimProcessor."""
    for i in (1, 2, 3):
        code = str(row.get(f"icd{i}_cd") or "").strip()
        if code in CLOSED_HEAD_INJURY_CODES:
            return "CHI"
    return row.get("brain_inj_cd")


class ICNValidator:
    """Port of com.acg.mcca.batch.util.ICNValidator."""

    MANDATORY_FIELDS = [
        ("carrier_id", "carrierId"),
        ("naic_cd", "naicCode"),
        ("pol_num", "policyNumber"),
        ("pol_eff_dt", "effectiveDate"),
        ("pol_exp_dt", "expirationDate"),
        ("loss_dt", "dateOfLoss"),
        ("ins_fst_name", "insuredFirstName"),
        ("ins_lst_name", "insuredLastName"),
        ("clmt_fst_name", "claimantFirstName"),
        ("clmt_lst_name", "claimantLastName"),
        ("clmt_birth_dt", "birthDate"),
        ("clmt_gndr_cd", "gender"),
        ("inj_desc", "injuryDescription"),
        ("mcca_stat_cd", "mccaStatusCode"),
        ("mcca_rel_cd", "mccaRelationCode"),
        ("accd_dt", "accidentDate"),
        ("accd_desc", "accidentDescription"),
    ]

    @classmethod
    def validate(cls, claim: Dict[str, Any]) -> Dict[str, Any]:
        errors: List[str] = []
        for col_key, err_name in cls.MANDATORY_FIELDS:
            val = claim.get(col_key)
            if val is None or str(val).strip() == "" or (col_key == "carrier_id" and int(val or 0) == 0):
                errors.append(err_name)

        if float(claim.get("tot_res_amt") or 0.0) <= 0.0 and float(claim.get("cum_amt_paid_to_dt") or 0.0) <= 0.0:
            errors.append("totalReserve,cumulativePaidToDate")

        claim["err_ele_list"] = ",".join(errors) if errors else None
        claim["status"] = "IC" if errors else "PN"
        return claim


class CSRValidator:
    """Port of com.acg.mcca.batch.util.CSRValidator."""

    MANDATORY_FIELDS = [
        ("carrier_id", "carrierId"),
        ("mcca_clm_num", "mccaClaimNumber"),
        ("pol_num", "policyNumber"),
        ("loss_dt", "dateOfLoss"),
        ("clmt_fst_name", "claimantFirstName"),
        ("clmt_lst_name", "claimantLastName"),
        ("mcca_stat_cd", "mccaStatusCode"),
    ]

    @classmethod
    def validate(cls, claim: Dict[str, Any]) -> Dict[str, Any]:
        errors: List[str] = []
        for col_key, err_name in cls.MANDATORY_FIELDS:
            val = claim.get(col_key)
            if val is None or str(val).strip() == "" or (col_key == "carrier_id" and int(val or 0) == 0):
                errors.append(err_name)

        claim["err_ele_list"] = ",".join(errors) if errors else None
        claim["status"] = "IC" if errors else "PN"
        return claim
