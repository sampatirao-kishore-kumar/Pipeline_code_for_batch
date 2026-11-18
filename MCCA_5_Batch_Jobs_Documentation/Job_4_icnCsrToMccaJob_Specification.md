# Job 4 Specification: `icnCsrToMccaJob` (FACTS ICN & CSR Monthly / Weekly / Daily Batch Job)

## 1. Executive Summary & Job Overview
| Attribute | Details |
| :--- | :--- |
| **Job Name / ID** | `icnCsrToMccaJob` |
| **Source System** | **FACTS** (Ingested via Informatica IICS into AlloyDB staging tables `MCCA_TMP_CLM`, `MCCA_TMP_CLM_DTLS`, `MCCA_TMP_OTHR_INJ_CLMTS_PYMT`, `MCCA_CLM_RPTD`) |
| **Schedule / Execution Modes** | Controlled by runtime job parameter `batchType` via **`BatchTypeDecider.java`**:<br>1. **`MONTHLY` (`batchType = 'm'` or default)**: Runs on the 1st of the month at `12:20 AM` (Executes Steps 1–9, `updateRptdColumn`, Step 10 `clearIcnTempTables`, and `icnCsrMail`).<br>2. **`WEEKLY` (`batchType = 'w'`)**: Runs only `updateRptdColumn` (`MccaClaimRptdProcessor`).<br>3. **`DAILY` (`batchType = 'd'`)**: Runs Steps 8, 9, and `updateRptdColumn` (no temp table deletion). |
| **Spring XML Configs** | `jobs/icnCsrBatchJob.xml` (`<batch:job id="icnCsrToMccaJob">`), `common/icnCsrBeanInfo.xml` |
| **Input Staging Tables** | `MCCA_TMP_CLM`, `MCCA_TMP_CLM_DTLS`, `MCCA_TMP_OTHR_INJ_CLMTS_PYMT`, `MCCA_CLM_RPTD`, `MCCA_INCURRED_AMT_SUM` |
| **Main Target Tables** | `MCCA_CLM`, `MCCA_OTHR_INJ_CLMTS_PYMT`, `MCCA_HIST`, `MCCA_REMARKS`, `IPM_FACTS_CLAIM_MAPPING_TABLE`, `IPM_FACTS_CLID_MAPPING_TABLE`, `MCCA_CODES_DECODE` |
| **External API Called** | **None during batch execution** (Sets `STATUS = 'IC'` or `'PN'` in `MCCA_CLM`; claim examiners review and submit ICN/CSR via the MCCA Web Portal to `/api/v1/Claim/Icn` and `/api/v1/Claim/Csr`). |
| **Email Notification** | `icnCsrMail` (`MailImpl.java` — runs at the end of the `MONTHLY` flow) |

---

## 2. End-to-End Architecture & Step Execution Flow (`BatchTypeDecider.java`)

At startup, `<batch:decision id="decider" decider="batchTypeDecider">` inspects `jobParameters.getString("batchType")`:
- If `"w"` (case-insensitive) -> returns **`FlowExecutionStatus("WEEKLY")`** -> jumps directly to `updateRptdColumn` and ends.
- If `"d"` (case-insensitive) -> returns **`FlowExecutionStatus("DAILY")`** -> jumps to `step8` -> `step9` -> `updateRptdColumn` and ends.
- Otherwise (`"m"` or omitted) -> returns **`FlowExecutionStatus("MONTHLY")`** -> runs the full 12-stage monthly pipeline:

