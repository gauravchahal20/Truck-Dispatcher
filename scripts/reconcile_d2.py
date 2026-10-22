import sqlite3
import json

conn = sqlite3.connect("trucklead.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("="*60)
print("D2. RECONCILED ROW COUNTS")
print("="*60)

c.execute("SELECT count(*) FROM companies")
total_companies = c.fetchone()[0]
print(f"Total Companies in trucklead.db: {total_companies}")

# Remediate shippers operating_status (Authority is N/A for shippers)
c.execute("UPDATE companies SET operating_status = NULL, safety_rating = NULL WHERE lead_type = 'SHIPPER'")
conn.commit()

print("\n1. Row Counts by lead_type:")
c.execute("SELECT coalesce(lead_type, 'NULL'), count(*) FROM companies GROUP BY lead_type")
for r in c.fetchall():
    print(f"   {r[0]:<15}: {r[1]}")

print("\n2. Row Counts by lead_source:")
c.execute("SELECT coalesce(lead_source, 'NULL'), count(*) FROM companies GROUP BY lead_source")
for r in c.fetchall():
    print(f"   {r[0]:<25}: {r[1]}")

print("\n3. Row Counts by run_id:")
c.execute("SELECT coalesce(run_id, 'NULL (Legacy pre-run / standalone)'), count(*) FROM companies GROUP BY run_id")
for r in c.fetchall():
    print(f"   {r[0]:<40}: {r[1]}")

print("\n4. Carriers vs Shippers Contact & Authority Metrics:")
# Carriers
c.execute("""
    SELECT 
        count(*) as total,
        sum(case when phone is not null and phone != '' then 1 else 0 end) as with_phone,
        sum(case when email is not null and email != '' then 1 else 0 end) as with_email,
        sum(case when operating_status in ('ACTIVE', 'AUTHORIZED FOR HIRE', 'AUTHORIZED FOR Property') then 1 else 0 end) as active_auth,
        sum(case when lead_source in ('fmcsa_official', 'fmcsa_safer', 'fmcsa_li') then 1 else 0 end) as official_source
    FROM companies
    WHERE lead_type = 'CARRIER' or lead_type is null
""")
carrier_stats = c.fetchone()
print(f"   CARRIERS (Denominator = {carrier_stats['total']}):")
print(f"     Phone:           {carrier_stats['with_phone']} / {carrier_stats['total']} ({carrier_stats['with_phone']/carrier_stats['total']*100:.1f}%)")
print(f"     Email:           {carrier_stats['with_email']} / {carrier_stats['total']} ({carrier_stats['with_email']/carrier_stats['total']*100:.1f}%)")
print(f"     Active Authority:{carrier_stats['active_auth']} / {carrier_stats['total']} ({carrier_stats['active_auth']/carrier_stats['total']*100:.1f}%)")
print(f"     Official Source: {carrier_stats['official_source']} / {carrier_stats['total']} ({carrier_stats['official_source']/carrier_stats['total']*100:.1f}%)")

# Shippers
c.execute("""
    SELECT 
        count(*) as total,
        sum(case when phone is not null and phone != '' then 1 else 0 end) as with_phone,
        sum(case when email is not null and email != '' then 1 else 0 end) as with_email,
        sum(case when operating_status is not null then 1 else 0 end) as with_auth_status,
        sum(case when operating_status in ('ACTIVE', 'AUTHORIZED FOR HIRE') then 1 else 0 end) as active_auth
    FROM companies
    WHERE lead_type = 'SHIPPER'
""")
shipper_stats = c.fetchone()
print(f"\n   SHIPPERS (Denominator = {shipper_stats['total']}):")
print(f"     Phone:           {shipper_stats['with_phone']} / {shipper_stats['total']} ({shipper_stats['with_phone']/shipper_stats['total']*100:.1f}%)")
print(f"     Email:           {shipper_stats['with_email']} / {shipper_stats['total']} ({shipper_stats['with_email']/shipper_stats['total']*100:.1f}%)")
print(f"     Auth Status Set: {shipper_stats['with_auth_status']} / {shipper_stats['total']} (Expected 0 - Authority is N/A for shippers)")
print(f"     Active Auth:     {shipper_stats['active_auth']} / {shipper_stats['total']}")

print("\n5. Step D Standardized Benchmark Run (Run ID: 33dcf26c-c9e6-4a2e-bbd7-525622a0dd27):")
c.execute("""
    SELECT 
        count(*) as total,
        sum(case when lead_type = 'CARRIER' then 1 else 0 end) as carrier_count,
        sum(case when lead_type = 'SHIPPER' then 1 else 0 end) as shipper_count,
        sum(case when phone is not null and phone != '' then 1 else 0 end) as with_phone,
        sum(case when email is not null and email != '' then 1 else 0 end) as with_email,
        sum(case when lead_source in ('fmcsa_official', 'fmcsa_safer', 'fmcsa_li') then 1 else 0 end) as official_source,
        sum(case when operating_status in ('ACTIVE', 'AUTHORIZED FOR HIRE') and lead_type = 'CARRIER' then 1 else 0 end) as carrier_active_auth
    FROM companies
    WHERE run_id = '33dcf26c-c9e6-4a2e-bbd7-525622a0dd27'
""")
run_d = c.fetchone()
print(f"   Total Stored in Run D: {run_d['total']}")
print(f"     Carriers: {run_d['carrier_count']} | Shippers: {run_d['shipper_count']}")
print(f"     Official Source: {run_d['official_source']} / {run_d['total']} ({run_d['official_source']/run_d['total']*100:.1f}% overall, {run_d['official_source']/run_d['carrier_count']*100:.1f}% on carriers)")
print(f"     Valid Phone:     {run_d['with_phone']} / {run_d['total']} ({run_d['with_phone']/run_d['total']*100:.1f}%)")
print(f"     Valid Email:     {run_d['with_email']} / {run_d['total']} ({run_d['with_email']/run_d['total']*100:.1f}%)")
print(f"     Active Authority on Carriers: {run_d['carrier_active_auth']} / {run_d['carrier_count']} ({run_d['carrier_active_auth']/run_d['carrier_count']*100:.1f}%)")

print("\n6. Single SQL Query for Score Distribution & Tiers across Current DB:")
c.execute("""
    SELECT 
        case 
            when lead_score is null then 'None'
            when lead_score < 3.0 then '0.0 - 2.9'
            when lead_score < 5.0 then '3.0 - 4.9'
            when lead_score < 6.0 then '5.0 - 5.9'
            when lead_score < 8.0 then '6.0 - 7.9'
            else '8.0 - 10.0'
        end as score_bucket,
        coalesce(priority, 'None') as tier,
        count(*) as lead_count,
        round(avg(lead_score), 2) as avg_score
    FROM companies
    GROUP BY score_bucket, tier
    ORDER BY min(coalesce(lead_score, 0)) ASC
""")
rows = c.fetchall()
print(f"   {'Score Bucket':<15} | {'Tier':<10} | {'Count':<6} | {'Avg Score'}")
print("   " + "-"*45)
for r in rows:
    print(f"   {r['score_bucket']:<15} | {r['tier']:<10} | {r['lead_count']:<6} | {r['avg_score']}")

conn.close()
