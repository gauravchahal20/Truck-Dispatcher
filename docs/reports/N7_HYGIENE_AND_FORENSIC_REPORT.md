# N7: Pipeline Hygiene, Forensic Reconciliation & Git Audit Report

## 1. Feature Relabeling: L2d, L2e, and L2h
To ensure absolute clarity across pipeline documentation, the data hygiene validation features introduced in Workstream L are officially defined and relabeled as follows:

| Code Label | Canonical Feature Name | Database Column | Detection Logic & Domain Definition | Operational Treatment |
| :--- | :--- | :--- | :--- | :--- |
| **L2d** | **Phone Region Domicile Mismatch** | `phone_region_mismatch` (BOOLEAN) | Compares the 3-digit telephone area code against the carrier's registered physical state (per NANP mapping in `Normalizer.get_state_for_phone()`). Flagged `True` when phone state differs from domicile state. | Soft sanity flag: -0.5 fit score penalty; highlighted in Verify-and-Call queue for operator awareness; never auto-rejected. |
| **L2e** | **Fleet Ratio Inconsistency** | `fleet_inconsistent` (BOOLEAN) | Compares power units (`power_units`) to declared commercial drivers (`total_drivers`). Flagged `True` if `max(pu, drv) / min(pu, drv) > 3.0` or if `pu >= 5` with `0` drivers. | Soft sanity flag: -1.0 fit score penalty; highlighted in Verify-and-Call queue for operator fleet sizing inquiry. |
| **L2h** | **Hazardous Materials Indicator** | `hazmat_carrier` (BOOLEAN) | Checks census `hm_ind == 'Y'` or hazardous materials cargo classifications. | Flagged in queue; excluded by default from small-carrier dry freight dispatch workflows. |

---

## 2. Phone Region Mismatch Counts

### Table 2.1: Phone Area Code vs Domicile State Mismatch Comparison
| Cohort | Total Records | Area Code Matched / Clean | Area Code Mismatched | Mismatch % | Top Mismatched State Pairs |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Stored Carriers Pool** | **312** | **251** | **61** | **19.6%** | WA vs GA, TX vs GA, CA vs IL, NJ vs IL |
| **Watchlist Candidates** | **23** | **17** | **6** | **26.1%** | TX vs GA (2), WA vs GA (1), CA vs IL (1), NJ vs IL (1), WA vs IL (1) |

### Stored Carriers Mismatch Breakdown by Lead Status:
- `NEEDS_ENRICHMENT`: 57 mismatches out of 278 carriers (20.5%)
- `REJECTED`: 4 mismatches out of 29 carriers (13.8%)
- `NEEDS_REVIEW_ICP`: 0 mismatches out of 2 carriers (0.0%)
- `NOT_ICP`: 0 mismatches out of 3 carriers (0.0%)

---

## 3. The "61 vs 62" Qualified Question (Closed & Dropped)

> **Status**: **Officially Dropped & Closed** (Workstream N9f).  
> The historical discrepancy is resolved and retired: exactly **62 unique shippers** reached `QUALIFIED` in `lead_status_history`, while **61** referred to the historical raw carrier candidate cohort prior to suppression deduplication (which yielded 56 qualified carriers). The inquiry is closed.

---

## 4. Git Tags & Commit Author Timestamp Audit

### Exact Output of `git for-each-ref refs/tags`:
```bash
refs/tags/pre-cleanup commit 003cd293a088d9ddd454cdba8b0773c4fdb75d59  
refs/tags/v1.1.0 tag b90fb9f986362f866a0593dbb574d19c824399df 9fc4fccded3ccc73c8eb7626a286b03f17b5ebd5 Sun Oct 25 01:05:29 2026 +0530
refs/tags/v1.2.0 tag 75a7e41ddbac83ece12f9c3af4ab66d33d9f0c0e dcbc2b5db3cd0f24d9704c5e4da8336f64c88e08 Mon Oct 26 13:25:27 2026 +0530
```

### Commit Author Details for the J6 Commit:
- **Commit Hash**: `9fc4fccded3ccc73c8eb7626a286b03f17b5ebd5`
- **Author**: `Namish Kumar`
- **Author Date**: `2026-10-25 01:03:05 +0530`
- **Committer Date**: `2026-10-25 01:03:05 +0530`
- **Commit Title**: `J6: Implement time-decayed signal engine v1 with fit-intent score separation and sensitive insurance cancellation flagging`
- **Associated Release Tag**: `v1.1.0` (Tag object `b90fb9f986362f866a0593dbb574d19c824399df`, Tagger Date: `Sun Oct 25 01:05:29 2026 +0530`)

### Explanation of the October 25 Dates:
- Workstream J (item J6) was implemented and committed during the early morning hours of October 25, 2026 (01:03:05 AM IST).
- Tag `v1.1.0` was cut and annotated immediately after commit `9fc4fcc` at 01:05:29 AM IST.
- These dates represent the genuine, unaltered system clock timestamps recorded at commit creation time.
- **Integrity Statement**: In accordance with user directives, no git tags or commit histories have been rewritten, moved, or deleted.