```
                                   ┌────────────────────────┐
                                   │   BatchTypeDecider     │
                                   │ (batchType parameter)  │
                                   └───────────┬────────────┘
                  ┌────────────────────────────┼────────────────────────────┐
                  │ MONTHLY ('m')              │ DAILY ('d')                │ WEEKLY ('w')
                  ▼                            │                            │
[Step 1: ipmFactsMappingUpdateStep]            │                            │
  (IPMFactsMappingUtil [jobType='icn_csr'])    │                            │
                  │                            │                            │
                  ▼                            │                            │
[Step 2: step2 (CopyIcnProcessor)]             │                            │
  (Copies previous max-TXN ICN rows in         │                            │
   MCCA_CLM to new TXN_ID with REC_TYPE='CSR') │                            │
                  │                            │                            │
                  ▼                            │                            │
[Step 3: step3 (IcnDetailProcessor)]           │                            │
  (Reads new ICNs from MCCA_TMP_CLM ->         │                            │
   Validates via ICNValidator -> Inserts       │                            │
   new ICN records into MCCA_CLM)              │                            │
                  │                            │                            │
                  ▼                            │                            │
[Step 4: step4 (CsrDetailProcessor)]           │                            │
  (Reads CSRs from MCCA_TMP_CLM joined with    │                            │
   MCCA_CLM -> Validates via CSRValidator ->   │                            │
   Updates MCCA_CLM & Inserts MCCA_REMARKS)    │                            │
                  │                            │                            │
                  ▼                            │                            │
[Step 5: step5 (OthrInjClmtsWriter)]           │                            │
  (Copies MCCA_TMP_OTHR_INJ_CLMTS_PYMT         │                            │
   for valid UNIQUE_IDs into                   │                            │
   MCCA_OTHR_INJ_CLMTS_PYMT)                   │                            │
                  │                            │                            │
                  ▼                            │                            │
[Step 6: step6 (UpdateIcnTmpClaimProcessor)]   │                            │
  (Enriches MCCA_CLM where TXN_ID > maxTxnId   │                            │
   using MCCA_TMP_CLM_DTLS, sets INJ_DESC &    │                            │
   BRAIN_INJ_CD, runs ICN/CSR validators)      │                            │
                  │                            │                            │
                  ▼                            │                            │
[Step 7: step7 (UpdateIcnCsrClaimProcessor)]   │                            │
  (Updates active/open MCCA_CLM records        │                            │
   for claims NOT in MCCA_TMP_CLM using        │                            │
   MCCA_TMP_CLM_DTLS)                          │                            │
                  │                            │                            │
                  ▼                            ▼                            │
[Step 8: step8 (CsrAmountUpdateWriter)] ◄──────┘                            │
  (Updates TOT_RES_AMT & CUM_AMT_PAID_TO_DT                                 │
   in MCCA_CLM from MCCA_INCURRED_AMT_SUM)                                  │
                  │                                                         │
                  ▼                                                         │
[Step 9: step9 (AmountUpdateProcessor)]                                     │
  (Recalculates TOT_RES_AMT & CUM_AMT_PAID_TO_DT                            │
    across companion claims with same MCCA_CLM_NUM)                          │
                  │                                                         │
                  ▼                                                         ▼
[Step 9b: updateRptdColumn (MccaClaimRptdProcessor)] ◄──────────────────────┘
  (Marks RPTD_TO_MCCA='Y' in MCCA_CLM_RPTD for claims present in MCCA_CLM)
                  │
                  ├──► (If DAILY or WEEKLY: Job Ends Here)
                  │
                  ▼ (If MONTHLY)
[Step 10: clearIcnTempTables (DBUtils)]
  (Deletes from MCCA_TMP_CLM, MCCA_TMP_OTHR_INJ_CLMTS_PYMT, MCCA_TMP_CLM_DTLS)
                  │
                  ▼
[Step 11: icnCsrMail (MailImpl)]
  (Sends monthly ICN/CSR batch completion email)
```

---

## 3. Detailed Step-by-Step Business Logic, Conditions & SQL Queries

