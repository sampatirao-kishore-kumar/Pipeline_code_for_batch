"""
Job 5: mccaWriteOffFlatFileJob — Month-End MCCA Write-Off Flat File Export Job.
Direct port of:
  - jobs/mccaWriteOffFlatFileJob.xml (<batch:job id="mccaWriteOffFlatFileJob">)
  - common/writeOffFlatFileBeanInfo.xml (writeOffJdbcCursorReader & writeOffFlatFileItemWriter)
  - com.acg.mcca.batch.mapper.WriteOffFlatFileMapper
  - com.acg.mcca.batch.dto.WriteOff
  - com.acg.mcca.batch.mail.MailImpl
"""

import argparse
import logging
import os
import smtplib
from decimal import Decimal, ROUND_HALF_UP
from email.message import EmailMessage
from typing import Any, Dict, List
import psycopg2
import psycopg2.extras

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("mccaWriteOffFlatFileJob")


def format_write_off_row(row: Dict[str, Any]) -> Dict[str, str]:
    """
    Exact port of com.acg.mcca.batch.mapper.WriteOffFlatFileMapper.mapRow.
    - claimNumber: right-padded with spaces to 9 chars (or truncated to 9 chars)
    - coverageType: trimmed string
    - amount: rounded to 2 decimals, multiplied by 100 (cents), zero-padded to 11 chars
              (if negative: '-' + 10 zero-padded digits, total 11 chars)
    - writeOffType: trimmed string
    - userId: right-padded with spaces to 5 chars (or truncated to 5 chars)
    - submittedDate: MMYYYY string
    """
    raw_claim = str(row.get("carrier_clm_num") or "").strip()
    if len(raw_claim) <= 9:
        claim_number = f"{raw_claim:<9}"
    else:
        claim_number = raw_claim[:9]

    coverage_type = str(row.get("coverage_type") or "").strip()
    write_off_type = str(row.get("write_off_type") or "").strip()

    raw_amt = row.get("write_off_amount")
    if raw_amt is None:
        d_amt = Decimal("0.00")
    else:
        d_amt = Decimal(str(raw_amt)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    cents = int((d_amt * 100).to_integral_value(rounding=ROUND_HALF_UP))
    if cents >= 0:
        amount_str = f"{cents:011d}"
    else:
        amount_str = f"-{abs(cents):010d}"

    raw_user = str(row.get("submitted_by") or "").strip()
    if len(raw_user) <= 5:
        user_id = f"{raw_user:<5}"
    else:
        user_id = raw_user[:5]

    submitted_date = str(row.get("submitted_date") or "").strip()

    return {
        "claimNumber": claim_number,
        "coverageType": coverage_type,
        "amount": amount_str,
        "writeOffType": write_off_type,
        "userId": user_id,
        "submittedDate": submitted_date,
    }


def send_write_off_email() -> None:
    """Port of MailImpl.java (writeOffMailStep)."""
    smtp_host = os.getenv("SMTP_HOST", "")
    if not smtp_host:
        logger.info("SMTP_HOST not set; skipping writeOffMailStep email send.")
        return
    msg = EmailMessage()
    msg["From"] = os.getenv("WRITEOFF_MAIL_FROM", "mcca-batch@acg.aaa.com")
    msg["To"] = os.getenv("WRITEOFF_MAIL_TO", "mcca-support@acg.aaa.com")
    msg["Subject"] = os.getenv("WRITEOFF_MAIL_SUBJECT", "MCCA Write-Off Flat File Export Completed")
    msg.set_content(
        os.getenv("WRITEOFF_MAIL_BODY", "MCCA Write-Off Month-End Flat File Export completed.")
    )
    with smtplib.SMTP(smtp_host, int(os.getenv("SMTP_PORT", "25"))) as server:
        server.send_message(msg)


def run_mcca_write_off_flat_file_job(
    conn,
    batch_date: str,
    output_dir: str,
    schema: str = "mcca",
) -> str:
    """
    Executes Step 1 (createFlatFileStep) and Step 2 (writeOffMailStep).
    Returns the generated flat file path.
    """
    if len(batch_date) < 6:
        raise ValueError(f"batchDate must be at least 6 characters (YYYYMM or YYYYMMDD), got '{batch_date}'")

    year_month = batch_date[:6]
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"MCCAWriteOffExport_{batch_date}.txt")

    # ==========================================================================
    # STEP 1: createFlatFileStep (writeOffJdbcCursorReader & writeOffFlatFileItemWriter)
    # ==========================================================================
    sql = f"""
        SELECT
            carrier_clm_num,
            coverage_type,
            write_off_amount,
            write_off_type,
            submitted_by,
            TO_CHAR(submitted_date, 'MMYYYY') AS submitted_date
        FROM {schema}.mcca_write_off
        WHERE TO_CHAR(submitted_date, 'YYYYMM') = %s
        ORDER BY write_off_seq_id
    """
    logger.info(
        "Step 1: Querying %s.mcca_write_off for YYYYMM='%s' (batchDate='%s')...",
        schema,
        year_month,
        batch_date,
    )
    rows_written = 0
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (year_month,))
        rows: List[Dict[str, Any]] = [dict(r) for r in cur.fetchall()]

    with open(output_file, mode="w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            dto = format_write_off_row(row)
            # BeanWrapperFieldExtractor extracts: claimNumber,coverageType,amount,writeOffType
            line = f"{dto['claimNumber']},{dto['coverageType']},{dto['amount']},{dto['writeOffType']}\n"
            f.write(line)
            rows_written += 1

    logger.info("Step 1 completed: Wrote %d write-off records to '%s'.", rows_written, output_file)

    # ==========================================================================
    # STEP 2: writeOffMailStep (MailImpl.java)
    # ==========================================================================
    logger.info("Step 2: Sending writeOffMailStep notification...")
    send_write_off_email()
    logger.info("mccaWriteOffFlatFileJob completed successfully.")
    return output_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Job 5: mccaWriteOffFlatFileJob (MCCA Write-Off Flat File Export Job)"
    )
    parser.add_argument(
        "--batch-date",
        required=True,
        help="Batch date parameter in YYYYMMDD format (e.g., 20261128)",
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("WRITEOFF_FLATFILE_PATH", "./output"),
        help="Output directory for MCCAWriteOffExport_<batchDate>.txt",
    )
    parser.add_argument("--schema", default=os.getenv("DB_SCHEMA", "mcca"))
    args = parser.parse_args()

    conn = psycopg2.connect(
        host=os.getenv("ALLOYDB_HOST", "localhost"),
        port=int(os.getenv("ALLOYDB_PORT", "5432")),
        dbname=os.getenv("ALLOYDB_DB", "mcca"),
        user=os.getenv("ALLOYDB_USER", "postgres"),
        password=os.getenv("ALLOYDB_PASSWORD", ""),
    )
    try:
        run_mcca_write_off_flat_file_job(
            conn=conn,
            batch_date=args.batch_date,
            output_dir=args.output_dir,
            schema=args.schema,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
