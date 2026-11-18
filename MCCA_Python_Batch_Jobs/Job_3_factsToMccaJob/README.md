# Job 3: `factsToMccaJob` (FACTS RFR Monthly Batch Job)

## Overview
Python modernization of the Spring Batch job `factsToMccaJob` (`jobs/rfrBatchJob.xml`).
Processes FACTS RFR staging data from AlloyDB (`MCCA_FAC_TMP_RFR`, `MCCA_FAC_TMP_RFR_PAYLOG`, `MCCA_FAC_TMP_RFR_PAYLOG_CPT`), executes IPM-to-FACTS historical claim/CLID mapping sanity checks and updates across 9 MCCA tables, validates headers/paylogs/CPTs against `MCCA_EXCEPTION` (`EXCEPTION_CODE='3'`), `RFRValidator`, and March 2022 rules, submits valid RFRs to the **MCCA MMS REST API (`POST /api/v1/Claim/Rfr`)**, updates `MCCA_LAST_BILL_DATE` and `MCCA_REMARKS` (`RFR Fall Below`), promotes records to `MCCA_RFR*`, and generates and emails `rfrProcessingReport.xlsx` and `missingDatesReport.xlsx`.

## Files in This Folder
- `main.py` — Orchestrates all 8 steps (`ipmFactsMappingUpdateStep` -> `rfrFactsPreLoadStep` -> `rfrFactsMissingDatesStep` -> `rfrFactsHeaderStep` -> `rfrFactsDetailCptStep` -> `rfrFactsPostStep` -> `rfrMail` -> `clearTempTables`).
- `ipm_facts_mapping_util.py` — Port of `IPMFactsMappingUtil.java` (`jobType='rfr'`) & `IPMFactsMappingUpdateDaoImpl.java` (8 staging sanity checks + 9 table updates).
- `validators.py` — Port of `RFRValidator.java`, `DataValidator.java`, and `BatchConstants.java`.
- `mms_client.py` — Port of `OAuthClient.java`, `RfrRestMapper.java`, `RfrJsonBuilder.java`, and `RfrRestClient.java`.
- `excel_reports.py` — Port of `RFRReportAttachedMailImpl.java` generating `rfrProcessingReport.xlsx` and `missingDatesReport.xlsx`.
- `dao.py` — All AlloyDB SQL operations for `factsToMccaJob`.
- `requirements.txt` — Python dependencies (`psycopg2-binary`, `requests`, `urllib3`, `openpyxl`).

## Usage
```bash
python main.py \
  --cpt-effective-date 2019-01-01 \
  --report-dir ./reports \
  --schema mcca
```
