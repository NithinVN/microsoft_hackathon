from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATASET_PATH = PROJECT_ROOT / "data" / "historical_incidents.json"
FEEDBACK_STORE_PATH = PROJECT_ROOT / "data" / "engineer_feedback.json"

ALLOWED_SERVICES = {
    "payment-api",
    "order-service",
    "user-service",
    "notification-service",
    "database",
    "api-gateway",
}

ALLOWED_ACTION_TYPES = {
    "RESTART_DATABASE",
    "SCALE_CONNECTION_POOL",
    "ENABLE_CIRCUIT_BREAKER",
    "SCALE_POD_REPLICAS",
    "ROUTE_DEAD_LETTER_QUEUE",
    "ROLLBACK_DEPLOYMENT",
    "CREATE_INDEX_CONCURRENTLY",
    "INCREASE_RATE_LIMIT",
    "ROTATE_CERTIFICATE",
    "CIRCUIT_BREAKER",
    "CACHE_WARMUP",
    "RESTART_SERVICE",
    "CONFIGURE_RETRY_BACKOFF",
    "DEAD_LETTER_QUEUE",
    "REBALANCE_WORKERS",
    "FAILOVER_READ_REPLICA",
    "CLEAR_CACHED_SECRETS",
    "RESTART_WORKER",
    "RESOLVE_DEADLOCK",
    "PAUSE_BATCH",
    "REVERT_CONFIG",
    "INCREASE_CLIENT_TIMEOUT",
}

DANGEROUS_SQL_RE = re.compile(
    r"(--|/\*|\*/|;|\b(select|insert|update|delete|drop|alter|truncate|grant|revoke)\b)",
    re.IGNORECASE,
)
DANGEROUS_COMMAND_RE = re.compile(
    r"(;;|&&|\|\||`|\$\(|\b(ssh|curl|wget|bash|sh|kubectl|docker|systemctl|psql|mysql|mongo|rm\s+-rf|chmod\s|chown\s)\b)",
    re.IGNORECASE,
)


class IncidentToolError(Exception):
    """Raised for validation or operational safety failures in the incident tool layer."""


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolExecutionResult(BaseModel):
    ok: bool = True
    tool: str
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    function: Any = Field(exclude=True)


class GetIncidentDetailsInput(ToolInput):
    incident_id: str = Field(..., min_length=3, max_length=50)

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, value: str) -> str:
        if DANGEROUS_SQL_RE.search(value) or DANGEROUS_COMMAND_RE.search(value):
            raise ValueError("incident_id must be a safe incident identifier")
        return value.strip()


class GetIncidentDetailsOutput(BaseModel):
    ok: bool = True
    tool: str = "get_incident_details"
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None


class ServiceMetricsInput(ToolInput):
    service: str
    limit: int = Field(default=3, ge=1, le=10)

    @field_validator("service")
    @classmethod
    def validate_service(cls, value: str) -> str:
        normalized = value.strip().lower()
        if DANGEROUS_SQL_RE.search(value) or DANGEROUS_COMMAND_RE.search(value):
            raise ValueError("service contains unsafe characters")
        if normalized not in ALLOWED_SERVICES:
            raise ValueError(f"unsupported service: {value}")
        return normalized


class ServiceMetricsOutput(BaseModel):
    ok: bool = True
    tool: str = "get_service_metrics"
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None


class ServiceLogsInput(ToolInput):
    service: str
    limit: int = Field(default=5, ge=1, le=20)

    @field_validator("service")
    @classmethod
    def validate_service(cls, value: str) -> str:
        normalized = value.strip().lower()
        if DANGEROUS_SQL_RE.search(value) or DANGEROUS_COMMAND_RE.search(value):
            raise ValueError("service contains unsafe characters")
        if normalized not in ALLOWED_SERVICES:
            raise ValueError(f"unsupported service: {value}")
        return normalized


class ServiceLogsOutput(BaseModel):
    ok: bool = True
    tool: str = "get_service_logs"
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None


class RecentDeploymentsInput(ToolInput):
    service: str
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("service")
    @classmethod
    def validate_service(cls, value: str) -> str:
        normalized = value.strip().lower()
        if DANGEROUS_SQL_RE.search(value) or DANGEROUS_COMMAND_RE.search(value):
            raise ValueError("service contains unsafe characters")
        if normalized not in ALLOWED_SERVICES:
            raise ValueError(f"unsupported service: {value}")
        return normalized


class RecentDeploymentsOutput(BaseModel):
    ok: bool = True
    tool: str = "get_recent_deployments"
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None


class ServiceDependenciesInput(ToolInput):
    service: str

    @field_validator("service")
    @classmethod
    def validate_service(cls, value: str) -> str:
        normalized = value.strip().lower()
        if DANGEROUS_SQL_RE.search(value) or DANGEROUS_COMMAND_RE.search(value):
            raise ValueError("service contains unsafe characters")
        if normalized not in ALLOWED_SERVICES:
            raise ValueError(f"unsupported service: {value}")
        return normalized


class ServiceDependenciesOutput(BaseModel):
    ok: bool = True
    tool: str = "get_service_dependencies"
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None


