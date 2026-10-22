import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.config import settings, config
from .core.logging import setup_logger
from .core.database import init_db
from .api import api_router
from .services.continuous_runner import continuous_autopilot

logger = setup_logger(log_level=settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup & shutdown events."""
    logger.info("==================================================")
    logger.info("   TRUCKLEAD AUTOPILOT - Backend Engine v1.0.0    ")
    logger.info("==================================================")
    logger.info("Initializing relational database schema...")
    await init_db()
    logger.info("Database schema successfully initialized.")
    if config.outreach.enable_continuous_autopilot or settings.enable_continuous_autopilot:
        logger.info("Launching Continuous Autopilot background runner...")
        await continuous_autopilot.start()
    else:
        logger.info("Continuous Autopilot background runner is standby (start via API or config).")
    yield
    logger.info("Stopping Continuous Autopilot background runner...")
    await continuous_autopilot.stop()
    logger.info("Shutting down TRUCKLEAD AUTOPILOT Engine...")


app = FastAPI(
    title="TRUCKLEAD AUTOPILOT API",
    description="Production-Oriented Lead Generation & Verification Engine for U.S. Trucking & Dispatch",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(api_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.version,
        "environment": settings.environment
    }


@app.get("/")
async def root():
    return {
        "message": "TRUCKLEAD AUTOPILOT API Engine is running.",
        "docs_url": "/docs",
        "health_url": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True
    )
