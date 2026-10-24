import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON, Index, text
)
from sqlalchemy.orm import relationship
from ..core.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Run(Base):
    __tablename__ = "runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, default="Lead Gen Run")
    status = Column(String(50), nullable=False, default="PENDING")  # PENDING, RUNNING, COMPLETED, FAILED, PAUSED
    target_states = Column(JSON, default=list)
    fleet_size_min = Column(Integer, default=2)
    fleet_size_max = Column(Integer, default=10)
    equipment_types = Column(JSON, default=list)
    target_lead_count = Column(Integer, default=25)
    score_threshold = Column(Float, default=5.0)
    lead_type = Column(String(50), default="ALL")  # ALL, CARRIER, SHIPPER

    raw_count = Column(Integer, default=0)
    verified_count = Column(Integer, default=0)
    qualified_count = Column(Integer, default=0)
    final_count = Column(Integer, default=0)
    rejected_count = Column(Integer, default=0)
    duplicate_count = Column(Integer, default=0)
    priority_a_count = Column(Integer, default=0)
    priority_b_count = Column(Integer, default=0)
    source_counts = Column(JSON, default=dict)
    error_count = Column(Integer, default=0)

    google_sheet_url = Column(String(500), nullable=True)
    export_csv_path = Column(String(500), nullable=True)
    export_xlsx_path = Column(String(500), nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    companies = relationship("Company", back_populates="run", cascade="all, delete-orphan", lazy="selectin")
    errors = relationship("ErrorLog", back_populates="run", cascade="all, delete-orphan", lazy="selectin")


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        Index(
            "uq_companies_carrier_usdot",
            "usdot",
            unique=True,
            sqlite_where=text("usdot IS NOT NULL AND TRIM(usdot) != '' AND UPPER(lead_type) = 'CARRIER'")
        ),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True)

    # Identifiers & Names
    usdot = Column(String(50), nullable=True, index=True)
    mc_number = Column(String(50), nullable=True, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    legal_name = Column(String(255), nullable=True)
    dba_name = Column(String(255), nullable=True)
    normalized_name = Column(String(255), nullable=True, index=True)

    # Online & Contact
    website = Column(String(500), nullable=True)
    normalized_domain = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    normalized_phone = Column(String(50), nullable=True, index=True)
    phone_e164 = Column(String(50), nullable=True, index=True)
    phone_display = Column(String(50), nullable=True)
    phone_line_type = Column(String(50), nullable=True)  # mobile, landline, voip, tollfree, unknown
    phone_carrier_name = Column(String(100), nullable=True)
    phone_country_code = Column(String(10), default="US")
    phone_verification_status = Column(String(50), default="UNKNOWN", index=True)  # VERIFIED, INVALID, UNREACHABLE, UNKNOWN
    phone_verified_at = Column(DateTime, nullable=True)
    phone_verification_provider = Column(String(50), nullable=True)
    phone_raw_status = Column(String(100), nullable=True)
    phone_cost = Column(Float, default=0.0)
    call_guidance = Column(String(100), nullable=True)  # "call manually only, check DNC"
    dnc_status = Column(String(100), default="DNC not checked")

    # Time Zone & Call Windows (Local & Operator Asia/Kolkata)
    local_timezone = Column(String(50), nullable=True)
    call_window_local = Column(String(100), nullable=True)
    call_window_ist = Column(String(100), nullable=True)

    # Email & Verification Details
    email = Column(String(255), nullable=True)
    email_verification_status = Column(String(50), default="UNKNOWN", index=True)  # DELIVERABLE, RISKY, UNDELIVERABLE, UNKNOWN
    email_mx_valid = Column(Boolean, nullable=True)
    email_is_disposable = Column(Boolean, default=False)
    email_role_tier = Column(String(50), nullable=True)  # named, departmental, generic
    email_verified_at = Column(DateTime, nullable=True)
    email_verification_provider = Column(String(50), nullable=True)

    # Location
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True, index=True)
    zip_code = Column(String(20), nullable=True)

    # Fleet & Operations
    lead_type = Column(String(50), default="CARRIER", index=True)  # CARRIER (Have Trucks) or SHIPPER (Need Trucks)
    industry_sector = Column(String(100), nullable=True)
    freight_volume = Column(String(100), nullable=True)
    fleet_size = Column(Integer, nullable=True)
    driver_count = Column(Integer, nullable=True)
    equipment = Column(JSON, default=list)
    carrier_operation = Column(String(100), nullable=True)
    operating_status = Column(String(100), nullable=True)  # AUTHORIZED, ACTIVE, NOT AUTHORIZED, INACTIVE (Form MCS-150 census self-declaration)
    authority_status = Column(String(50), default="UNKNOWN", index=True)  # ACTIVE, INACTIVE, REVOKED, UNKNOWN (L&I Operating Authority)
    authority_status_source = Column(String(50), nullable=True, index=True)  # li_dataset, census_docket, manual_operator
    insurance_filing_status = Column(String(50), default="UNKNOWN", index=True)  # ACTIVE, CANCEL_PENDING, EXPIRED, UNKNOWN (L&I Insurance Filing)
    safety_rating = Column(String(100), nullable=True)
    mcs_150_date = Column(String(50), nullable=True)

    # Lead Lifecycle Status
    lead_status = Column(String(50), nullable=False, default="RAW", index=True)
    # Statuses: RAW, RESEARCHING, VERIFIED, ENRICHED, QUALIFIED, FINAL, REJECTED, NEEDS_REVIEW
    qualification_reason = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    lead_score = Column(Float, default=0.0)
    fit_score = Column(Float, default=0.0)
    intent_score = Column(Float, default=0.0)
    priority = Column(String(10), nullable=True)  # A, B, C
    scoring_version = Column(String(20), default="2.0")

    # Verification Metadata
    verification_status = Column(String(50), default="UNVERIFIED")  # VERIFIED, UNVERIFIED, FAILED, NEEDS_REVIEW
    verification_confidence = Column(Float, default=0.0)
    verification_date = Column(DateTime, nullable=True)

    # Primary Provenance & Integrity
    lead_source = Column(String(100), nullable=True)
    source_url = Column(String(1000), nullable=True)
    notes = Column(Text, nullable=True)
    field_provenance = Column(JSON, default=dict)
    needs_reverification = Column(Boolean, default=False, index=True)
    dnc_flag = Column(Boolean, default=False, index=True)
    suppression_reason = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    run = relationship("Run", back_populates="companies")
    contacts = relationship("Contact", back_populates="company", cascade="all, delete-orphan", lazy="selectin")
    sources = relationship("SourceRecord", back_populates="company", cascade="all, delete-orphan", lazy="selectin")
    verification_records = relationship("VerificationRecord", back_populates="company", cascade="all, delete-orphan", lazy="selectin")
    intent_signals = relationship("IntentSignal", back_populates="company", cascade="all, delete-orphan", lazy="selectin")
    lead_score_detail = relationship("LeadScore", back_populates="company", uselist=False, cascade="all, delete-orphan", lazy="selectin")
    status_history = relationship("LeadStatusHistory", back_populates="company", cascade="all, delete-orphan", lazy="selectin")
    outcomes = relationship("LeadOutcome", back_populates="company", cascade="all, delete-orphan", lazy="selectin")

    @property
    def dial_link(self) -> Optional[str]:
        return f"tel:{self.phone_e164}" if self.phone_e164 else (f"tel:{self.normalized_phone}" if self.normalized_phone else None)

    @property
    def mailto_link(self) -> Optional[str]:
        return f"mailto:{self.email}" if self.email else None


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    full_name = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    title = Column(String(150), nullable=True)

    # Phone & Line Intelligence
    phone = Column(String(50), nullable=True)
    phone_e164 = Column(String(50), nullable=True, index=True)
    phone_display = Column(String(50), nullable=True)
    phone_line_type = Column(String(50), nullable=True)  # mobile, landline, voip, tollfree, unknown
    phone_carrier_name = Column(String(100), nullable=True)
    phone_verification_status = Column(String(50), default="UNKNOWN", index=True)  # VERIFIED, INVALID, UNREACHABLE, UNKNOWN
    phone_verified_at = Column(DateTime, nullable=True)
    phone_verification_provider = Column(String(50), nullable=True)
    phone_raw_status = Column(String(100), nullable=True)
    phone_cost = Column(Float, default=0.0)
    dnc_status = Column(String(100), default="DNC not checked")

    # Email & Verification Details
    email = Column(String(255), nullable=True)
    email_verification_status = Column(String(50), default="UNKNOWN", index=True)  # DELIVERABLE, RISKY, UNDELIVERABLE, UNKNOWN
    email_mx_valid = Column(Boolean, nullable=True)
    email_is_disposable = Column(Boolean, default=False)
    email_role_tier = Column(String(50), nullable=True)  # named, departmental, generic
    email_verified_at = Column(DateTime, nullable=True)
    email_verification_provider = Column(String(50), nullable=True)

    linkedin_url = Column(String(500), nullable=True)
    is_decision_maker = Column(Boolean, default=False)
    confidence = Column(Float, default=0.5)
    source_url = Column(String(1000), nullable=True)
    verification_status = Column(String(50), default="UNVERIFIED")
    field_provenance = Column(JSON, default=dict)
    dnc_flag = Column(Boolean, default=False, index=True)

    created_at = Column(DateTime, default=utc_now)

    company = relationship("Company", back_populates="contacts")
    outcomes = relationship("LeadOutcome", back_populates="contact", cascade="all, delete-orphan", lazy="selectin")

    @property
    def dial_link(self) -> Optional[str]:
        return f"tel:{self.phone_e164}" if self.phone_e164 else (f"tel:{self.phone}" if self.phone else None)

    @property
    def mailto_link(self) -> Optional[str]:
        return f"mailto:{self.email}" if self.email else None