### Step 1: `ipmFactsMappingUpdateStep` (`IPMFactsMappingUtil.java` [`jobType='icn_csr'`])
Performs 7 staging sanity checks against `MCCA_TMP_CLM` and `MCCA_TMP_CLM_DTLS`:
1. `getDuplicatesCountFromClaimMappingTable`: Checks `MCCA_TMP_CLM` and `MCCA_TMP_CLM_DTLS` for duplicate `IPM_CLM_NUM` or `CARRIER_CLM_NUM`.
2. `getConflictsCountForClaimMapping`: Checks if `MCCA_TMP_CLM` or `MCCA_TMP_CLM_DTLS` conflicts with `IPM_FACTS_CLAIM_MAPPING_TABLE`.
3. `getMissingIpmClaimsCountFromClaimMapping`: Checks if mapped claims in `MCCA_TMP_CLM` or `MCCA_TMP_CLM_DTLS` are missing `IPM_CLM_NUM`.
4. `getCountOfClaimsWithFeatureCountMismatch`: Checks if any claim in `MCCA_TMP_CLM` or `MCCA_TMP_CLM_DTLS` has inconsistent `IPM_CLID_NUM` presence across claimants or against `IPM_FACTS_CLID_MAPPING_TABLE`.
5. `getDuplicatesCountFromClidMappingTable`: Checks for duplicate `(CARRIER_CLM_NUM, CARRIER_CLMT_NUM)` or `(IPM_CLM_NUM, IPM_CLID_NUM)` in `MCCA_TMP_CLM` and `MCCA_TMP_CLM_DTLS`.
6. `getConflictsCountForClidMapping`: Checks for conflicts with `IPM_FACTS_CLID_MAPPING_TABLE`.
7. `getMissingIpmClidsCountFromClidMapping`: Checks for missing `IPM_CLM_NUM`/`IPM_CLID_NUM` on already-mapped CLIDs.
- **Note on Empty Staging Tables**: If `SELECT COUNT(*) FROM mcca_tmp_clm` and `SELECT COUNT(*) FROM mcca_tmp_clm_dtls` are both `0`, `IPMFactsMappingUtil` logs `"No data found in ICN CSR temp tables"` and returns `COMPLETED` (continues gracefully).
- Otherwise, increments `ipm_facts_mapping_version` in `MCCA_CODES_DECODE`, inserts new mappings into `IPM_FACTS_CLAIM_MAPPING_TABLE` and `IPM_FACTS_CLID_MAPPING_TABLE`, and updates converted claim/CLID numbers across the 9 target tables (`MCCA_CLM`, `MCCA_RFR`, `MCCA_RFR_PAYLOG`, `MCCA_LAST_BILL_DATE`, `MCCA_WRITE_OFF`, `MCCA_HIST`, `MCCA_REMARKS`, `MCCA_EXCEPTION`, `MCCA_OTHR_INJ_CLMTS_PYMT`).

---

### Step 2: `step2` — Copy Previous Submitted ICNs as CSR Baseline (`CopyIcnProcessor.java` & `CopyIcnWriter.java`)
1. **Before-Step Max TXN Capture (`CopyIcnProcessor.getMaxId()`)**:
   - Executes `SELECT MAX(TXN_ID) FROM MCCA_CLM` and saves it in `UpdateIcnTmpClaimProcessor.maxTxnId`. All records inserted during this batch run will have `TXN_ID > maxTxnId`.
2. **Reader (`copyIcnDataReader` -> `IcnCsrRowMapper.java`)**:
   - Selects existing claims in `MCCA_CLM` that also exist in `MCCA_TMP_CLM`, where `MCCA_CLM.TXN_ID` is the latest transaction for that `UNIQUE_ID` and `STATUS IN ('SB', 'MN')` (Submitted or Manually Processed):
   ```sql
   SELECT CLM.*
   FROM MCCA_CLM CLM, MCCA_TMP_CLM TMP
   WHERE CLM.UNIQUE_ID = TMP.CARRIER_CLM_NUM || '-' || TMP.CARRIER_CLMT_NUM
     AND CLM.TXN_ID IN (
         SELECT MAX(CLM2.TXN_ID) FROM MCCA_CLM CLM2 WHERE CLM.UNIQUE_ID = CLM2.UNIQUE_ID
     )
     AND CLM.STATUS IN ('SB', 'MN');
   ```
3. **Processor (`CopyIcnProcessor.process`)**:
   - Checks if the claim has an exception blocking CSR creation (`IcnJdbcDaoImpl.isExceptionClaim`):
     ```sql
     SELECT COUNT(*) FROM mcca.mcca_exception
     WHERE carrier_clm_num = ? AND carrier_clmt_num = ?
       AND exception_code IN ('1', '2') AND exception_value = 'Y';
     ```
   - If `isExceptionClaim == true`: skips the record (`returns null`).
   - Otherwise, clones the `MCCA_CLM` record, sets `REC_TYPE = 'CSR'`, `CRT_USER_ID = 'BATCH'`, `MDFD_USER_ID = 'BATCH'`, and inserts a new row into `MCCA_CLM` with `MCCA_CLM_TXN_ID_SEQ.NEXTVAL` via `CopyIcnWriter.java`.

