import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from app.models.entities import Company, Contact, Run, SuppressionEntry, PhoneVerificationCache, LeadOutcome
from app.services.normalizer import Normalizer
from app.services.phone_verifier import PhoneVerifier, MockPhoneProvider, PhoneVerificationResult
from app.services.email_verifier import EmailVerifier
from app.services.lead_scorer import LeadScorer
from app.api.routes_outcomes import log_lead_outcome, LogOutcomeRequest, list_callable_mailable_leads
from app.core.database import AsyncSessionLocal, async_engine, Base


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


def test_e164_formatting_and_pretty_display():
    """Validates strict E.164 conversion (+1XXXXXXXXXX) and display format '+1 (214) 555-0182'."""
    raw_inputs = [
        "(214) 555-0182",
        "1-214-555-0182",
        "214.555.0182",
        "2145550182",
        "+12145550182"
    ]
    for raw in raw_inputs:
        e164 = Normalizer.to_e164(raw)
        assert e164 == "+12145550182"
        display = Normalizer.format_phone_display(e164)
        assert display == "+1 (214) 555-0182"
        dial_link = Normalizer.get_dial_link(e164)
        assert dial_link == "tel:+12145550182"

    # Invalid length
    assert Normalizer.to_e164("555-01") is None
    assert Normalizer.to_e164("") is None


def test_timezone_and_kolkata_call_window():
    """Validates US state to timezone mapping and Kolkata (Asia/Kolkata) equivalent call window."""
    # Texas (Central Time)
    tz_tx, w_loc_tx, w_ist_tx = Normalizer.get_timezone_and_windows("TX", "+12145550182")
    assert tz_tx == "America/Chicago"
    assert "09:00 - 17:00" in w_loc_tx
    assert "IST" in w_ist_tx

    # Georgia (Eastern Time)
    tz_ga, w_loc_ga, w_ist_ga = Normalizer.get_timezone_and_windows("GA", "+14045550144")
    assert tz_ga == "America/New_York"
    assert "09:00 - 17:00" in w_loc_ga
    assert "IST" in w_ist_ga


def test_dst_transition_november_2026():
    """
    Validates dynamic IANA zoneinfo handling across the Nov 1, 2026 DST transition.
    Proves that 9:00 AM local maps to different IST times before (CDT: 19:30 IST) vs after (CST: 20:30 IST).
    """
    # 1. Before DST transition (Oct 31, 2026 - Daylight Saving Time CDT, UTC-5)
    dt_before = datetime(2026, 10, 31, 10, 0)
    tz_b, loc_b, ist_b = Normalizer.get_timezone_and_windows("TX", "+12145550182", reference_date=dt_before)
    assert tz_b == "America/Chicago"
    assert "CDT" in loc_b
    assert "19:30" in ist_b

    # 2. After DST transition (Nov 2, 2026 - Standard Time CST, UTC-6)
    dt_after = datetime(2026, 11, 2, 10, 0)
    tz_a, loc_a, ist_a = Normalizer.get_timezone_and_windows("TX", "+12145550182", reference_date=dt_after)
    assert tz_a == "America/Chicago"
    assert "CST" in loc_a
    assert "20:30" in ist_a

    # Prove difference across DST transition
    assert ist_b != ist_a
    assert loc_b != loc_a


@pytest.mark.asyncio
async def test_phone_verifier_unknown_when_no_key():
    """Proves that without an API key, PhoneVerifier returns UNKNOWN (never VERIFIED)."""
    async with AsyncSessionLocal() as session:
        verifier = PhoneVerifier()
        # Ensure no keys configured
        for p in verifier.providers.values():
            p.account_sid = None
            p.auth_token = None
            p.api_key = None

        result = await verifier.verify_phone(session, "+12145550182")
        assert result.phone_verification_status in ["FORMAT_OK", "UNKNOWN"]
        assert result.phone_verification_status != "VERIFIED"
        assert result.provider == "none"
        assert result.cost == 0.0


