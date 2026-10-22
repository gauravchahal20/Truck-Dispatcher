import sqlite3

conn = sqlite3.connect('trucklead.db')
c = conn.cursor()

sql = '''
SELECT 
    lead_type,
    lead_status,
    CASE 
        WHEN lead_score >= 8.0 THEN '8.0-10.0 (Tier A)'
        WHEN lead_score >= 6.0 THEN '6.0-7.9 (Tier B)'
        WHEN lead_score >= 5.0 THEN '5.0-5.9 (Tier C)'
        ELSE '< 5.0 (Below 5.0)'
    END as score_bucket,
    priority,
    count(*) as lead_count
FROM companies
GROUP BY lead_type, lead_status, score_bucket, priority
ORDER BY lead_type, lead_status, score_bucket;
'''
rows = c.execute(sql).fetchall()

header = f"{'LEAD_TYPE':<10} | {'STATUS':<18} | {'SCORE_BUCKET':<18} | {'PRIORITY':<10} | {'COUNT':<6}"
print(header)
print("-" * len(header))
total = 0
for r in rows:
    print(f"{r[0]:<10} | {r[1]:<18} | {r[2]:<18} | {r[3]:<10} | {r[4]:<6}")
    total += r[4]
print("-" * len(header))
print(f"{'TOTAL':<52} | {total:<6}")
