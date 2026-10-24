import sqlite3

con = sqlite3.connect("data/trucklead.db")
cur = con.cursor()

statuses = [r[0] for r in cur.execute("SELECT DISTINCT lead_status FROM companies ORDER BY lead_status").fetchall()]
tiers = ["A", "B", "C", "NONE"]

print("### Status x Priority Cross-Tabulation (All 209 Stored Companies)")
print("| Lead Lifecycle Status | Priority A | Priority B | Priority C | Priority NONE | Total |")
print("| :--- | :---: | :---: | :---: | :---: | :---: |")

for st in statuses:
    row_counts = []
    total_st = 0
    for t in tiers:
        cnt = cur.execute("SELECT COUNT(*) FROM companies WHERE lead_status = ? AND COALESCE(priority, 'NONE') = ?", (st, t)).fetchone()[0]
        row_counts.append(cnt)
        total_st += cnt
    print(f"| `{st}` | {row_counts[0]} | {row_counts[1]} | {row_counts[2]} | {row_counts[3]} | **{total_st}** |")

col_totals = [cur.execute("SELECT COUNT(*) FROM companies WHERE COALESCE(priority, 'NONE') = ?", (t,)).fetchone()[0] for t in tiers]
print(f"| **Total** | **{col_totals[0]}** | **{col_totals[1]}** | **{col_totals[2]}** | **{col_totals[3]}** | **{sum(col_totals)}** |")

print("\n### Status x Priority Cross-Tabulation (119 Stored Carriers Only)")
print("| Lead Lifecycle Status | Priority A | Priority B | Priority C | Priority NONE | Total |")
print("| :--- | :---: | :---: | :---: | :---: | :---: |")

for st in statuses:
    row_counts = []
    total_st = 0
    for t in tiers:
        cnt = cur.execute("SELECT COUNT(*) FROM companies WHERE lead_type = 'CARRIER' AND lead_status = ? AND COALESCE(priority, 'NONE') = ?", (st, t)).fetchone()[0]
        row_counts.append(cnt)
        total_st += cnt
    if total_st > 0:
        print(f"| `{st}` | {row_counts[0]} | {row_counts[1]} | {row_counts[2]} | {row_counts[3]} | **{total_st}** |")

col_carrier_totals = [cur.execute("SELECT COUNT(*) FROM companies WHERE lead_type = 'CARRIER' AND COALESCE(priority, 'NONE') = ?", (t,)).fetchone()[0] for t in tiers]
print(f"| **Total** | **{col_carrier_totals[0]}** | **{col_carrier_totals[1]}** | **{col_carrier_totals[2]}** | **{col_carrier_totals[3]}** | **{sum(col_carrier_totals)}** |")