class SourceRecord(Base):
    __tablename__ = "sources"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    source_name = Column(String(100), nullable=False)
    source_url = Column(String(1000), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    extraction_confidence = Column(Float, default=1.0)
    discovered_at = Column(DateTime, default=utc_now)

    company = relationship("Company", back_populates="sources")


class VerificationRecord(Base):
    __tablename__ = "verification_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    step_name = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)  # PASSED, FAILED, WARNING, SKIPPED
    confidence = Column(Float, default=1.0)
    evidence_text = Column(Text, nullable=True)
    source_url = Column(String(1000), nullable=True)
    checked_at = Column(DateTime, default=utc_now)

    company = relationship("Company", back_populates="verification_records")


class IntentSignal(Base):
    __tablename__ = "intent_signals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    signal_type = Column(String(100), nullable=False)  # NEW_AUTHORITY, INSURANCE_CANCEL_PENDING, MCS150_RECENT_UPDATE, POWER_UNITS_GROWTH, HIRING_DISPATCH, etc.
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    source_url = Column(String(1000), nullable=True)
    confidence = Column(Float, default=0.7)
    strength = Column(Float, default=1.0)
    observed_at = Column(DateTime, default=utc_now)
    half_life_days = Column(Float, default=60.0)
    evidence = Column(JSON, default=dict)
    is_sensitive = Column(Boolean, default=False, index=True)
    detected_date = Column(DateTime, default=utc_now)

    company = relationship("Company", back_populates="intent_signals")


class LeadScore(Base):
    __tablename__ = "lead_scores"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    total_score = Column(Float, default=0.0)
    fit_score = Column(Float, default=0.0)
    intent_score = Column(Float, default=0.0)
    priority = Column(String(10), default="C")
    scoring_version = Column(String(20), default="2.0")

    target_fleet_size_score = Column(Float, default=0.0)
    verified_active_carrier_score = Column(Float, default=0.0)
    decision_maker_score = Column(Float, default=0.0)
    equipment_verified_score = Column(Float, default=0.0)
    usable_contact_score = Column(Float, default=0.0)
    intent_signal_score = Column(Float, default=0.0)
    tech_business_event_score = Column(Float, default=0.0)
    score_breakdown = Column(JSON, default=dict)

    scored_at = Column(DateTime, default=utc_now)

    company = relationship("Company", back_populates="lead_score_detail")



class LeadStatusHistory(Base):
    __tablename__ = "lead_status_history"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    from_status = Column(String(50), nullable=True)
    to_status = Column(String(50), nullable=False)
    reason = Column(Text, nullable=True)
    changed_at = Column(DateTime, default=utc_now)

    company = relationship("Company", back_populates="status_history")


class ErrorLog(Base):
    __tablename__ = "errors"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True)
    company_id = Column(String(36), nullable=True, index=True)

    source_name = Column(String(100), nullable=True)
    source_url = Column(String(1000), nullable=True)
    error_type = Column(String(100), nullable=False)  # CAPTCHA_BLOCKED, HTTP_ERROR, PARSE_ERROR, AUTH_WALL, TIMEOUT
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    status = Column(String(50), default="OPEN")  # OPEN, REVIEWED, RESOLVED

    created_at = Column(DateTime, default=utc_now)

    run = relationship("Run", back_populates="errors")


