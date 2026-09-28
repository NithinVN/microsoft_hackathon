from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.core.config import settings

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
async def readiness() -> Dict[str, str]:
    """Kubernetes/container readiness probe."""
    return {"status": "ready"}


@router.get("/hindsight")
async def hindsight_health() -> Dict[str, Any]:
    """Live diagnostic check for Hindsight Cloud organizational memory connection."""
    from backend.app.memory.hindsight_service import hindsight_service
    return hindsight_service.check_health()

