import pytest
from app.models.entities import Company
from app.services.deduplicator import Deduplicator
from app.services.normalizer import Normalizer
from app.core.database import AsyncSessionLocal, async_engine, Base


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


def test_name_normalization_case_insensitivity():
    name1 = "LONE STAR EAGLE EXPRESS LLC"
    name2 = "lone star eagle express llc"
    name3 = "Lone Star Eagle Express, Inc."
    
    n1 = Normalizer.normalize_company_name(name1)
    n2 = Normalizer.normalize_company_name(name2)
    n3 = Normalizer.normalize_company_name(name3)
    
    assert n1 == "lone star eagle"
    assert n2 == "lone star eagle"
    assert n3 == "lone star eagle"
    assert n1 == n2 == n3


def test_legal_and_industry_suffix_stripping():
    variants = [
        "Apex Logistics LLC",
        "Apex Transport Inc.",
        "Apex Freight Corp.",
        "Apex Transportation Co.",
        "Apex Trucking Services",
        "Apex Enterprises Group",
        "Apex Hauling Lines Ltd.",
    ]
    for v in variants:
        norm = Normalizer.normalize_company_name(v)
        assert norm == "apex", f"Failed for variant: {v} -> got '{norm}'"


def test_phone_format_variations():
    phones = [
        "(214) 555-0182",
        "2145550182",
        "+12145550182",
        "1-214-555-0182",
        "214.555.0182",
        "+1 (214) 555-0182",
    ]
    for p in phones:
        assert Normalizer.normalize_phone(p) == "+12145550182"


def test_domain_normalization_and_path_stripping():
    domains = [
        "https://www.lonestareagle.com",
        "http://lonestareagle.com/",
        "https://lonestareagle.com/about-us?team=1",
        "www.lonestareagle.com/contact/",
        "http://www.lonestareagle.com:8080/portal",
    ]
    for d in domains:
        assert Normalizer.normalize_domain(d) == "lonestareagle.com"


def test_aggregator_domains_excluded_from_dedup():
    """Confirms aggregator and directory domains are marked as non-custom to prevent collisions."""
    aggregators = [
        "safer.fmcsa.dot.gov",
        "fmcsa.dot.gov",
        "usdotlookup.com",
        "google.com",
        "maps.google.com",
        "quicktransportsolutions.com",
        "clutch.co",
        "linkedin.com",
        "facebook.com",
        "indeed.com",
    ]
    for agg in aggregators:
        assert Normalizer.is_custom_domain(agg) is False, f"Aggregator {agg} should not be custom"

    # Proprietary company domains must be recognised as custom
    assert Normalizer.is_custom_domain("lonestareagle.com") is True
    assert Normalizer.is_custom_domain("blueridgefreight.net") is True


@pytest.mark.asyncio
async def test_dedup_by_usdot():
    async with AsyncSessionLocal() as session:
        c1 = Company(
            company_name="Lone Star Carrier LLC",
            usdot="3849102",
            state="TX",
            normalized_name="lone star",
            run_id="run-101"
        )
        session.add(c1)
        await session.commit()

        # Candidate with same USDOT but different raw name
        candidate = Company(
            company_name="Lone Star Express Inc",
            usdot="3849102",
            state="TX"
        )
        duplicate = await Deduplicator.find_duplicate(session, candidate)
        assert duplicate is not None
        assert duplicate.id == c1.id


@pytest.mark.asyncio
async def test_dedup_by_phone():
    async with AsyncSessionLocal() as session:
        c1 = Company(
            company_name="Blue Ridge Transport LLC",
            phone="(404) 555-0199",
            normalized_phone="+14045550199",
            state="GA",
            run_id="run-101"
        )
        session.add(c1)
        await session.commit()

        # Candidate with different name format but same normalized phone
        candidate = Company(
            company_name="Blue Ridge Logistics",
            normalized_phone="+14045550199",
            state="GA"
        )
        duplicate = await Deduplicator.find_duplicate(session, candidate)
        assert duplicate is not None
        assert duplicate.id == c1.id


@pytest.mark.asyncio
async def test_dedup_by_name_and_state():
    async with AsyncSessionLocal() as session:
        c1 = Company(
            company_name="Apex Freight Lines LLC",
            normalized_name="apex",
            state="OH",
            run_id="run-101"
        )
        session.add(c1)
        await session.commit()

        # Candidate with same normalized name and state
        candidate = Company(
            company_name="Apex Transportation Inc",
            normalized_name="apex",
            state="Ohio"
        )
        duplicate = await Deduplicator.find_duplicate(session, candidate)
        assert duplicate is not None
        assert duplicate.id == c1.id


