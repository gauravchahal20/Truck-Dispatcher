#!/usr/bin/env python3
"""
Carrier Deduplication and Survivorship Merging (Workstream H1)

1. Identifies duplicate motor carriers by USDOT.
2. Applies survivorship ranking to select the best-verified record.
3. Merges child records (contacts, outcomes, sources, signals, history).
4. Merges field-level provenance and DNC/suppression flags.
5. Deletes redundant loser company rows.
6. Writes an audit trail to data/merge_log.jsonl.
7. Applies partial unique index on companies(usdot) for carriers.
"""

import os
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/trucklead.db")
LOG_PATH = Path("data/merge_log.jsonl")


def calculate_survivorship_score(row: dict, contact_count: int, outcome_count: int) -> float:
    score = 0.0

    # 1. Status weight
    status = (row.get("lead_status") or "").upper()
    if status == "FINAL":
        score += 400.0
    elif status == "QUALIFIED":
        score += 300.0
    elif status == "NEEDS_ENRICHMENT":
        score += 200.0
    elif status == "REJECTED":
        score += 100.0

    # 2. Verification status
    v_stat = (row.get("verification_status") or "").upper()
    if v_stat == "VERIFIED":
        score += 50.0
    elif v_stat == "PARTIALLY_VERIFIED":
        score += 25.0

    # 3. Phone verification
    p_stat = (row.get("phone_verification_status") or "").upper()
    if p_stat == "VERIFIED":
        score += 50.0
    elif p_stat == "CORROBORATED":
        score += 30.0
    elif p_stat == "FORMAT_OK":
        score += 10.0

    # 4. Email verification
    e_stat = (row.get("email_verification_status") or "").upper()
    if e_stat == "DELIVERABLE":
        score += 50.0
    elif e_stat == "DOMAIN_OK":
        score += 30.0
    elif e_stat == "SYNTAX_OK":
        score += 10.0

    # 5. Lead score & confidence
    score += float(row.get("lead_score") or 0.0) * 10.0
    score += float(row.get("verification_confidence") or 0.0) * 20.0

    # 6. Child entities attached
    score += contact_count * 15.0
    score += outcome_count * 50.0

    return score


