from __future__ import annotations

from typing import Any, Dict, List

from backend.app.tools import (
    execute_tool,
    get_incident_details,
    get_recent_deployments,
    get_recent_incident_events,
    get_runbook,
    get_service_dependencies,
    get_service_logs,
    get_service_metrics,
    recall_similar_incidents,
)


def _tool_result(tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return execute_tool(tool_name, payload)


def _normalize_services(incident: Dict[str, Any]) -> List[str]:
    service = incident.get("service")
    if service:
        return [service]
    return []


def _build_timeline(incident: Dict[str, Any], logs: List[Dict[str, Any]], events: List[Dict[str, Any]], deployments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    timeline: List[Dict[str, Any]] = []

    for step in incident.get("actions_attempted", []):
        timeline.append({
            "timestamp": incident.get("timestamp"),
            "event": step.get("action_type"),
            "detail": step.get("reason"),
            "classification": "fact",
        })

    for log in logs:
        timeline.append({
            "timestamp": log.get("timestamp"),
            "event": log.get("source"),
            "detail": log.get("message"),
            "classification": "fact",
        })

    for event in events:
        timeline.append({
            "timestamp": event.get("timestamp"),
            "event": event.get("event_type"),
            "detail": event.get("message"),
            "classification": "fact",
        })

    for deployment in deployments:
        timeline.append({
            "timestamp": deployment.get("deployed_at") or incident.get("timestamp"),
            "event": "deployment",
            "detail": f"{deployment.get('service')} deployed {deployment.get('deployment_version') or 'unknown'}",
            "classification": "fact",
        })

    if not timeline:
        timeline.append({
            "timestamp": incident.get("timestamp"),
            "event": "incident_detected",
            "detail": "Information unavailable: no log, deployment, or event history was available.",
            "classification": "fact",
        })

    return sorted(timeline, key=lambda item: str(item.get("timestamp") or ""))


def _candidate_causes(incident: Dict[str, Any], similar: List[Dict[str, Any]], dependencies: List[str]) -> List[Dict[str, Any]]:
    causes: List[Dict[str, Any]] = []
    root = incident.get("root_cause")
    if root:
        causes.append({
            "cause": root,
            "status": "fact",
            "classification": "fact",
            "confidence": "high",
            "source": "incident record",
        })

    for match in similar[:3]:
        cause = match.get("root_cause")
        if cause:
            causes.append({
                "cause": cause,
                "status": "hypothesis",
                "classification": "hypothesis",
                "confidence": "medium",
                "source": "similar incident match",
            })

    if dependencies:
        causes.append({
            "cause": f"Dependency chain may be amplifying the issue across {', '.join(dependencies)}.",
            "status": "hypothesis",
            "classification": "hypothesis",
            "confidence": "medium",
            "source": "service dependency analysis",
        })

    if not causes:
        causes.append({
            "cause": "Information unavailable: no candidate cause could be established from the available evidence.",
            "status": "hypothesis",
            "classification": "hypothesis",
            "confidence": "low",
            "source": "missing evidence",
        })

    return causes


def _extract_abnormal_signals(incident: Dict[str, Any], metrics_result: Dict[str, Any]) -> List[str]:
    signals: List[str] = []
    combined_text = " ".join(incident.get("symptoms", []) + incident.get("alerts", [])).lower()

    if "thread" in combined_text or "thread_pool" in combined_text:
        signals.append("thread starvation")
    if "connection" in combined_text or "max_connections" in combined_text or "active database connections" in combined_text:
        signals.append("connection pool exhaustion")
    if "poison" in combined_text or "malformed json" in combined_text or "deserialization" in combined_text:
        signals.append("poison message / deserialization failure")
    if "latency" in combined_text or "p99" in combined_text:
        signals.append("latency spike")
    if "retry" in combined_text or "dead-letter" in combined_text or "dlq" in combined_text:
        signals.append("queue backlog / retry loop")

    if metrics_result.get("ok"):
        for metric_entry in metrics_result["data"].get("metric_history", []):
            metrics = metric_entry.get("relevant_metrics", {})
            for key, value in metrics.items():
                if isinstance(value, (int, float)) and value > 90:
                    key_text = str(key).lower()
                    if "thread" in key_text:
                        signals.append("thread starvation")
                    if "connection" in key_text:
                        signals.append("connection pool exhaustion")
                    if "cpu" in key_text:
                        signals.append("cpu saturation")
                    if "latency" in key_text or "p99" in key_text:
                        signals.append("latency spike")
                    if "lag" in key_text or "queue" in key_text:
                        signals.append("queue backlog")

    deduped = []
    seen = set()
    for signal in signals:
        key = signal.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(signal)

    if not deduped:
        deduped = ["No abnormal metric threshold was identified from the available record."]

    return deduped


def investigate_incident(incident_id: str) -> Dict[str, Any]:
    incident_response = get_incident_details({"incident_id": incident_id})
    if not incident_response.get("ok"):
        return {
            "incident_id": incident_id,
            "current_state": "Information unavailable: no matching incident was found.",
            "symptoms": [],
            "affected_services": [],
            "abnormal_signals": [],
            "recent_changes": [],
            "timeline": [],
            "candidate_causes": [{
                "cause": "Information unavailable: no matching incident was found.",
                "status": "hypothesis",
                "classification": "hypothesis",
                "confidence": "low",
                "source": "missing evidence",
            }],
            "evidence": [{
                "item": "No incident record matched the supplied identifier.",
                "classification": "fact",
                "source": "incident lookup",
            }],
            "uncertainties": [
                "Information unavailable: no matching incident was found.",
                "No logs, metrics, deployments, or dependencies were available for this incident identifier.",
            ],
        }

    incident = incident_response["data"]["incident"]
    service = incident.get("service")
    symptoms = incident.get("symptoms", [])
    affected_services = [service] if service else []

    metrics_result = _tool_result("get_service_metrics", {"service": service, "limit": 5}) if service else {"ok": False, "data": {}}
    logs_result = _tool_result("get_service_logs", {"service": service, "limit": 5}) if service else {"ok": False, "data": {}}
    deployments_result = _tool_result("get_recent_deployments", {"service": service, "limit": 5}) if service else {"ok": False, "data": {}}
    dependencies_result = _tool_result("get_service_dependencies", {"service": service}) if service else {"ok": False, "data": {}}
    events_result = _tool_result("get_recent_incident_events", {"service": service, "limit": 10}) if service else {"ok": False, "data": {}}
    similar_result = _tool_result("recall_similar_incidents", {"query": " ".join(symptoms), "service": service, "limit": 3}) if service else {"ok": False, "data": {}}
    runbook_result = _tool_result("get_runbook", {"service": service}) if service else {"ok": False, "data": {}}

    abnormal_signals = _extract_abnormal_signals(incident, metrics_result)

    recent_changes = []
    if deployments_result.get("ok"):
        for deployment in deployments_result["data"].get("deployments", []):
            recent_changes.append({
                "service": deployment.get("service"),
                "version": deployment.get("deployment_version"),
                "timestamp": deployment.get("deployed_at"),
                "classification": "fact",
            })
    if not recent_changes:
        recent_changes = [{
            "service": service,
            "version": "Information unavailable",
            "timestamp": "Information unavailable",
            "classification": "fact",
            "note": "No deployment history was available for this service.",
        }]

    timeline = _build_timeline(
        incident=incident,
        logs=logs_result["data"].get("logs", []) if logs_result.get("ok") else [],
        events=events_result["data"].get("events", []) if events_result.get("ok") else [],
        deployments=deployments_result["data"].get("deployments", []) if deployments_result.get("ok") else [],
    )

    dependencies = dependencies_result["data"].get("dependencies", []) if dependencies_result.get("ok") else []
    similar_matches = similar_result["data"].get("matches", []) if similar_result.get("ok") else []
    candidate_causes = _candidate_causes(incident, similar_matches, dependencies)

    evidence = []
    for item in symptoms:
        evidence.append({"item": item, "classification": "fact", "source": "incident symptoms"})
    if logs_result.get("ok"):
        for log in logs_result["data"].get("logs", [])[:3]:
            evidence.append({"item": log.get("message"), "classification": "fact", "source": "service logs"})
    if metrics_result.get("ok"):
        for metric_entry in metrics_result["data"].get("metric_history", [])[:2]:
            relevant_metrics = metric_entry.get("relevant_metrics", {})
            for key, value in relevant_metrics.items():
                evidence.append({"item": f"{key}={value}", "classification": "fact", "source": "service metrics"})
    if runbook_result.get("ok"):
        runbook = runbook_result["data"]
        evidence.append({"item": runbook.get("runbook", "No runbook available."), "classification": "fact", "source": "runbook"})
    if not evidence:
        evidence.append({"item": "Information unavailable: no direct evidence was available.", "classification": "fact", "source": "missing evidence"})

    uncertainties = []
    if not logs_result.get("ok"):
        uncertainties.append("Information unavailable: no service logs were available for this incident.")
    if not metrics_result.get("ok"):
        uncertainties.append("Information unavailable: no service metrics were available for this incident.")
    if not deployments_result.get("ok"):
        uncertainties.append("Information unavailable: no recent deployment history was available for this service.")
    if not dependencies_result.get("ok"):
        uncertainties.append("Information unavailable: no dependency data was available for this service.")
    if not similar_result.get("ok") or not similar_matches:
        uncertainties.append("Information unavailable: no similar incidents were available to compare against this incident.")
    if not uncertainties:
        uncertainties.append("No material uncertainties were identified from the available evidence.")

    current_state = (
        f"{incident.get('service')} is in a {incident.get('status', 'unknown')} state with "
        f"{len(symptoms)} symptom(s) and abnormal signal(s): {', '.join(abnormal_signals[:3])}."
    )

    return {
        "incident_id": incident_id,
        "current_state": current_state,
        "symptoms": symptoms,
        "affected_services": affected_services,
        "abnormal_signals": abnormal_signals,
        "recent_changes": recent_changes,
        "timeline": timeline,
        "candidate_causes": candidate_causes,
        "evidence": evidence,
        "uncertainties": uncertainties,
    }


__all__ = ["investigate_incident"]
