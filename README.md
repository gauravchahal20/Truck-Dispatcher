# TRUCKLEAD AUTOPILOT (GENLEAD)

> **Autonomous Freight & Carrier Lead Generation, Deep-Enrichment, and 10-Point Verification Engine**  
> Designed for U.S. Freight Brokerages, Dispatch Services, and Fleet Operators.

---

## 1. Project Directory Structure

```text
GENLEAD/
├── README.md                           # System overview, setup & usage guide
├── docker-compose.yml                  # Production container stack (Postgres + Backend + Frontend)
├── pytest.ini                          # Test configuration & markers
├── config/
│   ├── default_config.yaml             # System defaults, ICP rules, scoring & verification parameters
│   └── .env.example                    # Environment variable template
├── docs/
│   ├── ARCHITECTURE.md                 # Technical architecture & pipeline specification
│   ├── PROJECT_INFO.md                 # System overview, data dictionary & changelog
│   ├── DATA_SOURCES.md                 # Ingestion sources & SODA catalog dictionary
│   ├── BENCHMARKS.md                   # Throughput & accuracy benchmarks
│   ├── AUDIT.md                        # Audit findings & hardening tracker
│   ├── RUNBOOK.md                      # Operational runbook & troubleshooting
│   └── reports/
│       ├── PROJECT_ANALYSIS_REPORT.md  # Automated evidence-based project report
│       ├── step_b_baseline_results.json
│       └── step_d_benchmark_results.json
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt                # Python dependencies
│   ├── alembic.ini                     # Migration configuration
│   ├── alembic/                        # Database migration scripts
│   ├── app/                            # Application package (api, core, adapters, models, schemas, services)
│   └── tests/
│       ├── conftest.py                 # Pytest runner setup & network isolation fixtures
│       ├── unit/                       # Deterministic offline unit test suite
│       ├── integration/                # End-to-end offline pipeline integration tests
│       ├── live/                       # Network-touching external endpoint & parser drift tests
│       └── fixtures/                   # Offline HTML/JSON test fixtures
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx                     # Main shell & tab navigation
│       ├── components/                 # UI views (DashboardStats, ReadyToContact, LeadsTable, etc.)
│       ├── services/                   # API client & URL utility helpers
│       └── styles/                     # Layout & design tokens (App.css, index.css)
├── scripts/
│   ├── audit/                          # Audit & reporting scripts (generate_analysis_report.py, etc.)
│   ├── maintenance/                    # Data migration & reconciliation scripts
│   └── dev/                            # Benchmarking & dev test utilities
├── data/                               # (gitignored) Active SQLite DB (trucklead.db) & test DBs
└── backups/                            # (gitignored) Master DB snapshots & historical backups
```

---

## 2. Setup & Installation

### Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- Git

### Initial Setup
```bash
# Clone and enter repo
git clone <repo-url>
cd GENLEAD

# Setup Python Virtual Environment
python -m venv venv
.\venv\Scripts\activate
pip install -r backend/requirements.txt

# Setup Frontend
cd frontend
npm install
cd ..

# Copy Environment Configuration
cp config/.env.example .env
```

---

## 3. Running Locally

### Backend Server (FastAPI)
```bash
.\venv\Scripts\activate
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Docs: `http://127.0.0.1:8000/docs`
- Healthcheck: `http://127.0.0.1:8000/health`

### Frontend Application (React + Vite)
```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```
- Web UI: `http://127.0.0.1:5173`

---

## 4. Testing

```bash
# Run offline test suite (network-isolated, fast)
python -m pytest -q -m "not live"

# Run full test suite including live FMCSA SODA endpoint checks
python -m pytest -q

# Run by tier
python -m pytest backend/tests/unit -q
python -m pytest backend/tests/integration -q
python -m pytest backend/tests/live -q
```

---

## 5. Documentation Links

- [System Architecture](docs/ARCHITECTURE.md)
- [Project Information & Dictionary](docs/PROJECT_INFO.md)
- [Operations Runbook](docs/RUNBOOK.md)
- [Project Analysis Report](docs/reports/PROJECT_ANALYSIS_REPORT.md)
