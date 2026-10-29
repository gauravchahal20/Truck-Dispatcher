import sqlite3
import pytest
from pathlib import Path
from app.api.routes_outcomes import compute_contact_confidence
from app.services.email_verifier import EmailVerifier


def test_format_only_phone_never_ready_high():
    """Asserts that format-only phone is never assigned ready-HIGH confidence."""
    # Format-only phone with no email or domain-only email must be LOW (or MEDIUM if named match)
    assert compute_contact_confidence("FORMAT_OK", "UNKNOWN", False) == "LOW"
    assert compute_contact_confidence("FORMAT_OK", "DOMAIN_OK", False) == "LOW"
    assert compute_contact_confidence("FORMAT_OK", "DOMAIN_OK", True) == "MEDIUM"

    # Only provider-VERIFIED phone or DELIVERABLE email for named person can be HIGH
    assert compute_contact_confidence("VERIFIED", "UNKNOWN", False) == "HIGH"
    assert compute_contact_confidence("FORMAT_OK", "DELIVERABLE", True) == "HIGH"
    assert compute_contact_confidence("FORMAT_OK", "DELIVERABLE", False) == "MEDIUM"


@pytest.mark.live
def test_rejected_only_for_hard_gates(session_fixture_db):
    """Regression test: REJECTED status is strictly reserved for hard gates; low score => NEEDS_ENRICHMENT."""
    conn = sqlite3.connect(str(session_fixture_db))
    c = conn.cursor()

    # Query all rejected leads
    rejected_rows = c.execute("""
        SELECT id, lead_type, lead_score, operating_status, dnc_flag, rejection_reason
        FROM companies
        WHERE lead_status = 'REJECTED'
    """).fetchall()

    assert len(rejected_rows) > 0, "Expected rejected leads from hard gates"

    for cid, lt, score, op_st, dnc, rej_reason in rejected_rows:
        # Every rejected lead MUST have a hard-gate failure (DNC or unauthorized operating status)
        op_upper = (op_st or "").upper()
        has_auth_hard_gate = any(bad in op_upper for bad in ["PRIVATE PROPERTY", "NOT AUTHORIZED", "REVOKED", "INACTIVE"])
        assert dnc or has_auth_hard_gate, (
            f"Company {cid} was REJECTED without hard-gate failure: score={score}, op_st={op_st}, reason={rej_reason}"
        )
        assert not (rej_reason and rej_reason.startswith("Score")), (
            f"Company {cid} has score-based rejection reason: {rej_reason}"
        )

    # Assert that all leads with score < 5.0 and NO hard gate are in NEEDS_ENRICHMENT (or NOT_ICP)
    low_score_clean = c.execute("""
        SELECT COUNT(*)
        FROM companies
        WHERE lead_score < 5.0
          AND dnc_flag = 0
          AND (operating_status IS NULL OR NOT (
              operating_status LIKE '%PRIVATE PROPERTY%' OR
              operating_status LIKE '%NOT AUTHORIZED%' OR
              operating_status LIKE '%REVOKED%' OR
              operating_status LIKE '%INACTIVE%'
          ))
          AND lead_status NOT IN ('NEEDS_ENRICHMENT', 'NOT_ICP')
    """).fetchone()[0]

    assert low_score_clean == 0, f"Found {low_score_clean} low-score leads outside NEEDS_ENRICHMENT"
    conn.close()


@pytest.mark.live
def test_final_requires_verified_contact_or_reached(session_fixture_db):
    """Regression test: with no providers and no outreach outcomes, FINAL must be 0."""
    conn = sqlite3.connect(str(session_fixture_db))
    c = conn.cursor()

    final_count = c.execute("SELECT COUNT(*) FROM companies WHERE lead_status = 'FINAL'").fetchone()[0]
    assert final_count == 0, f"Expected 0 FINAL leads without provider verification; got {final_count}"
    conn.close()


