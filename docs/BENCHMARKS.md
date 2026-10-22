# BENCHMARKS: TRUCKLEAD AUTOPILOT (GENLEAD)
**Author**: Principal Engineer & Growth-Systems Architect  
**Last Updated**: October 22, 2026 (Phase 0 Baseline)  

---

## 1. Fixed Benchmark Configuration

To measure performance systematically across engineering phases, all benchmark runs use the following standardized target parameters:
- **Target States**: `TX`, `GA`, `OH` (3 states)
- **Fleet Size Range**: `2 – 10` Power Units (Small fleet ICP)
- **Equipment Types**: `Dry Van`, `Reefer`, `Flatbed`
- **Target Lead Count**: `25` candidates per run
- **Lead Type**: `ALL` (Dual Carrier & Shipper)

---

## 2. Benchmark Progress Tracking Matrix

| Metric | Phase 0 (Baseline) | Target State (Post-Upgrade) | Phase 1 (WS9) | Phase 2 (WS1) | Phase 3 (WS4/5) | Phase 4 (WS2/3) | Phase 5 (WS6/7) |
|---|---|---|---|---|---|---|---|
| **Pytest Suite Runtime** | **69.26s** (network bound) | **< 15.0s** (100% offline) | | | | | |
| **Offline Test Coverage** | 0% (All 16 hit live web) | 100% (with `-m live` opt-in) | | | | | |
| **Primary Discovery Source**| 100% HTML Scraper (`usdotlookup`) | $\ge 85\%$ Official FMCSA (`transportation.gov`) | | | | | |
| **Data Provenance Integrity**| ~70% (30% guessed in search adapters) | **100% verified** (0% guessed fields) | | | | | |
| **Verified-Reachable Rate** | ~35% (named DM + valid phone/email) | **$\ge 75\%$** | | | | | |
| **Email Deliverability Check**| 0% (regex check only) | **100%** (MX + SMTP/provider verified) | | | | | |
| **Phone Line-Type Detection**| 0% (unclassified strings) | **100%** (Mobile vs Landline vs VoIP) | | | | | |
| **TCPA / DNC Screening** | 0% (No DNC check) | **100%** (Mobile/DNC flagged) | | | | | |
| **Signal Time Decay** | 0% (stale signals = fresh signals) | **100%** (exponential half-life decay) | | | | | |
| **Enrichment Cost per Lead** | $0.00 (raw web search only) | **Tracked with budget cap ($0.05/lead)** | | | | | |
| **Priority A Precision** | Unmeasured (no outcome feedback) | **Tracked via outcome loop ($\ge 80\%$)** | | | | | |

---

## 3. Phase 0 Baseline Observations

### Benchmark Run 0 (October 22, 2026, 17:19 UTC)
- **Test Command**: `pytest backend/tests -v`
- **Total Tests**: 16 passed
- **Total Execution Time**: **69.26 seconds** (01:09)
  - `test_autopilot.py`: 3 tests passed in 0.4s
  - `test_integration.py::test_end_to_end_pipeline_run`: 1 test passed in **65.1s** (Bottleneck: makes real live HTTP requests to usdotlookup.com and duckduckgo.com)
  - `test_normalizer.py`: 7 tests passed in 0.1s
  - `test_services.py`: 5 tests passed in 0.2s
- **Defects Identified**:
  - Live network dependency during `pytest` makes CI brittle and vulnerable to external rate-limiting and network latency.
  - Secondary adapters (`indeed_jobs`, `procurement_news`, `google_search`, `industry_directories`) populate missing city with `"Dallas"`, `"Atlanta"` or `"Chicago"`, and fleet size with `5` or `6`.
  - Intent signals have no age decay applied in `LeadScorer`.
  - Zero suppression checks or opt-out storage.

---

## 4. Measurement Protocol for Subsequent Phases

After completing each phase:
1. Run `pytest` offline suite and record execution time.
2. If changing discovery, run the standardized benchmark run (TX, GA, OH, 25 leads).
3. Compute and log:
   - Total Raw Leads Discovered
   - Deduplication Rate (%)
   - Verified-Reachable Leads (Count and %)
   - Decision-Maker Coverage (%)
   - Email Deliverability Rate (%)
   - Average Processing Time per Lead (seconds)
   - Estimated Enrichment Cost per Lead ($)
