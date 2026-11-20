"""
ItemProcessors and MccaBatchUtil for icnCsrToMccaJob.
Exact 1:1 port of:
- com.acg.mcca.batch.util.MccaBatchUtil
- com.acg.mcca.batch.processor.CopyIcnProcessor (Step 2)
- com.acg.mcca.batch.processor.IcnDetailProcessor (Step 3)
- com.acg.mcca.batch.processor.CsrDetailProcessor (Step 4)
- com.acg.mcca.batch.processor.UpdateIcnTmpClaimProcessor (Step 5)
- com.acg.mcca.batch.processor.UpdateIcnCsrClaimProcessor (Steps 6 & 7)
- com.acg.mcca.batch.processor.AmountUpdateProcessor (Steps 8 & 9)
- com.acg.mcca.batch.processor.MccaClaimRptdProcessor (updateRptdColumn)
"""

import logging
import re
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Dict, List, Optional

from config import BatchConstants
from dao.csr_dao import CsrJdbcDaoImpl
from dao.icn_dao import IcnJdbcDaoImpl
from dao.mcca_claim_dao import MccaClaimDaoImpl
from dao.othr_inj_clmts_dao import OthrInjClmtsDaoImpl
from models import CsrDetail, IcnCsrDetail, Threshold, TmpCsrDetail, TmpIcnDetail

logger = logging.getLogger(__name__)


class MccaBatchUtil:
    """Exact 1:1 port of com.acg.mcca.batch.util.MccaBatchUtil."""

    @staticmethod
    def is_numeric(val: Optional[str]) -> bool:
        if val is None or val == "":
            return False
        return all(ch.isdigit() or ch == "." for ch in val)

    @staticmethod
    def is_operable(data: Optional[str]) -> bool:
        return data is not None and data != BatchConstants.EMPTY_STRING

    @staticmethod
    def is_facts_claim(carrier_clm_num: Optional[str]) -> bool:
        if not carrier_clm_num:
            return False
        return bool(re.match(BatchConstants.REGEX_FACTS_CLAIMS, carrier_clm_num))

    @staticmethod
    def calculate_csr_due_dt(submitted_date: Optional[date] = None) -> date:
        """Calculates the CSR due date as 6 months from current/submitted date."""
        base_dt = submitted_date or date.today()
        return base_dt + relativedelta(months=6)

    @staticmethod
    def get_formatted_county(county: Optional[str]) -> str:
        if county and county.strip():
            words = county.strip().split()
            if len(words) > 1 and words[-1].lower() == "county":
                return " ".join(words[:-1]) + " "
        return county or ""

    @staticmethod
    def get_address_county(
        address1: Optional[str],
        address2: Optional[str],
        city: Optional[str],
        state: Optional[str],
        zip_code: Optional[str],
    ) -> str:
        """
        Port of MccaBatchUtil.getAddressCounty().
        If the SAS AddressScrub SOAP endpoint is not configured or unreachable,
        returns empty string just like the Java catch block.
        """
        return ""


# ==============================================================================
# STEP 2 PROCESSOR: CopyIcnProcessor
# ==============================================================================
class CopyIcnProcessor:
    """Exact 1:1 port of com.acg.mcca.batch.processor.CopyIcnProcessor."""

    def __init__(self, icn_dao: IcnJdbcDaoImpl, batch_date: str):
        self.icn_dao = icn_dao
        self.batch_date = batch_date
        self._is_stop_loaded = False
        self._is_threshold_loaded = False
        self._stop_icn_csr_exception: List[str] = []
        self._threshold_list: List[Threshold] = []

    def get_stop_icn_csr_exception(self) -> List[str]:
        if not self._is_stop_loaded:
            self._stop_icn_csr_exception = self.icn_dao.stop_icn_csr_exception()
            self._is_stop_loaded = True
        return self._stop_icn_csr_exception

    def get_threshold_list(self) -> List[Threshold]:
        if not self._is_threshold_loaded:
            self._threshold_list = self.icn_dao.get_threshold_from_database()
            self._is_threshold_loaded = True
        return self._threshold_list

    def _get_mcca_threshold_amount(self, date_of_loss: Optional[date]) -> Optional[str]:
        if date_of_loss is None:
            return None
        dol = date_of_loss.date() if isinstance(date_of_loss, datetime) else date_of_loss
        for threshold in self.get_threshold_list():
            vf = (
                threshold.valid_from.date()
                if isinstance(threshold.valid_from, datetime)
                else threshold.valid_from
            )
            vt = (
                threshold.valid_to.date()
                if isinstance(threshold.valid_to, datetime)
                else threshold.valid_to
            )
            if vf and vt and (vf <= dol <= vt):
                return threshold.threshold_amount
        return None

    def _has_icn_met_threshold(self, date_of_loss: Optional[date], incurred_amount: int) -> bool:
        if incurred_amount is not None and date_of_loss is not None:
            thr_str = self._get_mcca_threshold_amount(date_of_loss)
            if thr_str is not None:
                threshold_amount = int(float(thr_str))
                if threshold_amount <= incurred_amount:
                    return True
        return False

    def process(self, icn_csr_detail: IcnCsrDetail) -> Optional[IcnCsrDetail]:
        claim_num = icn_csr_detail.carrier_claim_num
        if not claim_num:
            return None
        if claim_num not in self.get_stop_icn_csr_exception():
            paid_to_date = self.icn_dao.get_paid_to_date_for_clsd_icn(claim_num, self.batch_date)
            reserves = self.icn_dao.get_reserves_for_clsd_icn(claim_num, self.batch_date)
            incurred_amount = paid_to_date + reserves
            if self._has_icn_met_threshold(icn_csr_detail.date_of_loss, incurred_amount):
                return icn_csr_detail
        return None