class FMCSACarrierCensus(Base):
    """Local cache and mirror of official FMCSA MCMIS Motor Carrier Census dataset."""
    __tablename__ = "fmcsa_carrier_census"

    dot_number = Column(String(50), primary_key=True, index=True)
    legal_name = Column(String(255), nullable=False, index=True)
    dba_name = Column(String(255), nullable=True)
    carrier_operation = Column(String(100), nullable=True)
    phy_street = Column(String(500), nullable=True)
    phy_city = Column(String(100), nullable=True)
    phy_state = Column(String(50), nullable=False, index=True)
    phy_zip = Column(String(20), nullable=True)
    phone = Column(String(50), nullable=True)
    cell_phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    company_officer_1 = Column(String(255), nullable=True)
    company_officer_2 = Column(String(255), nullable=True)
    power_units = Column(Integer, nullable=True)
    total_drivers = Column(Integer, nullable=True)
    operating_status = Column(String(100), nullable=True)
    safety_rating = Column(String(100), nullable=True)
    docket_number = Column(String(50), nullable=True, index=True)  # MC / MX number
    add_date = Column(String(50), nullable=True)
    mcs150_date = Column(String(50), nullable=True)
    raw_checksum = Column(String(64), nullable=True)  # SHA256 of raw data for incremental sync
    synced_at = Column(DateTime, default=utc_now)
    source_url = Column(String(500), nullable=True)


