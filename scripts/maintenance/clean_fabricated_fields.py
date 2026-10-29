#!/usr/bin/env python3
"""
scripts/clean_fabricated_fields.py

Scans existing companies in trucklead.db and:
1. Detects fabricated defaults from adapters:
   - indeed_jobs, procurement_news, google_search, industry_directories,
     google_maps, specialized_verticals
   - Fields matching old hardcoded fallbacks:
     * city in [Dallas, Atlanta, Chicago, Columbus, Houston, Savannah, Long Beach]
     * fleet_size in [5, 6]
     * driver_count in [5, 6]
     * operating_status in [ACTIVE]
     * safety_rating in [SATISFACTORY]
     * carrier_operation in [Interstate]
     * equipment matching guessed defaults (['Dry Van'], ['Dry Van', 'Drayage'])
2. Sets fabricated fields to NULL / empty list.
3. Flags the lead needs_reverification = True.
4. Builds baseline field_provenance for remaining non-null fields.
5. Runs in dry-run mode by default; pass --apply to commit changes.
"""

import sys
import json
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime, timezone

TARGET_ADAPTERS = [
    "indeed_jobs",
    "procurement_news",
    "google_search",
    "industry_directories",
    "google_maps",
    "specialized_verticals",
]

GUESSED_CITIES = {
    "Dallas", "Atlanta", "Chicago", "Columbus", "Houston", "Savannah", "Long Beach"
}


