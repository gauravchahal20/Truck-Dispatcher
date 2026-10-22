#!/usr/bin/env python3
"""
scripts/audit_and_clean_completeness.py

Performs complete audit and remediation for Step A follow-ups A2 and A3:
- A2: Checks each source for fallback values:
    * city in ('Dallas', 'Atlanta', 'Chicago', 'Houston', 'Savannah', 'Long Beach', 'Columbus')
    * fleet_size in (1, 5, 6)
    * driver_count in (1, 5, 6)
    * operating_status == 'ACTIVE'
    * safety_rating == 'SATISFACTORY'
    * carrier_operation == 'Interstate'
  For rows from HTML scrapers (fmcsa_safer, fmcsa_li, google_maps, google_search, etc.)
  where genuine vs fallback is ambiguous, sets suspect values to NULL and flags needs_reverification=True.
- A3: Re-writes field_provenance on all existing legacy rows to use:
    method="legacy_unverified", retrieved_at=None.
"""

import sys
import json
import sqlite3
import argparse
from pathlib import Path

SUSPECT_CITIES = ('Dallas', 'Atlanta', 'Chicago', 'Houston', 'Savannah', 'Long Beach', 'Columbus')
SUSPECT_FLEET = (1, 5, 6)
SUSPECT_DRIVERS = (1, 5, 6)
HTML_SCRAPER_SOURCES = [
    'fmcsa_safer',
    'fmcsa_li',
    'google_maps',
    'google_search',
    'industry_directories',
    'indeed_jobs',
    'procurement_news',
    'specialized_verticals',
    'live_carrier_scraper',
]


def audit(cursor):
    """Runs audit query returning breakdown by source."""
    cursor.execute("SELECT DISTINCT lead_source FROM companies")
    sources = [r[0] for r in cursor.fetchall()]

    report = {}
    for src in sources:
        cursor.execute("SELECT * FROM companies WHERE lead_source IS ?", (src,))
        rows = cursor.fetchall()

        cnt = len(rows)
        suspect_city = sum(1 for r in rows if r['city'] in SUSPECT_CITIES)
        suspect_fleet = sum(1 for r in rows if r['fleet_size'] in SUSPECT_FLEET)
        suspect_drivers = sum(1 for r in rows if r['driver_count'] in SUSPECT_DRIVERS)
        suspect_status = sum(1 for r in rows if r['operating_status'] == 'ACTIVE')
        suspect_safety = sum(1 for r in rows if r['safety_rating'] == 'SATISFACTORY')
        suspect_oper = sum(1 for r in rows if r['carrier_operation'] == 'Interstate')
        needs_reverification = sum(1 for r in rows if r['needs_reverification'])

        report[src or 'NULL'] = {
            'count': cnt,
            'suspect_city': suspect_city,
            'suspect_fleet': suspect_fleet,
            'suspect_drivers': suspect_drivers,
            'suspect_status': suspect_status,
            'suspect_safety': suspect_safety,
            'suspect_oper': suspect_oper,
            'needs_reverification': needs_reverification,
        }
    return report


def print_report(title, report):
    print(f"\n{'='*75}")
    print(f"{title}")
    print(f"{'='*75}")
    header = f"{'Source':<20} | {'Total':<5} | {'City':<5} | {'Fleet':<5} | {'Driver':<6} | {'Status':<6} | {'Safety':<6} | {'Oper':<5} | {'Re-verify':<9}"
    print(header)
    print("-" * len(header))
    for src, data in report.items():
        print(f"{src:<20} | {data['count']:<5} | {data['suspect_city']:<5} | {data['suspect_fleet']:<5} | {data['suspect_drivers']:<6} | {data['suspect_status']:<6} | {data['suspect_safety']:<6} | {data['suspect_oper']:<5} | {data['needs_reverification']:<9}")
    print("-" * len(header))


