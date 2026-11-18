"""
AlloyDB / PostgreSQL Data Access Layer for Job 4: icnCsrToMccaJob.
Direct port of:
  - IcnJdbcDaoImpl.java
  - CsrJdbcDaoImpl.java
  - OthrInjClmtsDaoImpl.java
  - UpdateIcnCsrJdbcDaoImpl.java
  - MccaClaimDaoImpl.java
  - CopyIcnWriter.java, IcnDetailWriter.java, CsrDetailWriter.java
  - OthrInjClmtsWriter.java, UpdateIcnTmpClaimDetailWriter.java
  - UpdateIcnCsrClaimDetailWriter.java, CsrAmountUpdateWriter.java, MccaClaimRptdWriter.java
  - DBUtils.java (clearIcnTempTables)
"""

from typing import Any, Dict, List
import psycopg2.extras


class IcnCsrDao:
    """Handles all AlloyDB operations for icnCsrToMccaJob across Steps 2 through 10."""

    def __init__(self, conn, schema: str = "mcca") -> None:
        self.conn = conn
        self.schema = schema

    def get_max_txn_id(self) -> int:
        """Port of CopyIcnProcessor.getMaxId: SELECT MAX(TXN_ID) FROM MCCA_CLM."""
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT COALESCE(MAX(txn_id), 0) FROM {self.schema}.mcca_clm")
            return int(cur.fetchone()[0])

    def is_exception_claim(self, carrier_claim_number: str, carrier_claimant_number: int) -> bool:
        """Port of IcnJdbcDaoImpl.isExceptionClaim & CsrJdbcDaoImpl.isExceptionClaim (codes '1', '2')."""
        sql = f"""
            SELECT COUNT(*)
            FROM {self.schema}.mcca_exception
            WHERE carrier_clm_num = %s
              AND carrier_clmt_num = %s
              AND exception_code IN ('1', '2')
              AND exception_value = 'Y'
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (carrier_claim_number, carrier_claimant_number))
            return int(cur.fetchone()[0]) > 0

    # ==========================================================================
    # STEP 2: CopyIcnProcessor & CopyIcnWriter
    # ==========================================================================
    def fetch_copy_icn_candidates(self) -> List[Dict[str, Any]]:
        """Reads latest SB/MN rows in MCCA_CLM that match MCCA_TMP_CLM."""
        sql = f"""
            SELECT clm.*
            FROM {self.schema}.mcca_clm clm, {self.schema}.mcca_tmp_clm tmp
            WHERE clm.unique_id = tmp.carrier_clm_num || '-' || tmp.carrier_clmt_num
              AND clm.txn_id IN (
                  SELECT MAX(clm2.txn_id)
                  FROM {self.schema}.mcca_clm clm2
                  WHERE clm.unique_id = clm2.unique_id
              )
              AND clm.status IN ('SB', 'MN')
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            return [dict(r) for r in cur.fetchall()]

    def clone_icn_to_csr(self, clm: Dict[str, Any]) -> None:
        """Port of CopyIcnWriter: Clones existing MCCA_CLM row as a new TXN_ID with REC_TYPE='CSR'."""
        sql = f"""
            INSERT INTO {self.schema}.mcca_clm (
                txn_id, unique_id, rec_type, carrier_id, naic_cd, carrier_clm_num,
                carrier_clmt_num, mcca_clm_num, pol_num, pol_eff_dt, pol_exp_dt,
                loss_dt, ins_fst_name, ins_midl_init, ins_lst_name,
                clmt_fst_name, clmt_midl_init, clmt_lst_name, clmt_birth_dt, clmt_gndr_cd,
                inj_desc, brain_inj_cd, mcca_stat_cd, mcca_rel_cd, accd_dt, accd_desc,
                tot_res_amt, cum_amt_paid_to_dt, adj_name, adj_phn_num,
                status, err_ele_list, clm_type, crt_dttm, crt_user_id, mdfd_dttm, mdfd_user_id
            ) VALUES (
                nextval('{self.schema}.mcca_clm_txn_id_seq'),
                %(unique_id)s, 'CSR', %(carrier_id)s, %(naic_cd)s, %(carrier_clm_num)s,
                %(carrier_clmt_num)s, %(mcca_clm_num)s, %(pol_num)s, %(pol_eff_dt)s, %(pol_exp_dt)s,
                %(loss_dt)s, %(ins_fst_name)s, %(ins_midl_init)s, %(ins_lst_name)s,
                %(clmt_fst_name)s, %(clmt_midl_init)s, %(clmt_lst_name)s, %(clmt_birth_dt)s, %(clmt_gndr_cd)s,
                %(inj_desc)s, %(brain_inj_cd)s, %(mcca_stat_cd)s, %(mcca_rel_cd)s, %(accd_dt)s, %(accd_desc)s,
                %(tot_res_amt)s, %(cum_amt_paid_to_dt)s, %(adj_name)s, %(adj_phn_num)s,
                'PN', NULL, 'FACTS', CURRENT_TIMESTAMP, 'BATCH', CURRENT_TIMESTAMP, 'BATCH'
            )
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, clm)

    # ==========================================================================
    # STEP 3: IcnDetailProcessor & IcnDetailWriter
    # ==========================================================================
    def fetch_new_icn_candidates(self) -> List[Dict[str, Any]]:
        """Reads rows in MCCA_TMP_CLM not yet present in MCCA_CLM."""
        sql = f"""
            SELECT *
            FROM {self.schema}.mcca_tmp_clm tmp
            WHERE (tmp.carrier_clm_num || '-' || tmp.carrier_clmt_num) NOT IN (
                SELECT DISTINCT unique_id FROM {self.schema}.mcca_clm
            )
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            return [dict(r) for r in cur.fetchall()]

    def insert_new_icn(self, icn: Dict[str, Any]) -> None:
        """Port of IcnDetailWriter: Inserts new ICN row into MCCA_CLM."""
        sql = f"""
            INSERT INTO {self.schema}.mcca_clm (
                txn_id, unique_id, rec_type, carrier_id, naic_cd, carrier_clm_num,
                carrier_clmt_num, mcca_clm_num, pol_num, pol_eff_dt, pol_exp_dt,
                loss_dt, ins_fst_name, ins_midl_init, ins_lst_name,
                clmt_fst_name, clmt_midl_init, clmt_lst_name, clmt_birth_dt, clmt_gndr_cd,
                inj_desc, brain_inj_cd, mcca_stat_cd, mcca_rel_cd, accd_dt, accd_desc,
                tot_res_amt, cum_amt_paid_to_dt, adj_name, adj_phn_num,
                status, err_ele_list, clm_type, crt_dttm, crt_user_id, mdfd_dttm, mdfd_user_id
            ) VALUES (
                nextval('{self.schema}.mcca_clm_txn_id_seq'),
                %(unique_id)s, 'ICN', %(carrier_id)s, %(naic_cd)s, %(carrier_clm_num)s,
                %(carrier_clmt_num)s, %(mcca_clm_num)s, %(pol_num)s, %(pol_eff_dt)s, %(pol_exp_dt)s,
                %(loss_dt)s, %(ins_fst_name)s, %(ins_midl_init)s, %(ins_lst_name)s,
                %(clmt_fst_name)s, %(clmt_midl_init)s, %(clmt_lst_name)s, %(clmt_birth_dt)s, %(clmt_gndr_cd)s,
                %(inj_desc)s, %(brain_inj_cd)s, %(mcca_stat_cd)s, %(mcca_rel_cd)s, %(accd_dt)s, %(accd_desc)s,
                %(tot_res_amt)s, %(cum_amt_paid_to_dt)s, %(adj_name)s, %(adj_phn_num)s,
                %(status)s, %(err_ele_list)s, 'FACTS',
                CURRENT_TIMESTAMP, 'BATCH', CURRENT_TIMESTAMP, 'BATCH'
            )
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, icn)

    # ==========================================================================
    # STEP 4: CsrDetailProcessor & CsrDetailWriter
    # ==========================================================================
    def fetch_csr_candidates(self) -> List[Dict[str, Any]]:
        """Reads MCCA_TMP_CLM joined with latest TXN_ID in MCCA_CLM."""
        sql = f"""
            SELECT tmp.*, clm.txn_id AS clm_txn_id, clm.unique_id AS clm_unique_id,
                   clm.rec_type AS clm_rec_type, clm.mcca_clm_num AS clm_mcca_clm_num
            FROM {self.schema}.mcca_tmp_clm tmp, {self.schema}.mcca_clm clm
            WHERE clm.unique_id = tmp.carrier_clm_num || '-' || tmp.carrier_clmt_num
              AND clm.txn_id IN (
                  SELECT MAX(clm2.txn_id)
                  FROM {self.schema}.mcca_clm clm2
                  WHERE clm2.unique_id = clm.unique_id
              )
              AND clm.rec_type = 'CSR'
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            return [dict(r) for r in cur.fetchall()]

    def insert_remarks(self, unique_id: str, remarks: str) -> None:
        """Port of CsrJdbcDaoImpl.insertRemarks."""
        sql = f"""
            INSERT INTO {self.schema}.mcca_remarks (
                remark_seq_num, unique_id, remarks, crt_dttm, crt_user_id, mdfd_dttm, mdfd_user_id
            ) VALUES (
                nextval('{self.schema}.mcca_remark_seq'),
                %s, %s, CURRENT_TIMESTAMP, 'BATCH', CURRENT_TIMESTAMP, 'BATCH'
            )
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (unique_id, remarks))

    def update_csr_detail(self, csr: Dict[str, Any]) -> None:
        """Port of CsrDetailWriter: Updates latest CSR row in MCCA_CLM."""
        sql = f"""
            UPDATE {self.schema}.mcca_clm
            SET tot_res_amt = %(tot_res_amt)s,
                cum_amt_paid_to_dt = %(cum_amt_paid_to_dt)s,
                adj_name = COALESCE(%(adj_name)s, adj_name),
                adj_phn_num = COALESCE(%(adj_phn_num)s, adj_phn_num),
                mcca_stat_cd = COALESCE(%(mcca_stat_cd)s, mcca_stat_cd),
                status = %(status)s,
                err_ele_list = %(err_ele_list)s,
                mdfd_dttm = CURRENT_TIMESTAMP,
                mdfd_user_id = 'BATCH'
            WHERE txn_id = %(clm_txn_id)s
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, csr)

    # ==========================================================================
    # STEP 5: OthrInjClmtsWriter
    # ==========================================================================
    def copy_other_injured_claimants(self) -> int:
        """Port of OthrInjClmtsWriter & OthrInjClmtsDaoImpl."""
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                DELETE FROM {self.schema}.mcca_othr_inj_clmts_pymt
                WHERE (carrier_clm_num || '-' || carrier_clmt_num) IN (
                    SELECT carrier_clm_num || '-' || carrier_clmt_num
                    FROM {self.schema}.mcca_tmp_othr_inj_clmts_pymt
                )
                """
            )
            cur.execute(
                f"""
                INSERT INTO {self.schema}.mcca_othr_inj_clmts_pymt (
                    othr_inj_seq_id, carrier_clm_num, carrier_clmt_num,
                    othr_clmt_fst_name, othr_clmt_midl_init, othr_clmt_lst_name,
                    tot_res_amt, cum_amt_paid_to_dt,
                    crt_dttm, crt_user_id, mdfd_dttm, mdfd_user_id
                )
                SELECT
                    nextval('{self.schema}.mcca_othr_inj_seq'),
                    tmp.carrier_clm_num, tmp.carrier_clmt_num,
                    tmp.othr_clmt_fst_name, tmp.othr_clmt_midl_init, tmp.othr_clmt_lst_name,
                    tmp.tot_res_amt, tmp.cum_amt_paid_to_dt,
                    CURRENT_TIMESTAMP, 'BATCH', CURRENT_TIMESTAMP, 'BATCH'
                FROM {self.schema}.mcca_tmp_othr_inj_clmts_pymt tmp
                WHERE (tmp.carrier_clm_num || '-' || tmp.carrier_clmt_num) IN (
                    SELECT DISTINCT unique_id FROM {self.schema}.mcca_clm
                )
                """
            )
            return cur.rowcount

    # ==========================================================================
    # STEP 6: UpdateIcnTmpClaimProcessor & UpdateIcnTmpClaimDetailWriter
    # ==========================================================================
    def fetch_step6_tmp_claim_details(self, max_txn_id: int) -> List[Dict[str, Any]]:
        """Joins MCCA_CLM (where TXN_ID > max_txn_id) with MCCA_TMP_CLM_DTLS."""
        sql = f"""
            SELECT clm.*,
                   dtls.pol_num AS d_pol_num, dtls.pol_eff_dt AS d_pol_eff_dt,
                   dtls.pol_exp_dt AS d_pol_exp_dt, dtls.loss_dt AS d_loss_dt,
                   dtls.ins_fst_name AS d_ins_fst_name, dtls.ins_midl_init AS d_ins_midl_init,
                   dtls.ins_lst_name AS d_ins_lst_name, dtls.clmt_fst_name AS d_clmt_fst_name,
                   dtls.clmt_midl_init AS d_clmt_midl_init, dtls.clmt_lst_name AS d_clmt_lst_name,
                   dtls.clmt_birth_dt AS d_clmt_birth_dt, dtls.clmt_gndr_cd AS d_clmt_gndr_cd,
                   dtls.accd_dt AS d_accd_dt, dtls.accd_desc AS d_accd_desc,
                   dtls.icd1_cd, dtls.icd1_desc, dtls.icd2_cd, dtls.icd2_desc,
                   dtls.icd3_cd, dtls.icd3_desc
            FROM {self.schema}.mcca_clm clm, {self.schema}.mcca_tmp_clm_dtls dtls
            WHERE clm.unique_id = dtls.carrier_clm_num || '-' || dtls.carrier_clmt_num
              AND clm.txn_id > %s
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (max_txn_id,))
            return [dict(r) for r in cur.fetchall()]

    def update_claim_from_details(self, clm: Dict[str, Any]) -> None:
        """Port of UpdateIcnTmpClaimDetailWriter & UpdateIcnCsrClaimDetailWriter."""
        sql = f"""
            UPDATE {self.schema}.mcca_clm
            SET pol_num = COALESCE(%(pol_num)s, pol_num),
                pol_eff_dt = COALESCE(%(pol_eff_dt)s, pol_eff_dt),
                pol_exp_dt = COALESCE(%(pol_exp_dt)s, pol_exp_dt),
                loss_dt = COALESCE(%(loss_dt)s, loss_dt),
                ins_fst_name = COALESCE(%(ins_fst_name)s, ins_fst_name),
                ins_midl_init = COALESCE(%(ins_midl_init)s, ins_midl_init),
                ins_lst_name = COALESCE(%(ins_lst_name)s, ins_lst_name),
                clmt_fst_name = COALESCE(%(clmt_fst_name)s, clmt_fst_name),
                clmt_midl_init = COALESCE(%(clmt_midl_init)s, clmt_midl_init),
                clmt_lst_name = COALESCE(%(clmt_lst_name)s, clmt_lst_name),
                clmt_birth_dt = COALESCE(%(clmt_birth_dt)s, clmt_birth_dt),
                clmt_gndr_cd = COALESCE(%(clmt_gndr_cd)s, clmt_gndr_cd),
                accd_dt = COALESCE(%(accd_dt)s, accd_dt),
                accd_desc = COALESCE(%(accd_desc)s, accd_desc),
                inj_desc = COALESCE(%(inj_desc)s, inj_desc),
                brain_inj_cd = COALESCE(%(brain_inj_cd)s, brain_inj_cd),
                status = %(status)s,
                err_ele_list = %(err_ele_list)s,
                mdfd_dttm = CURRENT_TIMESTAMP,
                mdfd_user_id = 'BATCH'
            WHERE txn_id = %(txn_id)s
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, clm)

    # ==========================================================================
    # STEP 7: UpdateIcnCsrClaimProcessor (Claims NOT in MCCA_TMP_CLM)
    # ==========================================================================
    def fetch_step7_existing_claim_details(self, max_txn_id: int) -> List[Dict[str, Any]]:
        """Selects open IC/PN claims at max TXN_ID <= max_txn_id joined with MCCA_TMP_CLM_DTLS."""
        sql = f"""
            SELECT clm.*,
                   dtls.pol_num AS d_pol_num, dtls.pol_eff_dt AS d_pol_eff_dt,
                   dtls.pol_exp_dt AS d_pol_exp_dt, dtls.loss_dt AS d_loss_dt,
                   dtls.ins_fst_name AS d_ins_fst_name, dtls.ins_midl_init AS d_ins_midl_init,
                   dtls.ins_lst_name AS d_ins_lst_name, dtls.clmt_fst_name AS d_clmt_fst_name,
                   dtls.clmt_midl_init AS d_clmt_midl_init, dtls.clmt_lst_name AS d_clmt_lst_name,
                   dtls.clmt_birth_dt AS d_clmt_birth_dt, dtls.clmt_gndr_cd AS d_clmt_gndr_cd,
                   dtls.accd_dt AS d_accd_dt, dtls.accd_desc AS d_accd_desc,
                   dtls.icd1_cd, dtls.icd1_desc, dtls.icd2_cd, dtls.icd2_desc,
                   dtls.icd3_cd, dtls.icd3_desc
            FROM {self.schema}.mcca_clm clm, {self.schema}.mcca_tmp_clm_dtls dtls
            WHERE clm.unique_id = dtls.carrier_clm_num || '-' || dtls.carrier_clmt_num
              AND clm.txn_id <= %s
              AND clm.txn_id IN (
                  SELECT MAX(clm2.txn_id)
                  FROM {self.schema}.mcca_clm clm2
                  WHERE clm2.unique_id = clm.unique_id
              )
              AND clm.status IN ('IC', 'PN')
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (max_txn_id,))
            return [dict(r) for r in cur.fetchall()]

    # ==========================================================================
    # STEP 8: CsrAmountUpdateWriter (From MCCA_INCURRED_AMT_SUM)
    # ==========================================================================
    def update_amounts_from_incurred_sum(self) -> int:
        """Step 8: Updates TOT_RES_AMT & CUM_AMT_PAID_TO_DT from MCCA_INCURRED_AMT_SUM."""
        sql = f"""
            UPDATE {self.schema}.mcca_clm clm
            SET tot_res_amt = inc.tot_res_amt,
                cum_amt_paid_to_dt = inc.cum_amt_paid_to_dt,
                mdfd_dttm = CURRENT_TIMESTAMP,
                mdfd_user_id = 'BATCH'
            FROM {self.schema}.mcca_incurred_amt_sum inc
            WHERE clm.carrier_clm_num = inc.carrier_clm_num
              AND clm.carrier_clmt_num = inc.carrier_clmt_num
              AND clm.txn_id IN (
                  SELECT MAX(clm2.txn_id)
                  FROM {self.schema}.mcca_clm clm2
                  WHERE clm2.unique_id = clm.unique_id
              )
              AND clm.status IN ('IC', 'PN')
        """
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.rowcount

    # ==========================================================================
    # STEP 9: AmountUpdateProcessor (Companion Claim Amount Aggregation)
    # ==========================================================================
    def update_companion_claim_amounts(self) -> int:
        """Step 9: Aggregates TOT_RES_AMT & CUM_AMT_PAID_TO_DT across companion claims sharing MCCA_CLM_NUM."""
        sql = f"""
            WITH companion_totals AS (
                SELECT
                    SUBSTR(TRIM(mcca_clm_num), 1, 8) AS base_mcca_num,
                    SUM(tot_res_amt) AS sum_res,
                    SUM(cum_amt_paid_to_dt) AS sum_paid
                FROM {self.schema}.mcca_clm clm
                WHERE clm.mcca_clm_num IS NOT NULL
                  AND clm.txn_id IN (
                      SELECT MAX(clm2.txn_id)
                      FROM {self.schema}.mcca_clm clm2
                      WHERE clm2.unique_id = clm.unique_id
                  )
                GROUP BY SUBSTR(TRIM(mcca_clm_num), 1, 8)
                HAVING COUNT(*) > 1
            )
            UPDATE {self.schema}.mcca_clm target
            SET tot_res_amt = ct.sum_res,
                cum_amt_paid_to_dt = ct.sum_paid,
                mdfd_dttm = CURRENT_TIMESTAMP,
                mdfd_user_id = 'BATCH'
            FROM companion_totals ct
            WHERE SUBSTR(TRIM(target.mcca_clm_num), 1, 8) = ct.base_mcca_num
              AND target.txn_id IN (
                  SELECT MAX(clm3.txn_id)
                  FROM {self.schema}.mcca_clm clm3
                  WHERE clm3.unique_id = target.unique_id
              )
              AND target.status IN ('IC', 'PN')
        """
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.rowcount

    # ==========================================================================
    # STEP 9b: updateRptdColumn (MccaClaimRptdProcessor & MccaClaimRptdWriter)
    # ==========================================================================
    def update_rptd_to_mcca_column(self) -> int:
        """
        Marks RPTD_TO_MCCA = 'Y' in MCCA_CLM_RPTD for all claims present in MCCA_CLM
        (Port of MccaClaimRptdProcessor + MccaClaimDaoImpl.getClaimCount + MccaClaimRptdWriter).
        """
        sql = f"""
            UPDATE {self.schema}.mcca_clm_rptd rptd
            SET rptd_to_mcca = 'Y',
                mdfd_dttm = CURRENT_TIMESTAMP
            WHERE COALESCE(rptd.rptd_to_mcca, 'N') <> 'Y'
              AND EXISTS (
                  SELECT 1
                  FROM {self.schema}.mcca_clm clm
                  WHERE clm.carrier_clm_num = rptd.carrier_clm_num
                    AND clm.carrier_clmt_num = rptd.carrier_clmt_num
              )
        """
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.rowcount

    # ==========================================================================
    # STEP 10: clearIcnTempTables (DBUtils.java)
    # ==========================================================================
    def clear_icn_temp_tables(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(f"DELETE FROM {self.schema}.mcca_tmp_clm")
            cur.execute(f"DELETE FROM {self.schema}.mcca_tmp_othr_inj_clmts_pymt")
            cur.execute(f"DELETE FROM {self.schema}.mcca_tmp_clm_dtls")
        self.conn.commit()
