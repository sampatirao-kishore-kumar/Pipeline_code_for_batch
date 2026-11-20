"""
MCCA_CLAIM RPTD Update DAO Implementation (Step updateRptdColumn).
1:1 port of com.acg.mcca.batch.impl.MccaClaimDaoImpl.

Tables Accessed:
- MCCA_CLAIM
- MCCA_CSR
"""

import logging
from decimal import Decimal
from typing import List

from dao.base_dao import BaseJdbcDao
from models import IcnCsrDetail

logger = logging.getLogger(__name__)


class MccaClaimDaoImpl(BaseJdbcDao):
    """Exact 1:1 port of com.acg.mcca.batch.impl.MccaClaimDaoImpl."""

    def update_mcca_clm_with_rptd(self, mcca_claim_detail: IcnCsrDetail) -> None:
        """
        Inserts a new version row (TXN_ID + 1) into MCCA_CLAIM with updated RPTD status
        ('RM', 'RF', 'CL', or '').
        Exact port of MccaClaimDaoImpl.updateMccaClmWithRptd(final IcnCsrDetail mccaClaimDetail).
        """
        try:
            sql = """
                INSERT INTO MCCA_CLAIM (
                    TXN_ID,
                    CARRIER_CLM_NUM,
                    MCCA_CLM_NUM,
                    LINK_ID,
                    MASTER_CLAIM_IND,
                    RETENTION,
                    THRESHOLD,
                    IS_PIP,
                    DATE_OF_LOSS,
                    CLAIM_STATUS,
                    POLICY_INCEPTION_DATE,
                    POLICY_END_DATE,
                    COMPANY,
                    RPTD,
                    CARRIER_PLCY_NUM,
                    UPDATE_DATE,
                    PIP_UNLMT_IND,
                    BROKER,
                    STATE,
                    LOB,
                    CONV_DT,
                    PREV_IPM_CLMNBR,
                    IPM_CNVTD_CLM_IND
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, SYSDATE, ?, ?, ?, ?, ?, ?, ?
                )
            """
            next_txn_id = int(mcca_claim_detail.txn_id) + 1 if mcca_claim_detail.txn_id else 1
            params = [
                next_txn_id,
                mcca_claim_detail.carrier_claim_num,
                mcca_claim_detail.mcca_claim_num,
                mcca_claim_detail.link_claim,
                mcca_claim_detail.master_claim_ind,
                Decimal(str(mcca_claim_detail.retention_amt))
                if mcca_claim_detail.retention_amt is not None
                else None,
                Decimal(str(mcca_claim_detail.threshold_amt))
                if mcca_claim_detail.threshold_amt is not None
                else None,
                mcca_claim_detail.is_pip_ind,
                mcca_claim_detail.date_of_loss,
                mcca_claim_detail.status,
                mcca_claim_detail.policy_effc_dt,
                mcca_claim_detail.policy_exp_dt,
                mcca_claim_detail.company,
                mcca_claim_detail.rptd,
                mcca_claim_detail.carrier_policy_num,
                mcca_claim_detail.pip_unlmt_ind,
                mcca_claim_detail.broker,
                mcca_claim_detail.state,
                mcca_claim_detail.lob,
                mcca_claim_detail.conv_dt,
                mcca_claim_detail.prev_ipm_clmnbr,
                mcca_claim_detail.ipm_convtd_clm_ind,
            ]
            self.update(sql, params)
        except Exception as exc:
            logger.error(
                "Error in MccaClaimDaoImpl.update_mcca_clm_with_rptd() CARRIER_CLM_NUM=%s: %s",
                mcca_claim_detail.carrier_claim_num,
                exc,
            )

    def get_csr_status_list(self, carrier_clm_num: str, batch_date: str) -> List[IcnCsrDetail]:
        """
        Returns STATUS_LST and CLOSED_IND for all non-zero CLID rows in MCCA_CSR as of batch_date.
        Exact port of MccaClaimDaoImpl.getCsrStatusList(String carrierClmNum, String batchDate).
        """
        sql = f"""
            SELECT CSR.STATUS_LST, CSR.CLOSED_IND
            FROM MCCA_CSR CSR
            WHERE CSR.CARRIER_CLM_NUM = ?
              AND CSR.CLID <> '0'
              AND TO_DATE(TO_CHAR(CSR.LST_UPDT_TIME_STMP, 'MM/DD/YYYY'), 'MM/DD/YYYY') <=
                  TO_DATE('{batch_date}', 'YYYY/MM/DD')
              AND CSR.TXN_ID IN (
                  SELECT MAX(CSR2.TXN_ID)
                  FROM MCCA_CSR CSR2
                  WHERE CSR2.CARRIER_CLM_NUM = CSR.CARRIER_CLM_NUM
                    AND CSR2.CLID = CSR.CLID
                    AND TO_DATE(TO_CHAR(CSR2.LST_UPDT_TIME_STMP, 'MM/DD/YYYY'), 'MM/DD/YYYY') <=
                        TO_DATE('{batch_date}', 'YYYY/MM/DD')
              )
              AND (CSR.PRBL_LIFE_TM_CARE_IND = 'Y' OR CSR.PRBL_LIFE_TM_CARE_IND IS NULL)
        """
        rows = self.query_for_list(sql, [carrier_clm_num])
        return [
            IcnCsrDetail(
                status_lst=r.get("STATUS_LST"),
                closed_ind=r.get("CLOSED_IND"),
            )
            for r in rows
        ]
