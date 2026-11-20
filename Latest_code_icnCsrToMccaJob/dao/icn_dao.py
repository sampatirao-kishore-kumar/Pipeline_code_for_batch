"""
ICN JDBC DAO Implementation.
1:1 port of com.acg.mcca.batch.impl.IcnJdbcDaoImpl.

Tables Accessed:
- MCCA_ICN
- MCCA_CSR
- MCCA_CLAIM
- MCCA_LOSS_EXPENSE_DETAILS
- MCCA_RESERVES
- D_FISCAL_MONTH
- MCCA_EXCEPTION
- MCCA_CODES_DECODE
- MCCA_THRESHOLD
- MCCA_TMP_CLM
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional

from config import BatchConstants
from dao.base_dao import BaseJdbcDao
from models import IcnCsrDetail, Threshold

logger = logging.getLogger(__name__)


class IcnJdbcDaoImpl(BaseJdbcDao):
    """Exact 1:1 port of com.acg.mcca.batch.impl.IcnJdbcDaoImpl."""

    def save_icn_detail(self, icn_csr_detail: IcnCsrDetail) -> None:
        """
        Inserts a new ICN record into MCCA_ICN.
        Exact port of IcnJdbcDaoImpl.saveIcnDetail(final IcnCsrDetail icnCsrDetail).
        """
        try:
            sql = """
                INSERT INTO MCCA_ICN (
                    TXN_ID,
                    CARRIER_CLM_NUM,
                    REC_TYP,
                    STATUS,
                    LST_UPDT_TIME_STMP,
                    MCCA_CLM_NUM,
                    CARRIER_PLCY_NUM,
                    PLCY_EFF_DT,
                    PLCY_EXP_DT,
                    LOSS_DT,
                    ACC_DT,
                    ACC_DESC,
                    ACC_ADD1,
                    ACC_ADD2,
                    ACC_CITY,
                    ACC_STATE,
                    ACC_ZIP,
                    ACC_CNTY,
                    CRR_ADJ_FST_NAME,
                    CRR_ADJ_LST_NAME,
                    CRR_ADJ_PHN_NUM,
                    INSRD_SUFFIX,
                    INSRD_FST_NAME,
                    INSRD_MI,
                    INSRD_LST_NAME,
                    INSRD_ADD1,
                    INSRD_ADD2,
                    INSRD_CITY,
                    INSRD_STATE,
                    INSRD_ZIP,
                    INSRD_CNTY,
                    INSRD_GENDER,
                    INSRD_DOB,
                    COMP_CRS_CLM_IND,
                    MAIPF_JUA_IND,
                    COM_PLCY_IND,
                    PLCY_WRTN_CRDNT_BAS,
                    LST_UPDTING_PRSN,
                    BATCH_NUM,
                    CSR_OPEN_CLS_ST_FLG,
                    CROSS_COMP_CLM_NUM,
                    RETENTION,
                    THRESHOLD
                ) VALUES (
                    (SELECT NVL(MAX(TXN_ID), 0) FROM MCCA_ICN WHERE CARRIER_CLM_NUM = ? AND REC_TYP = ?) + 1,
                    ?, ?, ?, SYSDATE,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """
            params = [
                icn_csr_detail.carrier_claim_num,
                BatchConstants.ICN_REC_TYPE,
                icn_csr_detail.carrier_claim_num,
                BatchConstants.ICN_REC_TYPE,
                icn_csr_detail.status,
                Decimal(icn_csr_detail.mcca_claim_num) if icn_csr_detail.mcca_claim_num else None,
                icn_csr_detail.carrier_policy_num,
                icn_csr_detail.policy_effc_dt,
                icn_csr_detail.policy_exp_dt,
                icn_csr_detail.date_of_loss,
                icn_csr_detail.accident_date,
                icn_csr_detail.accident_desc,
                icn_csr_detail.accident_addr1,
                icn_csr_detail.accident_addr2,
                icn_csr_detail.accident_city,
                icn_csr_detail.accident_state,
                icn_csr_detail.accident_zip,
                icn_csr_detail.accident_county,
                icn_csr_detail.adjuster_frst_name,
                icn_csr_detail.adjuster_lst_name,
                icn_csr_detail.adjuster_ph_num,
                BatchConstants.PREFIX_HONOR_CD
                if icn_csr_detail.insured_prefix
                and icn_csr_detail.insured_prefix.lower() == BatchConstants.PREFIX_HONOR.lower()
                else icn_csr_detail.insured_prefix,
                icn_csr_detail.insured_frst_name,
                icn_csr_detail.insured_midl_in,
                icn_csr_detail.insured_lst_name,
                icn_csr_detail.insured_addr1,
                icn_csr_detail.insured_addr2,
                icn_csr_detail.insured_city,
                icn_csr_detail.insured_state,
                icn_csr_detail.insured_zip,
                icn_csr_detail.insured_county,
                icn_csr_detail.insured_gender,
                icn_csr_detail.insured_dob,
                icn_csr_detail.comp_crs_clm_ind,
                icn_csr_detail.maipf_jua_ind,
                icn_csr_detail.com_plcy_ind,
                icn_csr_detail.plcy_wrtn_crdnt_bas,
                BatchConstants.BATCH_LST_UPDTING_PRSN,
                icn_csr_detail.batch_num,
                BatchConstants.PARENT,
                icn_csr_detail.cross_comp_clm_num,
                Decimal(str(icn_csr_detail.retention_amt)) if icn_csr_detail.retention_amt is not None else None,
                Decimal(str(icn_csr_detail.threshold_amt)) if icn_csr_detail.threshold_amt is not None else None,
            ]
            self.update(sql, params)
        except Exception as exc:
            logger.error(
                "Error in IcnJdbcDaoImpl.save_icn_detail() for CARRIER_CLM_NUM=%s: %s",
                icn_csr_detail.carrier_claim_num,
                exc,
            )

    def save_icn_csr_detail(self, icn_csr_detail: IcnCsrDetail) -> None:
        """
        Inserts the claim-level (CLID='0', CSR_SEQ=0, REC_TYP='ICN') row into MCCA_CSR.
        Exact port of IcnJdbcDaoImpl.saveIcnCsrDetail(final IcnCsrDetail icnCsrDetail).
        """
        try:
            sql = """
                INSERT INTO MCCA_CSR (
                    TXN_ID,
                    CARRIER_CLM_NUM,
                    CLID,
                    CSR_SEQ,
                    REC_TYP,
                    LST_UPDT_TIME_STMP,
                    MCCA_CLM_NUM,
                    STATUS_LST,
                    CRR_USR_ID,
                    CSR_DUE_DT,
                    PRBL_LIFE_TM_CARE_IND,
                    CLOSED_IND,
                    RETNTON_AMT,
                    ASSGND_PRSN,
                    LST_UPDTING_PRSN,
                    CRR_ID,
                    WS_PLCY_CORDNTD_DT_OF_LOSS_IND,
                    STATUS
                ) VALUES (
                    (SELECT NVL(MAX(TXN_ID), 0) FROM MCCA_CSR WHERE CARRIER_CLM_NUM = ? AND CLID = ? AND REC_TYP = ?) + 1,
                    ?, ?, ?, ?, SYSDATE, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """
            params = [
                icn_csr_detail.carrier_claim_num,
                BatchConstants.ZERO,
                BatchConstants.ICN_REC_TYPE,
                icn_csr_detail.carrier_claim_num,
                BatchConstants.ZERO,
                0,
                BatchConstants.ICN_REC_TYPE,
                Decimal(icn_csr_detail.mcca_claim_num) if icn_csr_detail.mcca_claim_num else None,
                BatchConstants.OPEN,
                icn_csr_detail.carrier_user_id,
                icn_csr_detail.csr_due_dt,
                icn_csr_detail.prbl_life_tm_care_ind,
                icn_csr_detail.closed_ind,
                Decimal(str(icn_csr_detail.retention_amt)) if icn_csr_detail.retention_amt is not None else None,
                icn_csr_detail.assign_to,
                BatchConstants.BATCH_LST_UPDTING_PRSN,
                icn_csr_detail.carrier_id,
                icn_csr_detail.ws_pol_cord_on_dt_loss,
                BatchConstants.STATUS_PENDING_CD,
            ]
            self.update(sql, params)
        except Exception as exc:
            logger.error(
                "Error in IcnJdbcDaoImpl.save_icn_csr_detail() for CARRIER_CLM_NUM=%s: %s",
                icn_csr_detail.carrier_claim_num,
                exc,
            )

    def get_icn_status(self, carrier_clm_num: str) -> str:
        """
        Returns the latest STATUS from MCCA_ICN where REC_TYP='ICN'.
        Exact port of IcnJdbcDaoImpl.getIcnStatus(String carrierClmNum).
        """
        sql = """
            SELECT ICN.STATUS
            FROM MCCA_ICN ICN
            WHERE ICN.CARRIER_CLM_NUM = ?
              AND ICN.REC_TYP = 'ICN'
              AND ICN.TXN_ID = (
                  SELECT MAX(ICN2.TXN_ID)
                  FROM MCCA_ICN ICN2
                  WHERE ICN2.CARRIER_CLM_NUM = ICN.CARRIER_CLM_NUM
                    AND ICN2.REC_TYP = ICN.REC_TYP
              )
        """
        rows = self.query_for_list(sql, [carrier_clm_num])
        if rows and rows[0].get("STATUS") is not None:
            return str(rows[0]["STATUS"])
        return ""

    def stop_icn_csr_exception(self) -> List[str]:
        """
        Returns CARRIER_CLM_NUM list from MCCA_EXCEPTION where EXCEPTION_CD = '9'.
        Exact port of IcnJdbcDaoImpl.stopIcnCsrException().
        """
        sql = "SELECT DISTINCT CARRIER_CLM_NUM FROM MCCA_EXCEPTION WHERE EXCEPTION_CD = ?"
        rows = self.query_for_list(sql, [BatchConstants.STOP_ICN_CSR_EXCEPTION_CODE])
        return [str(r["CARRIER_CLM_NUM"]) for r in rows if r.get("CARRIER_CLM_NUM")]

    def get_values_from_code_decode(self, category: str) -> Dict[str, str]:
        """
        Returns CODE -> DECODE map from MCCA_CODES_DECODE for the given category.
        Exact port of IcnJdbcDaoImpl.getValuesFromCodeDecode(String category).
        """
        sql = "SELECT CODE, DECODE FROM MCCA_CODES_DECODE WHERE CATEGORY = ? ORDER BY CODE ASC"
        rows = self.query_for_list(sql, [category])
        return {str(r["CODE"]): str(r["DECODE"]) for r in rows if r.get("CODE") is not None}

    def get_paid_to_date_for_clsd_icn(self, carrier_clm_num: str, batch_date: str) -> int:
        """
        Returns total LOSSES_PAID for a closed/finance ICN up to the fiscal month prior to batch_date.
        Exact port of IcnJdbcDaoImpl.getPaidToDateForClsdIcn(String carrierClmNum, String batchDate).
        """
        sql = f"""
            SELECT NVL(SUM(LED.LOSSES_PAID), 0) AS TOTAL_PAID
            FROM MCCA_LOSS_EXPENSE_DETAILS LED
            WHERE LED.CARRIER_CLM_NUM = ?
              AND LED.TO_DATE <= (
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
              )
        """
        return self.query_for_long(sql, [carrier_clm_num])

    def get_reserves_for_clsd_icn(self, carrier_clm_num: str, batch_date: str) -> int:
        """
        Returns total RESERVE_AMOUNT for a closed/finance ICN in the fiscal month prior to batch_date.
        Exact port of IcnJdbcDaoImpl.getReservesForClsdIcn(String carrierClmNum, String batchDate).
        """
        sql = f"""
            SELECT NVL(SUM(RES.RESERVE_AMOUNT), 0) AS TOTAL_RES
            FROM MCCA_RESERVES RES
            WHERE RES.CARRIER_CLM_NUM = ?
              AND RES.RESERVE_DATE IN (
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
              )
        """
        return self.query_for_long(sql, [carrier_clm_num])

    def update_icn_submitted_to_finance(self, icn_csr_detail: IcnCsrDetail) -> None:
        """
        Step 2 Writer (1/5): Inserts a new TXN_ID+1 into MCCA_ICN with REC_TYP='CSR' for ICNs
        previously submitted to Finance (SUBMITTED_TO='FIN').
        Exact port of IcnJdbcDaoImpl.updateIcnSubmittedToFinance().
        """
        sql = """
            INSERT INTO MCCA_ICN (
                TXN_ID, CARRIER_CLM_NUM, REC_TYP, STATUS, LST_UPDT_TIME_STMP,
                MCCA_CLM_NUM, CARRIER_PLCY_NUM, PLCY_EFF_DT, PLCY_EXP_DT, LOSS_DT,
                ACC_DT, ACC_DESC, ACC_ADD1, ACC_ADD2, ACC_CITY, ACC_STATE, ACC_ZIP,
                ACC_CNTY, CRR_ADJ_FST_NAME, CRR_ADJ_LST_NAME, CRR_ADJ_PHN_NUM,
                INSRD_SUFFIX, INSRD_FST_NAME, INSRD_MI, INSRD_LST_NAME, INSRD_ADD1,
                INSRD_ADD2, INSRD_CITY, INSRD_STATE, INSRD_ZIP, INSRD_CNTY,
                INSRD_GENDER, INSRD_DOB, COMP_CRS_CLM_IND, MAIPF_JUA_IND,
                COM_PLCY_IND, PLCY_WRTN_CRDNT_BAS, LST_UPDTING_PRSN, BATCH_NUM,
                CSR_OPEN_CLS_ST_FLG, CROSS_COMP_CLM_NUM, RETENTION, THRESHOLD,
                SUBMITTED_BY, SUBMITTED_TO, SUBMITTED_DATE
            )
            SELECT
                ICN.TXN_ID + 1, ICN.CARRIER_CLM_NUM, ?, ICN.STATUS, SYSDATE,
                ICN.MCCA_CLM_NUM, ICN.CARRIER_PLCY_NUM, ICN.PLCY_EFF_DT, ICN.PLCY_EXP_DT, ICN.LOSS_DT,
                ICN.ACC_DT, ICN.ACC_DESC, ICN.ACC_ADD1, ICN.ACC_ADD2, ICN.ACC_CITY, ICN.ACC_STATE, ICN.ACC_ZIP,
                ICN.ACC_CNTY, ICN.CRR_ADJ_FST_NAME, ICN.CRR_ADJ_LST_NAME, ICN.CRR_ADJ_PHN_NUM,
                ICN.INSRD_SUFFIX, ICN.INSRD_FST_NAME, ICN.INSRD_MI, ICN.INSRD_LST_NAME, ICN.INSRD_ADD1,
                ICN.INSRD_ADD2, ICN.INSRD_CITY, ICN.INSRD_STATE, ICN.INSRD_ZIP, ICN.INSRD_CNTY,
                ICN.INSRD_GENDER, ICN.INSRD_DOB, ICN.COMP_CRS_CLM_IND, ICN.MAIPF_JUA_IND,
                ICN.COM_PLCY_IND, ICN.PLCY_WRTN_CRDNT_BAS, ?, ICN.BATCH_NUM,
                ?, ICN.CROSS_COMP_CLM_NUM, ICN.RETENTION, ICN.THRESHOLD,
                ICN.SUBMITTED_BY, ICN.SUBMITTED_TO, ICN.SUBMITTED_DATE
            FROM MCCA_ICN ICN
            WHERE ICN.CARRIER_CLM_NUM = ?
              AND ICN.REC_TYP = 'ICN'
              AND ICN.TXN_ID = (
                  SELECT MAX(ICN1.TXN_ID)
                  FROM MCCA_ICN ICN1
                  WHERE ICN1.CARRIER_CLM_NUM = ICN.CARRIER_CLM_NUM
                    AND ICN1.REC_TYP = 'ICN'
              )
        """
        self.update(
            sql,
            [
                BatchConstants.CSR_REC_TYPE,
                BatchConstants.BATCH_LST_UPDTING_PRSN,
                BatchConstants.COPIED,
                icn_csr_detail.carrier_claim_num,
            ],
        )

    def update_csr_record_for_sf(self, icn_csr_detail: IcnCsrDetail) -> None:
        """
        Step 2 Writer (2/5): Inserts a new TXN_ID+1 into MCCA_CSR with REC_TYP='CSR', CLOSED_IND='Y',
        STATUS_LST='Closed' from the CLID='0' ICN row.
        Exact port of IcnJdbcDaoImpl.updateCsrRecordForSF().
        """
        sql = """
            INSERT INTO MCCA_CSR (
                TXN_ID, CARRIER_CLM_NUM, CLID, CSR_SEQ, REC_TYP, STATUS,
                LST_UPDT_TIME_STMP, MCCA_CLM_NUM, STATUS_LST, CRR_USR_ID,
                CSR_DUE_DT, PRBL_LIFE_TM_CARE_IND, CLOSED_IND, RETNTON_AMT,
                ASSGND_PRSN, LST_UPDTING_PRSN, CRR_ID, WS_PLCY_CORDNTD_DT_OF_LOSS_IND
            )
            SELECT
                CSR.TXN_ID + 1, CSR.CARRIER_CLM_NUM, CSR.CLID, CSR.CSR_SEQ, ?,
                CSR.STATUS, SYSDATE, CSR.MCCA_CLM_NUM, ?, CSR.CRR_USR_ID,
                CSR.CSR_DUE_DT, CSR.PRBL_LIFE_TM_CARE_IND, ?, CSR.RETNTON_AMT,
                CSR.ASSGND_PRSN, ?, CSR.CRR_ID, CSR.WS_PLCY_CORDNTD_DT_OF_LOSS_IND
            FROM MCCA_CSR CSR
            WHERE CSR.CARRIER_CLM_NUM = ?
              AND CSR.CLID = '0'
              AND CSR.REC_TYP = 'ICN'
              AND CSR.TXN_ID = (
                  SELECT MAX(CSR1.TXN_ID)
                  FROM MCCA_CSR CSR1
                  WHERE CSR1.CARRIER_CLM_NUM = CSR.CARRIER_CLM_NUM
                    AND CSR1.CLID = '0'
                    AND CSR1.REC_TYP = 'ICN'
              )
        """
        self.update(
            sql,
            [
                BatchConstants.CSR_REC_TYPE,
                BatchConstants.CLOSED,
                BatchConstants.YES_CD,
                BatchConstants.BATCH_LST_UPDTING_PRSN,
                icn_csr_detail.carrier_claim_num,
            ],
        )

    def copy_icn(self, icn_csr_detail: IcnCsrDetail) -> None:
        """
        Step 2 Writer (3/5): Copies the ICN row in MCCA_ICN with STATUS='PN' and SUBMITTED_TO=NULL
        so it can now be submitted to MCCA.
        Exact port of IcnJdbcDaoImpl.copyIcn().
        """
        sql = """
            INSERT INTO MCCA_ICN (
                TXN_ID, CARRIER_CLM_NUM, REC_TYP, STATUS, LST_UPDT_TIME_STMP,
                MCCA_CLM_NUM, CARRIER_PLCY_NUM, PLCY_EFF_DT, PLCY_EXP_DT, LOSS_DT,
                ACC_DT, ACC_DESC, ACC_ADD1, ACC_ADD2, ACC_CITY, ACC_STATE, ACC_ZIP,
                ACC_CNTY, CRR_ADJ_FST_NAME, CRR_ADJ_LST_NAME, CRR_ADJ_PHN_NUM,
                INSRD_SUFFIX, INSRD_FST_NAME, INSRD_MI, INSRD_LST_NAME, INSRD_ADD1,
                INSRD_ADD2, INSRD_CITY, INSRD_STATE, INSRD_ZIP, INSRD_CNTY,
                INSRD_GENDER, INSRD_DOB, COMP_CRS_CLM_IND, MAIPF_JUA_IND,
                COM_PLCY_IND, PLCY_WRTN_CRDNT_BAS, LST_UPDTING_PRSN, BATCH_NUM,
                CSR_OPEN_CLS_ST_FLG, CROSS_COMP_CLM_NUM, RETENTION, THRESHOLD,
                SUBMITTED_BY, SUBMITTED_TO, SUBMITTED_DATE
            )
            SELECT
                ICN.TXN_ID + 1, ICN.CARRIER_CLM_NUM, ?, ?, SYSDATE,
                ICN.MCCA_CLM_NUM, ICN.CARRIER_PLCY_NUM, ICN.PLCY_EFF_DT, ICN.PLCY_EXP_DT, ICN.LOSS_DT,
                ICN.ACC_DT, ICN.ACC_DESC, ICN.ACC_ADD1, ICN.ACC_ADD2, ICN.ACC_CITY, ICN.ACC_STATE, ICN.ACC_ZIP,
                ICN.ACC_CNTY, ICN.CRR_ADJ_FST_NAME, ICN.CRR_ADJ_LST_NAME, ICN.CRR_ADJ_PHN_NUM,
                ICN.INSRD_SUFFIX, ICN.INSRD_FST_NAME, ICN.INSRD_MI, ICN.INSRD_LST_NAME, ICN.INSRD_ADD1,
                ICN.INSRD_ADD2, ICN.INSRD_CITY, ICN.INSRD_STATE, ICN.INSRD_ZIP, ICN.INSRD_CNTY,
                ICN.INSRD_GENDER, ICN.INSRD_DOB, ICN.COMP_CRS_CLM_IND, ICN.MAIPF_JUA_IND,
                ICN.COM_PLCY_IND, ICN.PLCY_WRTN_CRDNT_BAS, ?, ICN.BATCH_NUM,
                ?, ICN.CROSS_COMP_CLM_NUM, ICN.RETENTION, ICN.THRESHOLD,
                NULL, NULL, NULL
            FROM MCCA_ICN ICN
            WHERE ICN.CARRIER_CLM_NUM = ?
              AND ICN.REC_TYP = 'CSR'
              AND ICN.TXN_ID = (
                  SELECT MAX(ICN1.TXN_ID)
                  FROM MCCA_ICN ICN1
                  WHERE ICN1.CARRIER_CLM_NUM = ICN.CARRIER_CLM_NUM
                    AND ICN1.REC_TYP = 'CSR'
              )
        """
        self.update(
            sql,
            [
                BatchConstants.ICN_REC_TYPE,
                BatchConstants.STATUS_PENDING_CD,
                BatchConstants.BATCH_LST_UPDTING_PRSN,
                BatchConstants.PARENT,
                icn_csr_detail.carrier_claim_num,
            ],
        )

    def close_csr_submitted_to_finance(self, icn_csr_detail: IcnCsrDetail) -> None:
        """
        Step 2 Writer (4/5): Inserts a new TXN_ID+1 into MCCA_CSR (CLID='0', REC_TYP='ICN',
        STATUS='PN', STATUS_LST='Open', CLOSED_IND='N') from the closed CSR record.
        Exact port of IcnJdbcDaoImpl.closeCsrSubmittedToFinance().
        """
        sql = """
            INSERT INTO MCCA_CSR (
                TXN_ID, CARRIER_CLM_NUM, CLID, CSR_SEQ, REC_TYP, STATUS,
                LST_UPDT_TIME_STMP, MCCA_CLM_NUM, STATUS_LST, CRR_USR_ID,
                CSR_DUE_DT, PRBL_LIFE_TM_CARE_IND, CLOSED_IND, RETNTON_AMT,
                ASSGND_PRSN, LST_UPDTING_PRSN, CRR_ID, WS_PLCY_CORDNTD_DT_OF_LOSS_IND
            )
            SELECT
                CSR.TXN_ID + 1, CSR.CARRIER_CLM_NUM, CSR.CLID, CSR.CSR_SEQ, ?,
                ?, SYSDATE, CSR.MCCA_CLM_NUM, ?, CSR.CRR_USR_ID,
                CSR.CSR_DUE_DT, CSR.PRBL_LIFE_TM_CARE_IND, ?, CSR.RETNTON_AMT,
                CSR.ASSGND_PRSN, ?, CSR.CRR_ID, CSR.WS_PLCY_CORDNTD_DT_OF_LOSS_IND
            FROM MCCA_CSR CSR
            WHERE CSR.CARRIER_CLM_NUM = ?
              AND CSR.CLID = '0'
              AND CSR.REC_TYP = 'CSR'
              AND CSR.TXN_ID = (
                  SELECT MAX(CSR1.TXN_ID)
                  FROM MCCA_CSR CSR1
                  WHERE CSR1.CARRIER_CLM_NUM = CSR.CARRIER_CLM_NUM
                    AND CSR1.CLID = '0'
                    AND CSR1.REC_TYP = 'CSR'
              )
        """
        self.update(
            sql,
            [
                BatchConstants.ICN_REC_TYPE,
                BatchConstants.STATUS_PENDING_CD,
                BatchConstants.OPEN,
                BatchConstants.NO_CD,
                BatchConstants.BATCH_LST_UPDTING_PRSN,
                icn_csr_detail.carrier_claim_num,
            ],
        )

    def get_csr_clid_list(self, carrier_clm_num: str) -> List[str]:
        """Exact port of IcnJdbcDaoImpl.getCsrClidList(String carrierClmNum)."""
        sql = """
            SELECT CSR.CLID
            FROM MCCA_CSR CSR
            WHERE CSR.CARRIER_CLM_NUM = ?
              AND CSR.REC_TYP = 'CSR'
            GROUP BY CSR.CLID
        """
        rows = self.query_for_list(sql, [carrier_clm_num])
        return [str(r["CLID"]) for r in rows if r.get("CLID") is not None]

    def insert_csr_claimant_info(self, csr_detail: IcnCsrDetail) -> None:
        """
        Step 2 Writer (5/5 helper): Copies claimant-level MCCA_CSR record into a new
        TXN_ID+1 with CSR_SEQ=0, REC_TYP='ICN', STATUS='PN', STATUS_LST='Open'.
        Exact port of IcnJdbcDaoImpl.insertCsrClaimantInfo(final IcnCsrDetail csrDetail).
        """
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
                TXN_ID + 1, CARRIER_CLM_NUM, ?, ?, ?, ?, SYSDATE,
                PLCY_EXP_DATE, DEMAND, SUIT_DT, LITGN_ISSUE_DESC, SSDI_APPLN_STATUS,
                CLMT_CRNT_CONDN_FUTR_CARE_DESC, MCCA_CLM_NUM, ?, CLMT_SUFFIX,
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
                ALINJ_CL_CM_PD_TO_DT_MEDWLESSL, ASSGND_PRSN, ?, CRR_ID,
                WS_PLCY_CORDNTD_DT_OF_LOSS_IND, CRNT_STS_CLM_ISUES_IN_DISPTE, LOCK_STATUS,
                SUBMITTED_TO, SUBMITTED_BY, ?, SUBMITTED_DATE,
                ALL_INJ_CL_COMB_PAID_TO_DT_RES, ALINJ_CL_CM_PD_TO_DT_MEDWLRES, CLMT_MI,
                AGNCY_DLY_RATE_2, AGNCY_HRLY_RATE_2, FMLY_DLY_RATE_2, FMLY_HRLY_RATE_2,
                AGNCY_AC_HRS_2, FMLY_AC_HRS_2, AGNCY_DLY_RATE_3, AGNCY_HRLY_RATE_3,
                FMLY_DLY_RATE_3, FMLY_HRLY_RATE_3, AGNCY_AC_HRS_3, FMLY_AC_HRS_3,
                AGNCY_DLY_RATE_4, AGNCY_HRLY_RATE_4, FMLY_DLY_RATE_4, FMLY_HRLY_RATE_4,
                AGNCY_AC_HRS_4, FMLY_AC_HRS_4, AGNCY_LEVEL_OF_CARE_1, AGNCY_LEVEL_OF_CARE_2,
                AGNCY_LEVEL_OF_CARE_3, AGNCY_LEVEL_OF_CARE_4, FMLY_LEVEL_OF_CARE_1,
                FMLY_LEVEL_OF_CARE_2, FMLY_LEVEL_OF_CARE_3, FMLY_LEVEL_OF_CARE_4,
                AVG_MNTHLY_RATE, ROOM_DLY_RATE
            FROM MCCA_CSR CSR
            WHERE CSR.CARRIER_CLM_NUM = ?
              AND CSR.CLID = ?
              AND CSR.TXN_ID = (
                  SELECT MAX(CSR1.TXN_ID)
                  FROM MCCA_CSR CSR1
                  WHERE CSR1.CARRIER_CLM_NUM = CSR.CARRIER_CLM_NUM
                    AND CSR1.CLID = CSR.CLID
              )
              AND CSR.CSR_SEQ = (
                  SELECT MAX(CSR2.CSR_SEQ)
                  FROM MCCA_CSR CSR2
                  WHERE CSR2.CARRIER_CLM_NUM = CSR.CARRIER_CLM_NUM
                    AND CSR2.CLID = CSR.CLID
              )
        """
        self.update(
            sql,
            [
                csr_detail.clid,
                0,
                BatchConstants.ICN_REC_TYPE,
                BatchConstants.STATUS_PENDING_CD,
                BatchConstants.OPEN,
                BatchConstants.BATCH_LST_UPDTING_PRSN,
                "",
                csr_detail.carrier_claim_num,
                csr_detail.clid,
            ],
        )

    def copy_csr_info(self, csr_detail: IcnCsrDetail) -> None:
        """
        Step 2 Writer (5/5): Copies all claimant CSR rows for the claim into new ICN-typed CSR rows.
        Exact port of IcnJdbcDaoImpl.copyCsrInfo(IcnCsrDetail csrDetail).
        """
        if not csr_detail.carrier_claim_num:
            return
        clids = self.get_csr_clid_list(csr_detail.carrier_claim_num)
        for clid in clids:
            if clid is not None:
                csr_detail.clid = clid
                self.insert_csr_claimant_info(csr_detail)

    def get_related_claims(self, carrier_clm_num: str, link_id: str) -> List[str]:
        """
        Returns linked companion CARRIER_CLM_NUM values from MCCA_CLAIM.
        Exact port of IcnJdbcDaoImpl.getRelatedClaims(String carrierClmNum, String linkId).
        """
        sql = """
            SELECT CARRIER_CLM_NUM
            FROM MCCA_CLAIM CLM
            WHERE LINK_ID = ?
              AND CARRIER_CLM_NUM <> ?
              AND CLM.TXN_ID = (
                  SELECT MAX(CLM1.TXN_ID)
                  FROM MCCA_CLAIM CLM1
                  WHERE CLM1.CARRIER_CLM_NUM = CLM.CARRIER_CLM_NUM
              )
        """
        rows = self.query_for_list(sql, [link_id, carrier_clm_num])
        return [str(r["CARRIER_CLM_NUM"]) for r in rows if r.get("CARRIER_CLM_NUM")]

    def get_claim_status(self, link_id: str) -> List[str]:
        """
        Returns CLAIM_STATUS values for all linked claims sharing LINK_ID in MCCA_CLAIM.
        Exact port of IcnJdbcDaoImpl.getClaimStatus(String linkId).
        """
        sql = """
            SELECT CLAIM_STATUS
            FROM MCCA_CLAIM CLM
            WHERE LINK_ID = ?
              AND CLM.TXN_ID = (
                  SELECT MAX(CLM1.TXN_ID)
                  FROM MCCA_CLAIM CLM1
                  WHERE CLM1.CARRIER_CLM_NUM = CLM.CARRIER_CLM_NUM
              )
        """
        rows = self.query_for_list(sql, [link_id])
        return [str(r["CLAIM_STATUS"]) for r in rows if r.get("CLAIM_STATUS")]

    def get_threshold_from_database(self) -> List[Threshold]:
        """
        Loads threshold schedule from MCCA_THRESHOLD.
        Exact port of IcnJdbcDaoImpl.getThresholdFromDatabase().
        """
        sql = "SELECT VALID_FROM, VALID_TO, THRESHOLD FROM MCCA_THRESHOLD ORDER BY VALID_FROM ASC"
        rows = self.query_for_list(sql)
        return [
            Threshold(
                valid_from=r.get("VALID_FROM"),
                valid_to=r.get("VALID_TO"),
                threshold_amount=str(r["THRESHOLD"]) if r.get("THRESHOLD") is not None else None,
            )
            for r in rows
        ]

    def create_backup_log(self) -> None:
        """
        Logs all records in MCCA_TMP_CLM before deletion in Step 10.
        Exact port of IcnJdbcDaoImpl.createBackupLog().
        """
        rows = self.query_for_list("SELECT * FROM MCCA_TMP_CLM")
        logger.info("Total Records in MCCA_TMP_CLM : %d", len(rows))
        for row in rows:
            line = " || ".join(
                str(row.get(col, ""))
                for col in [
                    "CARRIER_CLM_NUM", "ACC_DESC", "ACC_ADD1", "ACC_ADD2", "ACC_CITY",
                    "ACC_STATE", "ACC_ZIP", "CRS_COMP_CLM_IND", "CRS_COMP_CLM_NUM",
                    "MAIPF_JUA_IND", "COM_PLCY_IND", "PIP_ADJ_ID", "CRR_ID",
                    "CARRIER_PLCY_NUM", "PLCY_WRTN_CRDNT_BAS", "PLCY_CORD_DT_OF_LOSS",
                    "INSRD_PREFIX", "INSRD_FST_NAME", "INSRD_LST_NAME", "INSRD_MDL_INI",
                    "INSRD_GENDER", "INSRD_DOB", "INSRD_ADD1", "INSRD_ADD2",
                    "INSRD_CITY", "INSRD_STATE", "INSRD_ZIP",
                ]
            )
            logger.info(line)

    def delete_all(self, table_name: str) -> int:
        """Exact port of IcnJdbcDaoImpl.deleteAll(String tableName)."""
        return self.update(f"DELETE FROM {table_name}")
