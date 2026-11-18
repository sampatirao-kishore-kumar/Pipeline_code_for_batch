# Job 1 Specification: `bisCpsToMccaJob` (CPS RFR Monthly Batch Job)

## 1. Executive Summary & Job Overview
| Attribute | Details |
| :--- | :--- |
| **Job Name / ID** | `bisCpsToMccaJob` |
| **Source System** | **CPS** (Claim Payment System — Flat Files delivered via FTP / GCS Landing Zone) |
| **Schedule / Frequency** | Monthly (Runs on the 1st of the month at `12:45 AM`) |
| **Spring XML Configs** | `jobs/rfrBatchJob.xml` (`<batch:job id="bisCpsToMccaJob">`), `common/beanInfo.xml` |
| **Input Flat Files** | 1. Header File (`${bis.cps.header.file.name}` — 19 semicolon-delimited columns)<br>2. Detail File (`${bis.cps.detail.file.name}` — 66 semicolon-delimited columns containing `BIL*` and `CPT*` lines) |
| **Staging / Temp Tables** | `MCCA_CPS_TMP_RFR`, `MCCA_CPS_TMP_RFR_PAYLOG`, `MCCA_CPS_TMP_RFR_PAYLOG_CPT` |
| **Main Target Tables** | `MCCA_RFR`, `MCCA_RFR_PAYLOG`, `MCCA_RFR_PAYLOG_CPT` |
| **External API Called** | **MCCA MMS REST API** — `POST /api/v1/Claim/Rfr` (Authenticated via ADFS OAuth2 `client_credentials`) |
| **Email Notifications** | `cpsSuccessMail` (Step 9) or `cpsRejectMail` (if Step 5 `FileValidator` fails) via `MailImpl.java` |

---

## 2. End-to-End Architecture & Step Execution Flow

`bisCpsToMccaJob` executes **10 sequential steps** (plus a conditional failure branch to `cpsRejectMailStep` if file cross-validation fails in Step 5):

```
[Step 1: clearCpsTempTablesBeforeProcess]
       │ (Deletes all rows from MCCA_CPS_TMP_RFR, MCCA_CPS_TMP_RFR_PAYLOG, MCCA_CPS_TMP_RFR_PAYLOG_CPT)
       ▼
[Step 2: rfrHeaderBisCpsToDbStep]
       │ (Reads CPS Header File -> RfrHeaderFieldSetMapper -> RfrHeaderBisToDbProcessor -> Inserts into MCCA_CPS_TMP_RFR)
       ▼
[Step 3: rfrDetailBisCpsToDbStep]
       │ (Reads CPS Detail File 'BIL*' lines -> RfrDetailFieldSetMapper -> RfrDetailBisToDbProcessor -> Inserts into MCCA_CPS_TMP_RFR_PAYLOG)
       ▼
[Step 4: rfrDetailCptBisCpsToDbStep]
       │ (Reads CPS Detail File 'CPT*' lines -> RfrDetailCptFieldSetMapper -> RfrDetailCptBisToDbProcessor -> Inserts into MCCA_CPS_TMP_RFR_PAYLOG_CPT)
       ▼
[Step 5: validateCpsFiles] (FileValidator.java)
       ├──► [Status = FAILED] ──► [cpsRejectMailStep] (Sends file failure email & halts job)
       │
       ▼ [Status = COMPLETED]
[Step 6: rfrHeaderStep] (RfrHeaderProcessor.java)
       │ (Reads MCCA_CPS_TMP_RFR + Paylogs + CPTs -> Runs RFRValidator & March 2022 Rules -> Calls MMS API if valid -> Inserts into MCCA_RFR)
       ▼
[Step 7: rfrDetailStep]
       │ (Copies all rows from MCCA_CPS_TMP_RFR_PAYLOG -> MCCA_RFR_PAYLOG)
       ▼
[Step 8: rfrDetailCptStep]
       │ (Copies all rows from MCCA_CPS_TMP_RFR_PAYLOG_CPT -> MCCA_RFR_PAYLOG_CPT)
       ▼
[Step 9: cpsSuccessMailStep] (MailImpl.java)
       │ (Sends completion email notification)
       ▼
[Step 10: clearCpsTempTables]
       │ (Cleans up MCCA_CPS_TMP_RFR, MCCA_CPS_TMP_RFR_PAYLOG, MCCA_CPS_TMP_RFR_PAYLOG_CPT)
```

