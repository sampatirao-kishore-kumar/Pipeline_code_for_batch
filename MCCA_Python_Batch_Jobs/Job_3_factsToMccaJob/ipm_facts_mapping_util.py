"""
Step 1 of factsToMccaJob: IPM-to-FACTS Claim & Claimant Mapping Utility.
Direct port of:
  - com.acg.mcca.batch.util.IPMFactsMappingUtil (jobType = 'rfr')
  - com.acg.mcca.batch.dao.impl.IPMFactsMappingUpdateDaoImpl
"""

import logging

logger = logging.getLogger(__name__)


class IPMFactsMappingUtilRfr:
    """
    Validates MCCA_FAC_TMP_RFR and MCCA_FAC_TMP_RFR_PAYLOG for historical IPM-to-FACTS
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

    def perform_sanity_checks_on_temp_tables(self) -> bool:
        """Port of IPMFactsMappingUtil.performSanityChecksOnTempTables for jobType='rfr'."""
        s = self.schema

        # 1. Duplicate IPM or FACTS claim numbers in MCCA_FAC_TMP_RFR
        dup_claim_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT ipm_clm_num, COUNT(ipm_clm_num)
                FROM {s}.mcca_fac_tmp_rfr GROUP BY ipm_clm_num HAVING COUNT(ipm_clm_num) > 1
                UNION ALL
                SELECT carrier_clm_num, COUNT(carrier_clm_num)
                FROM {s}.mcca_fac_tmp_rfr GROUP BY carrier_clm_num HAVING COUNT(carrier_clm_num) > 1
            ) t
        """
        if self._query_count(dup_claim_sql) > 0:
            logger.error("Duplicates found in MCCA_FAC_TMP_RFR for IPM/FACTS claim mapping.")
            return False

        # 2. Conflicts with existing IPM_FACTS_CLAIM_MAPPING_TABLE
        conflict_claim_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT ipm_clm_num, facts_clm_num FROM {s}.ipm_facts_claim_mapping_table
                UNION
                SELECT ipm_clm_num, carrier_clm_num AS facts_clm_num
                FROM {s}.mcca_fac_tmp_rfr WHERE ipm_clm_num IS NOT NULL
            ) a
            INNER JOIN {s}.ipm_facts_claim_mapping_table b
                ON a.ipm_clm_num = b.ipm_clm_num OR a.facts_clm_num = b.facts_clm_num
            WHERE a.ipm_clm_num <> b.ipm_clm_num OR a.facts_clm_num <> b.facts_clm_num
        """
        if self._query_count(conflict_claim_sql) > 0:
            logger.error("Conflicts found in temp tables for Claim mapping table.")
            return False

        # 3. Mapped FACTS claims missing IPM_CLM_NUM in MCCA_FAC_TMP_RFR
        missing_ipm_claim_sql = f"""
            SELECT COUNT(*) FROM {s}.mcca_fac_tmp_rfr a
            INNER JOIN {s}.ipm_facts_claim_mapping_table b
                ON a.carrier_clm_num = b.facts_clm_num
            WHERE a.ipm_clm_num IS NULL
        """
        if self._query_count(missing_ipm_claim_sql) > 0:
            logger.error("FACTS claims mapped to IPM claims are missing IPM claim numbers in MCCA_FAC_TMP_RFR.")
            return False

        # 4. Feature count mismatch in MCCA_FAC_TMP_RFR_PAYLOG
        feature_mismatch_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT carrier_clm_num FROM (
                    SELECT DISTINCT carrier_clm_num, carrier_clmt_num, ipm_clm_num, ipm_clid_num
                    FROM {s}.mcca_fac_tmp_rfr_paylog
                ) p
                GROUP BY carrier_clm_num
                HAVING COUNT(ipm_clid_num) > 0 AND COUNT(carrier_clmt_num) <> COUNT(ipm_clid_num)
            ) t
        """
        if self._query_count(feature_mismatch_sql) > 0:
            logger.error("Claims with feature count mismatch found in MCCA_FAC_TMP_RFR_PAYLOG.")
            return False

        # 5. Duplicates in CLID mapping in MCCA_FAC_TMP_RFR_PAYLOG
        dup_clid_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT carrier_clm_num, carrier_clmt_num
                FROM (
                    SELECT DISTINCT carrier_clm_num, carrier_clmt_num, ipm_clm_num, ipm_clid_num
                    FROM {s}.mcca_fac_tmp_rfr_paylog
                    WHERE ipm_clm_num IS NOT NULL AND ipm_clid_num IS NOT NULL
                ) p1
                GROUP BY carrier_clm_num, carrier_clmt_num HAVING COUNT(*) > 1
                UNION ALL
                SELECT ipm_clm_num, ipm_clid_num
                FROM (
                    SELECT DISTINCT carrier_clm_num, carrier_clmt_num, ipm_clm_num, ipm_clid_num
                    FROM {s}.mcca_fac_tmp_rfr_paylog
                    WHERE ipm_clm_num IS NOT NULL AND ipm_clid_num IS NOT NULL
                ) p2
                GROUP BY ipm_clm_num, ipm_clid_num HAVING COUNT(*) > 1
            ) t
        """
        if self._query_count(dup_clid_sql) > 0:
            logger.error("Duplicates found in MCCA_FAC_TMP_RFR_PAYLOG for CLID mapping.")
            return False

        # 6. Conflicts with IPM_FACTS_CLID_MAPPING_TABLE
        conflict_clid_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT ipm_clm_num, ipm_clid_num, facts_clm_num, facts_clid_num
                FROM {s}.ipm_facts_clid_mapping_table
                UNION
                SELECT DISTINCT ipm_clm_num, ipm_clid_num, carrier_clm_num, carrier_clmt_num
                FROM {s}.mcca_fac_tmp_rfr_paylog
                WHERE ipm_clm_num IS NOT NULL AND ipm_clid_num IS NOT NULL
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
            logger.error("Conflicts found in MCCA_FAC_TMP_RFR_PAYLOG for CLID mapping table.")
            return False

        # 7. Missing IPM CLIDs on already-mapped FACTS CLIDs
        missing_clid_sql = f"""
            SELECT COUNT(*) FROM {s}.mcca_fac_tmp_rfr_paylog a
            INNER JOIN {s}.ipm_facts_clid_mapping_table b
                ON a.carrier_clm_num = b.facts_clm_num AND a.carrier_clmt_num = b.facts_clid_num
            WHERE a.ipm_clm_num IS NULL OR a.ipm_clid_num IS NULL
        """
        if self._query_count(missing_clid_sql) > 0:
            logger.error("FACTS CLIDs mapped to IPM CLIDs are missing IPM CLID numbers.")
            return False

        # 8. Verify MCCA_FAC_TMP_RFR has > 0 records
        rfr_count = self._query_count(f"SELECT COUNT(*) FROM {s}.mcca_fac_tmp_rfr")
        if rfr_count == 0:
            logger.error("No data found in RFR temp tables (MCCA_FAC_TMP_RFR is empty).")
            return False

        return True

    def execute_step1(self) -> bool:
        """Executes Step 1 sanity checks and updates mapping + 9 dependent tables."""
        if not self.perform_sanity_checks_on_temp_tables():
            return False

        s = self.schema
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT code FROM {s}.mcca_codes_decode WHERE code_type = 'ipm_facts_mapping_version'"
            )
            row = cur.fetchone()
            current_ver = int(row[0]) if row and row[0] is not None else 0
            new_ver = current_ver + 1

            # 1. Insert new claim mappings from MCCA_FAC_TMP_RFR
            cur.execute(
                f"""
                INSERT INTO {s}.ipm_facts_claim_mapping_table (
                    ipm_clm_num, facts_clm_num, crt_dttm, crt_user_id, mdfd_dttm, mdfd_user_id, version
                )
                SELECT DISTINCT a.ipm_clm_num, a.carrier_clm_num, CURRENT_TIMESTAMP, 'BATCH', CURRENT_TIMESTAMP, 'BATCH', %s
                FROM {s}.mcca_fac_tmp_rfr a
                WHERE a.ipm_clm_num IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM {s}.ipm_facts_claim_mapping_table b
                      WHERE b.ipm_clm_num = a.ipm_clm_num
                  )
                """,
                (new_ver,),
            )

            # 2. Insert new CLID mappings from MCCA_FAC_TMP_RFR_PAYLOG
            cur.execute(
                f"""
                INSERT INTO {s}.ipm_facts_clid_mapping_table (
                    ipm_clm_num, ipm_clid_num, facts_clm_num, facts_clid_num,
                    crt_dttm, crt_user_id, mdfd_dttm, mdfd_user_id, version
                )
                SELECT DISTINCT a.ipm_clm_num, a.ipm_clid_num, a.carrier_clm_num, a.carrier_clmt_num,
                       CURRENT_TIMESTAMP, 'BATCH', CURRENT_TIMESTAMP, 'BATCH', %s
                FROM {s}.mcca_fac_tmp_rfr_paylog a
                WHERE a.ipm_clm_num IS NOT NULL AND a.ipm_clid_num IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM {s}.ipm_facts_clid_mapping_table b
                      WHERE b.ipm_clm_num = a.ipm_clm_num AND b.ipm_clid_num = a.ipm_clid_num
                  )
                """,
                (new_ver,),
            )

            # 3. Update converted claim numbers across the 9 target tables
            tables_with_clm_type = ["mcca_clm", "mcca_rfr", "mcca_rfr_paylog"]
            for tbl in tables_with_clm_type:
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

            tables_without_clm_type = [
                "mcca_last_bill_date",
                "mcca_write_off",
                "mcca_exception",
                "mcca_othr_inj_clmts_pymt",
            ]
            for tbl in tables_without_clm_type:
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

            # Update MCCA_CLM unique_id & carrier_clmt_num for newly mapped CLIDs
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

            # 4. Update version in MCCA_CODES_DECODE
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
