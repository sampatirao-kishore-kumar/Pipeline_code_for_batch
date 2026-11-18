# Job 3 Specification: `factsToMccaJob` (FACTS RFR Monthly Batch Job)

## 1. Executive Summary & Job Overview
| Attribute | Details |
| :--- | :--- |
| **Job Name / ID** | `factsToMccaJob` |
| **Source System** | **FACTS** (Ingested via Informatica IICS directly into AlloyDB staging tables `MCCA_FAC_TMP_RFR*`) |
| **Schedule / Frequency** | Monthly (Runs on the 1st of the month at `12:01 AM`) |
| **Spring XML Configs** | `jobs/rfrBatchJob.xml` (`<batch:job id="factsToMccaJob">`), `common/beanInfo.xml` |
| **Input Staging Tables** | `MCCA_FAC_TMP_RFR`, `MCCA_FAC_TMP_RFR_PAYLOG`, `MCCA_FAC_TMP_RFR_PAYLOG_CPT` |
| **Mapping & Control Tables** | `IPM_FACTS_CLAIM_MAPPING_TABLE`, `IPM_FACTS_CLID_MAPPING_TABLE`, `MCCA_CODES_DECODE`, `MCCA_EXCEPTION`, `MCCA_LAST_BILL_DATE`, `MCCA_REMARKS` |
| **Main Target Tables** | `MCCA_RFR`, `MCCA_RFR_PAYLOG`, `MCCA_RFR_PAYLOG_CPT` (plus 9 tables updated during IPM-to-FACTS claim/CLID conversion in Step 1) |
| **External API Called** | **MCCA MMS REST API** — `POST /api/v1/Claim/Rfr` (Authenticated via ADFS OAuth2 `client_credentials`) |
| **Generated Excel Reports & Email** | Step 7 (`RFRReportAttachedMailImpl.java`) generates and attaches two Excel workbooks:<br>1. `rfrProcessingReport.xls` (Pre- vs. Post-processing amounts & status `SB`/`RJ`/`PN`)<br>2. `missingDatesReport.xls` (Paylog lines with missing `STRT_DATE` or `END_DT`) |

---

## 2. End-to-End Architecture & Step Execution Flow

`factsToMccaJob` executes **8 sequential steps** (with conditional stop if Step 1 fails sanity checks):

```
[Step 1: ipmFactsMappingUpdateStep] (IPMFactsMappingUtil.java [jobType='rfr'] & IPMFactsMappingUpdateDaoImpl.java)
       ├──► [Status = FAILED] ──► (Stops job if any of the 8 staging sanity checks fail)
       │
       ▼ [Status = COMPLETED]
[Step 2: rfrFactsPreLoadStep] (rfrFactsPaylogJdbcPreReader -> RFRFactsPayLogPreRowMapper)
       │ (Aggregates pre-processing billed, review fee, repriced paid, and MCCA payment amounts per claim into batchReport)
       ▼
[Step 3: rfrFactsMissingDatesStep] (rfrFactsPaylogJdbcMissingDatesReader -> MissingDatesBatchReportMapper)
       │ (Queries MCCA_FAC_TMP_RFR_PAYLOG where STRT_DATE IS NULL OR END_DT IS NULL into missingDatesReport)
       ▼
[Step 4: rfrFactsHeaderStep] (RfrFactsHeaderProcessor.java)
       │ (Reads MCCA_FAC_TMP_RFR + Paylogs + CPTs -> Checks AutoBillingException -> Runs RFRValidator, DataValidator & March 2022 Rules
       │  -> Sets uniqueKey = carrierClaimNumber + yyyyMMdd -> Calls MMS REST API if valid -> Updates MCCA_LAST_BILL_DATE & MCCA_REMARKS
       │  -> Inserts Paylogs into MCCA_RFR_PAYLOG & Header into MCCA_RFR)
       ▼
[Step 5: rfrFactsDetailCptStep] (RfrFactsDetailCptProcessor.java)
       │ (Sets uniqueKey = carrierClaimNumber + yyyyMMdd and inserts CPT rows from MCCA_FAC_TMP_RFR_PAYLOG_CPT into MCCA_RFR_PAYLOG_CPT)
       ▼
[Step 6: rfrFactsPostStep] (RfrFactsPaylogPostProcessor.java)
       │ (Joins MCCA_RFR, MCCA_RFR_PAYLOG, MCCA_FAC_TMP_RFR to populate post-processing amounts and status ['SB', 'RJ', 'PN'] into batchReport)
       ▼
[Step 7: rfrMail] (RFRReportAttachedMailImpl.java)
       │ (Builds rfrProcessingReport.xls and missingDatesReport.xls in memory/temp and emails them to business recipients)
       ▼
[Step 8: clearTempTables] (DBUtils.java)
       │ (Deletes all rows from MCCA_FAC_TMP_RFR_PAYLOG_CPT, MCCA_FAC_TMP_RFR_PAYLOG, MCCA_FAC_TMP_RFR)
```

