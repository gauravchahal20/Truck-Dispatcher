import pytest
from datetime import datetime, timezone
from app.models.entities import Company, Contact, SuppressionEntry, Run, FMCSAInsurance, FMCSAAuthorityHistory, FMCSANewApplication
# pyrefly: ignore[missing-import]
from app.services.compliance import ComplianceService
from app.services.sheets_service import GoogleSheetsService
from app.core.database import AsyncSessionLocal, async_engine, Base


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.mark.asyncio
async def test_suppression_detection_by_email_phone_domain_usdot():
    """Verifies that ComplianceService accurately flags suppression across all 4 identifiers."""
    async with AsyncSessionLocal() as session:
        # 1. Add suppression entries
        await ComplianceService.add_suppression(
            session,
            email="optout@litigator-carrier.com",
            phone="(214) 555-0199",
            domain="litigator-carrier.com",
            usdot="9876543",
            reason="LITIGATOR_OPT_OUT"
        )

        # 2. Check email match
        supp_email, reason_email = await ComplianceService.is_suppressed(session, email="OPTOUT@litigator-carrier.com")
        assert supp_email is True
        assert "LITIGATOR" in reason_email

        # 3. Check phone match (normalized variation)
        supp_phone, _ = await ComplianceService.is_suppressed(session, phone="+1-214-555-0199")
        assert supp_phone is True

        # 4. Check domain match (url variation)
        supp_dom, _ = await ComplianceService.is_suppressed(session, domain="https://www.litigator-carrier.com/contact")
        assert supp_dom is True

        # 5. Check USDOT match
        supp_dot, _ = await ComplianceService.is_suppressed(session, usdot=9876543)
        assert supp_dot is True

        # 6. Check clean lead is NOT suppressed
        clean_supp, _ = await ComplianceService.is_suppressed(
            session,
            email="clean@example.com",
            phone="555-0182",
            domain="cleanexample.com",
            usdot="1234567"
        )
        assert clean_supp is False


@pytest.mark.asyncio
async def test_screen_and_apply_sets_dnc_flags():
    """Verifies screen_and_apply marks dnc_flag on company and individual contacts."""
    async with AsyncSessionLocal() as session:
        await ComplianceService.add_suppression(
            session,
            phone="(404) 555-0123",
            reason="DNC_REQUEST"
        )

        comp = Company(
            company_name="Southern Transport LLC",
            phone="(404) 555-0123",
            usdot="5551234"
        )
        ct = Contact(
            company_id="dummy-id",
            full_name="John Doe",
            phone="(404) 555-0123"
        )
        comp.contacts.append(ct)

        is_supp = await ComplianceService.screen_and_apply(session, comp)
        assert is_supp is True
        assert comp.dnc_flag is True
        assert comp.suppression_reason == "DNC_REQUEST"


@pytest.mark.asyncio
async def test_suppressed_leads_never_appear_in_final_export():
    """
    CRITICAL COMPLIANCE TEST:
    Proves that suppressed companies or contacts never appear in final lead export rows.
    """
    async with AsyncSessionLocal() as session:
        sheets_srv = GoogleSheetsService()
        run = Run(
            id="run-compliance-test",
            name="Compliance Verification Run",
            target_states=["TX"]
        )
        session.add(run)

        # 1. Clean qualified lead
        c_clean = Company(
            id="c-clean-1",
            run_id=run.id,
            company_name="Valid Clean Logistics",
            usdot="1111111",
            lead_status="FINAL",
            lead_score=7.8,
            priority="B",
            dnc_flag=False
        )
        ct_clean = Contact(
            id="ct-clean-1",
            company_id=c_clean.id,
            full_name="Alice Vance",
            title="Owner",
            phone="(214) 555-0182",
            email="alice@cleanlogistics.example.com",
            is_decision_maker=True,
            dnc_flag=False
        )
        c_clean.contacts.append(ct_clean)
        session.add(c_clean)

        # 2. Suppressed company (opted out)
        c_suppressed = Company(
            id="c-suppressed-1",
            run_id=run.id,
            company_name="Do Not Contact Freight",
            usdot="2222222",
            lead_status="FINAL",
            lead_score=8.5,
            priority="A",
            dnc_flag=True,
            suppression_reason="OPT_OUT_REQUESTED"
        )
        session.add(c_suppressed)

        # 3. Company with a DNC contact
        c_dnc_contact = Company(
            id="c-dnc-contact-1",
            run_id=run.id,
            company_name="Mixed Contact Logistics",
            usdot="3333333",
            lead_status="FINAL",
            lead_score=7.5,
            priority="B",
            dnc_flag=False
        )
        ct_dnc = Contact(
            id="ct-dnc-1",
            company_id=c_dnc_contact.id,
            full_name="Bob Litigator",
            phone="(214) 555-0199",
            is_decision_maker=True,
            dnc_flag=True  # Contact on DNC list
        )
        ct_valid_staff = Contact(
            id="ct-valid-staff",
            company_id=c_dnc_contact.id,
            full_name="Carol Operations",
            phone="(214) 555-0188",
            is_decision_maker=False,
            dnc_flag=False
        )
        c_dnc_contact.contacts.extend([ct_dnc, ct_valid_staff])
        session.add(c_dnc_contact)

        await session.commit()

        # Generate sync export
        export_result = await sheets_srv.sync_run_to_sheets(session, run)

        csv_path = export_result.get("csv_path")
        assert csv_path is not None
        assert export_result["rejected_count"] == 1
        assert export_result["final_count"] == 2

        # Read exported final CSV content
        with open(csv_path, "r", encoding="utf-8") as f:
            final_csv_text = f.read()

        # Assert suppressed company is NEVER in final CSV
        assert "Do Not Contact Freight" not in final_csv_text
        assert "2222222" not in final_csv_text

        # Assert DNC contact is NEVER exported as the contact
        assert "Bob Litigator" not in final_csv_text

        # Assert valid clean lead IS in final CSV
        assert "Valid Clean Logistics" in final_csv_text
        assert "Alice Vance" in final_csv_text

        # Assert mixed company used non-DNC staff
        assert "Carol Operations" in final_csv_text


