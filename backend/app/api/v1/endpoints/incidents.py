from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.schemas.incident import (
    ActionExecutionCreate,
    ActionExecutionRead,
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