---

### Step 3: `step3` — Process New ICN Claims (`IcnDetailProcessor.java`, `ICNValidator.java`, `IcnDetailWriter.java`)
1. **Reader (`icnDetailReader` -> `IcnCsrRowMapper.java`)**:
   - Reads rows from `MCCA_TMP_CLM` whose `CARRIER_CLM_NUM || '-' || CARRIER_CLMT_NUM` does **NOT** yet exist in `MCCA_CLM`:
   ```sql
   SELECT * FROM MCCA_TMP_CLM TMP
   WHERE TMP.CARRIER_CLM_NUM || '-' || TMP.CARRIER_CLMT_NUM NOT IN (
       SELECT DISTINCT UNIQUE_ID FROM MCCA_CLM
   );
   ```
2. **Processor (`IcnDetailProcessor.process`)**:
   - Checks `IcnJdbcDaoImpl.isExceptionClaim(carrierClaimNumber, carrierClaimantNumber)` (`EXCEPTION_CODE IN ('1', '2') AND EXCEPTION_VALUE = 'Y'`). If `true`, skips the record (`returns null`).
   - Sets `uniqueId = carrierClaimNumber + "-" + carrierClaimantNumber`.
   - Sets `recordType = "ICN"` and `claimType = "FACTS"`.
   - Sets `reportedCatastrophicDate = new Date()`.
   - **Adjuster Phone Formatting (`formatPhoneNumber`)**:
     - If `adjusterPhone` is 10 digits (e.g. `"3134906206"`), formats as `"313-490-6206"`.
   - **Policy Number Formatting**:
     - Left-pads numeric policy numbers or formats per `ICN` rules.
   - **Checks for Companion Claims (`IcnJdbcDaoImpl.isCompanionClaim`)**:
     - Queries `MCCA_CLM` and `MCCA_TMP_CLM` to see if other claimants exist under the same `CARRIER_CLM_NUM`.
   - **Validation (`ICNValidator.validate(icn)`)**:
     - Validates mandatory ICN fields (`carrierId`, `naicCode`, `policyNumber`, `effectiveDate`, `expirationDate`, `dateOfLoss`, `insuredFirstName`/`LastName`, `claimantFirstName`/`LastName`, `birthDate`, `gender`, `injuryDescription`, `mccaStatusCode`, `mccaRelationCode`, `accidentDate`, `accidentDescription`, `totalReserve`, `cumulativePaidToDate`, etc.).
     - Populates `ERR_ELE_LIST` with comma-separated names of any missing/invalid fields.
     - Sets `statusIndicator = "IC"` (Incomplete) if mandatory fields are missing, or `"PN"` (Pending Examiner Review).
3. **Writer (`IcnDetailWriter.java`)**:
   - Inserts the new ICN row into `MCCA_CLM` using `MCCA_CLM_TXN_ID_SEQ.NEXTVAL`.

---

### Step 4: `step4` — Process CSR Updates on Existing Claims (`CsrDetailProcessor.java`, `CSRValidator.java`, `CsrDetailWriter.java`)
1. **Reader (`csrDetailReader` -> `CsrRowMapper.java`)**:
   - Joins `MCCA_TMP_CLM` with `MCCA_CLM` for claims that already exist in `MCCA_CLM` (either newly cloned in Step 2 or currently in `'PN'`/`'IC'` status at `MAX(TXN_ID)`):
   ```sql
   SELECT TMP.*, CLM.TXN_ID AS CLM_TXN_ID, CLM.UNIQUE_ID AS CLM_UNIQUE_ID, CLM.STATUS AS CLM_STATUS
   FROM MCCA_TMP_CLM TMP, MCCA_CLM CLM
   WHERE CLM.UNIQUE_ID = TMP.CARRIER_CLM_NUM || '-' || TMP.CARRIER_CLMT_NUM
     AND CLM.TXN_ID IN (
         SELECT MAX(CLM2.TXN_ID) FROM MCCA_CLM CLM2 WHERE CLM2.UNIQUE_ID = CLM.UNIQUE_ID
     );
   ```
