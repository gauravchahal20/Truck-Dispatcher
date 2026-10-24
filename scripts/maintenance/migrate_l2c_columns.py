import sqlite3

for db_path in ["data/trucklead.db", "data/test_trucklead.db"]:
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    if "companies" not in tables:
        con.close()
        continue

    existing_cols = [c[1] for c in cur.execute("PRAGMA table_info(companies)").fetchall()]

    if "authority_status" not in existing_cols:
        cur.execute("ALTER TABLE companies ADD COLUMN authority_status VARCHAR(50) DEFAULT 'UNKNOWN'")
        print(f"[{db_path}] Added column authority_status")

    if "insurance_filing_status" not in existing_cols:
        cur.execute("ALTER TABLE companies ADD COLUMN insurance_filing_status VARCHAR(50) DEFAULT 'UNKNOWN'")
        print(f"[{db_path}] Added column insurance_filing_status")

    if "authority_status_source" not in existing_cols:
        cur.execute("ALTER TABLE companies ADD COLUMN authority_status_source VARCHAR(50)")
        print(f"[{db_path}] Added column authority_status_source")

    cur.execute("CREATE INDEX IF NOT EXISTS ix_companies_authority_status ON companies (authority_status)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_companies_authority_status_source ON companies (authority_status_source)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_companies_insurance_filing_status ON companies (insurance_filing_status)")

    con.commit()
    con.close()
    print(f"[{db_path}] Migration completed.")
