"""
Update ICN & CSR Claim Detail JDBC DAO Implementation (Steps 5, 6, and 7).
1:1 port of com.acg.mcca.batch.impl.UpdateIcnCsrJdbcDaoImpl.

Tables Accessed:
- MCCA_ICN
- MCCA_CSR
"""

import logging
from decimal import Decimal

from config import BatchConstants
from dao.base_dao import BaseJdbcDao
from models import IcnCsrDetail, TmpIcnDetail

logger = logging.getLogger(__name__)


class UpdateIcnCsrJdbcDaoImpl(BaseJdbcDao):
    """Exact 1:1 port of com.acg.mcca.batch.impl.UpdateIcnCsrJdbcDaoImpl."""

    def update_icn_tmp_claim_detail(self, icn_csr_detail: TmpIcnDetail) -> None:
        """
        Step 5 Writer DAO: Inserts a new version row (TXN_ID + 1) into MCCA_ICN merging
        updated fields from MCCA_TMP_CLM for pending ICNs (STATUS='PN').
        Exact port of UpdateIcnCsrJdbcDaoImpl.updateIcnTmpClaimDetail(final TmpIcnDetail icnCsrDetail).
        """
        try:
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
                    TXN_ID + 1, CARRIER_CLM_NUM, REC_TYP, STATUS, SYSDATE,
                    MCCA_CLM_NUM, ?, PLCY_EFF_DT, PLCY_EXP_DT, LOSS_DT,
                    ACC_DT, ?, ?, ?, ?, ?, ?,
                    ACC_CNTY, CRR_ADJ_FST_NAME, CRR_ADJ_LST_NAME, CRR_ADJ_PHN_NUM,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, INSRD_CNTY,
                    ?, ?, ?, ?,
                    ?, ?, ?, BATCH_NUM,
                    CSR_OPEN_CLS_ST_FLG, ?, RETENTION, THRESHOLD,
                    SUBMITTED_BY, SUBMITTED_TO, SUBMITTED_DATE
                FROM MCCA_ICN ICN
                WHERE CARRIER_CLM_NUM = ?
                  AND REC_TYP = 'ICN'
                  AND STATUS = 'PN'
                  AND TXN_ID = (
                      SELECT MAX(ICN1.TXN_ID)
                      FROM MCCA_ICN ICN1
                      WHERE ICN1.CARRIER_CLM_NUM = ICN.CARRIER_CLM_NUM
                        AND ICN1.REC_TYP = 'ICN'
                        AND ICN1.STATUS = 'PN'
                  )
            """
            params = [
                icn_csr_detail.carrier_policy_num,
                icn_csr_detail.accident_desc,
                icn_csr_detail.accident_addr1,
                icn_csr_detail.accident_addr2,
                icn_csr_detail.accident_city,
                icn_csr_detail.accident_state,
                icn_csr_detail.accident_zip,
                icn_csr_detail.insured_prefix,
                icn_csr_detail.insured_frst_name,
                icn_csr_detail.insured_midl_in,
                icn_csr_detail.insured_lst_name,
                icn_csr_detail.insured_addr1,
                icn_csr_detail.insured_addr2,
                icn_csr_detail.insured_city,
                icn_csr_detail.insured_state,
                icn_csr_detail.insured_zip,
                icn_csr_detail.insured_gender,
                icn_csr_detail.insured_dob,
                icn_csr_detail.comp_crs_clm_ind,
                icn_csr_detail.maipf_jua_ind,
                icn_csr_detail.com_plcy_ind,
                icn_csr_detail.plcy_wrtn_crdnt_bas,
                BatchConstants.BATCH_LST_UPDTING_PRSN,
                icn_csr_detail.cross_comp_clm_num,
                icn_csr_detail.carrier_claim_num,
            ]
            self.update(sql, params)
        except Exception as exc:
            logger.error(
                "Error in UpdateIcnCsrJdbcDaoImpl.update_icn_tmp_claim_detail() CARRIER_CLM_NUM=%s: %s",
                icn_csr_detail.carrier_claim_num,
                exc,
            )

    def update_icn_claim_detail(self, icn_csr_detail: IcnCsrDetail, rec_type: str) -> None:
        """
        Step 6 Writer DAO (recType='ICN'):
        1. Inserts a new TXN_ID+1 row into MCCA_ICN with updated MCCA_CLM_NUM, CARRIER_PLCY_NUM,
           PLCY_EFF_DT, PLCY_EXP_DT, LOSS_DT, RETENTION, THRESHOLD from MCCA_CLAIM.
        2. Updates MCCA_CSR (SET MCCA_CLM_NUM=?, RETNTON_AMT=?, LST_UPDT_TIME_STMP=SYSDATE,
           LST_UPDTING_PRSN='Batch') for CLID='0' and CLID <> '0' where REC_TYP='ICN'.
        Exact port of UpdateIcnCsrJdbcDaoImpl.updateIcnClaimDetail() and updateCsrForIcn().
        """
        try:
            sql_icn = """
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
                    TXN_ID + 1, CARRIER_CLM_NUM, REC_TYP, STATUS, SYSDATE,
                    ?, ?, ?, ?, ?,
                    ACC_DT, ACC_DESC, ACC_ADD1, ACC_ADD2, ACC_CITY, ACC_STATE, ACC_ZIP,
                    ACC_CNTY, CRR_ADJ_FST_NAME, CRR_ADJ_LST_NAME, CRR_ADJ_PHN_NUM,
                    INSRD_SUFFIX, INSRD_FST_NAME, INSRD_MI, INSRD_LST_NAME, INSRD_ADD1,
                    INSRD_ADD2, INSRD_CITY, INSRD_STATE, INSRD_ZIP, INSRD_CNTY,
                    INSRD_GENDER, INSRD_DOB, COMP_CRS_CLM_IND, MAIPF_JUA_IND,
                    COM_PLCY_IND, PLCY_WRTN_CRDNT_BAS, ?, BATCH_NUM,
                    CSR_OPEN_CLS_ST_FLG, CROSS_COMP_CLM_NUM, ?, ?,
                    SUBMITTED_BY, SUBMITTED_TO, SUBMITTED_DATE
                FROM MCCA_ICN ICN
                WHERE CARRIER_CLM_NUM = ?
                  AND REC_TYP = 'ICN'
                  AND STATUS = 'PN'
                  AND TXN_ID = (
                      SELECT MAX(ICN1.TXN_ID)
                      FROM MCCA_ICN ICN1
                      WHERE ICN1.CARRIER_CLM_NUM = ICN.CARRIER_CLM_NUM
                        AND ICN1.REC_TYP = 'ICN'
                        AND ICN1.STATUS = 'PN'
                  )
            """
            mcca_clm_dec = (
                Decimal(icn_csr_detail.mcca_claim_num) if icn_csr_detail.mcca_claim_num else None
            )
            ret_dec = (
                Decimal(str(icn_csr_detail.retention_amt))
                if icn_csr_detail.retention_amt is not None
                else None
            )
            thr_dec = (
                Decimal(str(icn_csr_detail.threshold_amt))
                if icn_csr_detail.threshold_amt is not None
                else None
            )
            self.update(
                sql_icn,
                [
                    mcca_clm_dec,
                    icn_csr_detail.carrier_policy_num,
                    icn_csr_detail.policy_effc_dt,
                    icn_csr_detail.policy_exp_dt,
                    icn_csr_detail.date_of_loss,
                    BatchConstants.BATCH_LST_UPDTING_PRSN,
                    ret_dec,
                    thr_dec,
                    icn_csr_detail.carrier_claim_num,
                ],
            )
            self.update_csr_for_icn(icn_csr_detail, rec_type)
        except Exception as exc:
            logger.error(
                "Error in UpdateIcnCsrJdbcDaoImpl.update_icn_claim_detail() CARRIER_CLM_NUM=%s: %s",
                icn_csr_detail.carrier_claim_num,
                exc,
            )

    def update_csr_for_icn(self, icn_csr_detail: IcnCsrDetail, rec_type: str) -> None:
        """
        Updates MCCA_CSR (both CLID='0' and CLID <> '0') for pending ICNs in Step 6.
        Exact port of UpdateIcnCsrJdbcDaoImpl.updateCsrForIcn() (lines 207-260).
        """
        mcca_clm_dec = (
            Decimal(icn_csr_detail.mcca_claim_num) if icn_csr_detail.mcca_claim_num else None
        )
        ret_dec = (
            Decimal(str(icn_csr_detail.retention_amt))
            if icn_csr_detail.retention_amt is not None
            else None
        )
        # Update CLID='0'
        sql_clid_0 = """
            UPDATE MCCA_CSR CSR
            SET MCCA_CLM_NUM = ?,
                RETNTON_AMT = ?,
                LST_UPDT_TIME_STMP = SYSDATE,
                LST_UPDTING_PRSN = ?
            WHERE CSR.CARRIER_CLM_NUM = ?
              AND CSR.CLID = '0'
              AND CSR.REC_TYP = ?
              AND CSR.TXN_ID = (
                  SELECT MAX(CSR1.TXN_ID)
                  FROM MCCA_CSR CSR1
                  WHERE CSR1.CARRIER_CLM_NUM = CSR.CARRIER_CLM_NUM
                    AND CSR1.CLID = '0'
                    AND CSR1.REC_TYP = ?
              )
        """
        self.update(
            sql_clid_0,
            [
                mcca_clm_dec,
                ret_dec,
                BatchConstants.BATCH_LST_UPDTING_PRSN,
                icn_csr_detail.carrier_claim_num,
                rec_type,
                rec_type,
            ],
        )
        # Update CLID <> '0'
        sql_clids = """
            UPDATE MCCA_CSR CSR
            SET MCCA_CLM_NUM = ?,
                RETNTON_AMT = ?,
                LST_UPDT_TIME_STMP = SYSDATE,
                LST_UPDTING_PRSN = ?
            WHERE CSR.CARRIER_CLM_NUM = ?
              AND CSR.CLID <> '0'
              AND CSR.REC_TYP = ?
              AND CSR.TXN_ID = (
                  SELECT MAX(CSR1.TXN_ID)
                  FROM MCCA_CSR CSR1
                  WHERE CSR1.CARRIER_CLM_NUM = CSR.CARRIER_CLM_NUM
                    AND CSR1.CLID = CSR.CLID
                    AND CSR1.REC_TYP = ?
              )
        """
        self.update(
            sql_clids,
            [
                mcca_clm_dec,
                ret_dec,
                BatchConstants.BATCH_LST_UPDTING_PRSN,
                icn_csr_detail.carrier_claim_num,
                rec_type,
                rec_type,
            ],
        )

    def update_csr_claim_detail(self, icn_csr_detail: IcnCsrDetail, rec_type: str) -> None:
        """
        Step 7 Writer DAO (recType='CSR'):
        Updates MCCA_CSR SET MCCA_CLM_NUM=?, RETNTON_AMT=?, LST_UPDT_TIME_STMP=SYSDATE,
        LST_UPDTING_PRSN='Batch' for open pending CSR records.
        Exact port of UpdateIcnCsrJdbcDaoImpl.updateCsrClaimDetail() (lines 262-304).
        """
        try:
            mcca_clm_dec = (
                Decimal(icn_csr_detail.mcca_claim_num) if icn_csr_detail.mcca_claim_num else None
            )
            ret_dec = (
                Decimal(str(icn_csr_detail.retention_amt))
                if icn_csr_detail.retention_amt is not None
                else None
            )
            sql = """
                UPDATE MCCA_CSR CSR
                SET MCCA_CLM_NUM = ?,
                    RETNTON_AMT = ?,
                    LST_UPDT_TIME_STMP = SYSDATE,
                    LST_UPDTING_PRSN = ?
                WHERE CSR.CARRIER_CLM_NUM = ?
                  AND CSR.CLID = ?
                  AND CSR.REC_TYP = ?
                  AND CSR.STATUS = 'PN'
                  AND CSR.STATUS_LST = 'Open'
                  AND (CSR.CLOSED_IND IS NULL OR CSR.CLOSED_IND = 'N')
                  AND CSR.TXN_ID = (
                      SELECT MAX(CSR1.TXN_ID)
                      FROM MCCA_CSR CSR1
                      WHERE CSR1.CARRIER_CLM_NUM = CSR.CARRIER_CLM_NUM
                        AND CSR1.CLID = CSR.CLID
                        AND CSR1.REC_TYP = ?
                  )
            """
            self.update(
                sql,
                [
                    mcca_clm_dec,
                    ret_dec,
                    BatchConstants.BATCH_LST_UPDTING_PRSN,
                    icn_csr_detail.carrier_claim_num,
                    icn_csr_detail.clid,
                    rec_type,
                    rec_type,
                ],
            )
        except Exception as exc:
            logger.error(
                "Error in UpdateIcnCsrJdbcDaoImpl.update_csr_claim_detail() CARRIER_CLM_NUM=%s CLID=%s: %s",
                icn_csr_detail.carrier_claim_num,
                icn_csr_detail.clid,
                exc,
            )