2. **Processor (`CsrDetailProcessor.process`)**:
   - Checks `CsrJdbcDaoImpl.isExceptionClaim` (`EXCEPTION_CODE IN ('1', '2') AND EXCEPTION_VALUE = 'Y'`). If `true`, returns `null`.
   - Sets `recordType = "CSR"`, `claimType = "FACTS"`, and formats `adjusterPhone`.
   - **Change Reason Remark Insertion (`MCCA_REMARKS`)**:
     - If `changeReasonDescription != null && !changeReasonDescription.isEmpty()` (e.g., `"Reserve Increase"`, `"Fall Below"`, `"Reopen"`), inserts a remark into `MCCA_REMARKS` via `CsrJdbcDaoImpl.insertRemarks`:
       ```sql
       INSERT INTO mcca.mcca_remarks (REMARK_SEQ_NUM, UNIQUE_ID, REMARKS, CRT_DTTM, CRT_USER_ID, MDFD_DTTM, MDFD_USER_ID)
       VALUES (mcca.mcca_remark_seq.NEXTVAL, :uniqueId, :remarks, SYSDATE, 'BATCH', SYSDATE, 'BATCH');
       ```
   - Runs `CSRValidator.validate(csr)` to populate `ERR_ELE_LIST` and set `STATUS` (`'IC'` or `'PN'`).
3. **Writer (`CsrDetailWriter.java`)**:
   - Updates the latest `TXN_ID` row in `MCCA_CLM` with the updated reserve, paid, adjuster, and status fields from `MCCA_TMP_CLM`.

---

### Step 5: `step5` — Copy Other Injured Claimants Payments (`OthrInjClmtsPymtRowMapper.java` & `OthrInjClmtsWriter.java`)
1. **Reader (`othrInjClmtsReader`)**:
   - Reads rows from `MCCA_TMP_OTHR_INJ_CLMTS_PYMT` where `CARRIER_CLM_NUM || '-' || CARRIER_CLMT_NUM` exists in `MCCA_CLM`.
2. **Before-Write Cleanup & Insert (`OthrInjClmtsWriter.java` & `OthrInjClmtsDaoImpl.java`)**:
   - Deletes existing records in `MCCA_OTHR_INJ_CLMTS_PYMT` for the matching `UNIQUE_ID` and inserts the refreshed other-injured-claimant payment rows into `MCCA_OTHR_INJ_CLMTS_PYMT`.

---

### Step 6: `step6` — Enrich Newly Processed ICN/CSR Rows from `MCCA_TMP_CLM_DTLS` (`UpdateIcnTmpClaimProcessor.java` & `UpdateIcnTmpClaimDetailWriter.java`)
1. **Reader (`updateIcnTmpClaimReader` -> `TmpClaimDetailRowMapper.java`)**:
   - Joins `MCCA_CLM` (where `TXN_ID > maxTxnId` captured at the start of Step 2) with `MCCA_TMP_CLM_DTLS`.
2. **Processor (`UpdateIcnTmpClaimProcessor.process`)**:
   - Concatenates up to 3 ICD codes and descriptions into `injuryDescription`:
     `icd1Code + " - " + icd1Desc + ", " + icd2Code + " - " + icd2Desc + ", " + icd3Code + " - " + icd3Desc` (truncated to max `200` characters).
   - **Brain Injury Code Logic**:
     - If `REC_TYPE == 'ICN'` and any of `icd1Code`, `icd2Code`, `icd3Code` is in `BatchConstants.CLOSED_HEAD_INJURY_CODES` (`{"854.0","854.00","854.01","854.02","854.03","854.04","854.05","854.06","854.09","S06.9X9A","S06.2X9A"}`), sets `brainInjuryCode = "CHI"`.
   - Re-runs `ICNValidator.validate` (if `REC_TYPE == 'ICN'`) or `CSRValidator.validate` (if `REC_TYPE == 'CSR'`) to refresh `ERR_ELE_LIST` and `STATUS`.
3. **Writer (`UpdateIcnTmpClaimDetailWriter.java`)**:
   - Updates `MCCA_CLM` with the enriched claimant, insured, policy, accident, and injury details from `MCCA_TMP_CLM_DTLS`.

---

