import sqlite3

conn = sqlite3.connect('trucklead.db')
c = conn.cursor()

print("1. Companies count by lead_type:")
for r in c.execute("SELECT lead_type, COUNT(*) FROM companies GROUP BY lead_type").fetchall():
    print(" ", r)

print("\n2. Contacts count by lead_type of company:")
for r in c.execute("SELECT c.lead_type, COUNT(ct.id) FROM contacts ct JOIN companies c ON ct.company_id = c.id GROUP BY c.lead_type").fetchall():
    print(" ", r)

print("\n3. Companies LEFT JOIN contacts row count:")
for r in c.execute("SELECT c.lead_type, COUNT(*) FROM companies c LEFT JOIN contacts ct ON ct.company_id = c.id GROUP BY c.lead_type").fetchall():
    print(" ", r)

print("\n4. Distinct company_id in contacts:")
print("  Distinct company_ids in contacts:", c.execute("SELECT COUNT(DISTINCT company_id) FROM contacts").fetchone()[0])

print("\n5. Companies with contacts count distribution:")
for r in c.execute("SELECT cnt, COUNT(*) FROM (SELECT c.id, COUNT(ct.id) as cnt FROM companies c LEFT JOIN contacts ct ON ct.company_id = c.id GROUP BY c.id) GROUP BY cnt").fetchall():
    print(f"  Companies with {r[0]} contacts: {r[1]}")

print("\n6. Phone counts in companies:")
for r in c.execute("""
    SELECT lead_type, 
           COUNT(*) as total,
           COUNT(phone) as has_phone,
           COUNT(phone_e164) as has_e164,
           SUM(CASE WHEN phone IS NOT NULL AND phone != '' THEN 1 ELSE 0 END) as non_empty_phone,
           SUM(CASE WHEN phone_e164 IS NOT NULL AND phone_e164 != '' THEN 1 ELSE 0 END) as non_empty_e164
    FROM companies
    GROUP BY lead_type
""").fetchall():
    print(" ", r)

print("\n7. Phone counts in contacts:")
for r in c.execute("""
    SELECT c.lead_type,
           COUNT(ct.id) as total_contacts,
           SUM(CASE WHEN ct.phone IS NOT NULL AND ct.phone != '' THEN 1 ELSE 0 END) as non_empty_contact_phone,
           SUM(CASE WHEN ct.phone_e164 IS NOT NULL AND ct.phone_e164 != '' THEN 1 ELSE 0 END) as non_empty_contact_e164
    FROM contacts ct
    JOIN companies c ON ct.company_id = c.id
    GROUP BY c.lead_type
""").fetchall():
    print(" ", r)

conn.close()
