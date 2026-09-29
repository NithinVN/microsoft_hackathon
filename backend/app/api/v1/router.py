from fastapi import APIRouter
from backend.app.api.v1.endpoints import health, incidents, simulator, webhooks

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(simulator.router, prefix="/incidents", tags=["Simulator"])
api_router.include_router(incidents.router, prefix="/incidents", tags=["Incidents"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