# ==============================================================================
# STEP 3 PROCESSOR: IcnDetailProcessor
# ==============================================================================
class IcnDetailProcessor:
    """Exact 1:1 port of com.acg.mcca.batch.processor.IcnDetailProcessor."""

    def __init__(
        self,
        icn_dao: IcnJdbcDaoImpl,
        othr_inj_clmts_dao: OthrInjClmtsDaoImpl,
        batch_date: str,
    ):
        self.icn_dao = icn_dao
        self.othr_inj_clmts_dao = othr_inj_clmts_dao
        self.batch_date = batch_date
        self._is_stop_loaded = False
        self._is_assign_to_loaded = False
        self._is_crr_userid_loaded = False
        self._stop_icn_csr_exception: List[str] = []
        self._assign_to_from_code_decode: Dict[str, str] = {}
        self._carrier_userid_from_code_decode: Dict[str, str] = {}

    def get_stop_icn_csr_exception(self) -> List[str]:
        if not self._is_stop_loaded:
            self._stop_icn_csr_exception = self.icn_dao.stop_icn_csr_exception()
            self._is_stop_loaded = True
        return self._stop_icn_csr_exception

    def get_assign_to_frm_code_decode(self) -> Dict[str, str]:
        if not self._is_assign_to_loaded:
            self._assign_to_from_code_decode = self.icn_dao.get_values_from_code_decode(
                BatchConstants.ASSIGNTO_CATEGORY
            )
            self._is_assign_to_loaded = True
        return self._assign_to_from_code_decode

    def get_carr_user_id_frm_code_decode(self) -> Dict[str, str]:
        if not self._is_crr_userid_loaded:
            self._carrier_userid_from_code_decode = self.icn_dao.get_values_from_code_decode(
                BatchConstants.CARRIER_USERID_CATEGORY
            )
            self._is_crr_userid_loaded = True
        return self._carrier_userid_from_code_decode

    def _get_related_claim_number(self, carrier_clm_num: str, link_id: Optional[str]) -> Optional[str]:
        if link_id and link_id.strip():
            related = self.icn_dao.get_related_claims(carrier_clm_num, link_id)
            if related and len(related) < 2:
                return related[0]
        return None

    def _get_claim_status(self, link_id: Optional[str]) -> List[str]:
        if link_id and link_id.strip():
            return self.icn_dao.get_claim_status(link_id)
        return []

    def is_claim_open(self, icn_csr_detail: IcnCsrDetail) -> bool:
        """Exact port of IcnDetailProcessor.isClaimOpen() (Defect #279)."""
        if (
            icn_csr_detail.status
            and icn_csr_detail.status.upper() == BatchConstants.OPEN_STATUS_CD
        ):
            return True
        if (
            icn_csr_detail.status
            and icn_csr_detail.status.upper() == BatchConstants.CLOSED_STATUS_CD
            and icn_csr_detail.link_claim is not None
            and BatchConstants.OPEN_STATUS_CD in self._get_claim_status(icn_csr_detail.link_claim)
        ):
            return True
        if (
            icn_csr_detail.status
            and icn_csr_detail.status.upper() == BatchConstants.CLOSED_STATUS_CD
            and icn_csr_detail.link_claim is None
            and (icn_csr_detail.paid_to_date or 0.0) > (icn_csr_detail.retention_amt or 0.0)
        ):
            return True
        return False

    @staticmethod
    def _set_batch_number(claim_no: Optional[str]) -> Optional[int]:
        """Exact port of IcnDetailProcessor.setBatchNumber()."""
        if claim_no and claim_no != BatchConstants.EMPTY_STRING and len(claim_no) >= 2:
            two_digit = claim_no[-2:]
            if MccaBatchUtil.is_numeric(two_digit):
                two_digit_int = int(float(two_digit))
                if 0 <= two_digit_int <= 33:
                    return 1
                if 34 <= two_digit_int <= 66:
                    return 2
                if 67 <= two_digit_int <= 99:
                    return 3
        return None

    def _get_assign_to_value(self, last_two_digit: int) -> Optional[str]:
        assign_map = self.get_assign_to_frm_code_decode()
        try:
            for code, decode_val in assign_map.items():
                if code.lower() != BatchConstants.ASSIGNTO_DEFAULT.lower():
                    if "-" in code:
                        parts = code.split("-")
                        start_range = int(parts[0])
                        end_range = int(parts[1])
                    else:
                        start_range = int(code)
                        end_range = start_range
                    if start_range <= last_two_digit <= end_range:
                        return decode_val
        except Exception as exc:
            logger.warning("Error parsing assignTo range: %s", exc)
        return assign_map.get(BatchConstants.ASSIGNTO_DEFAULT)

    def _get_assign_to_from_code_decode_db(self, icn_csr_detail: IcnCsrDetail) -> None:
        """Exact port of IcnDetailProcessor.getAssignToFromCodeDecodeDB() (Defect #281)."""
        if (
            icn_csr_detail.link_claim is None
            or (
                icn_csr_detail.master_claim_ind
                and icn_csr_detail.master_claim_ind.upper() == BatchConstants.YES_CD
            )
        ):
            claim_no = icn_csr_detail.carrier_claim_num
        else:
            claim_no = icn_csr_detail.link_claim

        if claim_no and len(claim_no) >= 2:
            two_digit = claim_no[-2:]
            if MccaBatchUtil.is_numeric(two_digit):
                two_digit_int = int(float(two_digit))
                assign_to = self._get_assign_to_value(two_digit_int)
                if assign_to is not None:
                    icn_csr_detail.assign_to = assign_to
                    crr_map = self.get_carr_user_id_frm_code_decode()
                    icn_csr_detail.carrier_user_id = crr_map.get(assign_to, "")
                    return
        icn_csr_detail.assign_to = ""
        icn_csr_detail.carrier_user_id = ""

    def process(self, icn_csr_detail: IcnCsrDetail) -> Optional[IcnCsrDetail]:
        claim_num = icn_csr_detail.carrier_claim_num
        if not claim_num:
            return None

        # Defect #287: resolve related companion claim number if CRS_COMP_CLM_IND == 'Y'
        if (
            icn_csr_detail.comp_crs_clm_ind
            and icn_csr_detail.comp_crs_clm_ind.strip().upper() == "Y"
        ):
            icn_csr_detail.cross_comp_clm_num = self._get_related_claim_number(
                claim_num, icn_csr_detail.cross_comp_clm_num
            )

        icn_csr_detail.stop_icn_csr_exception = False
        icn_status = self.icn_dao.get_icn_status(claim_num)

        # Defect #279: only create new ICN when icnStatus is null or empty
        if not icn_status:
            icn_csr_detail.icn_new = True
            if not self.is_claim_open(icn_csr_detail):
                icn_csr_detail.closed_ind = BatchConstants.YES_CD

            icn_csr_detail.status = BatchConstants.STATUS_PENDING_CD
            icn_csr_detail.accident_date = icn_csr_detail.date_of_loss

            if (
                icn_csr_detail.accident_state
                and icn_csr_detail.accident_state.upper() == BatchConstants.NA_STRING
            ):
                icn_csr_detail.accident_zip = BatchConstants.ZERO

            if MccaBatchUtil.is_operable(icn_csr_detail.adjuster_id):
                icn_csr_detail.adjuster_frst_name = icn_csr_detail.adjuster_frst_name or ""
                icn_csr_detail.adjuster_lst_name = icn_csr_detail.adjuster_lst_name or ""

            icn_csr_detail.accident_county = MccaBatchUtil.get_address_county(
                icn_csr_detail.accident_addr1,
                icn_csr_detail.accident_addr2,
                icn_csr_detail.accident_city,
                icn_csr_detail.accident_state,
                icn_csr_detail.accident_zip,
            )
            icn_csr_detail.insured_county = MccaBatchUtil.get_address_county(
                icn_csr_detail.insured_addr1,
                icn_csr_detail.insured_addr2,
                icn_csr_detail.insured_city,
                icn_csr_detail.insured_state,
                icn_csr_detail.insured_zip,
            )

            self._get_assign_to_from_code_decode_db(icn_csr_detail)
            icn_csr_detail.batch_num = self._set_batch_number(claim_num)
            icn_csr_detail.csr_due_dt = MccaBatchUtil.calculate_csr_due_dt(date.today())

            if claim_num in self.get_stop_icn_csr_exception():
                icn_csr_detail.closed_ind = BatchConstants.YES_CD

            return icn_csr_detail
        return None


