# TRUCKLEAD AUTOPILOT — Operations Runbook

## 1. Quick Start & Local Execution

### Backend API Server (FastAPI / Uvicorn)
```bash
# Activate virtual environment
.\venv\Scripts\activate

# Launch backend on port 8000
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
- Swagger Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- API Healthcheck: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### Frontend Dashboard (Vite / React)
```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```
- Dashboard UI: [http://127.0.0.1:5173/](http://127.0.0.1:5173/)

---

## 2. Testing & Quality Assurance

### Run Offline Test Suite (Deterministic, Network-Isolated)
```bash
python -m pytest -q -m "not live"
```

### Run Full Test Suite (Including Live SODA Network Probes)
```bash
python -m pytest -q
```

### Run Specific Test Directories
```bash
python -m pytest backend/tests/unit -q
python -m pytest backend/tests/integration -q
python -m pytest backend/tests/live -q
```

---

## 3. Database Management & Backups

- **Primary Database**: `data/trucklead.db` (SQLite in WAL mode).
- **Test Database**: `data/test_trucklead.db` (isolated during pytest).
- **Backups Directory**: `backups/` (gitignored).

### Taking a Manual Backup
```powershell
Copy-Item data/trucklead.db backups/trucklead_manual_$(Get-Date -Format 'yyyyMMdd_HHmmss').db
```

### Re-running Evidence-Based Project Analysis
```bash
python scripts/audit/generate_analysis_report.py
```
Outputs: `docs/reports/PROJECT_ANALYSIS_REPORT.md`

### Database Reconciliation & Verification Audit
```bash
python scripts/maintenance/reconcile_g1_database.py
python scripts/audit/print_f8_metrics.py
```

---

## 4. Production Deployment (Docker Compose)

```bash
# Build and start PostgreSQL, Backend API, and Frontend
docker compose up -d --build

# View logs
docker compose logs -f backend
```
