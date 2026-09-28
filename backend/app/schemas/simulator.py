from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.schemas.incident import IncidentRead


class SimulateIncidentRequest(BaseModel):
    scenario: str = Field(
        ...,
        description="Scenario identifier (e.g. database_connection_pool, payment_api_latency, memory_leak, failed_deployment, dependency_service_failure)",
    )
    severity: Optional[str] = Field(
        default=None,
        description="Optional severity override (SEV-1, SEV-2, SEV-3, SEV-4 or critical, major, minor)",
    )
    environment: Optional[str] = Field(
        default="production-us-east",
        description="Target deployment environment",
    )


class ScenarioInfo(BaseModel):
    id: str
    name: str
    description: str
    default_severity: str
    primary_service: str
    affected_services: List[str]
    root_cause_type: str


class SimulateIncidentResponse(BaseModel):
    success: bool
    incident: IncidentRead
    alert_id: str
    service: str
    environment: str
    telemetry_metrics: Dict[str, Any]
    live_logs: List[str]
    traces: List[Dict[str, Any]]
    historical_match_available: bool
    suggested_hindsight_incident: Optional[str] = None
