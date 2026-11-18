"""
Step 7 of factsToMccaJob: Excel Report Generator & Email Sender.
Direct port of:
  - com.acg.mcca.batch.mail.RFRReportAttachedMailImpl
Generates:
  1. rfrProcessingReport.xlsx (Sheet: 'RFR Batch Processing Summary' - 12 columns + totals + SB/RJ/PN counts)
  2. missingDatesReport.xlsx (Sheet: 'Service Dates Missing Paylogs' - 11 columns)
"""

import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Any, Dict, List
import openpyxl
from openpyxl.styles import Font

logger = logging.getLogger(__name__)


class RFRReportAttachedMailImpl:
    """Port of com.acg.mcca.batch.mail.RFRReportAttachedMailImpl."""

    @staticmethod
    def generate_rfr_processing_report(
        batch_report: Dict[str, Dict[str, Any]], output_path: str
    ) -> str:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "RFR Batch Processing Summary"

        headers = [
            "Claim Number",
            "Claimant Number",
            "Claimant Name",
            "Pre Billed Amt",
            "Pre Bill Review Fee",
            "Pre Repriced Paid Amt",
            "Pre Total MCCA Payment Req",
            "Post Billed Amt",
            "Post Bill Review Fee",
            "Post Repriced Paid Amt",
            "Post Total MCCA Payment Req",
            "Status",
        ]
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)

        tot_pre_billed = 0.0
        tot_pre_fee = 0.0
        tot_pre_rep = 0.0
        tot_pre_req = 0.0
        tot_post_billed = 0.0
        tot_post_fee = 0.0
        tot_post_rep = 0.0
        tot_post_req = 0.0

        sb_count = 0
        rj_count = 0
        pn_count = 0

        for clm_num in sorted(batch_report.keys()):
            r = batch_report[clm_num]
            status = r.get("status") or ""
            if status == "SB":
                sb_count += 1
            elif status == "RJ":
                rj_count += 1
            elif status == "PN":
                pn_count += 1

            tot_pre_billed += float(r.get("pre_billed_amt") or 0.0)
            tot_pre_fee += float(r.get("pre_bill_review_fees") or 0.0)
            tot_pre_rep += float(r.get("pre_repriced_paid_amt") or 0.0)
            tot_pre_req += float(r.get("pre_total_mcca_pmt_req") or 0.0)
            tot_post_billed += float(r.get("post_billed_amt") or 0.0)
            tot_post_fee += float(r.get("post_bill_review_fees") or 0.0)
            tot_post_rep += float(r.get("post_repriced_paid_amt") or 0.0)
            tot_post_req += float(r.get("post_total_mcca_pmt_req") or 0.0)

            ws.append([
                r.get("claim_number"),
                r.get("claimant_number"),
                r.get("claimant_name"),
                round(float(r.get("pre_billed_amt") or 0.0), 2),
                round(float(r.get("pre_bill_review_fees") or 0.0), 2),
                round(float(r.get("pre_repriced_paid_amt") or 0.0), 2),
                round(float(r.get("pre_total_mcca_pmt_req") or 0.0), 2),
                round(float(r.get("post_billed_amt") or 0.0), 2),
                round(float(r.get("post_bill_review_fees") or 0.0), 2),
                round(float(r.get("post_repriced_paid_amt") or 0.0), 2),
                round(float(r.get("post_total_mcca_pmt_req") or 0.0), 2),
                status,
            ])

        # Total Row
        ws.append([
            "Total",
            "",
            "",
            round(tot_pre_billed, 2),
            round(tot_pre_fee, 2),
            round(tot_pre_rep, 2),
            round(tot_pre_req, 2),
            round(tot_post_billed, 2),
            round(tot_post_fee, 2),
            round(tot_post_rep, 2),
            round(tot_post_req, 2),
            "",
        ])
        ws.append([])
        ws.append(["Total Claims Count", len(batch_report)])
        ws.append(["Claims Submitted Count", sb_count])
        ws.append(["Claims Rejected Count", rj_count])
        ws.append(["Claims Pended Count", pn_count])

        wb.save(output_path)
        logger.info("Generated RFR Processing Report: %s", output_path)
        return output_path

    @staticmethod
    def generate_missing_dates_report(
        missing_dates_list: List[Dict[str, Any]], output_path: str
    ) -> str:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Service Dates Missing Paylogs"

        headers = [
            "Claim Number",
            "Claimant Number",
            "Claimant Name",
            "Pay Code",
            "Check Number",
            "Check Date",
            "Payee/Provider",
            "Billed Amt",
            "Bill Review Fee",
            "Repriced Paid Amt",
            "Total MCCA Payment Req",
        ]
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)

        for r in missing_dates_list:
            chk_dt = r.get("check_date")
            chk_dt_str = chk_dt.strftime("%Y-%m-%d") if hasattr(chk_dt, "strftime") else str(chk_dt or "")
            ws.append([
                r.get("claim_number"),
                r.get("claimant_number"),
                r.get("claimant_name"),
                r.get("pay_code"),
                r.get("check_number"),
                chk_dt_str,
                r.get("payee_or_provider"),
                round(float(r.get("billed_amt") or 0.0), 2),
                round(float(r.get("bill_review_fees") or 0.0), 2),
                round(float(r.get("repriced_paid_amt") or 0.0), 2),
                round(float(r.get("total_mcca_pmt_req") or 0.0), 2),
            ])

        wb.save(output_path)
        logger.info("Generated Missing Dates Report: %s", output_path)
        return output_path

    @classmethod
    def send_reports_email(
        cls,
        batch_report: Dict[str, Dict[str, Any]],
        missing_dates_list: List[Dict[str, Any]],
        output_dir: str = ".",
    ) -> None:
        os.makedirs(output_dir, exist_ok=True)
        rfr_report_path = os.path.join(output_dir, "rfrProcessingReport.xlsx")
        missing_report_path = os.path.join(output_dir, "missingDatesReport.xlsx")

        cls.generate_rfr_processing_report(batch_report, rfr_report_path)
        cls.generate_missing_dates_report(missing_dates_list, missing_report_path)

        smtp_host = os.getenv("SMTP_HOST", "")
        if not smtp_host:
            logger.info(
                "SMTP_HOST not set; Excel reports saved locally at '%s' and '%s'.",
                rfr_report_path,
                missing_report_path,
            )
            return

        msg = EmailMessage()
        msg["From"] = os.getenv("FACTS_RFR_MAIL_FROM", "mcca-batch@acg.aaa.com")
        msg["To"] = os.getenv("FACTS_RFR_MAIL_TO", "mcca-support@acg.aaa.com")
        msg["Subject"] = os.getenv(
            "FACTS_RFR_MAIL_SUBJECT", "FACTS RFR Monthly Batch Processing Reports"
        )
        msg.set_content(
            os.getenv(
                "FACTS_RFR_MAIL_BODY",
                "Please find attached the FACTS RFR Batch Processing Summary and Missing Service Dates reports.",
            )
        )

        for path in (rfr_report_path, missing_report_path):
            with open(path, "rb") as f:
                msg.add_attachment(
                    f.read(),
                    maintype="application",
                    subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    filename=os.path.basename(path),
                )

        with smtplib.SMTP(smtp_host, int(os.getenv("SMTP_PORT", "25"))) as server:
            server.send_message(msg)
        logger.info("Sent FACTS RFR report email with attachments.")
