import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.incident import Alert, Deployment, Service
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.schemas.incident import IncidentCreate, IncidentEventCreate, IncidentRead, InvestigationCreate
from backend.app.schemas.simulator import SimulateIncidentRequest, SimulateIncidentResponse
from backend.app.simulator.scenarios import get_scenario


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_severity(severity_input: Optional[str], default_sev: str) -> str:
    """Normalizes input strings like 'critical', 'major', 'sev-1' to 'SEV-1'..'SEV-4'."""
    if not severity_input:
        return default_sev

    sev_upper = severity_input.strip().upper()
    if sev_upper in ["SEV-1", "SEV-2", "SEV-3", "SEV-4"]:
        return sev_upper
    if sev_upper in ["CRITICAL", "SEV1", "P1"]:
        return "SEV-1"
    if sev_upper in ["MAJOR", "SEV2", "P2", "HIGH"]:
        return "SEV-2"
    if sev_upper in ["MODERATE", "SEV3", "P3", "MEDIUM"]:
        return "SEV-3"
    if sev_upper in ["MINOR", "SEV4", "P4", "LOW"]:
        return "SEV-4"
    return default_sev


class IncidentSimulatorEngine:
    """Deterministic Incident Simulator generating real operational database records."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = IncidentRepository(session)

    async def _ensure_service(self, service_info: dict) -> Service:
        """Ensure service exists in the operational catalog."""
        stmt = select(Service).where(Service.name == service_info["name"])
        res = await self.session.execute(stmt)
        service = res.scalar_one_or_none()
        if not service:
            service = Service(
                name=service_info["name"],
                tier=service_info.get("tier", 1),
                owner_team=service_info.get("owner_team", "sre"),
                repository_url=service_info.get("repository_url"),
                health_status=service_info.get("health_status", "OUTAGE"),
                metadata_json=service_info.get("metadata_json", {}),
                created_at=utcnow(),
            )
            self.session.add(service)
            await self.session.commit()
            await self.session.refresh(service)
        else:
            service.health_status = service_info.get("health_status", "OUTAGE")
            await self.session.commit()
            await self.session.refresh(service)
        return service

    async def _ensure_deployment(self, service_id: int, dep_info: dict) -> Deployment:
        """Ensure deployment history is present for root-cause change correlation."""
        stmt = select(Deployment).where(
            Deployment.service_id == service_id,
            Deployment.version == dep_info["version"],
        )
        res = await self.session.execute(stmt)
        deployment = res.scalar_one_or_none()
        if not deployment:
            deployment = Deployment(
                service_id=service_id,
                version=dep_info["version"],
                environment=dep_info.get("environment", "production-us-east"),
                status=dep_info.get("status", "SUCCESS"),
                deployed_by=dep_info.get("deployed_by", "release-engineer"),
                commit_hash=dep_info.get("commit_hash"),
                deployed_at=utcnow(),
            )
            self.session.add(deployment)
            await self.session.commit()
            await self.session.refresh(deployment)
        return deployment

    async def simulate(self, request: SimulateIncidentRequest) -> SimulateIncidentResponse:
        """Executes a realistic incident simulation, populating PostgreSQL operational tables."""
        scenario_data = get_scenario(request.scenario)
        if not scenario_data:
            raise ValueError(f"Unknown scenario '{request.scenario}'. Available: database_connection_pool, payment_api_latency, memory_leak, failed_deployment, dependency_service_failure")

        # 1. Resolve severity and identifiers
        severity = normalize_severity(request.severity, scenario_data["default_severity"])
        unique_suffix = uuid.uuid4().hex[:6].upper()
        incident_id = f"INC-{unique_suffix}"

        # 2. Ensure Service and Deployment records exist
        service = await self._ensure_service(scenario_data["service_info"])
        await self._ensure_deployment(service.id, scenario_data["deployment_info"])

        # 3. Create Operational Alert record
        raw_alert = scenario_data["alert"]
        alert = Alert(
            alert_id=f"{raw_alert['alert_id']}-{unique_suffix}",
            name=raw_alert["name"],
            source=raw_alert.get("source", "simulator"),
            severity=raw_alert.get("severity", "critical"),
            status="firing",
            payload=raw_alert.get("payload", {}),
            triggered_at=utcnow(),
        )
        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)

        # 4. Create Incident in PostgreSQL via Incident Repository (Same pipeline as real alerts)
        incident_create = IncidentCreate(
            incident_id=incident_id,
            title=f"[{scenario_data['primary_service']}] {scenario_data['name']}",
            description=scenario_data["description"],
            severity=severity,
            status="DETECTED",
            source="Incident Simulator Engine",
            affected_service=scenario_data["primary_service"],
            symptoms=scenario_data.get("symptoms", []),
            metadata={
                "scenario_id": request.scenario,
                "environment": request.environment,
                "alert_id": alert.alert_id,
                "affected_services": scenario_data["affected_services"],
                "root_cause_type": scenario_data["root_cause_type"],
            },
        )
        incident = await self.repo.create_incident(incident_create)

        # Link alert to incident
        alert.incident_id = incident.id
        await self.session.commit()

        # 5. Populate initial Investigation telemetry evidence
        await self.repo.store_investigation(
            incident_id=incident.id,
            data=InvestigationCreate(
                agent_name="InvestigationAgent",
                findings=f"Telemetry anomaly detected: {scenario_data['description']}",
                telemetry_summary=scenario_data.get("metrics", {}),
                correlated_traces=scenario_data.get("traces", []),
            ),
        )

        # 6. Append chronological pipeline event
        await self.repo.add_event(
            incident_id=incident.id,
            data=IncidentEventCreate(
                event_type="PIPELINE_INITIALIZED",
                actor="IncidentOrchestrator",
                message="Incident entered the active response pipeline. Dispatched Investigation and Blast Radius agents.",
                payload={"scenario": request.scenario, "severity": severity},
            ),
        )

        # 7. Fetch refreshed full incident
        full_incident = await self.repo.get_incident_by_id(incident.id)

        return SimulateIncidentResponse(
            success=True,
            incident=IncidentRead.model_validate(full_incident),
            alert_id=alert.alert_id,
            service=scenario_data["primary_service"],
            environment=request.environment or "production-us-east",
            telemetry_metrics=scenario_data.get("metrics", {}),
            live_logs=scenario_data.get("live_logs", []),
            traces=scenario_data.get("traces", []),
            historical_match_available=bool(scenario_data.get("suggested_hindsight_incident")),
            suggested_hindsight_incident=scenario_data.get("suggested_hindsight_incident"),
        )