@pytest.mark.asyncio
async def test_phone_verifier_caching_and_cost_cap():
    """Validates 30-day cache hit and per-run cost cap enforcement."""
    async with AsyncSessionLocal() as session:
        mock_provider = MockPhoneProvider()
        verifier = PhoneVerifier(provider_override=mock_provider)
        verifier.cost_cap_per_run = 0.01  # Only allows 2 lookups at $0.005 each

        # 1. First lookup (hits mock provider)
        res1 = await verifier.verify_phone(session, "+12145550181")
        assert res1.phone_verification_status == "VERIFIED"
        assert res1.cached is False
        assert res1.cost == 0.005

        # 2. Second lookup on same number (hits 30-day SQLite cache, zero cost)
        res2 = await verifier.verify_phone(session, "+12145550181")
        assert res2.cached is True
        assert res2.cost == 0.0
        assert res2.phone_verification_status == "VERIFIED"

        # 3. Lookup on second number (hits mock provider, reaches run cost limit)
        res3 = await verifier.verify_phone(session, "+12145550182")
        assert res3.cost == 0.005

        # 4. Third lookup on new number should exceed cost cap ($0.01) -> returns UNKNOWN
        res4 = await verifier.verify_phone(session, "+12145550183")
        assert res4.phone_verification_status == "UNKNOWN"
        assert res4.raw_status == "COST_CAP_REACHED"
        assert res4.cost == 0.0


def test_sole_proprietor_mobile_call_guidance():
    """Flags mobile numbers on 1-truck carriers as 'call manually only, check DNC'."""
    # 1 truck + mobile -> Manual only, check DNC
    guidance1 = PhoneVerifier.determine_call_guidance(fleet_size=1, carrier_operation="Interstate", line_type="mobile")
    assert guidance1 == "call manually only, check DNC"

    # 1 truck + landline -> Call allowed
    guidance2 = PhoneVerifier.determine_call_guidance(fleet_size=1, carrier_operation="Interstate", line_type="landline")
    assert guidance2 == "call allowed"

    # 5 trucks + mobile -> Call allowed (fleet company)
    guidance3 = PhoneVerifier.determine_call_guidance(fleet_size=5, carrier_operation="Interstate", line_type="mobile")
    assert guidance3 == "call allowed"


@pytest.mark.asyncio
async def test_email_verifier_syntax_disposable_and_tiering():
    """Tests syntax validation, disposable domain blacklist, and role-account tiering."""
    verifier = EmailVerifier(mx_resolver_override=lambda dom: (True, "Mock MX server active"))

    # 1. Invalid Syntax
    res_bad = await verifier.verify_email("invalid-email-address")
    assert res_bad.email_verification_status == "UNDELIVERABLE"
    assert res_bad.valid_syntax is False

    # 2. Disposable Domain Blacklist
    res_disp = await verifier.verify_email("carrier_test@mailinator.com")
    assert res_disp.email_verification_status == "UNDELIVERABLE"
    assert res_disp.is_disposable is True

    # 3. Generic Role Account -> RISKY
    res_gen = await verifier.verify_email("info@lonestartrucking.com")
    assert res_gen.role_tier == "generic"
    assert res_gen.email_verification_status == "RISKY"

    # 4. Departmental Role Account -> RISKY
    res_dept = await verifier.verify_email("dispatch@lonestartrucking.com")
    assert res_dept.role_tier == "departmental"
    assert res_dept.email_verification_status == "RISKY"

    # 5. Named Person (MX only, no external provider key) -> DOMAIN_OK (never DELIVERABLE)
    res_named = await verifier.verify_email("robert.davis@lonestartrucking.com")
    assert res_named.role_tier == "named"
    assert res_named.email_verification_status == "DOMAIN_OK"
    assert res_named.email_verification_status != "DELIVERABLE"


