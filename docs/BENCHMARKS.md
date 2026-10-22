# BENCHMARKS: TRUCKLEAD AUTOPILOT (GENLEAD)
**Author**: Principal Engineer & Growth-Systems Architect  
**Last Updated**: October 22, 2026 (Phase 0 Measured Baseline)  

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

| Metric | Phase 0 (Measured Baseline) | Target State (Post-Upgrade) | Phase 1 (WS9: Offline Suite) | Phase 2 (WS1) | Phase 3 (WS4/5) | Phase 4 (WS2/3) | Phase 5 (WS6/7) |
|---|---|---|---|---|---|---|---|
| **Pytest Suite Runtime** | **32.12s** (network bound) *(prev. 69.26s)* | **< 15.0s** (100% offline) | **4.53s** (100% offline) | | | | |
| **Offline Test Coverage** | 0% (All 27 tests live network) | 100% (with `-m live` opt-in) | **100%** (53 offline, 2 opt-in live) | | | | |
| **Primary Discovery Source**| 100% HTML Scraper (`usdotlookup`) | $\ge 85\%$ Official FMCSA (`transportation.gov`) | 100% Scraper (pre-Phase 2) | | | | |
| **Data Provenance Integrity**| **100.0%** (84/84 DB, 25/25 Run) *(prev. estimated ~70%)* | **100% verified** (0% guessed fields) | **100.0%** verified | | | | |
| **Named Decision Maker Rate**| **0.0%** (0/84 DB, 0/25 Run) *(prev. estimated ~35%)* | **$\ge 75\%$** | **0.0%** (unmodified in Step C) | | | | |
| **Valid Phone Rate** | **51.2%** (43/84 DB), **48.0%** (12/25 Run) | **$\ge 90\%$** | **51.2%** (unmodified in Step C) | | | | |
| **Valid Email Rate** | **0.0%** (0/84 DB, 0/25 Run) *(prev. estimated ~20%)* | **$\ge 65\%$** | **0.0%** (unmodified in Step C) | | | | |
| **Deduplication Rate** | **23.4%** DB lifetime, **24.5%** Fresh Run *(prev. unmeasured)* | **$\ge 30\%$** cross-channel | **24.5%** verified | | | | |
| **Email Deliverability Check**| 0% (regex check only) | **100%** (MX + SMTP/provider verified) | Role account detection added | | | | |
| **Phone Line-Type Detection**| 0% (unclassified strings) | **100%** (Mobile vs Landline vs VoIP) | NANP phone validator added | | | | |
| **TCPA / DNC Screening** | 0% (No DNC check) | **100%** (Mobile/DNC flagged) | Pending Phase 3 | | | | |
| **Signal Time Decay** | 0% (stale signals = fresh signals) | **100%** (exponential half-life decay) | Pending Phase 4 | | | | |
| **Enrichment Cost per Lead** | $0.00 (raw web search only) | **Tracked with budget cap ($0.05/lead)** | $0.00 | | | | |
| **Priority A Precision** | 0.0% (0 Priority A leads produced) | **Tracked via outcome loop ($\ge 80\%$)** | 0.0% (honest scoring) | | | | |

---

## 3. Phase 0 Baseline Observations

### Benchmark Run 0 (Pre-Cleanup, October 22, 2026, 17:19 UTC)
- **Test Command**: `pytest backend/tests -v`
- **Total Tests**: 16 passed in **69.26 seconds** (Bottleneck: `test_end_to_end_pipeline_run` 65.1s live network)
- **Defects Identified**:
  - Live network dependency during `pytest` makes suite brittle and slow.
  - Secondary adapters fabricated missing cities (`"Dallas"`, `"Atlanta"`, `"Chicago"`), fleet size (`5` or `6`), and statuses (`ACTIVE`, `SATISFACTORY`).

### Benchmark Run 1: Standardized Baseline Run (Post Step A & A2-A5, October 22, 2026, 18:09 UTC)
- **Run ID**: `2df209d9-5d1c-4325-a874-89afc1e3d2c7`
- **Configuration**: Target States: `TX, GA, OH` | Fleet: `2 – 10` | Equipment: `Dry Van, Reefer, Flatbed` | Target Count: `25` | Type: `ALL`
- **Execution Duration**: **66.31 seconds**
- **Raw Candidates Discovered**: 37
- **Duplicates Intercepted & Merged**: 12 (Dedup Rate: **24.5%**)
- **Total Unique Leads Stored**: 25
- **Measured Quality Metrics**:
  - **Named Decision Maker**: **0.0%** (0 / 25) — *Note: was previously estimated as ~35%. Discovery census directories do not contain executive names without enrichment keys.*
  - **Valid Phone Coverage**: **48.0%** (12 / 25)
  - **Valid Email Coverage**: **0.0%** (0 / 25) — *Note: was previously estimated as ~20%. No real emails exist without B2B API keys.*
  - **Field-Level Provenance**: **100.0%** (25 / 25) with `{source, url, retrieved_at, method}` on every non-null field.
  - **Fabricated Defaults Emitted**: **0** (All missing values stored as `None`/`[]`).