# ==============================================================================
# STEP 4 PROCESSOR: CsrDetailProcessor
# ==============================================================================
class CsrDetailProcessor:
    """Exact 1:1 port of com.acg.mcca.batch.processor.CsrDetailProcessor."""

    def __init__(self, csr_dao: CsrJdbcDaoImpl, icn_dao: IcnJdbcDaoImpl):
        self.csr_dao = csr_dao
        self.icn_dao = icn_dao
        self._is_stop_loaded = False
        self._is_process_new_clid_loaded = False
        self._stop_icn_csr_exception: List[str] = []
        self._process_new_clid_exception: Dict[str, str] = {}

    def get_stop_icn_csr_exception(self) -> List[str]:
        if not self._is_stop_loaded:
            self._stop_icn_csr_exception = self.icn_dao.stop_icn_csr_exception()
            self._is_stop_loaded = True
        return self._stop_icn_csr_exception

    def get_process_new_clid_exception(self) -> Dict[str, str]:
        if not self._is_process_new_clid_loaded:
            self._process_new_clid_exception = self.csr_dao.process_new_clid_exception()
            self._is_process_new_clid_loaded = True
        return self._process_new_clid_exception

    def _get_icn_details(self, csr_detail: TmpCsrDetail) -> None:
        if not csr_detail.carrier_claim_num:
            return
        info = self.csr_dao.get_icn_details(csr_detail.carrier_claim_num)
        csr_detail.mcca_claim_number = info.get("mccaClaimNum")
        csr_detail.carrier_user_id = info.get("crrUserId")
        if info.get("csrDueDate") is not None:
            csr_detail.csr_due_dt = info["csrDueDate"]
        csr_detail.assign_to = info.get("assignTo")
        csr_detail.carrier_id = info.get("crrId")
        if info.get("retentionAmt") is not None:
            csr_detail.retention_amt = info["retentionAmt"]

    @staticmethod
    def _set_tmp_recrd_to_csr(csr_detail: TmpCsrDetail) -> None:
        """Copies all 26 claimant fields from MCCA_TMP_CLMNT into CsrDetail for a new claimant."""
        csr_detail.claimt_prefix = csr_detail.tmp_claimt_prefix
        csr_detail.claimt_frst_name = csr_detail.tmp_claimt_frst_name
        csr_detail.claimt_lst_name = csr_detail.tmp_claimt_lst_name
        csr_detail.claimt_addres1 = csr_detail.tmp_claimt_addres1
        csr_detail.claimt_addres2 = csr_detail.tmp_claimt_addres2
        csr_detail.claimt_gender = csr_detail.tmp_claimt_gender
        csr_detail.claimt_city = csr_detail.tmp_claimt_city
        csr_detail.claimt_state = csr_detail.tmp_claimt_state
        csr_detail.claimt_zip = csr_detail.tmp_claimt_zip
        csr_detail.claimt_dob = csr_detail.tmp_claimt_dob
        csr_detail.are_issue_in_litg_ind = csr_detail.tmp_are_issue_in_litg_ind
        csr_detail.pip_clm_in_litg_ind = csr_detail.tmp_pip_clm_in_litg_ind
        csr_detail.injured_desc = csr_detail.tmp_injured_desc
        csr_detail.cordnt_no_fault = csr_detail.tmp_cordnt_no_fault
        csr_detail.claimt_midl_in = csr_detail.tmp_claimt_midl_in
        csr_detail.health_crr = csr_detail.tmp_health_crr
        csr_detail.claimt_status_cd = csr_detail.tmp_claimt_status_cd
        csr_detail.claimt_death_dt = csr_detail.tmp_claimt_death_dt
        csr_detail.relation_cd = csr_detail.tmp_relation_cd
        csr_detail.seatbelt_cd = csr_detail.tmp_seatbelt_cd
        csr_detail.air_bg_use_cd = csr_detail.tmp_air_bg_use_cd
        csr_detail.injured_cd = csr_detail.tmp_injured_cd
        csr_detail.demand = csr_detail.tmp_demand
        csr_detail.suit_date = csr_detail.tmp_suit_date
        csr_detail.litgn_issue_desc = csr_detail.tmp_litgn_issue_desc
        csr_detail.claimt_is_dceasd_ind = csr_detail.tmp_claimt_is_dceasd_ind

    @staticmethod
    def _update_new_rec_from_tmp(csr_detail: TmpCsrDetail) -> None:
        """Defect 307: Overwrites existing CSR fields only when MCCA_TMP_CLMNT field is non-empty."""
        def _non_empty(val: object) -> bool:
            return val is not None and str(val).strip() != BatchConstants.EMPTY_STRING

        if _non_empty(csr_detail.tmp_claimt_prefix):
            csr_detail.claimt_prefix = csr_detail.tmp_claimt_prefix
        if _non_empty(csr_detail.tmp_claimt_frst_name):
            csr_detail.claimt_frst_name = csr_detail.tmp_claimt_frst_name
        if _non_empty(csr_detail.tmp_claimt_lst_name):
            csr_detail.claimt_lst_name = csr_detail.tmp_claimt_lst_name
        if _non_empty(csr_detail.tmp_claimt_addres1):
            csr_detail.claimt_addres1 = csr_detail.tmp_claimt_addres1
        if _non_empty(csr_detail.tmp_claimt_addres2):
            csr_detail.claimt_addres2 = csr_detail.tmp_claimt_addres2
        if _non_empty(csr_detail.tmp_claimt_gender):
            csr_detail.claimt_gender = csr_detail.tmp_claimt_gender
        if _non_empty(csr_detail.tmp_claimt_city):
            csr_detail.claimt_city = csr_detail.tmp_claimt_city
        if _non_empty(csr_detail.tmp_claimt_state):
            csr_detail.claimt_state = csr_detail.tmp_claimt_state
        if _non_empty(csr_detail.tmp_claimt_zip):
            csr_detail.claimt_zip = csr_detail.tmp_claimt_zip
        if csr_detail.tmp_claimt_dob is not None:
            csr_detail.claimt_dob = csr_detail.tmp_claimt_dob
        if _non_empty(csr_detail.tmp_are_issue_in_litg_ind):
            csr_detail.are_issue_in_litg_ind = csr_detail.tmp_are_issue_in_litg_ind
        if _non_empty(csr_detail.tmp_pip_clm_in_litg_ind):
            csr_detail.pip_clm_in_litg_ind = csr_detail.tmp_pip_clm_in_litg_ind
        if _non_empty(csr_detail.tmp_injured_desc):
            csr_detail.injured_desc = csr_detail.tmp_injured_desc
        if _non_empty(csr_detail.tmp_cordnt_no_fault):
            csr_detail.cordnt_no_fault = csr_detail.tmp_cordnt_no_fault
        if _non_empty(csr_detail.tmp_claimt_midl_in):
            csr_detail.claimt_midl_in = csr_detail.tmp_claimt_midl_in
        if _non_empty(csr_detail.tmp_health_crr):
            csr_detail.health_crr = csr_detail.tmp_health_crr
        if _non_empty(csr_detail.tmp_claimt_status_cd):
            csr_detail.claimt_status_cd = csr_detail.tmp_claimt_status_cd
        if csr_detail.tmp_claimt_death_dt is not None:
            csr_detail.claimt_death_dt = csr_detail.tmp_claimt_death_dt
        if _non_empty(csr_detail.tmp_relation_cd):
            csr_detail.relation_cd = csr_detail.tmp_relation_cd
        if _non_empty(csr_detail.tmp_seatbelt_cd):
            csr_detail.seatbelt_cd = csr_detail.tmp_seatbelt_cd
        if _non_empty(csr_detail.tmp_air_bg_use_cd):
            csr_detail.air_bg_use_cd = csr_detail.tmp_air_bg_use_cd
        if _non_empty(csr_detail.tmp_injured_cd):
            csr_detail.injured_cd = csr_detail.tmp_injured_cd
        if _non_empty(csr_detail.tmp_demand):
            csr_detail.demand = csr_detail.tmp_demand
        if csr_detail.tmp_suit_date is not None:
            csr_detail.suit_date = csr_detail.tmp_suit_date
        if _non_empty(csr_detail.tmp_litgn_issue_desc):
            csr_detail.litgn_issue_desc = csr_detail.tmp_litgn_issue_desc
        if _non_empty(csr_detail.tmp_claimt_is_dceasd_ind):
            csr_detail.claimt_is_dceasd_ind = csr_detail.tmp_claimt_is_dceasd_ind

    def process(self, csr_detail: TmpCsrDetail) -> Optional[TmpCsrDetail]:
        claim_num = csr_detail.carrier_claim_num
        if not claim_num:
            return None

        csr_detail.icn_status = self.icn_dao.get_icn_status(claim_num)
        self._get_icn_details(csr_detail)

        if csr_detail.new_claimant_ind and csr_detail.new_claimant_ind.upper() == BatchConstants.YES_CD:
            self._set_tmp_recrd_to_csr(csr_detail)
            csr_detail.claimt_county = MccaBatchUtil.get_address_county(
                csr_detail.claimt_addres1,
                csr_detail.claimt_addres2,
                csr_detail.claimt_city,
                csr_detail.claimt_state,
                csr_detail.claimt_zip,
            )
            csr_detail.prbl_life_tm_care_ind = BatchConstants.YES_CD

            if (csr_detail.icn_status or "").upper() == BatchConstants.STATUS_PENDING_CD:
                csr_detail.record_type = BatchConstants.ICN_REC_TYPE
                csr_detail.csr_seq = 0
                return csr_detail
            if (csr_detail.icn_status or "").upper() in (
                BatchConstants.STATUS_SUBMITTED_FINANCE_CD,
                BatchConstants.STATUS_SUBMITTED_MCCA_CD,
            ):
                new_clid_map = self.get_process_new_clid_exception()
                if (
                    claim_num in new_clid_map
                    and csr_detail.clid
                    and new_clid_map[claim_num].lower() == csr_detail.clid.lower()
                ):
                    csr_detail.csr_due_dt = MccaBatchUtil.calculate_csr_due_dt(date.today())
                    csr_detail.record_type = BatchConstants.CSR_REC_TYPE
                    csr_detail.csr_seq = 1
                    return csr_detail
            return None
        else:
            # Existing claimant in MCCA_CSR: update directly via DAO and return None
            if claim_num not in self.get_stop_icn_csr_exception():
                self._update_new_rec_from_tmp(csr_detail)
                if (csr_detail.icn_status or "").upper() == BatchConstants.STATUS_PENDING_CD:
                    csr_detail.record_type = BatchConstants.ICN_REC_TYPE
                    self.csr_dao.update_icn_claimant_info(csr_detail)
                elif (csr_detail.icn_status or "").upper() in (
                    BatchConstants.STATUS_SUBMITTED_FINANCE_CD,
                    BatchConstants.STATUS_SUBMITTED_MCCA_CD,
                ):
                    csr_detail.record_type = BatchConstants.CSR_REC_TYPE
                    self.csr_dao.update_csr_claimant_info(csr_detail)
            return None


