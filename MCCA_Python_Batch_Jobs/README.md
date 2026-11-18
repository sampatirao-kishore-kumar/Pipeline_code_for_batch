# MCCA Python Batch Jobs — Backend Team Handover Package

This directory contains **5 standalone, self-contained Python batch job folders**, representing the 1:1 modernization of the 5 active Spring Batch Java jobs (`Current_Java_Btach_Code/MccaBatch/src`) targeting **Google Cloud AlloyDB for PostgreSQL** and the **MCCA MMS REST API**.

---

## Folder Structure (One Folder per Batch Job)

```text
MCCA_Python_Batch_Jobs/
├── README.md                                  # Master Handover & Configuration Guide
├── Job_1_bisCpsToMccaJob/                     # Job 1: CPS RFR Monthly Batch Job (10 Steps)
│   ├── main.py                                # Full 10-step orchestrator + Flat File Mappers
│   ├── validators.py                          # RFRValidator, DataValidator, FileValidator, March 2022 rules
│   ├── mms_client.py                          # OAuthClient, RfrRestMapper, RfrJsonBuilder, RfrRestClient
│   ├── dao.py                                 # AlloyDB SQL queries & writers (MCCA_CPS_TMP_RFR* -> MCCA_RFR*)
│   ├── requirements.txt
│   └── README.md
│
├── Job_2_meemicToMccaJob/                     # Job 2: Meemic RFR Monthly Batch Job (10 Steps)
│   ├── main.py                                # Full 10-step orchestrator + Meemic fee overrides + MeemicMailImpl
│   ├── validators.py                          # RFRValidator, DataValidator, FileValidator, March 2022 rules
│   ├── mms_client.py                          # OAuthClient, RfrRestMapper, RfrJsonBuilder, RfrRestClient
│   ├── dao.py                                 # AlloyDB SQL queries & writers (MCCA_MEEMIC_TMP_RFR* -> MCCA_RFR*)
│   ├── requirements.txt
│   └── README.md
│
├── Job_3_factsToMccaJob/                      # Job 3: FACTS RFR Monthly Batch Job (8 Steps)
│   ├── main.py                                # Full 8-step orchestrator
│   ├── ipm_facts_mapping_util.py              # Step 1: IPMFactsMappingUtil (jobType='rfr') & 9-table updates
│   ├── validators.py                          # RFRValidator, DataValidator, March 2022 rules
│   ├── mms_client.py                          # OAuthClient, RfrRestMapper, RfrJsonBuilder, RfrRestClient
│   ├── excel_reports.py                       # Step 7: RFRReportAttachedMailImpl (2 Excel reports + Email)
│   ├── dao.py                                 # Pre/Post readers, MCCA_EXCEPTION, MCCA_LAST_BILL_DATE, MCCA_REMARKS
│   ├── requirements.txt
│   └── README.md
│
├── Job_4_icnCsrToMccaJob/                     # Job 4: FACTS ICN & CSR Batch Job (Monthly / Daily / Weekly)
│   ├── main.py                                # BatchTypeDecider ('m', 'd', 'w') + Steps 1..11 orchestrator
│   ├── ipm_facts_mapping_util.py              # Step 1: IPMFactsMappingUtil (jobType='icn_csr') & 9-table updates
│   ├── validators.py                          # ICNValidator, CSRValidator, CHI Brain Injury & Phone formatters
│   ├── dao.py                                 # All 8 ICN/CSR writers & DAO queries
│   ├── requirements.txt
│   └── README.md
│
└── Job_5_mccaWriteOffFlatFileJob/             # Job 5: Month-End MCCA Write-Off Flat File Export Job (2 Steps)
    ├── main.py                                # WriteOffFlatFileMapper (9-char claim, 11-digit cents) + Export writer
    ├── requirements.txt
    └── README.md
```

---

## Shared Environment Variables (AlloyDB & MMS REST API)

| Environment Variable | Default / Description |
| :--- | :--- |
| `ALLOYDB_HOST` | AlloyDB instance IP or hostname |
| `ALLOYDB_PORT` | `5432` |
| `ALLOYDB_DB` | `mcca` |
| `ALLOYDB_USER` | AlloyDB username |
| `ALLOYDB_PASSWORD` | AlloyDB password (fetched from GCP Secret Manager in production) |
| `DB_SCHEMA` | `mcca` |
| `MMS_TOKEN_URL` | `https://adfs.micatastrophic.com/adfs/oauth2/token` |
| `MMS_RFR_SUBMIT_URL` | `https://carrierservices.hft2.mccatest.com/api/v1/Claim/Rfr` |
| `MMS_CLIENT_ID` | `64f2df60-0ea9-4def-befc-77e99ab6892d` |
| `MMS_CLIENT_SECRET` | `I1Do7yxl7AWdhAvo1pMhipQcB5b70DHxHtzRTUia` |
| `RFR_CPT_EFFECTIVE_DATE` | `2019-01-01` (`rfr.cpt.effective.date`) |
| `SMTP_HOST` / `SMTP_PORT` | SMTP relay host and port (`25`) for batch completion emails |
