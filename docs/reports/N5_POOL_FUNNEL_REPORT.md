# N5: Carrier Lead Pool Funnel & Uncapped Ingestion Audit

## 1. Executive Summary & Net-New Ingestion Results
- **Manual Uncapped Batch Run**: Successfully completed.
- **Net-New Clean ICP Carriers Ingested**: **193 carriers** (after deduplicating against existing stored USDOTs).
- **Company Officers / Contacts Created**: **199 individual named decision-makers**.
- **Total Stored Carriers with USDOT**: **297 carriers** (increased from 104 to 297).
- **Total Entities in Database**: **402 companies** (297 carriers with USDOT + 15 carriers without USDOT + 90 archived shippers).

---

## 2. Funnel Accounting

### Funnel 2.1: Main Carrier Pool (FMCSA Census Mirror)
The main carrier pool derives from the synchronized federal census registry (`fmcsa_carrier_census`):

| Funnel Stage | Carrier Count | Retention % | Filtering Criteria |
| :--- | :--- | :--- | :--- |
| **1. Total Census Mirror Records** | **365** | 100.0% | Synchronized records in local `fmcsa_carrier_census` |
| **2. Target Fleet Range** | **333** | 91.2% | Small carrier ICP target: 2 - 10 Power Units |
| **3. For-Hire Interstate Authority** | **223** | 61.1% | Authorized for-hire interstate property carriage (excluded passenger/refuse) |
| **4. MCS-150 Recency Gating** | **223** | 61.1% | Active biennial update filed within the last 24 months |
| **5. Deduplication Against Stored Pool** | **193** | 52.9% | Net-new unique USDOTs not previously in `companies` table |
| **6. Ingested into Pipeline** | **193** | 52.9% | Successfully ingested into `NEEDS_ENRICHMENT` for verify-and-call queue |
| **7. Cumulative Stored Carriers** | **297** | - | 104 baseline stored carriers + 193 newly ingested |

---

### Funnel 2.2: New-Registration Pool (Watchlist Candidates)
The new-registration pool derives from recent FMCSA applicant filings and grant notices:

| Funnel Stage | Candidate Count | Percentage | Operational Gate / Rule |
| :--- | :--- | :--- | :--- |
| **1. Staged in Watchlist** | **23** | 100.0% | Staged candidates in `candidate_watchlist` |
| **2. Active Motus Property Authority** | **23** | 100.0% | Verified `Active` property carrier filing in `inys-ebih` |
| **3. Full Active Insurance ($750k - $1M BIPD)** | **22** | 95.7% | 22 hold full BIPD ($750k+); 1 partial ($300k, KB Premier) |
| **4. Area Code & Fleet Data Sanity** | **16** | 69.6% | 16 clean matches; 6 phone region mismatches, 1 fleet inconsistency |
| **5. Ingested into Database** | **0** | **0.0%** | **STRICTLY GATED (0 ingested)** pending user approval of dry-run table |

---

## 3. Autopilot Cap Analysis: Why 50 -> 5 and Default Restoration

### Root Cause of the Cap Reduction:
1. **Why the cap was set to 5**: In workstream K5 / commit `0f49c09`, the autopilot cap was throttled from 50 to 5 (`per_cycle_leads_cap: 5`) to serve as a safety throttle during automated development cycles. This prevented runaway loops from exhausting external rate limits while phone/email verification providers and scrapers were being tested.
2. **Config Default Status**: In `config/default_config.yaml` line 301, the default setting is **50 leads per cycle** (`autopilot.per_cycle_leads_cap: 50`).
3. **Confirmation**: The default capacity of **50 leads per cycle** is active in `default_config.yaml` and verified by tests (`test_autopilot.py`). No temporary 5-lead throttle remains active.

---

## 4. Current Carrier Status & Priority Distribution (Post-Ingestion)

### Current Lead Statuses (Carriers):

| Lead Status | Count | Description |
| :--- | :--- | :--- |
| **NEEDS_ENRICHMENT** | **278** | Verify-and-call queue |
| **NEEDS_REVIEW_ICP** | **2** | Gated / suppressed |
| **NOT_ICP** | **3** | Gated / suppressed |
| **REJECTED** | **29** | Gated / suppressed |
| **Total Carriers** | **312** | - |

### Current Priority Bands (Carriers):

| Priority Band | Count | Interpretation |
| :--- | :--- | :--- |
| **Priority B** | **2** | Scored ICP lead |
| **Priority C** | **143** | Scored ICP lead |
| **Priority NONE** | **167** | Below 5.0 score gate |
| **Total Carriers** | **312** | - |