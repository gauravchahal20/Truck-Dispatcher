from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class ContactBase(BaseModel):
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    is_decision_maker: bool = False
    confidence: float = 0.5
    source_url: Optional[str] = None
    verification_status: Optional[str] = "UNVERIFIED"
    dnc_flag: Optional[bool] = False


class ContactCreate(ContactBase):
    pass


class ContactResponse(ContactBase):
    id: str
    company_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SourceRecordResponse(BaseModel):
    id: str
    source_name: str
    source_url: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None
    extraction_confidence: float = 1.0
    discovered_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VerificationRecordResponse(BaseModel):
    id: str
    step_name: str
    status: str
    confidence: float
    evidence_text: Optional[str] = None
    source_url: Optional[str] = None
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IntentSignalResponse(BaseModel):
    id: str
    signal_type: str
    title: Optional[str] = None
    description: Optional[str] = None
    source_url: Optional[str] = None
    confidence: float
    strength: Optional[float] = 1.0
    observed_at: Optional[datetime] = None
    half_life_days: Optional[float] = 60.0
    evidence: Optional[Dict[str, Any]] = None
    is_sensitive: Optional[bool] = False
    detected_date: datetime

    model_config = ConfigDict(from_attributes=True)


class LeadScoreResponse(BaseModel):
    id: str
    total_score: float
    fit_score: Optional[float] = 0.0
    intent_score: Optional[float] = 0.0
    priority: str
    scoring_version: Optional[str] = "2.0"
    target_fleet_size_score: float
    verified_active_carrier_score: float
    decision_maker_score: float
    equipment_verified_score: float
    usable_contact_score: float
    intent_signal_score: float
    tech_business_event_score: float
    score_breakdown: Optional[Dict[str, Any]] = None
    scored_at: datetime

    model_config = ConfigDict(from_attributes=True)



class LeadStatusHistoryResponse(BaseModel):
    id: str
    from_status: Optional[str] = None
    to_status: str
    reason: Optional[str] = None
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CompanyBase(BaseModel):
    usdot: Optional[str] = None
    mc_number: Optional[str] = None
    company_name: str
    legal_name: Optional[str] = None
    dba_name: Optional[str] = None
    lead_type: Optional[str] = "CARRIER"  # CARRIER (Have Trucks) or SHIPPER (Need Trucks)
    industry_sector: Optional[str] = None
    freight_volume: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    fleet_size: Optional[int] = None
    driver_count: Optional[int] = None
    equipment: List[str] = Field(default_factory=list)
    carrier_operation: Optional[str] = None
    operating_status: Optional[str] = None
    authority_status: Optional[str] = "UNKNOWN"
    authority_status_source: Optional[str] = None
    insurance_filing_status: Optional[str] = "UNKNOWN"
    safety_rating: Optional[str] = None
    mcs_150_date: Optional[str] = None
    field_provenance: Optional[Dict[str, Any]] = Field(default_factory=dict)
    fleet_inconsistent: Optional[bool] = False
    hazmat_carrier: Optional[bool] = False
    phone_region_mismatch: Optional[bool] = False
    needs_reverification: Optional[bool] = False
    dnc_flag: Optional[bool] = False
    suppression_reason: Optional[str] = None


class CompanyCreate(CompanyBase):
    lead_source: Optional[str] = None
    source_url: Optional[str] = None
    notes: Optional[str] = None


class CompanyResponse(CompanyBase):
    id: str
    run_id: Optional[str] = None
    normalized_name: Optional[str] = None
    normalized_domain: Optional[str] = None
    normalized_phone: Optional[str] = None
    lead_status: str
    qualification_reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    lead_score: float
    fit_score: Optional[float] = 0.0
    intent_score: Optional[float] = 0.0
    priority: Optional[str] = None
    scoring_version: Optional[str] = "2.0"
    verification_status: str
    verification_confidence: float
    verification_date: Optional[datetime] = None
    lead_source: Optional[str] = None
    source_url: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    contacts: List[ContactResponse] = Field(default_factory=list)
    sources: List[SourceRecordResponse] = Field(default_factory=list)
    verification_records: List[VerificationRecordResponse] = Field(default_factory=list)
    intent_signals: List[IntentSignalResponse] = Field(default_factory=list)
    lead_score_detail: Optional[LeadScoreResponse] = None
    status_history: List[LeadStatusHistoryResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class RunCreateRequest(BaseModel):
    name: Optional[str] = "Trucking & Freight Lead Generation Run"
    target_states: List[str] = ["TX", "CA", "GA", "IL", "OH", "PA", "FL", "NC", "IN", "MI"]
    lead_type: Optional[str] = "ALL"  # ALL, CARRIER (Have Trucks), SHIPPER (Need Trucks)
    fleet_size_min: int = 1
    fleet_size_max: int = 9999
    equipment_types: List[str] = ["dry_van", "reefer", "flatbed", "drayage", "hotshot", "box_truck", "tanker"]
    target_lead_count: Optional[int] = 35
    score_threshold: float = 5.0
    active_sources: Optional[List[str]] = None
    auto_enrich: bool = True


class RunResponse(BaseModel):
    id: str
    name: str
    status: str
    target_states: List[str]
    lead_type: Optional[str] = "ALL"
    fleet_size_min: int
    fleet_size_max: int
    equipment_types: List[str]
    target_lead_count: Optional[int] = None
    score_threshold: float
    raw_count: int
    verified_count: int
    qualified_count: int
    final_count: int
    rejected_count: int
    duplicate_count: int
    priority_a_count: int
    priority_b_count: int
    source_counts: Dict[str, int]
    error_count: int
    google_sheet_url: Optional[str] = None
    export_csv_path: Optional[str] = None
    export_xlsx_path: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ErrorLogResponse(BaseModel):
    id: str
    run_id: Optional[str] = None
    company_id: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    error_type: str
    error_message: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardStatsResponse(BaseModel):
    total_runs: int
    total_raw_leads: int
    total_verified_leads: int
    total_final_leads: int
    total_priority_a: int
    total_priority_b: int
    total_rejected: int
    total_duplicates_prevented: int
    total_errors: int
    total_carriers: int = 0
    total_shippers: int = 0
    total_carrier_final: int = 0
    total_shipper_final: int = 0
    active_run: Optional[RunResponse] = None
    recent_final_leads: List[CompanyResponse] = Field(default_factory=list)
    recent_errors: List[ErrorLogResponse] = Field(default_factory=list)

