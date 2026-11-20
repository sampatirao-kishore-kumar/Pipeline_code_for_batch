"""
ItemWriters for icnCsrToMccaJob.
Exact 1:1 port of:
- com.acg.mcca.batch.writer.CopyIcnWriter (Step 2)
- com.acg.mcca.batch.writer.IcnDetailWriter (Step 3)
- com.acg.mcca.batch.writer.CsrDetailWriter (Step 4)
- com.acg.mcca.batch.writer.AlInjrdClmntCmbndWriter (Used in Steps 4, 8, 9)
- com.acg.mcca.batch.writer.OthrInjClmtsWriter
- com.acg.mcca.batch.writer.UpdateIcnTmpClaimDetailWriter (Step 5)
- com.acg.mcca.batch.writer.UpdateIcnCsrClaimDetailWriter (Steps 6 & 7)
- com.acg.mcca.batch.writer.CsrAmountUpdateWriter (Steps 8 & 9)
- com.acg.mcca.batch.writer.MccaClaimRptdWriter (updateRptdColumn)
"""

import logging
from decimal import Decimal
from typing import List, Sequence

from config import BatchConstants
from dao.csr_dao import CsrJdbcDaoImpl
from dao.icn_dao import IcnJdbcDaoImpl
from dao.mcca_claim_dao import MccaClaimDaoImpl
from dao.othr_inj_clmts_dao import OthrInjClmtsDaoImpl
from dao.update_icn_csr_dao import UpdateIcnCsrJdbcDaoImpl
from models import CsrDetail, IcnCsrDetail, OthrInjClmtsPymt, TmpCsrDetail, TmpIcnDetail

logger = logging.getLogger(__name__)


# ==============================================================================
# STEP 2 WRITER: CopyIcnWriter
# ==============================================================================
class CopyIcnWriter:
    """Exact 1:1 port of com.acg.mcca.batch.writer.CopyIcnWriter."""

    def __init__(self, icn_dao: IcnJdbcDaoImpl):
        self.icn_dao = icn_dao

    def write(self, items: Sequence[IcnCsrDetail]) -> None:
        for icn_csr in items:
            self.icn_dao.update_icn_submitted_to_finance(icn_csr)
            self.icn_dao.update_csr_record_for_sf(icn_csr)
            self.icn_dao.copy_icn(icn_csr)
            self.icn_dao.close_csr_submitted_to_finance(icn_csr)
            self.icn_dao.copy_csr_info(icn_csr)


# ==============================================================================
# STEP 3 WRITER: IcnDetailWriter
# ==============================================================================
class IcnDetailWriter:
    """Exact 1:1 port of com.acg.mcca.batch.writer.IcnDetailWriter."""

    def __init__(self, icn_dao: IcnJdbcDaoImpl):
        self.icn_dao = icn_dao

    def write(self, items: Sequence[IcnCsrDetail]) -> None:
        for icn_csr in items:
            self.icn_dao.save_icn_detail(icn_csr)
            self.icn_dao.save_icn_csr_detail(icn_csr)


