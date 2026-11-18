# MCCA 5 Active Batch Jobs — Technical Specification Documents

This folder contains the complete, job-by-job technical specification documents derived directly from the 85-file legacy Spring Batch Java codebase (`Current_Java_Btach_Code/MccaBatch/src`).

Each job is documented in its own standalone specification file (available in `.docx`, `.doc`, and `.md` formats):

| # | Batch Job ID | Source System | Schedule | Specification Documents |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **`bisCpsToMccaJob`** | CPS (FTP / GCS Flat Files) | Monthly (1st at 12:45 AM) | • `Job_1_bisCpsToMccaJob_Specification.docx`<br>• `Job_1_bisCpsToMccaJob_Specification.doc`<br>• `Job_1_bisCpsToMccaJob_Specification.md` |
| **2** | **`meemicToMccaJob`** | Meemic (FTP / GCS Flat Files) | Monthly (1st at 1:00 AM) | • `Job_2_meemicToMccaJob_Specification.docx`<br>• `Job_2_meemicToMccaJob_Specification.doc`<br>• `Job_2_meemicToMccaJob_Specification.md` |
| **3** | **`factsToMccaJob`** | FACTS (IICS Staging Tables) | Monthly (1st at 12:01 AM) | • `Job_3_factsToMccaJob_Specification.docx`<br>• `Job_3_factsToMccaJob_Specification.doc`<br>• `Job_3_factsToMccaJob_Specification.md` |
| **4** | **`icnCsrToMccaJob`** | FACTS (IICS Staging Tables) | Monthly (`'m'`), Daily (`'d'`), Weekly (`'w'`) | • `Job_4_icnCsrToMccaJob_Specification.docx`<br>• `Job_4_icnCsrToMccaJob_Specification.doc`<br>• `Job_4_icnCsrToMccaJob_Specification.md` |
| **5** | **`mccaWriteOffFlatFileJob`** | AlloyDB (`MCCA_WRITE_OFF`) | Month-End (28th at 11:00 PM) | • `Job_5_mccaWriteOffFlatFileJob_Specification.docx`<br>• `Job_5_mccaWriteOffFlatFileJob_Specification.doc`<br>• `Job_5_mccaWriteOffFlatFileJob_Specification.md` |

> **Scope Note**: Out of the 5 legacy sources (`Mitchell`, `FACTS`, `IPM`, `CPS`, `Meemic`), `Mitchell` is out of scope and the standalone `bisIpmToMccaJob` is retired because IPM is decommissioned. However, Step 1 (`IPMFactsMappingUtil`) inside `factsToMccaJob` and `icnCsrToMccaJob` is retained to map historical converted IPM claim and claimant numbers inside FACTS.
