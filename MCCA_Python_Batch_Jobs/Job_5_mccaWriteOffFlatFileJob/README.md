# Job 5: `mccaWriteOffFlatFileJob` (Month-End MCCA Write-Off Flat File Export Job)

## Overview
Python modernization of the Spring Batch job `mccaWriteOffFlatFileJob` (`jobs/mccaWriteOffFlatFileJob.xml` & `common/writeOffFlatFileBeanInfo.xml`).
Queries `MCCA_WRITE_OFF` for records where `TO_CHAR(SUBMITTED_DATE, 'YYYYMM') = SUBSTR(:batchDate, 0, 6)`, formats each row using the exact padding and 11-digit cents rules from `WriteOffFlatFileMapper.java`, writes the comma-delimited export file `MCCAWriteOffExport_<batchDate>.txt`, and sends the completion email via `MailImpl.java`.

## Files in This Folder
- `main.py` — Implements `writeOffJdbcCursorReader`, `WriteOffFlatFileMapper.format_write_off_row`, `writeOffFlatFileItemWriter`, and `writeOffMailStep`.
- `requirements.txt` — Python dependencies (`psycopg2-binary`).

## Usage
```bash
python main.py \
  --batch-date 20261128 \
  --output-dir ./output \
  --schema mcca
```
