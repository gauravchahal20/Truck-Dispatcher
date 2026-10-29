from fastapi import APIRouter
from .routes_runs import router as runs_router
from .routes_companies import router as companies_router
from .routes_config import router as config_router
from .routes_sheets import router as sheets_router
from .routes_stats import router as stats_router
from .routes_autopilot import router as autopilot_router
from .routes_compliance import router as compliance_router
from .routes_outcomes import router as outcomes_router
from .routes_intake import router as intake_router
from .routes_reservoir import router as reservoir_router

api_router = APIRouter()
api_router.include_router(stats_router)
api_router.include_router(runs_router)
api_router.include_router(companies_router)
api_router.include_router(config_router)
api_router.include_router(sheets_router)
api_router.include_router(autopilot_router)
api_router.include_router(compliance_router)
api_router.include_router(outcomes_router)
api_router.include_router(intake_router)
api_router.include_router(reservoir_router)

__all__ = ["api_router"]
