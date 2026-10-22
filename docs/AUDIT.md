# AUDIT: TRUCKLEAD AUTOPILOT (GENLEAD)
**Author**: Principal Engineer & Growth-Systems Architect  
**Date**: October 22, 2026  
**Status**: Completed Baseline Audit (Phase 0)  
**Target Repo**: `f:\GAURAV\GENLEAD`  

---

## 1. Executive Summary

TRUCKLEAD AUTOPILOT is an active, functioning platform with a solid dual-persona model (Carriers vs Shippers), SQLite WAL persistence, async FastAPI backend, and React 18 frontend. However, it currently relies on fragile commercial directory HTML scrapers (`usdotlookup.com`, Indeed search parsing, IndustrySelect blog scraping), contains heuristic data-guessing in secondary adapters, lacks compliance guardrails (CAN-SPAM, TCPA/DNC, suppression lists), has discrepancies between documented rules and actual verification/scoring code, and has a network-bound test suite taking ~70–170 seconds.

This audit establishes the baseline facts across all 10 workstreams and outlines the prioritized, phased engineering plan.

---

## 2. Real vs. Documented Behavior Discrepancies

| Subsystem / Feature | Claimed in Documentation | Reality in Codebase | Severity |
|---|---|---|---|
| **Primary Carrier Discovery** | Uses "FMCSA SAFER" and "FMCSA L&I" official sources | Both `fmcsa_safer.py` and `fmcsa_li.py` scrape HTML from `usdotlookup.com/state/{st}`. No official FMCSA API (`data.transportation.gov` or QCMobile) is called. | **HIGH** |
| **Data Provenance & Fabrication** | "No mock or fabricated data, ever. Every field carries provenance." | In `indeed_jobs.py`, `procurement_news.py`, `google_search.py`, and `industry_directories.py`, candidates without extracted fields are assigned hardcoded fallbacks: `city="Dallas"/"Atlanta"/"Chicago"`, `fleet_size=6`, `driver_count=6`, `operating_status="ACTIVE"`, `safety_rating="SATISFACTORY"`. | **HIGH** |
| **10-Point Grounded Verification** | Claims 10 specific rules: (1) Identity, (2) Operating Authority, (3) Fleet Sizing, (4) Web Presence, (5) Phone, (6) Physical Yard Address, (7) Equipment, (8) Safety Rating, (9) Decision Maker, (10) High-Intent Recency. | `verifier.py` implements: (1) Identity, (2) Geography state check, (3) Passenger check, (4) Operating Authority, (5) Fleet Sizing, (6) Equipment, (7) Website, (8) Decision Maker, (9) Usable Contact, (10) Source Provenance. Rules 6 (Address), 8 (Safety), and 10 (Recency) are missing. | **HIGH** |
| **Verification States** | Implies nuanced audit tracking. | Code only issues `PASSED`, `WARNING`, and `FAILED`. There is no `UNKNOWN` state. Missing data either receives a generic `WARNING` or wrongly penalizes confidence without distinction. | **MEDIUM** |
| **Scoring Formula & Decay** | Claims $\sum(\text{Weight}_i \times \text{Confidence}_i)$ with intent timing. | Hardcoded fractional penalties (`* 0.75`, `* 0.4`). No time decay is applied to intent signals (a 6-month-old post yields the same score as yesterday's). Fit score and intent score are lumped together. | **HIGH** |
| **Learning & Feedback Loop** | "Learns which leads convert and adjusts weights." | No outcome states exist in the database (`CONTACTED`, `REPLIED`, `MEETING`, `SIGNED`, `BAD_DATA`, `NOT_INTERESTED`). No machine learning or weight proposal job exists. | **HIGH** |
| **Outreach & CRM Execution** | AI outreach and multichannel campaigns. | Code only generates static string templates in `LeadDetailModal.jsx`. No background email/SMS sequence engine, no suppression list, no DNC check, no CRM push. | **HIGH** |

---

## 3. Bugs, Logic Flaws & Vulnerabilities

1. **Heuristic Fabrication in Adapters**:
   - Files: [`indeed_jobs.py`](file:///f:/GAURAV/GENLEAD/backend/app/adapters/indeed_jobs.py#L60-L75), [`procurement_news.py`](file:///f:/GAURAV/GENLEAD/backend/app/adapters/procurement_news.py#L60-L75), [`google_search.py`](file:///f:/GAURAV/GENLEAD/backend/app/adapters/google_search.py#L70-L84), [`industry_directories.py`](file:///f:/GAURAV/GENLEAD/backend/app/adapters/industry_directories.py#L74-L85).
   - Bug: Defaults `city`, `fleet_size=5/6`, `operating_status="ACTIVE"`, `safety_rating="SATISFACTORY"`.
   - Fix: Store `None` / `UNKNOWN` when not present in source snippet; rely on subsequent enrichment and verification.
2. **Missing `UNKNOWN` Status in Verification**:
   - File: [`verifier.py`](file:///f:/GAURAV/GENLEAD/backend/app/services/verifier.py).
   - Bug: Steps mark `status="WARNING"` or `status="FAILED"` on missing values. Leads with incomplete public data cannot be distinguished from leads that affirmatively failed checks.
   - Fix: Introduce `status="UNKNOWN"` for unverified attributes; separate hard gates (e.g. revoked authority, passenger carrier) from missing soft signals.
3. **No Time Decay on Intent Signals**:
   - File: [`lead_scorer.py`](file:///f:/GAURAV/GENLEAD/backend/app/services/lead_scorer.py#L102-L111).
   - Bug: `intent_signals` table records `detected_date`, but `LeadScorer` ignores age completely.
   - Fix: Implement exponential half-life decay ($\text{Strength} = S_0 \times 2^{-\Delta t / t_{1/2}}$).
4. **No Rate Limiting or Circuit Breaker on Web Scrapers**:
   - If `usdotlookup.com` or `industryselect.com` returns 429/403 or times out, the adapters throw exceptions that degrade run yield without demoting the failing source.
   - Fix: Implement adapter health tracking (success rate, latency, yield) with automatic source circuit breaking.

---

## 4. Legal, Compliance & ToS Risks

| Risk Area | Regulation / ToS | Current State in Repository | Required Engineering Remediation |
|---|---|---|---|
| **Commercial Directory Scraping** | Site ToS (usdotlookup, IndustrySelect, Indeed) | Relies on scraping commercial directory HTML pages that prohibit automated extraction. | Shift primary discovery to official open datasets: **FMCSA API / data.transportation.gov** (public domain, zero ToS issues). Keep scrapers strictly as secondary fallbacks. |
| **Telephone Consumer Protection Act (TCPA)** | 47 U.S.C. § 227 (Statutory damages: $500–$1,500/call) | No distinction between mobile, landline, and VoIP numbers. No National DNC Registry checking. | Add phone line-type classifier (mobile vs landline vs VoIP). Flag DNC numbers. Enforce strict "no automated calling/texting without consent" policy. |
| **CAN-SPAM Act** | 15 U.S.C. 7701 et seq. | Static email copy with no mandatory physical address, no opt-out link, no unsubscribe tracking. | Add global suppression list table (`suppression_list`). Enforce opt-out tokens, honest sender headers, and physical mailing address in all outreach drafts. |
| **Permanent Opt-Out & Suppression** | CAN-SPAM & Privacy Standards | Opt-outs are not stored globally. A re-run would re-import and re-contact an opted-out carrier. | Implement global suppression database table checked at discovery, scoring, and outreach dispatch. Permanently honor opt-outs across all future runs. |

---

## 5. Prioritized Engineering Backlog

Ordered by **Impact per Effort Ratio**:

| Phase | Workstream | Primary Objective | Impact | Effort | Est. Hours |
|---|---|---|---|---|---|
| **Phase 1** | **WS 9: Offline Test Suite** | Fast recorded VCR/fixture suite; pytest offline in < 15s. Opt-in `-m live` suite. | Very High | Low | 4h |
| **Phase 2** | **WS 1: Official FMCSA Data** | Implement `fmcsa_official.py` via `data.transportation.gov` / QCMobile API. Demote `usdotlookup` to fallback. | Very High | Med | 6h |
| **Phase 3** | **WS 4: Data Quality & Provenance** | Eradicate all guessed fields. Add survivorship policy, address/MC matching, chameleon carrier flags. | High | Med | 5h |
| **Phase 4** | **WS 5: Verification Engine v2** | Configurable carrier/shipper rules from YAML. Add `UNKNOWN` state. Implement missing Rules 6, 8, 10. | High | Med | 5h |
| **Phase 5** | **WS 2: High-Intent Trigger Engine** | Implement `signals/` module with typed signals, time decay half-lives, new authority & lapse tracking. | Very High | Med | 6h |
| **Phase 6** | **WS 3: Contact Verification & Waterfall** | MX/SMTP email verification, role-account filtering, phone line-type (mobile/VoIP), provider waterfall interface. | High | Med | 6h |
| **Phase 7** | **WS 6: Scoring v2 & Feedback Loop** | Separate Fit & Intent scores. Add outcome tracking (`REPLIED`, `SIGNED`, etc.) and weight proposal job. | Very High | Med | 6h |
| **Phase 8** | **WS 7: Outreach Engine & Compliance** | CAN-SPAM suppression list, TCPA DNC flags, structured fact-based copy generation, multi-step sequence drafts. | High | Med | 7h |
| **Phase 9** | **WS 8: Orchestration & Reliability** | Persistent job queue with retry/backoff, PostgreSQL support, health endpoint `/api/health/deep`. | Med | Med | 5h |
| **Phase 10**| **WS 10: Frontend Upgrades** | "Why this lead" intelligence card, one-click outreach approval, outcomes logging, ICP & weights UI. | High | Med | 6h |

---

## 6. Execution Plan & Next Steps

1. **Phase 1 (WS 9)**: Build the offline test fixture harness and split live vs offline tests. (Target: offline test execution < 15s vs current 69.26s).
2. **Phase 2 (WS 1)**: Implement official FMCSA open datasets adapter as the primary carrier pipeline.
3. **Phase 3 (WS 4 & WS 5)**: Eradicate data guessing, implement `UNKNOWN` audit states, and unify verification rules with documented specifications.
4. **Phase 4 (WS 2 & WS 3)**: Implement high-intent decaying signal engine and contact verification waterfall.
5. **Phase 5 (WS 6 & WS 7)**: Implement outcome tracking, learning weight optimizer, and CAN-SPAM/TCPA compliant outreach engine.
6. **Phase 6 (WS 8 & WS 10)**: Hardening, PostgreSQL profile, and frontend intelligence cards.

*Baseline benchmark report initialized in `docs/BENCHMARKS.md`.*