@pytest.mark.live
def test_population_distributions_sum_to_totals(session_fixture_db):
    """
    Asserts that every distribution across carriers and shippers
    sums exactly to its population:
    - lead status
    - phone verification status
    - email verification status
    - contact confidence tiers
    - named-person email matching
    """
    conn = sqlite3.connect(str(session_fixture_db))
    c = conn.cursor()

    TOTAL_CARRIERS = c.execute("SELECT COUNT(*) FROM companies WHERE lead_type = 'CARRIER'").fetchone()[0]
    TOTAL_SHIPPERS = c.execute("SELECT COUNT(*) FROM companies WHERE lead_type = 'SHIPPER'").fetchone()[0]

    # 1. Lead Status Distribution
    st_rows = c.execute("SELECT lead_type, COUNT(*) FROM companies GROUP BY lead_type").fetchall()
    st_dict = dict(st_rows)
    assert st_dict["CARRIER"] == TOTAL_CARRIERS
    assert st_dict["SHIPPER"] == TOTAL_SHIPPERS

    carrier_st = dict(c.execute("SELECT lead_status, COUNT(*) FROM companies WHERE lead_type = 'CARRIER' GROUP BY lead_status").fetchall())
    assert sum(carrier_st.values()) == TOTAL_CARRIERS
    assert carrier_st.get("FINAL", 0) == 0

    shipper_st = dict(c.execute("SELECT lead_status, COUNT(*) FROM companies WHERE lead_type = 'SHIPPER' GROUP BY lead_status").fetchall())
    assert sum(shipper_st.values()) == TOTAL_SHIPPERS

    # 2. Phone Status Distribution
    carrier_ph = dict(c.execute("SELECT phone_verification_status, COUNT(*) FROM companies WHERE lead_type = 'CARRIER' GROUP BY phone_verification_status").fetchall())
    assert sum(carrier_ph.values()) == TOTAL_CARRIERS

    shipper_ph = dict(c.execute("SELECT phone_verification_status, COUNT(*) FROM companies WHERE lead_type = 'SHIPPER' GROUP BY phone_verification_status").fetchall())
    assert sum(shipper_ph.values()) == TOTAL_SHIPPERS

    # 3. Email Status Distribution
    carrier_em = dict(c.execute("SELECT email_verification_status, COUNT(*) FROM companies WHERE lead_type = 'CARRIER' GROUP BY email_verification_status").fetchall())
    assert sum(carrier_em.values()) == TOTAL_CARRIERS

    shipper_em = dict(c.execute("SELECT email_verification_status, COUNT(*) FROM companies WHERE lead_type = 'SHIPPER' GROUP BY email_verification_status").fetchall())
    assert sum(shipper_em.values()) == TOTAL_SHIPPERS

    # 4. Confidence Tiers & Named-Person Email Matches
    rows = c.execute("""
        SELECT c.id, c.lead_type, c.phone_verification_status, c.email_verification_status, c.email, ct.full_name, ct.email
        FROM companies c
        LEFT JOIN contacts ct ON ct.company_id = c.id
    """).fetchall()

    by_comp = {}
    for cid, lt, p_st, em_st, c_em, ct_name, ct_em in rows:
        if cid not in by_comp:
            by_comp[cid] = {"lt": lt, "p_st": p_st, "em_st": em_st, "is_named": False}
        target_em = ct_em or c_em
        if target_em and ct_name and EmailVerifier.is_named_person_match(target_em, ct_name):
            by_comp[cid]["is_named"] = True

    carrier_confs = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    shipper_confs = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    carrier_named = {"NAMED": 0, "UNMATCHED": 0, "NO_EMAIL": 0}
    shipper_named = {"NAMED": 0, "UNMATCHED": 0, "NO_EMAIL": 0}

    for cid, info in by_comp.items():
        conf = compute_contact_confidence(info["p_st"], info["em_st"], info["is_named"])
        target_dict = carrier_confs if info["lt"] == "CARRIER" else shipper_confs
        target_dict[conf] += 1

        named_dict = carrier_named if info["lt"] == "CARRIER" else shipper_named
        if info["em_st"] in ["DOMAIN_OK", "RISKY", "DELIVERABLE"]:
            if info["is_named"]:
                named_dict["NAMED"] += 1
            else:
                named_dict["UNMATCHED"] += 1
        else:
            named_dict["NO_EMAIL"] += 1

    assert sum(carrier_confs.values()) == TOTAL_CARRIERS
    assert carrier_confs["HIGH"] == 0

    assert sum(shipper_confs.values()) == TOTAL_SHIPPERS
    assert shipper_confs["HIGH"] == 0

    assert sum(carrier_named.values()) == TOTAL_CARRIERS
    assert sum(shipper_named.values()) == TOTAL_SHIPPERS

    conn.close()
