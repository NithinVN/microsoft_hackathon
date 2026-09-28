from __future__ import annotations

from collections import deque
from typing import Any, Dict, Iterable, List, Set

from backend.app.tools import execute_tool, get_incident_details, recall_similar_incidents

DEMO_SERVICE_GRAPH: Dict[str, List[str]] = {
    "payment-api": ["order-service", "database", "notification-service", "api-gateway"],
    "order-service": ["database", "payment-api", "notification-service", "api-gateway"],
    "user-service": ["database", "api-gateway", "notification-service", "authentication"],
    "notification-service": ["api-gateway", "user-service", "payment-api"],
    "database": ["payment-api", "order-service", "user-service", "api-gateway"],
    "api-gateway": ["payment-api", "order-service", "user-service", "notification-service"],
    "authentication": [],
}

KNOWN_SERVICES = sorted(DEMO_SERVICE_GRAPH.keys())


def _collect_propagation(service: str, max_depth: int = 2) -> Dict[str, Set[str]]:
    direct: Set[str] = set()
    potential: Set[str] = set()
    seen: Set[str] = {service}
    queue: deque[tuple[str, int]] = deque([(service, 0)])

    while queue:
        current, depth = queue.popleft()
        for neighbor in DEMO_SERVICE_GRAPH.get(current, []):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            if depth == 0:
                direct.add(neighbor)
            else:
                potential.add(neighbor)
            if depth < max_depth:
                queue.append((neighbor, depth + 1))

    return {"direct": direct, "potential": potential | direct}


def _service_reason(service: str, incident_service: str, incident_id: str, signals: List[str], similar_matches: List[Dict[str, Any]]) -> str:
    if service == incident_service:
        return f"{incident_service} is the directly affected service for {incident_id} and is producing the active incident signals: {', '.join(signals) if signals else 'no signal detail'} ."
    if service in DEMO_SERVICE_GRAPH.get(incident_service, []):
        return f"{service} is a direct dependency or adjacent dependency of {incident_service} in the demo dependency graph, so it is a likely propagation target for the active failure."
    if similar_matches:
        return f"This service appears in similar historical patterns for {incident_id} and shares the same dependency path in prior incidents."
    return f"This service is on the dependency path from {incident_service} and therefore could see downstream impact if the incident spreads across the graph."


def _build_user_impact(incident_service: str, direct_services: List[str], potential_services: List[str]) -> str:
    if not incident_service:
        return "Information unavailable: no service context was available for this incident."

    affected = sorted(set(direct_services) | set(potential_services))
    if incident_service in affected:
        impacted = [svc for svc in affected if svc != incident_service]
    else:
        impacted = affected

    if not impacted:
        return f"No customer-facing impact could be confirmed for {incident_service} from the current evidence."

    return (
        f"Customer-facing flows tied to {incident_service} may degrade or fail for users depending on "
        f"{', '.join(impacted[:3])}."
    )


def _severity_assessment(incident_service: str, direct_services: List[str], potential_services: List[str], signals: List[str]) -> str:
    if not incident_service:
        return "Information unavailable: no incident service was available."
    criticality = len(set(direct_services) | set(potential_services))
    if criticality >= 4 or any("latency" in signal.lower() or "timeout" in signal.lower() or "failure" in signal.lower() for signal in signals):
        return "High: the dependency path spans multiple critical services and user-facing flows are likely to be degraded."
    if criticality >= 2:
        return "Moderate: the affected dependency chain is limited but there is still user-facing impact risk."
    return "Low: the incident appears localized with limited propagation beyond the primary service."


def assess_blast_radius(incident_id: str) -> Dict[str, Any]:
    incident_result = get_incident_details({"incident_id": incident_id})
    if not incident_result.get("ok"):
        return {
            "directly_affected_services": [],
            "potentially_affected_services": [],
            "unaffected_services": [],
            "user_impact": "Information unavailable: no matching incident was found.",
            "severity_assessment": "Information unavailable: no service or dependency evidence was available.",
            "evidence": [
                {
                    "service": "none",
                    "reason": "Information unavailable: no matching incident was found.",
                    "source": "incident lookup",
                    "classification": "fact",
                }
            ],
        }

    incident = incident_result["data"]["incident"]
    service = incident.get("service")
    symptoms = incident.get("symptoms", [])
    alerts = incident.get("alerts", [])
    signals = list(symptoms) + list(alerts)

    direct_neighbors = DEMO_SERVICE_GRAPH.get(service, [])
    direct_affected = [service] if service else []
    direct_affected.extend(direct_neighbors)
    direct_affected = sorted(set(direct_affected))

    propagation = _collect_propagation(service, max_depth=2) if service else {"direct": set(), "potential": set()}
    potentially_affected = sorted(set(propagation["potential"]) - {service})
    unaffected = sorted(service for service in KNOWN_SERVICES if service not in direct_affected and service not in potentially_affected)

    similar_result = execute_tool(
        "recall_similar_incidents",
        {"query": " ".join(signals), "service": service, "limit": 3},
    ) if service else {"ok": False, "data": {}}
    similar_matches = similar_result.get("data", {}).get("matches", []) if similar_result.get("ok") else []

    evidence: List[Dict[str, Any]] = []
    for target in direct_affected + potentially_affected:
        if target == service:
            evidence.append({
                "service": target,
                "reason": _service_reason(target, service, incident_id, signals, similar_matches),
                "source": "incident signals",
                "classification": "fact",
            })
        else:
            evidence.append({
                "service": target,
                "reason": _service_reason(target, service, incident_id, signals, similar_matches),
                "source": "dependency graph",
                "classification": "hypothesis",
            })

    if not evidence:
        evidence.append({
            "service": service,
            "reason": "Information unavailable: no dependency or signal evidence existed for this incident.",
            "source": "missing evidence",
            "classification": "fact",
        })

    user_impact = _build_user_impact(service, direct_affected, potentially_affected)
    severity_assessment = _severity_assessment(service, direct_affected, potentially_affected, signals)

    return {
        "directly_affected_services": direct_affected,
        "potentially_affected_services": potentially_affected,
        "unaffected_services": unaffected,
        "user_impact": user_impact,
        "severity_assessment": severity_assessment,
        "evidence": evidence,
    }


__all__ = ["assess_blast_radius", "DEMO_SERVICE_GRAPH"]