@pytest.mark.asyncio
async def test_d5_signal_tables_checksum_persistence():
    """Verifies D5 signal tables (insurance, authority history, new applications) support incremental checksum inserts."""
    async with AsyncSessionLocal() as session:
        # Insurance record
        ins = FMCSAInsurance(
            dot_number="1234567",
            docket_number="MC-99999",
            policy_no="POL-7788",
            max_cov_amount="1000000",
            raw_checksum="chk_ins_123"
        )
        session.add(ins)

        # Authority History record
        auth = FMCSAAuthorityHistory(
            dot_number="1234567",
            docket_number="MC-99999",
            op_auth_type="COMMON CARRIER",
            order_type_desc="GRANTED",
            raw_checksum="chk_auth_123"
        )
        session.add(auth)

        # New Application / Rejection record
        app_rec = FMCSANewApplication(
            dot_number="1234567",
            docket_number="MC-99999",
            rej_reasons="Pending BOC-3 filing",
            raw_checksum="chk_app_123"
        )
        session.add(app_rec)

        await session.commit()

        # Verify query
        ins_loaded = await session.get(FMCSAInsurance, ins.id)
        assert ins_loaded is not None
        assert ins_loaded.raw_checksum == "chk_ins_123"
        assert ins_loaded.policy_no == "POL-7788"


@pytest.mark.asyncio
async def test_h6_signal_sync_methods_offline(monkeypatch):
    """H6: Verifies sync_insurance, sync_authority_history, and sync_new_applications store rows with checksums."""
    from unittest.mock import AsyncMock, MagicMock
    import httpx
    from app.adapters.fmcsa_official import FMCSAOfficialAdapter

    adapter = FMCSAOfficialAdapter(enabled=True)

    mock_ins_resp = MagicMock()
    mock_ins_resp.status_code = 200
    mock_ins_resp.json.return_value = [
        {"dot_number": "01234567", "docket_number": "MC11111", "policy_no": "P-100", "name_company": "SAFE CARRIER INS", "max_cov_amount": "1000"}
    ]

    mock_auth_resp = MagicMock()
    mock_auth_resp.status_code = 200
    mock_auth_resp.json.return_value = [
        {"usdot_number": "01234567", "docket_number": "MC11111", "order1_type_desc": "Notice Of Voluntary Suspension", "order1_serve_date": "20261024"}
    ]

    mock_app_resp = MagicMock()
    mock_app_resp.status_code = 200
    mock_app_resp.json.return_value = [
        {"dot_number": "01234567", "docket_number": "MC11111", "policy_no": "P-200", "rej_reasons": "Carrier name differs"}
    ]

    async with AsyncSessionLocal() as session:
        # 1. Test sync insurance
        with monkeypatch.context() as m:
            m.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=mock_ins_resp))
            res_ins = await adapter.sync_insurance(session, limit=1)
            assert res_ins["status_code"] == 200
            assert res_ins["inserted_or_updated"] == 1

        # 2. Test sync authority history
        with monkeypatch.context() as m:
            m.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=mock_auth_resp))
            res_auth = await adapter.sync_authority_history(session, limit=1)
            assert res_auth["status_code"] == 200
            assert res_auth["inserted_or_updated"] == 1

        # 3. Test sync new applications
        with monkeypatch.context() as m:
            m.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=mock_app_resp))
            res_app = await adapter.sync_new_applications(session, limit=1)
            assert res_app["status_code"] == 200
            assert res_app["inserted_or_updated"] == 1


@pytest.mark.asyncio
async def test_j4_signal_coverage_and_config_caps():
    """J4: Verifies signals configuration caps and stored carrier targeting options."""
    from backend.app.core.config import config
    
    assert hasattr(config, "signals")
    assert config.signals.sync_caps.insurance_limit >= 500
    assert config.signals.sync_caps.authority_history_limit >= 500
    assert config.signals.sync_caps.new_applications_limit >= 500
    assert config.signals.sync_caps.sync_stored_carriers_first is True

    # Test joining by USDOT logic
    from backend.app.models.entities import Company, FMCSAInsurance
    from backend.app.adapters.fmcsa_official import FMCSAOfficialAdapter
    async with AsyncSessionLocal() as session:
        carrier = Company(
            company_name="Test Logistics",
            lead_type="CARRIER",
            usdot="1234567",
            lead_status="QUALIFIED"
        )
        session.add(carrier)
        await session.commit()

        adapter = FMCSAOfficialAdapter(enabled=True)
        stored_dots = await adapter._get_stored_carrier_dots(session)
        assert isinstance(stored_dots, list)
        assert "1234567" in stored_dots


