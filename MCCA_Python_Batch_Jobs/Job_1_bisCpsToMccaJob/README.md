# Job 1: `bisCpsToMccaJob` (CPS RFR Monthly Batch Job)

## Overview
Python modernization of the Spring Batch job `bisCpsToMccaJob` (`jobs/rfrBatchJob.xml`).
Ingests the monthly CPS RFR Header (19 semicolon-delimited columns) and Detail (66 semicolon-delimited columns containing `BIL*` and `CPT*` lines) flat files into AlloyDB staging tables (`MCCA_CPS_TMP_RFR*`), performs cross-file and March 2022 business validations, submits valid claims to the **MCCA MMS REST API (`POST /api/v1/Claim/Rfr`)**, and promotes all records into `MCCA_RFR`, `MCCA_RFR_PAYLOG`, and `MCCA_RFR_PAYLOG_CPT`.

## Files in This Folder
- `main.py` — Orchestrates all 10 steps (`clearCpsTempTablesBeforeProcess` -> `rfrHeaderBisCpsToDbStep` -> `rfrDetailBisCpsToDbStep` -> `rfrDetailCptBisCpsToDbStep` -> `validateCpsFiles` -> `rfrHeaderStep` -> `rfrDetailStep` -> `rfrDetailCptStep` -> `cpsSuccessMailStep` -> `clearCpsTempTables`).
- `validators.py` — Exact port of `RFRValidator.java`, `DataValidator.java`, `BatchConstants.java`, and `FileValidator.java`.
- `mms_client.py` — Exact port of `OAuthClient.java`, `RfrRestMapper.java`, `RfrJsonBuilder.java`, and `RfrRestClient.java`.
- `dao.py` — All AlloyDB SQL operations for `MCCA_CPS_TMP_RFR*` and `MCCA_RFR*`.
- `requirements.txt` — Python dependencies.

## Usage
```bash
python main.py \
  --header-file /path/to/CPS_RFR_HEADER.txt \
  --detail-file /path/to/CPS_RFR_DETAIL.txt \
  --cpt-effective-date 2019-01-01 \
  --schema mcca
```
