import sqlite3

con = sqlite3.connect("data/trucklead.db")
cur = con.cursor()

existing_cols = [c[1] for c in cur.execute("PRAGMA table_info(companies)").fetchall()]

if "authority_status" not in existing_cols:
    cur.execute("ALTER TABLE companies ADD COLUMN authority_status VARCHAR(50) DEFAULT 'UNKNOWN'")
    print("Added column authority_status")
else:
    print("authority_status already exists")

if "insurance_filing_status" not in existing_cols:
    cur.execute("ALTER TABLE companies ADD COLUMN insurance_filing_status VARCHAR(50) DEFAULT 'UNKNOWN'")
    print("Added column insurance_filing_status")
else:
    print("insurance_filing_status already exists")

cur.execute("CREATE INDEX IF NOT EXISTS ix_companies_authority_status ON companies (authority_status)")
cur.execute("CREATE INDEX IF NOT EXISTS ix_companies_insurance_filing_status ON companies (insurance_filing_status)")

con.commit()
con.close()
print("Migration completed.")