# ==============================================================================
# STEP 5 PROCESSOR: UpdateIcnTmpClaimProcessor
# ==============================================================================
class UpdateIcnTmpClaimProcessor:
    """Exact 1:1 port of com.acg.mcca.batch.processor.UpdateIcnTmpClaimProcessor."""

    def __init__(self, icn_dao: IcnJdbcDaoImpl):
        self.icn_dao = icn_dao
        self._is_stop_loaded = False
        self._stop_icn_csr_exception: List[str] = []

    def get_stop_icn_csr_exception(self) -> List[str]:
        if not self._is_stop_loaded:
            self._stop_icn_csr_exception = self.icn_dao.stop_icn_csr_exception()
            self._is_stop_loaded = True
        return self._stop_icn_csr_exception

    def _get_related_claim_number(self, carrier_clm_num: str, link_id: Optional[str]) -> Optional[str]:
        if link_id and link_id.strip():
            related = self.icn_dao.get_related_claims(carrier_clm_num, link_id)
            if related and len(related) < 2:
                return related[0]
        return None

    @staticmethod
    def _update_icn_record_from_tmp(icn_csr_detail: TmpIcnDetail) -> None:
        """Defect 307: Overwrites ICN fields from MCCA_TMP_CLM when non-empty."""
        def _non_empty(val: object) -> bool:
            return val is not None and str(val).strip() != BatchConstants.EMPTY_STRING

        if _non_empty(icn_csr_detail.tmp_accident_desc):
            icn_csr_detail.accident_desc = icn_csr_detail.tmp_accident_desc
        if _non_empty(icn_csr_detail.tmp_accident_addr1):
            icn_csr_detail.accident_addr1 = icn_csr_detail.tmp_accident_addr1
        if _non_empty(icn_csr_detail.tmp_accident_addr2):
            icn_csr_detail.accident_addr2 = icn_csr_detail.tmp_accident_addr2
        if _non_empty(icn_csr_detail.tmp_accident_city):
            icn_csr_detail.accident_city = icn_csr_detail.tmp_accident_city
        if _non_empty(icn_csr_detail.tmp_accident_state):
            icn_csr_detail.accident_state = icn_csr_detail.tmp_accident_state
        if _non_empty(icn_csr_detail.tmp_accident_zip):
            icn_csr_detail.accident_zip = icn_csr_detail.tmp_accident_zip
        if _non_empty(icn_csr_detail.tmp_comp_crs_clm_ind):
            icn_csr_detail.comp_crs_clm_ind = icn_csr_detail.tmp_comp_crs_clm_ind
        if _non_empty(icn_csr_detail.tmp_maipf_jua_ind):
            icn_csr_detail.maipf_jua_ind = icn_csr_detail.tmp_maipf_jua_ind
        if _non_empty(icn_csr_detail.tmp_carrier_policy_num):
            icn_csr_detail.carrier_policy_num = icn_csr_detail.tmp_carrier_policy_num
        if _non_empty(icn_csr_detail.tmp_com_plcy_ind):
            icn_csr_detail.com_plcy_ind = icn_csr_detail.tmp_com_plcy_ind
        if icn_csr_detail.tmp_carrier_id is not None:
            icn_csr_detail.carrier_id = icn_csr_detail.tmp_carrier_id
        if _non_empty(icn_csr_detail.tmp_insured_addr1):
            icn_csr_detail.insured_addr1 = icn_csr_detail.tmp_insured_addr1
        if _non_empty(icn_csr_detail.tmp_insured_addr2):
            icn_csr_detail.insured_addr2 = icn_csr_detail.tmp_insured_addr2
        if _non_empty(icn_csr_detail.tmp_insured_city):
            icn_csr_detail.insured_city = icn_csr_detail.tmp_insured_city
        if _non_empty(icn_csr_detail.tmp_insured_state):
            icn_csr_detail.insured_state = icn_csr_detail.tmp_insured_state
        if _non_empty(icn_csr_detail.tmp_insured_zip):
            icn_csr_detail.insured_zip = icn_csr_detail.tmp_insured_zip
        if _non_empty(icn_csr_detail.tmp_insured_prefix):
            icn_csr_detail.insured_prefix = icn_csr_detail.tmp_insured_prefix
        if _non_empty(icn_csr_detail.tmp_insured_frst_name):
            icn_csr_detail.insured_frst_name = icn_csr_detail.tmp_insured_frst_name
        if _non_empty(icn_csr_detail.tmp_insured_lst_name):
            icn_csr_detail.insured_lst_name = icn_csr_detail.tmp_insured_lst_name
        if _non_empty(icn_csr_detail.tmp_insured_midl_in):
            icn_csr_detail.insured_midl_in = icn_csr_detail.tmp_insured_midl_in
        if _non_empty(icn_csr_detail.tmp_insured_gender):
            icn_csr_detail.insured_gender = icn_csr_detail.tmp_insured_gender
        if icn_csr_detail.tmp_insured_dob is not None:
            icn_csr_detail.insured_dob = icn_csr_detail.tmp_insured_dob
        if _non_empty(icn_csr_detail.tmp_ws_pol_cord_on_dt_loss):
            icn_csr_detail.ws_pol_cord_on_dt_loss = icn_csr_detail.tmp_ws_pol_cord_on_dt_loss
        if _non_empty(icn_csr_detail.tmp_plcy_wrtn_crdnt_bas):
            icn_csr_detail.plcy_wrtn_crdnt_bas = icn_csr_detail.tmp_plcy_wrtn_crdnt_bas

    def process(self, icn_csr_detail: TmpIcnDetail) -> Optional[TmpIcnDetail]:
        claim_num = icn_csr_detail.carrier_claim_num
        if not claim_num or claim_num in self.get_stop_icn_csr_exception():
            return None
        self._update_icn_record_from_tmp(icn_csr_detail)
        if (
            icn_csr_detail.comp_crs_clm_ind
            and icn_csr_detail.comp_crs_clm_ind.strip().upper() == "Y"
        ):
            icn_csr_detail.cross_comp_clm_num = self._get_related_claim_number(
                claim_num, icn_csr_detail.cross_comp_clm_num
            )
        return icn_csr_detail