# ==============================================================================
# HELPER WRITER: AlInjrdClmntCmbndWriter
# ==============================================================================
class AlInjrdClmntCmbndWriter:
    """
    Exact 1:1 port of com.acg.mcca.batch.writer.AlInjrdClmntCmbndWriter.
    Calculates combined All Injured Claimant Paid-to-Date / Wage Loss / Reserves
    and Retention Indicator across all claimants for each claim, and updates MCCA_CSR.
    """

    def __init__(self, csr_dao: CsrJdbcDaoImpl):
        self.csr_dao = csr_dao

    @staticmethod
    def _validate_str(val: object) -> bool:
        if val is not None and str(val).strip() != "" and str(val).strip() != "undefined":
            return True
        return False

    @classmethod
    def populate_all_claimant_fields(
        cls,
        csr: CsrDetail,
        claimant_list: List[CsrDetail],
        counter: int,
        other_inj_list: List[OthrInjClmtsPymt],
    ) -> None:
        all_ins_med = Decimal("0")
        all_ins_wl_es_sl = Decimal("0")
        med_tot = Decimal("0")
        ws_tot = Decimal("0")
        reserve_total = Decimal("0")
        all_ins_res = Decimal("0")

        for item in claimant_list:
            if item.med_paid_to_dt is not None and cls._validate_str(item.med_paid_to_dt):
                med_tot += Decimal(int(item.med_paid_to_dt))
            if item.wl_es_sl_paid_to_dt is not None and cls._validate_str(item.wl_es_sl_paid_to_dt):
                ws_tot += Decimal(int(item.wl_es_sl_paid_to_dt))
            if item.new_net is not None and cls._validate_str(item.new_net):
                reserve_total += Decimal(int(item.new_net))
            if item.wl_es_sl_net is not None and cls._validate_str(item.wl_es_sl_net):
                reserve_total += Decimal(int(item.wl_es_sl_net))

        for other_data in other_inj_list:
            if other_data.med is not None:
                all_ins_med += other_data.med
            if other_data.wl_es_sl is not None:
                all_ins_wl_es_sl += other_data.wl_es_sl
            if other_data.reserve_amt is not None:
                all_ins_res += other_data.reserve_amt

        val = all_ins_med + med_tot
        csr.all_inj_cl_comb_paid_to_dt_med = val if val > Decimal("0") else None

        val1 = all_ins_wl_es_sl + ws_tot
        csr.al_inj_cl_cm_pd_to_dt_wl_es_sl = val1 if val1 > Decimal("0") else None

        val3 = med_tot + all_ins_med + ws_tot + all_ins_wl_es_sl
        csr.alinj_cl_cm_pd_to_dt_medwlessl = val3 if val3 > Decimal("0") else None

        val4 = all_ins_res + reserve_total
        csr.all_inj_cl_comb_paid_to_dt_res = val4 if val4 > Decimal("0") else None

        val5 = val3 + val4
        csr.alinj_cl_cm_pd_to_dt_medwlres = val5 if val5 > Decimal("0") else None

        if counter == 0:
            for csr_new in claimant_list:
                csr_new.all_inj_cl_comb_paid_to_dt_med = csr.all_inj_cl_comb_paid_to_dt_med
                csr_new.al_inj_cl_cm_pd_to_dt_wl_es_sl = csr.al_inj_cl_cm_pd_to_dt_wl_es_sl
                csr_new.alinj_cl_cm_pd_to_dt_medwlessl = csr.alinj_cl_cm_pd_to_dt_medwlessl
                csr_new.all_inj_cl_comb_paid_to_dt_res = csr.all_inj_cl_comb_paid_to_dt_res
                csr_new.alinj_cl_cm_pd_to_dt_medwlres = csr.alinj_cl_cm_pd_to_dt_medwlres

        final_total = csr.alinj_cl_cm_pd_to_dt_medwlessl or Decimal("0")
        if csr.retention_amt is not None and final_total > Decimal("0"):
            if csr.retention_amt > final_total:
                csr.retention_ind = BatchConstants.NO_CD
            else:
                csr.retention_ind = BatchConstants.YES_CD
        else:
            csr.retention_ind = None

    def write(self, claim_num_list: Sequence[str]) -> None:
        for carrier_clm_num in claim_num_list:
            claimant_list = self.csr_dao.search_icn_csr_data(carrier_clm_num)
            other_inj_list = self.csr_dao.get_other_proj_clmtss_data(carrier_clm_num)

            claim_int_info: CsrDetail | None = None
            for csr_detail in claimant_list:
                if (csr_detail.clid or "") == BatchConstants.ZERO:
                    claim_int_info = csr_detail

            if claim_int_info is not None:
                self.populate_all_claimant_fields(claim_int_info, claimant_list, 0, other_inj_list)
                for j, new_mcca_csr_updated in enumerate(claimant_list):
                    if (new_mcca_csr_updated.clid or "") == BatchConstants.ZERO:
                        new_mcca_csr_updated = claim_int_info
                        self.populate_all_claimant_fields(
                            claim_int_info, claimant_list, j, other_inj_list
                        )
                    final_total = new_mcca_csr_updated.alinj_cl_cm_pd_to_dt_medwlessl or Decimal("0")
                    if new_mcca_csr_updated.retention_amt is not None and final_total > Decimal("0"):
                        if new_mcca_csr_updated.retention_amt > final_total:
                            new_mcca_csr_updated.retention_ind = BatchConstants.NO_CD
                        else:
                            new_mcca_csr_updated.retention_ind = BatchConstants.YES_CD
                    else:
                        new_mcca_csr_updated.retention_ind = None

                    self.csr_dao.update_csr_amount(new_mcca_csr_updated)