---

## 3. Input Flat File Layouts & Mappers

### 3.1 CPS Header Flat File (`rfrDelimitedLineTokenizer` & `RfrHeaderFieldSetMapper.java`)
- **Delimiter**: Semicolon (`;`)
- **Lines to Skip**: `1` (Header row skipped)
- **Total Columns**: `19` (`includedFields`: `0` through `18`)

| Col Index | Tokenizer Field Name | Java Field (`RFR.java`) | Data Type | Mapping / Parsing Rule in `RfrHeaderFieldSetMapper` |
| :--- | :--- | :--- | :--- | :--- |
| `0` | `lineType` | `lineType` | `String` | Trimmed string |
| `1` | `carrierId` | `carrierId` | `long` | `readLong("carrierId")` (Default `0` if empty; must be `!= 0`) |
| `2` | `carrierClaimNumber` | `carrierClaimNumber` | `String` | Trimmed string (Mandatory; cannot be empty) |
| `3` | `mccaClaimNumber` | `mccaClaimNumber` | `String` | Trimmed string |
| `4` | `billSequenceNumber` | `billSequenceNumber` | `String` | Trimmed string |
| `5` | `insuredFirstName` | `insuredFirstName` | `String` | Trimmed string |
| `6` | `insuredMiddleInit` | `insuredMiddleInit` | `String` | Trimmed string |
| `7` | `insuredLastName` | `insuredLastName` | `String` | Trimmed string |
| `8` | `AdjusterFirstName` | `adjusterName` | `String` | Concatenated with `AdjusterLastName`: `AdjusterFirstName + " " + AdjusterLastName` |
| `9` | `AdjusterLastName` | `adjusterName` | `String` | Appended to `AdjusterFirstName` |
| `10` | `dateOfLoss` | `dateOfLoss` | `Date` | Parsed using `yyyy-MM-dd` (`BatchConstants.RFR_DATE_FORMAT`) |
| `11` | `claimantFirstName` | `claimantFirstName` | `String` | Trimmed string |
| `12` | `claimantMiddleInit` | `claimantMiddleInit` | `String` | Trimmed string |
| `13` | `claimantLastName` | `claimantLastName` | `String` | Trimmed string |
| `14` | `totalAmtBilled` | `totalAmtBilled` | `double` | `Double.valueOf()` (Defaults to `0.00` if empty) |
| `15` | `totalBillReviewFees` | `totalBillReviewFees` | `double` | `Double.valueOf()` (Defaults to `0.00` if empty) |
| `16` | `totalMccaPaymentReq` | `totalMccaPaymentReq` | `double` | `Double.valueOf()` (Defaults to `0.00` if empty) |
| `17` | `uniqueKey` | `uniqueKey` | `String` | Trimmed string (Primary correlation key between Header, Paylog, and CPT) |
| `18` | `deductibleAmount` | `deductibleAmount` | `double` | `Double.valueOf()` (Defaults to `0.00` if empty) |

### 3.2 CPS Detail Flat File — `BIL*` Lines (`rfrBillDelimitedLineTokenizer` & `RfrDetailFieldSetMapper.java`)
- **Delimiter**: Semicolon (`;`)
- **Total Columns in File**: `66` (`0` through `65`)
- **Active Columns for `BIL*` Lines**: Columns `0` through `42` (`43` fields mapped when `lineType` starts with `"BIL"`, e.g., `"BILA"`, `"BILB"`). If `lineType` does not start with `"BIL"`, `RfrDetailBisToDbProcessor` returns `null` (skips the line).

