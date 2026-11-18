"""
AlloyDB / PostgreSQL Data Access Layer for Job 2: meemicToMccaJob.
Direct port of:
  - com.acg.mcca.batch.util.DBUtils (clearMeemicTempTables*)
  - com.acg.mcca.batch.dao.impl.RfrJdbcDaoImpl
  - com.acg.mcca.batch.dao.impl.RfrPaylogJdbcDaoImpl
  - com.acg.mcca.batch.writer.RFRWriter
  - com.acg.mcca.batch.writer.RFRPayLogWriter
  - com.acg.mcca.batch.writer.RFRPayLogCptWriter
  - com.acg.mcca.batch.mail.MeemicMailImpl
"""

from typing import Any, Dict, List, Tuple
import psycopg2.extras


class MeemicRfrDao:
    """Handles all AlloyDB staging and target table operations for meemicToMccaJob."""

    def __init__(self, conn, schema: str = "mcca") -> None:
        self.conn = conn
        self.schema = schema

    def clear_meemic_temp_tables(self) -> None:
        """Step 1 & Step 10: Clear MCCA_MEEMIC_TMP_RFR* tables (DBUtils.java)."""
        with self.conn.cursor() as cur:
            cur.execute(f"DELETE FROM {self.schema}.mcca_meemic_tmp_rfr_paylog_cpt")
            cur.execute(f"DELETE FROM {self.schema}.mcca_meemic_tmp_rfr_paylog")
            cur.execute(f"DELETE FROM {self.schema}.mcca_meemic_tmp_rfr")
        self.conn.commit()

    def get_next_paylog_unique_id(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT nextval('{self.schema}.mcca_paylog_id_seq')")
            return int(cur.fetchone()[0])

    def insert_tmp_rfr_header(self, rfr: Dict[str, Any]) -> None:
        """Step 2: Insert header into MCCA_MEEMIC_TMP_RFR (RFRWriter.java)."""
        sql = f"""
            INSERT INTO {self.schema}.mcca_meemic_tmp_rfr (
                txn_id, unique_id, rec_type, carrier_id, carrier_clm_num, mcca_clm_num,
                bill_seq_num, ins_fst_name, ins_midl_init, ins_lst_name, adj_name, loss_dt,
                clmt_fst_name, clmt_midl_init, clmt_lst_name, tot_amt_billed, tot_bill_rview_fees,
                tot_mcca_pmt_req, x_companion_clm_ind, x_companion_clm_num, crt_dttm, crt_user_id,
                mdfd_dttm, mdfd_user_id, trans_sent_dt, status, err_ele_list, clm_type, deductible_amt
            ) VALUES (
                nextval('{self.schema}.mcca_rfr_txn_id_seq'),
                %(unique_key)s, %(record_type)s, %(carrier_id)s, %(carrier_claim_number)s, %(mcca_claim_number)s,
                %(bill_sequence_number)s, %(insured_first_name)s, %(insured_middle_init)s, %(insured_last_name)s,
                %(adjuster_name)s, %(date_of_loss)s,
                %(claimant_first_name)s, %(claimant_middle_init)s, %(claimant_last_name)s,
                %(total_amt_billed)s, %(total_bill_review_fees)s,
                %(total_mcca_payment_req)s, %(cross_companion_indicator)s, %(cross_companion_claim_number)s,
                CURRENT_TIMESTAMP, 'BATCH', CURRENT_TIMESTAMP, 'BATCH',
                %(transaction_sent_date)s, %(status_indicator)s, %(status)s, %(claim_type)s, %(deductible_amount)s
            )
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, rfr)

    def insert_tmp_rfr_paylog(self, detail: Dict[str, Any]) -> None:
        """Step 3: Insert BIL* line into MCCA_MEEMIC_TMP_RFR_PAYLOG (RFRPayLogWriter.java)."""
        sql = f"""
            INSERT INTO {self.schema}.mcca_meemic_tmp_rfr_paylog (
                rfr_paylog_seq_id, unique_id, carrier_clm_num, carrier_id, strt_date, end_dt,
                pay_cd, num_hours, chk_num, chk_dt, payee_or_prvdr, fed_tin, cost_share_amt,
                rep_paid_amt, bill_review_fees, ppo_fees, tot_mcca_pmt_req, corrections_ind,
                crt_dttm, crt_user_id, mdfd_dttm, mdfd_user_id, billed_amt,
                ppo_or_othr_negotiated_disc, srvc_desc, carrier_check_total, clm_type,
                rx_ind, ndc_number, days_supply, quantity, dispense_has_written_cd,
                prescriber_npi, drg_cd, patient_status, admit_dt, discharge_dt,
                ub_bill_type, service_facility_zip_cd, admission_source,
                icd1, icd2, icd3, icd4, icd5, icd6, icd7,
                eob_id, bill_type, eob_revision_num, paylog_unique_id, admission_type
            ) VALUES (
                nextval('{self.schema}.mcca_rfr_paylog_id_seq'),
                %(unique_key)s, %(carrier_claim_number)s, %(carrier_id)s,
                %(service_start_date)s, %(service_end_date)s,
                %(pay_code)s, %(number_of_hours)s, %(check_number)s, %(check_date)s,
                %(payee_or_provider)s, %(federal_tin)s, %(cost_share_amount)s,
                %(repriced_paid_amt)s, %(bill_review_fees)s, %(ppo_fees)s,
                %(total_mcca_payment_req)s, %(corrections_indicator)s,
                CURRENT_TIMESTAMP, 'BATCH', CURRENT_TIMESTAMP, 'BATCH', %(bill_amount)s,
                %(ppo_or_other_negotiated_discount)s, %(service_description)s,
                %(carrier_check_total)s, %(claim_type)s,
                %(rx_indicator)s, %(ndc_number)s, %(days_supply)s, %(quantity)s,
                %(dispense_as_written_code)s,
                %(prescriber_npi)s, %(drg_code)s, %(patient_status)s, %(admit_date)s, %(discharge_date)s,
                %(ub_bill_type)s, %(service_facility_zipcode)s, %(admission_source)s,
                %(icd1)s, %(icd2)s, %(icd3)s, %(icd4)s, %(icd5)s, %(icd6)s, %(icd7)s,
                %(eob_id)s, %(bill_type)s, %(eob_revision_num)s, %(paylog_unique_id)s, %(admission_type)s
            )
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, detail)

    def insert_tmp_rfr_paylog_cpt(self, cpt: Dict[str, Any]) -> None:
        """Step 4: Insert CPT* line into MCCA_MEEMIC_TMP_RFR_PAYLOG_CPT (RFRPayLogCptWriter.java)."""
        sql = f"""
            INSERT INTO {self.schema}.mcca_meemic_tmp_rfr_paylog_cpt (
                rfr_paylog_cpt_seq_id, unique_id, carrier_clm_num, carrier_id, strt_date, end_dt,
                service_location, cpt_cd, modifier1, modifier2, modifier3, modifier4,
                service_units, total_charges, total_charges_carrier_approved, revenue_cd,
                prescriber_npi, icd1, icd2, icd3, icd4, icd5, icd6, icd7, icd8, icd9, icd10,
                eob_id, bill_type, eob_revision_num, carrier_paylog_id,
                crt_dttm, crt_user_id, mdfd_dttm, mdfd_user_id
            ) VALUES (
                nextval('{self.schema}.mcca_rfr_paylog_cpt_id_seq'),
                %(unique_key)s, %(carrier_claim_number)s, %(carrier_id)s,
                %(service_start_date)s, %(service_end_date)s,
                %(service_location)s, %(cpt_code)s, %(modifier1)s, %(modifier2)s, %(modifier3)s, %(modifier4)s,
                %(service_units)s, %(total_charges)s, %(total_charges_carrier_approved)s, %(revenue_code)s,
                %(prescriber_npi)s,
                %(icd1)s, %(icd2)s, %(icd3)s, %(icd4)s, %(icd5)s,
                %(icd6)s, %(icd7)s, %(icd8)s, %(icd9)s, %(icd10)s,
                %(eob_id)s, %(bill_type)s, %(eob_revision_num)s, %(carrier_paylog_id)s,
                CURRENT_TIMESTAMP, 'BATCH', CURRENT_TIMESTAMP, 'BATCH'
            )
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, cpt)

    def fetch_validation_keys(self) -> Tuple[List[str], List[Tuple[str, int]], List[Tuple[str, int]]]:
        """Step 5: Fetch UNIQUE_ID and PAYLOG_UNIQUE_ID keys for FileValidator."""
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT unique_id FROM {self.schema}.mcca_meemic_tmp_rfr")
            headers = [r[0] for r in cur.fetchall()]

            cur.execute(f"SELECT unique_id, paylog_unique_id FROM {self.schema}.mcca_meemic_tmp_rfr_paylog")
            details = [(r[0], int(r[1])) for r in cur.fetchall()]

            cur.execute(f"SELECT unique_id, carrier_paylog_id FROM {self.schema}.mcca_meemic_tmp_rfr_paylog_cpt")
            cpts = [(r[0], int(r[1])) for r in cur.fetchall()]

        return headers, details, cpts

    def is_previous_rfr_submitted(self, carrier_claim_number: str) -> bool:
        sql = f"""
            SELECT COUNT(*)
            FROM {self.schema}.mcca_rfr rfr
            WHERE rfr.carrier_clm_num = %s
              AND rfr.txn_id IN (
                  SELECT MAX(rfr2.txn_id)
                  FROM {self.schema}.mcca_rfr rfr2
                  WHERE rfr2.unique_id = rfr.unique_id
              )
              AND rfr.status = 'PN'
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (carrier_claim_number,))
            return int(cur.fetchone()[0]) > 0

    def fetch_all_tmp_headers(self) -> List[Dict[str, Any]]:
        sql = f"""
            SELECT
                txn_id, unique_id AS unique_key, rec_type AS record_type,
                carrier_id, carrier_clm_num AS carrier_claim_number,
                mcca_clm_num AS mcca_claim_number, bill_seq_num AS bill_sequence_number,
                ins_fst_name AS insured_first_name, ins_midl_init AS insured_middle_init,
                ins_lst_name AS insured_last_name, adj_name AS adjuster_name,
                loss_dt AS date_of_loss, clmt_fst_name AS claimant_first_name,
                clmt_midl_init AS claimant_middle_init, clmt_lst_name AS claimant_last_name,
                tot_amt_billed AS total_amt_billed, tot_bill_rview_fees AS total_bill_review_fees,
                tot_mcca_pmt_req AS total_mcca_payment_req,
                x_companion_clm_ind AS cross_companion_indicator,
                x_companion_clm_num AS cross_companion_claim_number,
                trans_sent_dt AS transaction_sent_date, status AS status_indicator,
                err_ele_list AS status, clm_type AS claim_type, deductible_amt AS deductible_amount
            FROM {self.schema}.mcca_meemic_tmp_rfr
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            return [dict(r) for r in cur.fetchall()]

    def fetch_tmp_paylogs_by_unique_key(self, unique_key: str) -> List[Dict[str, Any]]:
        sql = f"""
            SELECT
                rfr_paylog_seq_id, unique_id AS unique_key, carrier_clm_num AS carrier_claim_number,
                carrier_id, strt_date AS service_start_date, end_dt AS service_end_date,
                pay_cd AS pay_code, num_hours AS number_of_hours, chk_num AS check_number,
                chk_dt AS check_date, payee_or_prvdr AS payee_or_provider, fed_tin AS federal_tin,
                cost_share_amt AS cost_share_amount, rep_paid_amt AS repriced_paid_amt,
                bill_review_fees, ppo_fees, tot_mcca_pmt_req AS total_mcca_payment_req,
                corrections_ind AS corrections_indicator, billed_amt AS bill_amount,
                ppo_or_othr_negotiated_disc AS ppo_or_other_negotiated_discount,
                srvc_desc AS service_description, carrier_check_total, clm_type AS claim_type,
                rx_ind AS rx_indicator, ndc_number, days_supply, quantity,
                dispense_has_written_cd AS dispense_as_written_code, prescriber_npi,
                drg_cd AS drg_code, patient_status, admit_dt AS admit_date,
                discharge_dt AS discharge_date, ub_bill_type,
                service_facility_zip_cd AS service_facility_zipcode, admission_source,
                icd1, icd2, icd3, icd4, icd5, icd6, icd7,
                eob_id, bill_type, eob_revision_num, paylog_unique_id, admission_type
            FROM {self.schema}.mcca_meemic_tmp_rfr_paylog
            WHERE unique_id = %s
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (unique_key,))
            return [dict(r) for r in cur.fetchall()]

    def fetch_tmp_cpts_by_paylog(self, unique_key: str, paylog_unique_id: int) -> List[Dict[str, Any]]:
        sql = f"""
            SELECT
                rfr_paylog_cpt_seq_id, unique_id AS unique_key, carrier_clm_num AS carrier_claim_number,
                carrier_id, strt_date AS service_start_date, end_dt AS service_end_date,
                service_location, cpt_cd AS cpt_code, modifier1, modifier2, modifier3, modifier4,
                service_units, total_charges, total_charges_carrier_approved,
                revenue_cd AS revenue_code, prescriber_npi,
                icd1, icd2, icd3, icd4, icd5, icd6, icd7, icd8, icd9, icd10,
                eob_id, bill_type, eob_revision_num, carrier_paylog_id
            FROM {self.schema}.mcca_meemic_tmp_rfr_paylog_cpt
            WHERE unique_id = %s AND carrier_paylog_id = %s
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (unique_key, paylog_unique_id))
            return [dict(r) for r in cur.fetchall()]

    def update_tmp_paylog_correction(self, detail: Dict[str, Any]) -> None:
        sql = f"""
            UPDATE {self.schema}.mcca_meemic_tmp_rfr_paylog
            SET corrections_ind = %s
            WHERE rfr_paylog_seq_id = %s
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (detail["corrections_indicator"], detail["rfr_paylog_seq_id"]))

    def insert_main_rfr_header(self, rfr: Dict[str, Any]) -> None:
        sql = f"""
            INSERT INTO {self.schema}.mcca_rfr (
                txn_id, unique_id, rec_type, carrier_id, carrier_clm_num, mcca_clm_num,
                bill_seq_num, ins_fst_name, ins_midl_init, ins_lst_name, adj_name, loss_dt,
                clmt_fst_name, clmt_midl_init, clmt_lst_name, tot_amt_billed, tot_bill_rview_fees,
                tot_mcca_pmt_req, x_companion_clm_ind, x_companion_clm_num, crt_dttm, crt_user_id,
                mdfd_dttm, mdfd_user_id, trans_sent_dt, status, err_ele_list, clm_type,
                submit_err_msg, deductible_amt
            ) VALUES (
                nextval('{self.schema}.mcca_rfr_txn_id_seq'),
                %(unique_key)s, %(record_type)s, %(carrier_id)s, %(carrier_claim_number)s, %(mcca_claim_number)s,
                %(bill_sequence_number)s, %(insured_first_name)s, %(insured_middle_init)s, %(insured_last_name)s,
                %(adjuster_name)s, %(date_of_loss)s,
                %(claimant_first_name)s, %(claimant_middle_init)s, %(claimant_last_name)s,
                %(total_amt_billed)s, %(total_bill_review_fees)s,
                %(total_mcca_payment_req)s, %(cross_companion_indicator)s, %(cross_companion_claim_number)s,
                CURRENT_TIMESTAMP, 'BATCH', CURRENT_TIMESTAMP, 'BATCH',
                %(transaction_sent_date)s, %(status_indicator)s, %(status)s, %(claim_type)s,
                %(submit_err_msg)s, %(deductible_amount)s
            )
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, rfr)

    def copy_tmp_paylogs_to_main(self) -> int:
        sql = f"""
            INSERT INTO {self.schema}.mcca_rfr_paylog (
                rfr_paylog_seq_id, unique_id, carrier_clm_num, carrier_id, strt_date, end_dt,
                pay_cd, num_hours, chk_num, chk_dt, payee_or_prvdr, fed_tin, cost_share_amt,
                rep_paid_amt, bill_review_fees, ppo_fees, tot_mcca_pmt_req, corrections_ind,
                crt_dttm, crt_user_id, mdfd_dttm, mdfd_user_id, billed_amt,
                ppo_or_othr_negotiated_disc, srvc_desc, carrier_check_total, clm_type,
                rx_ind, ndc_number, days_supply, quantity, dispense_has_written_cd,
                prescriber_npi, drg_cd, patient_status, admit_dt, discharge_dt,
                ub_bill_type, service_facility_zip_cd, admission_source,
                icd1, icd2, icd3, icd4, icd5, icd6, icd7,
                eob_id, bill_type, eob_revision_num, paylog_unique_id, admission_type
            )
            SELECT
                nextval('{self.schema}.mcca_rfr_paylog_id_seq'),
                unique_id, carrier_clm_num, carrier_id, strt_date, end_dt,
                pay_cd, num_hours, chk_num, chk_dt, payee_or_prvdr, fed_tin, cost_share_amt,
                rep_paid_amt, bill_review_fees, ppo_fees, tot_mcca_pmt_req, corrections_ind,
                CURRENT_TIMESTAMP, 'BATCH', CURRENT_TIMESTAMP, 'BATCH', billed_amt,
                ppo_or_othr_negotiated_disc, srvc_desc, carrier_check_total, clm_type,
                rx_ind, ndc_number, days_supply, quantity, dispense_has_written_cd,
                prescriber_npi, drg_cd, patient_status, admit_dt, discharge_dt,
                ub_bill_type, service_facility_zip_cd, admission_source,
                icd1, icd2, icd3, icd4, icd5, icd6, icd7,
                eob_id, bill_type, eob_revision_num, paylog_unique_id, admission_type
            FROM {self.schema}.mcca_meemic_tmp_rfr_paylog
        """
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.rowcount

    def copy_tmp_cpts_to_main(self) -> int:
        sql = f"""
            INSERT INTO {self.schema}.mcca_rfr_paylog_cpt (
                rfr_paylog_cpt_seq_id, unique_id, carrier_clm_num, carrier_id, strt_date, end_dt,
                service_location, cpt_cd, modifier1, modifier2, modifier3, modifier4,
                service_units, total_charges, total_charges_carrier_approved, revenue_cd,
                prescriber_npi, icd1, icd2, icd3, icd4, icd5, icd6, icd7, icd8, icd9, icd10,
                eob_id, bill_type, eob_revision_num, carrier_paylog_id,
                crt_dttm, crt_user_id, mdfd_dttm, mdfd_user_id
            )
            SELECT
                nextval('{self.schema}.mcca_rfr_paylog_cpt_id_seq'),
                unique_id, carrier_clm_num, carrier_id, strt_date, end_dt,
                service_location, cpt_cd, modifier1, modifier2, modifier3, modifier4,
                service_units, total_charges, total_charges_carrier_approved, revenue_cd,
                prescriber_npi, icd1, icd2, icd3, icd4, icd5, icd6, icd7, icd8, icd9, icd10,
                eob_id, bill_type, eob_revision_num, carrier_paylog_id,
                CURRENT_TIMESTAMP, 'BATCH', CURRENT_TIMESTAMP, 'BATCH'
            FROM {self.schema}.mcca_meemic_tmp_rfr_paylog_cpt
        """
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.rowcount

    def get_meemic_record_counts(self) -> Tuple[int, int]:
        """Step 9: Port of MeemicMailImpl.java record count queries."""
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(1) FROM {self.schema}.mcca_meemic_tmp_rfr")
            header_cnt = int(cur.fetchone()[0])
            cur.execute(f"SELECT COUNT(1) FROM {self.schema}.mcca_meemic_tmp_rfr_paylog")
            paylog_cnt = int(cur.fetchone()[0])
        return header_cnt, paylog_cnt
