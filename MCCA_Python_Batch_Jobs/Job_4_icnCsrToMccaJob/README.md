# Job 4: `icnCsrToMccaJob` (FACTS ICN & CSR Monthly / Weekly / Daily Batch Job)

## Overview
Python modernization of the Spring Batch job `icnCsrToMccaJob` (`jobs/icnCsrBatchJob.xml` & `common/icnCsrBeanInfo.xml`).
Supports all 3 execution modes controlled by `BatchTypeDecider.java` (`--batch-type`):
1. **`m` (MONTHLY — Default)**: Executes Steps 1 through 11 (`ipmFactsMappingUpdateStep` -> `CopyIcnProcessor` -> `IcnDetailProcessor` -> `CsrDetailProcessor` -> `OthrInjClmtsWriter` -> `UpdateIcnTmpClaimProcessor` -> `UpdateIcnCsrClaimProcessor` -> `CsrAmountUpdateWriter` -> `AmountUpdateProcessor` -> `MccaClaimRptdProcessor` -> `clearIcnTempTables` -> `icnCsrMail`).
2. **`d` (DAILY)**: Executes Step 8 (`CsrAmountUpdateWriter`), Step 9 (`AmountUpdateProcessor`), and `updateRptdColumn` (`MccaClaimRptdProcessor`).
3. **`w` (WEEKLY)**: Executes only `updateRptdColumn` (`MccaClaimRptdProcessor`).

## Files in This Folder
- `main.py` — Orchestrates `BatchTypeDecider` routing and all 11 steps.
- `ipm_facts_mapping_util.py` — Port of `IPMFactsMappingUtil.java` (`jobType='icn_csr'`) & `IPMFactsMappingUpdateDaoImpl.java` (7 sanity checks on `MCCA_TMP_CLM` and `MCCA_TMP_CLM_DTLS` + 9 table updates).
- `validators.py` — Port of `ICNValidator.java`, `CSRValidator.java`, `formatPhoneNumber`, `buildInjuryDescription`, and `CLOSED_HEAD_INJURY_CODES` (`CHI`).
- `dao.py` — Port of `IcnJdbcDaoImpl`, `CsrJdbcDaoImpl`, `OthrInjClmtsDaoImpl`, `UpdateIcnCsrJdbcDaoImpl`, `MccaClaimDaoImpl`, and all 8 Writers.
- `requirements.txt` — Python dependencies.

## Usage
```bash
# Monthly run (1st of month at 12:20 AM)
python main.py --batch-type m --schema mcca

# Daily run
python main.py --batch-type d --schema mcca

# Weekly run
python main.py --batch-type w --schema mcca
```
