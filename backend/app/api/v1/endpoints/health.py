from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.db.session import check_db_health

router = APIRouter()


class HealthCheckResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    timestamp: str
    version: str
    services: Dict[str, Any]


@router.get("", response_model=HealthCheckResponse)
@router.get("/", response_model=HealthCheckResponse)
async def get_health() -> HealthCheckResponse:
    """Returns the operational status of IncidentMind API and subsystem readiness."""
    return HealthCheckResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        environment=settings.APP_ENV,
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
        services={
            "api": "operational",
            "model_configured": settings.GROQ_MODEL,
            "hindsight_configured": bool(settings.HINDSIGHT_API_KEY and settings.HINDSIGHT_API_KEY != "your_hindsight_api_key_here"),
            "groq_configured": bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY != "your_groq_api_key_here"),
            "database_url_configured": bool(settings.DATABASE_URL),
        },
    )


@router.get("/live")
async def liveness() -> Dict[str, str]:
    """Kubernetes/container liveness probe."""
    return {"status": "alive"}


@router.get("/ready")
async def readiness() -> Dict[str, Any]:
    """Kubernetes/container readiness probe."""
    database_ready = await check_db_health()
    return {
        "status": "ready" if database_ready else "degraded",
        "services": {"postgresql": "available" if database_ready else "unavailable"},
        "retryable": not database_ready,
        "message": "Database is reachable." if database_ready else "Database is temporarily unavailable; incident records have not been discarded.",
    }


@router.get("/hindsight")
async def hindsight_health() -> Dict[str, Any]:
    """Live diagnostic check for Hindsight Cloud organizational memory connection."""
    from backend.app.memory.hindsight_service import hindsight_service
    return hindsight_service.check_health()