class SourceHealthMetric(Base):
    """Tracks circuit-breaker status, latency, and success/failure rates per data source."""
    __tablename__ = "source_health_metrics"

    source_name = Column(String(100), primary_key=True)
    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    consecutive_failures = Column(Integer, default=0)
    circuit_breaker_tripped = Column(Boolean, default=False)
    circuit_breaker_tripped_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    last_failure_at = Column(DateTime, nullable=True)
    last_error_message = Column(Text, nullable=True)
    avg_latency_ms = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class SuppressionEntry(Base):
    """Compliance suppression list preventing outreach to opted-out, DNC, or litigator entities."""
    __tablename__ = "suppression_list"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True, index=True)
    normalized_phone = Column(String(50), nullable=True, index=True)
    domain = Column(String(255), nullable=True, index=True)
    usdot = Column(String(50), nullable=True, index=True)
    reason = Column(String(255), default="OPT_OUT")  # OPT_OUT, DNC, LITIGATOR, BOUNCE
    added_at = Column(DateTime, default=utc_now)


class FMCSAInsurance(Base):
    """Local cache of active and pending FMCSA insurance filings (SODA qh9u-swkp / ypjt-5ydn)."""
    __tablename__ = "fmcsa_insurance_active_pending"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dot_number = Column(String(50), nullable=True, index=True)
    docket_number = Column(String(50), nullable=True, index=True)
    ins_form_code = Column(String(50), nullable=True)
    name_company = Column(String(255), nullable=True)
    policy_no = Column(String(100), nullable=True)
    underl_lim_amount = Column(String(50), nullable=True)
    max_cov_amount = Column(String(50), nullable=True)
    effective_date = Column(String(50), nullable=True)
    cancl_effective_date = Column(String(50), nullable=True)
    raw_checksum = Column(String(64), nullable=True)
    synced_at = Column(DateTime, default=utc_now)


