# TRUCKLEAD AUTOPILOT (GENLEAD)

> **Autonomous Freight & Carrier Lead Generation, Deep-Enrichment, and 10-Point Verification Engine**  
> Designed for U.S. Freight Brokerages, Dispatch Services, and Fleet Operators.

---

## Quick Navigation

- **System Architecture & Technical Blueprint**: [`ARCHITECTURE.md`](file:///f:/GAURAV/GENLEAD/ARCHITECTURE.md)
- **Master Project Information & Operations Manual**: [`PROJECT_INFO.md`](file:///f:/GAURAV/GENLEAD/PROJECT_INFO.md)
- **Backend API**: `http://127.0.0.1:8000` (Docs: `http://127.0.0.1:8000/docs`)
- **Frontend Dashboard**: `http://127.0.0.1:5173`

---

## Core Capabilities

1. **100% Real Live Data Pipeline**: No static mock datasets. Discovers real active U.S. motor carriers and direct shippers dynamically from official registries and live web sources.
2. **Dual-Persona Targeting**:
   - **Carriers**: Fleets with 1–10 trucks seeking dispatch support and higher revenue loads.
   - **Direct Shippers**: Manufacturing plants, distribution centers, and warehouses with outbound freight demand.
3. **10-Point Grounded Verification Engine**: Evaluates federal authority, safety ratings, phone validity, equipment types, and physical yard addresses with evidence notes.
4. **Weighted Scoring (0–10) & Prioritization**: Automatically classifies prospects into Priority A (Ready for outreach), Priority B, and Priority C.
5. **Zero-403 Safe URLs**: Prevents government WAF blocks by automatically resolving carrier profiles to open public links (`https://usdotlookup.com/carrier/{usdot}`) with zero 403 Forbidden errors.
6. **Continuous 24/7 Autopilot**: Background runner that executes scheduled discovery sweeps across target states.
7. **Google Sheets Live Sync**: Exports qualified leads with verified decision-maker emails, direct phones, and AI outreach scripts.

---

## Quick Start

### 1. Backend Server (FastAPI)
```bash
# Activate virtual environment
.\venv\Scripts\activate

# Launch FastAPI server
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend Application (React + Vite)
```bash
# In a new terminal
cd frontend
npm run dev
```

### 3. Run Automated Tests
```bash
.\venv\Scripts\python.exe -m pytest backend/tests
```

For full system details, workflows, and operational manuals, see [`PROJECT_INFO.md`](file:///f:/GAURAV/GENLEAD/PROJECT_INFO.md).
