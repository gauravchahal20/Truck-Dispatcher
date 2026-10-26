import sqlite3

con = sqlite3.connect("data/trucklead.db")
cur = con.cursor()

print("--- MIGRATING INVALID PRIORITIES TO NONE ---")
# 1. Inspect before
before_rows = cur.execute("""
    SELECT id, company_name, lead_status, priority, lead_score
    FROM companies
    WHERE lead_status IN ('REJECTED', 'NOT_ICP', 'NEEDS_REVIEW_ICP', 'ARCHIVED_NO_CONTACT')
      AND priority != 'NONE'
""").fetchall()

print(f"Companies to fix: {len(before_rows)}")
for r in before_rows:
    print(f"  {r[0]}: {r[1]} (Status: {r[2]}, Old Priority: {r[3]}, Score: {r[4]})")

# 2. Update companies
cur.execute("""
    UPDATE companies
    SET priority = 'NONE'
    WHERE lead_status IN ('REJECTED', 'NOT_ICP', 'NEEDS_REVIEW_ICP', 'ARCHIVED_NO_CONTACT')
      AND priority != 'NONE'
""")
updated_companies = cur.rowcount
print(f"Updated {updated_companies} companies to priority = 'NONE'")

# 3. Update lead_scores
cur.execute("""
    UPDATE lead_scores
    SET priority = 'NONE'
    WHERE company_id IN (
        SELECT id FROM companies
        WHERE lead_status IN ('REJECTED', 'NOT_ICP', 'NEEDS_REVIEW_ICP', 'ARCHIVED_NO_CONTACT')
    ) AND priority != 'NONE'
""")
updated_scores = cur.rowcount
print(f"Updated {updated_scores} lead_scores to priority = 'NONE'")

con.commit()

# 4. Verify after
remaining = cur.execute("""
    SELECT count(*)
    FROM companies
    WHERE lead_status IN ('REJECTED', 'NOT_ICP', 'NEEDS_REVIEW_ICP', 'ARCHIVED_NO_CONTACT')
      AND priority != 'NONE'
""").fetchone()[0]

print(f"Remaining non-NONE priority leads in those statuses: {remaining}")
assert remaining == 0, "Migration failed: remaining invalid priorities found!"

con.close()
print("Migration successful.")
