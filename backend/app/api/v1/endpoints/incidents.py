import hmac
from typing import List, Optional
from dataclasses import asdict
import asyncio
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.orchestration.incident_orchestrator import IncidentOrchestrator
from backend.app.agents.incident_memory_agent import assess_incident_memory
from backend.app.agents.time_machine_agent import _failed_fix_warning_for_incident, build_time_machine_analysis
from backend.app.db.session import get_db
from backend.app.memory.hindsight_service import hindsight_service
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.schemas.incident import (
    ActionExecutionCreate,
    ActionExecutionRead,
    ApprovalDecisionCreate,
    ApprovalDecisionRead,
    DiagnosisCreate,
    DiagnosisRead,
    EngineerFeedbackCreate,
    EngineerFeedbackRead,
    IncidentCreate,
    IncidentEventCreate,
    IncidentEventRead,
    IncidentRead,
    IncidentUpdate,
    InvestigationCreate,
    InvestigationRead,
    PostmortemCreate,
    PostmortemRead,
    RemediationActionCreate,
    RemediationActionRead,
)

router = APIRouter()


@router.post("/demo/retain")
async def retain_demo_outcome() -> dict:
    """Best-effort retain for the deterministic payment incident demo."""
    if not hindsight_service.is_configured:
        return {
            "status": "unavailable",
            "retained": False,
            "bank_id": settings.HINDSIGHT_BANK_ID,
            "message": "Hindsight Cloud is not configured; the demo keeps its deterministic memory fixture in the UI.",
        }

    def retain() -> dict:
        incident = hindsight_service.retain_incident({
            "incident_id": "INC-DEMO-001",
            "affected_service": "payment-api",
            "severity": "SEV-1",
            "status": "resolved",
            "title": "Payment API connection pool exhaustion after deployment",
            "description": "Deterministic demo: 37% error rate, 18s latency, and 98% database connection utilization.",
            "symptoms": ["37% errors", "18 second latency", "98% database connection utilization", "deployment shortly before incident"],
            "root_cause": "Database connection pool exhaustion following deployment v2.8.4.",
            "resolution": "Corrected the connection pool settings and verified recovery in simulation.",
            "telemetry": {"error_rate_pct": 0.4, "latency_ms": 220, "connection_utilization_pct": 52},
            "logs": [],
        })
        fix = hindsight_service.retain_successful_fix(
            incident_id="INC-DEMO-001",
            service="payment-api",
            action_type="CORRECT_DATABASE_CONNECTION_POOL",
            parameters={"mode": "demo_simulation", "pool_utilization_after_pct": 52},
            rationale="Historical precedent and current pool telemetry support the correction.",
            outcome_notes="Error rate fell to 0.4% and latency to 220ms in the deterministic simulation.",
        )
        postmortem = hindsight_service.retain_postmortem(
            incident_id="INC-DEMO-001",
            service="payment-api",
            executive_summary="Connection pool saturation after deployment caused payment failures.",
            root_cause_analysis="Database connection pool exhaustion; avoid restarting the service, which failed historically.",
            lessons_learned=[
                "Use pool correction before restarting services when connection utilization is saturated.",
                "Correlate recent deployments with connection pool and latency metrics.",
            ],
            preventive_actions=["Alert on pool utilization above 90%.", "Verify pool configuration during deployment rollout."],
        )
        successful = all(isinstance(result, dict) and result.get("success") is True for result in (incident, fix, postmortem))
        return {
            "status": "retained" if successful else "unavailable",
            "retained": successful,
            "bank_id": settings.HINDSIGHT_BANK_ID,
            "message": "Demo outcome and lessons retained to Hindsight." if successful else "Hindsight retain did not complete; the deterministic demo memory remains available locally.",
        }

    try:
        return await asyncio.to_thread(retain)
    except Exception as exc:
        logger.exception("Demo Hindsight retention failed.", extra={"incident_id": "INC-DEMO-001", "error_type": type(exc).__name__})
        return {
            "status": "unavailable",
            "retained": False,
            "bank_id": settings.HINDSIGHT_BANK_ID,
            "message": "Hindsight retention failed; the deterministic demo memory remains available locally.",
        }


@router.post("/{incident_id}/orchestrate")
def retry_incident_analysis(incident_id: str) -> dict:
    """Retry analysis for a persisted incident; execution still requires human approval."""
    try:
        state = IncidentOrchestrator().run(incident_id)
        return asdict(state)
    except Exception as exc:
        logger.exception("Incident analysis retry failed.", extra={
            "incident_id": incident_id,
            "error_type": type(exc).__name__,
            "retryable": True,
        })
        return {
            "incident_id": incident_id,
            "status": "failed",
            "current_step": "RETRY",
            "retryable": True,
            "message": "Analysis could not be completed. The incident remains saved; retry when dependent services recover.",
        }