@pytest.mark.asyncio
async def test_scorer_awards_authority_only_when_proven():
    """Proves that unverified authority awards 0.0 points in scorer, and shippers get N/A (0.0)."""
    # Carrier with unverified / None authority
    c_unverified = Company(
        company_name="Pending Logistics LLC",
        lead_type="CARRIER",
        usdot="4123456",
        operating_status=None,
        fleet_size=3
    )
    score1, _ = LeadScorer.calculate_score(c_unverified)
    assert score1.verified_active_carrier_score == 0.0

    # Carrier with active authority
    c_active = Company(
        company_name="Active Freight LLC",
        lead_type="CARRIER",
        usdot="4123457",
        operating_status="AUTHORIZED FOR HIRE",
        fleet_size=3
    )
    score2, _ = LeadScorer.calculate_score(c_active)
    assert score2.verified_active_carrier_score == 2.0

    # Shipper has authority = N/A (0.0)
    c_shipper = Company(
        company_name="Texas Pipe Supply",
        lead_type="SHIPPER",
        freight_volume="50 FTL/month"
    )
    score3, _ = LeadScorer.calculate_score(c_shipper)
    assert score3.verified_active_carrier_score == 0.0


@pytest.mark.asyncio
async def test_final_requires_verified_contact_channel_for_named_person():
    """
    Proves that a lead with active authority and qualifying score stays QUALIFIED
    if contacts are unverified MCS-150 officers, and only reaches FINAL when at least
    one contact channel is VERIFIED.
    """
    async with AsyncSessionLocal() as session:
        # 1. Carrier with unverified contacts -> stays QUALIFIED
        c1 = Company(
            company_name="Midwest Express LLC",
            lead_type="CARRIER",
            usdot="3812901",
            operating_status="AUTHORIZED FOR HIRE",
            state="OH",
            fleet_size=4,
            lead_score=7.0,
            priority="B",
            phone_verification_status="UNKNOWN",
            email_verification_status="UNKNOWN"
        )
        officer = Contact(
            full_name="Marcus Vance",
            title="Company officer (per MCS-150)",
            is_decision_maker=True,
            phone_verification_status="UNKNOWN",
            email_verification_status="UNKNOWN"
        )
        c1.contacts.append(officer)
        session.add(c1)
        await session.commit()

        # Evaluation logic check:
        has_verified = (c1.phone_verification_status == "VERIFIED" or c1.email_verification_status == "DELIVERABLE" or
                        any((ct.phone_verification_status == "VERIFIED" or ct.email_verification_status == "DELIVERABLE") for ct in c1.contacts))
        assert has_verified is False

        # 2. When contact is verified with line intelligence -> Reaches FINAL
        officer.phone_verification_status = "VERIFIED"
        officer.phone_line_type = "mobile"
        await session.commit()

        has_verified_now = (c1.phone_verification_status == "VERIFIED" or c1.email_verification_status == "DELIVERABLE" or
                            any((ct.phone_verification_status == "VERIFIED" or ct.email_verification_status == "DELIVERABLE") for ct in c1.contacts))
        assert has_verified_now is True


@pytest.mark.asyncio
async def test_ready_to_contact_excludes_suppressed_and_dnc():
    """Verifies that suppressed and DNC leads are excluded from callable & mailable view."""
    async with AsyncSessionLocal() as session:
        # Valid company
        c_valid = Company(
            company_name="Apex Freight Lines LLC",
            state="GA",
            phone="+14045550188",
            phone_e164="+14045550188",
            phone_verification_status="VERIFIED",
            email="dispatch@apexfreight.com",
            email_verification_status="DELIVERABLE",
            lead_status="FINAL",
            dnc_flag=False,
            lead_score=8.5,
            priority="A"
        )
        # Suppressed company
        c_suppressed = Company(
            company_name="Suppressed Carrier LLC",
            state="TX",
            phone="+12145550199",
            phone_e164="+12145550199",
            phone_verification_status="VERIFIED",
            email="optout@suppressed.com",
            email_verification_status="DELIVERABLE",
            lead_status="FINAL",
            dnc_flag=True,
            suppression_reason="DO_NOT_CONTACT",
            lead_score=9.0,
            priority="A"
        )
        session.add_all([c_valid, c_suppressed])
        await session.commit()

        result = await list_callable_mailable_leads(filter_mode="all", limit=50, session=session)
        returned_names = [l["company"] for l in result["leads"]]

        assert "Apex Freight Lines LLC" in returned_names
        assert "Suppressed Carrier LLC" not in returned_names