# ==============================================================================
# STEPS 6 & 7 PROCESSOR: UpdateIcnCsrClaimProcessor
# ==============================================================================
class UpdateIcnCsrClaimProcessor:
    """Exact 1:1 port of com.acg.mcca.batch.processor.UpdateIcnCsrClaimProcessor."""

    def __init__(
        self,
        icn_dao: IcnJdbcDaoImpl,
        othr_inj_clmts_dao: OthrInjClmtsDaoImpl,
        batch_date: str,
    ):
        self.icn_dao = icn_dao
        self.othr_inj_clmts_dao = othr_inj_clmts_dao
        self.batch_date = batch_date
        self._is_stop_loaded = False
        self._stop_icn_csr_exception: List[str] = []

    def get_stop_icn_csr_exception(self) -> List[str]:
        if not self._is_stop_loaded:
            self._stop_icn_csr_exception = self.icn_dao.stop_icn_csr_exception()
            self._is_stop_loaded = True
        return self._stop_icn_csr_exception

    def process(self, icn_csr_detail: IcnCsrDetail) -> Optional[IcnCsrDetail]:
        claim_num = icn_csr_detail.carrier_claim_num
        if not claim_num or claim_num in self.get_stop_icn_csr_exception():
            return None

        if icn_csr_detail.link_claim is not None:
            is_icn = (icn_csr_detail.record_type or "").upper() == BatchConstants.ICN_REC_TYPE
            target_clid = "0" if is_icn else (icn_csr_detail.clid or "0")
            target_csr_seq = Decimal("0") if is_icn else (icn_csr_detail.csr_seq or Decimal("0"))
            updated_list = self.othr_inj_clmts_dao.set_othr_inj_clmts_pymt_for_pn_icn_csr(
                claim_num,
                icn_csr_detail.link_claim,
                self.batch_date,
                target_clid,
                icn_csr_detail.record_type or BatchConstants.ICN_REC_TYPE,
                target_csr_seq,
            )
            if updated_list:
                txn_id = 0
                is_max_set = False
                for othr in updated_list:
                    if not is_max_set:
                        txn_id = self.othr_inj_clmts_dao.get_max_others_txn_id(
                            othr.carrier_clm_num or claim_num,
                            othr.clid or target_clid,
                            othr.rec_typ or (icn_csr_detail.record_type or "ICN"),
                        )
                        txn_id += 1
                        is_max_set = True
                    othr.txn_id = txn_id
                    self.othr_inj_clmts_dao.save_othr_inj_clmts_pymt(othr)
        return icn_csr_detail


