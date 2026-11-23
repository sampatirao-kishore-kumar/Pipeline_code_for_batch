"""
Exact Reader SQL Queries (from jobs/beanInfo.xml lines 937-1503) and RowMappers
(from com.acg.mcca.batch.mapper.*) for icnCsrToMccaJob.

Real Tables Referenced:
- MCCA_ICN
- MCCA_CSR
- MCCA_CLAIM
- MCCA_TMP_CLM
- MCCA_TMP_CLMNT
- MCCA_LOSS_EXPENSE_DETAILS
- D_FISCAL_MONTH
"""

import re
from decimal import Decimal
from typing import Any, Dict

from models import CsrDetail, IcnCsrDetail, TmpCsrDetail, TmpIcnDetail


def adapt_sql(sql: str, dialect: str = "postgresql") -> str:
    """
    Preserves 100% of the exact legacy Oracle SQL table and column names while
    adapting Oracle-specific functions (NVL, SYSDATE, REGEXP_LIKE, 1-arg TO_NUMBER)
    when running against AlloyDB (PostgreSQL).
    """
    if dialect.lower() == "oracle":
        return sql
    adapted = sql
    # NVL(a, b) -> COALESCE(a, b)
    adapted = re.sub(r"\bNVL\s*\(", "COALESCE(", adapted, flags=re.IGNORECASE)
    # SYSDATE -> CURRENT_TIMESTAMP
    adapted = re.sub(r"\bSYSDATE\b", "CURRENT_TIMESTAMP", adapted, flags=re.IGNORECASE)
    # REGEXP_LIKE(col, 'pattern') -> (col ~ 'pattern')
    adapted = re.sub(
        r"REGEXP_LIKE\s*\(\s*([^,]+?)\s*,\s*('[^']*')\s*\)",
        r"(\1 ~ \2)",
        adapted,
        flags=re.IGNORECASE,
    )
    # Single-argument TO_NUMBER(TO_CHAR(...)) -> CAST(TO_CHAR(...) AS INTEGER) for PostgreSQL/AlloyDB
    adapted = re.sub(
        r"TO_NUMBER\s*\(\s*(TO_CHAR\s*\([^)]+\(\s*'[^']*'\s*,\s*'[^']*'\s*\)\s*,\s*'[^']*'\s*\))\s*\)",
        r"CAST(\1 AS INTEGER)",
        adapted,
        flags=re.IGNORECASE,
    )
    # F.FISCAL_MONTH_NUMBER || F.FISCAL_YEAR -> CONCAT(F.FISCAL_MONTH_NUMBER, F.FISCAL_YEAR)
    adapted = re.sub(
        r"F\.FISCAL_MONTH_NUMBER\s*\|\|\s*F\.FISCAL_YEAR",
        r"CONCAT(F.FISCAL_MONTH_NUMBER, F.FISCAL_YEAR)",
        adapted,
        flags=re.IGNORECASE,
    )

    # Postgres CONCAT for specific batch_date queries:
    # THEN (12 || (expr - 1)) -> THEN CONCAT('12', expr - 1)
    adapted = re.sub(
        r"THEN\s*\(\s*12\s*\|\|\s*\((.*?-\s*1)\)\s*\)",
        r"THEN CONCAT('12', \1)",
        adapted,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # ELSE ((expr - 1) || expr) -> ELSE CONCAT(expr - 1, expr)
    adapted = re.sub(
        r"ELSE\s*\(\s*\((.*?-\s*1)\)\s*\|\|\s*(.*?)\s*\)\s+END",
        r"ELSE CONCAT(\1, \2)\nEND",
        adapted,
        flags=re.IGNORECASE | re.DOTALL,
    )
    
    return adapted


# ==============================================================================
# STEP 2 READER: copyIcnJdbcReader (beanInfo.xml lines 953-969)
# ==============================================================================
def get_step2_copy_icn_sql() -> str:
    return """
        SELECT CARRIER_CLM_NUM, LOSS_DT
        FROM MCCA_ICN icn1
        WHERE REC_TYP = 'ICN'
          AND SUBMITTED_TO = 'FIN'
          AND REGEXP_LIKE(CARRIER_CLM_NUM, '^([4-9]{1})\\d{8}$')
          AND TXN_ID = (
              SELECT MAX(TXN_ID)
              FROM MCCA_ICN icn2
              WHERE icn1.CARRIER_CLM_NUM = icn2.CARRIER_CLM_NUM
          )
    """


def map_icn_incurred_amount_row(row: Dict[str, Any]) -> IcnCsrDetail:
    """1:1 port of com.acg.mcca.batch.mapper.IcnIncurredAmountRowMapper."""
    return IcnCsrDetail(
        carrier_claim_num=row.get("CARRIER_CLM_NUM"),
        date_of_loss=row.get("LOSS_DT"),
    )


# ==============================================================================
# STEP 3 READER: icnDetailJdbcReader (beanInfo.xml lines 971-1047)
# ==============================================================================
def get_step3_icn_detail_sql(batch_date_param: str) -> str:
    return f"""
        SELECT
            tClaim.CARRIER_CLM_NUM,
            tClaim.ACC_DESC,
            tClaim.ACC_ADD1,
            tClaim.ACC_ADD2,
            tClaim.ACC_CITY,
            tClaim.ACC_STATE,
            tClaim.ACC_ZIP,
            tClaim.CRS_COMP_CLM_IND,
            tClaim.CRS_COMP_CLM_NUM,
            tClaim.MAIPF_JUA_IND,
            tClaim.COM_PLCY_IND,
            tClaim.PIP_ADJ_ID,
            tClaim.CRR_ID,
            tClaim.CARRIER_PLCY_NUM,
            tClaim.PLCY_WRTN_CRDNT_BAS,
            tClaim.PLCY_CORD_DT_OF_LOSS,
            tClaim.INSRD_PREFIX,
            tClaim.INSRD_FST_NAME,
            tClaim.INSRD_LST_NAME,
            tClaim.INSRD_MDL_INI,
            tClaim.INSRD_GENDER,
            tClaim.INSRD_DOB,
            tClaim.INSRD_ADD1,
            tClaim.INSRD_ADD2,
            tClaim.INSRD_CITY,
            tClaim.INSRD_STATE,
            tClaim.INSRD_ZIP,
            claim.MCCA_CLM_NUM,
            claim.LINK_ID,
            claim.MASTER_CLAIM_IND,
            claim.RETENTION,
            claim.THRESHOLD,
            claim.IS_PIP,
            claim.DATE_OF_LOSS,
            claim.CLAIM_STATUS,
            claim.POLICY_INCEPTION_DATE,
            claim.POLICY_END_DATE,
            claim.COMPANY,
            LOSSES.LOSSES_PAID
        FROM MCCA_TMP_CLM tClaim,
             MCCA_CLAIM claim
        LEFT OUTER JOIN (
            SELECT LED.CARRIER_CLM_NUM, SUM(LED.LOSSES_PAID) LOSSES_PAID
            FROM MCCA_LOSS_EXPENSE_DETAILS LED
            WHERE LED.TO_DATE <= (
                SELECT DISTINCT F.LAST_DAY_FISCAL_MONTH
                FROM D_FISCAL_MONTH F
                WHERE F.FISCAL_MONTH_NUMBER || F.FISCAL_YEAR = (
                    CASE
                        WHEN TO_NUMBER(TO_CHAR(TO_DATE('{batch_date_param}', 'YYYY/MM/DD'), 'MM')) = 1
                        THEN (12 || (TO_NUMBER(TO_CHAR(TO_DATE('{batch_date_param}', 'YYYY/MM/DD'), 'YYYY')) - 1))
                        ELSE ((TO_NUMBER(TO_CHAR(TO_DATE('{batch_date_param}', 'YYYY/MM/DD'), 'MM')) - 1)
                              || TO_NUMBER(TO_CHAR(TO_DATE('{batch_date_param}', 'YYYY/MM/DD'), 'YYYY')))
                    END
                )
            )
            GROUP BY LED.CARRIER_CLM_NUM
        ) LOSSES ON LOSSES.CARRIER_CLM_NUM = claim.CARRIER_CLM_NUM
        WHERE claim.CARRIER_CLM_NUM = tClaim.CARRIER_CLM_NUM
          AND claim.TXN_ID = (
              SELECT MAX(claim1.TXN_ID)
              FROM MCCA_CLAIM claim1
              WHERE claim1.CARRIER_CLM_NUM = claim.CARRIER_CLM_NUM
          )
    """


def map_icn_csr_row(row: Dict[str, Any]) -> IcnCsrDetail:
    """1:1 port of com.acg.mcca.batch.mapper.IcnCsrRowMapper."""
    return IcnCsrDetail(
        carrier_claim_num=row.get("CARRIER_CLM_NUM"),
        status=row.get("CLAIM_STATUS"),
        company=row.get("COMPANY"),
        date_of_loss=row.get("DATE_OF_LOSS"),
        is_pip_ind=row.get("IS_PIP"),
        master_claim_ind=row.get("MASTER_CLAIM_IND"),
        mcca_claim_num=row.get("MCCA_CLM_NUM"),
        retention_amt=float(row["RETENTION"]) if row.get("RETENTION") is not None else 0.0,
        threshold_amt=float(row["THRESHOLD"]) if row.get("THRESHOLD") is not None else 0.0,
        accident_desc=row.get("ACC_DESC"),
        accident_addr1=row.get("ACC_ADD1"),
        accident_addr2=row.get("ACC_ADD2"),
        accident_city=row.get("ACC_CITY"),
        accident_state=row.get("ACC_STATE"),
        accident_zip=row.get("ACC_ZIP"),
        comp_crs_clm_ind=row.get("CRS_COMP_CLM_IND"),
        cross_comp_clm_num=str(row["CRS_COMP_CLM_NUM"]) if row.get("CRS_COMP_CLM_NUM") is not None else None,
        maipf_jua_ind=row.get("MAIPF_JUA_IND"),
        com_plcy_ind=row.get("COM_PLCY_IND"),
        adjuster_id=row.get("PIP_ADJ_ID"),
        carrier_id=int(row["CRR_ID"]) if row.get("CRR_ID") is not None else None,
        carrier_policy_num=row.get("CARRIER_PLCY_NUM"),
        plcy_wrtn_crdnt_bas=row.get("PLCY_WRTN_CRDNT_BAS"),
        ws_pol_cord_on_dt_loss=row.get("PLCY_CORD_DT_OF_LOSS"),
        insured_prefix=row.get("INSRD_PREFIX"),
        insured_frst_name=row.get("INSRD_FST_NAME"),
        insured_lst_name=row.get("INSRD_LST_NAME"),
        insured_midl_in=row.get("INSRD_MDL_INI"),
        insured_gender=row.get("INSRD_GENDER"),
        insured_dob=row.get("INSRD_DOB"),
        insured_addr1=row.get("INSRD_ADD1"),
        insured_addr2=row.get("INSRD_ADD2"),
        insured_city=row.get("INSRD_CITY"),
        insured_state=row.get("INSRD_STATE"),
        insured_zip=row.get("INSRD_ZIP"),
        policy_effc_dt=row.get("POLICY_INCEPTION_DATE"),
        policy_exp_dt=row.get("POLICY_END_DATE"),
        link_claim=row.get("LINK_ID"),
        paid_to_date=float(row["LOSSES_PAID"]) if row.get("LOSSES_PAID") is not None else 0.0,
    )


# ==============================================================================
# STEP 4 READER: csrDetailJdbcReader (beanInfo.xml lines 1049-1131)
# ==============================================================================
def get_step4_csr_detail_sql() -> str:
    return """
        SELECT DISTINCT
            CLMNT.CARRIER_CLM_NUM,
            CLMNT.CLID,
            CLMNT.CLMT_PREFIX,
            CLMNT.CLMT_FST_NAME,
            CLMNT.CLMT_LST_NAME,
            CLMNT.CLMT_GNDR,
            CLMNT.CLMT_DOB,
            CLMNT.CLMT_ADD1,
            CLMNT.CLMT_ADD2,
            CLMNT.CLMT_CITY,
            CLMNT.CLMT_STATE,
            CLMNT.CLMT_ZIP,
            CLMNT.LITGN_ISSUE_IND,
            CLMNT.PIP_CLM_LITIGN_IND,
            CLMNT.INJ_DESC,
            CLMNT.COORDINATE_NO_FLT_IND,
            CLMNT.HLTH_CRR,
            CLMNT.CLMT_STAT_CD,
            CLMNT.RLN_CD,
            CLMNT.SEABLT_CD,
            CLMNT.ARBG_USE_CD,
            CLMNT.INJ_CD,
            CLMNT.CLMT_DCSD_IND,
            CLMNT.DEMAND,
            CLMNT.SUIT_DT,
            CLMNT.LITGN_ISSUE_DESC,
            CLMNT.DEATH_DT,
            CLMNT.PIP_CLOSED_IND,
            CLMNT.CLMT_MDL_INI,
            (CASE WHEN CSR.CLID IS NULL THEN 'Y' ELSE 'N' END) AS NEW_CLAIMANT,
            CSR.CLMT_SUFFIX AS CSR_CLMT_SUFFIX,
            CSR.CLMT_FST_NAME AS CSR_CLMT_FST_NAME,
            CSR.CLMT_LST_NAME AS CSR_CLMT_LST_NAME,
            CSR.CLMT_GNDR AS CSR_CLMT_GNDR,
            CSR.CLMT_DOB AS CSR_CLMT_DOB,
            CSR.CLMT_ADD1 AS CSR_CLMT_ADD1,
            CSR.CLMT_ADD2 AS CSR_CLMT_ADD2,
            CSR.CLMT_CITY AS CSR_CLMT_CITY,
            CSR.CLMT_STATE AS CSR_CLMT_STATE,
            CSR.CLMT_ZIP AS CSR_CLMT_ZIP,
            CSR.LITGN_ISSUE_IND AS CSR_LITGN_ISSUE_IND,
            CSR.PIP_CLM_LITIGN_IND AS CSR_PIP_CLM_LITIGN_IND,
            CSR.INJ_DESC AS CSR_INJ_DESC,
            CSR.COORDINATE_NO_FLT_IND AS CSR_COORDINATE_NO_FLT_IND,
            CSR.HLTH_CRR AS CSR_HLTH_CRR,
            CSR.CLMT_STAT_CD AS CSR_CLMT_STAT_CD,
            CSR.RLN_CD AS CSR_RLN_CD,
            CSR.SEABLT_CD AS CSR_SEABLT_CD,
            CSR.ARBG_USE_CD AS CSR_ARBG_USE_CD,
            CSR.INJ_CD AS CSR_INJ_CD,
            CSR.CLMT_DCSD_IND AS CSR_CLMT_DCSD_IND,
            CSR.DEMAND AS CSR_DEMAND,
            CSR.SUIT_DT AS CSR_SUIT_DT,
            CSR.LITGN_ISSUE_DESC AS CSR_LITGN_ISSUE_DESC,
            CSR.DEATH_DT AS CSR_DEATH_DT,
            CSR.CLMT_MI AS CSR_CLMT_MI,
            CSR.PTD_RESERVES_AS_OF_DATE
        FROM MCCA_TMP_CLMNT CLMNT
        LEFT OUTER JOIN (
            SELECT *
            FROM MCCA_CSR CSR1
            WHERE CSR1.TXN_ID = (
                SELECT MAX(CSR2.TXN_ID)
                FROM MCCA_CSR CSR2
                WHERE CSR2.CARRIER_CLM_NUM = CSR1.CARRIER_CLM_NUM
                  AND CSR2.CLID = CSR1.CLID
            )
        ) CSR ON CSR.CARRIER_CLM_NUM = CLMNT.CARRIER_CLM_NUM
             AND CSR.CLID = CLMNT.CLID
    """


def map_csr_row(row: Dict[str, Any]) -> TmpCsrDetail:
    """1:1 port of com.acg.mcca.batch.mapper.CsrRowMapper."""
    return TmpCsrDetail(
        carrier_claim_num=row.get("CARRIER_CLM_NUM"),
        clid=row.get("CLID"),
        tmp_claimt_prefix=row.get("CLMT_PREFIX"),
        tmp_claimt_frst_name=row.get("CLMT_FST_NAME"),
        tmp_claimt_lst_name=row.get("CLMT_LST_NAME"),
        tmp_claimt_gender=row.get("CLMT_GNDR"),
        tmp_claimt_dob=row.get("CLMT_DOB"),
        tmp_claimt_addres1=row.get("CLMT_ADD1"),
        tmp_claimt_addres2=row.get("CLMT_ADD2"),
        tmp_claimt_city=row.get("CLMT_CITY"),
        tmp_claimt_state=row.get("CLMT_STATE"),
        tmp_claimt_zip=row.get("CLMT_ZIP"),
        tmp_are_issue_in_litg_ind=row.get("LITGN_ISSUE_IND"),
        tmp_pip_clm_in_litg_ind=row.get("PIP_CLM_LITIGN_IND"),
        tmp_injured_desc=row.get("INJ_DESC"),
        tmp_cordnt_no_fault=row.get("COORDINATE_NO_FLT_IND"),
        tmp_health_crr=row.get("HLTH_CRR"),
        tmp_claimt_status_cd=row.get("CLMT_STAT_CD"),
        tmp_relation_cd=row.get("RLN_CD"),
        tmp_seatbelt_cd=row.get("SEABLT_CD"),
        tmp_air_bg_use_cd=row.get("ARBG_USE_CD"),
        tmp_injured_cd=row.get("INJ_CD"),
        tmp_claimt_is_dceasd_ind=row.get("CLMT_DCSD_IND"),
        tmp_demand=row.get("DEMAND"),
        tmp_suit_date=row.get("SUIT_DT"),
        tmp_litgn_issue_desc=row.get("LITGN_ISSUE_DESC"),
        tmp_claimt_death_dt=row.get("DEATH_DT"),
        tmp_pip_clsd_ind=row.get("PIP_CLOSED_IND"),
        new_claimant_ind=row.get("NEW_CLAIMANT"),
        tmp_claimt_midl_in=row.get("CLMT_MDL_INI"),
        claimt_prefix=row.get("CSR_CLMT_SUFFIX"),
        claimt_frst_name=row.get("CSR_CLMT_FST_NAME"),
        claimt_lst_name=row.get("CSR_CLMT_LST_NAME"),
        claimt_gender=row.get("CSR_CLMT_GNDR"),
        claimt_dob=row.get("CSR_CLMT_DOB"),
        claimt_addres1=row.get("CSR_CLMT_ADD1"),
        claimt_addres2=row.get("CSR_CLMT_ADD2"),
        claimt_city=row.get("CSR_CLMT_CITY"),
        claimt_state=row.get("CSR_CLMT_STATE"),
        claimt_zip=row.get("CSR_CLMT_ZIP"),
        are_issue_in_litg_ind=row.get("CSR_LITGN_ISSUE_IND"),
        pip_clm_in_litg_ind=row.get("CSR_PIP_CLM_LITIGN_IND"),
        injured_desc=row.get("CSR_INJ_DESC"),
        cordnt_no_fault=row.get("CSR_COORDINATE_NO_FLT_IND"),
        health_crr=row.get("CSR_HLTH_CRR"),
        claimt_status_cd=row.get("CSR_CLMT_STAT_CD"),
        relation_cd=row.get("CSR_RLN_CD"),
        seatbelt_cd=row.get("CSR_SEABLT_CD"),
        air_bg_use_cd=row.get("CSR_ARBG_USE_CD"),
        injured_cd=row.get("CSR_INJ_CD"),
        claimt_is_dceasd_ind=row.get("CSR_CLMT_DCSD_IND"),
        demand=row.get("CSR_DEMAND"),
        suit_date=row.get("CSR_SUIT_DT"),
        litgn_issue_desc=row.get("CSR_LITGN_ISSUE_DESC"),
        claimt_death_dt=row.get("CSR_DEATH_DT"),
        claimt_midl_in=row.get("CSR_CLMT_MI"),
        ptd_reserve_asof_date=row.get("PTD_RESERVES_AS_OF_DATE"),
    )


# ==============================================================================
# STEP 5 READER: updateIcnTmpClaimDetailJdbcReader (beanInfo.xml lines 1223-1305)
# ==============================================================================
def get_step5_update_icn_tmp_claim_sql() -> str:
    return """
        SELECT
            T.CARRIER_CLM_NUM,
            T.ACC_ADD1,
            T.ACC_ADD2,
            T.ACC_CITY,
            T.ACC_DESC,
            T.ACC_STATE,
            T.ACC_ZIP,
            T.CARRIER_PLCY_NUM,
            T.COM_PLCY_IND,
            T.CRR_ID,
            T.CRS_COMP_CLM_IND,
            T.CRS_COMP_CLM_NUM,
            T.INSRD_ADD1,
            T.INSRD_ADD2,
            T.INSRD_CITY,
            T.INSRD_DOB,
            T.INSRD_FST_NAME,
            T.INSRD_GENDER,
            T.INSRD_LST_NAME,
            T.INSRD_MDL_INI,
            T.INSRD_PREFIX,
            T.INSRD_STATE,
            T.INSRD_ZIP,
            T.MAIPF_JUA_IND,
            T.PIP_ADJ_ID,
            T.PLCY_CORD_DT_OF_LOSS,
            T.PLCY_WRTN_CRDNT_BAS,
            ICN.ACC_ADD1 AS ICN_ACC_ADD1,
            ICN.ACC_ADD2 AS ICN_ACC_ADD2,
            ICN.ACC_CITY AS ICN_ACC_CITY,
            ICN.ACC_DESC AS ICN_ACC_DESC,
            ICN.ACC_STATE AS ICN_ACC_STATE,
            ICN.ACC_ZIP AS ICN_ACC_ZIP,
            ICN.CARRIER_PLCY_NUM AS ICN_CARRIER_PLCY_NUM,
            ICN.COM_PLCY_IND AS ICN_COM_PLCY_IND,
            ICN.COMP_CRS_CLM_IND AS ICN_COMP_CRS_CLM_IND,
            ICN.INSRD_ADD1 AS ICN_INSRD_ADD1,
            ICN.INSRD_ADD2 AS ICN_INSRD_ADD2,
            ICN.INSRD_CITY AS ICN_INSRD_CITY,
            ICN.INSRD_DOB AS ICN_INSRD_DOB,
            ICN.INSRD_FST_NAME AS ICN_INSRD_FST_NAME,
            ICN.INSRD_GENDER AS ICN_INSRD_GENDER,
            ICN.INSRD_LST_NAME AS ICN_INSRD_LST_NAME,
            ICN.INSRD_MI AS ICN_INSRD_MI,
            ICN.INSRD_SUFFIX AS ICN_INSRD_SUFFIX,
            ICN.INSRD_STATE AS ICN_INSRD_STATE,
            ICN.INSRD_ZIP AS ICN_INSRD_ZIP,
            ICN.MAIPF_JUA_IND AS ICN_MAIPF_JUA_IND,
            ICN.PLCY_WRTN_CRDNT_BAS AS ICN_PLCY_WRTN_CRDNT_BAS
        FROM MCCA_TMP_CLM T,
             MCCA_ICN ICN
        WHERE T.CARRIER_CLM_NUM IN (
            SELECT CSR.CARRIER_CLM_NUM
            FROM MCCA_CSR CSR
            WHERE (CSR.CLOSED_IND IS NULL OR CSR.CLOSED_IND = 'N')
              AND CSR.CLID = '0'
              AND CSR.REC_TYP = 'ICN'
              AND CSR.STATUS_LST = 'Open'
              AND CSR.TXN_ID = (
                  SELECT MAX(CSR1.TXN_ID)
                  FROM MCCA_CSR CSR1
                  WHERE CSR1.CARRIER_CLM_NUM = CSR.CARRIER_CLM_NUM
                    AND CSR1.CLID = '0'
                    AND CSR1.REC_TYP = 'ICN'
              )
        )
          AND ICN.CARRIER_CLM_NUM = T.CARRIER_CLM_NUM
          AND ICN.REC_TYP = 'ICN'
          AND ICN.STATUS = 'PN'
          AND ICN.TXN_ID = (
              SELECT MAX(ICN1.TXN_ID)
              FROM MCCA_ICN ICN1
              WHERE ICN1.CARRIER_CLM_NUM = ICN.CARRIER_CLM_NUM
                AND ICN1.REC_TYP = 'ICN'
                AND ICN1.STATUS = 'PN'
          )
    """


def map_tmp_claim_detail_row(row: Dict[str, Any]) -> TmpIcnDetail:
    """1:1 port of com.acg.mcca.batch.mapper.TmpClaimDetailRowMapper."""
    return TmpIcnDetail(
        carrier_claim_num=row.get("CARRIER_CLM_NUM"),
        tmp_accident_addr1=row.get("ACC_ADD1"),
        tmp_accident_addr2=row.get("ACC_ADD2"),
        tmp_accident_city=row.get("ACC_CITY"),
        tmp_accident_desc=row.get("ACC_DESC"),
        tmp_accident_state=row.get("ACC_STATE"),
        tmp_accident_zip=row.get("ACC_ZIP"),
        tmp_carrier_policy_num=row.get("CARRIER_PLCY_NUM"),
        tmp_com_plcy_ind=row.get("COM_PLCY_IND"),
        tmp_carrier_id=int(row["CRR_ID"]) if row.get("CRR_ID") is not None else None,
        tmp_comp_crs_clm_ind=row.get("CRS_COMP_CLM_IND"),
        tmp_cross_comp_clm_num=str(row["CRS_COMP_CLM_NUM"]) if row.get("CRS_COMP_CLM_NUM") is not None else None,
        tmp_insured_addr1=row.get("INSRD_ADD1"),
        tmp_insured_addr2=row.get("INSRD_ADD2"),
        tmp_insured_city=row.get("INSRD_CITY"),
        tmp_insured_state=row.get("INSRD_STATE"),
        tmp_insured_zip=row.get("INSRD_ZIP"),
        tmp_insured_prefix=row.get("INSRD_PREFIX"),
        tmp_insured_frst_name=row.get("INSRD_FST_NAME"),
        tmp_insured_lst_name=row.get("INSRD_LST_NAME"),
        tmp_insured_midl_in=row.get("INSRD_MDL_INI"),
        tmp_insured_gender=row.get("INSRD_GENDER"),
        tmp_insured_dob=row.get("INSRD_DOB"),
        tmp_maipf_jua_ind=row.get("MAIPF_JUA_IND"),
        tmp_adjuster_id=row.get("PIP_ADJ_ID"),
        tmp_ws_pol_cord_on_dt_loss=row.get("PLCY_CORD_DT_OF_LOSS"),
        tmp_plcy_wrtn_crdnt_bas=row.get("PLCY_WRTN_CRDNT_BAS"),
        accident_addr1=row.get("ICN_ACC_ADD1"),
        accident_addr2=row.get("ICN_ACC_ADD2"),
        accident_city=row.get("ICN_ACC_CITY"),
        accident_desc=row.get("ICN_ACC_DESC"),
        accident_state=row.get("ICN_ACC_STATE"),
        accident_zip=row.get("ICN_ACC_ZIP"),
        carrier_policy_num=row.get("ICN_CARRIER_PLCY_NUM"),
        com_plcy_ind=row.get("ICN_COM_PLCY_IND"),
        comp_crs_clm_ind=row.get("ICN_COMP_CRS_CLM_IND"),
        insured_addr1=row.get("ICN_INSRD_ADD1"),
        insured_addr2=row.get("ICN_INSRD_ADD2"),
        insured_city=row.get("ICN_INSRD_CITY"),
        insured_state=row.get("ICN_INSRD_STATE"),
        insured_zip=row.get("ICN_INSRD_ZIP"),
        insured_prefix=row.get("ICN_INSRD_SUFFIX"),
        insured_frst_name=row.get("ICN_INSRD_FST_NAME"),
        insured_lst_name=row.get("ICN_INSRD_LST_NAME"),
        insured_midl_in=row.get("ICN_INSRD_MI"),
        insured_gender=row.get("ICN_INSRD_GENDER"),
        insured_dob=row.get("ICN_INSRD_DOB"),
        maipf_jua_ind=row.get("ICN_MAIPF_JUA_IND"),
        plcy_wrtn_crdnt_bas=row.get("ICN_PLCY_WRTN_CRDNT_BAS"),
    )


# ==============================================================================
# STEP 6 READER: updateIcnClaimDetailJdbcReader (beanInfo.xml lines 1317-1361)
# ==============================================================================
def get_step6_update_icn_claim_sql() -> str:
    return """
        SELECT DISTINCT
            T.CARRIER_CLM_NUM,
            T.MCCA_CLM_NUM,
            T.RETENTION,
            T.THRESHOLD,
            T.DATE_OF_LOSS,
            T.POLICY_INCEPTION_DATE,
            T.POLICY_END_DATE,
            T.CARRIER_PLCY_NUM,
            T.LINK_ID,
            ICN.REC_TYP
        FROM MCCA_CLAIM T,
             (
                 SELECT I.CARRIER_CLM_NUM, I.REC_TYP
                 FROM MCCA_ICN I,
                      MCCA_CSR CSR
                 WHERE I.TXN_ID = (
                     SELECT MAX(ICN1.TXN_ID)
                     FROM MCCA_ICN ICN1
                     WHERE ICN1.CARRIER_CLM_NUM = I.CARRIER_CLM_NUM
                       AND ICN1.REC_TYP = 'ICN'
                 )
                   AND CSR.CARRIER_CLM_NUM = I.CARRIER_CLM_NUM
                   AND (CSR.CLOSED_IND IS NULL OR CSR.CLOSED_IND = 'N')
                   AND CSR.CLID = '0'
                   AND CSR.REC_TYP = 'ICN'
                   AND CSR.STATUS_LST = 'Open'
                   AND I.REC_TYP = 'ICN'
                   AND I.STATUS = 'PN'
                   AND CSR.TXN_ID = (
                       SELECT MAX(CSR1.TXN_ID)
                       FROM MCCA_CSR CSR1
                       WHERE CSR1.CARRIER_CLM_NUM = CSR.CARRIER_CLM_NUM
                         AND CSR1.CLID = '0'
                         AND CSR1.REC_TYP = 'ICN'
                   )
             ) ICN
        WHERE T.CARRIER_CLM_NUM = ICN.CARRIER_CLM_NUM
          AND REGEXP_LIKE(T.CARRIER_CLM_NUM, '^([4-9]{1})\\d{8}$')
          AND T.TXN_ID = (
              SELECT MAX(T1.TXN_ID)
              FROM MCCA_CLAIM T1
              WHERE T1.CARRIER_CLM_NUM = T.CARRIER_CLM_NUM
          )
    """


def map_icn_csr_claim_detail_row(row: Dict[str, Any]) -> IcnCsrDetail:
    """1:1 port of com.acg.mcca.batch.mapper.IcnCsrClaimDetailRowMapper."""
    return IcnCsrDetail(
        carrier_claim_num=row.get("CARRIER_CLM_NUM"),
        carrier_policy_num=row.get("CARRIER_PLCY_NUM"),
        date_of_loss=row.get("DATE_OF_LOSS"),
        mcca_claim_num=row.get("MCCA_CLM_NUM"),
        retention_amt=float(row["RETENTION"]) if row.get("RETENTION") is not None else 0.0,
        threshold_amt=float(row["THRESHOLD"]) if row.get("THRESHOLD") is not None else 0.0,
        policy_effc_dt=row.get("POLICY_INCEPTION_DATE"),
        policy_exp_dt=row.get("POLICY_END_DATE"),
        link_claim=row.get("LINK_ID"),
        record_type=row.get("REC_TYP"),
    )


# ==============================================================================
# STEP 7 READER: updateCsrClaimDetailJdbcReader (beanInfo.xml lines 1363-1399)
# ==============================================================================
def get_step7_update_csr_claim_sql() -> str:
    return """
        SELECT DISTINCT
            T.CARRIER_CLM_NUM,
            T.MCCA_CLM_NUM,
            T.RETENTION,
            T.THRESHOLD,
            T.DATE_OF_LOSS,
            T.POLICY_INCEPTION_DATE,
            T.POLICY_END_DATE,
            T.CARRIER_PLCY_NUM,
            T.LINK_ID,
            CSR.CLID,
            CSR.REC_TYP,
            CSR.CSR_SEQ
        FROM MCCA_CLAIM T,
             (
                 SELECT C.CARRIER_CLM_NUM, C.CLID, C.REC_TYP, C.CSR_SEQ
                 FROM MCCA_CSR C
                 WHERE (C.CLOSED_IND IS NULL OR C.CLOSED_IND = 'N')
                   AND C.REC_TYP = 'CSR'
                   AND C.STATUS = 'PN'
                   AND C.STATUS_LST = 'Open'
                   AND C.TXN_ID = (
                       SELECT MAX(CSR1.TXN_ID)
                       FROM MCCA_CSR CSR1
                       WHERE CSR1.CARRIER_CLM_NUM = C.CARRIER_CLM_NUM
                         AND CSR1.CLID = C.CLID
                         AND CSR1.REC_TYP = 'CSR'
                   )
             ) CSR
        WHERE T.CARRIER_CLM_NUM = CSR.CARRIER_CLM_NUM
          AND REGEXP_LIKE(T.CARRIER_CLM_NUM, '^([4-9]{1})\\d{8}$')
          AND T.TXN_ID = (
              SELECT MAX(T1.TXN_ID)
              FROM MCCA_CLAIM T1
              WHERE T1.CARRIER_CLM_NUM = T.CARRIER_CLM_NUM
          )
    """


def map_csr_claim_detail_row(row: Dict[str, Any]) -> IcnCsrDetail:
    """1:1 port of com.acg.mcca.batch.mapper.CsrClaimDetailRowMapper."""
    return IcnCsrDetail(
        carrier_claim_num=row.get("CARRIER_CLM_NUM"),
        carrier_policy_num=row.get("CARRIER_PLCY_NUM"),
        date_of_loss=row.get("DATE_OF_LOSS"),
        mcca_claim_num=row.get("MCCA_CLM_NUM"),
        retention_amt=float(row["RETENTION"]) if row.get("RETENTION") is not None else 0.0,
        threshold_amt=float(row["THRESHOLD"]) if row.get("THRESHOLD") is not None else 0.0,
        policy_effc_dt=row.get("POLICY_INCEPTION_DATE"),
        policy_exp_dt=row.get("POLICY_END_DATE"),
        link_claim=row.get("LINK_ID"),
        clid=row.get("CLID"),
        record_type=row.get("REC_TYP"),
        csr_seq=Decimal(str(row["CSR_SEQ"])) if row.get("CSR_SEQ") is not None else Decimal("0"),
    )


# ==============================================================================
# STEP 8 READER: pendingIcnJdbcReader (beanInfo.xml lines 1136-1174)
# ==============================================================================
def get_step8_pending_icn_sql() -> str:
    return """
        SELECT C.*
        FROM MCCA_ICN I,
             MCCA_CSR C
        WHERE I.REC_TYP = 'ICN'
          AND I.TXN_ID = (
              SELECT MAX(I1.TXN_ID)
              FROM MCCA_ICN I1
              WHERE I1.CARRIER_CLM_NUM = I.CARRIER_CLM_NUM
                AND I1.REC_TYP = 'ICN'
          )
          AND I.STATUS NOT IN ('SB', 'SF')
          AND REGEXP_LIKE(I.CARRIER_CLM_NUM, '^([4-9]{1})\\d{8}$')
          AND I.CARRIER_CLM_NUM = C.CARRIER_CLM_NUM
          AND C.CLID <> '0'
          AND C.CSR_SEQ = 0
          AND C.REC_TYP = 'ICN'
          AND C.LST_UPDTING_PRSN = 'Batch'
          AND C.TXN_ID = (
              SELECT MAX(C1.TXN_ID)
              FROM MCCA_CSR C1
              WHERE C1.CARRIER_CLM_NUM = C.CARRIER_CLM_NUM
                AND C1.CLID = C.CLID
                AND C1.CSR_SEQ = C.CSR_SEQ
          )
    """


# ==============================================================================
# STEP 9 READER: csrsToUpdateJdbcReader (beanInfo.xml lines 1176-1208)
# ==============================================================================
def get_step9_csrs_to_update_sql() -> str:
    return """
        SELECT *
        FROM MCCA_CSR C
        WHERE C.TXN_ID = (
            SELECT MAX(C1.TXN_ID)
            FROM MCCA_CSR C1
            WHERE C1.CARRIER_CLM_NUM = C.CARRIER_CLM_NUM
              AND C1.CLID = C.CLID
        )
          AND (C.CLOSED_IND IS NULL OR C.CLOSED_IND = 'N')
          AND C.REC_TYP = 'CSR'
          AND C.STATUS_LST = 'Open'
          AND C.STATUS NOT IN ('SB', 'SF')
          AND REGEXP_LIKE(C.CARRIER_CLM_NUM, '^([4-9]{1})\\d{8}$')
    """


def _dec(val: Any) -> Decimal | None:
    return Decimal(str(val)) if val is not None else None


def map_csr_amount_update_row(row: Dict[str, Any]) -> CsrDetail:
    """1:1 port of com.acg.mcca.batch.mapper.CsrAmountUpdateRowMapper."""
    return CsrDetail(
        carrier_claim_num=row.get("CARRIER_CLM_NUM"),
        clid=row.get("CLID"),
        csr_seq=int(row["CSR_SEQ"]) if row.get("CSR_SEQ") is not None else 0,
        record_type=row.get("REC_TYP"),
        status=row.get("STATUS"),
        plcy_exp_date=row.get("PLCY_EXP_DATE"),
        demand=row.get("DEMAND"),
        suit_date=row.get("SUIT_DT"),
        litgn_issue_desc=row.get("LITGN_ISSUE_DESC"),
        ssdi_appln_status=row.get("SSDI_APPLN_STATUS"),
        clmt_crnt_condn_futr_care_desc=row.get("CLMT_CRNT_CONDN_FUTR_CARE_DESC"),
        mcca_clm_num=_dec(row.get("MCCA_CLM_NUM")),
        status_lst=row.get("STATUS_LST"),
        claimt_prefix=row.get("CLMT_SUFFIX"),
        claimt_frst_name=row.get("CLMT_FST_NAME"),
        claimt_midl_in=row.get("CLMT_MI"),
        claimt_lst_name=row.get("CLMT_LST_NAME"),
        claimt_gender=row.get("CLMT_GNDR"),
        claimt_dob=row.get("CLMT_DOB"),
        claimt_addres1=row.get("CLMT_ADD1"),
        claimt_addres2=row.get("CLMT_ADD2"),
        claimt_city=row.get("CLMT_CITY"),
        claimt_state=row.get("CLMT_STATE"),
        claimt_zip=row.get("CLMT_ZIP"),
        claimt_county=row.get("CLMT_CNTY"),
        health_crr=row.get("HLTH_CRR"),
        claimt_status_cd=row.get("CLMT_STAT_CD"),
        relation_cd=row.get("RLN_CD"),
        seatbelt_cd=row.get("SEABLT_CD"),
        air_bg_use_cd=row.get("ARBG_USE_CD"),
        injured_desc=row.get("INJ_DESC"),
        injured_cd=row.get("INJ_CD"),
        claimt_death_dt=row.get("DEATH_DT"),
        carrier_user_id=row.get("CRR_USR_ID"),
        csr_due_dt=row.get("CSR_DUE_DT"),
        prjctd_lng_trm_instl_amt=_dec(row.get("PRJCTD_LNG_TRM_INSTL_AMT")),
        prjctd_lng_trm_medl_amt=_dec(row.get("PRJCTD_LNG_TRM_MEDL_AMT")),
        prjctd_lng_trm_othr_amt=_dec(row.get("PRJCTD_LNG_TRM_OTHR_AMT")),
        prjctd_lng_trm_outstndg_amt=_dec(row.get("PRJCTD_LNG_TRM_OUTSTNDG_AMT")),
        med_paid_to_dt=_dec(row.get("MED_PAID_TO_DT")),
        med_net_resrv=_dec(row.get("MED_NET_RESRV")),
        med_incurd=_dec(row.get("MED_INCURD")),
        res_chng=_dec(row.get("RES_CHNG")),
        new_net=_dec(row.get("NEW_NET")),
        new_incrd=_dec(row.get("NEW_INCRD")),
        wl_es_sl_paid_to_dt=_dec(row.get("WL_ES_SL_PAID_TO_DT")),
        wl_es_sl_net=_dec(row.get("WL_ES_SL_NET")),
        wl_es_sl_incrd=_dec(row.get("WL_ES_SL_INCRD")),
        hsptl_12_mnth_cst=_dec(row.get("HSPTL_12_MNTH_CST")),
        hsptl_annl_futr_cst=_dec(row.get("HSPTL_ANNL_FUTR_CST")),
        doc_lab_12_mnth_cst=_dec(row.get("DOC_LAB_12_MNTH_CST")),
        doc_lab_annl_futr_cst=_dec(row.get("DOC_LAB_ANNL_FUTR_CST")),
        home_pur_12_mnth_cst=_dec(row.get("HOME_PUR_12_MNTH_CST")),
        home_pur_annl_futr_cst=_dec(row.get("HOME_PUR_ANNL_FUTR_CST")),
        veh_pur_modfn_12_mnth_cst=_dec(row.get("VEH_PUR_MODFN_12_MNTH_CST")),
        veh_pur_annl_futr_cst=_dec(row.get("VEH_PUR_ANNL_FUTR_CST")),
        eqpmt_pur_12_mnth_cst=_dec(row.get("EQPMT_PUR_12_MNTH_CST")),
        eqpmt_pur_annl_futr_cst=_dec(row.get("EQPMT_PUR_ANNL_FUTR_CST")),
        pro_12_mnth_cst=_dec(row.get("PRO_12_MNTH_CST")),
        pro_annl_futr_cst=_dec(row.get("PRO_ANNL_FUTR_CST")),
        pre_drg_sup_12_mnth_cst=_dec(row.get("PRE_DRG_SUP_12_MNTH_CST")),
        pre_drg_sup_annl_futr_cst=_dec(row.get("PRE_DRG_SUP_ANNL_FUTR_CST")),
        therap_rehab_12_mnth_cst=_dec(row.get("THERAP_REHAB_12_MNTH_CST")),
        therap_rehab_annl_futr_cst=_dec(row.get("THERAP_REHAB_ANNL_FUTR_CST")),
        trnsprt_12_mnth_cst=_dec(row.get("TRNSPRT_12_MNTH_CST")),
        trnsprt_annl_futr_cst=_dec(row.get("TRNSPRT_ANNL_FUTR_CST")),
        case_mgmt_12_mnth_cst=_dec(row.get("CASE_MGMT_12_MNTH_CST")),
        case_mgmt_annl_futr_cst=_dec(row.get("CASE_MGMT_ANNL_FUTR_CST")),
        wgs_srv_sr_loss_12_mnth_cst=_dec(row.get("WGS_SRV_SR_LOSS_12_MNTH_CST")),
        wgs_srv_sr_loss_anl_futr_cst=_dec(row.get("WGS_SRV_SR_LOSS_ANL_FUTR_CST")),
        othr_12_mnth_cst=_dec(row.get("OTHR_12_MNTH_CST")),
        othr_annl_futr_cst=_dec(row.get("OTHR_ANNL_FUTR_CST")),
        totl_12_mnth_cst=_dec(row.get("TOTL_12_MNTH_CST")),
        tot_annl_futr_cst=_dec(row.get("TOT_ANNL_FUTR_CST")),
        resdntl_faclty_mnth_rate=_dec(row.get("RESDNTL_FACLTY_MNTH_RATE")),
        agncy_dly_rate=_dec(row.get("AGNCY_DLY_RATE")),
        agncy_hrly_rate=_dec(row.get("AGNCY_HRLY_RATE")),
        fmly_dly_rate=_dec(row.get("FMLY_DLY_RATE")),
        fmly_hrly_rate=_dec(row.get("FMLY_HRLY_RATE")),
        agncy_ac_hrs=_dec(row.get("AGNCY_AC_HRS")),
        fmly_ac_hrs=_dec(row.get("FMLY_AC_HRS")),
        health_ins_in_force=row.get("HLTH_INS_INFORCE_IND"),
        claimt_is_dceasd_ind=row.get("CLMT_DCSD_IND"),
        cordnt_no_fault=row.get("COORDINATE_NO_FLT_IND"),
        pip_clm_in_litg_ind=row.get("PIP_CLM_LITIGN_IND"),
        are_issue_in_litg_ind=row.get("LITGN_ISSUE_IND"),
        inj_party_app_ssdi_ind=row.get("INJ_PRTY_APPLD_SSDI_IND"),
        is_rvwd_or_uptd=row.get("IS_RVWD_OR_UPTD"),
        prbl_life_tm_care_ind=row.get("PRBL_LIFE_TM_CARE_IND"),
        noflt_hcc_cord_ind=row.get("NOFLT_HCC_CORD_IND"),
        closed_ind=row.get("CLOSED_IND"),
        retention_ind=row.get("RETENTION"),
        retention_amt=_dec(row.get("RETNTON_AMT")),
        life_exptncy=_dec(row.get("LIFE_EXPTNCY")),
        all_inj_cl_comb_paid_to_dt_med=_dec(row.get("ALL_INJ_CL_COMB_PAID_TO_DT_MED")),
        al_inj_cl_cm_pd_to_dt_wl_es_sl=_dec(row.get("AL_INJ_CL_CM_PD_TO_DT_WL_ES_SL")),
        alinj_cl_cm_pd_to_dt_medwlessl=_dec(row.get("ALINJ_CL_CM_PD_TO_DT_MEDWLESSL")),
        assign_to=row.get("ASSGND_PRSN"),
        last_updated_by=row.get("LST_UPDTING_PRSN"),
        carrier_id=_dec(row.get("CRR_ID")),
        ws_pol_cord_on_dt_loss=row.get("WS_PLCY_CORDNTD_DT_OF_LOSS_IND"),
        crnt_sts_clm_isues_in_dispte=row.get("CRNT_STS_CLM_ISUES_IN_DISPTE"),
        lock_status=row.get("LOCK_STATUS"),
        submitted_to=row.get("SUBMITTED_TO"),
        submitted_by=row.get("SUBMITTED_BY"),
        icn_sub_to=row.get("ICN_SUB_TO"),
        submitted_date=row.get("SUBMITTED_DATE"),
        all_inj_cl_comb_paid_to_dt_res=_dec(row.get("ALL_INJ_CL_COMB_PAID_TO_DT_RES")),
        alinj_cl_cm_pd_to_dt_medwlres=_dec(row.get("ALINJ_CL_CM_PD_TO_DT_MEDWLRES")),
        agncy_dly_rate_2=_dec(row.get("AGNCY_DLY_RATE_2")),
        agncy_hrly_rate_2=_dec(row.get("AGNCY_HRLY_RATE_2")),
        fmly_dly_rate_2=_dec(row.get("FMLY_DLY_RATE_2")),
        fmly_hrly_rate_2=_dec(row.get("FMLY_HRLY_RATE_2")),
        agncy_ac_hrs_2=_dec(row.get("AGNCY_AC_HRS_2")),
        fmly_ac_hrs_2=_dec(row.get("FMLY_AC_HRS_2")),
        agncy_dly_rate_3=_dec(row.get("AGNCY_DLY_RATE_3")),
        agncy_hrly_rate_3=_dec(row.get("AGNCY_HRLY_RATE_3")),
        fmly_dly_rate_3=_dec(row.get("FMLY_DLY_RATE_3")),
        fmly_hrly_rate_3=_dec(row.get("FMLY_HRLY_RATE_3")),
        agncy_ac_hrs_3=_dec(row.get("AGNCY_AC_HRS_3")),
        fmly_ac_hrs_3=_dec(row.get("FMLY_AC_HRS_3")),
        agncy_dly_rate_4=_dec(row.get("AGNCY_DLY_RATE_4")),
        agncy_hrly_rate_4=_dec(row.get("AGNCY_HRLY_RATE_4")),
        fmly_dly_rate_4=_dec(row.get("FMLY_DLY_RATE_4")),
        fmly_hrly_rate_4=_dec(row.get("FMLY_HRLY_RATE_4")),
        agncy_ac_hrs_4=_dec(row.get("AGNCY_AC_HRS_4")),
        fmly_ac_hrs_4=_dec(row.get("FMLY_AC_HRS_4")),
        agncy_level_of_care_1=row.get("AGNCY_LEVEL_OF_CARE_1"),
        agncy_level_of_care_2=row.get("AGNCY_LEVEL_OF_CARE_2"),
        agncy_level_of_care_3=row.get("AGNCY_LEVEL_OF_CARE_3"),
        agncy_level_of_care_4=row.get("AGNCY_LEVEL_OF_CARE_4"),
        fmly_level_of_care_1=row.get("FMLY_LEVEL_OF_CARE_1"),
        fmly_level_of_care_2=row.get("FMLY_LEVEL_OF_CARE_2"),
        fmly_level_of_care_3=row.get("FMLY_LEVEL_OF_CARE_3"),
        fmly_level_of_care_4=row.get("FMLY_LEVEL_OF_CARE_4"),
        avg_monthly_rate=_dec(row.get("AVG_MNTHLY_RATE")),
        room_dly_rate=_dec(row.get("ROOM_DLY_RATE")),
        ptd_reserve_asof_date=row.get("PTD_RESERVES_AS_OF_DATE"),
    )


# ==============================================================================
# STEP updateRptdColumn READER: updateRptdDetailJdbcReader (beanInfo.xml 1419-1482)
# ==============================================================================
def get_update_rptd_detail_sql(batch_date_param: str) -> str:
    return f"""
        SELECT
            CLAIM.TXN_ID,
            CLAIM.CARRIER_CLM_NUM,
            CLAIM.MCCA_CLM_NUM,
            CLAIM.LINK_ID,
            CLAIM.MASTER_CLAIM_IND,
            CLAIM.RETENTION,
            CLAIM.THRESHOLD,
            CLAIM.IS_PIP,
            CLAIM.DATE_OF_LOSS,
            CLAIM.CLAIM_STATUS,
            CLAIM.POLICY_INCEPTION_DATE,
            CLAIM.POLICY_END_DATE,
            CLAIM.COMPANY,
            CLAIM.RPTD,
            CLAIM.CARRIER_PLCY_NUM,
            CLAIM.UPDATE_DATE,
            CLAIM.PIP_UNLMT_IND,
            CLAIM.BROKER,
            CLAIM.STATE,
            CLAIM.LOB,
            CLAIM.CONV_DT,
            CLAIM.PREV_IPM_CLMNBR,
            CLAIM.IPM_CNVTD_CLM_IND,
            CSR.CLOSED_IND,
            ICN.STATUS AS ICN_STATUS
        FROM MCCA_CLAIM CLAIM,
             MCCA_ICN ICN,
             MCCA_CSR CSR
        WHERE CLAIM.CARRIER_CLM_NUM = ICN.CARRIER_CLM_NUM
          AND ICN.REC_TYP = 'ICN'
          AND TO_DATE(TO_CHAR(ICN.LST_UPDT_TIME_STMP, 'MM/DD/YYYY'), 'MM/DD/YYYY') <=
              TO_DATE('{batch_date_param}', 'YYYY/MM/DD')
          AND ICN.TXN_ID IN (
              SELECT MAX(ICN2.TXN_ID)
              FROM MCCA_ICN ICN2
              WHERE ICN2.CARRIER_CLM_NUM = ICN.CARRIER_CLM_NUM
                AND ICN2.REC_TYP = ICN.REC_TYP
                AND TO_DATE(TO_CHAR(ICN2.LST_UPDT_TIME_STMP, 'MM/DD/YYYY'), 'MM/DD/YYYY') <=
                    TO_DATE('{batch_date_param}', 'YYYY/MM/DD')
          )
          AND CSR.CARRIER_CLM_NUM = ICN.CARRIER_CLM_NUM
          AND CSR.CLID = '0'
          AND CSR.REC_TYP = 'ICN'
          AND TO_DATE(TO_CHAR(CSR.LST_UPDT_TIME_STMP, 'MM/DD/YYYY'), 'MM/DD/YYYY') <=
              TO_DATE('{batch_date_param}', 'YYYY/MM/DD')
          AND CSR.TXN_ID IN (
              SELECT MAX(CSR2.TXN_ID)
              FROM MCCA_CSR CSR2
              WHERE CSR2.CARRIER_CLM_NUM = CSR.CARRIER_CLM_NUM
                AND CSR2.CLID = CSR.CLID
                AND CSR2.REC_TYP = CSR.REC_TYP
                AND TO_DATE(TO_CHAR(CSR2.LST_UPDT_TIME_STMP, 'MM/DD/YYYY'), 'MM/DD/YYYY') <=
                    TO_DATE('{batch_date_param}', 'YYYY/MM/DD')
          )
          AND TO_DATE(TO_CHAR(CLAIM.UPDATE_DATE, 'mm/dd/yyyy'), 'mm/dd/yyyy') <=
              TO_DATE('{batch_date_param}', 'YYYY/MM/DD')
          AND CLAIM.TXN_ID IN (
              SELECT MAX(TXN_ID)
              FROM MCCA_CLAIM CLAIM2
              WHERE CLAIM2.CARRIER_CLM_NUM = CLAIM.CARRIER_CLM_NUM
                AND TO_DATE(TO_CHAR(CLAIM2.UPDATE_DATE, 'mm/dd/yyyy'), 'mm/dd/yyyy') <=
                    TO_DATE('{batch_date_param}', 'YYYY/MM/DD')
          )
    """


def map_update_rptd_row(row: Dict[str, Any]) -> IcnCsrDetail:
    """1:1 port of com.acg.mcca.batch.mapper.UpdateRptdRowMapper."""
    return IcnCsrDetail(
        txn_id=str(row["TXN_ID"]) if row.get("TXN_ID") is not None else None,
        carrier_claim_num=row.get("CARRIER_CLM_NUM"),
        mcca_claim_num=row.get("MCCA_CLM_NUM"),
        link_claim=row.get("LINK_ID"),
        master_claim_ind=row.get("MASTER_CLAIM_IND"),
        retention_amt=float(row["RETENTION"]) if row.get("RETENTION") is not None else 0.0,
        threshold_amt=float(row["THRESHOLD"]) if row.get("THRESHOLD") is not None else 0.0,
        is_pip_ind=row.get("IS_PIP"),
        date_of_loss=row.get("DATE_OF_LOSS"),
        status=row.get("CLAIM_STATUS"),
        policy_effc_dt=row.get("POLICY_INCEPTION_DATE"),
        policy_exp_dt=row.get("POLICY_END_DATE"),
        company=row.get("COMPANY"),
        rptd=row.get("RPTD"),
        carrier_policy_num=row.get("CARRIER_PLCY_NUM"),
        last_updated_time_stamp=row.get("UPDATE_DATE"),
        is_icn_closed=row.get("CLOSED_IND"),
        icn_status=row.get("ICN_STATUS"),
        pip_unlmt_ind=row.get("PIP_UNLMT_IND"),
        broker=row.get("BROKER"),
        state=row.get("STATE"),
        lob=row.get("LOB"),
        conv_dt=row.get("CONV_DT"),
        prev_ipm_clmnbr=row.get("PREV_IPM_CLMNBR"),
        ipm_convtd_clm_ind=row.get("IPM_CNVTD_CLM_IND"),
    )