# ==============================================================================
# STEP 4 WRITER: CsrDetailWriter
# ==============================================================================
class CsrDetailWriter:
    """Exact 1:1 port of com.acg.mcca.batch.writer.CsrDetailWriter."""

    def __init__(
        self,
        csr_dao: CsrJdbcDaoImpl,
        al_injrd_clmnt_cmbnd_writer: AlInjrdClmntCmbndWriter,
        batch_date: str,
    ):
        self.csr_dao = csr_dao
        self.al_injrd_clmnt_cmbnd_writer = al_injrd_clmnt_cmbnd_writer
        self.batch_date = batch_date

    def write(self, csrs: Sequence[TmpCsrDetail]) -> None:
        carrier_claim_num_list: List[str] = []
        ptd_reserves_as_of_dt = self.csr_dao.get_ptd_reserves_as_of_date(self.batch_date)

        for csr in csrs:
            if not csr.carrier_claim_num or not csr.clid:
                continue
            reserve_map = self.csr_dao.get_reserves_value(
                csr.carrier_claim_num, csr.clid, self.batch_date
            )
            if reserve_map:
                csr.med_net_resrv = reserve_map.get(BatchConstants.MED_NET_RESRV)
                zsl = reserve_map.get(BatchConstants.COVERAGE_ZSL, Decimal("0"))
                zwl = reserve_map.get(BatchConstants.COVERAGE_ZWL, Decimal("0"))
                csr.wl_es_sl_net = zsl + zwl

            paid_to_date_map = self.csr_dao.get_paid_to_date(
                csr.carrier_claim_num, csr.clid, self.batch_date
            )
            csr.ptd_reserve_asof_date = ptd_reserves_as_of_dt
            if paid_to_date_map:
                csr.med_paid_to_dt = paid_to_date_map.get(BatchConstants.MED_PAID_TO_DT)
                zsl = paid_to_date_map.get(BatchConstants.COVERAGE_ZSL, Decimal("0"))
                zwl = paid_to_date_map.get(BatchConstants.COVERAGE_ZWL, Decimal("0"))
                csr.wl_es_sl_paid_to_dt = zsl + zwl

            if csr.med_paid_to_dt is not None or csr.med_net_resrv is not None:
                csr.med_incurd = (csr.med_paid_to_dt or Decimal("0")) + (
                    csr.med_net_resrv or Decimal("0")
                )
            if csr.res_chng is not None or csr.med_net_resrv is not None:
                csr.new_net = (csr.res_chng or Decimal("0")) + (csr.med_net_resrv or Decimal("0"))
            if (
                csr.med_paid_to_dt is not None
                or csr.med_net_resrv is not None
                or csr.res_chng is not None
            ):
                csr.new_incrd = (
                    (csr.med_paid_to_dt or Decimal("0"))
                    + (csr.med_net_resrv or Decimal("0"))
                    + (csr.res_chng or Decimal("0"))
                )
            if csr.wl_es_sl_paid_to_dt is not None or csr.wl_es_sl_net is not None:
                csr.wl_es_sl_incrd = (csr.wl_es_sl_paid_to_dt or Decimal("0")) + (
                    csr.wl_es_sl_net or Decimal("0")
                )

            self.csr_dao.save_claimant_info(csr)
            self.csr_dao.insert_projections(csr)
            if reserve_map or paid_to_date_map:
                carrier_claim_num_list.append(csr.carrier_claim_num)

        if carrier_claim_num_list:
            self.al_injrd_clmnt_cmbnd_writer.write(carrier_claim_num_list)


