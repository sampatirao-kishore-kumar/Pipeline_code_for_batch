-- ==============================================================================
-- 03_insert_test_data.sql
-- Run this script to simulate the Informatica FACTS ETL process 
-- by injecting test data into the staging/temp tables.
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. RECORD 1 (NEW CLAIM): CARRIER_CLM_NUM = '400373747'
-- This simulates a brand new claim arriving from FACTS.
-- The Python batch job will see this in TMP tables, realize it does NOT exist 
-- in MCCA_ICN, and CREATE a brand new row in MCCA_ICN and MCCA_CSR (TXN_ID = 1).
-- ------------------------------------------------------------------------------

-- Delete if already exists to prevent duplicate key errors during testing
DELETE FROM MCCA_TMP_CLMNT WHERE CARRIER_CLM_NUM = '400373747';
DELETE FROM MCCA_TMP_CLM WHERE CARRIER_CLM_NUM = '400373747';

INSERT INTO MCCA_TMP_CLM (
    CARRIER_CLM_NUM, CARR_NUM, CARR_ID, ACC_DESC, POLICY_NUM, 
    POL_EFF_DT, POL_EXP_DT, DATE_OF_LOSS, STATUS_LST, REPORTED_DT, BATCH_DT
) VALUES (
    '400373747', '0055', '1125', 'TEST ACCIDENT NEW RECORD', 'POL12345', 
    '2013-01-01', '2014-01-01', '2014-01-06', 'Open', '2014-01-10', CURRENT_TIMESTAMP
);

INSERT INTO MCCA_TMP_CLMNT (
    CARRIER_CLM_NUM, CLMNT_NUM, FIRST_NAME, LAST_NAME, BIRTH_DT, INJ_DESC, 
    GENDER_CD, MED_PAID_TO_DT, MED_NET_RESRV, INDEM_PAID_TO_DT, INDEM_NET_RESRV, 
    ALLOC_PAID_TO_DT, ALLOC_NET_RESRV, BATCH_DT
) VALUES (
    '400373747', '1', 'JOHN', 'DOE', '1980-05-15', 'TEST INJURY', 
    'M', 1000.00, 5000.00, 0, 0, 0, 0, CURRENT_TIMESTAMP
);


-- ------------------------------------------------------------------------------
-- 2. RECORD 2 (EXISTING CLAIM - UPDATE): CARRIER_CLM_NUM = '400597174'
-- This simulates updated financials/data arriving from FACTS for an existing claim.
-- ------------------------------------------------------------------------------

DELETE FROM MCCA_TMP_CLMNT WHERE CARRIER_CLM_NUM = '400597174';
DELETE FROM MCCA_TMP_CLM WHERE CARRIER_CLM_NUM = '400597174';

INSERT INTO MCCA_TMP_CLM (
    CARRIER_CLM_NUM, CARR_NUM, CARR_ID, ACC_DESC, POLICY_NUM, 
    POL_EFF_DT, POL_EXP_DT, DATE_OF_LOSS, STATUS_LST, REPORTED_DT, BATCH_DT
) VALUES (
    '400597174', '0055', '1125', 'TEST ACCIDENT EXISTING RECORD UPDATE', 'POL98765', 
    '2014-01-01', '2015-01-01', '2014-06-15', 'Open', '2014-06-20', CURRENT_TIMESTAMP
);

INSERT INTO MCCA_TMP_CLMNT (
    CARRIER_CLM_NUM, CLMNT_NUM, FIRST_NAME, LAST_NAME, BIRTH_DT, INJ_DESC, 
    GENDER_CD, MED_PAID_TO_DT, MED_NET_RESRV, INDEM_PAID_TO_DT, INDEM_NET_RESRV, 
    ALLOC_PAID_TO_DT, ALLOC_NET_RESRV, BATCH_DT
) VALUES (
    '400597174', '1', 'JANE', 'SMITH', '1975-08-22', 'TEST INJURY UPDATE', 
    'F', 2500.50, 7500.00, 0, 0, 0, 0, CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 3. ENSURE RECORD 2 HAS STATUS = 'PN' (PENDING) IN MAIN TABLES
-- As per your screenshot, the existing record already has 'PN', but running this 
-- guarantees it's in the exact state the Batch Job Step B expects so it gets picked up.
-- ------------------------------------------------------------------------------
UPDATE MCCA_ICN
SET STATUS = 'SB'
WHERE CARRIER_CLM_NUM = '400597174'
  AND TXN_ID = (SELECT MAX(TXN_ID) FROM MCCA_ICN WHERE CARRIER_CLM_NUM = '400597174');

UPDATE MCCA_CSR
SET STATUS = 'PN'
WHERE CARRIER_CLM_NUM = '400597174'
  AND TXN_ID = (SELECT MAX(TXN_ID) FROM MCCA_CSR WHERE CARRIER_CLM_NUM = '400597174');

COMMIT;
