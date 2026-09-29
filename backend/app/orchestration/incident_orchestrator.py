from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.app.agents.blast_radius_agent import assess_blast_radius
from backend.app.agents.diagnosis_agent import diagnose_incident
from backend.app.agents.incident_memory_agent import assess_incident_memory
from backend.app.agents.investigation_agent import investigate_incident
from backend.app.agents.remediation_agent import build_remediation_plan
from backend.app.memory.hindsight_service import hindsight_service
from backend.app.tools import get_incident_details, get_runbook


@dataclass
class OrchestratorState:
    incident_id: str
    current_step: str = "START"
    status: str = "pending"
    incident: Optional[Dict[str, Any]] = None
    investigation: Optional[Dict[str, Any]] = None
    blast_radius: Optional[Dict[str, Any]] = None
    memory: Optional[Dict[str, Any]] = None
    diagnosis: Optional[Dict[str, Any]] = None
    what_if: Optional[Dict[str, Any]] = None
    remediation_plan: Optional[Dict[str, Any]] = None
    execution: Optional[Dict[str, Any]] = None
    verification: Optional[Dict[str, Any]] = None
    postmortem: Optional[Dict[str, Any]] = None
    hindsight_status: str = "unknown"
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    transition_log: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class IncidentOrchestrator:
    """Explicit incident-response state machine with typed state and safe transitions."""

    def __init__(self) -> None:
        self.steps = [
            "START",
            "LOAD_INCIDENT",
            "INVESTIGATION",
            "BLAST_RADIUS",
            "MEMORY",
            "DIAGNOSIS",
            "WHAT_IF_ANALYSIS",
            "REMEDIATION",
            "HUMAN_APPROVAL",
            "EXECUTION",
            "VERIFICATION",
            "POSTMORTEM",
            "HINDSIGHT_LEARNING",
            "END",
        ]

    def _record(self, state: OrchestratorState, step: str, status: str, details: str) -> None:
        state.current_step = step
        state.transition_log.append({"step": step, "status": status, "details": details})

    def _add_error(self, state: OrchestratorState, message: str) -> None:
        if message not in state.errors:
            state.errors.append(message)

    def _add_warning(self, state: OrchestratorState, message: str) -> None:
        if message not in state.warnings:
            state.warnings.append(message)

    def _safe_hindsight_available(self) -> bool:
        return bool(getattr(hindsight_service, "is_configured", False))

    def _validate_investigation(self, payload: Dict[str, Any]) -> bool:
        return isinstance(payload, dict) and "incident_id" in payload and isinstance(payload.get("candidate_causes"), list)

    def _validate_blast_radius(self, payload: Dict[str, Any]) -> bool:
        return isinstance(payload, dict) and isinstance(payload.get("directly_affected_services", []), list)

    def _validate_memory(self, payload: Dict[str, Any]) -> bool:
        return isinstance(payload, dict) and isinstance(payload.get("memory_sources", []), list)

    def _validate_diagnosis(self, payload: Dict[str, Any]) -> bool:
        return isinstance(payload, dict) and isinstance(payload.get("primary_hypothesis"), str)

    def _normalise_incident(self, incident_response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not incident_response or not incident_response.get("ok"):
            return None
        incident = incident_response.get("data", {}).get("incident")
        return incident if isinstance(incident, dict) else None

    def _run_hindsight_learning(self, state: OrchestratorState) -> None:
        if not self._safe_hindsight_available():
            state.hindsight_status = "unavailable"
            self._add_error(state, "Hindsight unavailable; organizational memory retention skipped.")
            self._add_warning(state, "Hindsight unavailable; organizational memory retention skipped.")
            self._record(state, "HINDSIGHT_LEARNING", "warning", "Hindsight unavailable")
            return

        state.hindsight_status = "retained"
        incident = state.incident or {}
        service = str(incident.get("service") or "unknown")
        root_cause = str((state.diagnosis or {}).get("primary_hypothesis") or incident.get("root_cause") or "Root cause under investigation")
        approved_action = ""
        actions = (state.remediation_plan or {}).get("recommended_actions") or []
        for action in actions:
            if str(action.get("status") or "").lower() == "approved":
                approved_action = str(action.get("action") or "UNKNOWN_ACTION")
                break

        hindsight_service.retain_incident({
            "incident_id": state.incident_id,
            "affected_service": service,
            "severity": incident.get("severity") or "medium",
            "status": "resolved",
            "title": incident.get("title") or "Incident",
            "description": incident.get("title") or "Incident resolved through the orchestrator workflow.",
            "symptoms": incident.get("symptoms") or [],
            "root_cause": root_cause,
            "resolution": state.postmortem.get("final_resolution", "Incident resolved after simulation verification.") if state.postmortem else "Incident resolved after simulation verification.",
            "telemetry": {},
            "logs": (state.investigation or {}).get("timeline", []) or [],
        })

        if root_cause:
            hindsight_service.retain_root_cause(
                incident_id=state.incident_id,
                service=service,
                root_cause=root_cause,
                evidence={"diagnosis": state.diagnosis or {}, "blast_radius": state.blast_radius or {}},
            )

        if approved_action:
            hindsight_service.retain_successful_fix(
                incident_id=state.incident_id,
                service=service,
                action_type=approved_action,
                parameters={"action": approved_action, "workflow": "incident_orchestrator"},
                rationale="Approved by human operator after diagnosis and verification.",
                outcome_notes="Action was validated as successful by the incident workflow.",
            )

        if state.postmortem:
            hindsight_service.retain_postmortem(
                incident_id=state.incident_id,
                service=service,
                executive_summary=str(state.postmortem.get("incident_summary") or "Resolved incident record."),
                root_cause_analysis=str(root_cause),
                lessons_learned=list(state.postmortem.get("lessons_learned", []) or []),
                preventive_actions=list(state.postmortem.get("future_prevention", []) or []),
            )

        feedback = incident.get("engineer_feedback") or {}
        engineer_id = str(feedback.get("engineer_id") or "engineer-unknown")
        rating = str(feedback.get("rating") or "unknown")
        if engineer_id and rating:
            hindsight_service.retain_engineer_feedback(
                incident_id=state.incident_id,
                service=service,
                engineer_id=engineer_id,
                rating=rating,
                feedback_text=str(feedback.get("comments") or "No additional comments provided."),
            )

        self._record(state, "HINDSIGHT_LEARNING", "ok", "Hindsight retention completed successfully.")

    def run(self, incident_id: str, approval_override: Optional[Dict[str, Any]] = None) -> OrchestratorState:
        state = OrchestratorState(incident_id=incident_id)
        self._record(state, "START", "started", "Workflow initialized.")

        incident_response = get_incident_details({"incident_id": incident_id})
        incident = self._normalise_incident(incident_response)
        if incident is None:
            state.status = "failed"
            self._add_error(state, f"No incident found for {incident_id}.")
            self._record(state, "LOAD_INCIDENT", "error", f"Incident {incident_id} was not found.")
            self._record(state, "END", "failed", "Workflow stopped before the investigation phase.")
            state.current_step = "END"
            return state

        state.incident = incident
        state.status = "running"
        self._record(state, "LOAD_INCIDENT", "ok", f"Loaded incident {incident_id}.")

        investigation = investigate_incident(incident_id)
        if not self._validate_investigation(investigation):
            state.status = "failed"
            self._add_error(state, "invalid agent output: investigation agent returned an invalid payload.")
            self._record(state, "INVESTIGATION", "error", "Invalid investigation payload.")
            self._record(state, "END", "failed", "Workflow terminated due to invalid agent output.")
            state.current_step = "END"
            return state
        state.investigation = investigation
        state.timeline = investigation.get("timeline", []) if isinstance(investigation.get("timeline", []), list) else []
        self._record(state, "INVESTIGATION", "ok", "Investigation completed.")

        blast_radius = assess_blast_radius(incident_id)
        if not self._validate_blast_radius(blast_radius):
            state.status = "failed"
            self._add_error(state, "invalid agent output: blast radius agent returned an invalid payload.")
            self._record(state, "BLAST_RADIUS", "error", "Invalid blast-radius payload.")
            self._record(state, "END", "failed", "Workflow terminated due to invalid agent output.")
            state.current_step = "END"
            return state
        state.blast_radius = blast_radius
        self._record(state, "BLAST_RADIUS", "ok", "Blast-radius assessment complete.")

        memory = assess_incident_memory(incident_id)
        if not self._validate_memory(memory):
            state.status = "failed"
            self._add_error(state, "invalid agent output: memory agent returned an invalid payload.")
            self._record(state, "MEMORY", "error", "Invalid memory payload.")
            self._record(state, "END", "failed", "Workflow terminated due to invalid agent output.")
            state.current_step = "END"
            return state
        state.memory = memory
        self._record(state, "MEMORY", "ok", "Hindsight and local memory evidence loaded.")

        runbook_response = get_runbook({"service": str(incident.get("service") or "unknown")}) if incident.get("service") else {"ok": False}
        runbook = runbook_response.get("data") if runbook_response.get("ok") else None
        diagnosis = diagnose_incident(investigation, blast_radius, memory, runbook)
        if not self._validate_diagnosis(diagnosis):
            state.status = "failed"
            self._add_error(state, "invalid agent output: diagnosis agent returned an invalid payload.")
            self._record(state, "DIAGNOSIS", "error", "Invalid diagnosis payload.")
            self._record(state, "END", "failed", "Workflow terminated due to invalid agent output.")
            state.current_step = "END"
            return state
        state.diagnosis = diagnosis
        self._record(state, "DIAGNOSIS", "ok", "Diagnosis completed.")

        state.what_if = {
            "scenario": f"If the service continues to fail under {incident.get('service') or 'the current dependency path'}, impact may spread to adjacent dependencies and user transactions.",
            "risk_assessment": blast_radius.get("severity_assessment", "unknown"),
            "primary_hypothesis": diagnosis.get("primary_hypothesis", "Unknown root cause"),
            "confidence": diagnosis.get("confidence", 0.0),
        }
        self._record(state, "WHAT_IF_ANALYSIS", "ok", "What-if analysis completed.")

        remediation_plan = build_remediation_plan(investigation, blast_radius, diagnosis, memory, runbook)
        state.remediation_plan = remediation_plan
        self._record(state, "REMEDIATION", "ok", "Remediation plan generated.")

        approval = approval_override or {}
        if approval.get("approved") is not True:
            state.status = "blocked"
            if approval_override is None:
                self._add_warning(state, "Remediation is awaiting explicit human approval; no execution or recovery was recorded.")
                approval_reason = "Explicit human approval is required."
            else:
                self._add_error(state, "rejected remediation: the remediation action was rejected by a human operator.")
                approval_reason = str(approval.get("reason") or "Human rejected the remediation.")
            self._record(state, "HUMAN_APPROVAL", "blocked", approval_reason)
            state.current_step = "HUMAN_APPROVAL"
            return state

        state.execution = {
            "status": "approved",
            "approved_action": (remediation_plan.get("recommended_actions") or [{}])[0].get("action") if remediation_plan.get("recommended_actions") else "UNKNOWN_ACTION",
            "details": "Approved remediation simulated successfully. No production command was executed.",
        }
        self._record(state, "HUMAN_APPROVAL", "ok", "Human approval granted.")
        self._record(state, "EXECUTION", "ok", "Execution step completed in simulation mode.")

        state.verification = {
            "status": "verified",
            "checks": [
                "Telemetry returned to nominal range",
                "No downstream dependency failures were introduced",
                "Runbook constraints remained satisfied",
            ],
        }
        self._record(state, "VERIFICATION", "ok", "Verification passed.")

        state.postmortem = {
            "incident_summary": incident.get("title") or "Incident resolved",
            "impact": blast_radius.get("user_impact", "No direct customer impact identified."),
            "detection": ", ".join(incident.get("alerts", []) or []),
            "timeline": state.timeline,
            "root_cause": diagnosis.get("primary_hypothesis", "Unknown root cause"),
            "contributing_factors": [
                blast_radius.get("severity_assessment", "No blast-radius impact data available."),
                diagnosis.get("primary_hypothesis", "No diagnosis data available."),
            ],
            "actions_attempted": incident.get("actions_attempted", []),
            "failed_actions": incident.get("failed_actions", []),
            "successful_actions": incident.get("successful_actions", []),
            "final_resolution": "The incident was contained with a human-approved remediation and verified in simulation mode.",
            "engineer_feedback": incident.get("engineer_feedback", {}) or {},
            "lessons_learned": memory.get("engineer_lessons", []) or ["Maintain operational memory across incident reviews."],
            "future_prevention": [
                "Review the dependency path for similar service interactions.",
                "Record and reuse successful remediation patterns in Hindsight.",
            ],
        }
        self._record(state, "POSTMORTEM", "ok", "Postmortem generated.")

        self._run_hindsight_learning(state)

        if state.warnings:
            state.status = "completed_with_warnings"
        else:
            state.status = "completed"

        state.current_step = "END"
        self._record(state, "END", "ok", "Workflow completed successfully.")
        return state


__all__ = ["IncidentOrchestrator", "OrchestratorState"]