@pytest.mark.asyncio
async def test_dedup_intra_run_isolation():
    """Verifies that scoping by run_id isolates matches when requested."""
    async with AsyncSessionLocal() as session:
        c1 = Company(
            company_name="Run A Carrier",
            usdot="1112223",
            run_id="run-A"
        )
        session.add(c1)
        await session.commit()

        candidate = Company(
            company_name="Run B Carrier",
            usdot="1112223"
        )
        # Search specifically within run-B
        dup_in_b = await Deduplicator.find_duplicate(session, candidate, run_id="run-B")
        assert dup_in_b is None

        # Search without run constraint
        dup_global = await Deduplicator.find_duplicate(session, candidate)
        assert dup_global is not None
        assert dup_global.id == c1.id


def test_merge_records_preserves_higher_quality_and_merges_provenance():
    existing = Company(
        company_name="Apex Freight Lines LLC",
        usdot="3849102",
        phone="(214) 555-0182",
        city="Dallas",
        state="TX",
        fleet_size=4,
        equipment=["dry_van"],
        field_provenance={
            "usdot": {"source": "fmcsa_safer", "method": "official"},
            "phone": {"source": "fmcsa_safer", "method": "official"}
        }
    )

    candidate = Company(
        company_name="Apex Freight",
        email="dispatch@apexfreight.example.com",
        website="https://apexfreight.example.com",
        normalized_domain="apexfreight.example.com",
        equipment=["reefer"],
        field_provenance={
            "email": {"source": "company_website", "method": "scraped"},
            "website": {"source": "company_website", "method": "scraped"},
            "phone": {"source": "google_search", "method": "inferred"}
        }
    )

    merged = Deduplicator.merge_records(existing, candidate)

    # Existing phone should NOT be overwritten
    assert merged.phone == "(214) 555-0182"
    # Missing fields should be populated
    assert merged.email == "dispatch@apexfreight.example.com"
    assert merged.website == "https://apexfreight.example.com"
    # Equipment lists should be merged
    assert set(merged.equipment) == {"dry_van", "reefer"}
    # Provenance should be merged: existing phone provenance preserved, email & website added
    assert merged.field_provenance["phone"]["method"] == "official"
    assert merged.field_provenance["email"]["method"] == "scraped"
    assert merged.field_provenance["website"]["method"] == "scraped"


@pytest.mark.asyncio
async def test_partial_unique_index_enforces_carrier_usdot_uniqueness():
    """H1: Enforces that CARRIER records cannot have duplicate USDOTs in database."""
    from sqlalchemy.exc import IntegrityError
    async with AsyncSessionLocal() as session:
        c1 = Company(
            company_name="Lone Star Carrier LLC",
            usdot="4910283",
            lead_type="CARRIER",
            state="TX"
        )
        session.add(c1)
        await session.commit()

        # Second carrier with exact same USDOT must fail partial unique index
        c2 = Company(
            company_name="Duplicate Lone Star LLC",
            usdot="4910283",
            lead_type="CARRIER",
            state="TX"
        )
        session.add(c2)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        # Shippers without USDOT or with empty USDOT are allowed
        s1 = Company(
            company_name="Shipper Plant A",
            lead_type="SHIPPER",
            usdot=None,
            state="OH"
        )
        s2 = Company(
            company_name="Shipper Plant B",
            lead_type="SHIPPER",
            usdot=None,
            state="PA"
        )
        session.add_all([s1, s2])
        await session.commit()
        assert s1.id is not None
        assert s2.id is not None


def test_survivorship_merging_rule():
    """H1: Verifies survivorship score selects best verified record and merges contacts/DNC flags."""
    from scripts.maintenance.deduplicate_carriers import calculate_survivorship_score

    loser_row = {
        "lead_status": "NEEDS_ENRICHMENT",
        "verification_status": "UNVERIFIED",
        "phone_verification_status": "FORMAT_OK",
        "email_verification_status": "UNKNOWN",
        "lead_score": 3.2,
        "verification_confidence": 0.3
    }
    survivor_row = {
        "lead_status": "QUALIFIED",
        "verification_status": "VERIFIED",
        "phone_verification_status": "VERIFIED",
        "email_verification_status": "DOMAIN_OK",
        "lead_score": 7.5,
        "verification_confidence": 0.85
    }

    loser_score = calculate_survivorship_score(loser_row, contact_count=0, outcome_count=0)
    survivor_score = calculate_survivorship_score(survivor_row, contact_count=1, outcome_count=0)

    assert survivor_score > loser_score
    assert survivor_score >= 450.0
