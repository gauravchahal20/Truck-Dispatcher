import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON, Index
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
    email = Column(String(255), nullable=True)

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
    operating_status = Column(String(100), nullable=True)  # AUTHORIZED, ACTIVE, NOT AUTHORIZED, INACTIVE
    safety_rating = Column(String(100), nullable=True)
    mcs_150_date = Column(String(50), nullable=True)

    # Lead Lifecycle Status
    lead_status = Column(String(50), nullable=False, default="RAW", index=True)
    # Statuses: RAW, RESEARCHING, VERIFIED, ENRICHED, QUALIFIED, FINAL, REJECTED, NEEDS_REVIEW
    qualification_reason = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    lead_score = Column(Float, default=0.0)
    priority = Column(String(10), nullable=True)  # A, B, C

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


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    full_name = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    title = Column(String(150), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    is_decision_maker = Column(Boolean, default=False)
    confidence = Column(Float, default=0.5)
    source_url = Column(String(1000), nullable=True)

    created_at = Column(DateTime, default=utc_now)

    company = relationship("Company", back_populates="contacts")


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

    signal_type = Column(String(100), nullable=False)  # HIRING_DISPATCH, HIRING_FLEET_MGR, FLEET_EXPANSION, CONTRACT_AWARD, DISPATCH_HELP_REQUEST
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    source_url = Column(String(1000), nullable=True)
    confidence = Column(Float, default=0.7)
    detected_date = Column(DateTime, default=utc_now)

    company = relationship("Company", back_populates="intent_signals")


class LeadScore(Base):
    __tablename__ = "lead_scores"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    total_score = Column(Float, default=0.0)
    priority = Column(String(10), default="C")

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
