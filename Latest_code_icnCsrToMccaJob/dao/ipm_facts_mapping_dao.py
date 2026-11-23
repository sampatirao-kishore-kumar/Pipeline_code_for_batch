"""
Step 1 DAO & Tasklet: IPM to FACTS Claim and Claimant Mapping.
1:1 port of:
- com.acg.mcca.batch.impl.IPMFactsMappingUpdateDaoImpl
- com.acg.mcca.batch.util.IPMFactsMappingUtil
"""

import logging
from typing import Dict, Tuple

from dao.base_dao import BaseJdbcDao

logger = logging.getLogger(__name__)


class IPMFactsMappingUpdateDaoImpl(BaseJdbcDao):
    """Exact 1:1 port of com.acg.mcca.batch.impl.IPMFactsMappingUpdateDaoImpl."""

    TARGET_TABLES_CLAIM = [
        "MCCA_RFR",
        "MCCA_RFR_PAYLOG",
        "MCCA_RFR_PAYLOG_CPT",
        "MCCA_ICN",
        "MCCA_CSR",
        "MCCA_PROJECTIONS",
        "MCCA_OTHR_INJ_CLMTS_PYMT",
        "MCCA_REMARKS",
        "MCCA_WRITE_OFF",
    ]

    TARGET_TABLES_CLID = [
        "MCCA_CSR",
        "MCCA_PROJECTIONS",
        "MCCA_OTHR_INJ_CLMTS_PYMT",
        "MCCA_REMARKS",
    ]

    def validate_temp_data(self) -> None:
        """
        Validates temporary tables MCCA_TMP_CLM, MCCA_TMP_CLMNT,
        IPM_FACTS_CLID_MAPPING_TABLE, IPM_FACTS_CLAIM_MAPPING_TABLE, and MCCA_FAC_TMP_RFR.
        Exact port of IPMFactsMappingUpdateDaoImpl.validateTempData().
        """
        sql_mcca_tmp_clm = """
            SELECT COUNT(*) FROM (
                SELECT COUNT(CARRIER_CLM_NUM) AS CNT
                FROM MCCA_TMP_CLM
                WHERE PREV_IPM_CLMNBR IS NOT NULL AND PREV_IPM_CLMNBR != ''
                GROUP BY PREV_IPM_CLMNBR
                HAVING COUNT(CARRIER_CLM_NUM) > 1
            ) sub1
        """
        sql_mcca_tmp_clmnt = """
            SELECT COUNT(*) FROM (
                SELECT COUNT(CLID) AS CNT
                FROM MCCA_TMP_CLMNT
                WHERE IPM_CLAIMANT_NO IS NOT NULL
                GROUP BY CARRIER_CLM_NUM, IPM_CLAIMANT_NO
                HAVING COUNT(CLID) > 1
            ) sub2
        """
        sql_clid_map = """
            SELECT COUNT(*) FROM (
                SELECT COUNT(CLID) AS CNT
                FROM IPM_FACTS_CLID_MAPPING_TABLE
                WHERE IPM_CLID IS NOT NULL
                GROUP BY CARRIER_CLM_NUM, IPM_CLID
                HAVING COUNT(CLID) > 1
            ) sub3
        """
        sql_claim_map = """
            SELECT COUNT(*) FROM (
                SELECT COUNT(CARRIER_CLM_NUM) AS CNT
                FROM IPM_FACTS_CLAIM_MAPPING_TABLE
                WHERE IPM_CLM_NUM IS NOT NULL AND IPM_CLM_NUM != ''
                GROUP BY IPM_CLM_NUM
                HAVING COUNT(CARRIER_CLM_NUM) > 1
            ) sub4
        """
        sql_fac_tmp_rfr = """
            SELECT COUNT(*) FROM (
                SELECT COUNT(CARRIER_CLM_NUM) AS CNT
                FROM MCCA_FAC_TMP_RFR
                WHERE PREV_IPM_CLMNBR IS NOT NULL AND PREV_IPM_CLMNBR != ''
                GROUP BY PREV_IPM_CLMNBR
                HAVING COUNT(CARRIER_CLM_NUM) > 1
            ) sub5
        """
        bad_records = (
            self.query_for_long(sql_mcca_tmp_clm)
            + self.query_for_long(sql_mcca_tmp_clmnt)
            + self.query_for_long(sql_clid_map)
            + self.query_for_long(sql_claim_map)
            + self.query_for_long(sql_fac_tmp_rfr)
        )
        if bad_records > 0:
            raise RuntimeError(
                f"Validation failed in IPMFactsMappingUpdateDaoImpl.validate_temp_data(): "
                f"{bad_records} duplicate mapping records found."
            )

    def update_claim_number_mapping(self, source_table: str = "MCCA_TMP_CLM") -> None:
        """
        Inserts new IPM-to-FACTS claim number mappings from MCCA_TMP_CLM into IPM_FACTS_CLAIM_MAPPING_TABLE.
        Exact port of IPMFactsMappingUpdateDaoImpl.updateClaimNumberMapping(String sourceTable).
        """
        sql = f"""
            INSERT INTO IPM_FACTS_CLAIM_MAPPING_TABLE (
                IPM_CLM_NUM,
                CARRIER_CLM_NUM
            )
            SELECT DISTINCT
                clm.PREV_IPM_CLMNBR,
                clm.CARRIER_CLM_NUM
            FROM {source_table} clm
            LEFT JOIN IPM_FACTS_CLAIM_MAPPING_TABLE map
              ON map.IPM_CLM_NUM = clm.PREV_IPM_CLMNBR
            WHERE map.IPM_CLM_NUM IS NULL
              AND clm.PREV_IPM_CLMNBR IS NOT NULL
        """
        self.update(sql)

    def apply_claim_number_mapping(self) -> None:
        """
        Updates CARRIER_CLM_NUM and CONV_IND='Y' across all 9 MCCA tables for newly mapped claims.
        Exact port of IPMFactsMappingUpdateDaoImpl.applyClaimNumberMapping().
        """
        for table in self.TARGET_TABLES_CLAIM:
            sql = f"""
                UPDATE {table} target
                SET CARRIER_CLM_NUM = (
                    SELECT map.CARRIER_CLM_NUM
                    FROM IPM_FACTS_CLAIM_MAPPING_TABLE map
                    WHERE map.IPM_CLM_NUM = target.CARRIER_CLM_NUM
                ),
                CONV_IND = 'Y'
                WHERE EXISTS (
                    SELECT 1
                    FROM IPM_FACTS_CLAIM_MAPPING_TABLE map
                    WHERE map.IPM_CLM_NUM = target.CARRIER_CLM_NUM
                )
            """
            self.update(sql)

    def get_claim_number_mapping(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        Returns (facts_to_ipm_map, ipm_to_facts_map) from IPM_FACTS_CLAIM_MAPPING_TABLE.
        Exact port of IPMFactsMappingUpdateDaoImpl.getClaimNumberMapping().
        """
        sql = """
            SELECT IPM_CLM_NUM, CARRIER_CLM_NUM
            FROM IPM_FACTS_CLAIM_MAPPING_TABLE
            WHERE IPM_CLM_NUM IS NOT NULL
              AND CARRIER_CLM_NUM IS NOT NULL
        """
        rows = self.query_for_list(sql)
        facts_ipm: Dict[str, str] = {}
        ipm_facts: Dict[str, str] = {}
        for row in rows:
            ipm_no = row["IPM_CLM_NUM"]
            facts_no = row["CARRIER_CLM_NUM"]
            facts_ipm[facts_no] = ipm_no
            ipm_facts[ipm_no] = facts_no
        return facts_ipm, ipm_facts

    def update_claimant_number_mapping(self, source_table: str = "MCCA_TMP_CLMNT") -> None:
        """
        Inserts new claimant number mappings from MCCA_TMP_CLMNT into IPM_FACTS_CLID_MAPPING_TABLE.
        Exact port of IPMFactsMappingUpdateDaoImpl.updateClaimantNumberMapping(String sourceTable).
        """
        clid_col = "CARRIER_CLMT_NUM" if source_table == "MCCA_FAC_TMP_RFR_PAYLOG" else "CLID"
        sql = f"""
            INSERT INTO IPM_FACTS_CLID_MAPPING_TABLE (
                CARRIER_CLM_NUM,
                IPM_CLID,
                CLID
            )
            SELECT DISTINCT
                clmnt.CARRIER_CLM_NUM,
                clmnt.IPM_CLAIMANT_NO,
                clmnt.{clid_col}
            FROM {source_table} clmnt
            LEFT JOIN IPM_FACTS_CLID_MAPPING_TABLE map
              ON map.CARRIER_CLM_NUM = clmnt.CARRIER_CLM_NUM
             AND map.IPM_CLID = clmnt.IPM_CLAIMANT_NO
            WHERE map.IPM_CLID IS NULL
              AND clmnt.IPM_CLAIMANT_NO IS NOT NULL
        """
        self.update(sql)

    def apply_claimant_number_mapping(self) -> None:
        """
        Updates CLID and CONV_IND='N' (where CONV_IND='Y') across MCCA_CSR, MCCA_PROJECTIONS,
        MCCA_OTHR_INJ_CLMTS_PYMT, MCCA_REMARKS, and CARRIER_CLMT_NUM on MCCA_RFR_PAYLOG.
        Exact port of IPMFactsMappingUpdateDaoImpl.applyClaimantNumberMapping().
        """
        for table in self.TARGET_TABLES_CLID:
            sql = f"""
                UPDATE {table} target
                SET CLID = (
                    SELECT map.CLID
                    FROM IPM_FACTS_CLID_MAPPING_TABLE map
                    WHERE map.CARRIER_CLM_NUM = target.CARRIER_CLM_NUM
                      AND CAST(map.IPM_CLID AS VARCHAR(50)) = target.CLID
                ),
                CONV_IND = 'N'
                WHERE target.CONV_IND = 'Y'
                  AND EXISTS (
                      SELECT 1
                      FROM IPM_FACTS_CLID_MAPPING_TABLE map
                      WHERE map.CARRIER_CLM_NUM = target.CARRIER_CLM_NUM
                        AND CAST(map.IPM_CLID AS VARCHAR(50)) = target.CLID
                  )
            """
            self.update(sql)

        sql_paylog = """
            UPDATE MCCA_RFR_PAYLOG target
            SET CARRIER_CLMT_NUM = (
                SELECT map.CLID
                FROM IPM_FACTS_CLID_MAPPING_TABLE map
                WHERE map.CARRIER_CLM_NUM = target.CARRIER_CLM_NUM
                  AND map.IPM_CLID = target.CARRIER_CLMT_NUM
            ),
            CONV_IND = 'N'
            WHERE target.CONV_IND = 'Y'
              AND EXISTS (
                  SELECT 1
                  FROM IPM_FACTS_CLID_MAPPING_TABLE map
                  WHERE map.CARRIER_CLM_NUM = target.CARRIER_CLM_NUM
                    AND map.IPM_CLID = target.CARRIER_CLMT_NUM
              )
        """
        self.update(sql_paylog)

    def get_claimant_number_mapping(self) -> Dict[str, Dict[str, str]]:
        """
        Returns nested dict {facts_claim_number: {facts_clid: ipm_clid}}.
        Exact port of IPMFactsMappingUpdateDaoImpl.getClaimantNumberMapping().
        """
        sql = """
            SELECT CARRIER_CLM_NUM, IPM_CLID, CLID
            FROM IPM_FACTS_CLID_MAPPING_TABLE
            WHERE CARRIER_CLM_NUM IS NOT NULL
              AND IPM_CLID IS NOT NULL
              AND CLID IS NOT NULL
        """
        rows = self.query_for_list(sql)
        result: Dict[str, Dict[str, str]] = {}
        for row in rows:
            claim_no = row["CARRIER_CLM_NUM"]
            ipm_clid = str(row["IPM_CLID"])
            facts_clid = str(row["CLID"])
            if claim_no not in result:
                result[claim_no] = {}
            result[claim_no][facts_clid] = ipm_clid
        return result

    def update_mapping_version_number(self) -> None:
        """
        Increments CODE and DECODE in MCCA_CODES_DECODE WHERE CATEGORY = 'ipm_facts_mapping_version'.
        Exact port of IPMFactsMappingUpdateDaoImpl.updateMappingVersionNumber().
        """
        sql = """
            UPDATE MCCA_CODES_DECODE
            SET CODE = CAST(CAST(CODE AS INTEGER) + 1 AS VARCHAR(50)),
                DECODE = CAST(CAST(DECODE AS INTEGER) + 1 AS VARCHAR(50))
            WHERE CATEGORY = 'ipm_facts_mapping_version'
        """
        self.update(sql)


class IPMFactsMappingUtil:
    """
    Exact 1:1 port of com.acg.mcca.batch.util.IPMFactsMappingUtil (Step 1 Tasklet).
    Configured with jobType="icncsr" in beanInfo.xml (lines 946-950).
    """

    def __init__(self, dao: IPMFactsMappingUpdateDaoImpl, job_type: str = "icncsr"):
        self.dao = dao
        self.job_type = job_type
        self.facts_ipm_claim_number_mapping: Dict[str, str] = {}
        self.ipm_facts_claim_number_mapping: Dict[str, str] = {}
        self.facts_ipm_claimant_number_mapping: Dict[str, Dict[str, str]] = {}

    def execute(self) -> None:
        logger.info("Executing Step 1: IPMFactsMappingUtil (jobType=%s)", self.job_type)
        self.dao.validate_temp_data()
        claim_source_table = (
            "MCCA_FAC_TMP_RFR" if self.job_type == "rfr" else "MCCA_TMP_CLM"
        )
        self.dao.update_claim_number_mapping(claim_source_table)
        self.dao.apply_claim_number_mapping()
        self.facts_ipm_claim_number_mapping, self.ipm_facts_claim_number_mapping = (
            self.dao.get_claim_number_mapping()
        )

        clmnt_source_table = (
            "MCCA_FAC_TMP_RFR_PAYLOG" if self.job_type == "rfr" else "MCCA_TMP_CLMNT"
        )
        self.dao.update_claimant_number_mapping(clmnt_source_table)
        self.dao.apply_claimant_number_mapping()
        self.facts_ipm_claimant_number_mapping = self.dao.get_claimant_number_mapping()
        self.dao.update_mapping_version_number()
        logger.info("Completed Step 1: IPMFactsMappingUtil")
