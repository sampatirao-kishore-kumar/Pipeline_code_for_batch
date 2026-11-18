# Job 2 Specification: `meemicToMccaJob` (Meemic RFR Monthly Batch Job)

## 1. Executive Summary & Job Overview
| Attribute | Details |
| :--- | :--- |
| **Job Name / ID** | `meemicToMccaJob` |
| **Source System** | **MEEMIC** (Meemic Insurance Company — Flat Files delivered via FTP / GCS Landing Zone) |
| **Schedule / Frequency** | Monthly (Runs on the 1st of the month at `1:00 AM`) |
| **Spring XML Configs** | `jobs/rfrBatchJob.xml` (`<batch:job id="meemicToMccaJob">`), `common/beanInfo.xml` |
| **Input Flat Files** | 1. Header File (`${meemic.header.file.name}` — 19 semicolon-delimited columns)<br>2. Detail File (`${meemic.detail.file.name}` — 66 semicolon-delimited columns containing `BIL*` and `CPT*` lines) |
| **Staging / Temp Tables** | `MCCA_MEEMIC_TMP_RFR`, `MCCA_MEEMIC_TMP_RFR_PAYLOG`, `MCCA_MEEMIC_TMP_RFR_PAYLOG_CPT` |
| **Main Target Tables** | `MCCA_RFR`, `MCCA_RFR_PAYLOG`, `MCCA_RFR_PAYLOG_CPT` |
| **External API Called** | **MCCA MMS REST API** — `POST /api/v1/Claim/Rfr` (Authenticated via ADFS OAuth2 `client_credentials`) |
| **Email Notifications** | `meemicSuccessMail` (Step 9 via `MeemicMailImpl.java` with Header & Paylog record counts) or `meemicRejectMail` (if Step 5 `FileValidator` fails) |

---

## 2. End-to-End Architecture & Step Execution Flow

`meemicToMccaJob` executes **10 sequential steps** (plus a conditional failure branch to `meemicRejectMailStep` if file cross-validation fails in Step 5):

```
[Step 1: clearMeemicTempTablesBeforeProcess]
       │ (Deletes all rows from MCCA_MEEMIC_TMP_RFR, MCCA_MEEMIC_TMP_RFR_PAYLOG, MCCA_MEEMIC_TMP_RFR_PAYLOG_CPT)
       ▼
[Step 2: rfrHeaderMeemicToDbStep]
       │ (Reads Meemic Header File -> RfrHeaderFieldSetMapper -> RfrHeaderBisToDbProcessor [claimType='MEEMIC'] -> Inserts into MCCA_MEEMIC_TMP_RFR)
       ▼
[Step 3: rfrDetailMeemicToDbStep]
       │ (Reads Meemic Detail File 'BIL*' lines -> RfrDetailFieldSetMapper -> RfrDetailBisToDbProcessor [claimType='MEEMIC'] -> Inserts into MCCA_MEEMIC_TMP_RFR_PAYLOG)
       ▼
[Step 4: rfrDetailCptMeemicToDbStep]
       │ (Reads Meemic Detail File 'CPT*' lines -> RfrDetailCptFieldSetMapper -> RfrDetailCptBisToDbProcessor -> Inserts into MCCA_MEEMIC_TMP_RFR_PAYLOG_CPT)
       ▼
[Step 5: validateMeemicFiles] (FileValidator.java)
       ├──► [Status = FAILED] ──► [meemicRejectMailStep] (Sends file failure email & halts job)
       │
       ▼ [Status = COMPLETED]
[Step 6: rfrMeemicHeaderStep] (RfrHeaderProcessor.java)
       │ (Reads MCCA_MEEMIC_TMP_RFR + Paylogs + CPTs -> Runs RFRValidator & March 2022 Rules -> Calls MMS API if valid -> Inserts into MCCA_RFR)
       ▼
[Step 7: rfrMeemicDetailStep]
       │ (Copies all rows from MCCA_MEEMIC_TMP_RFR_PAYLOG -> MCCA_RFR_PAYLOG)
       ▼
[Step 8: rfrMeemicDetailCptStep]
       │ (Copies all rows from MCCA_MEEMIC_TMP_RFR_PAYLOG_CPT -> MCCA_RFR_PAYLOG_CPT)
       ▼
[Step 9: meemicSuccessMailStep] (MeemicMailImpl.java)
       │ (Queries MCCA_MEEMIC_TMP_RFR & MCCA_MEEMIC_TMP_RFR_PAYLOG counts and sends summary email)
       ▼
[Step 10: clearMeemicTempTables]
       │ (Cleans up MCCA_MEEMIC_TMP_RFR, MCCA_MEEMIC_TMP_RFR_PAYLOG, MCCA_MEEMIC_TMP_RFR_PAYLOG_CPT)
```

---

## 3. Meemic-Specific Business Rules vs. CPS (`bisCpsToMccaJob`)

