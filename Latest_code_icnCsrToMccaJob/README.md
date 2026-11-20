# `icnCsrToMccaJob` — 100% Verified Python Port

This folder contains the exact 1:1 Python conversion of **`icnCsrToMccaJob.xml`** and all its associated Java classes (`beanInfo.xml`, `IPMFactsMappingUtil`, `IcnJdbcDaoImpl`, `CsrJdbcDaoImpl`, `OthrInjClmtsDaoImpl`, `UpdateIcnCsrJdbcDaoImpl`, `MccaClaimDaoImpl`, `BatchTypeDecider`, `DBUtils`, Processors, Mappers, and Writers).

---

## 1. Exact Database Tables Used in `icnCsrToMccaJob`

| Category | Exact Table Name | Purpose in `icnCsrToMccaJob` |
| :--- | :--- | :--- |
| **Temp / Staging Tables** | `MCCA_TMP_CLM` | Claim-level staging table loaded from FACTS (`ACC_*`, `INSRD_*`, `CARRIER_PLCY_NUM`, `PREV_IPM_CLMNBR`, etc.). Cleared in `step10`. |
| **Temp / Staging Tables** | `MCCA_TMP_CLMNT` | Claimant-level staging table loaded from FACTS (`CLID`, `CLMT_*`, `INJ_CD`, `IPM_CLAIMANT_NO`, etc.). Cleared in `step10`. |
| **Temp / Staging Tables** | `STG_MCCA_RESERVES` | Staging reserves table unioned with `MCCA_RESERVES` in `CsrJdbcDaoImpl.getReservesValue()`. |
| **Temp / Staging Tables** | `STG_MCCA_LOSS_EXPENSE_DETAILS` | Staging loss/expense table unioned with `MCCA_LOSS_EXPENSE_DETAILS` in `CsrJdbcDaoImpl.getPaidToDate()`. |
| **Main Transaction Tables** | `MCCA_CLAIM` | Master claim table (`TXN_ID`, `CARRIER_CLM_NUM`, `MCCA_CLM_NUM`, `LINK_ID`, `MASTER_CLAIM_IND`, `RETENTION`, `THRESHOLD`, `RPTD`, etc.). |
| **Main Transaction Tables** | `MCCA_ICN` | Initial Catastrophic Notification table (`TXN_ID`, `CARRIER_CLM_NUM`, `REC_TYP`, `STATUS`, `SUBMITTED_TO`, etc.). |
| **Main Transaction Tables** | `MCCA_CSR` | Claimant Status Report table (`TXN_ID`, `CARRIER_CLM_NUM`, `CLID`, `CSR_SEQ`, `REC_TYP`, `STATUS`, `STATUS_LST`, `CLOSED_IND`, 141 columns including MCCA 3.3 multi-tier attendant care). |
| **Main Transaction Tables** | `MCCA_OTHR_INJ_CLMTS_PYMT` | Cross-companion & other injured claimant payment/reserve table (`CLM_TYPE` `'1'`, `'2'`, `'3'`). |
| **Main Transaction Tables** | `MCCA_PROJECTIONS` | Projections table initialized in Step 4 (`CsrJdbcDaoImpl.insertProjections`). |
| **Financial & Reference Tables** | `MCCA_LOSS_EXPENSE_DETAILS` | Historical loss/expense payment ledger (`COVERAGE` `'ZPIP'`, `'ZWL'`, `'ZSL'`). |
| **Financial & Reference Tables** | `MCCA_RESERVES` | Historical reserve ledger (`COVERAGE` `'ZPIP'`, `'ZWL'`, `'ZSL'`). |
| **Financial & Reference Tables** | `D_FISCAL_MONTH` | Fiscal calendar lookup table (`LAST_DAY_FISCAL_MONTH`, `FISCAL_MONTH_NUMBER`, `FISCAL_YEAR`). |
| **Financial & Reference Tables** | `MCCA_THRESHOLD` | MCCA catastrophic threshold schedule (`VALID_FROM`, `VALID_TO`, `THRESHOLD`). |
| **Financial & Reference Tables** | `MCCA_EXCEPTION` | Exception override table (`EXCEPTION_CD = '8'` for Process New CLID, `EXCEPTION_CD = '9'` for Stop ICN/CSR). |
| **Financial & Reference Tables** | `MCCA_CODES_DECODE` | Lookup table (`CATEGORY = 'mcca_assign_to'`, `'mcca_assign_carrier'`, `'ipm_facts_mapping_version'`). |
| **IPM Conversion Tables** | `IPM_FACTS_CLAIM_MAPPING_TABLE` | Maps converted IPM claim numbers to FACTS claim numbers (Step 1). |
| **IPM Conversion Tables** | `IPM_FACTS_CLID_MAPPING_TABLE` | Maps converted IPM claimant numbers to FACTS `CLID`s (Step 1). |

---

## 2. How to Segregate Daily, Weekly, and Monthly Runs (CLI Parameters)

In `jobs/icnCsrToMccaJob.xml` and `BatchTypeDecider.java`, the job accepts two parameters:
1. **`batchTypeParameter`** (`--batch-type` / `-t`):
   - `m` -> **`MONTHLY`**
   - `d` -> **`DAILY`**
   - `w` -> **`WEEKLY`**
2. **`batchDateParameter`** (`--batch-date` / `-d`): Date in `YYYY/MM/DD` format (e.g., `2026/11/19`).

### Execution Path by `batchTypeParameter`:
- **Monthly (`--batch-type m --batch-date YYYY/MM/DD`)**:
  `step1` -> `step2` -> `step3` -> `step4` -> `step5` -> `step6` -> `step7` -> `step8` -> `step9` -> `updateRptdColumn` -> `step10` (`clearIcnTempTables`) -> `icnCsrMail`
- **Daily (`--batch-type d --batch-date YYYY/MM/DD`)**:
  `step8` -> `step9` -> `updateRptdColumn` -> **END** *(Skips Steps 1–7, does NOT clear temp tables in Step 10, and does NOT send the monthly email)*
- **Weekly (`--batch-type w --batch-date YYYY/MM/DD`)**:
  `updateRptdColumn` -> **END** *(Only updates `RPTD` on `MCCA_CLAIM`)*

```bash
# Run Monthly Batch
python main.py --batch-type m --batch-date 2026/11/19

# Run Daily Batch
python main.py --batch-type d --batch-date 2026/11/19

# Run Weekly Batch
python main.py --batch-type w --batch-date 2026/11/19
```
