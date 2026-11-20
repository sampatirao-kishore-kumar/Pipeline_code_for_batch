"""
Configuration and Constants for icnCsrToMccaJob.
1:1 port of com.acg.mcca.batch.util.BatchConstants and AlloyDB connection settings.
"""

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass


class BatchConstants:
    """Exact port of com.acg.mcca.batch.util.BatchConstants."""
    DATE_PATTERN = "MM/dd/yyyy"
    DOUBLE_PATTERN = "##########.##;0"
    EMPTY_STRING = ""
    CROSS_COMPANIAN_IND_YES = "YES"
    CROSS_COMPANIAN_IND_NO = "NO"
    REDEPOSIT_YES = "YES"
    REDEPOSIT_NO = "NO"
    YES_CD = "Y"
    NO_CD = "N"

    RFR_STATUS_PENDING = "PN"
    RFR_STATUS_SUBMITTED = "SUB"
    RFR_STATUS_ERROR = "ER"
    RFR_STATUS_REJECTED = "REJ"
    RFR_STATUS_OK = "OK"
    RFR_STATUS_SUBMITTED_CD = "SB"

    DEFAULT_TIN = "00-0000000"
    SOURCE_SYSTEM_FACTS = "FACTS"
    AUTO_CLUB_INSURANCE_ASSOCIATION_CD = "1124"
    AUTO_CLUB_GROUP_INSURANCE_COMPANY_CD = "1125"
    MEMBER_SELECT_INSURANCE_COMPANY_CD = "1126"
    LEGACY_COMPANY_CD = "1138"

    MCCA_USER_ID = "MCCA"
    CAAS_USER_ID = "MCCABATCH"
    ZERO = "0"
    NA_STRING = "NA"
    CLOSED = "Closed"
    OPEN = "Open"
    STATUS_SUBMITTED_FINANCE_CD = "SF"
    SUBMITTED_TO_FINANCE = "F"
    BATCH_LST_UPDTING_PRSN = "Batch"
    ASSIGNTO_CATEGORY = "mcca_assign_to"
    CARRIER_USERID_CATEGORY = "mcca_assign_carrier"
    ICN_REC_TYPE = "ICN"
    CSR_REC_TYPE = "CSR"
    STATUS_PENDING_CD = "PN"
    PARENT = "P"
    COPIED = "C"
    MCCA_DB_DATE_FORMAT = "yyyy-MM-dd"
    MCCA_DATE_FORMAT = "MM/dd/yyyy"
    STATUS_SUBMITTED_MCCA_CD = "SB"
    APOSTROPHE_DELIMITER = "'"
    COMMA_DELIMITER = ","
    COVERAGE_ZPIP = "ZPIP"
    COVERAGE_ZWL = "ZWL"
    COVERAGE_ZSL = "ZSL"
    MED_NET_RESRV = "MED_NET_RESRV"
    WL_ES_SL_NET = "WL_ES_SL_NET"
    WL_ES_SL_PAID_TO_DT = "WL_ES_SL_PAID_TO_DT"
    MED_PAID_TO_DT = "MED_PAID_TO_DT"
    MCCA_BATCH_DATE_FORMAT = "YYYYMMDD"
    CLM_TYPE_1 = "1"
    CLM_TYPE_2 = "2"
    CLM_TYPE_3 = "3"
    PROCESS_NEW_CLID_EXCEPTION_CODE = "8"
    STOP_ICN_CSR_EXCEPTION_CODE = "9"
    RPTD_SUBMITTED_MCCA_CD = "RM"
    RPTD_SUBMITTED_FINANCE_CD = "RF"
    RPTD_CLOSED_CD = "CL"
    ASSIGNTO_DEFAULT = "default"
    OPEN_STATUS_CD = "O"
    CLOSED_STATUS_CD = "C"
    REGEX_FACTS_CLAIMS = r"^([4-9]{1})\d{8}$"
    PREFIX_HONOR = "HONOR"
    PREFIX_HONOR_CD = "HONO"


@dataclass
class JobConfig:
    """
    AlloyDB (PostgreSQL) connection, Web Service, and SMTP configuration.
    Update the defaults below or set them via environment variables / .env file.
    """
    # AlloyDB (PostgreSQL) connection details
    db_dialect: str = os.getenv("MCCA_DB_DIALECT", "postgresql")  # 'postgresql' for AlloyDB
    db_host: str = os.getenv("MCCA_DB_HOST", "127.0.0.1")         # Put your AlloyDB IP / Auth Proxy host here
    db_port: int = int(os.getenv("MCCA_DB_PORT", "5432"))         # AlloyDB default port: 5432
    db_name: str = os.getenv("MCCA_DB_NAME", "postgres")          # Put your AlloyDB database name here
    db_user: str = os.getenv("MCCA_DB_USER", "postgres")          # Put your AlloyDB username here
    db_password: str = os.getenv("MCCA_DB_PASSWORD", "")          # Put your AlloyDB password here
    db_schema: str = os.getenv("MCCA_DB_SCHEMA", "public")        # Put your AlloyDB schema name here (e.g. mcca / public)
    db_sslmode: str = os.getenv("MCCA_DB_SSLMODE", "prefer")      # 'prefer' or 'require' for AlloyDB

    # External Web Services (from MccaBatchUtil JNDI lookups)
    caas_ws_url: str = os.getenv("MCCA_CAAS_WS_URL", "")
    address_scrub_ws_url: str = os.getenv("MCCA_ADDRESS_SCRUB_WS_URL", "")

    # SMTP Mail Configuration (from beanInfo.xml icnCsrMailImpl)
    smtp_host: str = os.getenv("MCCA_SMTP_HOST", "localhost")
    smtp_port: int = int(os.getenv("MCCA_SMTP_PORT", "25"))
    mail_from: str = os.getenv("MCCA_MAIL_FROM", "mcca-batch@acg.aaa.com")
    mail_to: str = os.getenv("MCCA_MAIL_TO", "mcca-support@acg.aaa.com")
    icn_csr_subject: str = os.getenv(
        "MCCA_ICN_CSR_SUBJECT",
        "MCCA Batch Process Completed: ICNCSR"
    )
    commit_interval: int = 1000  # Matches commit-interval="1000" in icnCsrToMccaJob.xml