| # | Component / Class | Meemic-Specific Rule in Java Code |
| :--- | :--- | :--- |
| **1** | `RfrHeaderBisToDbProcessor.java` (Step 2) | Because `claimType` is `"MEEMIC"` (`BatchConstants.MEEMIC_CLAIM_TYPE`), **after** running `RFRValidator.validate(rfr)` (which checks `totalMccaPaymentReq > totalAmtBilled + totalBillReviewFees`), the processor forces **`rfr.setTotalBillReviewFees(0.0)`** before inserting into `MCCA_MEEMIC_TMP_RFR`. |
| **2** | `RfrDetailBisToDbProcessor.java` (Step 3) | When `claimType` is `"MEEMIC"`, the processor forces three fee/discount fields to zero before inserting into `MCCA_MEEMIC_TMP_RFR_PAYLOG`:<br>• **`rfrDetail.setBillReviewFees(0.0)`**<br>• **`rfrDetail.setPpoFees(0.0)`**<br>• **`rfrDetail.setPpoOrOtherNegotiatedDiscount(0.0)`** |
| **3** | `MeemicMailImpl.java` (Step 9) | Queries staging table counts before Step 10 deletes them:<br>• `SELECT COUNT(1) FROM MCCA_MEEMIC_TMP_RFR` (`headerRecordCount`)<br>• `SELECT COUNT(1) FROM MCCA_MEEMIC_TMP_RFR_PAYLOG` (`paylogRecordCount`)<br>And appends to the email body:<br>`Total number of Header records processed : <headerRecordCount>`<br>`Total number of Paylog records processed : <paylogRecordCount>` |
| **4** | Staging Table Names | Uses `MCCA_MEEMIC_TMP_RFR`, `MCCA_MEEMIC_TMP_RFR_PAYLOG`, and `MCCA_MEEMIC_TMP_RFR_PAYLOG_CPT` (and sets `CLM_TYPE = 'MEEMIC'` in `MCCA_RFR` and `MCCA_RFR_PAYLOG`). |

---

## 4. Detailed Step-by-Step Business Logic, Conditions & SQL Queries

### Step 1: `clearMeemicTempTablesBeforeProcess` (`DBUtils.java`)
Deletes all rows from `MCCA_MEEMIC_TMP_RFR_PAYLOG_CPT`, `MCCA_MEEMIC_TMP_RFR_PAYLOG`, and `MCCA_MEEMIC_TMP_RFR`.

### Step 2: `rfrHeaderMeemicToDbStep` (`RfrHeaderBisToDbProcessor.java` & `RFRWriter.java`)
1. Sets `rfr.recordType = "RFR"` and `rfr.claimType = "MEEMIC"`.
2. Runs `RFRValidator.validate(rfr)` (`isTotalBillAmountValid`, `isCrossCompanionClaim`, `isInitial`).
3. Forces `rfr.setTotalBillReviewFees(0.0)`.
4. Verifies `carrierId != 0` and `!carrierClaimNumber.isEmpty()`, stores in `meemicHeaderMap`, and inserts into `MCCA_MEEMIC_TMP_RFR`.

### Step 3: `rfrDetailMeemicToDbStep` (`RfrDetailBisToDbProcessor.java` & `RFRPayLogWriter.java`)
1. Processes `BIL*` lines from the 66-column Detail flat file.
2. Verifies `meemicHeaderMap.containsKey(uniqueKey)`, inherits `carrierClaimNumber` and `carrierId`.
3. Forces `billReviewFees = 0.0`, `ppoFees = 0.0`, and `ppoOrOtherNegotiatedDiscount = 0.0`.
4. Truncates `payeeOrProvider` to `50` characters, generates `paylogUniqueId` from `MCCA_PAYLOG_ID_SEQ.NEXTVAL`, caches in `meemicPaylogMap`, and inserts into `MCCA_MEEMIC_TMP_RFR_PAYLOG`.

### Step 4: `rfrDetailCptMeemicToDbStep` (`RfrDetailCptBisToDbProcessor.java` & `RFRPayLogCptWriter.java`)
Processes `CPT*` lines, links `carrierPaylogId` via `meemicPaylogMap` using `uniqueKey-eobId-billType-eobRevisionNum-checkNumberKey-alphabetKey`, and inserts into `MCCA_MEEMIC_TMP_RFR_PAYLOG_CPT`.

### Step 5: `validateMeemicFiles` (`FileValidator.java`)
Cross-validates Header, Paylog, and CPT staging tables. Routes to `meemicRejectMailStep` on failure.

### Step 6: `rfrMeemicHeaderStep` (`RfrHeaderProcessor.java`, `RFRValidator.java`, `RfrRestClient.java`)
Validates each header, paylog, and CPT line against all 12 RFR validation rules (including March 2022 `TIN`/`NPI`, `ubBillType`, `cptCode`, `revenueCode`, and `payCode`/`billType` cross-checks). Submits valid claims (`pendingStatus == false`) to `POST /api/v1/Claim/Rfr` (`STATUS = 'SB'` on HTTP 2xx, or `'PN'` + `SUBMIT_ERR_MSG` on failure) and inserts into `MCCA_RFR`.

### Step 7: `rfrMeemicDetailStep`
Copies all rows from `MCCA_MEEMIC_TMP_RFR_PAYLOG` into `MCCA_RFR_PAYLOG`.

### Step 8: `rfrMeemicDetailCptStep`
Copies all rows from `MCCA_MEEMIC_TMP_RFR_PAYLOG_CPT` into `MCCA_RFR_PAYLOG_CPT`.

### Step 9: `meemicSuccessMailStep` (`MeemicMailImpl.java`)
Queries `MCCA_MEEMIC_TMP_RFR` and `MCCA_MEEMIC_TMP_RFR_PAYLOG` counts and sends completion email.

### Step 10: `clearMeemicTempTables` (`DBUtils.java`)
Clears `MCCA_MEEMIC_TMP_RFR_PAYLOG_CPT`, `MCCA_MEEMIC_TMP_RFR_PAYLOG`, and `MCCA_MEEMIC_TMP_RFR`.
