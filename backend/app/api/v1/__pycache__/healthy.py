"""
Health endpoints.
- /health        : is the app alive? (no database needed)
- /health/ready  : can the app reach the database? (runs SELECT 1)
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "version": "0.1.0",
    }


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as exc:
        return {"status": "not_ready", "database": "error", "detail": str(exc)}