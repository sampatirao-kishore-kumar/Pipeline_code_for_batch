"""
Other Injured Claimants Payment DAO Implementation.
1:1 port of com.acg.mcca.batch.impl.OthrInjClmtsDaoImpl.

Tables Accessed:
- MCCA_OTHR_INJ_CLMTS_PYMT
- MCCA_CLAIM
- MCCA_CSR
- MCCA_LOSS_EXPENSE_DETAILS
- MCCA_RESERVES
- D_FISCAL_MONTH
"""

import logging
import re
from decimal import Decimal
from typing import Dict, List, Optional

from config import BatchConstants
from dao.base_dao import BaseJdbcDao
from models import OthrInjClmtsPymt

logger = logging.getLogger(__name__)


def _is_facts_claim(claim_num: Optional[str]) -> bool:
    if not claim_num:
        return False
    return bool(re.match(BatchConstants.REGEX_FACTS_CLAIMS, claim_num))


class OthrInjClmtsDaoImpl(BaseJdbcDao):
    """Exact 1:1 port of com.acg.mcca.batch.impl.OthrInjClmtsDaoImpl."""

    def save_othr_inj_clmts_pymt(self, othr: OthrInjClmtsPymt) -> None:
        """
        Inserts a row into MCCA_OTHR_INJ_CLMTS_PYMT.
        Exact port of OthrInjClmtsDaoImpl.saveOthrInjClmtsPymt(final OthrInjClmtsPymt othrInjClmtsPymt).
        """
        try:
            sql = """
                INSERT INTO MCCA_OTHR_INJ_CLMTS_PYMT (
                    TXN_ID,
                    CARRIER_CLM_NUM,
                    CL_ID,
                    REC_TYP,
                    CLM_NUM,
                    CLM_TYPE,
                    PIP_IND,
                    CSR_SEQ,
                    MED,
                    WL_ES_SL,
                    RESERVE_AMT,
                    OTHER_PROJ_SEQ,
                    LST_UPDT_TIME_STMP,
                    CLID
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, SYSDATE, ?
                )
            """
            params = [
                othr.txn_id,
                othr.carrier_clm_num,
                othr.cl_id,
                othr.rec_typ,
                othr.clm_num,
                othr.clm_type,
                othr.pip_ind,
                othr.csr_seq,
                othr.med,
                othr.wl_es_sl,
                othr.reserve_amt,
                othr.other_proj_seq,
                othr.clid,
            ]
            self.update(sql, params)
        except Exception as exc:
            logger.error(
                "Error in OthrInjClmtsDaoImpl.save_othr_inj_clmts_pymt() CARRIER_CLM_NUM=%s CLID=%s: %s",
                othr.carrier_clm_num,
                othr.clid,
                exc,
            )

    def get_max_others_txn_id(self, carrier_clm_num: str, clid: str, record_type: str) -> int:
        """Exact port of OthrInjClmtsDaoImpl.getMaxOthersTxnId()."""
        sql = """
            SELECT NVL(MAX(OTHERINJPYMT.TXN_ID), 0)
            FROM MCCA_OTHR_INJ_CLMTS_PYMT OTHERINJPYMT
            WHERE OTHERINJPYMT.CARRIER_CLM_NUM = ?
              AND OTHERINJPYMT.CLID = ?
              AND OTHERINJPYMT.REC_TYP = ?
        """
        return self.query_for_long(sql, [carrier_clm_num, clid, record_type])

    def get_othr_inj_clmts_pymt(self, carrier_clm_num: str, rec_typ: str, clid: str) -> List[OthrInjClmtsPymt]:
        """
        Fetches latest MCCA_OTHR_INJ_CLMTS_PYMT rows for CARRIER_CLM_NUM, REC_TYP, CLID.
        Exact port of OthrInjClmtsDaoImpl.getOthrInjClmtsPymt().
        """
        sql = """
            SELECT *
            FROM MCCA_OTHR_INJ_CLMTS_PYMT OTHERS
            WHERE OTHERS.CARRIER_CLM_NUM = ?
              AND OTHERS.REC_TYP = ?
              AND OTHERS.CLID = ?
              AND OTHERS.TXN_ID = (
                  SELECT MAX(OTHERINJPYMT.TXN_ID)
                  FROM MCCA_OTHR_INJ_CLMTS_PYMT OTHERINJPYMT
                  WHERE OTHERINJPYMT.CARRIER_CLM_NUM = OTHERS.CARRIER_CLM_NUM
                    AND OTHERINJPYMT.CLID = OTHERS.CLID
                    AND OTHERINJPYMT.REC_TYP = OTHERS.REC_TYP
              )
            ORDER BY OTHERS.CLM_TYPE ASC, OTHERS.OTHER_PROJ_SEQ ASC
        """
        rows = self.query_for_list(sql, [carrier_clm_num, rec_typ, clid])
        return [
            OthrInjClmtsPymt(
                txn_id=int(r["TXN_ID"]) if r.get("TXN_ID") is not None else 0,
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

    def get_paid_to_date_for_cross_comp(
        self, carrier_clm_num: str, link_id: str, batch_date: str
    ) -> List[OthrInjClmtsPymt]:
        """
        Queries cross-companion paid-to-date amounts across MCCA_CLAIM and MCCA_LOSS_EXPENSE_DETAILS.
        Exact port of OthrInjClmtsDaoImpl.getPaidToDateForCrossCompSql() (lines 1067-1198).
        """
        sql = f"""
            SELECT DISTINCT CROSS_COMP_CLM, MASTER_CLAIM_IND, LINK_ID, MASTER_CLAIM, CLID, IS_PIP, COVERAGE, LOSSES_PAID
            FROM (
                SELECT DISTINCT
                    CLM.CARRIER_CLM_NUM AS CROSS_COMP_CLM,
                    CLM.MASTER_CLAIM_IND,
                    CLM.LINK_ID,
                    CLM.LINK_ID AS MASTER_CLAIM,
                    LOSSES.CLID,
                    CLM.IS_PIP,
                    LOSSES.COVERAGE,
                    LOSSES.LOSSES_PAID
                FROM MCCA_CLAIM CLM
                LEFT OUTER JOIN (
                    SELECT
                        LED.CARRIER_CLM_NUM,
                        LED.CLID,
                        SUM(LED.LOSSES_PAID) AS LOSSES_PAID,
                        (CASE WHEN LED.COVERAGE IN ('ZWL', 'ZSL') THEN 'WL' ELSE 'MED' END) AS COVERAGE
                    FROM MCCA_LOSS_EXPENSE_DETAILS LED
                    WHERE LED.TO_DATE <= (
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
                    GROUP BY LED.CARRIER_CLM_NUM, LED.CLID,
                             (CASE WHEN LED.COVERAGE IN ('ZWL', 'ZSL') THEN 'WL' ELSE 'MED' END)
                ) LOSSES ON LOSSES.CARRIER_CLM_NUM = CLM.CARRIER_CLM_NUM
                WHERE CLM.TXN_ID IN (
                    SELECT MAX(CLMII.TXN_ID)
                    FROM MCCA_CLAIM CLMII
                    WHERE CLMII.CARRIER_CLM_NUM = CLM.CARRIER_CLM_NUM
                )
                  AND CLM.LINK_ID IN (
                      SELECT DISTINCT CLMI.LINK_ID
                      FROM MCCA_CLAIM CLMI
                      WHERE CLMI.LINK_ID = ?
                  )
                  AND CLM.MASTER_CLAIM_IND = 'N'
                UNION ALL
                SELECT DISTINCT
                    LINKED_CLAIMS.CARRIER_CLM_NUM AS CROSS_COMP_CLM,
                    CLM.MASTER_CLAIM_IND,
                    CLM.LINK_ID,
                    (CASE WHEN (CLM.MASTER_CLAIM_IND = 'N' AND CLM.LINK_ID IS NOT NULL) THEN CLM.CARRIER_CLM_NUM ELSE '' END) AS MASTER_CLAIM,
                    LOSSES.CLID,
                    CLM.IS_PIP,
                    LOSSES.COVERAGE,
                    LOSSES.LOSSES_PAID
                FROM MCCA_CLAIM CLM
                LEFT OUTER JOIN (
                    SELECT CLAIM.CARRIER_CLM_NUM, CLAIM.LINK_ID
                    FROM MCCA_CLAIM CLAIM
                    WHERE CLAIM.TXN_ID IN (
                        SELECT MAX(CLAIM1.TXN_ID)
                        FROM MCCA_CLAIM CLAIM1
                        WHERE CLAIM1.CARRIER_CLM_NUM = CLAIM.CARRIER_CLM_NUM
                    )
                ) LINKED_CLAIMS ON LINKED_CLAIMS.LINK_ID = CLM.LINK_ID
                               AND LINKED_CLAIMS.CARRIER_CLM_NUM <> CLM.CARRIER_CLM_NUM
                LEFT OUTER JOIN (
                    SELECT
                        LED.CARRIER_CLM_NUM,
                        LED.CLID,
                        SUM(LED.LOSSES_PAID) AS LOSSES_PAID,
                        (CASE WHEN LED.COVERAGE IN ('ZWL', 'ZSL') THEN 'WL' ELSE 'MED' END) AS COVERAGE
                    FROM MCCA_LOSS_EXPENSE_DETAILS LED
                    WHERE LED.TO_DATE <= (
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
                    GROUP BY LED.CARRIER_CLM_NUM, LED.CLID,
                             (CASE WHEN LED.COVERAGE IN ('ZWL', 'ZSL') THEN 'WL' ELSE 'MED' END)
                ) LOSSES ON LOSSES.CARRIER_CLM_NUM = LINKED_CLAIMS.CARRIER_CLM_NUM
                WHERE CLM.TXN_ID IN (
                    SELECT MAX(CLMII.TXN_ID)
                    FROM MCCA_CLAIM CLMII
                    WHERE CLMII.CARRIER_CLM_NUM = CLM.CARRIER_CLM_NUM
                )
                  AND CLM.LINK_ID IN (
                      SELECT DISTINCT CLMI.LINK_ID
                      FROM MCCA_CLAIM CLMI
                      WHERE CLMI.LINK_ID = ?
                  )
                  AND CLM.CARRIER_CLM_NUM = ?
            ) T
            WHERE CROSS_COMP_CLM <> '0'
              AND MASTER_CLAIM IS NOT NULL
            GROUP BY LINK_ID, MASTER_CLAIM, IS_PIP, CLID, COVERAGE, CROSS_COMP_CLM, LOSSES_PAID, MASTER_CLAIM_IND
            ORDER BY LINK_ID ASC, IS_PIP DESC
        """
        rows = self.query_for_list(sql, [carrier_clm_num, link_id, carrier_clm_num])
        return [
            OthrInjClmtsPymt(
                cross_clm_num=r.get("CROSS_COMP_CLM"),
                master_claim_ind=r.get("MASTER_CLAIM_IND"),
                link_id=r.get("LINK_ID"),
                master_claim=r.get("MASTER_CLAIM"),
                cl_id=r.get("CLID"),
                pip_ind=r.get("IS_PIP"),
                coverage=r.get("COVERAGE"),
                losses_paid=Decimal(str(r["LOSSES_PAID"])) if r.get("LOSSES_PAID") is not None else Decimal("0"),
            )
            for r in rows
        ]

    def get_reserves_for_cross_comp(
        self, carrier_clm_num: str, link_id: str, batch_date: str
    ) -> Dict[str, Decimal]:
        """
        Queries cross-companion reserve amounts across MCCA_CLAIM and MCCA_RESERVES.
        Exact port of OthrInjClmtsDaoImpl.getReservesForCrossCompSql() (lines 1200-1313).
        """
        sql = f"""
            SELECT DISTINCT CROSS_COMP_CLM, MASTER_CLAIM, LINK_ID, CLID, RESERVE_AMOUNT, IS_PIP
            FROM (
                SELECT DISTINCT
                    CLM.CARRIER_CLM_NUM AS CROSS_COMP_CLM,
                    CLM.LINK_ID AS MASTER_CLAIM,
                    CLM.LINK_ID,
                    RESERV.CLID,
                    RESERV.RESERVE_AMOUNT,
                    CLM.IS_PIP
                FROM MCCA_CLAIM CLM
                LEFT OUTER JOIN (
                    SELECT RES.CARRIER_CLM_NUM, RES.CLID, SUM(RES.RESERVE_AMOUNT) AS RESERVE_AMOUNT
                    FROM MCCA_RESERVES RES
                    WHERE RES.RESERVE_DATE IN (
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
                    GROUP BY RES.CARRIER_CLM_NUM, RES.CLID
                ) RESERV ON RESERV.CARRIER_CLM_NUM = CLM.CARRIER_CLM_NUM
                WHERE CLM.TXN_ID IN (
                    SELECT MAX(CLMII.TXN_ID)
                    FROM MCCA_CLAIM CLMII
                    WHERE CLMII.CARRIER_CLM_NUM = CLM.CARRIER_CLM_NUM
                )
                  AND CLM.LINK_ID IN (
                      SELECT DISTINCT CLMI.LINK_ID
                      FROM MCCA_CLAIM CLMI
                      WHERE CLMI.LINK_ID = ?
                  )
                  AND CLM.MASTER_CLAIM_IND = 'N'
                UNION ALL
                SELECT DISTINCT
                    LINKED_CLAIMS.CARRIER_CLM_NUM AS CROSS_COMP_CLM,
                    (CASE WHEN (CLM.MASTER_CLAIM_IND = 'N' AND CLM.LINK_ID IS NOT NULL) THEN CLM.CARRIER_CLM_NUM ELSE '' END) AS MASTER_CLAIM,
                    CLM.LINK_ID,
                    RESERV.CLID,
                    RESERV.RESERVE_AMOUNT,
                    CLM.IS_PIP
                FROM MCCA_CLAIM CLM
                LEFT OUTER JOIN (
                    SELECT CLAIM.CARRIER_CLM_NUM, CLAIM.LINK_ID
                    FROM MCCA_CLAIM CLAIM
                    WHERE CLAIM.TXN_ID IN (
                        SELECT MAX(CLAIM1.TXN_ID)
                        FROM MCCA_CLAIM CLAIM1
                        WHERE CLAIM1.CARRIER_CLM_NUM = CLAIM.CARRIER_CLM_NUM
                    )
                ) LINKED_CLAIMS ON LINKED_CLAIMS.LINK_ID = CLM.LINK_ID
                               AND LINKED_CLAIMS.CARRIER_CLM_NUM <> CLM.CARRIER_CLM_NUM
                LEFT OUTER JOIN (
                    SELECT RES.CARRIER_CLM_NUM, RES.CLID, SUM(RES.RESERVE_AMOUNT) AS RESERVE_AMOUNT
                    FROM MCCA_RESERVES RES
                    WHERE RES.RESERVE_DATE IN (
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
                    GROUP BY RES.CARRIER_CLM_NUM, RES.CLID
                ) RESERV ON RESERV.CARRIER_CLM_NUM = LINKED_CLAIMS.CARRIER_CLM_NUM
                WHERE CLM.TXN_ID IN (
                    SELECT MAX(CLMII.TXN_ID)
                    FROM MCCA_CLAIM CLMII
                    WHERE CLMII.CARRIER_CLM_NUM = CLM.CARRIER_CLM_NUM
                )
                  AND CLM.LINK_ID IN (
                      SELECT DISTINCT CLMI.LINK_ID
                      FROM MCCA_CLAIM CLMI
                      WHERE CLMI.LINK_ID = ?
                  )
                  AND CLM.CARRIER_CLM_NUM = ?
            ) T
            WHERE CROSS_COMP_CLM <> '0'
              AND MASTER_CLAIM IS NOT NULL
            GROUP BY LINK_ID, MASTER_CLAIM, IS_PIP, CLID, CROSS_COMP_CLM, RESERVE_AMOUNT
            ORDER BY LINK_ID ASC, IS_PIP DESC
        """
        rows = self.query_for_list(sql, [carrier_clm_num, link_id, carrier_clm_num])
        reserves_map: Dict[str, Decimal] = {}
        for r in rows:
            key = f"{r.get('CROSS_COMP_CLM') or ''}{r.get('CLID') or ''}"
            amt = r.get("RESERVE_AMOUNT")
            reserves_map[key] = Decimal(str(amt)) if amt is not None else Decimal("0")
        return reserves_map

    def set_othr_inj_clmts_pymt_for_pn_icn_csr(
        self,
        carrier_clm_num: str,
        link_id: str,
        batch_date: str,
        clid: str,
        rec_typ: str,
        mcca_csr_seq: Decimal,
    ) -> List[OthrInjClmtsPymt]:
        """
        Calculates and merges cross-companion payment & reserve rows for pending ICN/CSR claims.
        Exact port of OthrInjClmtsDaoImpl.setOthrInjClmtsPymtForPnIcnCsr() (lines 589-1065).
        """
        paid_rows = self.get_paid_to_date_for_cross_comp(carrier_clm_num, link_id, batch_date)
        reserves_map = self.get_reserves_for_cross_comp(carrier_clm_num, link_id, batch_date)

        # Aggregate by (cross_clm_num, cl_id)
        grouped: Dict[str, OthrInjClmtsPymt] = {}
        for item in paid_rows:
            key = f"{item.cross_clm_num or ''}_{item.cl_id or ''}"
            if key not in grouped:
                res_key = f"{item.cross_clm_num or ''}{item.cl_id or ''}"
                grouped[key] = OthrInjClmtsPymt(
                    carrier_clm_num=carrier_clm_num,
                    clid=clid,
                    rec_typ=rec_typ,
                    cl_id=item.cl_id,
                    clm_num=item.cross_clm_num,
                    cross_clm_num=item.cross_clm_num,
                    pip_ind=item.pip_ind,
                    csr_seq=mcca_csr_seq,
                    med=Decimal("0"),
                    wl_es_sl=Decimal("0"),
                    reserve_amt=reserves_map.get(res_key, Decimal("0")),
                )
            if item.coverage == "MED" and item.losses_paid is not None:
                grouped[key].med = (grouped[key].med or Decimal("0")) + item.losses_paid
            elif item.coverage == "WL" and item.losses_paid is not None:
                grouped[key].wl_es_sl = (grouped[key].wl_es_sl or Decimal("0")) + item.losses_paid

        old_list = self.get_othr_inj_clmts_pymt(carrier_clm_num, rec_typ, clid)
        clm_type3_list = [o for o in old_list if o.clm_type == BatchConstants.CLM_TYPE_3]

        updated_list: List[OthrInjClmtsPymt] = []
        seq = 1
        for idx, entry in enumerate(grouped.values()):
            entry.clm_type = "1" if idx == 0 else "2"
            entry.other_proj_seq = seq
            updated_list.append(entry)
            seq += 1

        # Defect 315: preserve CLM_TYPE='3' (other CLIDs with PRBL_LIFE_TM_CARE_IND='N')
        for other_clid_row in clm_type3_list:
            other_clid_row.csr_seq = mcca_csr_seq
            other_clid_row.other_proj_seq = seq
            updated_list.append(other_clid_row)
            seq += 1

        return updated_list
