import sqlite3

def audit_qualified_transitions():
    con = sqlite3.connect("data/trucklead.db")
    cur = con.cursor()

    print("Transitions to QUALIFIED in lead_status_history:")
    rows = cur.execute("""
        SELECT h.company_id, c.company_name, c.lead_type, c.lead_status, h.from_status, h.to_status, h.reason, h.changed_at
        FROM lead_status_history h
        JOIN companies c ON h.company_id = c.id
        WHERE h.to_status = 'QUALIFIED'
    """).fetchall()

    print(f"Total rows where to_status = 'QUALIFIED': {len(rows)}")
    company_ids = set(r[0] for r in rows)
    print(f"Unique company_ids: {len(company_ids)}")

    by_lead_type = {}
    for r in rows:
        ltype = r[2]
        by_lead_type[ltype] = by_lead_type.get(ltype, 0) + 1
    print(f"By lead_type: {by_lead_type}")

    # Distinct companies by lead_type
    distinct_by_type = cur.execute("""
        SELECT c.lead_type, count(distinct h.company_id)
        FROM lead_status_history h
        JOIN companies c ON h.company_id = c.id
        WHERE h.to_status = 'QUALIFIED'
        GROUP BY c.lead_type
    """).fetchall()
    print(f"Distinct companies ever transitioned to QUALIFIED by type: {distinct_by_type}")

    # What about current status of companies?
    current_status = cur.execute("""
        SELECT c.lead_type, c.lead_status, count(*)
        FROM companies c
        WHERE c.id IN (SELECT company_id FROM lead_status_history WHERE to_status = 'QUALIFIED')
        GROUP BY c.lead_type, c.lead_status
    """).fetchall()
    print(f"Current status of companies ever transitioned to QUALIFIED: {current_status}")

    # Check shipper claim
    shippers = cur.execute("SELECT id, company_name, lead_status FROM companies WHERE lead_type = 'SHIPPER'").fetchall()
    print(f"\nShippers in companies table ({len(shippers)}):")
    for s in shippers:
        print(f"  {s}")

    con.close()

if __name__ == "__main__":
    audit_qualified_transitions()
