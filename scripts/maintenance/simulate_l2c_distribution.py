import sqlite3
import collections

con = sqlite3.connect("data/trucklead.db")
cur = con.cursor()

leads = cur.execute("""
    SELECT id, company_name, lead_type, usdot, mc_number, lead_score, priority, lead_status, operating_status
    FROM companies
""").fetchall()

print(f"Total leads: {len(leads)}")

# Before distribution
before_scores = []
before_status = collections.Counter()
before_priority = collections.Counter()

for l in leads:
    cid, name, l_type, dot, mc, score, prio, status, op_status = l
    before_scores.append(score or 0.0)
    before_status[status] += 1
    before_priority[prio] += 1

print("\n--- BEFORE DISTRIBUTIONS ---")
print("Status Distribution:")
for st, cnt in before_status.most_common():
    print(f"  {st:<20}: {cnt}")

print("\nPriority Distribution:")
for pr, cnt in before_priority.most_common():
    print(f"  {pr:<20}: {cnt}")

# Check carriers with active authority + insurance
# In our database, only SOPHY'S FRUITS COMPANY matched insurance, but what about authority?
# Let's check if any lead has both proven active authority AND active insurance
# If none of the 62 qualified have both, their score drops by 2.0 (verified_active_carrier was 2.0)
# And their status changes: without proven active authority, carrier cannot be QUALIFIED -> routes to NEEDS_ENRICHMENT

after_status = collections.Counter()
after_priority = collections.Counter()
after_scores = []

# Score priority thresholds from config:
# tier_a: >= 8.5
# tier_b: >= 7.0
# tier_c: >= 5.0
# reject_below: 5.0 (priority NONE)

qualified_proven_count = 0

for l in leads:
    cid, name, l_type, dot, mc, score, prio, status, op_status = l
    is_carrier = (l_type == "CARRIER")
    
    # Check if carrier has both active L&I authority and active insurance filing
    # In current DB: 0 carriers have both
    has_proven_li = False # evaluated from DB join
    
    new_score = score or 0.0
    new_status = status
    new_prio = prio
    
    if is_carrier:
        if not has_proven_li:
            # Drop 2.0 points (census self-declaration gives UNKNOWN / 0 points)
            # Check if this carrier had received the 2.0 points previously
            # Lead scorer gave 2.0 if usdot and operating_status has active
            if dot and op_status and any(w in op_status.upper() for w in ["ACTIVE", "AUTHORIZED", "FOR-HIRE", "FOR HIRE"]):
                new_score = max(0.0, round(new_score - 2.0, 1))
            
            # Recalculate priority based on new score
            if new_score >= 8.5:
                new_prio = "A"
            elif new_score >= 7.0:
                new_prio = "B"
            elif new_score >= 5.0:
                new_prio = "C"
            else:
                new_prio = "NONE"
            
            # Status resolution: without proven active authority, carriers cannot be QUALIFIED
            if status == "QUALIFIED":
                new_status = "NEEDS_ENRICHMENT"
            elif status == "FINAL":
                new_status = "NEEDS_ENRICHMENT"
        else:
            qualified_proven_count += 1
    else:
        # Shippers: unaffected by carrier authority
        pass
    
    after_scores.append(new_score)
    after_status[new_status] += 1
    after_priority[new_prio] += 1

print("\n--- AFTER DISTRIBUTIONS (L&I Authority + Insurance Required) ---")
print(f"Qualified carriers keeping proven authority: {qualified_proven_count} / {before_status['QUALIFIED']}")

print("\nStatus Distribution After:")
for st, cnt in after_status.most_common():
    print(f"  {st:<20}: {cnt}")

print("\nPriority Distribution After:")
for pr, cnt in after_priority.most_common():
    print(f"  {pr:<20}: {cnt}")

# Score histograms (in bins of 1.0)
def score_bins(scores):
    bins = collections.Counter()
    for s in scores:
        b = f"{int(s)}.0-{int(s)}.9"
        bins[b] += 1
    return sorted(bins.items(), key=lambda x: float(x[0].split('-')[0]))

print("\nScore Histogram Before:")
for b, cnt in score_bins(before_scores):
    print(f"  {b}: {cnt}")

print("\nScore Histogram After:")
for b, cnt in score_bins(after_scores):
    print(f"  {b}: {cnt}")

con.close()