| Col Index | Tokenizer Field Name | Java Field (`RfrDetail.java`) | Data Type | Mapping / Parsing Rule |
| :--- | :--- | :--- | :--- | :--- |
| `0` | `lineType` | `lineType` / `alphabetKey` | `String` / `char` | Must start with `"BIL"`. `alphabetKey = lineType.charAt(3)` (e.g. `'A'` from `"BILA"`) |
| `1` | `serviceStartDate` | `serviceStartDate` | `Date` | Parsed as `yyyy-MM-dd` |
| `2` | `serviceEndDate` | `serviceEndDate` | `Date` | Parsed as `yyyy-MM-dd` |
| `3` | `payCode` | `payCode` | `String` | Payment code (`HOSP`, `DRLB`, `REHA`, `RXSP`, `ACAG`, `RESI`, `EQUP`, `PROS`, `TRAN`, `CSMT`) |
| `4` | `numberOfHours` | `numberOfHours` | `long` | `Long.valueOf()` (Default `0`) |
| `5` | `checkNumber` | `checkNumber` / `checkNumberKey` | `String` | Check number string; also stored in `checkNumberKey` |
| `6` | `CheckIssuedDate` | `checkDate` | `Date` | Parsed as `yyyy-MM-dd` |
| `7` | `payeeOrProvider` | `payeeOrProvider` | `String` | Truncated to max `50` characters in `RfrDetailBisToDbProcessor` |
| `8` | `federalTIN` | `federalTIN` | `String` | Comma-separated `"TIN,NPI"` (e.g., `"123456789,1234567890"`) |
| `9` | `costShareAmount` | `costShareAmount` | `double` | `Double.valueOf()` (Default `0.00`) |
| `10` | `repricedPaidAmt` | `repricedPaidAmt` | `double` | `Double.valueOf()` (Default `0.00`) |
| `11` | `billReviewFees` | `billReviewFees` | `double` | `Double.valueOf()` (Default `0.00`) |
| `12` | `ppoFees` | `ppoFees` | `double` | `Double.valueOf()` (Default `0.00`) |
| `13` | `totalMccaPaymentReq` | `totalMccaPaymentReq` | `double` | `Double.valueOf()` (Default `0.00`) |
| `14` | `billAmount` | `billAmount` | `double` | `Double.valueOf()` (Default `0.00`) |
| `15` | `ppoOrOtherNegotiatedDiscount` | `ppoOrOtherNegotiatedDiscount` | `double` | `Double.valueOf()` (Default `0.00`) |
| `16` | `serviceDescription` | `serviceDescription` | `String` | Service description text |
| `17` | `carrierCheckTotal` | `carrierCheckTotal` | `double` | `Double.valueOf()` (Default `0.00`) |
| `18` | `uniqueKey` | `uniqueKey` | `String` | Links to Header `UNIQUE_ID` |
| `19` | `rxIndicator` | `rxIndicator` | `String` | Prescription indicator |
| `20` | `ndcNumber` | `ndcNumber` | `String` | National Drug Code |
| `21` | `daysSupply` | `daysSupply` | `long` | `Long.valueOf()` (Default `0`) |
| `22` | `quantity` | `quantity` | `long` | `Long.valueOf()` (Default `0`) |
| `23` | `dispenseAsWrittenCode` | `dispenseAsWrittenCode` | `String` | DAW code |
| `24` | `PrescriberNPI` | `prescriberNpi` | `String` | Prescriber NPI |
| `25` | `drgCode` | `drgCode` | `String` | DRG code |
| `26` | `patientStatus` | `patientStatus` | `String` | Patient status code |
| `27` | `admitDate` | `admitDate` | `Date` | Parsed as `yyyy-MM-dd` |
| `28` | `dischargeDate` | `dischargeDate` | `Date` | Parsed as `yyyy-MM-dd` |
| `29` | `ubBillType` | `ubBillType` | `String` | UB04 Bill Type (3 digits, or 4 digits starting with `0`) |
| `30` | `serviceFacilityZipcode` | `serviceFacilityZipcode` | `String` | Facility ZIP code |
| `31` | `admissionSource` | `admissionSource` | `String` | Admission source |
| `32`–`38` | `Icd1`–`Icd7` | `icd1`–`icd7` | `String` | ICD diagnosis codes 1 through 7 |
| `39` | `eobId` | `eobId` | `String` | EOB Identifier |
| `40` | `billType` | `billType` | `String` | `"1500"`, `"UB04"`, or `"MISC"` |
| `41` | `eobRevisionNum` | `eobRevisionNum` | `long` | `Long.valueOf()` (Default `0`) |
| `42` | `admissionType` | `admissionType` | `String` | Admission type |

