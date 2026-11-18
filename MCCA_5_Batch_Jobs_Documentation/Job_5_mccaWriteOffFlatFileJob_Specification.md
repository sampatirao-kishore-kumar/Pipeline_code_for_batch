# Job 5 Specification: `mccaWriteOffFlatFileJob` (MCCA Month-End Write-Off Flat File Export Job)

## 1. Executive Summary & Job Overview
| Attribute | Details |
| :--- | :--- |
| **Job Name / ID** | `mccaWriteOffFlatFileJob` |
| **Source System** | **MCCA Database (`MCCA_WRITE_OFF` table in AlloyDB)** |
| **Schedule / Frequency** | Monthly (Month-End run on the 28th of the month at `11:00 PM` with parameter `batchDate=YYYYMMDD`) |
| **Spring XML Configs** | `jobs/mccaWriteOffFlatFileJob.xml` (`<batch:job id="mccaWriteOffFlatFileJob">`), `common/writeOffFlatFileBeanInfo.xml` |
| **Source Database Table** | `MCCA_WRITE_OFF` |
| **Output Flat File** | `${writeOff.flatfile.path}/MCCAWriteOffExport_${batchDate}.txt` (Comma-delimited `.txt` export file with 4 fields per line) |
| **Java Components** | `WriteOff.java` (DTO), `WriteOffFlatFileMapper.java` (`RowMapper<WriteOff>`) |
| **Email Notification** | `writeOffMail` (`MailImpl.java` — runs in Step 2 after flat file generation) |

---

## 2. End-to-End Architecture & Step Execution Flow

`mccaWriteOffFlatFileJob` executes **2 sequential steps**:

```
[Step 1: createFlatFileStep]
       │ (Executes writeOffJdbcCursorReader on MCCA_WRITE_OFF filtered by SUBSTR(:batchDate, 0, 6)
       │  -> Formats fields via WriteOffFlatFileMapper.java
       │  -> Writes comma-delimited lines to MCCAWriteOffExport_<batchDate>.txt via writeOffFlatFileItemWriter)
       ▼
[Step 2: writeOffMailStep] (MailImpl.java)
       │ (Sends email notification confirming Write-Off flat file generation)
```

---

## 3. Detailed Step-by-Step Business Logic, Formatting Rules & SQL Query

### Step 1: `createFlatFileStep` (`writeOffFlatFileBeanInfo.xml` & `WriteOffFlatFileMapper.java`)

#### 3.1 Input SQL Query (`writeOffJdbcCursorReader`)
Reads all write-off transactions from `MCCA_WRITE_OFF` whose `SUBMITTED_DATE` year-month (`YYYYMM`) matches the first 6 characters of the job parameter `batchDate` (`#{jobParameters['batchDate']}`):
```sql
SELECT
    CARRIER_CLM_NUM,
    COVERAGE_TYPE,
    WRITE_OFF_AMOUNT,
    WRITE_OFF_TYPE,
    SUBMITTED_BY,
    TO_CHAR(SUBMITTED_DATE, 'MMYYYY') AS SUBMITTED_DATE
FROM MCCA_WRITE_OFF
WHERE TO_CHAR(SUBMITTED_DATE, 'YYYYMM') = SUBSTR(:batchDate, 0, 6)
ORDER BY WRITE_OFF_SEQ_ID;
```
*(In AlloyDB PostgreSQL, `SUBSTR(:batchDate, 1, 6)` is used as `SUBSTR` is 1-indexed in PostgreSQL, whereas Oracle treats `0` and `1` identically).*

#### 3.2 Field Formatting & Padding Rules (`WriteOffFlatFileMapper.java`)
`WriteOffFlatFileMapper` applies exact fixed-width padding and decimal scaling rules to each row returned by the query:

| Field | Database Column | Java Property (`WriteOff.java`) | Formatting / Padding Rule in `WriteOffFlatFileMapper.java` | Included in Output File? |
| :--- | :--- | :--- | :--- | :--- |
| **1. Claim Number** | `CARRIER_CLM_NUM` | `claimNumber` | Right-padded with spaces to `9` characters (`%-9s`), or truncated to first `9` characters if `length > 9`:<br>`String.format("%-9s", claimNumber)` | **Yes** (Field 1) |
| **2. Coverage Type** | `COVERAGE_TYPE` | `coverageType` | Trimmed string (e.g., `"PIP"`) | **Yes** (Field 2) |
| **3. Write-Off Amount** | `WRITE_OFF_AMOUNT` | `amount` | 1. Rounded to 2 decimal places (`#.00`).<br>2. Multiplied by `100` to remove decimal point (cents representation, `Math.round(amount * 100)`).<br>3. If `amount >= 0`: Left-padded with leading zeroes to **11 digits** (`%011d`, e.g., `123.45` -> `"00000012345"`).<br>4. If `amount < 0`: Prefix `"-"` followed by 10 zero-padded digits (`"-" + %010d`, total length 11, e.g., `-123.45` -> `"-0000012345"`). | **Yes** (Field 3) |
| **4. Write-Off Type** | `WRITE_OFF_TYPE` | `writeOffType` | Trimmed string | **Yes** (Field 4) |
| **5. Submitted By** | `SUBMITTED_BY` | `userId` | Right-padded with spaces to `5` characters (`%-5s`), or truncated to first `5` characters if `length > 5` | Mapped on DTO (`BeanWrapperFieldExtractor` extracts the 4 fields below) |
| **6. Submitted Date** | `TO_CHAR(SUBMITTED_DATE, 'MMYYYY')` | `submittedDate` | 6-character string `MMYYYY` | Mapped on DTO |

#### 3.3 Output Flat File Specification (`writeOffFlatFileItemWriter`)
- **Output Path**: `file:${writeOff.flatfile.path}/MCCAWriteOffExport_#{jobParameters['batchDate']}.txt`
- **Line Aggregator**: `DelimitedLineAggregator`
- **Delimiter**: Comma (`,`)
- **Extracted Fields (`BeanWrapperFieldExtractor`)**:
  ```xml
  <property name="names" value="claimNumber,coverageType,amount,writeOffType" />
  ```
- **Sample Output Line**:
  ```text
  JA159278 ,PIP,00000012345,WO
  ```

---

### Step 2: `writeOffMailStep` (`MailImpl.java`)
Sends a completion email via `JavaMailSender` with the configured `writeOff.mail.from`, `writeOff.mail.to`, `writeOff.mail.subject`, and `writeOff.mail.body`.