---

## 3. Detailed Step-by-Step Business Logic, Conditions & SQL Queries

### Step 1: `ipmFactsMappingUpdateStep` (`IPMFactsMappingUtil.java` & `IPMFactsMappingUpdateDaoImpl.java`)
Although the standalone IPM batch job is retired, historical IPM claims converted into FACTS still arrive in `MCCA_FAC_TMP_RFR` and `MCCA_FAC_TMP_RFR_PAYLOG` carrying `IPM_CLM_NUM` and `IPM_CLID_NUM` values. Step 1 validates the FACTS staging tables and updates converted claim/claimant numbers across the database.

#### 3.1.1 Eight Staging Table Sanity Checks (`performSanityChecksOnTempTables`)
Before updating any mapping tables, `IPMFactsMappingUtil` runs 8 SQL count checks. If **any** of checks 1–7 return `> 0`, or check 8 returns `0`, Step 1 returns `ExitStatus.FAILED` and halts the job:
1. **`getDuplicatesCountFromClaimMappingTable`**: Checks for duplicate `IPM_CLM_NUM` or `FACTS_CLM_NUM` in `MCCA_FAC_TMP_RFR`:
   ```sql
   SELECT COUNT(*) FROM (
       SELECT ipm_clm_num, COUNT(ipm_clm_num) FROM mcca.mcca_fac_tmp_rfr GROUP BY ipm_clm_num HAVING COUNT(ipm_clm_num) > 1
       UNION ALL
       SELECT carrier_clm_num, COUNT(carrier_clm_num) FROM mcca.mcca_fac_tmp_rfr GROUP BY carrier_clm_num HAVING COUNT(carrier_clm_num) > 1
   );
   ```
2. **`getConflictsCountForClaimMapping`**: Checks if `MCCA_FAC_TMP_RFR` conflicts with existing mappings in `IPM_FACTS_CLAIM_MAPPING_TABLE`.
3. **`getMissingIpmClaimsCountFromClaimMapping`**: Checks if any `CARRIER_CLM_NUM` in `MCCA_FAC_TMP_RFR` already mapped in `IPM_FACTS_CLAIM_MAPPING_TABLE` is missing its `IPM_CLM_NUM`.
4. **`getCountOfClaimsWithFeatureCountMismatch`**: Checks if a claim in `MCCA_FAC_TMP_RFR_PAYLOG` has a mixed presence of `IPM_CLID_NUM` (some rows null, some non-null) or mismatches `IPM_FACTS_CLID_MAPPING_TABLE`.
5. **`getDuplicatesCountFromClidMappingTable`**: Checks for duplicate `(CARRIER_CLM_NUM, CARRIER_CLMT_NUM)` or `(IPM_CLM_NUM, IPM_CLID_NUM)` in `MCCA_FAC_TMP_RFR_PAYLOG`.
6. **`getConflictsCountForClidMapping`**: Checks if `MCCA_FAC_TMP_RFR_PAYLOG` CLID mappings conflict with `IPM_FACTS_CLID_MAPPING_TABLE`.
7. **`getMissingIpmClidsCountFromClidMapping`**: Checks if any `(CARRIER_CLM_NUM, CARRIER_CLMT_NUM)` in `MCCA_FAC_TMP_RFR_PAYLOG` already mapped in `IPM_FACTS_CLID_MAPPING_TABLE` is missing `IPM_CLM_NUM` or `IPM_CLID_NUM`.
8. **`getReimbursmentRequestRecordsCount`**:
   ```sql
   SELECT COUNT(*) FROM mcca.mcca_fac_tmp_rfr;
   -- Must be > 0 (if 0, job fails with "No data found in RFR temp tables")
   ```