class FMCSAAuthorityHistory(Base):
    """Local cache of FMCSA operating authority dispositions, revocations & suspensions (SODA wb4f-neki / 9mw4-x3tu)."""
    __tablename__ = "fmcsa_authority_history"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dot_number = Column(String(50), nullable=True, index=True)
    docket_number = Column(String(50), nullable=True, index=True)
    op_auth_type = Column(String(100), nullable=True)
    order_type_desc = Column(String(255), nullable=True)
    serve_date = Column(String(50), nullable=True)
    effective_date = Column(String(50), nullable=True)
    raw_checksum = Column(String(64), nullable=True)
    synced_at = Column(DateTime, default=utc_now)


class FMCSANewApplication(Base):
    """Local cache of rejected or pending operating authority applications (SODA 96tg-4mhf)."""
    __tablename__ = "fmcsa_new_applications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dot_number = Column(String(50), nullable=True, index=True)
    docket_number = Column(String(50), nullable=True, index=True)
    ins_form_code = Column(String(50), nullable=True)
    policy_no = Column(String(100), nullable=True)
    recv_date = Column(String(50), nullable=True)
    rej_date = Column(String(50), nullable=True)
    name_company = Column(String(255), nullable=True)
    rej_reasons = Column(Text, nullable=True)
    raw_checksum = Column(String(64), nullable=True)
    synced_at = Column(DateTime, default=utc_now)


class PhoneVerificationCache(Base):
    """30-day cache of phone verification lookups to prevent redundant API queries and cost."""
    __tablename__ = "phone_verification_cache"

    phone_e164 = Column(String(50), primary_key=True, index=True)
    valid = Column(Boolean, default=False)
    line_type = Column(String(50), nullable=True)  # mobile, landline, voip, tollfree, unknown
    carrier_name = Column(String(100), nullable=True)
    country_code = Column(String(10), default="US")
    phone_verification_status = Column(String(50), default="UNKNOWN", index=True)  # VERIFIED, INVALID, UNREACHABLE, UNKNOWN
    provider = Column(String(50), nullable=True)
    raw_status = Column(String(100), nullable=True)
    cost = Column(Float, default=0.0)
    cached_at = Column(DateTime, default=utc_now)
    expires_at = Column(DateTime, nullable=False, index=True)


class LeadOutcome(Base):
    """Records one-click call and email outreach outcomes."""
    __tablename__ = "lead_outcomes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id = Column(String(36), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    channel = Column(String(20), nullable=False)  # "PHONE" or "EMAIL"
    outcome = Column(String(50), nullable=False)  # "no_answer", "wrong_number", "voicemail", "interested", "not_interested", "do_not_contact", "bounced"
    target_value = Column(String(255), nullable=True)  # phone number or email address reached
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    company = relationship("Company", back_populates="outcomes")
    contact = relationship("Contact", back_populates="outcomes")


class AutopilotRunLog(Base):
    """Audit log of autonomous corridor runs, tracking spend, lead yield, caps, and kill status."""
    __tablename__ = "autopilot_run_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    cycle_number = Column(Integer, nullable=False)
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True)
    corridor_name = Column(String(100), nullable=False)
    states = Column(JSON, default=list)
    lead_type = Column(String(50), default="CARRIER")
    leads_cap = Column(Integer, default=50)
    spend_cap = Column(Float, default=2.00)
    leads_found = Column(Integer, default=0)
    provider_spend = Column(Float, default=0.0)
    status = Column(String(50), default="RUNNING")  # RUNNING, COMPLETED, KILLED, FAILED, CAPPED
    kill_reason = Column(String(255), nullable=True)
    started_at = Column(DateTime, default=utc_now)
    completed_at = Column(DateTime, nullable=True)