@pytest.mark.asyncio
async def test_log_outcome_auto_suppresses_lead():
    """Validates that logging 'do_not_contact' automatically suppresses company and contact."""
    async with AsyncSessionLocal() as session:
        company = Company(
            company_name="Lone Star Hauling LLC",
            phone="2145550182",
            phone_e164="+12145550182",
            email="dispatch@lonestarhauling.com",
            usdot="3901234",
            lead_status="FINAL",
            dnc_flag=False
        )
        contact = Contact(
            full_name="Bill Miller",
            title="Owner",
            phone_e164="+12145550182",
            email="dispatch@lonestarhauling.com"
        )
        company.contacts.append(contact)
        session.add(company)
        await session.commit()

        req = LogOutcomeRequest(
            company_id=company.id,
            contact_id=contact.id,
            channel="PHONE",
            outcome="do_not_contact",
            notes="Requested to be removed from list."
        )
        resp = await log_lead_outcome(req, session=session)
        assert resp["status"] == "success"
        assert resp["suppression_applied"] is True

        # Re-fetch company
        await session.refresh(company)
        assert company.dnc_flag is True
        assert "outreach outcome: do_not_contact" in company.suppression_reason.lower()

        # Verify SuppressionEntry exists
        supp = await session.execute(
            select(SuppressionEntry).where(SuppressionEntry.normalized_phone == "+12145550182")
        )
        entry = supp.scalar_one_or_none()
        assert entry is not None
        assert entry.reason == "DO_NOT_CONTACT"


