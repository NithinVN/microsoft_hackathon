from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.incident import Alert, Incident
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.schemas.incident import IncidentCreate, IncidentEventCreate, InvestigationCreate


from backend.app.tools.incident_response_tools import register_runtime_incident


def normalize_severity(severity_input: Optional[str], default_sev: str = "SEV-2") -> str:
    """Map common alert severity names to the Incident severity contract."""
    if not severity_input:
        return default_sev

    normalized = str(severity_input).strip().upper().replace("_", "-")
    if normalized in {"SEV-1", "SEV-2", "SEV-3", "SEV-4"}:
        return normalized
    if normalized in {"CRITICAL", "SEV0", "SEV-0", "0", "SEV1", "1", "P1", "FATAL", "EMERGENCY"}:
        return "SEV-1"
    if normalized in {"MAJOR", "SEV2", "2", "P2", "HIGH", "WARNING", "WARN"}:
        return "SEV-2"
    if normalized in {"MODERATE", "SEV3", "3", "P3", "MEDIUM"}:
        return "SEV-3"
    if normalized in {"MINOR", "SEV4", "4", "P4", "LOW", "INFO", "INFORMATIONAL", "VERBOSE"}:
        return "SEV-4"
    return default_sev


class IncidentIntakeService:
    """Shared creation and pipeline handoff for simulated and external alerts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = IncidentRepository(session)

    async def create_from_alert(
        self,
        incident_data: IncidentCreate,
        alert_data: Dict[str, Any],
        *,
        findings: str,
        telemetry_summary: Optional[Dict[str, Any]] = None,
        correlated_traces: Optional[List[Dict[str, Any]]] = None,
        pipeline_payload: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Alert, Incident]:
        incident = await self.repository.create_incident(incident_data)
        alert = Alert(
            alert_id=alert_data["alert_id"],
            incident_id=incident.id,
            name=alert_data["name"],
            source=alert_data.get("source", "alertmanager"),
            severity=alert_data.get("severity", "warning"),
            status=alert_data.get("status", "firing"),
            payload=alert_data.get("payload", {}),
            triggered_at=alert_data.get("triggered_at") or incident.detected_at,
            resolved_at=alert_data.get("resolved_at"),
        )
        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)

        await self.repository.store_investigation(
            incident_id=incident.id,
            data=InvestigationCreate(
                agent_name="InvestigationAgent",
                findings=findings,
                telemetry_summary=telemetry_summary or {},
                correlated_traces=correlated_traces or [],
            ),
        )
        await self.repository.add_event(
            incident_id=incident.id,
            data=IncidentEventCreate(
                event_type="PIPELINE_INITIALIZED",
                actor="IncidentOrchestrator",
                message="Incident entered the active response pipeline. Dispatched Investigation and Blast Radius agents.",
                payload=pipeline_payload or {"severity": incident.severity, "source": incident.source},
            ),
        )

        register_runtime_incident({
            "incident_id": incident.incident_id,
            "timestamp": (incident.detected_at or datetime.now(timezone.utc)).isoformat(),
            "service": incident.affected_service,
            "title": incident.title,
            "severity": incident.severity,
            "status": incident.status,
            "symptoms": incident.symptoms or [],
            "alerts": [alert.name],
            "relevant_metrics": telemetry_summary or {},
            "deployment_context": {},
            "root_cause": None,
            "actions_attempted": [],
            "successful_actions": [],
            "failed_actions": [],
            "resolution_time_minutes": None,
            "final_outcome": None,
            "engineer_feedback": {},
            "lessons_learned": [],
        })

        full_incident = await self.repository.get_incident_by_id(incident.id)
        return alert, full_incident or incident

    async def resolve_alert(
        self,
        alert: Alert,
        resolved_at: datetime,
        payload: Dict[str, Any],
    ) -> Optional[Incident]:
        """Resolve the incident linked to an active alert, idempotently."""
        alert.status = "resolved"
        alert.resolved_at = resolved_at
        alert.payload = {**(alert.payload or {}), "resolution": payload}
        await self.session.commit()

        if alert.incident_id is None:
            return None

        incident = await self.repository.get_incident_by_id(alert.incident_id)
        if incident is None:
            return None

        if incident.status != "RESOLVED":
            incident.status = "RESOLVED"
            incident.resolved_at = resolved_at
            resolution_key = f"{alert.source}_resolution"
            incident.metadata_json = {
                **(incident.metadata_json or {}),
                resolution_key: payload,
            }
            if alert.source == "alertmanager":
                incident.metadata_json["alertmanager_resolution"] = payload
            await self.session.commit()

            actor_name = "AzureMonitor" if "azure" in (alert.source or "").lower() else "Alertmanager"
            await self.repository.add_event(
                incident_id=incident.id,
                data=IncidentEventCreate(
                    event_type="ALERT_RESOLVED",
                    actor=actor_name,
                    message=f"Alert '{alert.name}' resolved; incident marked resolved.",
                    timestamp=resolved_at,
                    payload=payload,
                ),
            )
        return await self.repository.get_incident_by_id(incident.id)