#### 3.1.2 Updating Mapping Tables & 9 Target Tables (`updateIPMFactsMappingAndDependentTables`)
If all 8 checks pass:
1. Reads current version from `MCCA_CODES_DECODE` (`WHERE CODE_TYPE = 'ipm_facts_mapping_version'`) and increments by `1`.
2. Inserts newly discovered `(IPM_CLM_NUM, CARRIER_CLM_NUM)` pairs from `MCCA_FAC_TMP_RFR` into `IPM_FACTS_CLAIM_MAPPING_TABLE` with `VERSION = newVersion`.
3. Inserts newly discovered `(IPM_CLM_NUM, IPM_CLID_NUM, CARRIER_CLM_NUM, CARRIER_CLMT_NUM)` tuples from `MCCA_FAC_TMP_RFR_PAYLOG` into `IPM_FACTS_CLID_MAPPING_TABLE` with `VERSION = newVersion`.
4. Updates `CARRIER_CLM_NUM` (from `IPM_CLM_NUM` to `FACTS_CLM_NUM`) and `CLM_TYPE = 'FACTS'` across **9 tables** for `VERSION = newVersion`:
   - `MCCA_CLM`, `MCCA_RFR`, `MCCA_RFR_PAYLOG`, `MCCA_LAST_BILL_DATE`, `MCCA_WRITE_OFF`, `MCCA_HIST`, `MCCA_REMARKS`, `MCCA_EXCEPTION`, `MCCA_OTHR_INJ_CLMTS_PYMT`.
5. Updates `CARRIER_CLMT_NUM` (and `UNIQUE_ID = FACTS_CLM_NUM || '-' || FACTS_CLID_NUM` in `MCCA_CLM`) across `MCCA_CLM`, `MCCA_LAST_BILL_DATE`, and `MCCA_EXCEPTION` using `IPM_FACTS_CLID_MAPPING_TABLE`.
6. Updates `MCCA_CODES_DECODE SET CODE = newVersion WHERE CODE_TYPE = 'ipm_facts_mapping_version'`.

---

### Step 2: `rfrFactsPreLoadStep` (`RFRFactsPayLogPreRowMapper.java`)
Aggregates pre-processing paylog totals per claim from `MCCA_FAC_TMP_RFR_PAYLOG` and stores them in the in-memory `batchReport` map (`Map<String, RFRBatchReport>` keyed by `carrierClaimNumber`):
```sql
SELECT
    CARRIER_CLM_NUM,
    CARRIER_CLMT_NUM,
    FST_NAME,
    LST_NAME,
    MIDL_INT,
    SUM(BILLED_AMT) AS BILLED_AMT,
    SUM(BILL_REVIEW_FEES) AS BILL_REVIEW_FEES,
    SUM(REP_PAID_AMT) AS REP_PAID_AMT,
    SUM(TOT_MCCA_PMT_REQ) AS TOT_MCCA_PMT_REQ
FROM MCCA_FAC_TMP_RFR_PAYLOG
GROUP BY CARRIER_CLM_NUM, CARRIER_CLMT_NUM, FST_NAME, LST_NAME, MIDL_INT
ORDER BY CARRIER_CLM_NUM;
```
- Concatenates claimant name as `LST_NAME + " " + FST_NAME + " " + MIDL_INT` (handled safely for nulls).
- Populates `preBilledAmt`, `preBillReviewFees`, `preRepricedPaidAmt`, `preTotalMccaPmtReq` in `batchReport`.

---