### Step 7: `step7` — Update Open/Existing Claims Not in `MCCA_TMP_CLM` (`UpdateIcnCsrClaimProcessor.java` & `UpdateIcnCsrClaimDetailWriter.java`)
1. **Reader (`updateIcnCsrClaimReader` -> `IcnCsrClaimDetailRowMapper.java`)**:
   - Selects latest `TXN_ID` rows in `MCCA_CLM` (`WHERE STATUS IN ('IC', 'PN')`) that were **not** part of `MCCA_TMP_CLM` in this run, joined with `MCCA_TMP_CLM_DTLS`.
2. **Processor (`UpdateIcnCsrClaimProcessor.process`)**:
   - Updates demographic, adjuster, policy, and injury fields from `MCCA_TMP_CLM_DTLS` (without overwriting manually entered UI fields if already populated), re-validates via `ICNValidator` / `CSRValidator`, and writes back to `MCCA_CLM` via `UpdateIcnCsrClaimDetailWriter.java`.

---

### Step 8: `step8` — Update Reserve & Cumulative Paid Amounts (`CsrAmountUpdateRowMapper.java` & `CsrAmountUpdateWriter.java`)
*(Runs in both `MONTHLY` and `DAILY` modes)*
1. Reads incurred amount summaries from `MCCA_INCURRED_AMT_SUM` joined with `MCCA_CLM` (latest `TXN_ID` where `STATUS IN ('IC', 'PN')`).
2. Updates `TOT_RES_AMT` (Total Reserve) and `CUM_AMT_PAID_TO_DT` (Cumulative Paid to Date) in `MCCA_CLM`.

---

### Step 9: `step9` — Companion Claim Amount Aggregation (`AmountUpdateProcessor.java` & `CsrAmountUpdateWriter.java`)
*(Runs in both `MONTHLY` and `DAILY` modes)*
1. Reads claims in `MCCA_CLM` sharing the same `MCCA_CLM_NUM` (companion claims where `MCCA_CLM_NUM` ends with `'A'`, `'B'`, etc. or shares the base claim number).
2. Aggregates `TOT_RES_AMT` and `CUM_AMT_PAID_TO_DT` across the companion group via `IcnJdbcDaoImpl.getIncurredAmount` and updates `MCCA_CLM`.

---

### Step 9b: `updateRptdColumn` — Update Reported-to-MCCA Flag (`MccaClaimRptdProcessor.java` & `MccaClaimRptdWriter.java`)
*(Runs in `MONTHLY`, `DAILY`, and `WEEKLY` modes)*
1. **Reader (`updateRptdColumnReader` -> `UpdateRptdRowMapper.java`)**:
   - Reads rows from `MCCA_CLM_RPTD` where `RPTD_TO_MCCA = 'N'` (or not `'Y'`).
2. **Processor (`MccaClaimRptdProcessor.process`)**:
   - Calls `MccaClaimDaoImpl.getClaimCount(carrierClaimNumber, carrierClaimantNumber)`:
     ```sql
     SELECT COUNT(*) FROM mcca.mcca_clm
     WHERE carrier_clm_num = ? AND carrier_clmt_num = ?;
     ```
   - If `count > 0`: sets `reportedToMcca = "Y"` and returns the record to `MccaClaimRptdWriter`.
   - If `count == 0`: returns `null` (leaves `RPTD_TO_MCCA` unchanged).
3. **Writer (`MccaClaimRptdWriter.java`)**:
   ```sql
   UPDATE MCCA_CLM_RPTD
   SET RPTD_TO_MCCA = :reportedToMcca, MDFD_DTTM = SYSDATE
   WHERE CARRIER_CLM_NUM = :carrierClaimNumber AND CARRIER_CLMT_NUM = :carrierClaimantNumber;
   ```

---

### Step 10: `clearIcnTempTables` (`DBUtils.java`)
*(Runs in `MONTHLY` mode only)*
Deletes all staging rows from the 3 ICN/CSR temporary tables:
```sql
DELETE FROM MCCA_TMP_CLM;
DELETE FROM MCCA_TMP_OTHR_INJ_CLMTS_PYMT;
DELETE FROM MCCA_TMP_CLM_DTLS;
```

---

### Step 11: `icnCsrMail` (`MailImpl.java`)
*(Runs in `MONTHLY` mode only)*
Sends the monthly completion email notification to configured recipients.
