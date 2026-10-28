"""
Workstream N9f: Hygiene and Compliance Verification Script
Verifies:
1. 61-vs-62 question dropped and closed across documentation.
2. Unevidenced claims of '22 carriers awaiting L&I insurance posting' removed.
3. Call script is hidden when sender_identity is unset.
4. Email-ready list is blocked when postal_address is unset.
5. Both states are exposed in GET /api/config and reflected in Settings UI.
"""
import os
import sys
import httpx
import asyncio
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.main import app
from backend.app.core.config import config


async def main():
    evidence_lines = []
    evidence_lines.append("=" * 80)
    evidence_lines.append("WORKSTREAM N9f: HYGIENE & COMPLIANCE PREREQUISITES AUDIT")
    evidence_lines.append("=" * 80)
    evidence_lines.append("")

    # 1. Forensic & Documentation Checks
    evidence_lines.append("[1] DOCUMENTATION & SPECIFICATION HYGIENE CHECKS:")
    doc_sources = Path("docs/DATA_SOURCES.md").read_text(encoding="utf-8")
    doc_n7 = Path("docs/reports/N7_HYGIENE_AND_FORENSIC_REPORT.md").read_text(encoding="utf-8")
    doc_n9b = Path("docs/reports/N9B_FULL_POOL_AUTHORITY_REPORT.md").read_text(encoding="utf-8")

    # 61-vs-62 dropped
    has_dropped_n7 = "Closed & Dropped" in doc_n7
    has_dropped_sources = "61 vs 62 Inquiry Dropped" in doc_sources
    evidence_lines.append(f"  - 61-vs-62 inquiry marked 'Closed & Dropped' in N7 report: {has_dropped_n7}")
    evidence_lines.append(f"  - 61-vs-62 inquiry marked 'Dropped' in DATA_SOURCES.md: {has_dropped_sources}")

    # 22 awaiting L&I claim removed
    claim_str = "22 carriers awaiting L&I insurance posting"
    in_sources = claim_str in doc_sources
    in_n9b = claim_str in doc_n9b
    evidence_lines.append(f"  - Unverified claim '{claim_str}' present in DATA_SOURCES.md: {in_sources} (Expected: False)")
    evidence_lines.append(f"  - Unverified claim '{claim_str}' present in N9B report: {in_n9b} (Expected: False)")
    evidence_lines.append("")

    # 2. Config Endpoint Prerequisites Verification
    evidence_lines.append("[2] SYSTEM CONFIGURATION ENDPOINT (GET /api/config):")
    orig_sender = getattr(config.compliance, "sender_identity", None)
    orig_address = getattr(config.compliance, "postal_address", None)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Case A: Both Unset
        config.compliance.sender_identity = ""
        config.compliance.postal_address = ""
        res_a = await client.get("/api/config")
        comp_a = res_a.json().get("compliance", {})
        evidence_lines.append("  Case A: Both Prerequisites Unset:")
        evidence_lines.append(f"    - call_script_status:     '{comp_a.get('call_script_status')}'")
        evidence_lines.append(f"    - email_readiness_status: '{comp_a.get('email_readiness_status')}'")

        # Case B: Both Set
        config.compliance.sender_identity = "Dispatch Logistics Team"
        config.compliance.postal_address = "5000 Freight Express Way, Suite 400, Dallas, TX 75201"
        res_b = await client.get("/api/config")
        comp_b = res_b.json().get("compliance", {})
        evidence_lines.append("  Case B: Both Prerequisites Configured:")
        evidence_lines.append(f"    - call_script_status:     '{comp_b.get('call_script_status')}'")
        evidence_lines.append(f"    - email_readiness_status: '{comp_b.get('email_readiness_status')}'")
        evidence_lines.append("")

        # 3. Call Script Hiding on Operator Call Queue
        evidence_lines.append("[3] CALL SCRIPT GATING (GET /api/leads/verify-and-call-queue):")
        headers = {"X-API-Key": "test-key"}
        
        config.compliance.sender_identity = ""
        res_q_hidden = await client.get("/api/leads/verify-and-call-queue", headers=headers)
        q_hidden_json = res_q_hidden.json()
        q_hidden_items = q_hidden_json.get("items", [])
        evidence_lines.append(f"  When sender_identity is UNSET (Queue count: {q_hidden_json.get('count', 0)}):")
        if q_hidden_items:
            evidence_lines.append(f"    - script_status: '{q_hidden_items[0].get('script_status')}'")
            evidence_lines.append(f"    - call_script is None: {q_hidden_items[0].get('call_script') is None}")
        
        config.compliance.sender_identity = "Alex Turner with Summit Dispatch"
        res_q_active = await client.get("/api/leads/verify-and-call-queue", headers=headers)
        q_active_json = res_q_active.json()
        q_active_items = q_active_json.get("items", [])
        evidence_lines.append(f"  When sender_identity is CONFIGURED (Queue count: {q_active_json.get('count', 0)}):")
        if q_active_items:
            evidence_lines.append(f"    - script_status: '{q_active_items[0].get('script_status')}'")
            evidence_lines.append(f"    - call_script present: {q_active_items[0].get('call_script') is not None}")
        evidence_lines.append("")

        # 4. Email-Ready List Gating
        evidence_lines.append("[4] EMAIL READINESS GATING (GET /api/compliance/email-ready-leads):")
        config.compliance.postal_address = ""
        config.compliance.sender_identity = "Apex Dispatch"
        res_em_blocked = await client.get("/api/compliance/email-ready-leads", headers=headers)
        em_blocked_json = res_em_blocked.json()
        evidence_lines.append(f"  When postal_address is UNSET:")
        evidence_lines.append(f"    - readiness_status: '{em_blocked_json.get('readiness_status')}'")
        evidence_lines.append(f"    - is_blocked: {em_blocked_json.get('is_blocked')}")
        evidence_lines.append(f"    - postal_address_configured: {em_blocked_json.get('prerequisites', {}).get('postal_address_configured')}")
        evidence_lines.append(f"    - total_email_eligible: {em_blocked_json.get('coverage_summary', {}).get('total_email_eligible')}")

        config.compliance.postal_address = "5000 Freight Express Way, Suite 400, Dallas, TX 75201"
        res_em_ready = await client.get("/api/compliance/email-ready-leads", headers=headers)
        em_ready_json = res_em_ready.json()
        evidence_lines.append(f"  When postal_address is CONFIGURED:")
        evidence_lines.append(f"    - readiness_status: '{em_ready_json.get('readiness_status')}'")
        evidence_lines.append(f"    - is_blocked: {em_ready_json.get('is_blocked')}")
        evidence_lines.append(f"    - postal_address_configured: {em_ready_json.get('prerequisites', {}).get('postal_address_configured')}")
        evidence_lines.append(f"    - total_email_eligible: {em_ready_json.get('coverage_summary', {}).get('total_email_eligible')}")

        # Restore original config
        config.compliance.sender_identity = orig_sender
        config.compliance.postal_address = orig_address

    evidence_lines.append("")
    evidence_lines.append("=" * 80)
    evidence_lines.append("END OF N9f EVIDENCE")
    evidence_lines.append("=" * 80)

    evidence_str = "\n".join(evidence_lines)
    print(evidence_str)

    out_file = Path("docs/reports/evidence/n9f.txt")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(evidence_str, encoding="utf-8")
    print(f"\nSaved raw evidence to {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