### 3.3 CPS Detail Flat File — `CPT*` Lines (`rfrCptDelimitedLineTokenizer` & `RfrDetailCptFieldSetMapper.java`)
- **Active Columns for `CPT*` Lines**: Columns `0, 5, 18, 39, 40, 41, 43..65` (`29` fields mapped when `lineType` starts with `"CPT"`, e.g., `"CPTA"`, `"CPTB"`).

| Col Index | Tokenizer Field Name | Java Field (`RfrDetailCpt.java`) | Data Type | Mapping / Parsing Rule |
| :--- | :--- | :--- | :--- | :--- |
| `0` | `lineType` | `lineType` / `alphabetKey` | `String` / `char` | Must start with `"CPT"`. `alphabetKey = lineType.charAt(3)` |
| `5` | `checkNumber` | `checkNumberKey` | `String` | Used to build parent Paylog lookup key |
| `18` | `uniqueKey` | `uniqueKey` | `String` | Links to Header `UNIQUE_ID` |
| `39` | `eobId` | `eobId` | `String` | EOB Identifier |
| `40` | `billType` | `billType` | `String` | `"1500"`, `"UB04"`, or `"MISC"` |
| `41` | `eobRevisionNum` | `eobRevisionNum` | `long` | `Long.valueOf()` (Default `0`) |
| `43` | `serviceStartDate` | `serviceStartDate` | `Date` | Parsed as `yyyy-MM-dd` |
| `44` | `serviceEndDate` | `serviceEndDate` | `Date` | Parsed as `yyyy-MM-dd` |
| `45` | `serviceLocation` | `serviceLocation` | `String` | Place of Service (required for `1500`) |
| `46` | `cptCode` | `cptCode` | `String` | CPT / HCPCS Procedure Code |
| `47`–`50` | `Modifier1`–`Modifier4` | `modifier1`–`modifier4` | `String` | CPT Modifiers 1 to 4 |
| `51` | `serviceUnits` | `serviceUnits` | `long` | `Long.valueOf()` (Default `0`) |
| `52` | `totalCharges` | `totalCharges` | `double` | `Double.valueOf()` (Default `0.00`) |
| `53` | `totalChargesCarrierApproved` | `totalChargesCarrierApproved` | `double` | `Double.valueOf()` (Default `0.00`) |
| `54` | `revenueCode` | `revenueCode` | `String` | Revenue Code (required for `UB04`) |
| `55` | `prescriberNpi` | `prescriberNpi` | `String` | Prescriber NPI |
| `56`–`65` | `Icd1`–`Icd10` | `icd1`–`icd10` | `String` | CPT-level ICD diagnosis codes 1 through 10 |

---

## 4. Detailed Step-by-Step Business Logic, Conditions & SQL Queries

### Step 1: `clearCpsTempTablesBeforeProcess` (`DBUtils.java`)
Executes 3 `DELETE` statements to ensure a clean staging state before reading the CPS flat files:
```sql
DELETE FROM MCCA_CPS_TMP_RFR_PAYLOG_CPT;
DELETE FROM MCCA_CPS_TMP_RFR_PAYLOG;
DELETE FROM MCCA_CPS_TMP_RFR;
```

### Step 2: `rfrHeaderBisCpsToDbStep` (`RfrHeaderBisToDbProcessor.java` & `RFRWriter.java`)
1. Sets `rfr.recordType = "RFR"` and `rfr.claimType = "CPS"`.
2. Runs `RFRValidator.validate(rfr)`:
   - **Rule H1 (`isTotalBillAmountValid`)**: If `totalMccaPaymentReq > (totalAmtBilled + totalBillReviewFees)` -> `pendingStatus = true`, appends `"totalAmtBilled,totalMccaPaymentReq"`.
   - **Rule H2 (`isCrossCompanionClaim`)**: If `crossCompanionClaimNumber` non-empty -> `crossCompanionIndicator = "Y"`, `pendingStatus = true`, appends `"crossCompanionClaimNumber"`; else `"N"`.
   - **Rule H3 (`isInitial`)**: If `billSequenceNumber` in `("001", "1")` -> `pendingStatus = true`, appends `"billSequenceNumber"`.
   - Sets `statusIndicator = "PN"` if `pendingStatus` else `"OK"`.