### Step 3: `rfrFactsMissingDatesStep` (`MissingDatesBatchReportMapper.java`)
Queries `MCCA_FAC_TMP_RFR_PAYLOG` for any paylog rows missing service start or end dates and stores them in `missingDatesReport` (`List<MissingDatesBatchReport>`):
```sql
SELECT
    CARRIER_CLM_NUM,
    CARRIER_CLMT_NUM,
    FST_NAME,
    LST_NAME,
    MIDL_INT,
    PAY_CD,
    CHK_NUM,
    CHK_DT,
    PAYEE_OR_PRVDR,
    BILLED_AMT,
    BILL_REVIEW_FEES,
    REP_PAID_AMT,
    TOT_MCCA_PMT_REQ
FROM MCCA_FAC_TMP_RFR_PAYLOG
WHERE STRT_DATE IS NULL OR END_DT IS NULL;
```

---

### Step 4: `rfrFactsHeaderStep` (`RfrFactsHeaderProcessor.java`, `RFRValidator.java`, `DataValidator.java`)
Reads every header from `MCCA_FAC_TMP_RFR`:
```sql
SELECT
    TXN_ID, UNIQUE_ID, REC_TYPE, CARRIER_ID, CARRIER_CLM_NUM, CARRIER_CLMT_NUM,
    MCCA_CLM_NUM, BILL_SEQ_NUM, INS_FST_NAME, INS_MIDL_INIT, INS_LST_NAME,
    ADJ_NAME, LOSS_DT, CLMT_FST_NAME, CLMT_MIDL_INIT, CLMT_LST_NAME,
    TOT_AMT_BILLED, TOT_BILL_RVIEW_FEES, TOT_MCCA_PMT_REQ, X_COMPANION_CLM_IND,
    X_COMPANION_CLM_NUM, CRT_DTTM, CRT_USER_ID, MDFD_DTTM, MDFD_USER_ID,
    TRANS_SENT_DT, STATUS, ERR_ELE_LIST, CLM_TYPE, CHNG_RSN_DESC, DEDUCTIBLE_AMT
FROM MCCA_FAC_TMP_RFR;
```

#### Complete Matrix of Step 4 Validations & Processing Rules (`RfrFactsHeaderProcessor`):
1. **Unique Key Generation**:
   - Generates `uniqueKey = rfr.getCarrierClaimNumber().trim() + DateFormat("yyyyMMdd").format(new Date())`.
   - Sets `rfr.setUniqueKey(uniqueKey)` and `rfr.setClaimType("FACTS")`.
2. **Auto-Billing Exception Check (`getAutoBillingException`)**:
   - Queries `MCCA_EXCEPTION`:
     ```sql
     SELECT COUNT(*) FROM mcca.mcca_exception
     WHERE carrier_clm_num = ? AND carrier_clmt_num = ?
       AND exception_code = '3' AND exception_value = 'Y';
     ```
   - If `COUNT(*) > 0`: sets `pendingStatus = true`.
3. **Previous RFR Pending Check (`isPreviousRfrSubmitted`)**:
   - Queries `MCCA_RFR` for the latest `TXN_ID` per `UNIQUE_ID` for `CARRIER_CLM_NUM` where `STATUS = 'PN'`.
   - If `COUNT(*) > 0`: sets `pendingStatus = true`.
4. **Header Validation (`RFRValidator.validate(rfr)` & `DataValidator`)**:
   - Checks `totalMccaPaymentReq > (totalAmtBilled + totalBillReviewFees)`.
   - Checks `crossCompanionClaimNumber != null && !isEmpty()`.
   - Checks `billSequenceNumber` in `("1", "001")`.
   - Checks `DataValidator.isNull(rfr.getMccaClaimNumber())` -> if null/empty, sets `pendingStatus = true`, appends `"mccaClaimNumber"`.
   - Checks `DataValidator.isNull(rfr.getInsuredFirstName())` AND `DataValidator.isNull(rfr.getInsuredLastName())` -> if both null/empty, sets `pendingStatus = true`, appends `"insuredFirstName,insuredLastName"`.
