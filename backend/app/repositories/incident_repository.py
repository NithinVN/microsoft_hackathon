from datetime import datetime, timezone
from typing import Any, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.incident import Incident, IncidentEvent
from backend.app.models.investigation import Diagnosis, Investigation
from backend.app.models.postmortem import EngineerFeedback, Postmortem
from backend.app.models.remediation import ActionExecution, ApprovalDecision, RemediationAction
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

    async def _build_postmortem_for_incident(self, incident: Incident) -> PostmortemCreate:
        """Synthesize the required resolved-incident learning summary from database evidence."""
        diagnosis = incident.diagnoses[-1].root_cause_hypothesis if incident.diagnoses else incident.description or incident.title
        successful_actions = []
        failed_actions = []
        failed_reasons = []
        attempted_actions = []

        remediation_map = {remediation.id: remediation for remediation in incident.remediations or []}
        for execution in incident.executions or []:
            action_title = "remediation action"
            remediation = remediation_map.get(execution.remediation_action_id)
            if remediation:
                action_title = remediation.title
                attempted_actions.append(remediation.title)

            if execution.status in {"VERIFIED_RECOVERED", "APPROVED", "SUCCESS", "RECOVERED", "RESOLVED"}:
                successful_actions.append(action_title)
            else:
                failed_actions.append(action_title)
                if execution.approval_notes:
                    failed_reasons.append(execution.approval_notes)

        feedback_comments = [entry.comments for entry in incident.feedbacks or []]
        lessons = list(filter(None, [
            *[f"Do not repeat: {item}" for item in failed_actions],
            *feedback_comments,
            f"Observe and protect against the root cause: {diagnosis}",
        ]))

        timeline = [{"time": event.timestamp.strftime("%H:%M"), "event": event.message} for event in incident.events or []]
        memory_id = f"HINDSIGHT-{incident.incident_id.upper()}"
        detection_message = incident.description or incident.title
        impact_summary = f"Customers and dependent services were affected while {incident.affected_service} was degraded."
        final_resolution = "; ".join(successful_actions) if successful_actions else "Incident recovered through validated monitoring and stabilization."

        return PostmortemCreate(
            title=f"{incident.title} Postmortem",
            duration_minutes=int((incident.resolved_at - incident.detected_at).total_seconds() // 60) if incident.resolved_at else 0,
            root_cause=diagnosis,
            trigger_event=incident.description or incident.title,
            what_happened=incident.description or f"Incident {incident.incident_id} affected {incident.affected_service}.",
            incident_summary=incident.description or f"Incident {incident.incident_id} affected {incident.affected_service} during {incident.status.lower()}.",
            impact=impact_summary,
            detection=detection_message,
            what_worked=successful_actions,
            what_failed=failed_actions,
            why_it_failed="; ".join(failed_reasons) if failed_reasons else "No failed remediation actions were observed in the final workflow.",
            contributing_factors="; ".join(filter(None, [incident.description, *feedback_comments])) or "Operational pressure and missing guardrails contributed to the event.",
            actual_outcome=final_resolution,
            final_resolution=final_resolution,
            engineer_corrections=feedback_comments,
            engineer_feedback="; ".join(feedback_comments) if feedback_comments else "No engineer feedback recorded.",
            lessons_learned=lessons,
            future_prevention="Prevent recurrence by retaining the proven fix, hardening guardrails, and escalating alerts before customer impact grows.",
            corrective_actions=successful_actions or ["Continue monitoring and verify the root cause remediation."],
            timeline=timeline,
            hindsight_retained=True,
            hindsight_memory_id=memory_id,
        )

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

        reloaded_incident = await self.get_incident_by_id(incident_id)
        if str(getattr(incident, "status", "")).upper() == "RESOLVED" and reloaded_incident is not None and reloaded_incident.postmortem is None:
            postmortem = await self.store_postmortem(incident.id, await self._build_postmortem_for_incident(reloaded_incident))
            reloaded_incident.postmortem = postmortem
            await self.session.flush()

        return reloaded_incident or incident

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

    async def store_approval_decision(self, incident_id: int, data: Any) -> ApprovalDecision:
        """Persist a human approval, reject, or modify decision and its simulated outcome."""
        import json

        decision = ApprovalDecision(
            incident_id=incident_id,
            engineer=data.engineer,
            action=data.action,
            original_recommendation=data.original_recommendation,
            modified_recommendation=getattr(data, "modified_recommendation", None),
            reason=data.reason,
            timestamp=data.timestamp or utcnow(),
            execution_result=json.dumps(data.execution_result or {}),
        )
        self.session.add(decision)
        await self.session.commit()
        await self.session.refresh(decision)
        return decision

    async def store_postmortem(self, incident_id: int, data: PostmortemCreate) -> Postmortem:
        """Store incident postmortem record and Hindsight memory retain flag."""
        incident = await self.get_incident_by_id(incident_id)
        if incident is None:
            raise ValueError(f"Incident {incident_id} not found")

        memory_id = data.hindsight_memory_id or f"HINDSIGHT-{incident.incident_id.upper()}"
        postmortem = Postmortem(
            incident_id=incident_id,
            title=data.title,
            duration_minutes=data.duration_minutes,
            root_cause=data.root_cause,
            trigger_event=data.trigger_event,
            incident_summary=data.incident_summary,
            impact=data.impact,
            detection=data.detection,
            what_happened=data.what_happened,
            what_worked=data.what_worked,
            what_failed=data.what_failed,
            why_it_failed=data.why_it_failed,
            contributing_factors=data.contributing_factors,
            actual_outcome=data.actual_outcome,
            final_resolution=data.final_resolution,
            engineer_corrections=data.engineer_corrections,
            engineer_feedback=data.engineer_feedback,
            lessons_learned=data.lessons_learned,
            future_prevention=data.future_prevention,
            corrective_actions=data.corrective_actions,
            timeline=data.timeline,
            hindsight_retained=data.hindsight_retained,
            hindsight_memory_id=memory_id,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        self.session.add(postmortem)
        await self.session.commit()
        await self.session.refresh(postmortem)

        postmortem_id = postmortem.id
        incident.postmortem = postmortem
        await self.session.commit()

        if data.hindsight_retained:
            from backend.app.memory.hindsight_service import hindsight_service

            incident_payload = {
                "incident_id": incident.incident_id,
                "title": incident.title,
                "affected_service": incident.affected_service,
                "severity": incident.severity,
                "status": "resolved",
                "description": incident.description or data.what_happened,
                "symptoms": incident.symptoms,
                "root_cause": data.root_cause,
                "resolution": "; ".join(data.corrective_actions or data.what_worked or ["Incident resolved"]),
                "detected_at": incident.detected_at.isoformat(),
            }
            hindsight_service.retain_incident(incident_payload)
            hindsight_service.retain_root_cause(
                incident_id=incident.incident_id,
                service=incident.affected_service,
                root_cause=data.root_cause,
                evidence={
                    "what_happened": data.what_happened,
                    "why_it_failed": data.why_it_failed,
                    "timeline": data.timeline,
                },
            )

            remediation_map = {remediation.id: remediation for remediation in incident.remediations or []}
            for execution in incident.executions or []:
                remediation = remediation_map.get(execution.remediation_action_id)
                if not remediation:
                    continue

                params = {
                    "action_key": remediation.action_key,
                    "title": remediation.title,
                    "description": remediation.description,
                    "safety_level": remediation.safety_level,
                    "historical_precedent": remediation.historical_precedent,
                }
                normalized_status = str(execution.status or "").upper()
                if normalized_status in {"VERIFIED_RECOVERED", "APPROVED", "SUCCESS", "RECOVERED", "RESOLVED"}:
                    hindsight_service.retain_successful_fix(
                        incident_id=incident.incident_id,
                        service=incident.affected_service,
                        action_type=remediation.action_key,
                        parameters=params,
                        rationale=execution.approval_notes or remediation.description,
                        outcome_notes=execution.execution_output or data.actual_outcome or "Recovery verified.",
                    )
                else:
                    hindsight_service.retain_failed_fix(
                        incident_id=incident.incident_id,
                        service=incident.affected_service,
                        action_type=remediation.action_key,
                        parameters=params,
                        failure_reason=execution.approval_notes or execution.execution_output or "Failed remediation action was attempted during the incident.",
                        unintended_consequences=execution.execution_output or "Action failed and was not retained as the final fix.",
                    )

            for feedback in incident.feedbacks or []:
                hindsight_service.retain_engineer_feedback(
                    incident_id=incident.incident_id,
                    service=incident.affected_service,
                    engineer_id=feedback.engineer_id,
                    rating=f"{feedback.rating}_stars",
                    feedback_text=feedback.comments,
                    tags=["postmortem", "engineer_correction"],
                )

            hindsight_service.retain_postmortem(
                incident_id=incident.incident_id,
                service=incident.affected_service,
                executive_summary=data.what_happened or incident.description or data.incident_summary,
                root_cause_analysis=data.root_cause,
                lessons_learned=data.lessons_learned or ["Incident was resolved with evidence-based remediation."],
                preventive_actions=data.corrective_actions or ["Monitor and harden the service against the root cause."],
            )

        # Timeline event
        await self.add_event(
            incident_id=incident_id,
            data=IncidentEventCreate(
                event_type="POSTMORTEM_SAVED",
                actor="PostmortemAgent",
                message=f"Postmortem saved: {data.title} (Duration: {data.duration_minutes}m, Retained: {data.hindsight_retained})",
                payload={"postmortem_id": postmortem_id, "hindsight_retained": data.hindsight_retained, "hindsight_memory_id": memory_id},
            ),
        )
        return postmortem