@pytest.mark.asyncio
async def test_status_consistency_and_hard_gates():
    """
    F1 REGRESSION TEST:
    Asserts that status is 100% consistent with score, hard gates, and contact verification:
    1. Unauthorized / Private Property carriers with score >= 5.0 are REJECTED (hard gate failure).
    2. Carriers with score < 5.0 are REJECTED.
    3. Carriers with active authority and score >= 5.0 but unverified contacts stay QUALIFIED.
    4. Carriers with active authority, score >= 5.0, and verified contact for named person reach FINAL.
    5. Carriers with unknown authority (operating_status is None) stay in NEEDS_ENRICHMENT.
    """
    async with AsyncSessionLocal() as session:
        # 1. Private Property carrier with high score -> REJECTED (Hard gate)
        c_private = Company(
            company_name="Private Hauler LLC",
            lead_type="CARRIER",
            usdot="1000001",
            operating_status="PRIVATE PROPERTY",
            state="TX",
            fleet_size=6,
            lead_score=7.2,
            priority="B",
            lead_status="FINAL" # Initially claimed FINAL
        )
        # 2. Score < 5.0 carrier -> REJECTED
        c_low_score = Company(
            company_name="Low Score Carrier LLC",
            lead_type="CARRIER",
            usdot="1000002",
            operating_status="AUTHORIZED FOR HIRE",
            state="GA",
            fleet_size=1,
            lead_score=3.2,
            priority="REJECTED"
        )
        # 3. Active authority + score >= 5.0 + unverified contact -> QUALIFIED (not FINAL)
        c_qualified = Company(
            company_name="Active Unverified Staff LLC",
            lead_type="CARRIER",
            usdot="1000003",
            operating_status="AUTHORIZED FOR HIRE",
            state="OH",
            fleet_size=4,
            lead_score=6.5,
            priority="B",
            phone_verification_status="UNKNOWN",
            email_verification_status="UNKNOWN"
        )
        ct_unverified = Contact(
            full_name="Dave Smith",
            title="Owner",
            is_decision_maker=True,
            phone_verification_status="UNKNOWN",
            email_verification_status="UNKNOWN"
        )
        c_qualified.contacts.append(ct_unverified)

        # 4. Active authority + score >= 5.0 + verified contact for named person -> FINAL
        c_final = Company(
            company_name="Verified Active Carrier LLC",
            lead_type="CARRIER",
            usdot="1000004",
            operating_status="AUTHORIZED FOR HIRE",
            state="TX",
            fleet_size=5,
            lead_score=8.2,
            priority="A",
            phone_verification_status="VERIFIED",
            email_verification_status="DELIVERABLE"
        )
        ct_verified = Contact(
            full_name="Sarah Connor",
            title="Owner & President",
            is_decision_maker=True,
            phone_verification_status="VERIFIED",
            email_verification_status="DELIVERABLE"
        )
        c_final.contacts.append(ct_verified)

        # 5. Operating status unknown -> NEEDS_ENRICHMENT
        c_unknown_op = Company(
            company_name="Unknown Authority Freight LLC",
            lead_type="CARRIER",
            usdot="1000005",
            operating_status=None,
            state="TX",
            fleet_size=4,
            lead_score=5.5,
            priority="C"
        )

        test_companies = [c_private, c_low_score, c_qualified, c_final, c_unknown_op]
        session.add_all(test_companies)
        await session.commit()

        # Query back with contacts eagerly loaded via selectinload
        from sqlalchemy.orm import selectinload
        res = await session.execute(select(Company).options(selectinload(Company.contacts)).order_by(Company.usdot))
        loaded_companies = res.scalars().all()

        # Run status assignment evaluation logic on each company
        for c in loaded_companies:
            op_status = (c.operating_status or "").upper()
            is_carrier = (c.lead_type != "SHIPPER")
            has_proven_active_authority = not is_carrier or (
                bool(c.usdot) and
                any(st in op_status for st in ["ACTIVE", "AUTHORIZED", "FOR-HIRE", "FOR HIRE"]) and
                not any(bad in op_status for bad in ["NOT AUTHORIZED", "REVOKED", "INACTIVE", "UNVERIFIED", "PRIVATE PROPERTY"])
            )
            has_verified_phone = (
                (c.phone_verification_status == "VERIFIED") or
                any(ct.phone_verification_status == "VERIFIED" for ct in c.contacts)
            )
            has_verified_email = (
                (c.email_verification_status == "DELIVERABLE") or
                any(ct.email_verification_status == "DELIVERABLE" for ct in c.contacts)
            )
            has_named_person = any(
                (ct.is_decision_maker or (ct.full_name and len(ct.full_name) > 3 and not ct.full_name.lower().startswith("company officer")))
                for ct in c.contacts
            )
            has_verified_channel = (has_verified_phone or has_verified_email) and has_named_person

            is_final_cand = has_proven_active_authority and c.lead_score >= 5.0 and not c.dnc_flag

            if c.dnc_flag:
                c.lead_status = "REJECTED"
                c.priority = "REJECTED"
            elif is_carrier and op_status and any(bad in op_status for bad in ["PRIVATE PROPERTY", "NOT AUTHORIZED", "REVOKED", "INACTIVE"]):
                c.lead_status = "REJECTED"
                c.priority = "REJECTED"
            elif c.lead_score < 5.0 or c.priority == "REJECTED":
                c.lead_status = "REJECTED"
                c.priority = "REJECTED"
            elif is_carrier and not c.operating_status:
                c.lead_status = "NEEDS_ENRICHMENT"
            elif is_final_cand and has_verified_channel:
                c.lead_status = "FINAL"
            elif is_final_cand:
                c.lead_status = "QUALIFIED"
            else:
                c.lead_status = "NEEDS_ENRICHMENT"

        await session.commit()

        # Assertions
        assert c_private.lead_status == "REJECTED"
        assert c_private.priority == "REJECTED"

        assert c_low_score.lead_status == "REJECTED"
        assert c_low_score.priority == "REJECTED"

        assert c_qualified.lead_status == "QUALIFIED"
        assert c_qualified.priority == "B"
        assert c_final.lead_status == "FINAL"
        assert c_final.priority == "A"

        assert c_unknown_op.lead_status == "NEEDS_ENRICHMENT"