def main():
    parser = argparse.ArgumentParser(description="Audit and clean completeness (A2 + A3)")
    parser.add_argument("--db-path", default="trucklead.db", help="Path to sqlite database")
    parser.add_argument("--apply", action="store_true", help="Apply cleanup and provenance rewrite")
    args = parser.parse_args()

    db_path = Path(args.db_path).resolve()
    if not db_path.exists():
        print(f"Error: {db_path} does not exist", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path), timeout=60.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA busy_timeout = 60000;")

    before_report = audit(cursor)
    print_report("BEFORE AUDIT: SUSPECT VALUES BY SOURCE", before_report)

    # Calculate rows to remediate
    cursor.execute("SELECT * FROM companies")
    all_rows = cursor.fetchall()

    updates = []
    for r in all_rows:
        lead_id = r['id']
        src = r['lead_source'] or ''
        row_updates = {}
        flag_reverify = bool(r['needs_reverification'])

        # Remediation A2: For rows from HTML scrapers, null ambiguous fallback values
        if src in HTML_SCRAPER_SOURCES:
            if r['city'] in SUSPECT_CITIES and src != 'google_maps':
                # In google_maps, Nominatim returned the city; in other scrapers it was pure fallback
                row_updates['city'] = None
                flag_reverify = True
            elif src == 'google_maps' and not r['address'] and r['city'] in SUSPECT_CITIES:
                row_updates['city'] = None
                flag_reverify = True

            if r['fleet_size'] in SUSPECT_FLEET:
                row_updates['fleet_size'] = None
                flag_reverify = True

            if r['driver_count'] in SUSPECT_DRIVERS:
                row_updates['driver_count'] = None
                flag_reverify = True

            if r['operating_status'] == 'ACTIVE':
                row_updates['operating_status'] = None
                flag_reverify = True

            if r['safety_rating'] == 'SATISFACTORY':
                row_updates['safety_rating'] = None
                flag_reverify = True

            if r['carrier_operation'] == 'Interstate':
                row_updates['carrier_operation'] = None
                flag_reverify = True

        if flag_reverify:
            row_updates['needs_reverification'] = 1

        # Remediation A3: Honest provenance for legacy rows
        # Existing 44 rows must have method="legacy_unverified", retrieved_at=None
        current_city = row_updates.get('city', r['city'])
        current_fleet = row_updates.get('fleet_size', r['fleet_size'])
        current_drivers = row_updates.get('driver_count', r['driver_count'])
        current_status = row_updates.get('operating_status', r['operating_status'])
        current_safety = row_updates.get('safety_rating', r['safety_rating'])
        current_oper = row_updates.get('carrier_operation', r['carrier_operation'])

        fields_to_check = {
            'company_name': r['company_name'],
            'legal_name': r['legal_name'],
            'dba_name': r['dba_name'],
            'usdot': r['usdot'],
            'mc_number': r['mc_number'],
            'website': r['website'],
            'phone': r['phone'],
            'email': r['email'],
            'address': r['address'],
            'city': current_city,
            'state': r['state'],
            'zip_code': r['zip_code'],
            'fleet_size': current_fleet,
            'driver_count': current_drivers,
            'operating_status': current_status,
            'safety_rating': current_safety,
            'carrier_operation': current_oper,
        }

        legacy_prov = {}
        for f_name, f_val in fields_to_check.items():
            if f_val is not None and f_val != '' and f_val != '[]' and f_val != []:
                legacy_prov[f_name] = {
                    'source': src,
                    'url': r['source_url'],
                    'retrieved_at': None,
                    'method': 'legacy_unverified'
                }

        row_updates['field_provenance'] = json.dumps(legacy_prov)
        updates.append((lead_id, row_updates))

    print(f"\nPrepared updates for {len(updates)} rows.")
    if not args.apply:
        print("Dry run complete. Run with --apply to commit these changes to trucklead.db.\n")
    else:
        print("Applying remediation (A2 + A3) to database...")
        for lead_id, upds in updates:
            set_clauses = [f"{k} = ?" for k in upds.keys()]
            values = list(upds.values()) + [lead_id]
            cursor.execute(f"UPDATE companies SET {', '.join(set_clauses)} WHERE id = ?", values)
        conn.commit()
        print("Updates applied successfully.")

        after_report = audit(cursor)
        print_report("AFTER AUDIT: SUSPECT VALUES BY SOURCE", after_report)

    conn.close()


if __name__ == '__main__':
    main()