5. **Paylog & CPT Level Validations (for each paylog in `MCCA_FAC_TMP_RFR_PAYLOG` where `CARRIER_CLM_NUM = ?`)**:
   - Assigns `rfrDetail.setUniqueKey(uniqueKey)` and `rfrDetail.setClaimType("FACTS")`.
   - Fetches child CPT records from `MCCA_FAC_TMP_RFR_PAYLOG_CPT` (`WHERE CARRIER_CLM_NUM = ? AND CARRIER_PAYLOG_ID = ?`).
   - **`isBillAmountValid`**: `billAmount > 0 && totalMccaPaymentReq > billAmount`.
   - **`isCorrection`**: `payeeOrProvider` equals `"CORRECTIONS"` or `"SAL/SUB RECEIPT"` -> sets `correctionsIndicator = "Y"`, `pendingStatus = true`, appends `"payeeOrProvider"`.
   - **`isServiceDatesValid`**: If `serviceStartDate == null || serviceEndDate == null` -> sets `pendingStatus = true`, appends `"serviceStartDate,serviceEndDate"`. Else if `serviceStartDate.after(serviceEndDate)` -> sets `pendingStatus = true`, appends `"serviceStartDate"`.
   - **Mandatory String Fields (`DataValidator.isNull`)**:
     - `checkNumber` null/empty -> appends `"checkNumber"`.
     - `payCode` null/empty -> appends `"payCode"`.
     - `payeeOrProvider` null/empty -> appends `"payeeOrProvider"`.
     - `serviceDescription` null/empty -> appends `"serviceDescription"`.
   - **`isBillTypeValid`**: `billType` in `("MISC", "1500", "UB04")` and if `serviceEndDate < rfrCptEffectiveDate`, `billType` must be `"MISC"`.
   - **`isServiceFacilityZipValid`**: If `billType` in `("1500", "UB04")`, `serviceFacilityZipcode` must not be empty.
   - **`isCptRequired` & `isCptListValid`**: If `billType` in `("1500", "UB04")`, CPT list must be non-empty and pass all CPT field rules.
   - **March 2022 Validations**: `validateTINNPI`, `validateUBBillTypeField`, `validateCPTCodes`, `validateNonMandatoryCPTCodes`, `validateRevenueCodes`, `validatePayCodeBillType`.
6. **MMS REST API Submission**:
   - If `pendingStatus == false`:
     - Calls `RfrRestMapper` + `RfrJsonBuilder` + `RfrRestClient` (`POST /api/v1/Claim/Rfr`).
     - If HTTP 200 / no errors: sets `statusIndicator = "SB"` and `transactionSentDate = new Date()`.
     - If error response: sets `statusIndicator = "PN"` and `submitErrMsg = err[:740]`.
   - If `pendingStatus == true`:
     - Sets `statusIndicator = "PN"`.
7. **Post-Header Database Updates (`MCCA_LAST_BILL_DATE`, `MCCA_REMARKS`, `MCCA_RFR_PAYLOG`, `MCCA_RFR`)**:
   - **`updateLastBillingDate`**:
     - If `rfr.getChangeReasonDescription()` equals `"Fall Below"` (case-insensitive):
       ```sql
       UPDATE mcca.mcca_last_bill_date
       SET last_bill_dt = SYSDATE, mdfd_dttm = SYSDATE, fall_back_ind = 'Y'
       WHERE carrier_clm_num = ? AND carrier_clmt_num = ?;
       ```
       And inserts a remark into `MCCA_REMARKS`:
       ```sql
       INSERT INTO mcca.mcca_remarks (REMARK_SEQ_NUM, UNIQUE_ID, REMARKS, CRT_DTTM, CRT_USER_ID, MDFD_DTTM, MDFD_USER_ID)
       VALUES (mcca.mcca_remark_seq.NEXTVAL, :carrierClaimNumber || '-' || :carrierClaimantNumber, 'RFR Fall Below', SYSDATE, 'BATCH', SYSDATE, 'BATCH');
       ```
     - Else:
       ```sql
       UPDATE mcca.mcca_last_bill_date
       SET last_bill_dt = SYSDATE, mdfd_dttm = SYSDATE
       WHERE carrier_clm_num = ? AND carrier_clmt_num = ?;
       ```
   - Writes all paylogs for the header into `MCCA_RFR_PAYLOG` (`RFRPayLogWriter`).
   - Writes the header into `MCCA_RFR` (`RFRWriter`).

---

