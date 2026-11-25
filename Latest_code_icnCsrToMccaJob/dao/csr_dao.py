"""
CSR JDBC DAO Implementation.
1:1 port of com.acg.mcca.batch.impl.CsrJdbcDaoImpl.

Tables Accessed:
- MCCA_CSR
- MCCA_ICN
- MCCA_CLAIM
- MCCA_RESERVES
- STG_MCCA_RESERVES
- MCCA_LOSS_EXPENSE_DETAILS
- STG_MCCA_LOSS_EXPENSE_DETAILS
- D_FISCAL_MONTH
- MCCA_EXCEPTION
- MCCA_PROJECTIONS
- MCCA_OTHR_INJ_CLMTS_PYMT
- MCCA_TMP_CLMNT
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from config import BatchConstants
from dao.base_dao import BaseJdbcDao
from models import CsrDetail, OthrInjClmtsPymt, TmpCsrDetail
from reader_queries import map_csr_amount_update_row

logger = logging.getLogger(__name__)


class CsrJdbcDaoImpl(BaseJdbcDao):
    """Exact 1:1 port of com.acg.mcca.batch.impl.CsrJdbcDaoImpl."""

    def save_claimant_info(self, csr_detail: TmpCsrDetail) -> None:
        """
        Inserts a new claimant record into MCCA_CSR.
        Exact port of CsrJdbcDaoImpl.saveClaimantInfo(final TmpCsrDetail csrDetail).
        """
        try:
            sql = """
                INSERT INTO MCCA_CSR (
                    TXN_ID, CARRIER_CLM_NUM, CLID, CSR_SEQ, REC_TYP, STATUS, LST_UPDT_TIME_STMP,
                    MCCA_CLM_NUM, STATUS_LST, CLMT_SUFFIX, CLMT_FST_NAME, CLMT_MI, CLMT_LST_NAME,
                    CLMT_GNDR, CLMT_DOB, CLMT_ADD1, CLMT_ADD2, CLMT_CITY, CLMT_STATE, CLMT_ZIP,
                    CLMT_CNTY, HLTH_CRR, CLMT_STAT_CD, RLN_CD, SEABLT_CD, ARBG_USE_CD, INJ_DESC,
                    INJ_CD, DEATH_DT, CRR_USR_ID, CSR_DUE_DT, MED_PAID_TO_DT, MED_NET_RESRV,
                    MED_INCURD, RES_CHNG, NEW_NET, NEW_INCRD, WL_ES_SL_PAID_TO_DT, WL_ES_SL_NET,
                    WL_ES_SL_INCRD, DEMAND, SUIT_DT, LITGN_ISSUE_DESC, CLMT_DCSD_IND,
                    COORDINATE_NO_FLT_IND, PIP_CLM_LITIGN_IND, LITGN_ISSUE_IND,
                    PRBL_LIFE_TM_CARE_IND, CLOSED_IND, RETNTON_AMT, ASSGND_PRSN,
                    LST_UPDTING_PRSN, CRR_ID, PTD_RESERVES_AS_OF_DATE
                ) VALUES (
                    (SELECT NVL(MAX(TXN_ID), 0) FROM MCCA_CSR WHERE CARRIER_CLM_NUM = ? AND CLID = ? AND REC_TYP = ?) + 1,
                    ?, ?, ?, ?, ?, SYSDATE,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """
            prefix_val = (
                BatchConstants.PREFIX_HONOR_CD
                if csr_detail.claimt_prefix
                and csr_detail.claimt_prefix.lower() == BatchConstants.PREFIX_HONOR.lower()
                else csr_detail.claimt_prefix
            )
            params = [
                csr_detail.carrier_claim_num,
                csr_detail.clid,
                csr_detail.record_type,
                csr_detail.carrier_claim_num,
                csr_detail.clid,
                csr_detail.csr_seq,
                csr_detail.record_type,
                BatchConstants.STATUS_PENDING_CD,
                Decimal(csr_detail.mcca_claim_number) if csr_detail.mcca_claim_number else csr_detail.mcca_clm_num,
                BatchConstants.OPEN,
                prefix_val,
                csr_detail.claimt_frst_name,
                csr_detail.claimt_midl_in,
                csr_detail.claimt_lst_name,
                csr_detail.claimt_gender,
                csr_detail.claimt_dob,
                csr_detail.claimt_addres1,
                csr_detail.claimt_addres2,
                csr_detail.claimt_city,
                csr_detail.claimt_state,
                csr_detail.claimt_zip,
                csr_detail.claimt_county,
                csr_detail.health_crr,
                csr_detail.claimt_status_cd,
                csr_detail.relation_cd,
                csr_detail.seatbelt_cd,
                csr_detail.air_bg_use_cd,
                csr_detail.injured_desc,
                csr_detail.injured_cd,
                csr_detail.claimt_death_dt,
                csr_detail.carrier_user_id,
                csr_detail.csr_due_dt,
                csr_detail.med_paid_to_dt,
                csr_detail.med_net_resrv,
                csr_detail.med_incurd,
                csr_detail.res_chng,
                csr_detail.new_net,
                csr_detail.new_incrd,
                csr_detail.wl_es_sl_paid_to_dt,
                csr_detail.wl_es_sl_net,
                csr_detail.wl_es_sl_incrd,
                csr_detail.demand,
                csr_detail.suit_date,
                csr_detail.litgn_issue_desc,
                csr_detail.claimt_is_dceasd_ind,
                csr_detail.cordnt_no_fault,
                csr_detail.pip_clm_in_litg_ind,
                csr_detail.are_issue_in_litg_ind,
                csr_detail.prbl_life_tm_care_ind,
                BatchConstants.NO_CD,
                csr_detail.retention_amt,
                csr_detail.assign_to,
                BatchConstants.BATCH_LST_UPDTING_PRSN,
                csr_detail.carrier_id,
                csr_detail.ptd_reserve_asof_date,
            ]
            self.update(sql, params)
        except Exception as exc:
            logger.error(
                "Error in CsrJdbcDaoImpl.save_claimant_info() CARRIER_CLM_NUM=%s CLID=%s: %s",
                csr_detail.carrier_claim_num,
                csr_detail.clid,
                exc,
            )

    def get_icn_details(self, carrier_clm_num: str) -> Dict[str, Any]:
        """
        Fetches MCCA_CLM_NUM, CRR_USR_ID, CSR_DUE_DT, ASSGND_PRSN, CRR_ID, RETNTON_AMT
        from the CLID='0' row of MCCA_CSR.
        Exact port of CsrJdbcDaoImpl.getIcnDetails(String carrierClmNum).
        """
        sql = """
            SELECT
                MCCA_CLM_NUM,
                CRR_USR_ID,
                CSR_DUE_DT,
                ASSGND_PRSN,
                CRR_ID,
                RETNTON_AMT
            FROM MCCA_CSR CSR
            WHERE CSR.CARRIER_CLM_NUM = ?
              AND CSR.CLID = '0'
              AND CSR.TXN_ID = (
                  SELECT MAX(CSR1.TXN_ID)
                  FROM MCCA_CSR CSR1
                  WHERE CSR1.CARRIER_CLM_NUM = CSR.CARRIER_CLM_NUM
                    AND CSR1.CLID = '0'
              )
        """
        rows = self.query_for_list(sql, [carrier_clm_num])
        if not rows:
            return {}
        r = rows[0]
        return {
            "mccaClaimNum": str(r["MCCA_CLM_NUM"]) if r.get("MCCA_CLM_NUM") is not None else None,
            "crrUserId": r.get("CRR_USR_ID"),
            "csrDueDate": r.get("CSR_DUE_DT"),
            "assignTo": r.get("ASSGND_PRSN"),
            "crrId": Decimal(str(r["CRR_ID"])) if r.get("CRR_ID") is not None else None,
            "retentionAmt": Decimal(str(r["RETNTON_AMT"])) if r.get("RETNTON_AMT") is not None else None,
        }

    def get_reserves_value(self, carrier_clm_num: str, clid: str, batch_date: str) -> Dict[str, Decimal]:
        """
        Queries MCCA_RESERVES and STG_MCCA_RESERVES for ZPIP (MED_NET_RESRV), ZSL, ZWL reserves.
        Exact port of CsrJdbcDaoImpl.getReservesValue(String carrierClmNum, String clid, String batchDate)
        and getReservesSql().
        """
        sql = """
            WITH Combined_Reserves AS (
                SELECT CARRIER_CLM_NUM, CLID, RESERVE_DATE, COVERAGE, RESERVE_AMOUNT
                FROM MCCA_RESERVES
                WHERE CARRIER_CLM_NUM = ? AND CLID = ?
                UNION ALL
                SELECT CARRIER_CLM_NUM, CLID, RESERVE_DATE, COVERAGE, RESERVE_AMOUNT
                FROM STG_MCCA_RESERVES
                WHERE CARRIER_CLM_NUM = ? AND CLID = ?
            ),
            Max_Date AS (
                SELECT MAX(RESERVE_DATE) AS max_date
                FROM Combined_Reserves
            )
            SELECT
                (CASE WHEN C.COVERAGE IN ('ZWL', 'ZSL') THEN C.COVERAGE ELSE 'MED_NET_RESRV' END) AS COVERAGE,
                SUM(C.RESERVE_AMOUNT) AS RESERVE_AMOUNT
            FROM Combined_Reserves C
            JOIN Max_Date M ON C.RESERVE_DATE = M.max_date
            GROUP BY (CASE WHEN C.COVERAGE IN ('ZWL', 'ZSL') THEN C.COVERAGE ELSE 'MED_NET_RESRV' END)
        """
        rows = self.query_for_list(sql, [carrier_clm_num, clid, carrier_clm_num, clid])
        result: Dict[str, Decimal] = {}
        for row in rows:
            cov = row.get("COVERAGE")
            amt = row.get("RESERVE_AMOUNT")
            if cov and amt is not None:
                result[str(cov)] = Decimal(str(amt))
        return result

    def get_paid_to_date(self, carrier_clm_num: str, clid: str, batch_date: str) -> Dict[str, Decimal]:
        """
        Queries MCCA_LOSS_EXPENSE_DETAILS and STG_MCCA_LOSS_EXPENSE_DETAILS for MED_PAID_TO_DT, ZSL, ZWL.
        Exact port of CsrJdbcDaoImpl.getPaidToDate(String carrierClmNum, String clid, String batchDate)
        and getLossExpDetlsSql().
        """
        sql = """
            SELECT COVERAGE, SUM(LOSSES_PAID) AS LOSSES_PAID
            FROM (
                SELECT
                    (CASE WHEN LED.COVERAGE IN ('ZWL', 'ZSL') THEN LED.COVERAGE ELSE 'MED_PAID_TO_DT' END) AS COVERAGE,
                    LED.LOSSES_PAID
                FROM MCCA_LOSS_EXPENSE_DETAILS LED
                WHERE LED.CARRIER_CLM_NUM = ?
                  AND LED.CLID = ?
                UNION ALL
                SELECT
                    (CASE WHEN STGLED.COVERAGE IN ('ZWL', 'ZSL') THEN STGLED.COVERAGE ELSE 'MED_PAID_TO_DT' END) AS COVERAGE,
                    STGLED.LOSSES_PAID
                FROM STG_MCCA_LOSS_EXPENSE_DETAILS STGLED
                WHERE STGLED.CARRIER_CLM_NUM = ?
                  AND STGLED.CLID = ?
            ) T
            GROUP BY COVERAGE
        """
        rows = self.query_for_list(sql, [carrier_clm_num, clid, carrier_clm_num, clid])
        result: Dict[str, Decimal] = {}
        for row in rows:
            cov = row.get("COVERAGE")
            amt = row.get("LOSSES_PAID")
            if cov and amt is not None:
                result[str(cov)] = Decimal(str(amt))
        return result

    def get_ptd_reserves_as_of_date(self, batch_date: str) -> Optional[date]:
        """
        Fetches LAST_DAY_FISCAL_MONTH from D_FISCAL_MONTH for the fiscal month preceding batch_date.
        Exact port of CsrJdbcDaoImpl.getPTDReservesAsOfDate(String batchDate).
        """
        sql = f"""
            SELECT DISTINCT F.LAST_DAY_FISCAL_MONTH
            FROM D_FISCAL_MONTH F
            WHERE F.FISCAL_MONTH_NUMBER || F.FISCAL_YEAR = (
                CASE
                    WHEN TO_NUMBER(TO_CHAR(TO_DATE('{batch_date}', 'yyyy/MM/dd'), 'MM')) = 1
                    THEN (12 || (TO_NUMBER(TO_CHAR(TO_DATE('{batch_date}', 'yyyy/MM/dd'), 'YYYY')) - 1))
                    ELSE ((TO_NUMBER(TO_CHAR(TO_DATE('{batch_date}', 'yyyy/MM/dd'), 'MM')) - 1)
                          || TO_NUMBER(TO_CHAR(TO_DATE('{batch_date}', 'yyyy/MM/dd'), 'YYYY')))
                END
            )
        """
        rows = self.query_for_list(sql)
        if rows and rows[0].get("LAST_DAY_FISCAL_MONTH") is not None:
            return rows[0]["LAST_DAY_FISCAL_MONTH"]
        return None

    def process_new_clid_exception(self) -> Dict[str, str]:
        """
        Returns CARRIER_CLM_NUM -> CLID map from MCCA_EXCEPTION where EXCEPTION_CODE = '8'.
        Exact port of CsrJdbcDaoImpl.processNewClidException().
        """
        sql = "SELECT CARRIER_CLM_NUM, CLID FROM MCCA_EXCEPTION WHERE EXCEPTION_CODE = ?"
        rows = self.query_for_list(sql, [BatchConstants.PROCESS_NEW_CLID_EXCEPTION_CODE])
        return {
            str(r["CARRIER_CLM_NUM"]): str(r["CLID"])
            for r in rows
            if r.get("CARRIER_CLM_NUM") and r.get("CLID")
        }

    def update_csr_amount(self, csr_detail: CsrDetail) -> None:
        """
        Inserts a new version row (TXN_ID + 1) into MCCA_CSR with updated financial amounts,
        combined totals, and MCCA 3.3 multi-tier attendant care fields.
        Exact port of CsrJdbcDaoImpl.updateCsrAmount(final CsrDetail csrDetail) (lines 480-1322).
        """
        try:
            sql = """
                INSERT INTO MCCA_CSR (
                    TXN_ID, CARRIER_CLM_NUM, CLID, CSR_SEQ, REC_TYP, STATUS, LST_UPDT_TIME_STMP,
                    PLCY_EXP_DATE, DEMAND, SUIT_DT, LITGN_ISSUE_DESC, SSDI_APPLN_STATUS,
                    CLMT_CRNT_CONDN_FUTR_CARE_DESC, MCCA_CLM_NUM, STATUS_LST, CLMT_SUFFIX,
                    CLMT_FST_NAME, CLMT_MI, CLMT_LST_NAME, CLMT_GNDR, CLMT_DOB, CLMT_ADD1,
                    CLMT_ADD2, CLMT_CITY, CLMT_STATE, CLMT_ZIP, CLMT_CNTY, HLTH_CRR,
                    CLMT_STAT_CD, RLN_CD, SEABLT_CD, ARBG_USE_CD, INJ_DESC, INJ_CD, DEATH_DT,
                    CRR_USR_ID, CSR_DUE_DT, PRJCTD_LNG_TRM_INSTL_AMT, PRJCTD_LNG_TRM_MEDL_AMT,
                    PRJCTD_LNG_TRM_OTHR_AMT, PRJCTD_LNG_TRM_OUTSTNDG_AMT, MED_PAID_TO_DT,
                    MED_NET_RESRV, MED_INCURD, RES_CHNG, NEW_NET, NEW_INCRD, WL_ES_SL_PAID_TO_DT,
                    WL_ES_SL_NET, WL_ES_SL_INCRD, HSPTL_12_MNTH_CST, HSPTL_ANNL_FUTR_CST,
                    DOC_LAB_12_MNTH_CST, DOC_LAB_ANNL_FUTR_CST, HOME_PUR_12_MNTH_CST,
                    HOME_PUR_ANNL_FUTR_CST, VEH_PUR_MODFN_12_MNTH_CST, VEH_PUR_ANNL_FUTR_CST,
                    EQPMT_PUR_12_MNTH_CST, EQPMT_PUR_ANNL_FUTR_CST, PRO_12_MNTH_CST,
                    PRO_ANNL_FUTR_CST, PRE_DRG_SUP_12_MNTH_CST, PRE_DRG_SUP_ANNL_FUTR_CST,
                    THERAP_REHAB_12_MNTH_CST, THERAP_REHAB_ANNL_FUTR_CST, TRNSPRT_12_MNTH_CST,
                    TRNSPRT_ANNL_FUTR_CST, CASE_MGMT_12_MNTH_CST, CASE_MGMT_ANNL_FUTR_CST,
                    WGS_SRV_SR_LOSS_12_MNTH_CST, WGS_SRV_SR_LOSS_ANL_FUTR_CST, OTHR_12_MNTH_CST,
                    OTHR_ANNL_FUTR_CST, TOTL_12_MNTH_CST, TOT_ANNL_FUTR_CST,
                    RESDNTL_FACLTY_MNTH_RATE, AGNCY_DLY_RATE, AGNCY_HRLY_RATE, FMLY_HRLY_RATE,
                    FMLY_DLY_RATE, AGNCY_AC_HRS, FMLY_AC_HRS, HLTH_INS_INFORCE_IND,
                    CLMT_DCSD_IND, COORDINATE_NO_FLT_IND, PIP_CLM_LITIGN_IND, LITGN_ISSUE_IND,
                    INJ_PRTY_APPLD_SSDI_IND, IS_RVWD_OR_UPTD, PRBL_LIFE_TM_CARE_IND,
                    NOFLT_HCC_CORD_IND, CLOSED_IND, RETENTION, RETNTON_AMT, LIFE_EXPTNCY,
                    ALL_INJ_CL_COMB_PAID_TO_DT_MED, AL_INJ_CL_CM_PD_TO_DT_WL_ES_SL,
                    ALINJ_CL_CM_PD_TO_DT_MEDWLESSL, ASSGND_PRSN, LST_UPDTING_PRSN, CRR_ID,
                    WS_PLCY_CORDNTD_DT_OF_LOSS_IND, CRNT_STS_CLM_ISUES_IN_DISPTE, LOCK_STATUS,
                    SUBMITTED_TO, SUBMITTED_BY, ICN_SUB_TO, SUBMITTED_DATE,
                    ALL_INJ_CL_COMB_PAID_TO_DT_RES, ALINJ_CL_CM_PD_TO_DT_MEDWLRES,
                    AGNCY_DLY_RATE_2, AGNCY_HRLY_RATE_2, FMLY_DLY_RATE_2, FMLY_HRLY_RATE_2,
                    AGNCY_AC_HRS_2, FMLY_AC_HRS_2, AGNCY_DLY_RATE_3, AGNCY_HRLY_RATE_3,
                    FMLY_DLY_RATE_3, FMLY_HRLY_RATE_3, AGNCY_AC_HRS_3, FMLY_AC_HRS_3,
                    AGNCY_DLY_RATE_4, AGNCY_HRLY_RATE_4, FMLY_DLY_RATE_4, FMLY_HRLY_RATE_4,
                    AGNCY_AC_HRS_4, FMLY_AC_HRS_4, AGNCY_LEVEL_OF_CARE_1, AGNCY_LEVEL_OF_CARE_2,
                    AGNCY_LEVEL_OF_CARE_3, AGNCY_LEVEL_OF_CARE_4, FMLY_LEVEL_OF_CARE_1,
                    FMLY_LEVEL_OF_CARE_2, FMLY_LEVEL_OF_CARE_3, FMLY_LEVEL_OF_CARE_4,
                    AVG_MNTHLY_RATE, ROOM_DLY_RATE, PTD_RESERVES_AS_OF_DATE
                ) VALUES (
                    (SELECT NVL(MAX(TXN_ID), 0) FROM MCCA_CSR WHERE CARRIER_CLM_NUM = ? AND CLID = ? AND REC_TYP = ?) + 1,
                    ?, ?, ?, ?, ?, SYSDATE,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """
            params = [
                csr_detail.carrier_claim_num,
                csr_detail.clid,
                csr_detail.record_type,
                csr_detail.carrier_claim_num,
                csr_detail.clid,
                csr_detail.csr_seq,
                csr_detail.record_type,
                csr_detail.status,
                csr_detail.plcy_exp_date,
                csr_detail.demand,
                csr_detail.suit_date,
                csr_detail.litgn_issue_desc,
                csr_detail.ssdi_appln_status,
                csr_detail.clmt_crnt_condn_futr_care_desc,
                csr_detail.mcca_clm_num,
                csr_detail.status_lst,
                csr_detail.claimt_prefix,
                csr_detail.claimt_frst_name,
                csr_detail.claimt_midl_in,
                csr_detail.claimt_lst_name,
                csr_detail.claimt_gender,
                csr_detail.claimt_dob,
                csr_detail.claimt_addres1,
                csr_detail.claimt_addres2,
                csr_detail.claimt_city,
                csr_detail.claimt_state,
                csr_detail.claimt_zip,
                csr_detail.claimt_county,
                csr_detail.health_crr,
                csr_detail.claimt_status_cd,
                csr_detail.relation_cd,
                csr_detail.seatbelt_cd,
                csr_detail.air_bg_use_cd,
                csr_detail.injured_desc,
                csr_detail.injured_cd,
                csr_detail.claimt_death_dt,
                csr_detail.carrier_user_id,
                csr_detail.csr_due_dt,
                csr_detail.prjctd_lng_trm_instl_amt,
                csr_detail.prjctd_lng_trm_medl_amt,
                csr_detail.prjctd_lng_trm_othr_amt,
                csr_detail.prjctd_lng_trm_outstndg_amt,
                csr_detail.med_paid_to_dt,
                csr_detail.med_net_resrv,
                csr_detail.med_incurd,
                csr_detail.res_chng,
                csr_detail.new_net,
                csr_detail.new_incrd,
                csr_detail.wl_es_sl_paid_to_dt,
                csr_detail.wl_es_sl_net,
                csr_detail.wl_es_sl_incrd,
                csr_detail.hsptl_12_mnth_cst,
                csr_detail.hsptl_annl_futr_cst,
                csr_detail.doc_lab_12_mnth_cst,
                csr_detail.doc_lab_annl_futr_cst,
                csr_detail.home_pur_12_mnth_cst,
                csr_detail.home_pur_annl_futr_cst,
                csr_detail.veh_pur_modfn_12_mnth_cst,
                csr_detail.veh_pur_annl_futr_cst,
                csr_detail.eqpmt_pur_12_mnth_cst,
                csr_detail.eqpmt_pur_annl_futr_cst,
                csr_detail.pro_12_mnth_cst,
                csr_detail.pro_annl_futr_cst,
                csr_detail.pre_drg_sup_12_mnth_cst,
                csr_detail.pre_drg_sup_annl_futr_cst,
                csr_detail.therap_rehab_12_mnth_cst,
                csr_detail.therap_rehab_annl_futr_cst,
                csr_detail.trnsprt_12_mnth_cst,
                csr_detail.trnsprt_annl_futr_cst,
                csr_detail.case_mgmt_12_mnth_cst,
                csr_detail.case_mgmt_annl_futr_cst,
                csr_detail.wgs_srv_sr_loss_12_mnth_cst,
                csr_detail.wgs_srv_sr_loss_anl_futr_cst,
                csr_detail.othr_12_mnth_cst,
                csr_detail.othr_annl_futr_cst,
                csr_detail.totl_12_mnth_cst,
                csr_detail.tot_annl_futr_cst,
                csr_detail.resdntl_faclty_mnth_rate,
                csr_detail.agncy_dly_rate,
                csr_detail.agncy_hrly_rate,
                csr_detail.fmly_hrly_rate,
                csr_detail.fmly_dly_rate,
                csr_detail.agncy_ac_hrs,
                csr_detail.fmly_ac_hrs,
                csr_detail.health_ins_in_force,
                csr_detail.claimt_is_dceasd_ind,
                csr_detail.cordnt_no_fault,
                csr_detail.pip_clm_in_litg_ind,
                csr_detail.are_issue_in_litg_ind,
                csr_detail.inj_party_app_ssdi_ind,
                csr_detail.is_rvwd_or_uptd,
                csr_detail.prbl_life_tm_care_ind,
                csr_detail.noflt_hcc_cord_ind,
                csr_detail.closed_ind,
                csr_detail.retention_ind,
                csr_detail.retention_amt,
                csr_detail.life_exptncy,
                csr_detail.all_inj_cl_comb_paid_to_dt_med,
                csr_detail.al_inj_cl_cm_pd_to_dt_wl_es_sl,
                csr_detail.alinj_cl_cm_pd_to_dt_medwlessl,
                csr_detail.assign_to,
                BatchConstants.BATCH_LST_UPDTING_PRSN if csr_detail.last_updated_by else None,
                csr_detail.carrier_id,
                csr_detail.ws_pol_cord_on_dt_loss,
                csr_detail.crnt_sts_clm_isues_in_dispte,
                csr_detail.lock_status,
                csr_detail.submitted_to,
                csr_detail.submitted_by,
                csr_detail.icn_sub_to,
                csr_detail.submitted_date,
                csr_detail.all_inj_cl_comb_paid_to_dt_res,
                csr_detail.alinj_cl_cm_pd_to_dt_medwlres,
                csr_detail.agncy_dly_rate_2,
                csr_detail.agncy_hrly_rate_2,
                csr_detail.fmly_dly_rate_2,
                csr_detail.fmly_hrly_rate_2,
                csr_detail.agncy_ac_hrs_2,
                csr_detail.fmly_ac_hrs_2,
                csr_detail.agncy_dly_rate_3,
                csr_detail.agncy_hrly_rate_3,
                csr_detail.fmly_dly_rate_3,
                csr_detail.fmly_hrly_rate_3,
                csr_detail.agncy_ac_hrs_3,
                csr_detail.fmly_ac_hrs_3,
                csr_detail.agncy_dly_rate_4,
                csr_detail.agncy_hrly_rate_4,
                csr_detail.fmly_dly_rate_4,
                csr_detail.fmly_hrly_rate_4,
                csr_detail.agncy_ac_hrs_4,
                csr_detail.fmly_ac_hrs_4,
                csr_detail.agncy_level_of_care_1,
                csr_detail.agncy_level_of_care_2,
                csr_detail.agncy_level_of_care_3,
                csr_detail.agncy_level_of_care_4,
                csr_detail.fmly_level_of_care_1,
                csr_detail.fmly_level_of_care_2,
                csr_detail.fmly_level_of_care_3,
                csr_detail.fmly_level_of_care_4,
                csr_detail.avg_monthly_rate,
                csr_detail.room_dly_rate,
                csr_detail.ptd_reserve_asof_date,
            ]
            self.update(sql, params)
        except Exception as exc:
            logger.error(
                "Error in CsrJdbcDaoImpl.update_csr_amount() CARRIER_CLM_NUM=%s CSR_SEQ=%s CLID=%s: %s",
                csr_detail.carrier_claim_num,
                csr_detail.csr_seq,
                csr_detail.clid,
                exc,
            )

    def update_csr_claimant_info(self, csr_detail: TmpCsrDetail) -> None:
        """
        Inserts a new version row (TXN_ID + 1) into MCCA_CSR for an existing pending CSR record
        (where STATUS='PN' at MAX(CSR_SEQ) and MAX(TXN_ID)).
        Exact port of CsrJdbcDaoImpl.updateCsrClaimantInfo(final TmpCsrDetail csrDetail) (lines 1325-1558).
        """
        try:
            sql = """
                INSERT INTO MCCA_CSR (
                    TXN_ID, CARRIER_CLM_NUM, CLID, CSR_SEQ, REC_TYP, STATUS, LST_UPDT_TIME_STMP,
                    PLCY_EXP_DATE, DEMAND, SUIT_DT, LITGN_ISSUE_DESC, SSDI_APPLN_STATUS,
                    CLMT_CRNT_CONDN_FUTR_CARE_DESC, MCCA_CLM_NUM, STATUS_LST, CLMT_SUFFIX,
                    CLMT_FST_NAME, CLMT_LST_NAME, CLMT_GNDR, CLMT_DOB, CLMT_ADD1, CLMT_ADD2,
                    CLMT_CITY, CLMT_STATE, CLMT_ZIP, CLMT_CNTY, HLTH_CRR, CLMT_STAT_CD,
                    RLN_CD, SEABLT_CD, ARBG_USE_CD, INJ_DESC, INJ_CD, DEATH_DT, CRR_USR_ID,
                    CSR_DUE_DT, PRJCTD_LNG_TRM_INSTL_AMT, PRJCTD_LNG_TRM_MEDL_AMT,
                    PRJCTD_LNG_TRM_OTHR_AMT, PRJCTD_LNG_TRM_OUTSTNDG_AMT, MED_PAID_TO_DT,
                    MED_NET_RESRV, MED_INCURD, RES_CHNG, NEW_NET, NEW_INCRD, WL_ES_SL_PAID_TO_DT,
                    WL_ES_SL_NET, WL_ES_SL_INCRD, HSPTL_12_MNTH_CST, HSPTL_ANNL_FUTR_CST,
                    DOC_LAB_12_MNTH_CST, DOC_LAB_ANNL_FUTR_CST, HOME_PUR_12_MNTH_CST,
                    HOME_PUR_ANNL_FUTR_CST, VEH_PUR_MODFN_12_MNTH_CST, VEH_PUR_ANNL_FUTR_CST,
                    EQPMT_PUR_12_MNTH_CST, EQPMT_PUR_ANNL_FUTR_CST, PRO_12_MNTH_CST,
                    PRO_ANNL_FUTR_CST, PRE_DRG_SUP_12_MNTH_CST, PRE_DRG_SUP_ANNL_FUTR_CST,
                    THERAP_REHAB_12_MNTH_CST, THERAP_REHAB_ANNL_FUTR_CST, TRNSPRT_12_MNTH_CST,
                    TRNSPRT_ANNL_FUTR_CST, CASE_MGMT_12_MNTH_CST, CASE_MGMT_ANNL_FUTR_CST,
                    WGS_SRV_SR_LOSS_12_MNTH_CST, WGS_SRV_SR_LOSS_ANL_FUTR_CST, OTHR_12_MNTH_CST,
                    OTHR_ANNL_FUTR_CST, TOTL_12_MNTH_CST, TOT_ANNL_FUTR_CST,
                    RESDNTL_FACLTY_MNTH_RATE, AGNCY_DLY_RATE, AGNCY_HRLY_RATE, FMLY_DLY_RATE,
                    FMLY_HRLY_RATE, AGNCY_AC_HRS, FMLY_AC_HRS, HLTH_INS_INFORCE_IND,
                    CLMT_DCSD_IND, COORDINATE_NO_FLT_IND, PIP_CLM_LITIGN_IND, LITGN_ISSUE_IND,
                    INJ_PRTY_APPLD_SSDI_IND, IS_RVWD_OR_UPTD, PRBL_LIFE_TM_CARE_IND,
                    NOFLT_HCC_CORD_IND, CLOSED_IND, RETENTION, RETNTON_AMT, LIFE_EXPTNCY,
                    ALL_INJ_CL_COMB_PAID_TO_DT_MED, AL_INJ_CL_CM_PD_TO_DT_WL_ES_SL,
                    ALINJ_CL_CM_PD_TO_DT_MEDWLESSL, ASSGND_PRSN, LST_UPDTING_PRSN, CRR_ID,
                    WS_PLCY_CORDNTD_DT_OF_LOSS_IND, CRNT_STS_CLM_ISUES_IN_DISPTE, LOCK_STATUS,
                    SUBMITTED_TO, SUBMITTED_BY, ICN_SUB_TO, SUBMITTED_DATE,
                    ALL_INJ_CL_COMB_PAID_TO_DT_RES, ALINJ_CL_CM_PD_TO_DT_MEDWLRES, CLMT_MI,
                    AGNCY_DLY_RATE_2, AGNCY_HRLY_RATE_2, FMLY_DLY_RATE_2, FMLY_HRLY_RATE_2,
                    AGNCY_AC_HRS_2, FMLY_AC_HRS_2, AGNCY_DLY_RATE_3, AGNCY_HRLY_RATE_3,
                    FMLY_DLY_RATE_3, FMLY_HRLY_RATE_3, AGNCY_AC_HRS_3, FMLY_AC_HRS_3,
                    AGNCY_DLY_RATE_4, AGNCY_HRLY_RATE_4, FMLY_DLY_RATE_4, FMLY_HRLY_RATE_4,
                    AGNCY_AC_HRS_4, FMLY_AC_HRS_4, AGNCY_LEVEL_OF_CARE_1, AGNCY_LEVEL_OF_CARE_2,
                    AGNCY_LEVEL_OF_CARE_3, AGNCY_LEVEL_OF_CARE_4, FMLY_LEVEL_OF_CARE_1,
                    FMLY_LEVEL_OF_CARE_2, FMLY_LEVEL_OF_CARE_3, FMLY_LEVEL_OF_CARE_4,
                    AVG_MNTHLY_RATE, ROOM_DLY_RATE
                )
                SELECT
                    TXN_ID + 1, CARRIER_CLM_NUM, CLID, CSR_SEQ, REC_TYP, STATUS, SYSDATE,
                    PLCY_EXP_DATE, ?, ?, ?, SSDI_APPLN_STATUS,
                    CLMT_CRNT_CONDN_FUTR_CARE_DESC, MCCA_CLM_NUM, STATUS_LST, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, CLMT_CNTY, ?, ?,
                    ?, ?, ?, ?, ?, ?, CRR_USR_ID,
                    CSR_DUE_DT, PRJCTD_LNG_TRM_INSTL_AMT, PRJCTD_LNG_TRM_MEDL_AMT,
                    PRJCTD_LNG_TRM_OTHR_AMT, PRJCTD_LNG_TRM_OUTSTNDG_AMT, MED_PAID_TO_DT,
                    MED_NET_RESRV, MED_INCURD, RES_CHNG, NEW_NET, NEW_INCRD, WL_ES_SL_PAID_TO_DT,
                    WL_ES_SL_NET, WL_ES_SL_INCRD, HSPTL_12_MNTH_CST, HSPTL_ANNL_FUTR_CST,
                    DOC_LAB_12_MNTH_CST, DOC_LAB_ANNL_FUTR_CST, HOME_PUR_12_MNTH_CST,
                    HOME_PUR_ANNL_FUTR_CST, VEH_PUR_MODFN_12_MNTH_CST, VEH_PUR_ANNL_FUTR_CST,
                    EQPMT_PUR_12_MNTH_CST, EQPMT_PUR_ANNL_FUTR_CST, PRO_12_MNTH_CST,
                    PRO_ANNL_FUTR_CST, PRE_DRG_SUP_12_MNTH_CST, PRE_DRG_SUP_ANNL_FUTR_CST,
                    THERAP_REHAB_12_MNTH_CST, THERAP_REHAB_ANNL_FUTR_CST, TRNSPRT_12_MNTH_CST,
                    TRNSPRT_ANNL_FUTR_CST, CASE_MGMT_12_MNTH_CST, CASE_MGMT_ANNL_FUTR_CST,
                    WGS_SRV_SR_LOSS_12_MNTH_CST, WGS_SRV_SR_LOSS_ANL_FUTR_CST, OTHR_12_MNTH_CST,
                    OTHR_ANNL_FUTR_CST, TOTL_12_MNTH_CST, TOT_ANNL_FUTR_CST,
                    RESDNTL_FACLTY_MNTH_RATE, AGNCY_DLY_RATE, AGNCY_HRLY_RATE, FMLY_DLY_RATE,
                    FMLY_HRLY_RATE, AGNCY_AC_HRS, FMLY_AC_HRS, HLTH_INS_INFORCE_IND,
                    ?, ?, ?, ?,
                    INJ_PRTY_APPLD_SSDI_IND, IS_RVWD_OR_UPTD, PRBL_LIFE_TM_CARE_IND,
                    NOFLT_HCC_CORD_IND, CLOSED_IND, RETENTION, ?, LIFE_EXPTNCY,
                    ALL_INJ_CL_COMB_PAID_TO_DT_MED, AL_INJ_CL_CM_PD_TO_DT_WL_ES_SL,
                    ALINJ_CL_CM_PD_TO_DT_MEDWLESSL, ASSGND_PRSN, ?, ?,
                    WS_PLCY_CORDNTD_DT_OF_LOSS_IND, CRNT_STS_CLM_ISUES_IN_DISPTE, LOCK_STATUS,
                    SUBMITTED_TO, SUBMITTED_BY, ICN_SUB_TO, SUBMITTED_DATE,
                    ALL_INJ_CL_COMB_PAID_TO_DT_RES, ALINJ_CL_CM_PD_TO_DT_MEDWLRES, ?,
                    AGNCY_DLY_RATE_2, AGNCY_HRLY_RATE_2, FMLY_DLY_RATE_2, FMLY_HRLY_RATE_2,
                    AGNCY_AC_HRS_2, FMLY_AC_HRS_2, AGNCY_DLY_RATE_3, AGNCY_HRLY_RATE_3,
                    FMLY_DLY_RATE_3, FMLY_HRLY_RATE_3, AGNCY_AC_HRS_3, FMLY_AC_HRS_3,
                    AGNCY_DLY_RATE_4, AGNCY_HRLY_RATE_4, FMLY_DLY_RATE_4, FMLY_HRLY_RATE_4,
                    AGNCY_AC_HRS_4, FMLY_AC_HRS_4, AGNCY_LEVEL_OF_CARE_1, AGNCY_LEVEL_OF_CARE_2,
                    AGNCY_LEVEL_OF_CARE_3, AGNCY_LEVEL_OF_CARE_4, FMLY_LEVEL_OF_CARE_1,
                    FMLY_LEVEL_OF_CARE_2, FMLY_LEVEL_OF_CARE_3, FMLY_LEVEL_OF_CARE_4,
                    AVG_MNTHLY_RATE, ROOM_DLY_RATE
                FROM MCCA_CSR CSR
                WHERE CARRIER_CLM_NUM = ?
                  AND CLID = ?
                  AND CSR_SEQ = (
                      SELECT MAX(CSR1.CSR_SEQ)
                      FROM MCCA_CSR CSR1
                      WHERE CSR1.CARRIER_CLM_NUM = CSR.CARRIER_CLM_NUM
                        AND CSR1.CLID = CSR.CLID
                        AND CSR1.STATUS = 'PN'
                  )
                  AND TXN_ID = (
                      SELECT MAX(CSR1.TXN_ID)
                      FROM MCCA_CSR CSR1
                      WHERE CSR1.CARRIER_CLM_NUM = CSR.CARRIER_CLM_NUM
                        AND CSR1.CLID = CSR.CLID
                        AND CSR1.STATUS = 'PN'
                  )
            """
            params = [
                csr_detail.demand,
                csr_detail.suit_date,
                csr_detail.litgn_issue_desc,
                csr_detail.claimt_prefix,
                csr_detail.claimt_frst_name,
                csr_detail.claimt_lst_name,
                csr_detail.claimt_gender,
                csr_detail.claimt_dob,
                csr_detail.claimt_addres1,
                csr_detail.claimt_addres2,
                csr_detail.claimt_city,
                csr_detail.claimt_state,
                csr_detail.claimt_zip,
                csr_detail.health_crr,
                csr_detail.claimt_status_cd,
                csr_detail.relation_cd,
                csr_detail.seatbelt_cd,
                csr_detail.air_bg_use_cd,
                csr_detail.injured_desc,
                csr_detail.injured_cd,
                csr_detail.claimt_death_dt,
                csr_detail.claimt_is_dceasd_ind,
                csr_detail.cordnt_no_fault,
                csr_detail.pip_clm_in_litg_ind,
                csr_detail.are_issue_in_litg_ind,
                csr_detail.retention_amt,
                BatchConstants.BATCH_LST_UPDTING_PRSN,
                csr_detail.carrier_id,
                csr_detail.claimt_midl_in,
                csr_detail.carrier_claim_num,
                csr_detail.clid,
            ]
            self.update(sql, params)
        except Exception as exc:
            logger.error(
                "Error in CsrJdbcDaoImpl.update_csr_claimant_info() CARRIER_CLM_NUM=%s CLID=%s: %s",
                csr_detail.carrier_claim_num,
                csr_detail.clid,
                exc,
            )

    def update_icn_claimant_info(self, csr_detail: TmpCsrDetail) -> None:
        """
        Inserts a new version row (TXN_ID + 1) into MCCA_CSR for an existing ICN-typed claimant row
        (where REC_TYP='ICN' at MAX(TXN_ID)).
        Exact port of CsrJdbcDaoImpl.updateIcnClaimantInfo(final TmpCsrDetail csrDetail) (lines 1561-1789).
        """
        try:
            sql = """
                INSERT INTO MCCA_CSR (
                    TXN_ID, CARRIER_CLM_NUM, CLID, CSR_SEQ, REC_TYP, LST_UPDT_TIME_STMP,
                    PLCY_EXP_DATE, DEMAND, SUIT_DT, LITGN_ISSUE_DESC, SSDI_APPLN_STATUS,
                    CLMT_CRNT_CONDN_FUTR_CARE_DESC, MCCA_CLM_NUM, STATUS_LST, CLMT_SUFFIX,
                    CLMT_FST_NAME, CLMT_LST_NAME, CLMT_GNDR, CLMT_DOB, CLMT_ADD1, CLMT_ADD2,
                    CLMT_CITY, CLMT_STATE, CLMT_ZIP, CLMT_CNTY, HLTH_CRR, CLMT_STAT_CD,
                    RLN_CD, SEABLT_CD, ARBG_USE_CD, INJ_DESC, INJ_CD, DEATH_DT, CRR_USR_ID,
                    CSR_DUE_DT, PRJCTD_LNG_TRM_INSTL_AMT, PRJCTD_LNG_TRM_MEDL_AMT,
                    PRJCTD_LNG_TRM_OTHR_AMT, PRJCTD_LNG_TRM_OUTSTNDG_AMT, MED_PAID_TO_DT,
                    MED_NET_RESRV, MED_INCURD, RES_CHNG, NEW_NET, NEW_INCRD, WL_ES_SL_PAID_TO_DT,
                    WL_ES_SL_NET, WL_ES_SL_INCRD, HSPTL_12_MNTH_CST, HSPTL_ANNL_FUTR_CST,
                    DOC_LAB_12_MNTH_CST, DOC_LAB_ANNL_FUTR_CST, HOME_PUR_12_MNTH_CST,
                    HOME_PUR_ANNL_FUTR_CST, VEH_PUR_MODFN_12_MNTH_CST, VEH_PUR_ANNL_FUTR_CST,
                    EQPMT_PUR_12_MNTH_CST, EQPMT_PUR_ANNL_FUTR_CST, PRO_12_MNTH_CST,
                    PRO_ANNL_FUTR_CST, PRE_DRG_SUP_12_MNTH_CST, PRE_DRG_SUP_ANNL_FUTR_CST,
                    THERAP_REHAB_12_MNTH_CST, THERAP_REHAB_ANNL_FUTR_CST, TRNSPRT_12_MNTH_CST,
                    TRNSPRT_ANNL_FUTR_CST, CASE_MGMT_12_MNTH_CST, CASE_MGMT_ANNL_FUTR_CST,
                    WGS_SRV_SR_LOSS_12_MNTH_CST, WGS_SRV_SR_LOSS_ANL_FUTR_CST, OTHR_12_MNTH_CST,
                    OTHR_ANNL_FUTR_CST, TOTL_12_MNTH_CST, TOT_ANNL_FUTR_CST,
                    RESDNTL_FACLTY_MNTH_RATE, AGNCY_DLY_RATE, AGNCY_HRLY_RATE, FMLY_DLY_RATE,
                    FMLY_HRLY_RATE, AGNCY_AC_HRS, FMLY_AC_HRS, HLTH_INS_INFORCE_IND,
                    CLMT_DCSD_IND, COORDINATE_NO_FLT_IND, PIP_CLM_LITIGN_IND, LITGN_ISSUE_IND,
                    INJ_PRTY_APPLD_SSDI_IND, IS_RVWD_OR_UPTD, PRBL_LIFE_TM_CARE_IND,
                    NOFLT_HCC_CORD_IND, CLOSED_IND, RETENTION, RETNTON_AMT, LIFE_EXPTNCY,
                    ALL_INJ_CL_COMB_PAID_TO_DT_MED, AL_INJ_CL_CM_PD_TO_DT_WL_ES_SL,
                    ALINJ_CL_CM_PD_TO_DT_MEDWLESSL, ASSGND_PRSN, LST_UPDTING_PRSN, CRR_ID,
                    WS_PLCY_CORDNTD_DT_OF_LOSS_IND, CRNT_STS_CLM_ISUES_IN_DISPTE, LOCK_STATUS,
                    SUBMITTED_TO, SUBMITTED_BY, ICN_SUB_TO, SUBMITTED_DATE,
                    ALL_INJ_CL_COMB_PAID_TO_DT_RES, ALINJ_CL_CM_PD_TO_DT_MEDWLRES, CLMT_MI, STATUS,
                    AGNCY_DLY_RATE_2, AGNCY_HRLY_RATE_2, FMLY_DLY_RATE_2, FMLY_HRLY_RATE_2,
                    AGNCY_AC_HRS_2, FMLY_AC_HRS_2, AGNCY_DLY_RATE_3, AGNCY_HRLY_RATE_3,
                    FMLY_DLY_RATE_3, FMLY_HRLY_RATE_3, AGNCY_AC_HRS_3, FMLY_AC_HRS_3,
                    AGNCY_DLY_RATE_4, AGNCY_HRLY_RATE_4, FMLY_DLY_RATE_4, FMLY_HRLY_RATE_4,
                    AGNCY_AC_HRS_4, FMLY_AC_HRS_4, AGNCY_LEVEL_OF_CARE_1, AGNCY_LEVEL_OF_CARE_2,
                    AGNCY_LEVEL_OF_CARE_3, AGNCY_LEVEL_OF_CARE_4, FMLY_LEVEL_OF_CARE_1,
                    FMLY_LEVEL_OF_CARE_2, FMLY_LEVEL_OF_CARE_3, FMLY_LEVEL_OF_CARE_4,
                    AVG_MNTHLY_RATE, ROOM_DLY_RATE
                )
                SELECT
                    TXN_ID + 1, CARRIER_CLM_NUM, CLID, CSR_SEQ, REC_TYP, SYSDATE,
                    PLCY_EXP_DATE, ?, ?, ?, SSDI_APPLN_STATUS,
                    CLMT_CRNT_CONDN_FUTR_CARE_DESC, MCCA_CLM_NUM, STATUS_LST, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, CLMT_CNTY, ?, ?,
                    ?, ?, ?, ?, ?, ?, CRR_USR_ID,
                    CSR_DUE_DT, PRJCTD_LNG_TRM_INSTL_AMT, PRJCTD_LNG_TRM_MEDL_AMT,
                    PRJCTD_LNG_TRM_OTHR_AMT, PRJCTD_LNG_TRM_OUTSTNDG_AMT, MED_PAID_TO_DT,
                    MED_NET_RESRV, MED_INCURD, RES_CHNG, NEW_NET, NEW_INCRD, WL_ES_SL_PAID_TO_DT,
                    WL_ES_SL_NET, WL_ES_SL_INCRD, HSPTL_12_MNTH_CST, HSPTL_ANNL_FUTR_CST,
                    DOC_LAB_12_MNTH_CST, DOC_LAB_ANNL_FUTR_CST, HOME_PUR_12_MNTH_CST,
                    HOME_PUR_ANNL_FUTR_CST, VEH_PUR_MODFN_12_MNTH_CST, VEH_PUR_ANNL_FUTR_CST,
                    EQPMT_PUR_12_MNTH_CST, EQPMT_PUR_ANNL_FUTR_CST, PRO_12_MNTH_CST,
                    PRO_ANNL_FUTR_CST, PRE_DRG_SUP_12_MNTH_CST, PRE_DRG_SUP_ANNL_FUTR_CST,
                    THERAP_REHAB_12_MNTH_CST, THERAP_REHAB_ANNL_FUTR_CST, TRNSPRT_12_MNTH_CST,
                    TRNSPRT_ANNL_FUTR_CST, CASE_MGMT_12_MNTH_CST, CASE_MGMT_ANNL_FUTR_CST,
                    WGS_SRV_SR_LOSS_12_MNTH_CST, WGS_SRV_SR_LOSS_ANL_FUTR_CST, OTHR_12_MNTH_CST,
                    OTHR_ANNL_FUTR_CST, TOTL_12_MNTH_CST, TOT_ANNL_FUTR_CST,
                    RESDNTL_FACLTY_MNTH_RATE, AGNCY_DLY_RATE, AGNCY_HRLY_RATE, FMLY_DLY_RATE,
                    FMLY_HRLY_RATE, AGNCY_AC_HRS, FMLY_AC_HRS, HLTH_INS_INFORCE_IND,
                    ?, ?, ?, ?,
                    INJ_PRTY_APPLD_SSDI_IND, IS_RVWD_OR_UPTD, PRBL_LIFE_TM_CARE_IND,
                    NOFLT_HCC_CORD_IND, CLOSED_IND, RETENTION, ?, LIFE_EXPTNCY,
                    ALL_INJ_CL_COMB_PAID_TO_DT_MED, AL_INJ_CL_CM_PD_TO_DT_WL_ES_SL,
                    ALINJ_CL_CM_PD_TO_DT_MEDWLESSL, ASSGND_PRSN, ?, ?,
                    WS_PLCY_CORDNTD_DT_OF_LOSS_IND, CRNT_STS_CLM_ISUES_IN_DISPTE, LOCK_STATUS,
                    SUBMITTED_TO, SUBMITTED_BY, ICN_SUB_TO, SUBMITTED_DATE,
                    ALL_INJ_CL_COMB_PAID_TO_DT_RES, ALINJ_CL_CM_PD_TO_DT_MEDWLRES, ?, ?,
                    AGNCY_DLY_RATE_2, AGNCY_HRLY_RATE_2, FMLY_DLY_RATE_2, FMLY_HRLY_RATE_2,
                    AGNCY_AC_HRS_2, FMLY_AC_HRS_2, AGNCY_DLY_RATE_3, AGNCY_HRLY_RATE_3,
                    FMLY_DLY_RATE_3, FMLY_HRLY_RATE_3, AGNCY_AC_HRS_3, FMLY_AC_HRS_3,
                    AGNCY_DLY_RATE_4, AGNCY_HRLY_RATE_4, FMLY_DLY_RATE_4, FMLY_HRLY_RATE_4,
                    AGNCY_AC_HRS_4, FMLY_AC_HRS_4, AGNCY_LEVEL_OF_CARE_1, AGNCY_LEVEL_OF_CARE_2,
                    AGNCY_LEVEL_OF_CARE_3, AGNCY_LEVEL_OF_CARE_4, FMLY_LEVEL_OF_CARE_1,
                    FMLY_LEVEL_OF_CARE_2, FMLY_LEVEL_OF_CARE_3, FMLY_LEVEL_OF_CARE_4,
                    AVG_MNTHLY_RATE, ROOM_DLY_RATE
                FROM MCCA_CSR CSR
                WHERE CARRIER_CLM_NUM = ?
                  AND CLID = ?
                  AND CSR.REC_TYP = 'ICN'
                  AND TXN_ID = (
                      SELECT MAX(CSR1.TXN_ID)
                      FROM MCCA_CSR CSR1
                      WHERE CSR1.CARRIER_CLM_NUM = CSR.CARRIER_CLM_NUM
                        AND CSR1.CLID = CSR.CLID
                        AND CSR1.REC_TYP = 'ICN'
                  )
            """
            params = [
                csr_detail.demand,
                csr_detail.suit_date,
                csr_detail.litgn_issue_desc,
                csr_detail.claimt_prefix,
                csr_detail.claimt_frst_name,
                csr_detail.claimt_lst_name,
                csr_detail.claimt_gender,
                csr_detail.claimt_dob,
                csr_detail.claimt_addres1,
                csr_detail.claimt_addres2,
                csr_detail.claimt_city,
                csr_detail.claimt_state,
                csr_detail.claimt_zip,
                csr_detail.health_crr,
                csr_detail.claimt_status_cd,
                csr_detail.relation_cd,
                csr_detail.seatbelt_cd,
                csr_detail.air_bg_use_cd,
                csr_detail.injured_desc,
                csr_detail.injured_cd,
                csr_detail.claimt_death_dt,
                csr_detail.claimt_is_dceasd_ind,
                csr_detail.cordnt_no_fault,
                csr_detail.pip_clm_in_litg_ind,
                csr_detail.are_issue_in_litg_ind,
                csr_detail.retention_amt,
                BatchConstants.BATCH_LST_UPDTING_PRSN,
                csr_detail.carrier_id,
                csr_detail.claimt_midl_in,
                BatchConstants.STATUS_PENDING_CD,
                csr_detail.carrier_claim_num,
                csr_detail.clid,
            ]
            self.update(sql, params)
        except Exception as exc:
            logger.error(
                "Error in CsrJdbcDaoImpl.update_icn_claimant_info() CARRIER_CLM_NUM=%s CLID=%s: %s",
                csr_detail.carrier_claim_num,
                csr_detail.clid,
                exc,
            )

    def insert_projections(self, csr_detail: TmpCsrDetail) -> None:
        """
        Inserts an initial projection row into MCCA_PROJECTIONS.
        Exact port of CsrJdbcDaoImpl.insertProjections(final TmpCsrDetail csrDetail) (lines 1794-1825).
        """
        try:
            sql = """
                INSERT INTO MCCA_PROJECTIONS (
                    TXN_ID, CARRIER_CLM_NUM, CLID, REC_TYP, PROJN_SEQ, CSR_SEQ, LST_UPDT_TIME_STMP
                ) VALUES (
                    (SELECT NVL(MAX(TXN_ID), 0) FROM MCCA_PROJECTIONS WHERE CARRIER_CLM_NUM = ? AND CLID = ?) + 1,
                    ?, ?, ?, ?, ?, SYSDATE
                )
            """
            self.update(
                sql,
                [
                    csr_detail.carrier_claim_num,
                    csr_detail.clid,
                    csr_detail.carrier_claim_num,
                    csr_detail.clid,
                    csr_detail.record_type,
                    1,
                    csr_detail.csr_seq,
                ],
            )
        except Exception as exc:
            logger.error(
                "Error in CsrJdbcDaoImpl.insert_projections() CARRIER_CLM_NUM=%s CLID=%s: %s",
                csr_detail.carrier_claim_num,
                csr_detail.clid,
                exc,
            )

    def search_icn_csr_data(self, carrier_clm_num: str) -> List[CsrDetail]:
        """
        Returns all latest MCCA_CSR rows for CARRIER_CLM_NUM where REC_TYP='ICN'
        and (PRBL_LIFE_TM_CARE_IND='Y' OR PRBL_LIFE_TM_CARE_IND IS NULL).
        Exact port of CsrJdbcDaoImpl.searchIcnCsrData(String carrierClmNum).
        """
        sql = """
            WITH Latest_CSR AS (
                SELECT DISTINCT ON (CLID, REC_TYP)
                    *
                FROM MCCA_CSR
                WHERE CARRIER_CLM_NUM = ?
                  AND REC_TYP = ?
                ORDER BY CLID, REC_TYP, TXN_ID DESC
            )
            SELECT *
            FROM Latest_CSR CSR
            WHERE (CSR.PRBL_LIFE_TM_CARE_IND = 'Y' OR CSR.PRBL_LIFE_TM_CARE_IND IS NULL)
            ORDER BY CSR.LST_UPDT_TIME_STMP DESC
        """
        return self.query(sql, map_csr_amount_update_row, [carrier_clm_num, BatchConstants.ICN_REC_TYPE])

    def get_max_others_txn_id(self, carrier_clm_num: str, clid: str, record_type: str) -> int:
        """Exact port of CsrJdbcDaoImpl.getMaxOthersTxnId()."""
        sql = """
            SELECT NVL(MAX(OTHERINJPYMT.TXN_ID), 0)
            FROM MCCA_OTHR_INJ_CLMTS_PYMT OTHERINJPYMT
            WHERE OTHERINJPYMT.CARRIER_CLM_NUM = ?
              AND OTHERINJPYMT.CLID = ?
              AND OTHERINJPYMT.REC_TYP = ?
        """
        return self.query_for_long(sql, [carrier_clm_num, clid, record_type])

    def get_other_proj_clmtss_data(self, carrier_clm_num: str) -> List[OthrInjClmtsPymt]:
        """
        Returns MCCA_OTHR_INJ_CLMTS_PYMT rows for CSR_SEQ='0', CLID='0', REC_TYP='ICN' at MAX(TXN_ID).
        Exact port of CsrJdbcDaoImpl.getOtherProjClmtssData(String carrierClmNum).
        """
        max_txn_id = self.get_max_others_txn_id(carrier_clm_num, "0", BatchConstants.ICN_REC_TYPE)
        sql = """
            SELECT *
            FROM MCCA_OTHR_INJ_CLMTS_PYMT OTHERS
            WHERE OTHERS.CSR_SEQ = 0
              AND OTHERS.CARRIER_CLM_NUM = ?
              AND OTHERS.CLID = '0'
              AND OTHERS.REC_TYP = 'ICN'
              AND OTHERS.TXN_ID = ?
            ORDER BY OTHERS.CLM_TYPE ASC
        """
        rows = self.query_for_list(sql, [carrier_clm_num, max_txn_id])
        return [
            OthrInjClmtsPymt(
                carrier_clm_num=r.get("CARRIER_CLM_NUM"),
                clid=r.get("CLID"),
                rec_typ=r.get("REC_TYP"),
                cl_id=r.get("CL_ID"),
                clm_num=r.get("CLM_NUM"),
                clm_type=r.get("CLM_TYPE"),
                pip_ind=r.get("PIP_IND"),
                csr_seq=Decimal(str(r["CSR_SEQ"])) if r.get("CSR_SEQ") is not None else Decimal("0"),
                med=Decimal(str(r["MED"])) if r.get("MED") is not None else None,
                wl_es_sl=Decimal(str(r["WL_ES_SL"])) if r.get("WL_ES_SL") is not None else None,
                reserve_amt=Decimal(str(r["RESERVE_AMT"])) if r.get("RESERVE_AMT") is not None else None,
                other_proj_seq=int(r["OTHER_PROJ_SEQ"]) if r.get("OTHER_PROJ_SEQ") is not None else 0,
            )
            for r in rows
        ]

    def create_backup_log(self) -> None:
        """
        Logs all records in MCCA_TMP_CLMNT before deletion in Step 10.
        Exact port of CsrJdbcDaoImpl.createBackupLog() (lines 1900-1949).
        """
        rows = self.query_for_list("SELECT * FROM MCCA_TMP_CLMNT")
        logger.info("Total Records in MCCA_TMP_CLMNT : %d", len(rows))
        for row in rows:
            line = " || ".join(
                str(row.get(col, ""))
                for col in [
                    "CARRIER_CLM_NUM", "CLID", "CLMT_PREFIX", "CLMT_FST_NAME",
                    "CLMT_LST_NAME", "CLMT_GNDR", "CLMT_DOB", "CLMT_ADD1",
                    "CLMT_ADD2", "CLMT_CITY", "CLMT_STATE", "CLMT_ZIP",
                    "LITGN_ISSUE_IND", "PIP_CLM_LITIGN_IND", "INJ_DESC",
                    "COORDINATE_NO_FLT_IND", "HLTH_CRR", "CLMT_STAT_CD",
                    "RLN_CD", "SEABLT_CD", "ARBG_USE_CD", "INJ_CD",
                    "CLMT_DCSD_IND", "DEMAND", "SUIT_DT", "LITGN_ISSUE_DESC",
                    "DEATH_DT", "PIP_CLOSED_IND", "CLMT_MDL_INI",
                ]
            )
            logger.info(line)

    def delete_all(self, table_name: str) -> int:
        """Exact port of CsrJdbcDaoImpl.deleteAll(String tableName)."""
        return self.update(f"DELETE FROM {table_name}")
