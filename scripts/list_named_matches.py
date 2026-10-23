import sqlite3
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
# pyrefly: ignore[missing-import]
from app.services.email_verifier import EmailVerifier

def inspect_matches():
    conn = sqlite3.connect('trucklead.db')
    c = conn.cursor()

    query = """
        SELECT c.id, c.company_name, c.usdot, c.email, ct.full_name, ct.title, ct.email, ct.field_provenance
        FROM companies c
        LEFT JOIN contacts ct ON ct.company_id = c.id
    """
    rows = c.execute(query).fetchall()

    matches = []
    seen = set()
    for cid, cname, usdot, c_em, ct_name, ct_title, ct_em, prov in rows:
        em = ct_em or c_em
        if em and ct_name:
            if EmailVerifier.is_named_person_match(em, ct_name):
                key = (cid, em)
                if key in seen:
                    continue
                seen.add(key)
                
                # Analyze matching rule
                local = em.strip().lower().split("@")[0]
                name_clean = ct_name.lower().strip()
                parts = [p for p in name_clean.split() if len(p) >= 2]
                first = parts[0] if parts else ""
                last = parts[-1] if len(parts) > 1 else ""
                
                rule = "unknown"
                if local == first:
                    rule = "exact_first_name (e.g. john@)"
                elif last and local == last:
                    rule = "exact_last_name (e.g. smith@)"
                elif last and local in [f"{first}.{last}", f"{first}_{last}", f"{first}{last}"]:
                    rule = "first_last_combo (e.g. john.smith@)"
                elif last and local in [f"{first[0]}{last}", f"{first[0]}.{last}", f"{first[0]}_{last}"]:
                    rule = "first_initial_last (e.g. jsmith@)"
                elif first in local:
                    rule = f"first_name_in_local ('{first}' in '{local}')"
                elif last and len(last) >= 4 and last in local:
                    rule = f"last_name_in_local ('{last}' in '{local}')"
                
                prov_dict = {}
                if prov:
                    try:
                        prov_dict = json.loads(prov)
                    except Exception:
                        prov_dict = {"raw": prov}

                matches.append({
                    "company": cname,
                    "usdot": usdot,
                    "contact_name": ct_name,
                    "title": ct_title or "Company officer (per MCS-150)",
                    "email": em,
                    "local_part": local,
                    "matched_rule": rule,
                    "name_source": prov_dict.get("full_name", "FMCSA Census / MCS-150 filing officer declaration")
                })

    print(f"Total Unique Named-Person Matches: {len(matches)}")
    for i, m in enumerate(matches, 1):
        print(f"\n[{i}] Company: {m['company']} (USDOT: {m['usdot']})")
        print(f"    Contact Name: {m['contact_name']} ({m['title']})")
        print(f"    Email: {m['email']}")
        print(f"    Rule: {m['matched_rule']}")
        print(f"    Name Source: {m['name_source']}")

    conn.close()

if __name__ == "__main__":
    inspect_matches()
