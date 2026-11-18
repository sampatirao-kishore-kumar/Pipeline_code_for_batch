"""
AlloyDB / PostgreSQL Data Access Layer for Job 3: factsToMccaJob.
Direct port of:
  - RFRFactsPayLogPreRowMapper.java (Step 2)
  - MissingDatesBatchReportMapper.java (Step 3)
  - RfrJdbcDaoImpl.java (getAutoBillingException, isPreviousRfrSubmitted, updateLastBillingDate)
  - RfrPaylogJdbcDaoImpl.java (getRfrDetailsListByClaimNum, getRfrDetailCptListByClaimNum)
  - CsrJdbcDaoImpl.java (insertRemarks for 'RFR Fall Below')
  - RFRWriter.java, RFRPayLogWriter.java, RFRPayLogCptWriter.java
  - RFRFactsPayLogPostRowMapper.java (Step 6)
  - DBUtils.java (clearTempTables - Step 8)
"""

from typing import Any, Dict, List
import psycopg2.extras


class FactsRfrDao:
    """Handles all AlloyDB operations for factsToMccaJob."""

    def __init__(self, conn, schema: str = "mcca") -> None:
        self.conn = conn
        self.schema = schema

    def fetch_preload_batch_report(self) -> Dict[str, Dict[str, Any]]:
        """Step 2: Port of rfrFactsPaylogJdbcPreReader & RFRFactsPayLogPreRowMapper.java."""
        sql = f"""
            SELECT
                carrier_clm_num,
                carrier_clmt_num,
                fst_name,
                lst_name,
                midl_int,
                SUM(billed_amt) AS billed_amt,
                SUM(bill_review_fees) AS bill_review_fees,
                SUM(rep_paid_amt) AS rep_paid_amt,
                SUM(tot_mcca_pmt_req) AS tot_mcca_pmt_req
            FROM {self.schema}.mcca_fac_tmp_rfr_paylog
            GROUP BY carrier_clm_num, carrier_clmt_num, fst_name, lst_name, midl_int
            ORDER BY carrier_clm_num
        """
        batch_report: Dict[str, Dict[str, Any]] = {}
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            for row in cur.fetchall():
                lst = (row.get("lst_name") or "").strip()
                fst = (row.get("fst_name") or "").strip()
                mid = (row.get("midl_int") or "").strip()
                name_parts = [p for p in (lst, fst, mid) if p]
                clmt_name = " ".join(name_parts)
                clm_num = str(row["carrier_clm_num"]).strip()
                batch_report[clm_num] = {
                    "claim_number": clm_num,
                    "claimant_number": int(row.get("carrier_clmt_num") or 0),
                    "claimant_name": clmt_name,
                    "pre_billed_amt": float(row.get("billed_amt") or 0.0),
                    "pre_bill_review_fees": float(row.get("bill_review_fees") or 0.0),
                    "pre_repriced_paid_amt": float(row.get("rep_paid_amt") or 0.0),
                    "pre_total_mcca_pmt_req": float(row.get("tot_mcca_pmt_req") or 0.0),
                    "post_billed_amt": 0.0,
                    "post_bill_review_fees": 0.0,
                    "post_repriced_paid_amt": 0.0,
                    "post_total_mcca_pmt_req": 0.0,
                    "status": "",
                }
        return batch_report

    def fetch_missing_dates_report(self) -> List[Dict[str, Any]]:
        """Step 3: Port of rfrFactsPaylogJdbcMissingDatesReader & MissingDatesBatchReportMapper.java."""
        sql = f"""
            SELECT
                carrier_clm_num,
                carrier_clmt_num,
                fst_name,
                lst_name,
                midl_int,
                pay_cd,
                chk_num,
                chk_dt,
                payee_or_prvdr,
                billed_amt,
                bill_review_fees,
                rep_paid_amt,
                tot_mcca_pmt_req
            FROM {self.schema}.mcca_fac_tmp_rfr_paylog
            WHERE strt_date IS NULL OR end_dt IS NULL
        """
        missing_list: List[Dict[str, Any]] = []
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            for row in cur.fetchall():
                lst = (row.get("lst_name") or "").strip()
                fst = (row.get("fst_name") or "").strip()
                mid = (row.get("midl_int") or "").strip()
                clmt_name = " ".join(p for p in (lst, fst, mid) if p)
                missing_list.append({
                    "claim_number": str(row.get("carrier_clm_num") or "").strip(),
                    "claimant_number": int(row.get("carrier_clmt_num") or 0),
                    "claimant_name": clmt_name,
                    "pay_code": str(row.get("pay_cd") or "").strip(),
                    "check_number": str(row.get("chk_num") or "").strip(),
                    "check_date": row.get("chk_dt"),
                    "payee_or_provider": str(row.get("payee_or_prvdr") or "").strip(),
                    "billed_amt": float(row.get("billed_amt") or 0.0),
                    "bill_review_fees": float(row.get("bill_review_fees") or 0.0),
                    "repriced_paid_amt": float(row.get("rep_paid_amt") or 0.0),
                    "total_mcca_pmt_req": float(row.get("tot_mcca_pmt_req") or 0.0),
                })
        return missing_list

    def fetch_all_fac_tmp_headers(self) -> List[Dict[str, Any]]:
        """Step 4 Reader: Read all rows from MCCA_FAC_TMP_RFR (RFRRowMapper.java)."""
        sql = f"""
            SELECT
                txn_id, unique_id AS unique_key, rec_type AS record_type,
                carrier_id, carrier_clm_num AS carrier_claim_number,
                carrier_clmt_num AS carrier_claimant_number,
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
                err_ele_list AS status, clm_type AS claim_type,
                chng_rsn_desc AS change_reason_description,
                deductible_amt AS deductible_amount
            FROM {self.schema}.mcca_fac_tmp_rfr
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            return [dict(r) for r in cur.fetchall()]

    def get_auto_billing_exception(self, carrier_claim_number: str, carrier_claimant_number: int) -> bool:
        """Port of RfrJdbcDaoImpl.getAutoBillingException (EXCEPTION_CODE='3' AND EXCEPTION_VALUE='Y')."""
        sql = f"""
            SELECT COUNT(*)
            FROM {self.schema}.mcca_exception
            WHERE carrier_clm_num = %s
              AND carrier_clmt_num = %s
              AND exception_code = '3'
              AND exception_value = 'Y'
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (carrier_claim_number, carrier_claimant_number))
            return int(cur.fetchone()[0]) > 0

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

    def fetch_fac_tmp_paylogs_by_claim(self, carrier_claim_number: str) -> List[Dict[str, Any]]:
        """Port of RfrPaylogJdbcDaoImpl.getRfrDetailsListByClaimNum."""
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
            FROM {self.schema}.mcca_fac_tmp_rfr_paylog
            WHERE carrier_clm_num = %s
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (carrier_claim_number,))
            return [dict(r) for r in cur.fetchall()]

    def fetch_fac_tmp_cpts_by_claim_and_paylog(
        self, carrier_claim_number: str, paylog_unique_id: int
    ) -> List[Dict[str, Any]]:
        """Port of RfrPaylogJdbcDaoImpl.getRfrDetailCptListByClaimNum."""
        sql = f"""
            SELECT
                rfr_paylog_cpt_seq_id, unique_id AS unique_key, carrier_clm_num AS carrier_claim_number,
                carrier_id, strt_date AS service_start_date, end_dt AS service_end_date,
                service_location, cpt_cd AS cpt_code, modifier1, modifier2, modifier3, modifier4,
                service_units, total_charges, total_charges_carrier_approved,
                revenue_cd AS revenue_code, prescriber_npi,
                icd1, icd2, icd3, icd4, icd5, icd6, icd7, icd8, icd9, icd10,
                eob_id, bill_type, eob_revision_num, carrier_paylog_id
            FROM {self.schema}.mcca_fac_tmp_rfr_paylog_cpt
            WHERE carrier_clm_num = %s AND carrier_paylog_id = %s
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (carrier_claim_number, paylog_unique_id))
            return [dict(r) for r in cur.fetchall()]

    def update_last_billing_date(
        self, carrier_claim_number: str, carrier_claimant_number: int, fall_below: bool
    ) -> None:
        """Port of RfrJdbcDaoImpl.updateLastBillingDate."""
        with self.conn.cursor() as cur:
            if fall_below:
                cur.execute(
                    f"""
                    UPDATE {self.schema}.mcca_last_bill_date
                    SET last_bill_dt = CURRENT_TIMESTAMP,
                        mdfd_dttm = CURRENT_TIMESTAMP,
                        fall_back_ind = 'Y'
                    WHERE carrier_clm_num = %s AND carrier_clmt_num = %s
                    """,
                    (carrier_claim_number, carrier_claimant_number),
                )
            else:
                cur.execute(
                    f"""
                    UPDATE {self.schema}.mcca_last_bill_date
                    SET last_bill_dt = CURRENT_TIMESTAMP,
                        mdfd_dttm = CURRENT_TIMESTAMP
                    WHERE carrier_clm_num = %s AND carrier_clmt_num = %s
                    """,
                    (carrier_claim_number, carrier_claimant_number),
                )

    def insert_remarks(self, unique_id: str, remark_text: str) -> None:
        """Port of CsrJdbcDaoImpl.insertRemarks ('RFR Fall Below')."""
        sql = f"""
            INSERT INTO {self.schema}.mcca_remarks (
                remark_seq_num, unique_id, remarks, crt_dttm, crt_user_id, mdfd_dttm, mdfd_user_id
            ) VALUES (
                nextval('{self.schema}.mcca_remark_seq'),
                %s, %s, CURRENT_TIMESTAMP, 'BATCH', CURRENT_TIMESTAMP, 'BATCH'
            )
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (unique_id, remark_text))

    def insert_main_rfr_paylog(self, detail: Dict[str, Any]) -> None:
        """Port of RFRPayLogWriter -> MCCA_RFR_PAYLOG."""
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

    def insert_main_rfr_header(self, rfr: Dict[str, Any]) -> None:
        """Port of RFRWriter -> MCCA_RFR."""
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

    def copy_fac_tmp_cpts_to_main(self, date_suffix: str) -> int:
        """Step 5: Port of RfrFactsDetailCptProcessor & RFRPayLogCptWriter."""
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
                TRIM(carrier_clm_num) || %s,
                carrier_clm_num, carrier_id, strt_date, end_dt,
                service_location, cpt_cd, modifier1, modifier2, modifier3, modifier4,
                service_units, total_charges, total_charges_carrier_approved, revenue_cd,
                prescriber_npi, icd1, icd2, icd3, icd4, icd5, icd6, icd7, icd8, icd9, icd10,
                eob_id, bill_type, eob_revision_num, carrier_paylog_id,
                CURRENT_TIMESTAMP, 'BATCH', CURRENT_TIMESTAMP, 'BATCH'
            FROM {self.schema}.mcca_fac_tmp_rfr_paylog_cpt
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (date_suffix,))
            return cur.rowcount

    def update_postload_batch_report(self, batch_report: Dict[str, Dict[str, Any]]) -> None:
        """Step 6: Port of rfrFactsPaylogJdbcPostReader, RFRFactsPayLogPostRowMapper & RfrFactsPaylogPostProcessor."""
        sql = f"""
            SELECT
                rfr.carrier_clm_num,
                rfr.status,
                rfr.submit_err_msg,
                SUM(paylog.billed_amt) AS billed_amt,
                SUM(paylog.bill_review_fees) AS bill_review_fees,
                SUM(paylog.rep_paid_amt) AS rep_paid_amt,
                SUM(paylog.tot_mcca_pmt_req) AS tot_mcca_pmt_req
            FROM {self.schema}.mcca_rfr rfr,
                 {self.schema}.mcca_rfr_paylog paylog,
                 {self.schema}.mcca_fac_tmp_rfr tmprfr
            WHERE rfr.unique_id = paylog.unique_id
              AND rfr.carrier_clm_num = tmprfr.carrier_clm_num
              AND rfr.txn_id IN (
                  SELECT MAX(rfr2.txn_id)
                  FROM {self.schema}.mcca_rfr rfr2
                  WHERE rfr2.unique_id = rfr.unique_id
              )
            GROUP BY rfr.carrier_clm_num, rfr.status, rfr.submit_err_msg
            ORDER BY rfr.carrier_clm_num
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            for row in cur.fetchall():
                clm_num = str(row["carrier_clm_num"]).strip()
                status = str(row.get("status") or "").strip()
                submit_err = row.get("submit_err_msg")
                # Exact rule in RFRFactsPayLogPostRowMapper.java:
                # if (rs.getString("SUBMIT_ERR_MSG") != null && !rs.getString("SUBMIT_ERR_MSG").isEmpty()) -> "RJ"
                if submit_err is not None and str(submit_err).strip() != "":
                    status = "RJ"

                if clm_num in batch_report:
                    entry = batch_report[clm_num]
                    entry["post_billed_amt"] = float(row.get("billed_amt") or 0.0)
                    entry["post_bill_review_fees"] = float(row.get("bill_review_fees") or 0.0)
                    entry["post_repriced_paid_amt"] = float(row.get("rep_paid_amt") or 0.0)
                    entry["post_total_mcca_pmt_req"] = float(row.get("tot_mcca_pmt_req") or 0.0)
                    entry["status"] = status

    def clear_fac_temp_tables(self) -> None:
        """Step 8: Clear MCCA_FAC_TMP_RFR* tables (DBUtils.java)."""
        with self.conn.cursor() as cur:
            cur.execute(f"DELETE FROM {self.schema}.mcca_fac_tmp_rfr_paylog_cpt")
            cur.execute(f"DELETE FROM {self.schema}.mcca_fac_tmp_rfr_paylog")
            cur.execute(f"DELETE FROM {self.schema}.mcca_fac_tmp_rfr")
        self.conn.commit()
