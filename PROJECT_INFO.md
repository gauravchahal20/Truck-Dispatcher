# TRUCKLEAD AUTOPILOT (GENLEAD) - Master Project Information & Operations Manual

> **Living Project Document**  
> **Last Updated**: October 22, 2026  
> **Application Version**: 1.0.0 (Production Live Pipeline)  
> **Status**: Active & Operational  
> **System Architecture Doc**: [`ARCHITECTURE.md`](file:///f:/GAURAV/GENLEAD/ARCHITECTURE.md)  

---

## Table of Contents
1. [Executive Summary & Purpose](#1-executive-summary--purpose)
2. [Key Capabilities & Innovations](#2-key-capabilities--innovations)
3. [Technology Stack & Runtime Dependencies](#3-technology-stack--runtime-dependencies)
4. [Complete File & Directory Manifest](#4-complete-file--directory-manifest)
5. [Setup, Installation & Running Locally](#5-setup-installation--running-locally)
6. [Data Pipeline & 8-Step Lifecycle](#6-data-pipeline--8-step-lifecycle)
7. [The 41+ Lead Generation Playbook](#7-the-41-lead-generation-playbook)
8. [10-Point Grounded Verification Engine](#8-10-point-grounded-verification-engine)
9. [Scoring Matrix & Prioritization Logic](#9-scoring-matrix--prioritization-logic)
10. [Critical Gotchas & Architectural Solutions](#10-critical-gotchas--architectural-solutions)
11. [Testing & Verification Suite](#11-testing--verification-suite)
12. [Project Changelog & Living Update Log](#12-project-changelog--living-update-log)

---

## 1. Executive Summary & Purpose

**TRUCKLEAD AUTOPILOT** (internally codebase **GENLEAD**) is an enterprise autonomous lead generation, deep-enrichment, verification, and dispatch intelligence platform engineered specifically for the **United States Freight, Trucking, and Logistics industry**.

### The Problem It Solves
Traditional freight brokerages and dispatch services struggle with:
1. **Stale, Recycled Lead Lists**: Static databases sold by generic brokers are saturated, outdated, and full of revoked DOT authorities.
2. **High Carrier Churn**: Finding owner-operators and small fleets (1–10 trucks) who actively need dispatch support requires hours of manual searching.
3. **Manual Verification Overhead**: Cross-referencing FMCSA safety ratings, insurance filings, phone validity, and yard addresses takes 15–20 minutes per lead.
4. **WAF & 403 Forbidden Link Outages**: Federal sites like FMCSA SAFER actively block browser clicks with Akamai 403 Forbidden errors when links are clicked from external tools.

### The Solution
TRUCKLEAD AUTOPILOT provides an end-to-end autonomous pipeline that:
- **Scrapes 100% Real Live Leads** from public federal census records, manufacturing registries, and search engines with zero mock data.
- **Supports Dual Target Personas**:
  - **Carriers**: Fleets with trucks seeking loads, dispatching, and lane optimization.
  - **Direct Shippers**: Manufacturers and distribution centers with outbound freight seeking reliable carrier capacity.
- **Performs 10-Point Grounded Verification** with explicit evidence logs before any lead is qualified.
- **Calculates Objective Weighted Scores (0–10)** prioritizing immediate high-intent prospects (Priority A, B, C).
- **Auto-Syncs to Google Sheets and Exports CSV/XLSX** with verified decision-maker emails, phone numbers, and tailored AI outreach scripts.

---

## 2. Key Capabilities & Innovations

- **100% Genuine Data Pipeline**: All static, hardcoded datasets and mock generators were completely removed. Leads are discovered dynamically via live scrapers.
- **Dual Carrier & Shipper Engine**: Single unified table and database schema that differentiates between carriers (have trucks) and shippers (need trucks).
- **Zero-403 Safe URL Architecture**: Government SAFER deep-links that return 403 Forbidden to web browsers are automatically resolved to fast, open public carrier profiles (`https://usdotlookup.com/carrier/{usdot}`) and live company domains.
- **Smart Aggregator Deduplication**: Canonical domain deduplication explicitly excludes directories (`safer.fmcsa.dot.gov`, `google.com`, `usdotlookup.com`) to prevent distinct carriers from falsely merging into a single entity.
- **Continuous 24/7 Autopilot Runner**: Background scheduler that automatically executes periodic discovery runs across target states without requiring human intervention.
- **Multi-Channel Lead Discovery**: Implements the Master 41+ Lead Generation Playbook spanning Federal registries, state associations, industrial parks, load boards, and procurement news.

---

## 3. Technology Stack & Runtime Dependencies

### Backend
- **Language**: Python 3.13+
- **API Framework**: FastAPI 0.115+ (Asynchronous REST API, OpenAPI/Swagger docs)
- **ASGI Server**: Uvicorn
- **ORM & Database**: SQLAlchemy 2.0 (Async) + `aiosqlite`
- **Database Engine**: SQLite 3 with **WAL Mode** (`PRAGMA journal_mode=WAL; PRAGMA busy_timeout=15000;`) for high concurrency, fully compatible with PostgreSQL.
- **HTTP & Scraping Clients**: `httpx` (async HTTP), `BeautifulSoup4` (HTML parsing)
- **Data Export & Cloud Sync**: `gspread` (Google Sheets API), `openpyxl` (Excel XLSX), Python standard `csv`
- **Testing**: `pytest`, `pytest-asyncio`

### Frontend
- **Framework**: React 18
- **Build Tool**: Vite 5
- **Icons**: Lucide React
- **Design System**: Vanilla CSS tokens in [`index.css`](file:///f:/GAURAV/GENLEAD/frontend/src/index.css) utilizing an editorial cream/terracotta/sage aesthetic
- **Typography**: Google Fonts (*Outfit* for headings, *Inter* for body, *JetBrains Mono* for numbers & DOT codes)

---

## 4. Complete File & Directory Manifest

```
f:\GAURAV\GENLEAD
├── ARCHITECTURE.md                  # Detailed architectural design & system diagrams
├── PROJECT_INFO.md                  # This master document (living project manual)
├── docker-compose.yml               # Container orchestration for backend & frontend
├── trucklead.db                     # Primary SQLite database (WAL mode enabled)
│
├── config/
│   └── default_config.yaml          # Master system configuration (ICP, weights, keywords)
│
├── backend/
│   ├── requirements.txt             # Python dependencies
│   ├── Dockerfile                   # Backend Docker containerization
│   ├── test_trucklead.db            # Isolated database used exclusively by pytest
│   │
│   ├── app/
│   │   ├── main.py                  # FastAPI application entrypoint, CORS & lifespan
│   │   │
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic v2 settings & YAML config loader
│   │   │   ├── database.py          # Async engine, WAL PRAGMA, sessionmaker
│   │   │   ├── live_carrier_scraper.py # Live FMCSA census scraper (usdotlookup.com)
│   │   │   ├── live_shipper_scraper.py # Live direct shipper & manufacturer scraper
│   │   │   ├── live_search.py       # DuckDuckGo HTML search & DOM website crawler
│   │   │   ├── url_validator.py     # Safe non-blocking URL resolver (eliminates 403s)
│   │   │   ├── security.py          # Domain allowlists and rate limiter
│   │   │   └── logging.py           # Structured colored console logger
│   │   │
│   │   ├── models/
│   │   │   └── entities.py          # SQLAlchemy models (Run, Company, Contact, etc.)
│   │   │
│   │   ├── schemas/
│   │   │   └── schemas.py           # Pydantic response and request models
│   │   │
│   │   ├── adapters/
│   │   │   ├── base.py              # BaseSourceAdapter, RawLeadRecord, EnrichmentResult
│   │   │   ├── registry.py          # Central registry of all active discovery adapters
│   │   │   ├── fmcsa_safer.py       # Live census adapter for active motor carriers
│   │   │   ├── fmcsa_li.py          # FMCSA Licensing & Insurance filing adapter
│   │   │   ├── direct_shippers.py   # Live manufacturers, plants, and distribution centers
│   │   │   ├── company_website.py   # Deep crawler extracting emails, phones, equipment
│   │   │   ├── b2b_enrichment.py    # Decision-maker extractor (Owner/President/Dispatch)
│   │   │   ├── google_search.py     # Live web search adapter
│   │   │   ├── google_maps.py       # Yard address and local logistics adapter
│   │   │   ├── indeed_jobs.py       # Freight hiring intent adapter
│   │   │   ├── industry_directories.py # Trade directory scraper
│   │   │   ├── procurement_news.py  # DOT freight contract awards adapter
│   │   │   ├── specialized_verticals.py # Reefer, Flatbed, Hazmat vertical adapter
│   │   │   └── linkedin_public.py   # Public corporate executive presence adapter
│   │   │
│   │   ├── services/
│   │   │   ├── orchestrator.py      # Core 8-step pipeline coordinator
│   │   │   ├── normalizer.py        # Name cleaning, E.164 phone, domain canonicalization
│   │   │   ├── deduplicator.py      # Multi-key entity resolution and attribute merging
│   │   │   ├── verifier.py          # 10-Point Grounded Verification Engine
│   │   │   ├── lead_scorer.py       # Weighted scoring matrix (Priority A/B/C)
│   │   │   ├── decision_maker_finder.py # Executive prioritization heuristics
│   │   │   ├── intent_analyzer.py   # Freight keyword & signal classifier
│   │   │   ├── continuous_runner.py # Autonomous 24/7 background autopilot
│   │   │   └── sheets_service.py    # Google Sheets API live sync and export generator
│   │   │
│   │   └── api/
│   │       ├── __init__.py          # Combined api_router aggregating all endpoints
│   │       ├── routes_runs.py       # Run execution, trigger, and status endpoints
│   │       ├── routes_companies.py  # Lead retrieval, filtering, and status overrides
│   │       ├── routes_autopilot.py  # Continuous autopilot runner control
│   │       ├── routes_sheets.py     # Google Sheets connection and manual sync
│   │       ├── routes_stats.py      # Aggregated dashboard metrics and charts
│   │       └── routes_config.py     # System settings and ICP configuration
│   │
│   └── tests/
│       ├── conftest.py              # Test setup and isolated test DB teardown
│       ├── test_autopilot.py        # Continuous runner unit tests
│       ├── test_integration.py      # End-to-end full live pipeline run test
│       ├── test_normalizer.py       # Phone, name, domain normalization tests
│       └── test_services.py         # Verifier, Scorer, and DM Finder tests
│
└── frontend/
    ├── package.json                 # Node dependencies
    ├── vite.config.js               # Vite bundler configuration
    ├── index.html                   # HTML host page
    │
    └── src/
        ├── App.jsx                  # Main application container & view router
        ├── index.css                # Global design system tokens and styling
        │
        ├── services/
        │   ├── api.js               # Axios API client connecting to backend (:8000)
        │   └── urlUtils.js          # Safe URL helper resolving non-blocking profile links
        │
        └── components/
            ├── Header.jsx           # Global header with Autopilot pill & quick actions
            ├── Sidebar.jsx          # Primary navigation drawer
            ├── DashboardStats.jsx   # Analytics cards, conversion funnels & charts
            ├── LeadsTable.jsx       # Interactive leads table with filters & safe URLs
            ├── LeadDetailModal.jsx  # 4-tab audit drawer (10-Point checklist, contacts)
            ├── SearchPlaybook.jsx   # Master 41+ lead generation methods guide
            ├── NewRunModal.jsx      # Launch run wizard (states, fleet size, equipment)
            ├── RunsManager.jsx      # Historical run management and logs
            ├── SheetsManager.jsx    # Google Sheets status and live sync button
            └── ConfigSettings.jsx   # ICP criteria and scoring weight editor
```

---

## 5. Setup, Installation & Running Locally

### Prerequisites
- Python 3.11 or higher (Python 3.13 recommended)
- Node.js 18+ and npm
- Windows, macOS, or Linux

### 1. Backend Setup
From the repository root (`f:\GAURAV\GENLEAD`):
```bash
# 1. Activate virtual environment
.\venv\Scripts\activate   # Windows PowerShell
# source venv/bin/activate # macOS/Linux

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Start FastAPI server
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
The backend API is now live at:
- **API URL**: `http://127.0.0.1:8000`
- **Swagger Docs**: `http://127.0.0.1:8000/docs`
- **Health Check**: `http://127.0.0.1:8000/health`

### 2. Frontend Setup
In a separate terminal:
```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Start Vite development server
npm run dev
```
The frontend application is now live at:
- **Web App**: `http://127.0.0.1:5173`

---

## 6. Data Pipeline & 8-Step Lifecycle

Every run follows a deterministic, 8-step autonomous qualification lifecycle:

```
[1. DISCOVERY] ──> [2. NORMALIZATION] ──> [3. DEDUPLICATION] ──> [4. ENRICHMENT]
                                                                        │
[8. EXPORT/SYNC] <── [7. QUALIFICATION] <── [6. SCORING] <── [5. VERIFICATION]
```

1. **Step 1: Multi-Source Discovery**: Active adapters query live FMCSA census tables, manufacturing directories, and live search engines in parallel across selected states (e.g. `TX`, `CA`, `GA`, `FL`, `OH`).
2. **Step 2: Normalization**: Standardizes company names, converts phone numbers to E.164, strips path/query elements from URLs, and validates 2-letter state codes.
3. **Step 3: Deduplication**: Compares candidates against in-memory batch cache and existing database records using USDOT, canonical domain, normalized phone, and fuzzy name matching. Duplicate records have their source records merged.
4. **Step 4: Deep Web Enrichment**: Crawls company websites for email addresses, direct phone lines, trailer equipment, and executive titles.
5. **Step 5: 10-Point Grounded Verification**: Executes 10 independent verification rules checking federal authority, safety records, and physical yard locations.
6. **Step 6: Weighted Scoring**: Evaluates the company against 7 weighted criteria, producing a score from 0.0 to 10.0 and assigning a priority tier (`A`, `B`, `C`).
7. **Step 7: Qualification Gate**: 
   - Score $\ge 5.0$ and Status `VERIFIED` $\rightarrow$ Lead marked `FINAL`.
   - Critical rule failure $\rightarrow$ Lead marked `REJECTED` with audit reason.
   - Low confidence $\rightarrow$ Lead marked `NEEDS_REVIEW`.
8. **Step 8: Automated Export & Sync**: Generates formatted CSV and Excel (`.xlsx`) files and synchronizes records directly to connected Google Sheets.

---

## 7. The 41+ Lead Generation Playbook

The platform implements 41+ specialized lead generation methods categorized across 8 core operational categories:

1. **Federal & Safety Registries (Methods 1–5)**:
   - FMCSA Census & Safety Snapshot lookup.
   - FMCSA L&I authority and BMC-91X insurance filing checks.
   - Unified Carrier Registration (UCR) compliance verification.
   - Hazardous materials safety permit registry.
2. **State & Local Registries (Methods 6–10)**:
   - State DOT intrastate databases (TxDOT, Caltrans, GDOT).
   - State Trucking Association member directories (TXTA, GMTA, OTA).
   - Regional Chambers of Commerce industrial logistics hubs.
3. **Physical & Visual Reconnaissance (Methods 11–15)**:
   - Google Maps satellite freight yard and truck terminal scouting.
   - Port container drayage terminals (Houston, Savannah, Long Beach).
   - Major interstate highway interchange logistics parks (I-10, I-35, I-75).
4. **Direct High-Volume Shippers (Methods 16–20)**:
   - Food & beverage refrigerated food manufacturing plants.
   - Heavy industrial equipment and metal fabricators.
   - Major retail distribution and fulfillment centers.
   - Building materials and lumber distribution yards.
5. **High-Intent Hiring & Expansion Signals (Methods 21–25)**:
   - Indeed / LinkedIn job postings for *Truck Dispatchers*.
   - Job postings for *Fleet Managers* and *Logistics Coordinators*.
   - Fleet expansion announcements (new tractors purchased/leased).
6. **Procurement & Government Freight Contracts (Methods 26–30)**:
   - Federal SAM.gov defense freight awards.
   - State DOT road material transportation contracts.
   - FEMA emergency logistics contractor registries.
7. **Specialized Verticals & Niches (Methods 31–35)**:
   - Temperature-controlled produce and pharmaceutical reefer lanes.
   - Oversized / overweight flatbed, stepdeck, and lowboy operations.
   - Specialized chemical and agricultural tanker fleets.
8. **Technology & B2B Footprint Discovery (Methods 36–41)**:
   - Transportation Management System (TMS) portal integrations.
   - Electronic Logging Device (ELD) technology footprints.
   - Executive decision-maker enrichment (Apollo / Lusha / LinkedIn).

---

## 8. 10-Point Grounded Verification Engine

Every lead undergoes rigorous testing across 10 verification dimensions:

```
[ Rule 1: Legal Entity Existence ] ──> PASS (Registered Corporate Entity)
[ Rule 2: Operating Authority   ] ──> PASS (Active For-Hire Interstate Authority)
[ Rule 3: Fleet Sizing Match    ] ──> PASS (Power units fit 2-10 truck sweet spot)
[ Rule 4: Authentic Web Profile ] ──> PASS (Resolving domain or public census page)
[ Rule 5: Reachable Phone Line  ] ──> PASS (Valid North American 10-digit number)
[ Rule 6: Physical Yard Address ] ──> PASS (Verifiable street address, city & state)
[ Rule 7: Equipment Alignment   ] ──> PASS (Dry Van, Reefer, or Flatbed confirmed)
[ Rule 8: Safety & Compliance   ] ──> PASS (Satisfactory safety rating, no violations)
[ Rule 9: Named Decision Maker  ] ──> PASS (Owner, President, or Dispatcher named)
[ Rule 10: High-Intent Recency  ] ──> PASS (Recent MCS-150 filing or hiring signal)
```

Verification results are saved in the `verification_records` table and displayed on the frontend with confidence meters and expandable evidence notes.

---

## 9. Scoring Matrix & Prioritization Logic

The lead score is a weighted composite between **0.0 and 10.0**:

| Criteria | Maximum Weight | Description |
|---|---|---|
| **Target Fleet Sizing** | **2.0 pts** | Fleet size fits the 2–10 power unit ICP sweet spot |
| **Verified Active Authority** | **2.0 pts** | Active interstate authority confirmed with no revocations |
| **Named Decision Maker** | **2.0 pts** | Owner, President, or Dispatch Manager identified |
| **Usable Contact Info** | **1.0 pt** | Valid business phone and/or verified direct email |
| **Equipment Verified** | **1.0 pt** | Desired trailer types confirmed on record |
| **Intent Signals Detected** | **1.0 pt** | Hiring dispatchers, fleet expansion, or freight requests |
| **Business Events / Recency**| **1.0 pt** | Recent MCS-150 filing or public contract award |

### Prioritization Tiers
- **Priority A (Score 8.0 – 10.0)**: Premium lead with direct decision maker, valid phone/email, active authority, and high intent. Ready for immediate outreach.
- **Priority B (Score 6.0 – 7.9)**: Qualified lead with verified active fleet; suitable for automated outreach sequences.
- **Priority C (Score 5.0 – 5.9)**: Verified active carrier with limited contact details; requires light manual research.
- **Disqualified (< 5.0)**: Failed safety checks, inactive authority, or outside target fleet constraints.

---

## 10. Critical Gotchas & Architectural Solutions

### 1. The 403 Forbidden Link Problem
- **Root Cause**: `safer.fmcsa.dot.gov` uses Akamai WAF to block incoming external referrers and deep links with `HTTP 403 Forbidden`.
- **Solution**: 
  1. [`url_validator.py`](file:///f:/GAURAV/GENLEAD/backend/app/core/url_validator.py) prevents any URL containing `fmcsa.dot.gov` from being stored as a company website.
  2. Fallbacks use `https://usdotlookup.com/carrier/{usdot}`, which returns `HTTP 200 OK` in all browsers and displays the carrier's full census and safety record.
  3. Frontend [`urlUtils.js`](file:///f:/GAURAV/GENLEAD/frontend/src/services/urlUtils.js) safely redirects any old or cached links dynamically.

### 2. Aggregator Domain Deduplication Collision
- **Root Cause**: Earlier versions used domain matching without excluding public directories. Multiple distinct carriers with `website = safer.fmcsa.dot.gov` were collapsed into a single entity.
- **Solution**: [`normalizer.py`](file:///f:/GAURAV/GENLEAD/backend/app/services/normalizer.py) maintains a `GENERIC_DOMAINS` blacklist (`safer.fmcsa.dot.gov`, `google.com`, `usdotlookup.com`, `yellowpages.com`). The deduplicator ignores these domains for entity matching.

### 3. SQLite Concurrency & Disk I/O Lockups
- **Root Cause**: Running concurrent async pipeline tasks while writing to SQLite triggered `sqlite3.OperationalError: disk I/O error` or database locks.
- **Solution**: Configured [`database.py`](file:///f:/GAURAV/GENLEAD/backend/app/core/database.py) with SQLite Write-Ahead Logging:
  ```python
  cursor.execute("PRAGMA journal_mode=WAL")
  cursor.execute("PRAGMA busy_timeout=15000")
  ```
  This permits simultaneous reads while writes are occurring.

### 4. Elimination of Mock Data
- **Root Cause**: Earlier prototypes relied on synthetic data in `real_carriers_data.py`.
- **Solution**: Replaced all mock lists with genuine dynamic scrapers (`live_carrier_scraper.py`, `live_shipper_scraper.py`, `live_search.py`).

---

## 11. Testing & Verification Suite

The backend contains a 16-test automated suite executed via `pytest`:
```bash
# Run test suite from repository root
.\venv\Scripts\python.exe -m pytest backend/tests
```

### Test Coverage Breakdown
- [`test_autopilot.py`](file:///f:/GAURAV/GENLEAD/backend/tests/test_autopilot.py): Tests background continuous runner start/stop states, interval triggers, and error resilience.
- [`test_integration.py`](file:///f:/GAURAV/GENLEAD/backend/tests/test_integration.py): End-to-end pipeline execution verifying multi-state discovery, deduplication, 10-point verification, lead scoring, and file exports against a clean temporary test database.
- [`test_normalizer.py`](file:///f:/GAURAV/GENLEAD/backend/tests/test_normalizer.py): Validates company name cleaning, E.164 phone parsing, domain canonicalization, and aggregator domain exclusions.
- [`test_services.py`](file:///f:/GAURAV/GENLEAD/backend/tests/test_services.py): Verifies decision-maker priority heuristics, intent signal classification, verification rule enforcement, and scoring calculations.

---

## 12. Project Changelog & Living Update Log

*This section is maintained chronologically as new features, adapters, and improvements are deployed.*

### Version 1.1.0 — Phase 0: Fabrication Elimination & Baseline Audit (October 22, 2026)
- **Zero-Fabrication Data Integrity**:
  - Removed all guessed defaults across `indeed_jobs.py`, `procurement_news.py`, `google_search.py`, `industry_directories.py`, `fmcsa_safer.py`, `fmcsa_li.py`.
  - Added JSON field provenance column (`field_provenance`) and Alembic migration tracking `{source, url, retrieved_at, method}`.
  - Backfilled all 84 existing legacy database records with honest `method="legacy_unverified"` and `retrieved_at=null`.
  - Audited and nulled 21 suspect legacy fallback values; flagged leads with `needs_reverification=True`.
- **Nominatim Compliance Hardening**:
  - Enforced 1 req/s rate-limiting, in-memory response caching, and descriptive contact User-Agent in `live_search.py`.
- **Measured Real Baseline**:
  - Conducted standardized benchmark run `2df209d9-5d1c-4325-a874-89afc1e3d2c7` (TX/GA/OH, 2-10 fleet, 25 leads).
  - Updated `docs/BENCHMARKS.md` with measured metrics: Decision Maker (0.0%), Valid Phone (51.2%), Valid Email (0.0%), Provenance (100.0%), Dedup Rate (23.4% DB, 24.5% run).

### Version 1.2.0 — Phase 1: Offline Test Suite Hardening (October 22, 2026)
- **100% Offline Test Enforcement**:
  - Configured `backend/tests/conftest.py` with `block_external_sockets` autouse fixture: intercepts external socket connections and DNS resolution, raising `SocketBlockedError`.
  - Added `pytest.ini` with `addopts = -m "not live"`: excludes live tests by default; opt-in with `pytest -m live`.
  - Created `backend/tests/fixtures/` with authentic recorded responses for SAFER, L&I, directory cards, and carrier websites.
  - Suite execution time reduced from 32.12s (and 69.26s before) down to **4.53s** (53 tests passed, 2 deselected).
- **Comprehensive Master Prompt Test Suites**:
  - `test_deduplication_edge_cases.py`: Suffix stripping, case-insensitivity, phone variations, domain normalization, aggregator collision exclusion, survivorship.
  - `test_scoring_rules.py`: All 7 criteria, priority tiers (A/B/C), None/UNKNOWN safety without crashing.
  - `test_validators.py`: RFC 1918 private IPv4 and cloud metadata SSRF protection, role-account email detection, NANP phone validation.
  - `test_socket_blocker.py`: Formally proves external sockets and DNS fail in offline mode.
  - `test_integration.py`: End-to-end 8-step pipeline execution in 2.44s completely offline.
