import sqlite3
import json

con = sqlite3.connect("data/trucklead.db")
cur = con.cursor()

# Find the 62 QUALIFIED carriers
qualified = cur.execute("""
    SELECT c.id, c.company_name, c.usdot, c.mc_number, c.lead_score, c.priority, c.lead_status, c.operating_status
    FROM companies c
    WHERE c.lead_status = 'QUALIFIED'
""").fetchall()

print(f"Total currently QUALIFIED carriers: {len(qualified)}")

# Check how many have matches in fmcsa_authority_history and fmcsa_insurance_active_pending
auth_hist_dots = set(r[0] for r in cur.execute("SELECT DISTINCT dot_number FROM fmcsa_authority_history WHERE dot_number IS NOT NULL").fetchall())
auth_hist_dockets = set(r[0] for r in cur.execute("SELECT DISTINCT docket_number FROM fmcsa_authority_history WHERE docket_number IS NOT NULL").fetchall())

insur_dots = set(r[0] for r in cur.execute("SELECT DISTINCT dot_number FROM fmcsa_insurance_active_pending WHERE dot_number IS NOT NULL").fetchall())
insur_dockets = set(r[0] for r in cur.execute("SELECT DISTINCT docket_number FROM fmcsa_insurance_active_pending WHERE docket_number IS NOT NULL").fetchall())

print(f"Unique DOTs in fmcsa_authority_history: {len(auth_hist_dots)}, dockets: {len(auth_hist_dockets)}")
print(f"Unique DOTs in fmcsa_insurance_active_pending: {len(insur_dots)}, dockets: {len(insur_dockets)}")

matched_both = []
matched_auth_only = []
matched_insur_only = []
matched_neither = []

for q in qualified:
    cid, name, usdot, mc, score, prio, st, op_st = q
    dot_str = str(usdot) if usdot else ""
    mc_str = str(mc) if mc else ""
    
    has_auth = (dot_str in auth_hist_dots) or (mc_str in auth_hist_dockets)
    has_insur = (dot_str in insur_dots) or (mc_str in insur_dockets)
    
    if has_auth and has_insur:
        matched_both.append(q)
    elif has_auth:
        matched_auth_only.append(q)
    elif has_insur:
        matched_insur_only.append(q)
    else:
        matched_neither.append(q)

print(f"\nAmong the {len(qualified)} QUALIFIED carriers (local mirror matches):")
print(f"  Matched BOTH authority history & active insurance: {len(matched_both)}")
print(f"  Matched authority history ONLY: {len(matched_auth_only)}")
print(f"  Matched active insurance ONLY: {len(matched_insur_only)}")
print(f"  Matched NEITHER: {len(matched_neither)}")

if matched_both:
    print("\nSample Matched Both:")
    for m in matched_both[:5]:
        print(f"  {m[1]} (DOT: {m[2]}, MC: {m[3]}) - Score: {m[4]}, Priority: {m[5]}")

if matched_auth_only:
    print("\nSample Matched Auth Only:")
    for m in matched_auth_only[:5]:
        print(f"  {m[1]} (DOT: {m[2]}, MC: {m[3]}) - Score: {m[4]}, Priority: {m[5]}")

if matched_insur_only:
    print("\nSample Matched Insurance Only:")
    for m in matched_insur_only[:5]:
        print(f"  {m[1]} (DOT: {m[2]}, MC: {m[3]}) - Score: {m[4]}, Priority: {m[5]}")

con.close()