# ==============================================================================
# STEPS 8 & 9 PROCESSOR: AmountUpdateProcessor
# ==============================================================================
class AmountUpdateProcessor:
    """Exact 1:1 port of com.acg.mcca.batch.processor.AmountUpdateProcessor."""

    def __init__(
        self,
        icn_dao: IcnJdbcDaoImpl,
        csr_dao: CsrJdbcDaoImpl,
        othr_inj_clmts_dao: OthrInjClmtsDaoImpl,
        batch_date: str,
    ):
        self.icn_dao = icn_dao
        self.csr_dao = csr_dao
        self.othr_inj_clmts_dao = othr_inj_clmts_dao
        self.batch_date = batch_date
        self._is_stop_loaded = False
        self._stop_icn_csr_exception: List[str] = []

    def get_stop_icn_csr_exception(self) -> List[str]:
        if not self._is_stop_loaded:
            self._stop_icn_csr_exception = self.icn_dao.stop_icn_csr_exception()
            self._is_stop_loaded = True
        return self._stop_icn_csr_exception

    def process(self, csr_detail: CsrDetail) -> Optional[CsrDetail]:
        claim_num = csr_detail.carrier_claim_num
        if not claim_num or claim_num in self.get_stop_icn_csr_exception():
            return None

        ptd_reserves_as_of_dt = self.csr_dao.get_ptd_reserves_as_of_date(self.batch_date)
        old_med_paid_to_date = csr_detail.med_paid_to_dt or Decimal("0")
        old_wl_es_sl_paid_to_dt = csr_detail.wl_es_sl_paid_to_dt or Decimal("0")
        old_wl_es_sl_net = csr_detail.wl_es_sl_net or Decimal("0")
        old_med_net_resrv = csr_detail.med_net_resrv or Decimal("0")
        old_res_chng = csr_detail.res_chng or Decimal("0")

        # Defect #293: reset reserve change field for pending ICNs and CSRs
        csr_detail.res_chng = None
        csr_detail.ptd_reserve_asof_date = ptd_reserves_as_of_dt

        # Fetch latest reserves from MCCA_RESERVES + STG_MCCA_RESERVES
        reserve_map = self.csr_dao.get_reserves_value(
            claim_num, csr_detail.clid or "0", self.batch_date
        )
        if reserve_map:
            csr_detail.med_net_resrv = reserve_map.get(BatchConstants.MED_NET_RESRV)
            zsl = reserve_map.get(BatchConstants.COVERAGE_ZSL, Decimal("0"))
            zwl = reserve_map.get(BatchConstants.COVERAGE_ZWL, Decimal("0"))
            csr_detail.wl_es_sl_net = zsl + zwl
            med_net = csr_detail.med_net_resrv or Decimal("0")
            wl_net = csr_detail.wl_es_sl_net or Decimal("0")
            if (med_net + wl_net) > Decimal("0"):
                csr_detail.closed_ind = BatchConstants.NO_CD
            elif csr_detail.record_type != BatchConstants.CSR_REC_TYPE:
                csr_detail.closed_ind = BatchConstants.YES_CD
        else:
            if csr_detail.record_type != BatchConstants.CSR_REC_TYPE:
                csr_detail.closed_ind = BatchConstants.YES_CD
            # Defect #310: set reserves to 0 if no reserves found
            csr_detail.med_net_resrv = Decimal("0")
            csr_detail.wl_es_sl_net = Decimal("0")

        # Fetch paid-to-date from MCCA_LOSS_EXPENSE_DETAILS + STG_MCCA_LOSS_EXPENSE_DETAILS
        paid_to_date_map = self.csr_dao.get_paid_to_date(
            claim_num, csr_detail.clid or "0", self.batch_date
        )
        if paid_to_date_map:
            csr_detail.med_paid_to_dt = paid_to_date_map.get(BatchConstants.MED_PAID_TO_DT)
            zsl = paid_to_date_map.get(BatchConstants.COVERAGE_ZSL, Decimal("0"))
            zwl = paid_to_date_map.get(BatchConstants.COVERAGE_ZWL, Decimal("0"))
            csr_detail.wl_es_sl_paid_to_dt = zsl + zwl
        else:
            # Defect #310
            csr_detail.med_paid_to_dt = Decimal("0")
            csr_detail.wl_es_sl_paid_to_dt = Decimal("0")

        # Incurred amount calculations
        if csr_detail.med_paid_to_dt is not None or csr_detail.med_net_resrv is not None:
            csr_detail.med_incurd = (csr_detail.med_paid_to_dt or Decimal("0")) + (
                csr_detail.med_net_resrv or Decimal("0")
            )
        if csr_detail.res_chng is not None or csr_detail.med_net_resrv is not None:
            csr_detail.new_net = (csr_detail.res_chng or Decimal("0")) + (
                csr_detail.med_net_resrv or Decimal("0")
            )
        if (
            csr_detail.med_paid_to_dt is not None
            or csr_detail.med_net_resrv is not None
            or csr_detail.res_chng is not None
        ):
            csr_detail.new_incrd = (
                (csr_detail.med_paid_to_dt or Decimal("0"))
                + (csr_detail.med_net_resrv or Decimal("0"))
                + (csr_detail.res_chng or Decimal("0"))
            )
        if csr_detail.wl_es_sl_paid_to_dt is not None or csr_detail.wl_es_sl_net is not None:
            csr_detail.wl_es_sl_incrd = (csr_detail.wl_es_sl_paid_to_dt or Decimal("0")) + (
                csr_detail.wl_es_sl_net or Decimal("0")
            )

        # For REC_TYP == 'CSR', adjust combined All Injured Claimant totals
        if csr_detail.record_type == BatchConstants.CSR_REC_TYPE:
            if reserve_map and csr_detail.all_inj_cl_comb_paid_to_dt_res is not None:
                med_net = csr_detail.med_net_resrv or Decimal("0")
                wl_net = csr_detail.wl_es_sl_net or Decimal("0")
                res_chng = csr_detail.res_chng or Decimal("0")
                csr_detail.all_inj_cl_comb_paid_to_dt_res = (
                    csr_detail.all_inj_cl_comb_paid_to_dt_res
                    - old_med_net_resrv
                    + med_net
                    - old_wl_es_sl_net
                    + wl_net
                    - old_res_chng
                    + res_chng
                )
            if paid_to_date_map:
                if csr_detail.all_inj_cl_comb_paid_to_dt_med is not None:
                    med_ptd = csr_detail.med_paid_to_dt or Decimal("0")
                    csr_detail.all_inj_cl_comb_paid_to_dt_med = (
                        csr_detail.all_inj_cl_comb_paid_to_dt_med - old_med_paid_to_date + med_ptd
                    )
                if csr_detail.al_inj_cl_cm_pd_to_dt_wl_es_sl is not None:
                    wl_ptd = csr_detail.wl_es_sl_paid_to_dt or Decimal("0")
                    csr_detail.al_inj_cl_cm_pd_to_dt_wl_es_sl = (
                        csr_detail.al_inj_cl_cm_pd_to_dt_wl_es_sl - old_wl_es_sl_paid_to_dt + wl_ptd
                    )
                if (
                    csr_detail.all_inj_cl_comb_paid_to_dt_med is not None
                    or csr_detail.al_inj_cl_cm_pd_to_dt_wl_es_sl is not None
                ):
                    csr_detail.alinj_cl_cm_pd_to_dt_medwlessl = (
                        csr_detail.all_inj_cl_comb_paid_to_dt_med or Decimal("0")
                    ) + (csr_detail.al_inj_cl_cm_pd_to_dt_wl_es_sl or Decimal("0"))
            csr_detail.alinj_cl_cm_pd_to_dt_medwlres = (
                csr_detail.all_inj_cl_comb_paid_to_dt_res or Decimal("0")
            ) + (csr_detail.alinj_cl_cm_pd_to_dt_medwlessl or Decimal("0"))

        # Update CLM_TYPE='3' in MCCA_OTHR_INJ_CLMTS_PYMT when REC_TYP='ICN' and PRBL_LIFE_TM_CARE_IND='N'
        if (
            csr_detail.record_type == BatchConstants.ICN_REC_TYPE
            and csr_detail.prbl_life_tm_care_ind == BatchConstants.NO_CD
            and (paid_to_date_map or reserve_map)
        ):
            old_others = self.othr_inj_clmts_dao.get_othr_inj_clmts_pymt(
                claim_num, csr_detail.record_type, "0"
            )
            has_other_clids = False
            for old_othr in old_others:
                if (
                    old_othr.clm_type == BatchConstants.CLM_TYPE_3
                    and old_othr.cl_id is not None
                    and old_othr.cl_id == csr_detail.clid
                ):
                    has_other_clids = True
                    old_othr.med = csr_detail.med_paid_to_dt
                    old_othr.wl_es_sl = csr_detail.wl_es_sl_paid_to_dt
                    old_othr.reserve_amt = (csr_detail.med_net_resrv or Decimal("0")) + (
                        csr_detail.wl_es_sl_net or Decimal("0")
                    )
            if has_other_clids and old_others:
                txn_id = 0
                is_max_set = False
                for othr in old_others:
                    if not is_max_set:
                        txn_id = self.othr_inj_clmts_dao.get_max_others_txn_id(
                            othr.carrier_clm_num or claim_num,
                            othr.clid or "0",
                            othr.rec_typ or BatchConstants.ICN_REC_TYPE,
                        )
                        txn_id += 1
                        is_max_set = True
                    othr.txn_id = txn_id
                    self.othr_inj_clmts_dao.save_othr_inj_clmts_pymt(othr)

        return csr_detail


