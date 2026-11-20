-- =============================================================================
-- 02_test_2_records_end_to_end.sql
-- End-to-End 2-Record Test Setup & Validation Queries for icnCsrToMccaJob
-- =============================================================================
-- HOW THE 2-RECORD END-TO-END TEST WORKS:
--   Record 1 (NEW ICN & CSR Creation - Tests Steps 3, 4, 6, 8, updateRptdColumn):
--     Pick 1 FACTS claim (9 digits starting with 4-9, e.g. '400099901') that exists in
--     MCCA_CLAIM, MCCA_TMP_CLM, and MCCA_TMP_CLMNT, and does NOT yet exist in MCCA_ICN.
--
--   Record 2 (EXISTING Pending 'PN' ICN/CSR Update - Tests Steps 4, 5, 6, 7, 8, 9, updateRptdColumn):
--     Pick 1 existing FACTS claim in MCCA_ICN & MCCA_CSR (or update its latest TXN_ID row
--     to STATUS = 'PN', STATUS_LST = 'Open', CLOSED_IND = 'N'), and put an updated row
--     for it in MCCA_TMP_CLM and MCCA_TMP_CLMNT.
-- =============================================================================

-- =============================================================================
-- STEP A: FIND 2 EXISTING CANDIDATE CLAIMS IN YOUR ALLOYDB DATABASE
-- =============================================================================

-- A1. Find Candidate for Record 1 (Exists in MCCA_CLAIM, NOT YET in MCCA_ICN):
SELECT c.CARRIER_CLM_NUM, c.MCCA_CLM_NUM, c.CLAIM_STATUS, c.RETENTION, c.THRESHOLD, c.DATE_OF_LOSS
FROM MCCA_CLAIM c
WHERE c.CARRIER_CLM_NUM ~ '^([4-9]{1})\d{8}$'
  AND c.TXN_ID = (SELECT MAX(c2.TXN_ID) FROM MCCA_CLAIM c2 WHERE c2.CARRIER_CLM_NUM = c.CARRIER_CLM_NUM)
  AND NOT EXISTS (
      SELECT 1 FROM MCCA_ICN i WHERE i.CARRIER_CLM_NUM = c.CARRIER_CLM_NUM
  )
LIMIT 5;

-- A2. Find Candidate for Record 2 (Already in MCCA_ICN and MCCA_CSR):
SELECT i.CARRIER_CLM_NUM, i.TXN_ID AS icn_txn_id, i.STATUS AS icn_status,
       csr.CLID, csr.TXN_ID AS csr_txn_id, csr.REC_TYP, csr.STATUS AS csr_status,
       csr.STATUS_LST, csr.CLOSED_IND, csr.MED_PAID_TO_DT, csr.MED_NET_RESRV
FROM MCCA_ICN i
JOIN MCCA_CSR csr ON csr.CARRIER_CLM_NUM = i.CARRIER_CLM_NUM
WHERE i.CARRIER_CLM_NUM ~ '^([4-9]{1})\d{8}$'
  AND i.REC_TYP = 'ICN'
  AND i.TXN_ID = (SELECT MAX(i2.TXN_ID) FROM MCCA_ICN i2 WHERE i2.CARRIER_CLM_NUM = i.CARRIER_CLM_NUM AND i2.REC_TYP = 'ICN')
  AND csr.CLID <> '0'
  AND csr.TXN_ID = (SELECT MAX(c2.TXN_ID) FROM MCCA_CSR c2 WHERE c2.CARRIER_CLM_NUM = csr.CARRIER_CLM_NUM AND c2.CLID = csr.CLID)
LIMIT 5;


-- =============================================================================
-- STEP B: IF YOU WANT TO TEST UPDATING AN EXISTING RECORD BY SETTING STATUS = 'PN'
-- (Replace '412345678' with a real 9-digit FACTS CARRIER_CLM_NUM from Query A2)
-- =============================================================================
/*
-- 1. Set latest MCCA_ICN row to STATUS = 'PN'
UPDATE MCCA_ICN i
SET STATUS = 'PN'
WHERE i.CARRIER_CLM_NUM = '412345678'
  AND i.REC_TYP = 'ICN'
  AND i.TXN_ID = (
      SELECT MAX(i2.TXN_ID)
      FROM MCCA_ICN i2
      WHERE i2.CARRIER_CLM_NUM = i.CARRIER_CLM_NUM
        AND i2.REC_TYP = 'ICN'
  );

-- 2. Set latest MCCA_CSR rows (both CLID = '0' and CLID <> '0') to STATUS = 'PN', Open, not closed, updated by Batch
UPDATE MCCA_CSR c
SET STATUS = 'PN',
    STATUS_LST = 'Open',
    CLOSED_IND = 'N',
    LST_UPDTING_PRSN = 'Batch'
WHERE c.CARRIER_CLM_NUM = '412345678'
  AND c.TXN_ID = (
      SELECT MAX(c2.TXN_ID)
      FROM MCCA_CSR c2
      WHERE c2.CARRIER_CLM_NUM = c.CARRIER_CLM_NUM
        AND c2.CLID = c.CLID
  );
*/