def main():
    parser = argparse.ArgumentParser(description="Clean fabricated fields from trucklead.db")
    parser.add_argument("--db-path", default="trucklead.db", help="Path to sqlite database")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    args = parser.parse_args()

    db_path = Path(args.db_path).resolve()
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    print(f"{'='*60}")
    print(f"TRUCKLEAD DB FABRICATION CLEANUP SCRIPT")
    print(f"Mode: {'APPLY (REAL RUN)' if args.apply else 'DRY RUN (NO CHANGES WRITTEN)'}")
    print(f"Database: {db_path}")
    print(f"{'='*60}\n")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Query all companies
    cursor.execute("""
        SELECT id, company_name, lead_source, source_url, created_at,
               city, state, fleet_size, driver_count, equipment,
               carrier_operation, operating_status, safety_rating,
               field_provenance, needs_reverification,
               usdot, mc_number, website, phone, email, address, zip_code
        FROM companies
    """)
    rows = cursor.fetchall()
    print(f"Total companies in database: {len(rows)}")

    target_leads = [r for r in rows if r["lead_source"] in TARGET_ADAPTERS]
    print(f"Companies from targeted adapters ({', '.join(TARGET_ADAPTERS)}): {len(target_leads)}\n")

    counts = {
        "city_cleared": 0,
        "fleet_size_cleared": 0,
        "driver_count_cleared": 0,
        "operating_status_cleared": 0,
        "safety_rating_cleared": 0,
        "carrier_operation_cleared": 0,
        "equipment_cleared": 0,
        "total_leads_flagged": 0,
        "provenance_initialized": 0,
    }

    leads_to_update = []

    for r in rows:
        lead_id = r["id"]
        source = r["lead_source"] or "unknown"
        is_target_source = source in TARGET_ADAPTERS

        updates = {}
        changes_for_lead = []

        if is_target_source:
            # Check city
            # Note: For google_maps, city extracted via Nominatim is genuine,
            # but Dallas/Atlanta/Columbus from state map was guessed.
            # In indeed/news/gsearch/dir/verticals, city was 100% guessed.
            if source != "google_maps":
                if r["city"] in GUESSED_CITIES or r["city"]:
                    updates["city"] = None
                    changes_for_lead.append(f"city: '{r['city']}' -> NULL")
                    counts["city_cleared"] += 1
            else:
                # In google_maps, Nominatim was used, but if city matched guessed default Dallas/Atlanta without address
                if not r["address"] and r["city"] in GUESSED_CITIES:
                    updates["city"] = None
                    changes_for_lead.append(f"city: '{r['city']}' -> NULL")
                    counts["city_cleared"] += 1

            # Check fleet_size (5 or 6 was hardcoded fallback)
            if r["fleet_size"] in (5, 6):
                updates["fleet_size"] = None
                changes_for_lead.append(f"fleet_size: {r['fleet_size']} -> NULL")
                counts["fleet_size_cleared"] += 1

            # Check driver_count (5 or 6 was hardcoded fallback)
            if r["driver_count"] in (5, 6):
                updates["driver_count"] = None
                changes_for_lead.append(f"driver_count: {r['driver_count']} -> NULL")
                counts["driver_count_cleared"] += 1

            # Check operating_status (ACTIVE was hardcoded fallback)
            if r["operating_status"] == "ACTIVE":
                updates["operating_status"] = None
                changes_for_lead.append(f"operating_status: '{r['operating_status']}' -> NULL")
                counts["operating_status_cleared"] += 1

            # Check safety_rating (SATISFACTORY was hardcoded fallback)
            if r["safety_rating"] == "SATISFACTORY":
                updates["safety_rating"] = None
                changes_for_lead.append(f"safety_rating: '{r['safety_rating']}' -> NULL")
                counts["safety_rating_cleared"] += 1

            # Check carrier_operation (Interstate was hardcoded fallback)
            if r["carrier_operation"] == "Interstate":
                updates["carrier_operation"] = None
                changes_for_lead.append(f"carrier_operation: '{r['carrier_operation']}' -> NULL")
                counts["carrier_operation_cleared"] += 1

            # Check equipment (['Dry Van'] or ['Dry Van', 'Drayage'] was hardcoded)
            eq_val = r["equipment"]
            if isinstance(eq_val, str):
                try:
                    eq_parsed = json.loads(eq_val)
                except Exception:
                    eq_parsed = []
            elif isinstance(eq_val, list):
                eq_parsed = eq_val
            else:
                eq_parsed = []

            if eq_parsed in (["Dry Van"], ["Dry Van", "Drayage"]):
                updates["equipment"] = "[]"
                changes_for_lead.append(f"equipment: {eq_parsed} -> []")
                counts["equipment_cleared"] += 1

        # Check / Build field_provenance for all leads if missing
        raw_prov = r["field_provenance"]
        try:
            prov_dict = json.loads(raw_prov) if raw_prov else {}
        except Exception:
            prov_dict = {}

        # If any fabricated field was updated, flag needs_reverification
        if changes_for_lead:
            updates["needs_reverification"] = 1
            counts["total_leads_flagged"] += 1

        # Build provenance for genuine fields remaining
        url_lower = (r["source_url"] or "").lower()
        src_lower = source.lower()
        is_official = (
            ("fmcsa_official" in src_lower or "data.transportation.gov" in url_lower or "fmcsa.dot.gov" in url_lower)
            and "usdotlookup.com" not in url_lower
            and src_lower not in ("fmcsa_safer", "fmcsa_li")
        )
        prov_method = "official" if is_official else "scraped"
        retrieved_time = r["created_at"] or datetime.now(timezone.utc).isoformat()
        if hasattr(retrieved_time, "isoformat"):
            retrieved_time = retrieved_time.isoformat()

        all_fields = {
            "company_name": r["company_name"],
            "usdot": r["usdot"],
            "mc_number": r["mc_number"],
            "website": r["website"],
            "phone": r["phone"],
            "email": r["email"],
            "address": r["address"],
            "city": updates.get("city", r["city"]),
            "state": r["state"],
            "zip_code": r["zip_code"],
            "fleet_size": updates.get("fleet_size", r["fleet_size"]),
            "driver_count": updates.get("driver_count", r["driver_count"]),
            "operating_status": updates.get("operating_status", r["operating_status"]),
            "safety_rating": updates.get("safety_rating", r["safety_rating"]),
            "carrier_operation": updates.get("carrier_operation", r["carrier_operation"]),
        }

        updated_prov = False
        for f_name, f_val in all_fields.items():
            if f_val is not None and f_val != "" and f_val != "[]" and f_val != []:
                if f_name not in prov_dict:
                    prov_dict[f_name] = {
                        "source": source,
                        "url": r["source_url"],
                        "retrieved_at": str(retrieved_time),
                        "method": prov_method,
                    }
                    updated_prov = True
                else:
                    # Enforce Workstream K2 rule: usdotlookup.com and scraper sources are strictly 'scraped'
                    entry = prov_dict[f_name]
                    entry_url = (entry.get("url") or "").lower()
                    entry_src = (entry.get("source") or "").lower()
                    if "usdotlookup.com" in entry_url or entry_src in ("fmcsa_safer", "fmcsa_li"):
                        if entry.get("method") != "scraped":
                            entry["method"] = "scraped"
                            updated_prov = True
            elif f_name in prov_dict and (f_val is None or f_val == "" or f_val == "[]"):
                # Remove cleaned fields from provenance
                del prov_dict[f_name]
                updated_prov = True

        # Enforce Workstream K2 rule: usdotlookup.com and scraper sources are strictly 'scraped' across all provenance keys
        for k, entry in prov_dict.items():
            if isinstance(entry, dict):
                e_url = (entry.get("url") or "").lower()
                e_src = (entry.get("source") or "").lower()
                if "usdotlookup.com" in e_url or e_src in ("fmcsa_safer", "fmcsa_li"):
                    if entry.get("method") != "scraped":
                        entry["method"] = "scraped"
                        updated_prov = True

        if updated_prov or not raw_prov:
            updates["field_provenance"] = json.dumps(prov_dict)
            counts["provenance_initialized"] += 1

        if updates:
            leads_to_update.append((lead_id, r["company_name"], source, updates, changes_for_lead))

    print(f"--- SUMMARY OF DETECTED FABRICATION & PROVENANCE ---")
    print(f"Leads with fabricated fields found:       {counts['total_leads_flagged']}")
    print(f"  - city fields to set NULL:             {counts['city_cleared']}")
    print(f"  - fleet_size fields to set NULL:       {counts['fleet_size_cleared']}")
    print(f"  - driver_count fields to set NULL:     {counts['driver_count_cleared']}")
    print(f"  - operating_status to set NULL:        {counts['operating_status_cleared']}")
    print(f"  - safety_rating to set NULL:           {counts['safety_rating_cleared']}")
    print(f"  - carrier_operation to set NULL:       {counts['carrier_operation_cleared']}")
    print(f"  - equipment fields to reset to []:     {counts['equipment_cleared']}")
    print(f"Leads getting field_provenance populated: {counts['provenance_initialized']}")
    print(f"----------------------------------------------------\n")

    fabricated_leads = [x for x in leads_to_update if x[4]]
    if fabricated_leads and not args.apply:
        print(f"SAMPLE OF LEADS WITH FABRICATED FIELDS TO BE CLEARED ({len(fabricated_leads)} total):")
        for idx, (lid, name, src, upds, chgs) in enumerate(fabricated_leads[:10]):
            print(f"[{idx+1}] {name} (ID: {lid[:8]}..., Source: {src})")
            for c in chgs:
                print(f"    * {c}")
        print("\nTo apply these updates, re-run with: python scripts/clean_fabricated_fields.py --apply\n")

    if args.apply:
        print(f"Applying updates to {len(leads_to_update)} leads in database...")
        for lid, name, src, upds, chgs in leads_to_update:
            set_clauses = [f"{k} = ?" for k in upds.keys()]
            values = list(upds.values()) + [lid]
            query = f"UPDATE companies SET {', '.join(set_clauses)} WHERE id = ?"
            cursor.execute(query, values)
        conn.commit()
        print("All updates successfully applied and committed to trucklead.db.")

    conn.close()


if __name__ == "__main__":
    main()
