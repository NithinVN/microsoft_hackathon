from __future__ import annotations

from typing import Any, Dict, List, Optional


def _normalise_action(action: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "action": action.get("action") or action.get("action_type") or "UNKNOWN_ACTION",
        "reason": action.get("reason") or "No rationale supplied.",
        "expected_outcome": action.get("expected_outcome") or "The action should reduce the active incident signal without requiring direct production execution.",
        "risk": action.get("risk") or "medium",
        "historical_evidence": action.get("historical_evidence") or [],
        "required_approval": action.get("required_approval") or "human approval required",
        "status": action.get("status") or "pending",
        "mode": action.get("mode") or "simulation",
    }


def _recommend_from_diagnosis(incident: Dict[str, Any], diagnosis: Dict[str, Any], memory: Dict[str, Any], runbooks: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    hypothesis = diagnosis.get("primary_hypothesis") or "An unknown service degradation is likely driving the active incident."
    confidence = float(diagnosis.get("confidence", 0.0) or 0.0)

    recommendations: List[Dict[str, Any]] = []

    if "payment" in hypothesis.lower() or "thread" in hypothesis.lower() or "latency" in hypothesis.lower():
        recommendations.append({
            "action": "ENABLE_CIRCUIT_BREAKER",
            "reason": "Fail fast on slow outbound dependencies to stop thread starvation and queue buildup.",
            "expected_outcome": "Reduce the backlog of pending requests and keep payment threads available for healthy traffic.",
            "risk": "medium",
            "historical_evidence": ["INC-H102"],
            "required_approval": "human approval required",
            "status": "pending",
            "mode": "simulation",
        })
    if "database" in hypothesis.lower() or "connection" in hypothesis.lower() or "pool" in hypothesis.lower():
        recommendations.append({
            "action": "SCALE_CONNECTION_POOL",
            "reason": "Increase headroom for active connections and drain idle sessions before rerunning throughput under peak load.",
            "expected_outcome": "Reduce connection saturation and restore checkouts or writes to stable throughput.",
            "risk": "medium",
            "historical_evidence": ["INC-H101"],
            "required_approval": "human approval required",
            "status": "pending",
            "mode": "simulation",
        })
    if "gateway" in hypothesis.lower() or "rollback" in hypothesis.lower() or "config" in hypothesis.lower():
        recommendations.append({
            "action": "ROLLBACK_DEPLOYMENT",
            "reason": "Revert the last known bad gateway configuration or release before more user traffic is impacted.",
            "expected_outcome": "Restore healthy routing and reduce global 5xx errors after the failed deployment is isolated.",
            "risk": "high",
            "historical_evidence": ["INC-H104"],
            "required_approval": "human approval required",
            "status": "pending",
            "mode": "simulation",
        })
    if not recommendations:
        recommendations.append({
            "action": "CHECK_DEPENDENCY_HEALTH",
            "reason": "No direct failure mode is strongly supported yet; begin with the dependency path and service health review.",
            "expected_outcome": "Confirm whether the degraded user impact is caused by an upstream service, queue, or config path.",
            "risk": "low",
            "historical_evidence": [],
            "required_approval": "human approval required",
            "status": "pending",
            "mode": "simulation",
        })

    if confidence < 0.5:
        for item in recommendations:
            item["risk"] = "high"
            item["required_approval"] = "human approval required"
            item["is_low_confidence"] = True

    if memory and isinstance(memory, dict):
        memory_sources = memory.get("memory_sources") or []
        for item in recommendations:
            item["historical_evidence"] = [
                source.get("memory_id") or "memory-unknown"
                for source in memory_sources
                if isinstance(source, dict)
                and any(token in str(source.get("content", "")).lower() for token in [
                    "circuit", "connection", "rollback", "thread", "latency", "dependency", "queue"
                ])
            ] or item.get("historical_evidence") or []

    if runbooks and isinstance(runbooks, dict):
        docs = runbooks.get("documents") or []
        for item in recommendations:
            if docs:
                item["runbook_reference"] = docs[0].get("document_name")

    return [_normalise_action(item) for item in recommendations]


def build_remediation_plan(
    investigation: Dict[str, Any],
    blast_radius: Dict[str, Any],
    diagnosis: Dict[str, Any],
    memory: Dict[str, Any],
    runbooks: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    actions = _recommend_from_diagnosis(investigation or {}, diagnosis or {}, memory or {}, runbooks)
    rationale = (
        "This remediation plan is simulation-only and requires a human approval step before any action reaches production. "
        "No production execution is allowed in this layer; all actions are dry-run recommendations only."
    )

    historical_support = []
    if memory and isinstance(memory, dict):
        historical_support = [
            {
                "memory_id": source.get("memory_id") or "memory-unknown",
                "content": source.get("content") or "",
                "source": source.get("source") or "Hindsight",
            }
            for source in (memory.get("memory_sources") or [])
            if isinstance(source, dict)
        ]

    risk_level = "medium"
    if diagnosis and float(diagnosis.get("confidence", 0.0) or 0.0) < 0.5:
        risk_level = "high"
    elif blast_radius and isinstance(blast_radius, dict) and blast_radius.get("potentially_affected_services"):
        risk_level = "high"

    rollback_plan = (
        "If the approved action worsens the incident or conflicts with the runbook, immediately stop the simulation, "
        "revert to the last known good configuration, and re-check service health before proceeding."
    )

    verification_steps = [
        "Confirm the affected service's immediate telemetry has improved and the symptom cluster is trending back toward baseline.",
        "Verify that no new dependency or blast-radius failures have appeared after the simulated intervention.",
        "Re-run the runbook checks and confirm the recovery step did not violate any safety guardrail.",
    ]

    return {
        "recommended_actions": actions,
        "why": rationale,
        "historical_support": historical_support,
        "risk_level": risk_level,
        "rollback_plan": rollback_plan,
        "verification_steps": verification_steps,
    }


def approve_action(plan: Dict[str, Any], index: int, actor: str) -> Dict[str, Any]:
    actions = plan.get("recommended_actions") or []
    if not 0 <= index < len(actions):
        raise IndexError("Action index out of range")

    action = actions[index]
    action["status"] = "approved"
    action["approved_by"] = actor
    action["required_approval"] = "approved by human"
    return plan


def reject_action(plan: Dict[str, Any], index: int, reason: str) -> Dict[str, Any]:
    actions = plan.get("recommended_actions") or []
    if not 0 <= index < len(actions):
        raise IndexError("Action index out of range")

    action = actions[index]
    action["status"] = "rejected"
    action["rejection_reason"] = reason
    action["required_approval"] = "human approval required"
    return plan


def modify_action(plan: Dict[str, Any], index: int, replacement_action: str) -> Dict[str, Any]:
    actions = plan.get("recommended_actions") or []
    if not 0 <= index < len(actions):
        raise IndexError("Action index out of range")

    action = actions[index]
    action["action"] = replacement_action
    action["status"] = "pending"
    action["required_approval"] = "human approval required"
    action["mode"] = "simulation"
    return plan


__all__ = [
    "build_remediation_plan",
    "approve_action",
    "reject_action",
    "modify_action",
]