def deduplicate_carriers(dry_run: bool = False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT usdot, COUNT(*) as c
        FROM companies
        WHERE usdot IS NOT NULL AND TRIM(usdot) != '' AND UPPER(lead_type) = 'CARRIER'
        GROUP BY usdot
        HAVING c > 1
    """)
    dup_clusters = cur.fetchall()
    print(f"Found {len(dup_clusters)} duplicate carrier USDOT clusters.")

    total_merged = 0
    total_losers_removed = 0
    merge_logs = []

    for cluster in dup_clusters:
        dot = cluster["usdot"]
        cur.execute("SELECT * FROM companies WHERE usdot = ? ORDER BY created_at ASC", (dot,))
        rows = [dict(r) for r in cur.fetchall()]

        # Rank records
        ranked = []
        for r in rows:
            cid = r["id"]
            cur.execute("SELECT COUNT(*) FROM contacts WHERE company_id = ?", (cid,))
            c_cnt = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM lead_outcomes WHERE company_id = ?", (cid,))
            o_cnt = cur.fetchone()[0]
            surv_score = calculate_survivorship_score(r, c_cnt, o_cnt)
            ranked.append((surv_score, r, c_cnt, o_cnt))

        # Highest score is survivor
        ranked.sort(key=lambda x: x[0], reverse=True)
        survivor_score, survivor, s_contacts, s_outcomes = ranked[0]
        losers = [x[1] for x in ranked[1:]]
        loser_ids = [l["id"] for l in losers]

        fields_backfilled = []

        # Merge suppression flags
        any_dnc = survivor.get("dnc_flag") or any(l.get("dnc_flag") for l in losers)
        supp_reason = survivor.get("suppression_reason") or next((l.get("suppression_reason") for l in losers if l.get("suppression_reason")), None)

        # Merge field provenance
        try:
            s_prov = json.loads(survivor.get("field_provenance") or "{}")
        except Exception:
            s_prov = {}

        for l in losers:
            try:
                l_prov = json.loads(l.get("field_provenance") or "{}")
                for k, v in l_prov.items():
                    if k not in s_prov:
                        s_prov[k] = v
            except Exception:
                pass

        # Backfill empty fields on survivor
        backfill_candidates = [
            "phone_e164", "phone_display", "phone_line_type", "phone_carrier_name",
            "phone_verification_status", "phone_verification_provider", "local_timezone",
            "call_window_local", "call_window_ist", "email", "email_verification_status",
            "email_mx_valid", "email_role_tier", "mc_number", "legal_name", "dba_name",
            "equipment", "fleet_size", "driver_count", "carrier_operation", "safety_rating",
            "operating_status", "address", "city", "state", "zip_code"
        ]

        updates = {}
        for field in backfill_candidates:
            if not survivor.get(field):
                for l in losers:
                    if l.get(field):
                        updates[field] = l[field]
                        fields_backfilled.append(field)
                        break

        if any_dnc != survivor.get("dnc_flag"):
            updates["dnc_flag"] = 1 if any_dnc else 0
        if supp_reason and supp_reason != survivor.get("suppression_reason"):
            updates["suppression_reason"] = supp_reason
        updates["field_provenance"] = json.dumps(s_prov)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "usdot": dot,
            "company_name": survivor.get("company_name"),
            "survivor_id": survivor["id"],
            "survivor_score": survivor_score,
            "loser_ids": loser_ids,
            "loser_count": len(loser_ids),
            "fields_backfilled": fields_backfilled,
            "suppression_merged": bool(any_dnc)
        }
        merge_logs.append(log_entry)

        if not dry_run:
            # 1. Update survivor
            set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
            cur.execute(f"UPDATE companies SET {set_clause} WHERE id = ?", list(updates.values()) + [survivor["id"]])

            # 2. Re-parent contacts
            for lid in loser_ids:
                cur.execute("UPDATE contacts SET company_id = ? WHERE company_id = ?", (survivor["id"], lid))
                cur.execute("UPDATE lead_outcomes SET company_id = ? WHERE company_id = ?", (survivor["id"], lid))
                cur.execute("UPDATE sources SET company_id = ? WHERE company_id = ?", (survivor["id"], lid))
                cur.execute("UPDATE verification_records SET company_id = ? WHERE company_id = ?", (survivor["id"], lid))
                cur.execute("UPDATE intent_signals SET company_id = ? WHERE company_id = ?", (survivor["id"], lid))
                cur.execute("UPDATE lead_status_history SET company_id = ? WHERE company_id = ?", (survivor["id"], lid))
                cur.execute("DELETE FROM lead_scores WHERE company_id = ?", (lid,))

            # 3. Deduplicate contacts on survivor
            cur.execute("""
                SELECT id, LOWER(TRIM(full_name)), LOWER(TRIM(COALESCE(email, ''))), COALESCE(phone_e164, '')
                FROM contacts
                WHERE company_id = ?
            """, (survivor["id"],))
            seen_contacts = set()
            dup_contact_ids = []
            for c_id, fn, em, ph in cur.fetchall():
                key = (fn, em, ph)
                if key in seen_contacts:
                    dup_contact_ids.append(c_id)
                else:
                    seen_contacts.add(key)
            for dcid in dup_contact_ids:
                cur.execute("DELETE FROM contacts WHERE id = ?", (dcid,))

            # 4. Delete loser company records
            placeholders = ", ".join("?" for _ in loser_ids)
            cur.execute(f"DELETE FROM companies WHERE id IN ({placeholders})", loser_ids)

        total_merged += 1
        total_losers_removed += len(loser_ids)

    if not dry_run:
        # Enforce partial unique index
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_carrier_usdot
            ON companies (usdot)
            WHERE usdot IS NOT NULL AND TRIM(usdot) != '' AND UPPER(lead_type) = 'CARRIER';
        """)
        conn.commit()

        # Write merge log
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            for entry in merge_logs:
                f.write(json.dumps(entry) + "\n")
        print(f"Wrote {len(merge_logs)} merge records to {LOG_PATH}")

    # Summary
    cur.execute("SELECT COUNT(*) FROM companies WHERE UPPER(lead_type) = 'CARRIER'")
    final_carriers = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM companies WHERE UPPER(lead_type) = 'SHIPPER'")
    final_shippers = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM companies")
    final_total = cur.fetchone()[0]

    print("\n=== DEDUPLICATION COMPLETE ===")
    print(f"Clusters processed: {total_merged}")
    print(f"Redundant rows removed: {total_losers_removed}")
    print(f"Remaining carriers: {final_carriers}")
    print(f"Remaining shippers: {final_shippers}")
    print(f"True unique leads in database: {final_total}")

    conn.close()


if __name__ == "__main__":
    deduplicate_carriers(dry_run=False)
