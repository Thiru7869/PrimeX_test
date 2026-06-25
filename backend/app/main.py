"""
The application entry point. This is what we run.
It creates the FastAPI app, sets up logging and CORS, and wires in our routes.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import health
from app.core.config import settings
from app.core.logging import get_logger, setup_logging

# Set up logging before anything else.
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the server starts...
    logger.info("application_startup", environment=settings.ENVIRONMENT)
    yield
    # ...and once when it stops.
    logger.info("application_shutdown")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS = which web origins may call this API. The frontend needs this.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all v1 routes under /api/v1
app.include_router(health.router, prefix="/api/v1", tags=["health"])


@app.get("/")
async def root():
    return {"message": "PrimeX AI API is running", "docs": "/docs"}