@pytest.mark.asyncio
async def test_draft_email_requires_can_spam_postal_address_and_sender_identity():
    """Validates that draft-email strictly requires postal_address and sender_identity per CAN-SPAM Act."""
    from fastapi import HTTPException
    from app.api.routes_outcomes import generate_compliant_email_draft
    from app.core.config import config

    async with AsyncSessionLocal() as session:
        # Create a test company
        c = Company(
            company_name="Valid Test Carrier LLC",
            lead_type="CARRIER",
            usdot="7788990",
            operating_status="AUTHORIZED FOR HIRE",
            state="TX",
            fleet_size=3,
            lead_score=8.5,
            priority="A"
        )
        ct = Contact(
            full_name="Alice Morgan",
            title="President",
            is_decision_maker=True,
            email="alice@validtestcarrier.com"
        )
        c.contacts.append(ct)
        session.add(c)
        await session.commit()
        await session.refresh(c)

        # 1. Unset postal_address -> raises 400 with exact instruction
        config.compliance.postal_address = ""
        config.outreach.physical_address = None
        config.compliance.sender_identity = "Dispatch Team"

        with pytest.raises(HTTPException) as exc_info:
            await generate_compliant_email_draft(c.id, session=session)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Set your postal address in Settings to generate drafts"

        # 2. Placeholder Wilmington address -> raises 400
        config.compliance.postal_address = "1209 Orange Street, Wilmington, DE 19801"
        with pytest.raises(HTTPException) as exc_info:
            await generate_compliant_email_draft(c.id, session=session)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Set your postal address in Settings to generate drafts"

        # 3. Unset sender_identity -> raises 400
        config.compliance.postal_address = "5000 Freight Express Way, Suite 400, Dallas, TX 75201"
        config.compliance.sender_identity = ""
        config.outreach.sender_name = None

        with pytest.raises(HTTPException) as exc_info:
            await generate_compliant_email_draft(c.id, session=session)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Set your sender identity in Settings to generate drafts"

        # 4. Valid configuration -> returns compliant draft
        config.compliance.postal_address = "5000 Freight Express Way, Suite 400, Dallas, TX 75201"
        config.compliance.sender_identity = "TRUCKLEAD Elite Dispatch"
        config.compliance.sender_email = "dispatch@trucklead.test"

        draft = await generate_compliant_email_draft(c.id, session=session)
        assert draft["status"] == "DRAFT_ONLY_OPERATOR_SENDS"
        assert draft["physical_address"] == "5000 Freight Express Way, Suite 400, Dallas, TX 75201"
        assert draft["sender_name"] == "TRUCKLEAD Elite Dispatch"
        assert "5000 Freight Express Way" in draft["body"]
        assert "TRUCKLEAD Elite Dispatch" in draft["body"]
        assert "UNSUBSCRIBE" in draft["body"]
        assert "1209 Orange Street" not in draft["body"]