3. Verifies `carrierId != 0` and `!carrierClaimNumber.isEmpty()`, caches `headerMap.put(uniqueKey, rfr)`, and inserts into `MCCA_CPS_TMP_RFR`.

### Step 3: `rfrDetailBisCpsToDbStep` (`RfrDetailBisToDbProcessor.java` & `RFRPayLogWriter.java`)
1. Filters for `lineType.startsWith("BIL")`.
2. Verifies `headerMap.containsKey(uniqueKey)`, inherits `carrierClaimNumber` and `carrierId`, truncates `payeeOrProvider` to `50` characters, fetches `MCCA_PAYLOG_ID_SEQ.NEXTVAL` into `paylogUniqueId`, caches `paylogMap.put(uniqueKey-eobId-billType-eobRevisionNum-checkNumberKey-alphabetKey, paylogUniqueId)`, and inserts into `MCCA_CPS_TMP_RFR_PAYLOG`.

### Step 4: `rfrDetailCptBisCpsToDbStep` (`RfrDetailCptBisToDbProcessor.java` & `RFRPayLogCptWriter.java`)
1. Filters for `lineType.startsWith("CPT")`.
2. Verifies `headerMap.containsKey(uniqueKey)`, looks up `carrierPaylogId` from `paylogMap` using `uniqueKey-eobId-billType-eobRevisionNum-checkNumberKey-alphabetKey` (throws `UnexpectedInputException` if missing), and inserts into `MCCA_CPS_TMP_RFR_PAYLOG_CPT`.

### Step 5: `validateCpsFiles` (`FileValidator.java`)
Cross-validates all 3 staging tables:
- Every Header `UNIQUE_ID` must exist in `MCCA_CPS_TMP_RFR_PAYLOG` and vice versa.
- Every CPT `CARRIER_PAYLOG_ID` must exist as a `PAYLOG_UNIQUE_ID` in `MCCA_CPS_TMP_RFR_PAYLOG`.
- On failure -> routes to `cpsRejectMailStep` and halts job.

### Step 6: `rfrHeaderStep` (`RfrHeaderProcessor.java`, `RFRValidator.java`, `RfrRestClient.java`)
Reads every header from `MCCA_CPS_TMP_RFR`, loads its paylogs and CPT lines, runs all 12 validation rules (`isPreviousRfrSubmitted`, `RFRValidator.validate`, `isBillAmountValid`, `isCorrection`, `isBillTypeValid`, `isServiceFacilityZipValid`, `isCptRequired`, `isCptListValid`, `validateTINNPI`, `validateUBBillTypeField`, `validateCPTCodes`, `validateNonMandatoryCPTCodes`, `validateRevenueCodes`, `validatePayCodeBillType`).
- If `pendingStatus == false`, submits JSON payload to `POST /api/v1/Claim/Rfr` (`STATUS = 'SB'` on HTTP 2xx, or `'PN'` + `SUBMIT_ERR_MSG` on error).
- Inserts header into `MCCA_RFR`.

### Step 7: `rfrDetailStep`
Copies all rows from `MCCA_CPS_TMP_RFR_PAYLOG` into `MCCA_RFR_PAYLOG`.

### Step 8: `rfrDetailCptStep`
Copies all rows from `MCCA_CPS_TMP_RFR_PAYLOG_CPT` into `MCCA_RFR_PAYLOG_CPT`.

### Step 9: `cpsSuccessMailStep` (`MailImpl.java`)
Sends completion email notification.

### Step 10: `clearCpsTempTables` (`DBUtils.java`)
Deletes all rows from `MCCA_CPS_TMP_RFR_PAYLOG_CPT`, `MCCA_CPS_TMP_RFR_PAYLOG`, and `MCCA_CPS_TMP_RFR`.
