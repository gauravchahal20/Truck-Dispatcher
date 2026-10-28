# N9b: Authority Gate on Full Pool (312 Stored Carriers) Report

**Generated**: 2026-10-26  
**Evidence Source**: `docs/reports/evidence/n9b.txt`  
**Raw Motus Cache**: `scripts/maintenance/inys_312_audit_results.json`  

---

## 1. Executive Summary

A targeted lookup on the FMCSA Insurance & Authority SODA endpoint (`inys-ebih`) was executed across all **312 stored carriers** (cached, batched). The authority gate rule was applied per specification:

> **N9b Rule Change**:  
> `QUALIFIED` = hard gates pass + Motus property authority `ACTIVE` + `BIPD >= 750,000` + (phone or email present).  
> Score only ranks leads within `QUALIFIED` and no longer blocks it.  
> `FINAL` still requires a verified channel or a human "reached" outcome.

---

## 2. Motus Authority Status Distribution Across All 312 Stored Carriers

*Copied directly from `docs/reports/evidence/n9b.txt`:*

| Authority Status (Motus inys-ebih) | Count | Description / Evidence |
| :--- | :--- | :--- |
| **ACTIVE (Property)** | **86** | Verified active Property Broker/Common/Contract authority with FMCSA |
| **PENDING** | **118** | Authority application filed with FMCSA, awaiting certificate / compliance |
| **WITHDRAWN** | **2** | Authority application dismissed or formally withdrawn |
| **INACTIVE** | **0** | No carriers in inactive revoked state in this sample |
| **NO_LI_RECORD** | **106** | No active or pending docket record in federal L&I dataset |
| **TOTAL** | **312** | **100.0% of Stored Carrier Pool** |

---

## 3. Table 3.1: Lead Status Before vs After (All 312 Stored Carriers)

*Copied verbatim from `docs/reports/evidence/n9b.txt`:*

```
Lead Status            | Before Count | After Count  | Net Change
--------------------------------------------------------------
NEEDS_ENRICHMENT       | 278          | 199          | -79
NEEDS_REVIEW_ICP       | 2            | 2            | +0
NOT_ICP                | 3            | 3            | +0
QUALIFIED              | 0            | 79           | +79
REJECTED               | 29           | 29           | +0
--------------------------------------------------------------
TOTAL                  | 312          | 312          | 0
```

> **Takeaway**: **79 carriers** are immediately **QUALIFIED** and ready to call today with proven active Motus property authority, verified BIPD insurance >= $750,000, and a reachable phone or email channel.

---

## 4. Table 3.2: Score Band (Priority) Before vs After (All 312 Stored Carriers)

*Copied verbatim from `docs/reports/evidence/n9b.txt`:*

```
Priority Band   | Score Range     | Before Count | After Count  | Net Change
------------------------------------------------------------------------
Priority A      | >= 8.0          | 0            | 0            | +0
Priority B      | 6.0 - 7.9       | 2            | 126          | +124
Priority C      | 5.0 - 5.9       | 143          | 100          | -43
Priority NONE   | < 5.0           | 167          | 86           | -81
------------------------------------------------------------------------
TOTAL           | -               | 312          | 312          | 0
```

---

## 5. Forensic Explanation: Why the N3 Before/After Tables Were Identical

In Workstream N3, the qualification logic required **both** active Motus property authority and a fit score threshold of **`score >= 5.0`** before promoting any carrier.

1. Out of the 104 stored carriers sampled in N3, exactly **1 carrier** held active property authority:
   - **SOPHY'S FRUITS COMPANY** (USDOT 2252252, BIPD $750,000).
2. However, under the N3 scoring implementation, SOPHY'S FRUITS had a fit score of **4.2** (< 5.0 threshold). Because 4.2 was below 5.0, it was not promoted.
3. The remaining 20 matched carriers in N3 were either **PENDING** (19 carriers) or **WITHDRAWN** (1 carrier). None held active authority.
4. As a result, exactly **0 carriers** met both criteria simultaneously in N3. Consequently, the before and after counts were 100% identical.
5. Under the N9b rule change, score no longer blocks qualification: SOPHY'S FRUITS is promoted directly into **QUALIFIED**!

---

## 6. Score Breakdown for SOPHY'S FRUITS COMPANY (USDOT 2252252)

*Copied from `docs/reports/evidence/n9b.txt`:*

- **Before N9b**: Status = `NEEDS_ENRICHMENT`, Fit Score = `4.2`, Total Score = `4.2`, Priority = `NONE`
- **After N9b**: Status = `QUALIFIED`, Fit Score = `5.8`, Total Score = `5.8`, Priority = `C`

### Detailed Component Breakdown (After):
1. **Fleet Size (4 Power Units)**: `+2.0 pts` (optimal small fleet range 2–10 units)
2. **Active Property Authority & Active Insurance (FMCSA inys-ebih)**: `+2.0 pts`
3. **Equipment Verified (Refrigerated / Reefer)**: `+1.0 pt`
4. **Usable Contact Channel (Phone Present & E.164 Clean)**: `+0.75 pts`
5. **Decision Maker Attribution (No verified named officer contact row)**: `+0.0 pts`
6. **Total Score**: `5.75 -> 5.8` (Priority C)
7. **Status Outcome**: Promoted from `NEEDS_ENRICHMENT` to **`QUALIFIED`** under N9b rule.

---

## 7. Empirical Split of the 106 NO_LI_RECORD Carriers

*Copied from `docs/reports/evidence/n9b.txt`:*

The 106 carriers without an `inys-ebih` record were audited against their FMCSA MCS-150 census attributes:

| Category | Count | Evidence / Legal Explanation |
| :--- | :--- | :--- |
| **Intrastate Carriers** | **50** | `carrier_operation` is `'B'` (Intrastate Non-Hazmat) or `'C'` (Intrastate Hazmat). Federal FMCSA L&I authority is strictly required for interstate commerce. Intrastate carriers operate under state DOT authorities (e.g. WUTC in WA, CPUC in CA) and do not file federal BMC-91X/inys-ebih. |
| **Exempt For-Hire / Private Carriage** | **19** | `operating_status` contains `'EXEMPT FOR-HIRE'` or `'PRIVATE'`. Private carriers haul their own goods and are exempt from federal commercial operating authority filings. |
| **Interstate For-Hire without Federal L&I Record** | **22** | `carrier_operation` is `'A'` (Interstate), but 0 filing records exist on `inys-ebih`. Empirical evidence confirms no active docket or insurance filing on federal record; no speculative claim of awaiting insurance posting is made without evidence. |
| **Records without USDOT** | **15** | Historical test or shipper entries lacking USDOT identifiers. |
| **TOTAL** | **106** | **100% accounted for with empirical database evidence.** |

---

## 8. Summary of Callable Carriers Today

- **Proven Active Authority + Insured (BIPD >= $750k) + Contact Channel**: **79 Carriers** (Ready to call immediately)
- **Pending Authority**: **118 Carriers** (Queued for daily SODA polling)
- **Withdrawn / Disqualified**: **2 Carriers**
- **Intrastate / Exempt / Pre-filing**: **106 Carriers**