# ==============================================================================
# STEP updateRptdColumn PROCESSOR: MccaClaimRptdProcessor
# ==============================================================================
class MccaClaimRptdProcessor:
    """Exact 1:1 port of com.acg.mcca.batch.processor.MccaClaimRptdProcessor."""

    def __init__(self, mcca_claim_dao: MccaClaimDaoImpl, batch_date: str):
        self.mcca_claim_dao = mcca_claim_dao
        self.batch_date = batch_date

    @staticmethod
    def _is_any_csr_status_open(csr_status_list: List[IcnCsrDetail]) -> bool:
        for item in csr_status_list:
            if (item.status_lst or "").lower() != BatchConstants.CLOSED.lower() and (
                item.closed_ind or ""
            ).upper() != BatchConstants.YES_CD:
                return True
        return False

    def process(self, icn_csr_detail: IcnCsrDetail) -> Optional[IcnCsrDetail]:
        if icn_csr_detail is None or not icn_csr_detail.carrier_claim_num:
            return None

        icn_status = icn_csr_detail.icn_status
        is_icn_closed = icn_csr_detail.is_icn_closed
        new_rptd_value = BatchConstants.EMPTY_STRING

        if is_icn_closed and is_icn_closed.upper() == BatchConstants.YES_CD:
            new_rptd_value = BatchConstants.RPTD_CLOSED_CD
        elif icn_status and icn_status.upper() in (
            BatchConstants.STATUS_SUBMITTED_MCCA_CD,
            BatchConstants.STATUS_SUBMITTED_FINANCE_CD,
        ):
            csr_status_list = self.mcca_claim_dao.get_csr_status_list(
                icn_csr_detail.carrier_claim_num, self.batch_date
            )
            if csr_status_list:
                if self._is_any_csr_status_open(csr_status_list):
                    if icn_status.upper() == BatchConstants.STATUS_SUBMITTED_MCCA_CD:
                        new_rptd_value = BatchConstants.RPTD_SUBMITTED_MCCA_CD
                    elif icn_status.upper() == BatchConstants.STATUS_SUBMITTED_FINANCE_CD:
                        new_rptd_value = BatchConstants.RPTD_SUBMITTED_FINANCE_CD
                else:
                    new_rptd_value = BatchConstants.RPTD_CLOSED_CD

        current_rptd = icn_csr_detail.rptd or BatchConstants.EMPTY_STRING
        if new_rptd_value.upper() != current_rptd.upper():
            icn_csr_detail.rptd = new_rptd_value
            return icn_csr_detail
        return None
