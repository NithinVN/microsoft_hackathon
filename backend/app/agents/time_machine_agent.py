from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.memory.hindsight_service import hindsight_service
from backend.app.tools import get_incident_details


CANDIDATE_ACTIONS = [
    {
        "action": "ROLLBACK_DEPLOYMENT",
        "keywords": ["rollback", "deployment", "revert", "version"],
        "description": "Return to the last known good deployment when configuration or release regressions are suspected.",
    },
    {
        "action": "RESTART_SERVICE",
        "keywords": ["restart", "service", "restart_service"],
        "description": "Restart a single service as a controlled recovery step after confirming it is the failure point.",
    },
    {
        "action": "SCALE_CONNECTION_POOL",
        "keywords": ["connection", "pool", "max_connections", "scale_connection_pool"],
        "description": "Add headroom for active database connections and drain idle sessions before reintroducing traffic.",
    },
    {
        "action": "ENABLE_CIRCUIT_BREAKER",
        "keywords": ["disable", "feature", "toggle", "fallback", "circuit", "breaker"],
        "description": "Temporarily gate slow or broken dependencies so the service fails fast without cascading overload.",
    },
    {
        "action": "REVERT_CONFIG",
        "keywords": ["config", "configuration", "gateway", "syntax", "rollback"],
        "description": "Address incorrect config or deployment syntax before wider traffic is resumed.",
    },
    {
        "action": "ROUTE_DEAD_LETTER_QUEUE",
        "keywords": ["dependency", "restore", "circuit", "provider", "upstream", "deadletter", "queue"],
        "description": "Restore or isolate the failing dependency so application threads and user flows can recover.",
    },
]


def _read_historical_dataset() -> List[Dict[str, Any]]:
    data_file = Path(__file__).resolve().parents[3] / "data" / "historical_incidents.json"
    if not data_file.exists():
        return []
    try:
        with data_file.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            return payload
    except (OSError, ValueError):
        return []
    return []


def _candidate_matches_action(candidate: Dict[str, Any], action_type: str) -> bool:
    # Match action identifiers exactly. Substring matching made
    # RESTART_SERVICE match RESTART_DATABASE and corrupted historical counts.
    normalize = lambda value: "_".join(str(value or "").strip().lower().replace("-", "_").split())
    target = normalize(candidate.get("action"))
    actual = normalize(action_type)
    return bool(target and actual and target == actual)


def _safe_hindsight_matches(service: Optional[str], action: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    try:
        successful = hindsight_service.recall_successful_remediations(service=service, query=action)
        failed = hindsight_service.recall_failed_remediations(service=service, query=action)
        results.extend(successful)
        results.extend(failed)
    except Exception:
        return []
    return results


def _summarise_context(incident: Dict[str, Any], action_type: str) -> str:
    attempts = incident.get("actions_attempted", []) or []
    for attempt in attempts:
        attempted_type = str(attempt.get("action_type") or "")
        if _candidate_matches_action({"action": action_type, "keywords": []}, attempted_type):
            reason = attempt.get("reason") or "No explicit reasoning recorded."
            return reason
    return incident.get("root_cause") or "Context not recorded in the historical incident metadata."


def _resolve_case_matches(service: str, action_label: str) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    dataset = _read_historical_dataset()
    candidate = {"action": action_label, "keywords": [part for part in action_label.split() if part]}

    for incident in dataset:
        current_service = incident.get("service")
        if service and current_service and current_service != service:
            continue
        for attempt in incident.get("actions_attempted", []) or []:
            action_type = str(attempt.get("action_type") or "")
            if not _candidate_matches_action(candidate, action_type):
                continue
            cases.append({
                "incident_id": incident.get("incident_id"),
                "service": incident.get("service"),
                "outcome": attempt.get("outcome"),
                "context": attempt.get("reason") or incident.get("root_cause") or "Historical context not recorded.",
                "action": action_type,
            })

    return cases


def build_time_machine_analysis(incident_id: str) -> List[Dict[str, Any]]:
    incident_result = get_incident_details({"incident_id": incident_id})
    if not incident_result.get("ok"):
        return []

    incident = incident_result["data"]["incident"]
    service = incident.get("service")

    action_results: List[Dict[str, Any]] = []
    for candidate in CANDIDATE_ACTIONS:
        action_name = candidate["action"]
        cases = _resolve_case_matches(service or "", action_name)
        if not cases:
            historical_hints = _safe_hindsight_matches(service, action_name)
            if historical_hints:
                for hint in historical_hints:
                    meta = hint.get("metadata") or {}
                    cases.append({
                        "incident_id": meta.get("incident_id") or hint.get("incident_id") or "unknown",
                        "service": meta.get("service") or service,
                        "outcome": meta.get("outcome") or "unknown",
                        "context": hint.get("text") or hint.get("content") or "Historical evidence available in Hindsight memory.",
                        "action": action_name,
                    })

        successful_attempts = sum(1 for case in cases if str(case.get("outcome") or "").lower() == "successful")
        failed_attempts = sum(1 for case in cases if str(case.get("outcome") or "").lower() == "failed")
        historical_attempts = len(cases)

        lessons: List[str] = []
        for case in cases[:3]:
            if case.get("context"):
                lesson = f"Historical evidence shows {case['incident_id']} used {case.get('action') or action_name} in a {case.get('service') or service} context: {case['context']}"
                lessons.append(lesson)

        if not lessons:
            lessons.append(
                f"Historical evidence shows no direct precedent was found for {action_name} in this service context, so the recommendation should be treated cautiously."
            )

        caveats = [
            "Historical evidence shows this action has been tried before, but past outcomes do not guarantee the same result in the current incident.",
            "Context matters: service state, dependency health, and traffic shape can change the effectiveness of the same action.",
        ]

        if historical_attempts == 0:
            caveats.append("No direct historical attempt was found for this candidate action in the current service context; this remains a low-confidence suggestion.")

        action_results.append({
            "action": action_name,
            "description": candidate.get("description"),
            "historical_attempts": historical_attempts,
            "successful_attempts": successful_attempts,
            "failed_attempts": failed_attempts,
            "historical_cases": [
                {
                    "incident_id": case.get("incident_id"),
                    "service": case.get("service"),
                    "outcome": case.get("outcome"),
                    "context": case.get("context"),
                    "action": case.get("action") or action_name,
                }
                for case in cases[:5]
            ],
            "lessons": lessons,
            "caveats": caveats,
            "confidence": 0.1 if historical_attempts == 0 else min(0.95, 0.4 + (successful_attempts * 0.2) - (failed_attempts * 0.15)),
        })

    return action_results


def _failed_fix_warning_for_incident(incident_id: str) -> Optional[Dict[str, Any]]:
    incident_result = get_incident_details({"incident_id": incident_id})
    if not incident_result.get("ok"):
        return None

    incident = incident_result["data"]["incident"]
    for action in incident.get("actions_attempted", []) or []:
        if str(action.get("outcome") or "").lower() == "failed":
            return {
                "dangerous_action": str(action.get("action_type") or "UNKNOWN_ACTION"),
                "incident_ref": incident.get("incident_id"),
                "reason": "Historical evidence shows this action was attempted but did not resolve the incident.",
                "historical_consequence": str(action.get("reason") or "The failed action worsened the incident or did not improve recovery."),
            }
    return None


__all__ = ["build_time_machine_analysis", "CANDIDATE_ACTIONS", "_failed_fix_warning_for_incident"]