-- =============================================================================
-- STEP C: RESTRICT MCCA_TMP_CLM & MCCA_TMP_CLMNT TO ONLY YOUR 2 TEST RECORDS
-- (After backing up MCCA_TMP_CLM_BKP and MCCA_TMP_CLMNT_BKP in Script 01!)
-- =============================================================================
/*
-- Option 1: If MCCA_TMP_CLM / MCCA_TMP_CLMNT already have data, keep only 2 claims for fast testing:
DELETE FROM MCCA_TMP_CLM
WHERE CARRIER_CLM_NUM NOT IN ('400099901', '412345678');

DELETE FROM MCCA_TMP_CLMNT
WHERE CARRIER_CLM_NUM NOT IN ('400099901', '412345678');
*/


-- =============================================================================
-- STEP D: POST-RUN VALIDATION QUERIES (RUN AFTER PYTHON BATCH JOB COMPLETES)
-- =============================================================================

-- 1. Verify MCCA_ICN created a new version row (TXN_ID incremented by +1, STATUS = 'PN', LST_UPDTING_PRSN = 'Batch')
SELECT CARRIER_CLM_NUM, TXN_ID, REC_TYP, STATUS, MCCA_CLM_NUM,
       ACC_DESC, INSRD_FST_NAME, INSRD_LST_NAME, RETENTION, THRESHOLD,
       LST_UPDTING_PRSN, LST_UPDT_TIME_STMP
FROM MCCA_ICN
WHERE CARRIER_CLM_NUM IN ('400099901', '412345678')
ORDER BY CARRIER_CLM_NUM, TXN_ID DESC;

-- 2. Verify MCCA_CSR created new version rows (CLID = '0' header row + CLID <> '0' claimant rows)
--    and calculated MED_PAID_TO_DT, MED_NET_RESRV, MED_INCURD, ALL_INJ_CL_COMB_PAID_TO_DT_MED
SELECT CARRIER_CLM_NUM, CLID, CSR_SEQ, TXN_ID, REC_TYP, STATUS, STATUS_LST, CLOSED_IND,
       MED_PAID_TO_DT, MED_NET_RESRV, MED_INCURD,
       WL_ES_SL_PAID_TO_DT, WL_ES_SL_NET, WL_ES_SL_INCRD,
       ALL_INJ_CL_COMB_PAID_TO_DT_MED, ALL_INJ_CL_COMB_PAID_TO_DT_RES, ALINJ_CL_CM_PD_TO_DT_MEDWLRES,
       RETENTION, RETNTON_AMT, PTD_RESERVES_AS_OF_DATE, LST_UPDTING_PRSN, LST_UPDT_TIME_STMP
FROM MCCA_CSR
WHERE CARRIER_CLM_NUM IN ('400099901', '412345678')
ORDER BY CARRIER_CLM_NUM, CLID, TXN_ID DESC;

-- 3. Verify MCCA_CLAIM RPTD column update (Step updateRptdColumn)
SELECT CARRIER_CLM_NUM, TXN_ID, MCCA_CLM_NUM, CLAIM_STATUS, RPTD, UPDATE_DATE
FROM MCCA_CLAIM
WHERE CARRIER_CLM_NUM IN ('400099901', '412345678')
ORDER BY CARRIER_CLM_NUM, TXN_ID DESC;

-- 4. Verify MCCA_PROJECTIONS (for newly inserted claimants in Step 4)
SELECT CARRIER_CLM_NUM, CLID, TXN_ID, REC_TYP, PROJN_SEQ, CSR_SEQ, LST_UPDT_TIME_STMP
FROM MCCA_PROJECTIONS
WHERE CARRIER_CLM_NUM IN ('400099901', '412345678')
ORDER BY CARRIER_CLM_NUM, CLID, TXN_ID DESC;

-- 5. Verify MCCA_TMP_CLM and MCCA_TMP_CLMNT were cleared (if Monthly '-t m' was run)
SELECT
    (SELECT COUNT(*) FROM MCCA_TMP_CLM)   AS tmp_clm_remaining,
    (SELECT COUNT(*) FROM MCCA_TMP_CLMNT) AS tmp_clmnt_remaining;