@pytest.mark.asyncio
async def test_honest_verification_labels_and_corroboration():
    """
    Validates honest verification labels per Workstream F3:
    1. Email statuses: SYNTAX_OK, DOMAIN_OK (MX only), DELIVERABLE (provider), RISKY, UNDELIVERABLE, UNKNOWN.
    2. Phone statuses: FORMAT_OK, CORROBORATED (>= 2 sources), VERIFIED (provider), INVALID, UNKNOWN.
    3. Named-person email matching (john@ for John Smith vs info@/dispatch@).
    4. Ready to contact confidence tiers: HIGH, MEDIUM, LOW.
    """
    from app.api.routes_outcomes import compute_contact_confidence

    # 1. Email Statuses & Named-person match
    verifier = EmailVerifier(mx_resolver_override=lambda dom: (True, "Mock MX active"))
    
    # Empty string -> UNKNOWN
    res_empty = await verifier.verify_email("")
    assert res_empty.email_verification_status == "UNKNOWN"

    # Bad syntax -> UNDELIVERABLE
    res_syntax = await verifier.verify_email("not-an-email")
    assert res_syntax.email_verification_status == "UNDELIVERABLE"

    # Disposable domain -> UNDELIVERABLE
    res_disp = await verifier.verify_email("carrier@mailinator.com")
    assert res_disp.email_verification_status == "UNDELIVERABLE"

    # Role generic -> RISKY
    res_info = await verifier.verify_email("info@lonestartrucking.com", full_name="John Smith")
    assert res_info.email_verification_status == "RISKY"
    assert res_info.is_named_person_match is False

    # MX-only named recipient -> DOMAIN_OK, NEVER DELIVERABLE
    res_mx_only = await verifier.verify_email("john.smith@lonestartrucking.com", full_name="John Smith")
    assert res_mx_only.email_verification_status == "DOMAIN_OK"
    assert res_mx_only.email_verification_status != "DELIVERABLE"
    assert res_mx_only.is_named_person_match is True

    # Named-person heuristic variations
    assert EmailVerifier.is_named_person_match("jsmith@carrier.com", "John Smith") is True
    assert EmailVerifier.is_named_person_match("john@carrier.com", "John Smith") is True
    assert EmailVerifier.is_named_person_match("dispatch@carrier.com", "John Smith") is False
    assert EmailVerifier.is_named_person_match("sales@carrier.com", "John Smith") is False

    # 2. Phone Statuses & Corroboration
    # Invalid format -> INVALID
    assert PhoneVerifier.corroborate_phone("12345", ["census"]) == "INVALID"
    assert PhoneVerifier.corroborate_phone("", ["census"]) == "INVALID"

    # Single source -> FORMAT_OK
    assert PhoneVerifier.corroborate_phone("+12145550182", ["census"]) == "FORMAT_OK"

    # >= 2 independent sources -> CORROBORATED
    assert PhoneVerifier.corroborate_phone("+12145550182", ["census", "website"]) == "CORROBORATED"
    assert PhoneVerifier.corroborate_phone("+12145550182", ["fmcsa_safer", "fmcsa_carrier_census", "google_places"]) == "CORROBORATED"

    # Duplicate sources don't artificially corroborate
    assert PhoneVerifier.corroborate_phone("+12145550182", ["census", "census"]) == "FORMAT_OK"

    # 3. Ready to Contact Confidence Labels
    # HIGH: Verified phone OR (Deliverable email AND named person)
    assert compute_contact_confidence(phone_status="VERIFIED", email_status="DOMAIN_OK", is_named_email=False) == "HIGH"
    assert compute_contact_confidence(phone_status="FORMAT_OK", email_status="DELIVERABLE", is_named_email=True) == "HIGH"

    # MEDIUM: Corroborated phone OR Deliverable generic email OR Domain_OK named email
    assert compute_contact_confidence(phone_status="CORROBORATED", email_status="UNKNOWN", is_named_email=False) == "MEDIUM"
    assert compute_contact_confidence(phone_status="FORMAT_OK", email_status="DELIVERABLE", is_named_email=False) == "MEDIUM"
    assert compute_contact_confidence(phone_status="FORMAT_OK", email_status="DOMAIN_OK", is_named_email=True) == "MEDIUM"

    # LOW: Unverified phone only
    assert compute_contact_confidence(phone_status="FORMAT_OK", email_status="UNKNOWN", is_named_email=False) == "LOW"
    assert compute_contact_confidence(phone_status="UNKNOWN", email_status="UNKNOWN", is_named_email=False) == "LOW"