### Step 5: `rfrFactsDetailCptStep` (`RfrFactsDetailCptProcessor.java`)
Reads all rows from `MCCA_FAC_TMP_RFR_PAYLOG_CPT`, sets `uniqueKey = carrierClaimNumber.trim() + yyyyMMdd`, and inserts them into `MCCA_RFR_PAYLOG_CPT` via `RFRPayLogCptWriter`.

---

### Step 6: `rfrFactsPostStep` (`RfrFactsPaylogPostProcessor.java` & `RFRFactsPayLogPostRowMapper.java`)
Executes the post-processing aggregation query joining `MCCA_RFR`, `MCCA_RFR_PAYLOG`, and `MCCA_FAC_TMP_RFR`:
```sql
SELECT
    RFR.CARRIER_CLM_NUM,
    RFR.STATUS,
    RFR.SUBMIT_ERR_MSG,
    SUM(PAYLOG.BILLED_AMT) AS BILLED_AMT,
    SUM(PAYLOG.BILL_REVIEW_FEES) AS BILL_REVIEW_FEES,
    SUM(PAYLOG.REP_PAID_AMT) AS REP_PAID_AMT,
    SUM(PAYLOG.TOT_MCCA_PMT_REQ) AS TOT_MCCA_PMT_REQ
FROM MCCA_RFR RFR, MCCA_RFR_PAYLOG PAYLOG, MCCA_FAC_TMP_RFR TMPRFR
WHERE RFR.UNIQUE_ID = PAYLOG.UNIQUE_ID
  AND RFR.CARRIER_CLM_NUM = TMPRFR.CARRIER_CLM_NUM
  AND RFR.TXN_ID IN (
      SELECT MAX(RFR2.TXN_ID) FROM MCCA_RFR RFR2 WHERE RFR2.UNIQUE_ID = RFR.UNIQUE_ID
  )
GROUP BY RFR.CARRIER_CLM_NUM, RFR.STATUS, RFR.SUBMIT_ERR_MSG
ORDER BY RFR.CARRIER_CLM_NUM;
```
- **Status Override Rule in `RFRFactsPayLogPostRowMapper`**:
  - If `SUBMIT_ERR_MSG != null && !SUBMIT_ERR_MSG.isEmpty()`, overrides `status` from `'PN'` to **`'RJ'`** (Rejected by MMS API) for the Excel report!
- Updates the matching `RFRBatchReport` entry in `batchReport` with `postBilledAmt`, `postBillReviewFees`, `postRepricedPaidAmt`, `postTotalMccaPmtReq`, and `status` (`SB`, `RJ`, or `PN`).

---

### Step 7: `rfrMail` (`RFRReportAttachedMailImpl.java`)
Generates two Excel files and sends them as email attachments:
1. **`rfrProcessingReport.xls`** (Sheet: `RFR Batch Processing Summary`):
   - **12 Columns**:
     `Claim Number | Claimant Number | Claimant Name | Pre Billed Amt | Pre Bill Review Fee | Pre Repriced Paid Amt | Pre Total MCCA Payment Req | Post Billed Amt | Post Bill Review Fee | Post Repriced Paid Amt | Post Total MCCA Payment Req | Status`
   - Includes a bottom `Total` row summing all 8 currency columns, plus summary counts for:
     - `Total Claims Count`
     - `Claims Submitted Count` (`status == "SB"`)
     - `Claims Rejected Count` (`status == "RJ"`)
     - `Claims Pended Count` (`status == "PN"`)
2. **`missingDatesReport.xls`** (Sheet: `Service Dates Missing Paylogs`):
   - **11 Columns**:
     `Claim Number | Claimant Number | Claimant Name | Pay Code | Check Number | Check Date | Payee/Provider | Billed Amt | Bill Review Fee | Repriced Paid Amt | Total MCCA Payment Req`

---

### Step 8: `clearTempTables` (`DBUtils.java`)
Cleans up all 3 FACTS RFR temporary tables:
```sql
DELETE FROM MCCA_FAC_TMP_RFR_PAYLOG_CPT;
DELETE FROM MCCA_FAC_TMP_RFR_PAYLOG;
DELETE FROM MCCA_FAC_TMP_RFR;
```
