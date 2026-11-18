"""
Step 1 of icnCsrToMccaJob: IPM-to-FACTS Claim & Claimant Mapping Utility.
Direct port of:
  - com.acg.mcca.batch.util.IPMFactsMappingUtil (jobType = 'icn_csr')
  - com.acg.mcca.batch.dao.impl.IPMFactsMappingUpdateDaoImpl
"""

import logging

logger = logging.getLogger(__name__)


class IPMFactsMappingUtilIcnCsr:
    """
    Validates MCCA_TMP_CLM and MCCA_TMP_CLM_DTLS for historical IPM-to-FACTS
    converted claims and updates converted claim/claimant numbers across all 9 MCCA tables.
    """

    def __init__(self, conn, schema: str = "mcca") -> None:
        self.conn = conn
        self.schema = schema

    def _query_count(self, sql: str) -> int:
        with self.conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            return int(row[0]) if row and row[0] is not None else 0

    def perform_sanity_checks_on_temp_tables(self) -> str:
        """
        Port of IPMFactsMappingUtil.performSanityChecksOnTempTables for jobType='icn_csr'.
        Returns:
          - 'OK': Checks passed and data exists
          - 'EMPTY': Both MCCA_TMP_CLM and MCCA_TMP_CLM_DTLS are empty (continues gracefully)
          - 'FAILED': Sanity check violation detected
        """
        s = self.schema

        # 1. Duplicate IPM or FACTS claim numbers across MCCA_TMP_CLM & MCCA_TMP_CLM_DTLS
        dup_claim_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT ipm_clm_num, COUNT(*) FROM (
                    SELECT DISTINCT ipm_clm_num, carrier_clm_num FROM {s}.mcca_tmp_clm WHERE ipm_clm_num IS NOT NULL
                    UNION
                    SELECT DISTINCT ipm_clm_num, carrier_clm_num FROM {s}.mcca_tmp_clm_dtls WHERE ipm_clm_num IS NOT NULL
                ) u1 GROUP BY ipm_clm_num HAVING COUNT(*) > 1
                UNION ALL
                SELECT carrier_clm_num, COUNT(*) FROM (
                    SELECT DISTINCT ipm_clm_num, carrier_clm_num FROM {s}.mcca_tmp_clm WHERE ipm_clm_num IS NOT NULL
                    UNION
                    SELECT DISTINCT ipm_clm_num, carrier_clm_num FROM {s}.mcca_tmp_clm_dtls WHERE ipm_clm_num IS NOT NULL
                ) u2 GROUP BY carrier_clm_num HAVING COUNT(*) > 1
            ) t
        """
        if self._query_count(dup_claim_sql) > 0:
            logger.error("Duplicates found in ICN/CSR temp tables for Claim mapping table.")
            return "FAILED"

        # 2. Conflicts with existing IPM_FACTS_CLAIM_MAPPING_TABLE
        conflict_claim_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT ipm_clm_num, facts_clm_num FROM {s}.ipm_facts_claim_mapping_table
                UNION
                SELECT ipm_clm_num, carrier_clm_num AS facts_clm_num FROM {s}.mcca_tmp_clm WHERE ipm_clm_num IS NOT NULL
                UNION
                SELECT ipm_clm_num, carrier_clm_num AS facts_clm_num FROM {s}.mcca_tmp_clm_dtls WHERE ipm_clm_num IS NOT NULL
            ) a
            INNER JOIN {s}.ipm_facts_claim_mapping_table b
                ON a.ipm_clm_num = b.ipm_clm_num OR a.facts_clm_num = b.facts_clm_num
            WHERE a.ipm_clm_num <> b.ipm_clm_num OR a.facts_clm_num <> b.facts_clm_num
        """
        if self._query_count(conflict_claim_sql) > 0:
            logger.error("Conflicts found in ICN/CSR temp tables for Claim mapping table.")
            return "FAILED"

        # 3. Mapped FACTS claims missing IPM_CLM_NUM
        missing_ipm_claim_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT carrier_clm_num, ipm_clm_num FROM {s}.mcca_tmp_clm
                UNION ALL
                SELECT carrier_clm_num, ipm_clm_num FROM {s}.mcca_tmp_clm_dtls
            ) a
            INNER JOIN {s}.ipm_facts_claim_mapping_table b
                ON a.carrier_clm_num = b.facts_clm_num
            WHERE a.ipm_clm_num IS NULL
        """
        if self._query_count(missing_ipm_claim_sql) > 0:
            logger.error("FACTS claims mapped to IPM claims are missing IPM claim numbers.")
            return "FAILED"

        # 4. Feature count mismatch
        feature_mismatch_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT carrier_clm_num FROM (
                    SELECT DISTINCT carrier_clm_num, carrier_clmt_num, ipm_clm_num, ipm_clid_num FROM {s}.mcca_tmp_clm
                    UNION
                    SELECT DISTINCT carrier_clm_num, carrier_clmt_num, ipm_clm_num, ipm_clid_num FROM {s}.mcca_tmp_clm_dtls
                ) p
                GROUP BY carrier_clm_num
                HAVING COUNT(ipm_clid_num) > 0 AND COUNT(carrier_clmt_num) <> COUNT(ipm_clid_num)
            ) t
        """
        if self._query_count(feature_mismatch_sql) > 0:
            logger.error("Claims with feature count mismatch found in ICN/CSR temp tables.")
            return "FAILED"

        # 5. Duplicates in CLID mapping
        dup_clid_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT carrier_clm_num, carrier_clmt_num FROM (
                    SELECT DISTINCT carrier_clm_num, carrier_clmt_num, ipm_clm_num, ipm_clid_num
                    FROM {s}.mcca_tmp_clm WHERE ipm_clm_num IS NOT NULL AND ipm_clid_num IS NOT NULL
                    UNION
                    SELECT DISTINCT carrier_clm_num, carrier_clmt_num, ipm_clm_num, ipm_clid_num
                    FROM {s}.mcca_tmp_clm_dtls WHERE ipm_clm_num IS NOT NULL AND ipm_clid_num IS NOT NULL
                ) p1 GROUP BY carrier_clm_num, carrier_clmt_num HAVING COUNT(*) > 1
            ) t
        """
        if self._query_count(dup_clid_sql) > 0:
            logger.error("Duplicates found in ICN/CSR temp tables for CLID mapping table.")
            return "FAILED"

        # 6. Conflicts with IPM_FACTS_CLID_MAPPING_TABLE
        conflict_clid_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT ipm_clm_num, ipm_clid_num, facts_clm_num, facts_clid_num
                FROM {s}.ipm_facts_clid_mapping_table
                UNION
                SELECT DISTINCT ipm_clm_num, ipm_clid_num, carrier_clm_num, carrier_clmt_num
                FROM {s}.mcca_tmp_clm WHERE ipm_clm_num IS NOT NULL AND ipm_clid_num IS NOT NULL
                UNION
                SELECT DISTINCT ipm_clm_num, ipm_clid_num, carrier_clm_num, carrier_clmt_num
                FROM {s}.mcca_tmp_clm_dtls WHERE ipm_clm_num IS NOT NULL AND ipm_clid_num IS NOT NULL
            ) a
            INNER JOIN {s}.ipm_facts_clid_mapping_table b
                ON (a.ipm_clm_num = b.ipm_clm_num AND a.ipm_clid_num = b.ipm_clid_num)
                OR (a.facts_clm_num = b.facts_clm_num AND a.facts_clid_num = b.facts_clid_num)
            WHERE a.ipm_clm_num <> b.ipm_clm_num
               OR a.ipm_clid_num <> b.ipm_clid_num
               OR a.facts_clm_num <> b.facts_clm_num
               OR a.facts_clid_num <> b.facts_clid_num
        """
        if self._query_count(conflict_clid_sql) > 0:
            logger.error("Conflicts found in ICN/CSR temp tables for CLID mapping table.")
            return "FAILED"

        # 7. Missing IPM CLIDs on already-mapped FACTS CLIDs
        missing_clid_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT carrier_clm_num, carrier_clmt_num, ipm_clm_num, ipm_clid_num FROM {s}.mcca_tmp_clm
                UNION ALL
                SELECT carrier_clm_num, carrier_clmt_num, ipm_clm_num, ipm_clid_num FROM {s}.mcca_tmp_clm_dtls
            ) a
            INNER JOIN {s}.ipm_facts_clid_mapping_table b
                ON a.carrier_clm_num = b.facts_clm_num AND a.carrier_clmt_num = b.facts_clid_num
            WHERE a.ipm_clm_num IS NULL OR a.ipm_clid_num IS NULL
        """
        if self._query_count(missing_clid_sql) > 0:
            logger.error("FACTS CLIDs mapped to IPM CLIDs are missing IPM CLID numbers.")
            return "FAILED"

        clm_cnt = self._query_count(f"SELECT COUNT(*) FROM {s}.mcca_tmp_clm")
        dtls_cnt = self._query_count(f"SELECT COUNT(*) FROM {s}.mcca_tmp_clm_dtls")
        if clm_cnt == 0 and dtls_cnt == 0:
            logger.info("No data found in ICN CSR temp tables.")
            return "EMPTY"

        return "OK"

    def execute_step1(self) -> bool:
        status = self.perform_sanity_checks_on_temp_tables()
        if status == "FAILED":
            return False
        if status == "EMPTY":
            return True

        s = self.schema
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT code FROM {s}.mcca_codes_decode WHERE code_type = 'ipm_facts_mapping_version'"
            )
            row = cur.fetchone()
            current_ver = int(row[0]) if row and row[0] is not None else 0
            new_ver = current_ver + 1

            cur.execute(
                f"""
                INSERT INTO {s}.ipm_facts_claim_mapping_table (
                    ipm_clm_num, facts_clm_num, crt_dttm, crt_user_id, mdfd_dttm, mdfd_user_id, version
                )
                SELECT DISTINCT a.ipm_clm_num, a.carrier_clm_num, CURRENT_TIMESTAMP, 'BATCH', CURRENT_TIMESTAMP, 'BATCH', %s
                FROM (
                    SELECT ipm_clm_num, carrier_clm_num FROM {s}.mcca_tmp_clm WHERE ipm_clm_num IS NOT NULL
                    UNION
                    SELECT ipm_clm_num, carrier_clm_num FROM {s}.mcca_tmp_clm_dtls WHERE ipm_clm_num IS NOT NULL
                ) a
                WHERE NOT EXISTS (
                    SELECT 1 FROM {s}.ipm_facts_claim_mapping_table b
                    WHERE b.ipm_clm_num = a.ipm_clm_num
                )
                """,
                (new_ver,),
            )

            cur.execute(
                f"""
                INSERT INTO {s}.ipm_facts_clid_mapping_table (
                    ipm_clm_num, ipm_clid_num, facts_clm_num, facts_clid_num,
                    crt_dttm, crt_user_id, mdfd_dttm, mdfd_user_id, version
                )
                SELECT DISTINCT a.ipm_clm_num, a.ipm_clid_num, a.carrier_clm_num, a.carrier_clmt_num,
                       CURRENT_TIMESTAMP, 'BATCH', CURRENT_TIMESTAMP, 'BATCH', %s
                FROM (
                    SELECT ipm_clm_num, ipm_clid_num, carrier_clm_num, carrier_clmt_num
                    FROM {s}.mcca_tmp_clm WHERE ipm_clm_num IS NOT NULL AND ipm_clid_num IS NOT NULL
                    UNION
                    SELECT ipm_clm_num, ipm_clid_num, carrier_clm_num, carrier_clmt_num
                    FROM {s}.mcca_tmp_clm_dtls WHERE ipm_clm_num IS NOT NULL AND ipm_clid_num IS NOT NULL
                ) a
                WHERE NOT EXISTS (
                    SELECT 1 FROM {s}.ipm_facts_clid_mapping_table b
                    WHERE b.ipm_clm_num = a.ipm_clm_num AND b.ipm_clid_num = a.ipm_clid_num
                )
                """,
                (new_ver,),
            )

            for tbl in ["mcca_clm", "mcca_rfr", "mcca_rfr_paylog"]:
                cur.execute(
                    f"""
                    UPDATE {s}.{tbl} t
                    SET carrier_clm_num = m.facts_clm_num,
                        clm_type = 'FACTS',
                        mdfd_dttm = CURRENT_TIMESTAMP,
                        mdfd_user_id = 'BATCH'
                    FROM {s}.ipm_facts_claim_mapping_table m
                    WHERE t.carrier_clm_num = m.ipm_clm_num AND m.version = %s
                    """,
                    (new_ver,),
                )

            for tbl in [
                "mcca_last_bill_date",
                "mcca_write_off",
                "mcca_exception",
                "mcca_othr_inj_clmts_pymt",
            ]:
                cur.execute(
                    f"""
                    UPDATE {s}.{tbl} t
                    SET carrier_clm_num = m.facts_clm_num,
                        mdfd_dttm = CURRENT_TIMESTAMP,
                        mdfd_user_id = 'BATCH'
                    FROM {s}.ipm_facts_claim_mapping_table m
                    WHERE t.carrier_clm_num = m.ipm_clm_num AND m.version = %s
                    """,
                    (new_ver,),
                )

            cur.execute(
                f"""
                UPDATE {s}.mcca_clm t
                SET carrier_clmt_num = m.facts_clid_num,
                    unique_id = m.facts_clm_num || '-' || m.facts_clid_num,
                    mdfd_dttm = CURRENT_TIMESTAMP,
                    mdfd_user_id = 'BATCH'
                FROM {s}.ipm_facts_clid_mapping_table m
                WHERE t.carrier_clm_num = m.facts_clm_num
                  AND t.carrier_clmt_num = m.ipm_clid_num
                  AND m.version = %s
                """,
                (new_ver,),
            )

            for tbl in ["mcca_last_bill_date", "mcca_exception"]:
                cur.execute(
                    f"""
                    UPDATE {s}.{tbl} t
                    SET carrier_clmt_num = m.facts_clid_num,
                        mdfd_dttm = CURRENT_TIMESTAMP,
                        mdfd_user_id = 'BATCH'
                    FROM {s}.ipm_facts_clid_mapping_table m
                    WHERE t.carrier_clm_num = m.facts_clm_num
                      AND t.carrier_clmt_num = m.ipm_clid_num
                      AND m.version = %s
                    """,
                    (new_ver,),
                )

            cur.execute(
                f"""
                UPDATE {s}.mcca_codes_decode
                SET code = %s, mdfd_dttm = CURRENT_TIMESTAMP, mdfd_user_id = 'BATCH'
                WHERE code_type = 'ipm_facts_mapping_version'
                """,
                (str(new_ver),),
            )

        self.conn.commit()
        logger.info("Step 1 completed: IPM-to-FACTS mapping version updated to %d.", new_ver)
        return True