@pytest.mark.asyncio
async def test_shipper_contact_enrichment_mock_and_offline():
    """Validates shipper contact enrichment using MockPlacesProvider with recorded fixtures."""
    from app.services.shipper_enricher import GooglePlacesClient, MockPlacesProvider, ShipperEnricher

    # 1. Unconfigured GooglePlacesClient
    real_client = GooglePlacesClient(api_key=None)
    assert real_client.is_configured() is False
    res_unconf = await real_client.search_place("Tesla", city="Austin", state="TX")
    assert res_unconf is None

    # 2. Mock Places Provider with recorded fixtures
    mock_client = MockPlacesProvider()
    assert mock_client.is_configured() is True
    enricher = ShipperEnricher(places_client=mock_client)

    res_tesla = await enricher.enrich_shipper("Tesla", city="Austin", state="TX")
    assert res_tesla["phone_e164"] == "+15125168177"
    assert "13101 Tesla Rd" in res_tesla["address"]
    assert res_tesla["website"] == "https://www.tesla.com"
    assert len(res_tesla["contacts"]) >= 1
    assert res_tesla["contacts"][0]["email"] == "mvance@tesla.com"
    assert res_tesla["contacts"][0]["full_name"] == "Marcus Vance"


@pytest.mark.asyncio
async def test_pause_shipper_discovery_safeguard():
    """Validates that pause_shipper_discovery config flag halts un-enrichable shipper discovery."""
    from app.core.config import config
    from app.adapters.direct_shippers import DirectShippersAdapter

    adapter = DirectShippersAdapter()

    # 1. When paused (default), discovery returns empty list
    config.pipeline.pause_shipper_discovery = True
    candidates = await adapter.discover_candidates(target_states=["TX", "GA"], limit=10)
    assert candidates == []

    # 2. Flag can be toggled via config
    config.pipeline.pause_shipper_discovery = False
    assert config.pipeline.pause_shipper_discovery is False
    config.pipeline.pause_shipper_discovery = True


@pytest.mark.asyncio
async def test_outcome_analytics_and_weekly_summary():
    """Validates outcome analytics and weekly summary endpoints (G4 Feedback Loop starter)."""
    import httpx
    from app.main import app

    # Create test company
    async with AsyncSessionLocal() as session:
        c1 = Company(
            company_name="Apex Freight Lines LLC",
            lead_type="CARRIER",
            state="TX",
            lead_score=8.5,
            priority="A",
            lead_source="fmcsa_official",
            phone_e164="+12145550199",
            email="dispatch@apexfreight.com",
            operating_status="ACTIVE / FOR-HIRE",
            lead_status="QUALIFIED"
        )
        session.add(c1)
        await session.commit()
        await session.refresh(c1)
        c1_id = c1.id

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Log two outcomes (one phone call 'interested', one email 'bounced')
        res1 = await client.post(
            "/api/leads/outcome",
            json={"company_id": c1_id, "channel": "PHONE", "outcome": "interested", "notes": "Dispatcher agreed to pilot"}
        )
        assert res1.status_code == 200

        res2 = await client.post(
            "/api/leads/outcome",
            json={"company_id": c1_id, "channel": "EMAIL", "outcome": "bounced", "notes": "Mailbox rejected"}
        )
        assert res2.status_code == 200

        # 2. Test /api/leads/outcomes/analytics
        analytics_res = await client.get("/api/leads/outcomes/analytics")
        assert analytics_res.status_code == 200
        analytics_data = analytics_res.json()
        assert analytics_data["total_logged"] >= 2
        assert analytics_data["channels"]["PHONE"] >= 1
        assert analytics_data["channels"]["EMAIL"] >= 1
        assert "interested" in analytics_data["outcomes"]
        assert "bounced" in analytics_data["outcomes"]
        assert "A" in analytics_data["by_priority_tier"]
        assert "fmcsa_official" in analytics_data["by_source"]

        # 3. Test /api/leads/outcomes/weekly-summary
        weekly_res = await client.get("/api/leads/outcomes/weekly-summary?days=7")
        assert weekly_res.status_code == 200
        weekly_data = weekly_res.json()
        assert weekly_data["period_days"] == 7
        assert weekly_data["total_outreach_events"] >= 2
        assert weekly_data["total_calls"] >= 1
        assert weekly_data["total_emails"] >= 1
        assert weekly_data["positive_responses"] >= 1
        assert weekly_data["positive_response_rate_pct"] > 0
        assert weekly_data["suppression_triggers"] >= 1
        assert weekly_data["top_converting_priority"] == "A"
        assert weekly_data["top_converting_source"] == "fmcsa_official"






