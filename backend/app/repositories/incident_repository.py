from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.incident import Incident, IncidentEvent
from backend.app.models.investigation import Diagnosis, Investigation
from backend.app.models.postmortem import EngineerFeedback, Postmortem
from backend.app.models.remediation import ActionExecution, RemediationAction
from backend.app.schemas.incident import (
    ActionExecutionCreate,
    DiagnosisCreate,
    EngineerFeedbackCreate,
    IncidentCreate,
    IncidentEventCreate,
    IncidentUpdate,
    InvestigationCreate,
    PostmortemCreate,
    RemediationActionCreate,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IncidentRepository:
    """Repository handling database operations for operational incident state."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_incident(self, data: IncidentCreate) -> Incident:
        """Create a new incident in the database."""
        incident = Incident(
            incident_id=data.incident_id,
            title=data.title,
            description=data.description,
            severity=data.severity,
            status=data.status,
            source=data.source,
            affected_service=data.affected_service,
            detected_at=data.detected_at or utcnow(),
            symptoms=data.symptoms or [],
            metadata_json=data.metadata,
        )
        self.session.add(incident)
        await self.session.commit()
        await self.session.refresh(incident)

        # Record initial creation event in the chronological timeline
        initial_event = IncidentEvent(
            incident_id=incident.id,
            event_type="INCIDENT_DETECTED",
            actor=incident.source,
            message=f"Incident {incident.incident_id} detected on service '{incident.affected_service}' with severity {incident.severity}.",
            timestamp=incident.detected_at,
            payload={"severity": incident.severity, "source": incident.source, "symptoms": incident.symptoms},
        )
        self.session.add(initial_event)
        await self.session.commit()

        return incident

    async def get_incident_by_id(self, id: int) -> Optional[Incident]:
        """Retrieve an incident by primary key, eagerly loading timeline events."""
        stmt = (
            select(Incident)
            .where(Incident.id == id)
            .options(
                selectinload(Incident.events),
                selectinload(Incident.investigations),
                selectinload(Incident.diagnoses),
                selectinload(Incident.remediations),
                selectinload(Incident.executions),
                selectinload(Incident.feedbacks),
                selectinload(Incident.postmortem),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_incident_by_incident_id(self, incident_id: str) -> Optional[Incident]:
        """Retrieve an incident by business identifier (e.g. INC-7041)."""
        stmt = (
            select(Incident)
            .where(Incident.incident_id == incident_id)
            .options(
                selectinload(Incident.events),
                selectinload(Incident.investigations),
                selectinload(Incident.diagnoses),
                selectinload(Incident.remediations),
                selectinload(Incident.executions),
                selectinload(Incident.feedbacks),
                selectinload(Incident.postmortem),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_incidents(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Incident]:
        """List incidents with optional filtering by status and severity."""
        stmt = select(Incident).order_by(Incident.detected_at.desc()).limit(limit).offset(offset)
        if status:
            stmt = stmt.where(Incident.status == status)
        if severity:
            stmt = stmt.where(Incident.severity == severity)
        stmt = stmt.options(selectinload(Incident.events))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_incident(self, incident_id: int, data: IncidentUpdate) -> Optional[Incident]:
        """Update fields of an existing incident."""
        incident = await self.get_incident_by_id(incident_id)
        if not incident:
            return None

        update_dict = data.model_dump(exclude_unset=True)
        if "metadata" in update_dict:
            incident.metadata_json = update_dict.pop("metadata")

        for key, value in update_dict.items():
            setattr(incident, key, value)

        await self.session.commit()
        await self.session.refresh(incident)
        return incident

    async def add_event(self, incident_id: int, data: IncidentEventCreate) -> IncidentEvent:
        """Add a chronological timeline event to an incident."""
        event = IncidentEvent(
            incident_id=incident_id,
            event_type=data.event_type,
            actor=data.actor,
            message=data.message,
            payload=data.payload,
            timestamp=data.timestamp or utcnow(),
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def store_investigation(self, incident_id: int, data: InvestigationCreate) -> Investigation:
        """Store findings collected by Investigation Agent."""
        investigation = Investigation(
            incident_id=incident_id,
            agent_name=data.agent_name,
            findings=data.findings,
            telemetry_summary=data.telemetry_summary,
            correlated_traces=data.correlated_traces,
            started_at=data.started_at or utcnow(),
            completed_at=data.completed_at,
        )
        self.session.add(investigation)
        await self.session.commit()
        await self.session.refresh(investigation)

        # Log timeline event
        await self.add_event(
            incident_id=incident_id,
            data=IncidentEventCreate(
                event_type="INVESTIGATION_COMPLETED",
                actor=data.agent_name,
                message=f"Investigation completed: {data.findings[:100]}...",
                payload={"investigation_id": investigation.id},
            ),
        )
        return investigation

    async def store_diagnosis(self, incident_id: int, data: DiagnosisCreate) -> Diagnosis:
        """Store root-cause hypothesis and confidence from Diagnosis Agent."""
        diagnosis = Diagnosis(
            incident_id=incident_id,
            agent_name=data.agent_name,
            root_cause_hypothesis=data.root_cause_hypothesis,
            confidence_score=data.confidence_score,
            chain_of_thought=data.chain_of_thought,
            risk_assessment=data.risk_assessment,
            diagnosed_at=data.diagnosed_at or utcnow(),
        )
        self.session.add(diagnosis)
        await self.session.commit()
        await self.session.refresh(diagnosis)

        # Log timeline event
        await self.add_event(
            incident_id=incident_id,
            data=IncidentEventCreate(
                event_type="DIAGNOSIS_FORMULATED",
                actor=data.agent_name,
                message=f"Diagnosis formulated with {(data.confidence_score * 100):.0f}% confidence: {data.root_cause_hypothesis[:100]}",
                payload={"confidence": data.confidence_score, "diagnosis_id": diagnosis.id},
            ),
        )
        return diagnosis

    async def store_remediation(self, incident_id: int, data: RemediationActionCreate) -> RemediationAction:
        """Store a candidate vetted remediation action."""
        action = RemediationAction(
            incident_id=incident_id,
            action_key=data.action_key,
            title=data.title,
            description=data.description,
            command_template=data.command_template,
            safety_level=data.safety_level,
            historical_precedent=data.historical_precedent,
            is_recommended=data.is_recommended,
            created_at=utcnow(),
        )
        self.session.add(action)
        await self.session.commit()
        await self.session.refresh(action)
        return action

    async def store_execution_result(self, incident_id: int, data: ActionExecutionCreate) -> ActionExecution:
        """Store human approval, execution output, and verification result."""
        execution = ActionExecution(
            remediation_action_id=data.remediation_action_id,
            incident_id=incident_id,
            status=data.status,
            approved_by=data.approved_by,
            approval_notes=data.approval_notes,
            executed_at=data.executed_at or utcnow(),
            execution_output=data.execution_output,
            verification_status=data.verification_status,
        )
        self.session.add(execution)
        await self.session.commit()
        await self.session.refresh(execution)

        # Timeline event
        await self.add_event(
            incident_id=incident_id,
            data=IncidentEventCreate(
                event_type=f"ACTION_{data.status}",
                actor=data.approved_by or "System",
                message=f"Remediation action {data.remediation_action_id} status updated to {data.status}.",
                payload={"execution_id": execution.id, "status": data.status},
            ),
        )
        return execution

    async def store_feedback(self, incident_id: int, data: EngineerFeedbackCreate) -> EngineerFeedback:
        """Store human engineer review, rating, and feedback."""
        feedback = EngineerFeedback(
            incident_id=incident_id,
            engineer_id=data.engineer_id,
            rating=data.rating,
            comments=data.comments,
            accuracy_evaluation=data.accuracy_evaluation,
            submitted_at=utcnow(),
        )
        self.session.add(feedback)
        await self.session.commit()
        await self.session.refresh(feedback)

        # Timeline event
        await self.add_event(
            incident_id=incident_id,
            data=IncidentEventCreate(
                event_type="ENGINEER_FEEDBACK_SUBMITTED",
                actor=data.engineer_id,
                message=f"Engineer {data.engineer_id} submitted feedback with rating {data.rating}/5 stars.",
                payload={"rating": data.rating},
            ),
        )
        return feedback

    async def store_postmortem(self, incident_id: int, data: PostmortemCreate) -> Postmortem:
        """Store incident postmortem record and Hindsight memory retain flag."""
        postmortem = Postmortem(
            incident_id=incident_id,
            title=data.title,
            duration_minutes=data.duration_minutes,
            root_cause=data.root_cause,
            trigger_event=data.trigger_event,
            corrective_actions=data.corrective_actions,
            timeline=data.timeline,
            hindsight_retained=data.hindsight_retained,
            hindsight_memory_id=data.hindsight_memory_id,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        self.session.add(postmortem)
        await self.session.commit()
        await self.session.refresh(postmortem)

        # Timeline event
        await self.add_event(
            incident_id=incident_id,
            data=IncidentEventCreate(
                event_type="POSTMORTEM_SAVED",
                actor="PostmortemAgent",
                message=f"Postmortem saved: {data.title} (Duration: {data.duration_minutes}m, Retained: {data.hindsight_retained})",
                payload={"postmortem_id": postmortem.id, "hindsight_retained": data.hindsight_retained},
            ),
        )
        return postmortem
