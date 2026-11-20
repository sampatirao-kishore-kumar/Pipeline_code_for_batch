"""
Domain Models for icnCsrToMccaJob.
1:1 port of com.acg.mcca.batch.model.{IcnCsrDetail, TmpIcnDetail, TmpCsrDetail, CsrDetail, OthrInjClmtsPymt, Threshold}.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass
class Threshold:
    """1:1 port of com.acg.mcca.batch.model.Threshold (from MCCA_THRESHOLD table)."""
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    threshold_amount: Optional[str] = None


@dataclass
class IcnCsrDetail:
    """1:1 port of com.acg.mcca.batch.model.IcnCsrDetail."""
    txn_id: Optional[str] = None
    carrier_claim_num: Optional[str] = None
    clid: Optional[str] = None
    csr_seq: Optional[Decimal] = None
    record_type: Optional[str] = None
    status: Optional[str] = None
    icn_status: Optional[str] = None
    is_icn_closed: Optional[str] = None
    company: Optional[str] = None
    date_of_loss: Optional[date] = None
    is_pip_ind: Optional[str] = None
    master_claim_ind: Optional[str] = None
    mcca_claim_num: Optional[str] = None
    retention_amt: Optional[float] = None
    threshold_amt: Optional[float] = None
    accident_date: Optional[date] = None
    accident_desc: Optional[str] = None
    accident_addr1: Optional[str] = None
    accident_addr2: Optional[str] = None
    accident_city: Optional[str] = None
    accident_state: Optional[str] = None
    accident_zip: Optional[str] = None
    accident_county: Optional[str] = None
    comp_crs_clm_ind: Optional[str] = None
    cross_comp_clm_num: Optional[str] = None
    maipf_jua_ind: Optional[str] = None
    com_plcy_ind: Optional[str] = None
    adjuster_id: Optional[str] = None
    adjuster_frst_name: Optional[str] = None
    adjuster_lst_name: Optional[str] = None
    adjuster_ph_num: Optional[Decimal] = None
    carrier_id: Optional[int] = None
    carrier_policy_num: Optional[str] = None
    plcy_wrtn_crdnt_bas: Optional[str] = None
    ws_pol_cord_on_dt_loss: Optional[str] = None
    insured_prefix: Optional[str] = None
    insured_frst_name: Optional[str] = None
    insured_lst_name: Optional[str] = None
    insured_midl_in: Optional[str] = None
    insured_gender: Optional[str] = None
    insured_dob: Optional[date] = None
    insured_addr1: Optional[str] = None
    insured_addr2: Optional[str] = None
    insured_city: Optional[str] = None
    insured_state: Optional[str] = None
    insured_zip: Optional[str] = None
    insured_county: Optional[str] = None
    policy_effc_dt: Optional[date] = None
    policy_exp_dt: Optional[date] = None
    link_claim: Optional[str] = None
    paid_to_date: Optional[float] = None
    assign_to: Optional[str] = None
    carrier_user_id: Optional[str] = None
    batch_num: Optional[int] = None
    csr_due_dt: Optional[date] = None
    closed_ind: Optional[str] = None
    prbl_life_tm_care_ind: Optional[str] = None
    status_lst: Optional[str] = None
    rptd: Optional[str] = None
    last_updated_time_stamp: Optional[datetime] = None
    pip_unlmt_ind: Optional[str] = None
    broker: Optional[str] = None
    state: Optional[str] = None
    lob: Optional[str] = None
    conv_dt: Optional[date] = None
    prev_ipm_clmnbr: Optional[str] = None
    ipm_convtd_clm_ind: Optional[str] = None
    icn_new: bool = False
    stop_icn_csr_exception: bool = False


@dataclass
class TmpIcnDetail(IcnCsrDetail):
    """1:1 port of com.acg.mcca.batch.model.TmpIcnDetail (used in Step 5)."""
    tmp_accident_addr1: Optional[str] = None
    tmp_accident_addr2: Optional[str] = None
    tmp_accident_city: Optional[str] = None
    tmp_accident_desc: Optional[str] = None
    tmp_accident_state: Optional[str] = None
    tmp_accident_zip: Optional[str] = None
    tmp_carrier_policy_num: Optional[str] = None
    tmp_com_plcy_ind: Optional[str] = None
    tmp_carrier_id: Optional[int] = None
    tmp_comp_crs_clm_ind: Optional[str] = None
    tmp_cross_comp_clm_num: Optional[str] = None
    tmp_insured_addr1: Optional[str] = None
    tmp_insured_addr2: Optional[str] = None
    tmp_insured_city: Optional[str] = None
    tmp_insured_state: Optional[str] = None
    tmp_insured_zip: Optional[str] = None
    tmp_insured_prefix: Optional[str] = None
    tmp_insured_frst_name: Optional[str] = None
    tmp_insured_lst_name: Optional[str] = None
    tmp_insured_midl_in: Optional[str] = None
    tmp_insured_gender: Optional[str] = None
    tmp_insured_dob: Optional[date] = None
    tmp_maipf_jua_ind: Optional[str] = None
    tmp_adjuster_id: Optional[str] = None
    tmp_ws_pol_cord_on_dt_loss: Optional[str] = None
    tmp_plcy_wrtn_crdnt_bas: Optional[str] = None


@dataclass
class CsrDetail:
    """1:1 port of com.acg.mcca.batch.model.CsrDetail (MCCA_CSR row)."""
    carrier_claim_num: Optional[str] = None
    clid: Optional[str] = None
    csr_seq: int = 0
    record_type: Optional[str] = None
    status: Optional[str] = None
    plcy_exp_date: Optional[date] = None
    demand: Optional[str] = None
    suit_date: Optional[date] = None
    litgn_issue_desc: Optional[str] = None
    ssdi_appln_status: Optional[str] = None
    clmt_crnt_condn_futr_care_desc: Optional[str] = None
    mcca_clm_num: Optional[Decimal] = None
    mcca_claim_number: Optional[str] = None
    status_lst: Optional[str] = None
    claimt_prefix: Optional[str] = None
    claimt_frst_name: Optional[str] = None
    claimt_midl_in: Optional[str] = None
    claimt_lst_name: Optional[str] = None
    claimt_gender: Optional[str] = None
    claimt_dob: Optional[date] = None
    claimt_addres1: Optional[str] = None
    claimt_addres2: Optional[str] = None
    claimt_city: Optional[str] = None
    claimt_state: Optional[str] = None
    claimt_zip: Optional[str] = None
    claimt_county: Optional[str] = None
    health_crr: Optional[str] = None
    claimt_status_cd: Optional[str] = None
    relation_cd: Optional[str] = None
    seatbelt_cd: Optional[str] = None
    air_bg_use_cd: Optional[str] = None
    injured_desc: Optional[str] = None
    injured_cd: Optional[str] = None
    claimt_death_dt: Optional[date] = None
    carrier_user_id: Optional[str] = None
    csr_due_dt: Optional[date] = None
    prjctd_lng_trm_instl_amt: Optional[Decimal] = None
    prjctd_lng_trm_medl_amt: Optional[Decimal] = None
    prjctd_lng_trm_othr_amt: Optional[Decimal] = None
    prjctd_lng_trm_outstndg_amt: Optional[Decimal] = None
    med_paid_to_dt: Optional[Decimal] = None
    med_net_resrv: Optional[Decimal] = None
    med_incurd: Optional[Decimal] = None
    res_chng: Optional[Decimal] = None
    new_net: Optional[Decimal] = None
    new_incrd: Optional[Decimal] = None
    wl_es_sl_paid_to_dt: Optional[Decimal] = None
    wl_es_sl_net: Optional[Decimal] = None
    wl_es_sl_incrd: Optional[Decimal] = None
    hsptl_12_mnth_cst: Optional[Decimal] = None
    hsptl_annl_futr_cst: Optional[Decimal] = None
    doc_lab_12_mnth_cst: Optional[Decimal] = None
    doc_lab_annl_futr_cst: Optional[Decimal] = None
    home_pur_12_mnth_cst: Optional[Decimal] = None
    home_pur_annl_futr_cst: Optional[Decimal] = None
    veh_pur_modfn_12_mnth_cst: Optional[Decimal] = None
    veh_pur_annl_futr_cst: Optional[Decimal] = None
    eqpmt_pur_12_mnth_cst: Optional[Decimal] = None
    eqpmt_pur_annl_futr_cst: Optional[Decimal] = None
    pro_12_mnth_cst: Optional[Decimal] = None
    pro_annl_futr_cst: Optional[Decimal] = None
    pre_drg_sup_12_mnth_cst: Optional[Decimal] = None
    pre_drg_sup_annl_futr_cst: Optional[Decimal] = None
    therap_rehab_12_mnth_cst: Optional[Decimal] = None
    therap_rehab_annl_futr_cst: Optional[Decimal] = None
    trnsprt_12_mnth_cst: Optional[Decimal] = None
    trnsprt_annl_futr_cst: Optional[Decimal] = None
    case_mgmt_12_mnth_cst: Optional[Decimal] = None
    case_mgmt_annl_futr_cst: Optional[Decimal] = None
    wgs_srv_sr_loss_12_mnth_cst: Optional[Decimal] = None
    wgs_srv_sr_loss_anl_futr_cst: Optional[Decimal] = None
    othr_12_mnth_cst: Optional[Decimal] = None
    othr_annl_futr_cst: Optional[Decimal] = None
    totl_12_mnth_cst: Optional[Decimal] = None
    tot_annl_futr_cst: Optional[Decimal] = None
    resdntl_faclty_mnth_rate: Optional[Decimal] = None
    agncy_dly_rate: Optional[Decimal] = None
    agncy_hrly_rate: Optional[Decimal] = None
    fmly_dly_rate: Optional[Decimal] = None
    fmly_hrly_rate: Optional[Decimal] = None
    agncy_ac_hrs: Optional[Decimal] = None
    fmly_ac_hrs: Optional[Decimal] = None
    health_ins_in_force: Optional[str] = None
    claimt_is_dceasd_ind: Optional[str] = None
    cordnt_no_fault: Optional[str] = None
    pip_clm_in_litg_ind: Optional[str] = None
    are_issue_in_litg_ind: Optional[str] = None
    inj_party_app_ssdi_ind: Optional[str] = None
    is_rvwd_or_uptd: Optional[str] = None
    prbl_life_tm_care_ind: Optional[str] = None
    noflt_hcc_cord_ind: Optional[str] = None
    closed_ind: Optional[str] = None
    retention_ind: Optional[str] = None
    retention_amt: Optional[Decimal] = None
    life_exptncy: Optional[Decimal] = None
    all_inj_cl_comb_paid_to_dt_med: Optional[Decimal] = None
    al_inj_cl_cm_pd_to_dt_wl_es_sl: Optional[Decimal] = None
    alinj_cl_cm_pd_to_dt_medwlessl: Optional[Decimal] = None
    assign_to: Optional[str] = None
    last_updated_by: Optional[str] = None
    carrier_id: Optional[Decimal] = None
    ws_pol_cord_on_dt_loss: Optional[str] = None
    crnt_sts_clm_isues_in_dispte: Optional[str] = None
    lock_status: Optional[str] = None
    submitted_to: Optional[str] = None
    submitted_by: Optional[str] = None
    icn_sub_to: Optional[str] = None
    submitted_date: Optional[date] = None
    all_inj_cl_comb_paid_to_dt_res: Optional[Decimal] = None
    alinj_cl_cm_pd_to_dt_medwlres: Optional[Decimal] = None
    # MCCA 3.3 multi-tier attendant care fields
    agncy_dly_rate_2: Optional[Decimal] = None
    agncy_hrly_rate_2: Optional[Decimal] = None
    fmly_dly_rate_2: Optional[Decimal] = None
    fmly_hrly_rate_2: Optional[Decimal] = None
    agncy_ac_hrs_2: Optional[Decimal] = None
    fmly_ac_hrs_2: Optional[Decimal] = None
    agncy_dly_rate_3: Optional[Decimal] = None
    agncy_hrly_rate_3: Optional[Decimal] = None
    fmly_dly_rate_3: Optional[Decimal] = None
    fmly_hrly_rate_3: Optional[Decimal] = None
    agncy_ac_hrs_3: Optional[Decimal] = None
    fmly_ac_hrs_3: Optional[Decimal] = None
    agncy_dly_rate_4: Optional[Decimal] = None
    agncy_hrly_rate_4: Optional[Decimal] = None
    fmly_dly_rate_4: Optional[Decimal] = None
    fmly_hrly_rate_4: Optional[Decimal] = None
    agncy_ac_hrs_4: Optional[Decimal] = None
    fmly_ac_hrs_4: Optional[Decimal] = None
    agncy_level_of_care_1: Optional[str] = None
    agncy_level_of_care_2: Optional[str] = None
    agncy_level_of_care_3: Optional[str] = None
    agncy_level_of_care_4: Optional[str] = None
    fmly_level_of_care_1: Optional[str] = None
    fmly_level_of_care_2: Optional[str] = None
    fmly_level_of_care_3: Optional[str] = None
    fmly_level_of_care_4: Optional[str] = None
    avg_monthly_rate: Optional[Decimal] = None
    room_dly_rate: Optional[Decimal] = None
    ptd_reserve_asof_date: Optional[date] = None


@dataclass
class TmpCsrDetail(CsrDetail):
    """1:1 port of com.acg.mcca.batch.model.TmpCsrDetail (used in Step 4)."""
    icn_status: Optional[str] = None
    new_claimant_ind: Optional[str] = None
    tmp_claimt_prefix: Optional[str] = None
    tmp_claimt_frst_name: Optional[str] = None
    tmp_claimt_lst_name: Optional[str] = None
    tmp_claimt_gender: Optional[str] = None
    tmp_claimt_dob: Optional[date] = None
    tmp_claimt_addres1: Optional[str] = None
    tmp_claimt_addres2: Optional[str] = None
    tmp_claimt_city: Optional[str] = None
    tmp_claimt_state: Optional[str] = None
    tmp_claimt_zip: Optional[str] = None
    tmp_are_issue_in_litg_ind: Optional[str] = None
    tmp_pip_clm_in_litg_ind: Optional[str] = None
    tmp_injured_desc: Optional[str] = None
    tmp_cordnt_no_fault: Optional[str] = None
    tmp_health_crr: Optional[str] = None
    tmp_claimt_status_cd: Optional[str] = None
    tmp_relation_cd: Optional[str] = None
    tmp_seatbelt_cd: Optional[str] = None
    tmp_air_bg_use_cd: Optional[str] = None
    tmp_injured_cd: Optional[str] = None
    tmp_claimt_is_dceasd_ind: Optional[str] = None
    tmp_demand: Optional[str] = None
    tmp_suit_date: Optional[date] = None
    tmp_litgn_issue_desc: Optional[str] = None
    tmp_claimt_death_dt: Optional[date] = None
    tmp_pip_clsd_ind: Optional[str] = None
    tmp_claimt_midl_in: Optional[str] = None


@dataclass
class OthrInjClmtsPymt:
    """1:1 port of com.acg.mcca.batch.model.OthrInjClmtsPymt (MCCA_OTHR_INJ_CLMTS_PYMT row)."""
    txn_id: int = 0
    carrier_clm_num: Optional[str] = None
    cl_id: Optional[str] = None        # maps to CL_ID column (other claimant ID)
    clid: Optional[str] = None         # maps to CLID column (primary claimant ID or '0')
    rec_typ: Optional[str] = None
    clm_num: Optional[str] = None
    clm_type: Optional[str] = None     # '1', '2', or '3'
    pip_ind: Optional[str] = None
    csr_seq: Optional[Decimal] = None
    med: Optional[Decimal] = None
    wl_es_sl: Optional[Decimal] = None
    reserve_amt: Optional[Decimal] = None
    other_proj_seq: int = 0
    # Transient helper fields used in OthrInjClmtsDaoImpl
    cross_clm_num: Optional[str] = None
    master_claim_ind: Optional[str] = None
    link_id: Optional[str] = None
    master_claim: Optional[str] = None
    coverage: Optional[str] = None
    losses_paid: Optional[Decimal] = None
    cross_comp_clm_type: Optional[str] = None
    facts_claim_number: Optional[str] = None