# ==============================================================================
# HELPER WRITER: OthrInjClmtsWriter
# ==============================================================================
class OthrInjClmtsWriter:
    """Exact 1:1 port of com.acg.mcca.batch.writer.OthrInjClmtsWriter."""

    def __init__(self, othr_inj_clmts_dao: OthrInjClmtsDaoImpl):
        self.othr_inj_clmts_dao = othr_inj_clmts_dao

    def write(self, others: Sequence[OthrInjClmtsPymt]) -> None:
        is_max_txn_id_set = False
        txn_id = 0
        for othr in others:
            if not is_max_txn_id_set:
                txn_id = self.othr_inj_clmts_dao.get_max_others_txn_id(
                    othr.carrier_clm_num or "",
                    othr.clid or "0",
                    othr.rec_typ or BatchConstants.ICN_REC_TYPE,
                )
                txn_id += 1
                is_max_txn_id_set = True
            othr.txn_id = txn_id
            self.othr_inj_clmts_dao.save_othr_inj_clmts_pymt(othr)


# ==============================================================================
# STEP 5 WRITER: UpdateIcnTmpClaimDetailWriter
# ==============================================================================
class UpdateIcnTmpClaimDetailWriter:
    """Exact 1:1 port of com.acg.mcca.batch.writer.UpdateIcnTmpClaimDetailWriter."""

    def __init__(self, update_dao: UpdateIcnCsrJdbcDaoImpl):
        self.update_dao = update_dao

    def write(self, items: Sequence[TmpIcnDetail]) -> None:
        for icn_csr in items:
            self.update_dao.update_icn_tmp_claim_detail(icn_csr)


# ==============================================================================
# STEPS 6 & 7 WRITER: UpdateIcnCsrClaimDetailWriter
# ==============================================================================
class UpdateIcnCsrClaimDetailWriter:
    """
    Exact 1:1 port of com.acg.mcca.batch.writer.UpdateIcnCsrClaimDetailWriter.
    Configured with rec_type="ICN" in Step 6 and rec_type="CSR" in Step 7.
    """

    def __init__(self, update_dao: UpdateIcnCsrJdbcDaoImpl, rec_type: str):
        self.update_dao = update_dao
        self.rec_type = rec_type

    def write(self, items: Sequence[IcnCsrDetail]) -> None:
        for icn_csr in items:
            if self.rec_type.upper() == BatchConstants.ICN_REC_TYPE:
                self.update_dao.update_icn_claim_detail(icn_csr, self.rec_type)
            elif self.rec_type.upper() == BatchConstants.CSR_REC_TYPE:
                self.update_dao.update_csr_claim_detail(icn_csr, self.rec_type)


# ==============================================================================
# STEPS 8 & 9 WRITER: CsrAmountUpdateWriter
# ==============================================================================
class CsrAmountUpdateWriter:
    """Exact 1:1 port of com.acg.mcca.batch.writer.CsrAmountUpdateWriter."""

    def __init__(
        self,
        csr_dao: CsrJdbcDaoImpl,
        al_injrd_clmnt_cmbnd_writer: AlInjrdClmntCmbndWriter,
    ):
        self.csr_dao = csr_dao
        self.al_injrd_clmnt_cmbnd_writer = al_injrd_clmnt_cmbnd_writer

    def write(self, icn_csrs: Sequence[CsrDetail]) -> None:
        carrier_claim_num_list: List[str] = []
        for icn_csr in icn_csrs:
            self.csr_dao.update_csr_amount(icn_csr)
            if (
                icn_csr.record_type == BatchConstants.ICN_REC_TYPE
                and icn_csr.carrier_claim_num
                and icn_csr.carrier_claim_num not in carrier_claim_num_list
            ):
                carrier_claim_num_list.append(icn_csr.carrier_claim_num)

        if carrier_claim_num_list:
            self.al_injrd_clmnt_cmbnd_writer.write(carrier_claim_num_list)


# ==============================================================================
# STEP updateRptdColumn WRITER: MccaClaimRptdWriter
# ==============================================================================
class MccaClaimRptdWriter:
    """Exact 1:1 port of com.acg.mcca.batch.writer.MccaClaimRptdWriter."""

    def __init__(self, mcca_claim_dao: MccaClaimDaoImpl):
        self.mcca_claim_dao = mcca_claim_dao

    def write(self, mcca_claim_details: Sequence[IcnCsrDetail]) -> None:
        for mcca_claim in mcca_claim_details:
            self.mcca_claim_dao.update_mcca_clm_with_rptd(mcca_claim)