class RecentIncidentEventsInput(ToolInput):
    service: str
    limit: int = Field(default=10, ge=1, le=20)

    @field_validator("service")
    @classmethod
    def validate_service(cls, value: str) -> str:
        normalized = value.strip().lower()
        if DANGEROUS_SQL_RE.search(value) or DANGEROUS_COMMAND_RE.search(value):
            raise ValueError("service contains unsafe characters")
        if normalized not in ALLOWED_SERVICES:
            raise ValueError(f"unsupported service: {value}")
        return normalized


class RecentIncidentEventsOutput(BaseModel):
    ok: bool = True
    tool: str = "get_recent_incident_events"
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None


class RecallSimilarIncidentsInput(ToolInput):
    query: str = Field(..., min_length=3, max_length=500)
    service: Optional[str] = None
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query cannot be empty")
        if DANGEROUS_SQL_RE.search(stripped) or DANGEROUS_COMMAND_RE.search(stripped):
            raise ValueError("query contains unsafe content")
        return stripped

    @field_validator("service")
    @classmethod
    def validate_service(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in ALLOWED_SERVICES:
            raise ValueError(f"unsupported service: {value}")
        return normalized


class RecallSimilarIncidentsOutput(BaseModel):
    ok: bool = True
    tool: str = "recall_similar_incidents"
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None


class RecallFailedFixesInput(ToolInput):
    service: Optional[str] = None
    action_type: Optional[str] = None
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("service")
    @classmethod
    def validate_service(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in ALLOWED_SERVICES:
            raise ValueError(f"unsupported service: {value}")
        return normalized

    @field_validator("action_type")
    @classmethod
    def validate_action(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().upper()
        if normalized not in ALLOWED_ACTION_TYPES:
            raise ValueError(f"unsupported action_type: {value}")
        return normalized


class RecallFailedFixesOutput(BaseModel):
    ok: bool = True
    tool: str = "recall_failed_fixes"
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None


class RecallSuccessfulFixesInput(RecallFailedFixesInput):
    pass


class RecallSuccessfulFixesOutput(BaseModel):
    ok: bool = True
    tool: str = "recall_successful_fixes"
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None


class GetRunbookInput(ToolInput):
    service: str
    scenario: Optional[str] = Field(default=None, max_length=100)

    @field_validator("service")
    @classmethod
    def validate_service(cls, value: str) -> str:
        normalized = value.strip().lower()
        if DANGEROUS_SQL_RE.search(value) or DANGEROUS_COMMAND_RE.search(value):
            raise ValueError("service contains unsafe characters")
        if normalized not in ALLOWED_SERVICES:
            raise ValueError(f"unsupported service: {value}")
        return normalized


class GetRunbookOutput(BaseModel):
    ok: bool = True
    tool: str = "get_runbook"
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None


class ProposeRemediationInput(ToolInput):
    service: str
    incident_id: Optional[str] = None
    symptom_summary: str = Field(..., min_length=5, max_length=1000)
    max_options: int = Field(default=3, ge=1, le=5)

    @field_validator("service")
    @classmethod
    def validate_service(cls, value: str) -> str:
        normalized = value.strip().lower()
        if DANGEROUS_SQL_RE.search(value) or DANGEROUS_COMMAND_RE.search(value):
            raise ValueError("service contains unsafe characters")
        if normalized not in ALLOWED_SERVICES:
            raise ValueError(f"unsupported service: {value}")
        return normalized

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if DANGEROUS_SQL_RE.search(value) or DANGEROUS_COMMAND_RE.search(value):
            raise ValueError("incident_id contains unsafe characters")
        return value.strip()

    @field_validator("symptom_summary")
    @classmethod
    def validate_symptom_summary(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("symptom_summary cannot be empty")
        if DANGEROUS_SQL_RE.search(stripped) or DANGEROUS_COMMAND_RE.search(stripped):
            raise ValueError("symptom_summary contains unsafe content")
        return stripped


class ProposeRemediationOutput(BaseModel):
    ok: bool = True
    tool: str = "propose_remediation"
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None


class SimulateRemediationInput(ToolInput):
    service: str
    action_type: str = Field(..., min_length=3, max_length=80)
    incident_id: Optional[str] = None
    dry_run: bool = True

    @field_validator("service")
    @classmethod
    def validate_service(cls, value: str) -> str:
        normalized = value.strip().lower()
        if DANGEROUS_SQL_RE.search(value) or DANGEROUS_COMMAND_RE.search(value):
            raise ValueError("service contains unsafe characters")
        if normalized not in ALLOWED_SERVICES:
            raise ValueError(f"unsupported service: {value}")
        return normalized

    @field_validator("action_type")
    @classmethod
    def validate_action_type(cls, value: str) -> str:
        normalized = value.strip().upper()
        if DANGEROUS_SQL_RE.search(value) or DANGEROUS_COMMAND_RE.search(value):
            raise ValueError("action_type contains unsafe content")
        if normalized not in ALLOWED_ACTION_TYPES:
            raise ValueError(f"unsupported action_type: {value}")
        return normalized

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if DANGEROUS_SQL_RE.search(value) or DANGEROUS_COMMAND_RE.search(value):
            raise ValueError("incident_id contains unsafe characters")
        return value.strip()


class SimulateRemediationOutput(BaseModel):
    ok: bool = True
    tool: str = "simulate_remediation"
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None


class RecordEngineerFeedbackInput(ToolInput):
    incident_id: str = Field(..., min_length=3, max_length=50)
    engineer_id: str = Field(..., min_length=2, max_length=100)
    rating: int = Field(..., ge=1, le=5)
    comments: str = Field(..., min_length=3, max_length=2000)

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, value: str) -> str:
        if DANGEROUS_SQL_RE.search(value) or DANGEROUS_COMMAND_RE.search(value):
            raise ValueError("incident_id contains unsafe characters")
        return value.strip()

    @field_validator("engineer_id")
    @classmethod
    def validate_engineer_id(cls, value: str) -> str:
        if DANGEROUS_SQL_RE.search(value) or DANGEROUS_COMMAND_RE.search(value):
            raise ValueError("engineer_id contains unsafe characters")
        return value.strip()

    @field_validator("comments")
    @classmethod
    def validate_comments(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("comments cannot be empty")
        if DANGEROUS_SQL_RE.search(value) or DANGEROUS_COMMAND_RE.search(value):
            raise ValueError("comments contain unsafe content")
        return value.strip()


class RecordEngineerFeedbackOutput(BaseModel):
    ok: bool = True
    tool: str = "record_engineer_feedback"
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None


_RUNTIME_INCIDENTS: Dict[str, Dict[str, Any]] = {}


def register_runtime_incident(incident: Dict[str, Any]) -> None:
    """Register an incident created at runtime (e.g. from webhooks or simulator) for agent tools."""
    incident_id = incident.get("incident_id")
    if incident_id:
        _RUNTIME_INCIDENTS[incident_id] = incident


def clear_runtime_incidents() -> None:
    """Clear registered runtime incidents (used primarily for test isolation)."""
    _RUNTIME_INCIDENTS.clear()


def _read_incidents() -> List[Dict[str, Any]]:
    if not DATASET_PATH.exists():
        raise IncidentToolError(f"Historical incident dataset not found at {DATASET_PATH}")
    with DATASET_PATH.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, list):
        raise IncidentToolError("Historical incident dataset is malformed")
    return raw


def _find_incident_by_id(incident_id: str) -> Optional[Dict[str, Any]]:
    incident_id = incident_id.strip()
    if incident_id in _RUNTIME_INCIDENTS:
        return _RUNTIME_INCIDENTS[incident_id]
    for incident in _read_incidents():
        if incident.get("incident_id") == incident_id:
            return incident
    return None


def _find_incidents_for_service(service: str) -> List[Dict[str, Any]]:
    runtime_matches = [inc for inc in _RUNTIME_INCIDENTS.values() if inc.get("service") == service]
    return runtime_matches + [incident for incident in _read_incidents() if incident.get("service") == service]


def _safe_error(code: str, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    safe_details = dict(details or {})
    errors = safe_details.get("errors")
    if isinstance(errors, list):
        safe_details["errors"] = [
            {key: error[key] for key in ("loc", "msg", "type") if key in error}
            for error in errors
            if isinstance(error, dict)
        ]
    return {
        "ok": False,
        "tool": "",
        "data": {},
        "error": {
            "code": code,
            "message": message,
            "details": safe_details,
        },
    }


def _score_incident_match(query: str, incident: Dict[str, Any]) -> int:
    text = " ".join([
        incident.get("incident_id", ""),
        incident.get("title", ""),
        incident.get("service", ""),
        incident.get("root_cause", ""),
        " ".join(incident.get("symptoms", []) or []),
        " ".join(incident.get("alerts", []) or []),
    ]).lower()
    q = query.lower()
    score = 0
    for piece in q.split():
        if len(piece) < 3:
            continue
        if piece in text:
            score += 2
    if incident.get("service", "").lower() in q:
        score += 3
    if incident.get("title", "").lower() in q:
        score += 4
    return score


def get_incident_details(payload: GetIncidentDetailsInput | Dict[str, Any]) -> Dict[str, Any]:
    try:
        params = GetIncidentDetailsInput.model_validate(payload)
    except ValidationError as exc:
        return _safe_error("validation_error", "Invalid input", {"errors": exc.errors()})
    except Exception:  # pragma: no cover - defensive fallback
        return _safe_error("validation_error", "Invalid input")

    incident = _find_incident_by_id(params.incident_id)
    if incident is None:
        return _safe_error("incident_not_found", f"No incident found for {params.incident_id}")

    return {
        "ok": True,
        "tool": "get_incident_details",
        "data": {
            "incident": {
                "incident_id": incident.get("incident_id"),
                "timestamp": incident.get("timestamp"),
                "service": incident.get("service"),
                "title": incident.get("title"),
                "severity": incident.get("severity"),
                "status": incident.get("status"),
                "symptoms": incident.get("symptoms", []),
                "alerts": incident.get("alerts", []),
                "relevant_metrics": incident.get("relevant_metrics", {}),
                "deployment_context": incident.get("deployment_context", {}),
                "root_cause": incident.get("root_cause"),
                "actions_attempted": incident.get("actions_attempted", []),
                "successful_actions": incident.get("successful_actions", []),
                "failed_actions": incident.get("failed_actions", []),
                "resolution_time_minutes": incident.get("resolution_time_minutes"),
                "final_outcome": incident.get("final_outcome"),
                "engineer_feedback": incident.get("engineer_feedback", {}),
                "lessons_learned": incident.get("lessons_learned", []),
            }
        },
        "error": None,
    }


def get_service_metrics(payload: ServiceMetricsInput | Dict[str, Any]) -> Dict[str, Any]:
    try:
        params = ServiceMetricsInput.model_validate(payload)
    except ValidationError as exc:
        return _safe_error("validation_error", "Invalid input", {"errors": exc.errors()})

    incidents = _find_incidents_for_service(params.service)
    if not incidents:
        return _safe_error("no_data", f"No historical incidents found for service {params.service}")

    latest = sorted(incidents, key=lambda item: item.get("timestamp", ""), reverse=True)[:params.limit]
    metrics = []
    for incident in latest:
        metrics.append({
            "incident_id": incident.get("incident_id"),
            "timestamp": incident.get("timestamp"),
            "relevant_metrics": incident.get("relevant_metrics", {}),
            "severity": incident.get("severity"),
            "status": incident.get("status"),
        })

    return {
        "ok": True,
        "tool": "get_service_metrics",
        "data": {
            "service": params.service,
            "metric_history": metrics,
            "observed_trends": [
                "p99 latency is strongest signal for degraded service health",
                "DB connection saturation and thread starvation are the most common critical failure modes",
            ],
        },
        "error": None,
    }


def get_service_logs(payload: ServiceLogsInput | Dict[str, Any]) -> Dict[str, Any]:
    try:
        params = ServiceLogsInput.model_validate(payload)
    except ValidationError as exc:
        return _safe_error("validation_error", "Invalid input", {"errors": exc.errors()})

    incidents = _find_incidents_for_service(params.service)
    logs: List[Dict[str, Any]] = []
    for incident in sorted(incidents, key=lambda item: item.get("timestamp", ""), reverse=True)[:params.limit]:
        for alert in incident.get("alerts", [])[:3]:
            logs.append({
                "timestamp": incident.get("timestamp"),
                "source": "incident-alert",
                "severity": "warning",
                "message": f"{alert} on {incident.get('service')}",
                "incident_id": incident.get("incident_id"),
            })
    if not logs:
        return _safe_error("no_data", f"No log history found for service {params.service}")

    return {
        "ok": True,
        "tool": "get_service_logs",
        "data": {"service": params.service, "logs": logs[:params.limit]},
        "error": None,
    }


def get_recent_deployments(payload: RecentDeploymentsInput | Dict[str, Any]) -> Dict[str, Any]:
    try:
        params = RecentDeploymentsInput.model_validate(payload)
    except ValidationError as exc:
        return _safe_error("validation_error", "Invalid input", {"errors": exc.errors()})

    incidents = _find_incidents_for_service(params.service)
    deployments: List[Dict[str, Any]] = []
    for incident in sorted(incidents, key=lambda item: item.get("timestamp", ""), reverse=True)[:params.limit]:
        context = incident.get("deployment_context", {})
        deployments.append({
            "incident_id": incident.get("incident_id"),
            "service": params.service,
            "deployment_version": context.get("last_deployment"),
            "deployed_at": context.get("deployed_at"),
            "environment": context.get("environment"),
            "status": incident.get("status"),
        })

    if not deployments:
        return _safe_error("no_data", f"No deployment history found for service {params.service}")

    return {"ok": True, "tool": "get_recent_deployments", "data": {"service": params.service, "deployments": deployments}, "error": None}


def get_service_dependencies(payload: ServiceDependenciesInput | Dict[str, Any]) -> Dict[str, Any]:
    try:
        params = ServiceDependenciesInput.model_validate(payload)
    except ValidationError as exc:
        return _safe_error("validation_error", "Invalid input", {"errors": exc.errors()})

    dependencies = {
        "payment-api": ["api-gateway", "database", "user-service", "notification-service"],
        "order-service": ["database", "payment-api", "notification-service", "api-gateway"],
        "user-service": ["database", "api-gateway", "notification-service"],
        "notification-service": ["api-gateway", "user-service", "payment-api"],
        "database": ["payment-api", "order-service", "user-service"],
        "api-gateway": ["payment-api", "order-service", "user-service", "notification-service"],
    }
    service_dependencies = dependencies.get(params.service, [])
    return {"ok": True, "tool": "get_service_dependencies", "data": {"service": params.service, "dependencies": service_dependencies}, "error": None}


def get_recent_incident_events(payload: RecentIncidentEventsInput | Dict[str, Any]) -> Dict[str, Any]:
    try:
        params = RecentIncidentEventsInput.model_validate(payload)
    except ValidationError as exc:
        return _safe_error("validation_error", "Invalid input", {"errors": exc.errors()})

    incidents = _find_incidents_for_service(params.service)
    events: List[Dict[str, Any]] = []
    for incident in sorted(incidents, key=lambda item: item.get("timestamp", ""), reverse=True)[:params.limit]:
        for alert in incident.get("alerts", [])[:2]:
            events.append({
                "incident_id": incident.get("incident_id"),
                "timestamp": incident.get("timestamp"),
                "event_type": "alert",
                "message": alert,
                "source": "alerting-system",
            })
        for action in incident.get("actions_attempted", [])[:2]:
            events.append({
                "incident_id": incident.get("incident_id"),
                "timestamp": incident.get("timestamp"),
                "event_type": "remediation",
                "message": f"{action.get('action_type')} -> {action.get('outcome')}",
                "source": "incident-response",
            })
    if not events:
        return _safe_error("no_data", f"No incident events found for service {params.service}")

    return {"ok": True, "tool": "get_recent_incident_events", "data": {"service": params.service, "events": events[:params.limit]}, "error": None}


def recall_similar_incidents(payload: RecallSimilarIncidentsInput | Dict[str, Any]) -> Dict[str, Any]:
    try:
        params = RecallSimilarIncidentsInput.model_validate(payload)
    except ValidationError as exc:
        return _safe_error("validation_error", "Invalid input", {"errors": exc.errors()})

    matches = []
    for incident in _read_incidents():
        if params.service and incident.get("service") != params.service:
            continue
        score = _score_incident_match(params.query, incident)
        if score > 0:
            matches.append({
                "incident_id": incident.get("incident_id"),
                "service": incident.get("service"),
                "title": incident.get("title"),
                "score": score,
                "root_cause": incident.get("root_cause"),
                "successful_actions": incident.get("successful_actions", []),
                "failed_actions": incident.get("failed_actions", []),
            })

    matches.sort(key=lambda item: item["score"], reverse=True)
    return {
        "ok": True,
        "tool": "recall_similar_incidents",
        "data": {"query": params.query, "service": params.service, "matches": matches[:params.limit]},
        "error": None,
    }


def recall_failed_fixes(payload: RecallFailedFixesInput | Dict[str, Any]) -> Dict[str, Any]:
    try:
        params = RecallFailedFixesInput.model_validate(payload)
    except ValidationError as exc:
        return _safe_error("validation_error", "Invalid input", {"errors": exc.errors()})

    matches: List[Dict[str, Any]] = []
    for incident in _read_incidents():
        if params.service and incident.get("service") != params.service:
            continue
        for action in incident.get("actions_attempted", []):
            if action.get("outcome") != "failed":
                continue
            if params.action_type and action.get("action_type") != params.action_type:
                continue
            matches.append({
                "incident_id": incident.get("incident_id"),
                "service": incident.get("service"),
                "action_type": action.get("action_type"),
                "reason": action.get("reason"),
                "failed_action": action,
            })

    return {"ok": True, "tool": "recall_failed_fixes", "data": {"service": params.service, "action_type": params.action_type, "matches": matches[:params.limit]}, "error": None}


def recall_successful_fixes(payload: RecallSuccessfulFixesInput | Dict[str, Any]) -> Dict[str, Any]:
    try:
        params = RecallSuccessfulFixesInput.model_validate(payload)
    except ValidationError as exc:
        return _safe_error("validation_error", "Invalid input", {"errors": exc.errors()})

    matches: List[Dict[str, Any]] = []
    for incident in _read_incidents():
        if params.service and incident.get("service") != params.service:
            continue
        for action in incident.get("actions_attempted", []):
            if action.get("outcome") != "successful":
                continue
            if params.action_type and action.get("action_type") != params.action_type:
                continue
            matches.append({
                "incident_id": incident.get("incident_id"),
                "service": incident.get("service"),
                "action_type": action.get("action_type"),
                "reason": action.get("reason"),
                "successful_action": action,
            })

    return {"ok": True, "tool": "recall_successful_fixes", "data": {"service": params.service, "action_type": params.action_type, "matches": matches[:params.limit]}, "error": None}


def get_runbook(payload: GetRunbookInput | Dict[str, Any]) -> Dict[str, Any]:
    try:
        params = GetRunbookInput.model_validate(payload)
    except ValidationError as exc:
        return _safe_error("validation_error", "Invalid input", {"errors": exc.errors()})

    runbooks = {
        "payment-api": {
            "service": "payment-api",
            "runbook": "Check upstream gateway latency, inspect thread pool saturation, enable circuit breaker, queue retries, and verify payment status before restarting worker processes.",
            "steps": [
                "Confirm payment gateway latency and queue backlog levels.",
                "Check worker thread utilization and outbound timeout configuration.",
                "Apply fail-fast circuit breaker and asynchronous retry queueing.",
                "Verify payment confirmations and replay only safe retries.",
            ],
            "allowed_actions": ["ENABLE_CIRCUIT_BREAKER", "SCALE_POD_REPLICAS", "CONFIGURE_RETRY_BACKOFF"],
            "safety_rules": [
                "Never restart downstream payment services during a known external outage.",
                "Do not execute arbitrary shell or database commands via the LLM.",
            ],
        },
        "database": {
            "service": "database",
            "runbook": "Inspect active connections, verify pool headroom, avoid hard restarts, and increase max_connections only after connection drain and idle cleanup.",
            "steps": [
                "Measure connection saturation and database CPU usage.",
                "Check for leaked sessions and idle connection churn.",
                "Increase pool headroom and drain idle sessions.",
                "Only restart if failover or maintenance is explicitly approved.",
            ],
            "allowed_actions": ["SCALE_CONNECTION_POOL", "RESTART_DATABASE"],
            "safety_rules": [
                "Avoid immediate primary restarts under load.",
                "Only use predetermined, approved operational actions.",
            ],
        },
        "order-service": {
            "service": "order-service",
            "runbook": " isolate malformed broker payloads, route to DLQ, verify consumer lag, and repair deserialization before resuming the consumer group.",
            "steps": [
                "Inspect consumer lag and broker offsets.",
                "Check last malformed payload and deserialization errors.",
                "Route poison message to dead-letter queue and resume offset consumption.",
                "Deploy serializer fix and verify stable queue drain.",
            ],
            "allowed_actions": ["ROUTE_DEAD_LETTER_QUEUE", "RESTART_SERVICE", "CONFIGURE_RETRY_BACKOFF"],
            "safety_rules": [
                "Never replay untrusted poison messages into the live topic.",
                "All operations must be queued for human approval before execution.",
            ],
        },
        "user-service": {
            "service": "user-service",
            "runbook": "Verify auth DB latency, check missing indexes, warm caches, and avoid destructive cache flushes unless a human approves the recovery plan.",
            "steps": [
                "Inspect login latency and database execution plans.",
                "Check for index loss or cache invalidation events.",
                "Create the missing index or warm replicas before server restarts.",
                "Verify login success and session consistency.",
            ],
            "allowed_actions": ["CREATE_INDEX_CONCURRENTLY", "CACHE_WARMUP", "RESTART_SERVICE"],
            "safety_rules": [
                "Do not flush the entire shared cache during active sessions.",
                "No LLM-generated database changes are allowed.",
            ],
        },
        "api-gateway": {
            "service": "api-gateway",
            "runbook": "Validate config syntax, verify certificate expiry and upstream routing, roll back the last gateway revision, and then confirm traffic returns to baseline.",
            "steps": [
                "Inspect TLS expiry and ingress routing config.",
                "Run config validation and confirm health probes.",
                "Rollback the last bad deployment if syntax or routing is broken.",
                "Verify public traffic returns to baseline before reopening canaries.",
            ],
            "allowed_actions": ["ROLLBACK_DEPLOYMENT", "ROTATE_CERTIFICATE", "REVERT_CONFIG"],
            "safety_rules": [
                "Never hot-patch live gateway config without staged rollback.",
                "No shell-based production changes are permitted from the agent.",
            ],
        },
        "notification-service": {
            "service": "notification-service",
            "runbook": "Check upstream provider health, the queue depth, retry/timeout settings, and the delivery backlog before escalating to a provider-side recovery.",
            "steps": [
                "Inspect provider backlog and queue depth.",
                "Review HTTP retry settings and token expiry.",
                "Restore queue processing with bounded retries and backoff.",
                "Verify delivery acceptance and provider continuity.",
            ],
            "allowed_actions": ["REBALANCE_WORKERS", "INCREASE_CLIENT_TIMEOUT", "CONFIGURE_RETRY_BACKOFF"],
            "safety_rules": [
                "Do not send duplicate notifications during retries without idempotency checks.",
                "No ad hoc production commands outside the approved runbook.",
            ],
        },
    }
    runbook = runbooks.get(params.service)
    if runbook is None:
        return _safe_error("unsupported_service", f"No runbook configured for {params.service}")

    if params.scenario:
        runbook = {**runbook, "scenario": params.scenario}

    return {"ok": True, "tool": "get_runbook", "data": runbook, "error": None}


def propose_remediation(payload: ProposeRemediationInput | Dict[str, Any]) -> Dict[str, Any]:
    try:
        params = ProposeRemediationInput.model_validate(payload)
    except ValidationError as exc:
        return _safe_error("validation_error", "Invalid input", {"errors": exc.errors()})

    incident = None
    if params.incident_id:
        incident = _find_incident_by_id(params.incident_id)
    else:
        incidents = _find_incidents_for_service(params.service)
        if incidents:
            incident = sorted(incidents, key=lambda item: item.get("timestamp", ""), reverse=True)[0]

    candidate_actions = []
    if incident is not None:
        for action in incident.get("actions_attempted", []):
            if action.get("outcome") == "successful":
                candidate_actions.append({
                    "action_type": action.get("action_type"),
                    "confidence": 0.95,
                    "reason": action.get("reason"),
                    "mode": "simulated",
                    "risk": "low",
                })
        if not candidate_actions:
            candidate_actions = [
                {"action_type": "ROLLBACK_DEPLOYMENT", "confidence": 0.78, "reason": "use last known good deployment", "mode": "simulated", "risk": "medium"},
            ]
    else:
        candidate_actions = [{
            "action_type": "CHECK_DEPENDENCY_HEALTH",
            "confidence": 0.6,
            "reason": "No exact incident match found; begin with dependency and deployment validation.",
            "mode": "simulated",
            "risk": "medium",
        }]

    filtered = candidate_actions[: params.max_options]
    for option in filtered:
        option["requires_human_approval"] = True
        option["command_template"] = "SIMULATED_ONLY: no shell or SQL execution"

    return {"ok": True, "tool": "propose_remediation", "data": {"service": params.service, "incident_id": incident.get("incident_id") if incident else params.incident_id, "recommendations": filtered}, "error": None}


def simulate_remediation(payload: SimulateRemediationInput | Dict[str, Any]) -> Dict[str, Any]:
    try:
        params = SimulateRemediationInput.model_validate(payload)
    except ValidationError as exc:
        return _safe_error("validation_error", "Invalid input", {"errors": exc.errors()})

    if not params.dry_run:
        return _safe_error("unsafe_mode", "Production execution is disabled in this tool layer; simulation mode is required.")

    incident = None
    if params.incident_id:
        incident = _find_incident_by_id(params.incident_id)
    else:
        incidents = _find_incidents_for_service(params.service)
        if incidents:
            incident = sorted(incidents, key=lambda item: item.get("timestamp", ""), reverse=True)[0]

    if incident is None:
        return _safe_error("incident_not_found", f"No incident data found for service {params.service}")

    failed_history = []
    success_history = []
    for action in incident.get("actions_attempted", []):
        if action.get("action_type") == params.action_type:
            if action.get("outcome") == "failed":
                failed_history.append(action)
            elif action.get("outcome") == "successful":
                success_history.append(action)

    if failed_history and not success_history:
        return {
            "ok": True,
            "tool": "simulate_remediation",
            "data": {
                "mode": "simulation",
                "service": params.service,
                "incident_id": incident.get("incident_id"),
                "action_type": params.action_type,
                "predicted_outcome": "likely_failure",
                "confidence": 0.9,
                "summary": f"{params.action_type} previously failed in similar conditions for {incident.get('incident_id')}; this simulation predicts continued degradation.",
                "safety_warning": "This action is not eligible for production execution in this tool layer.",
            },
            "error": None,
        }

    if success_history:
        return {
            "ok": True,
            "tool": "simulate_remediation",
            "data": {
                "mode": "simulation",
                "service": params.service,
                "incident_id": incident.get("incident_id"),
                "action_type": params.action_type,
                "predicted_outcome": "likely_success",
                "confidence": 0.88,
                "summary": f"{params.action_type} succeeded previously and is included in the safe-simulation playbook for {incident.get('incident_id')}.",
                "safety_warning": "This is a dry-run simulation only; no actual command is executed.",
            },
            "error": None,
        }

    return {
        "ok": True,
        "tool": "simulate_remediation",
        "data": {
            "mode": "simulation",
            "service": params.service,
            "incident_id": incident.get("incident_id"),
            "action_type": params.action_type,
            "predicted_outcome": "unknown",
            "confidence": 0.52,
            "summary": f"{params.action_type} has no historical precedent for this service; simulation recommends human review before any action.",
            "safety_warning": "This is a simulation only. No production command is permitted.",
        },
        "error": None,
    }


def record_engineer_feedback(payload: RecordEngineerFeedbackInput | Dict[str, Any]) -> Dict[str, Any]:
    try:
        params = RecordEngineerFeedbackInput.model_validate(payload)
    except ValidationError as exc:
        return _safe_error("validation_error", "Invalid input", {"errors": exc.errors()})

    incident = _find_incident_by_id(params.incident_id)
    if incident is None:
        return _safe_error("incident_not_found", f"No incident found for {params.incident_id}")

    record = {
        "incident_id": params.incident_id,
        "engineer_id": params.engineer_id,
        "service": incident.get("service"),
        "rating": params.rating,
        "comments": params.comments,
        "submitted_at": "2026-09-28T00:00:00Z",
    }

    existing: List[Dict[str, Any]] = []
    FEEDBACK_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if FEEDBACK_STORE_PATH.exists():
        try:
            with FEEDBACK_STORE_PATH.open("r", encoding="utf-8") as handle:
                existing = json.load(handle)
        except json.JSONDecodeError:
            existing = []
    existing.append(record)
    with FEEDBACK_STORE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(existing, handle, indent=2)

    return {"ok": True, "tool": "record_engineer_feedback", "data": {"record": record}, "error": None}


def _make_tool_spec(name: str, description: str, input_model: type[BaseModel], output_model: type[BaseModel], function: Any) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=description,
        input_schema=input_model.model_json_schema(),
        output_schema=output_model.model_json_schema(),
        function=function,
    )


TOOL_REGISTRY: Dict[str, ToolSpec] = {
    "get_incident_details": _make_tool_spec(
        "get_incident_details",
        "Return the full structured record for a single historical incident, including symptoms, alerts, deployment context, root cause, attempted actions, and final outcome.",
        GetIncidentDetailsInput,
        GetIncidentDetailsOutput,
        get_incident_details,
    ),
    "get_service_metrics": _make_tool_spec(
        "get_service_metrics",
        "Return recent telemetry and metric snapshots for a service from the incident corpus.",
        ServiceMetricsInput,
        ServiceMetricsOutput,
        get_service_metrics,
    ),
    "get_service_logs": _make_tool_spec(
        "get_service_logs",
        "Return deterministic log excerpts synthesized from historical incidents for a service.",
        ServiceLogsInput,
        ServiceLogsOutput,
        get_service_logs,
    ),
    "get_recent_deployments": _make_tool_spec(
        "get_recent_deployments",
        "Return recent deployment context associated with a service for change-correlation analysis.",
        RecentDeploymentsInput,
        RecentDeploymentsOutput,
        get_recent_deployments,
    ),
    "get_service_dependencies": _make_tool_spec(
        "get_service_dependencies",
        "Return the known upstream/downstream dependency list for a service to scope blast radius investigation.",
        ServiceDependenciesInput,
        ServiceDependenciesOutput,
        get_service_dependencies,
    ),
    "get_recent_incident_events": _make_tool_spec(
        "get_recent_incident_events",
        "Return alert and remediation event snapshots for recent incidents affecting a service.",
        RecentIncidentEventsInput,
        RecentIncidentEventsOutput,
        get_recent_incident_events,
    ),
    "recall_similar_incidents": _make_tool_spec(
        "recall_similar_incidents",
        "Search the historical incident dataset for similar failure patterns using a safe, deterministic text match over historical incidents.",
        RecallSimilarIncidentsInput,
        RecallSimilarIncidentsOutput,
        recall_similar_incidents,
    ),
    "recall_failed_fixes": _make_tool_spec(
        "recall_failed_fixes",
        "Return historically failed remediation actions for a service or action type, to warn against repeating destructive patterns.",
        RecallFailedFixesInput,
        RecallFailedFixesOutput,
        recall_failed_fixes,
    ),
    "recall_successful_fixes": _make_tool_spec(
        "recall_successful_fixes",
        "Return historically successful remediation actions for a service or action type, to guide safe next steps.",
        RecallSuccessfulFixesInput,
        RecallSuccessfulFixesOutput,
        recall_successful_fixes,
    ),
    "get_runbook": _make_tool_spec(
        "get_runbook",
        "Return the safe, approved runbook for a service and scenario, without allowing arbitrary production commands.",
        GetRunbookInput,
        GetRunbookOutput,
        get_runbook,
    ),
    "propose_remediation": _make_tool_spec(
        "propose_remediation",
        "Return a curated, human-approved set of remediation suggestions based on the incident history and service context. This tool does not execute changes.",
        ProposeRemediationInput,
        ProposeRemediationOutput,
        propose_remediation,
    ),
    "simulate_remediation": _make_tool_spec(
        "simulate_remediation",
        "Simulate the likely outcome of a known remediation action in dry-run mode only. No production action or shell command is executed.",
        SimulateRemediationInput,
        SimulateRemediationOutput,
        simulate_remediation,
    ),
    "record_engineer_feedback": _make_tool_spec(
        "record_engineer_feedback",
        "Persist structured engineer feedback for a closed incident so the organization learns from the correction path.",
        RecordEngineerFeedbackInput,
        RecordEngineerFeedbackOutput,
        record_engineer_feedback,
    ),
}


def list_tool_specs() -> List[Dict[str, Any]]:
    return [{
        "name": spec.name,
        "description": spec.description,
        "input_schema": spec.input_schema,
        "output_schema": spec.output_schema,
    } for spec in TOOL_REGISTRY.values()]


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    tool = TOOL_REGISTRY.get(tool_name)
    if tool is None:
        return _safe_error("unknown_tool", "Unknown tool requested")
    try:
        return tool.function(arguments)
    except IncidentToolError:
        return _safe_error("tool_execution_error", "Tool execution failed")
    except ValidationError as exc:
        return _safe_error("validation_error", "Tool validation failed", {"errors": exc.errors()})
    except Exception:  # pragma: no cover - last-resort guard
        return _safe_error("tool_execution_error", "Tool execution failed")


__all__ = [
    "ALLOWED_SERVICES",
    "ALLOWED_ACTION_TYPES",
    "TOOL_REGISTRY",
    "IncidentToolError",
    "execute_tool",
    "list_tool_specs",
    "get_incident_details",
    "get_service_metrics",
    "get_service_logs",
    "get_recent_deployments",
    "get_service_dependencies",
    "get_recent_incident_events",
    "recall_similar_incidents",
    "recall_failed_fixes",
    "recall_successful_fixes",
    "get_runbook",
    "propose_remediation",
    "simulate_remediation",
    "record_engineer_feedback",
    "register_runtime_incident",
    "clear_runtime_incidents",
]