def require_operator_authorization(authorization: Optional[str] = Header(None, alias="Authorization")) -> None:
    if settings.APP_ENV.lower() in {"development", "test"}:
        return

    expected_token = (settings.OPERATOR_API_TOKEN or "").strip()
    if not expected_token:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Operator authorization is not configured.")

    scheme, separator, credentials = (authorization or "").partition(" ")
    provided_token = credentials.strip() if separator and scheme.lower() == "bearer" else ""
    if not provided_token or not hmac.compare_digest(provided_token, expected_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Operator authorization is required.")


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
async def create_incident(
    data: IncidentCreate,
    db: AsyncSession = Depends(get_db),
) -> IncidentRead:
    """Create a new incident record in PostgreSQL."""
    repo = IncidentRepository(db)
    existing = await repo.get_incident_by_incident_id(data.incident_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Incident with ID '{data.incident_id}' already exists.",
        )
    incident = await repo.create_incident(data)
    # Refresh to load initial timeline event
    full_incident = await repo.get_incident_by_id(incident.id)
    return IncidentRead.model_validate(full_incident)


@router.get("", response_model=List[IncidentRead])
async def list_incidents(
    status: Optional[str] = Query(None, description="Filter by operational status"),
    severity: Optional[str] = Query(None, description="Filter by severity (SEV-1 to SEV-4)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> List[IncidentRead]:
    """List incidents with optional filtering."""
    repo = IncidentRepository(db)
    incidents = await repo.list_incidents(status=status, severity=severity, limit=limit, offset=offset)
    return [IncidentRead.model_validate(inc) for inc in incidents]


@router.get("/organizational-memory")
async def get_organizational_memory(
    incident_id: str = Query(..., min_length=3, max_length=50),
    service: str = Query(..., min_length=2, max_length=100),
    query: str = Query(..., min_length=3, max_length=500),
    limit: int = Query(5, ge=1, le=10),
) -> dict:
    """Return categorized Hindsight records for the selected incident context."""
    # Hindsight's SDK is synchronous. Keep network waits off the ASGI event loop.
    result = await asyncio.to_thread(
        hindsight_service.recall_organizational_memories,
        query=query,
        service=service,
        limit=limit,
    )
    return {
        "current_incident": {
            "incident_id": incident_id,
            "service": service,
            "query": query,
        },
        **result,
    }


@router.get("/{incident_id}", response_model=IncidentRead)
async def get_incident(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
) -> IncidentRead:
    """Get incident by business identifier (e.g. INC-7041) or integer ID."""
    repo = IncidentRepository(db)
    incident = None
    if incident_id.isdigit():
        incident = await repo.get_incident_by_id(int(incident_id))
    if not incident:
        incident = await repo.get_incident_by_incident_id(incident_id)

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found.",
        )
    return IncidentRead.model_validate(incident)


@router.get("/{incident_id}/memory")
async def get_incident_memory(
    incident_id: str,
) -> dict:
    """Return the Hindsight-based historical memory for an incident."""
    return await asyncio.to_thread(assess_incident_memory, incident_id)


@router.get("/{incident_id}/time-machine")
async def get_incident_time_machine(
    incident_id: str,
) -> dict:
    """Return historical action comparison data for candidate remediation decisions."""
    from backend.app.tools import get_incident_details

    incident_data = get_incident_details({"incident_id": incident_id})
    if not incident_data.get("ok"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found.")

    incident = incident_data["data"]["incident"]
    comparison, warning = await asyncio.gather(
        asyncio.to_thread(build_time_machine_analysis, incident_id),
        asyncio.to_thread(_failed_fix_warning_for_incident, incident_id),
    )

    return {
        "incident_id": incident_id,
        "service": incident.get("service"),
        "historical_action_comparison": comparison,
        "failed_fix_warning": warning,
    }


@router.patch("/{id}", response_model=IncidentRead)
async def update_incident(
    id: int,
    data: IncidentUpdate,
    db: AsyncSession = Depends(get_db),
) -> IncidentRead:
    """Update fields on an existing incident."""
    repo = IncidentRepository(db)
    incident = await repo.update_incident(id, data)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {id} not found.",
        )
    return IncidentRead.model_validate(incident)


@router.post("/{id}/events", response_model=IncidentEventRead, status_code=status.HTTP_201_CREATED)
async def add_incident_event(
    id: int,
    data: IncidentEventCreate,
    db: AsyncSession = Depends(get_db),
) -> IncidentEventRead:
    """Add a chronological timeline event to the incident."""
    repo = IncidentRepository(db)
    incident = await repo.get_incident_by_id(id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {id} not found.")
    event = await repo.add_event(id, data)
    return IncidentEventRead.model_validate(event)


@router.post("/{id}/investigations", response_model=InvestigationRead, status_code=status.HTTP_201_CREATED)
async def store_investigation(
    id: int,
    data: InvestigationCreate,
    db: AsyncSession = Depends(get_db),
) -> InvestigationRead:
    """Store investigation findings collected by Investigation Agent."""
    repo = IncidentRepository(db)
    incident = await repo.get_incident_by_id(id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {id} not found.")
    investigation = await repo.store_investigation(id, data)
    return InvestigationRead.model_validate(investigation)


@router.post("/{id}/diagnoses", response_model=DiagnosisRead, status_code=status.HTTP_201_CREATED)
async def store_diagnosis(
    id: int,
    data: DiagnosisCreate,
    db: AsyncSession = Depends(get_db),
) -> DiagnosisRead:
    """Store diagnosis hypothesis formulated by Diagnosis Agent."""
    repo = IncidentRepository(db)
    incident = await repo.get_incident_by_id(id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {id} not found.")
    diagnosis = await repo.store_diagnosis(id, data)
    return DiagnosisRead.model_validate(diagnosis)


@router.post("/{id}/remediations", response_model=RemediationActionRead, status_code=status.HTTP_201_CREATED)
async def store_remediation_action(
    id: int,
    data: RemediationActionCreate,
    db: AsyncSession = Depends(get_db),
) -> RemediationActionRead:
    """Store candidate vetted remediation action."""
    repo = IncidentRepository(db)
    incident = await repo.get_incident_by_id(id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {id} not found.")
    action = await repo.store_remediation(id, data)
    return RemediationActionRead.model_validate(action)


@router.post("/{id}/executions", response_model=ActionExecutionRead, status_code=status.HTTP_201_CREATED)
async def store_action_execution(
    id: int,
    data: ActionExecutionCreate,
    db: AsyncSession = Depends(get_db),
    _operator: None = Depends(require_operator_authorization),
) -> ActionExecutionRead:
    """Store human approval, execution output, and verification status."""
    repo = IncidentRepository(db)
    incident = await repo.get_incident_by_id(id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {id} not found.")
    execution = await repo.store_execution_result(id, data)
    return ActionExecutionRead.model_validate(execution)


@router.post("/{id}/feedback", response_model=EngineerFeedbackRead, status_code=status.HTTP_201_CREATED)
async def store_engineer_feedback(
    id: int,
    data: EngineerFeedbackCreate,
    db: AsyncSession = Depends(get_db),
) -> EngineerFeedbackRead:
    """Store human engineer rating and postmortem feedback."""
    repo = IncidentRepository(db)
    incident = await repo.get_incident_by_id(id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {id} not found.")
    feedback = await repo.store_feedback(id, data)
    return EngineerFeedbackRead.model_validate(feedback)


@router.post("/{id}/approval", response_model=ApprovalDecisionRead, status_code=status.HTTP_200_OK)
async def record_approval_decision(
    id: int,
    data: ApprovalDecisionCreate,
    db: AsyncSession = Depends(get_db),
    _operator: None = Depends(require_operator_authorization),
) -> ApprovalDecisionRead:
    """Record the engineer decision, including simulate-only execution output and recovery status."""
    repo = IncidentRepository(db)
    incident = await repo.get_incident_by_id(id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {id} not found.")

    effective_action = data.action
    execution_result = {
        "mode": "simulated",
        "action": effective_action,
        "recovered": False,
        "details": "Approval is recorded; no remediation simulator or production telemetry verification was run.",
        "status": "APPROVED_PENDING_SIMULATION" if data.action == "approve" else "MODIFIED_PENDING_SIMULATION",
    }

    if data.action == "reject":
        execution_result["recovered"] = False
        execution_result["status"] = "REJECTED"
        execution_result["details"] = "Action rejected by engineer; no live remediation was executed in this demo."
    elif data.action == "modify":
        execution_result["details"] = "Modified recommendation recorded; no remediation simulator or production telemetry verification was run."

    if data.action == "approve":
        execution_result["details"] = "Engineer approval recorded. No live command execution or recovery is claimed."

    payload = data.model_copy(update={"execution_result": execution_result})
    saved = await repo.store_approval_decision(id, payload)
    saved_dict = {
        "id": saved.id,
        "incident_id": saved.incident_id,
        "engineer": saved.engineer,
        "action": saved.action,
        "original_recommendation": saved.original_recommendation,
        "modified_recommendation": saved.modified_recommendation,
        "reason": saved.reason,
        "timestamp": saved.timestamp,
        "execution_result": execution_result,
    }
    return ApprovalDecisionRead.model_validate(saved_dict)


@router.post("/{id}/postmortem", response_model=PostmortemRead, status_code=status.HTTP_201_CREATED)
async def store_postmortem(
    id: int,
    data: PostmortemCreate,
    db: AsyncSession = Depends(get_db),
) -> PostmortemRead:
    """Store postmortem record with Hindsight memory retain flag."""
    repo = IncidentRepository(db)
    incident = await repo.get_incident_by_id(id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {id} not found.")
    postmortem = await repo.store_postmortem(id, data)
    return PostmortemRead.model_validate(postmortem)