- **Database Baseline (All 84 Existing Leads in `trucklead.db`)**:
  - Named Decision Maker: **0.0%** (0 / 84)
  - Valid Phone: **51.2%** (43 / 84)
  - Valid Email: **0.0%** (0 / 84)
  - Field-Level Provenance: **100.0%** (84 / 84) labeled with `legacy_unverified` and `retrieved_at=null`.
  - Dedup Rate: **23.4%** (29 duplicates across 124 raw candidates).
  - Average Lead Score: **3.26 / 10.0** (dropped from artificial 4.13 after removing guessed fleet/status defaults).

### Benchmark Run 2: Phase 1 Offline Test Suite (Step C, October 22, 2026, 18:23 UTC)
- **Suite Command**: `pytest` (default invocation)
- **Measured Offline Runtime**: **4.53 seconds** (Target: < 15.0s, achieved: **70% faster than target**)
- **Total Tests Executed**: 53 passed, 2 deselected (marked `@pytest.mark.live`)
- **Offline Proof**:
  - `backend/tests/conftest.py` intercepts `socket.socket.connect`, `connect_ex`, and `socket.getaddrinfo`.
  - Verified by `test_socket_blocker.py`: Any attempt to establish external socket connection or perform external DNS resolution in default mode fails immediately with `SocketBlockedError`.
  - Local loopback (`127.0.0.1`, `localhost`, `::1`) permitted for in-process SQLite event loops.
  - Tests decorated with `@pytest.mark.live` bypass the blocker and run selectively via `pytest -m live` (live run duration: 25.81s).
- **Recorded Fixtures & Mock Coverage**:
  - Created `backend/tests/fixtures/` containing authentic recorded responses for FMCSA SAFER snapshot, FMCSA L&I insurance details, USDOT Lookup carrier cards, and carrier websites.
  - Added `test_end_to_end_pipeline_offline`: Complete 8-step pipeline executes end-to-end in **2.44 seconds** 100% offline.
- **Master Prompt Test Suites Added**:
  - **Deduplication Edge Cases** (`test_deduplication_edge_cases.py` - 10 tests):
    - Case-insensitivity in legal names, phones, domains.
    - Suffix stripping (`LLC`, `L.L.C.`, `Inc.`, `Corp.`, `Logistics`, `Transport`, `Freight`, `Hauling`, `Lines`, `Ltd.`).
    - Phone number formats (`(214) 555-0182`, `2145550182`, `+12145550182`, `1-214-555-0182`).
    - Domain normalization with subdomains, protocols, ports, and trailing paths.
    - Aggregator domain collision protection (`safer.fmcsa.dot.gov`, `usdotlookup.com`, `google.com` excluded from domain matching).
    - Multi-factor resolution: USDOT, normalized domain, normalized phone, name+state matching.
    - Intra-run vs cross-run deduplication scoping.
    - Survivorship merging: merges candidate fields and field provenance without overwriting higher-fidelity data.
  - **Granular Lead Scoring Rules** (`test_scoring_rules.py` - 5 tests):
    - All 7 scoring criteria: target fleet capacity (+2.0), active carrier (+2.0), named DM (+2.0), equipment match (+1.0), usable contact (+1.0), intent signals (+1.0), tech/business event (+1.0).
    - Priority tiers: A (>= 8.0), B (5.0 to 7.9), C (< 5.0).
    - Unknown/None safety: None values award 0 without errors or crash.
    - Shipper scoring path and contact partial credit.
  - **Security Validators & Data Integrity** (`test_validators.py` - 8 tests):
    - SSRF protection: blocks RFC 1918 private IPv4 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopback (`127.0.0.0/8`), cloud metadata IP (`169.254.169.254`), non-HTTP schemes (`file://`, `ftp://`).
    - Role-account email detection: flags `info@`, `sales@`, `dispatch@`, `support@`, `admin@` as role accounts.
    - NANP phone validation: validates 10-digit North American numbering plan, rejects fictional `555-0100..0199` range and repeated dummy numbers.

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
