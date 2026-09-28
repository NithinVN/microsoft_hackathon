from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from backend.app.memory.hindsight_service import hindsight_service
from backend.app.tools import get_incident_details


def _local_incident_dataset() -> List[Dict[str, Any]]:
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


def _normalise_memory_item(item: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {
            "memory_id": "memory-unknown",
            "service": "",
            "type": "memory",
            "content": str(item or ""),
            "tags": [],
            "metadata": {},
            "score": None,
        }

    metadata = item.get("metadata") or {}
    return {
        "memory_id": item.get("id") or metadata.get("incident_id") or metadata.get("document_id") or "memory-unknown",
        "service": item.get("service") or metadata.get("service") or "",
        "type": item.get("type") or "memory",
        "content": item.get("text") or item.get("content") or str(item),
        "tags": item.get("tags") or [],
        "metadata": metadata,
        "score": item.get("score"),
    }


def _score_memory_confidence(seed_count: int, sources: List[Dict[str, Any]]) -> float:
    if not sources:
        return 0.0
    base = min(0.45, 0.15 * seed_count)
    weighted = 0.0
    for source in sources:
        score = source.get("score")
        if isinstance(score, (int, float)):
            weighted += float(score)
    if not weighted:
        weighted = float(min(1.0, len(sources) * 0.15))
    confidence = min(0.96, base + (weighted / max(1, len(sources)) * 0.65))
    return round(confidence, 2)


def _local_memory_retrieval(incident: Dict[str, Any], limit: int = 5) -> Dict[str, List[Dict[str, Any]]]:
    dataset = _local_incident_dataset()
    if not dataset:
        return {
            "similar": [],
            "root_causes": [],
            "successful_fixes": [],
            "failed_fixes": [],
            "lessons": [],
        }

    service = (incident or {}).get("service")
    query_text = " ".join((incident or {}).get("symptoms", []) + (incident or {}).get("alerts", [])).lower()
    selected: List[Dict[str, Any]] = []
    for record in dataset:
        if service and record.get("service") != service:
            continue
        if not query_text:
            selected.append(record)
            continue
        combined = " ".join([
            record.get("title", ""),
            record.get("service", ""),
            *record.get("symptoms", []),
            *record.get("alerts", []),
            record.get("root_cause", ""),
        ]).lower()
        if query_text and any(piece in combined for piece in [p.lower() for p in query_text.split() if len(p) > 3]):
            selected.append(record)

    similar = []
    for record in selected[:limit]:
        similar.append({
            "id": record.get("incident_id"),
            "text": f"{record.get('title')} - {record.get('root_cause')}",
            "service": record.get("service"),
            "type": "incident",
            "tags": ["incident", f"service:{record.get('service', '').lower()}"],
            "metadata": {"incident_id": record.get("incident_id"), "service": record.get("service")},
            "score": 0.65,
        })

    root_causes = []
    for record in dataset[:limit]:
        cause = record.get("root_cause")
        if cause:
            root_causes.append({
                "id": f"root-{record.get('incident_id')}",
                "text": cause,
                "service": record.get("service"),
                "type": "root_cause",
                "tags": ["root_cause", f"service:{record.get('service', '').lower()}"],
                "metadata": {"incident_id": record.get("incident_id"), "service": record.get("service"), "type": "root_cause"},
                "score": 0.7,
            })

    successful_fixes = []
    for record in dataset:
        for action in record.get("successful_actions", []) or []:
            successful_fixes.append({
                "id": f"fix-success-{record.get('incident_id')}-{action}",
                "text": f"{action} was successful on {record.get('service')}",
                "service": record.get("service"),
                "type": "successful_fix",
                "tags": ["remediation", "outcome:successful"],
                "metadata": {"incident_id": record.get("incident_id"), "service": record.get("service"), "action_type": action},
                "score": 0.75,
            })
        if len(successful_fixes) >= limit:
            break

    failed_fixes = []
    for record in dataset:
        for action in record.get("failed_actions", []) or []:
            failed_fixes.append({
                "id": f"fix-failed-{record.get('incident_id')}-{action}",
                "text": f"{action} failed on {record.get('service')}",
                "service": record.get("service"),
                "type": "failed_fix",
                "tags": ["remediation", "outcome:failed"],
                "metadata": {"incident_id": record.get("incident_id"), "service": record.get("service"), "action_type": action},
                "score": 0.72,
            })
        if len(failed_fixes) >= limit:
            break

    lessons = []
    for record in dataset:
        for lesson in record.get("lessons_learned", []) or []:
            lessons.append({
                "id": f"lesson-{record.get('incident_id')}",
                "text": lesson,
                "service": record.get("service"),
                "type": "lesson",
                "tags": ["postmortem", "lessons_learned"],
                "metadata": {"incident_id": record.get("incident_id"), "service": record.get("service")},
                "score": 0.7,
            })
        if len(lessons) >= limit:
            break

    return {
        "similar": similar,
        "root_causes": root_causes,
        "successful_fixes": successful_fixes,
        "failed_fixes": failed_fixes,
        "lessons": lessons,
    }


def _as_memory_entry_list(values: Iterable[Any]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for value in values:
        item = _normalise_memory_item(value)
        entries.append(item)
    return entries


def _build_memory_sources(memory_groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    for group in memory_groups:
        for entry in group:
            source = _normalise_memory_item(entry)
            items = source["content"]
            if not items:
                continue
            sources.append({
                "memory_id": source["memory_id"],
                "service": source["service"],
                "content": items,
                "classification": "historical_fact",
                "source": "Hindsight recall",
                "type": source["type"],
                "supporting_evidence": [source["memory_id"]],
            })
    return sources


def _summarise_reflection(reflection: Dict[str, Any]) -> Dict[str, Any]:
    if not reflection or reflection.get("success") is False:
        return {"pattern": "Historical pattern synthesis unavailable; memory evidence is insufficient.", "supporting_evidence": [], "classification": "current_inference"}

    text = reflection.get("text") or "No pattern synthesis available."
    facts = reflection.get("based_on") or []
    supporting = []
    for fact in facts:
        if isinstance(fact, dict):
            supporting.append(fact.get("id") or fact.get("memory_id") or fact.get("incident_id") or "memory-unknown")
        else:
            supporting.append(str(fact))
    return {
        "pattern": text,
        "supporting_evidence": supporting or ["reflective-synthesis"],
        "classification": "current_inference",
    }


def assess_incident_memory(incident_id: str) -> Dict[str, Any]:
    incident_response = get_incident_details({"incident_id": incident_id})
    if not incident_response.get("ok"):
        return {
            "similar_incidents": [],
            "historical_root_causes": [],
            "successful_fixes": [],
            "failed_fixes": [],
            "engineer_lessons": [],
            "historical_patterns": [],
            "memory_confidence": 0,
            "memory_sources": [{
                "memory_id": "memory-missing",
                "service": "",
                "content": "Information unavailable: no matching incident was found for this identifier; no historical memory could be retrieved.",
                "classification": "historical_fact",
                "source": "incident lookup",
                "type": "incident_lookup",
                "supporting_evidence": [],
            }],
        }

    incident = incident_response["data"]["incident"]
    service = incident.get("service")
    query_text = " ".join((incident.get("symptoms") or []) + (incident.get("alerts") or []) + [incident.get("root_cause") or ""])

    similar_results = hindsight_service.recall_similar_incidents(query=query_text, service=service, limit=5)
    if not similar_results:
        similar_results = _local_memory_retrieval(incident, limit=5)["similar"]

    successful_results = hindsight_service.recall_successful_remediations(service=service, query=query_text)
    if not successful_results:
        successful_results = _local_memory_retrieval(incident, limit=5)["successful_fixes"]
    successful_results = successful_results[:5]

    failed_results = hindsight_service.recall_failed_remediations(service=service, query=query_text)
    if not failed_results:
        failed_results = _local_memory_retrieval(incident, limit=5)["failed_fixes"]
    failed_results = failed_results[:5]

    reflection = hindsight_service.reflect_on_incident_history(
        query=f"What patterns repeat for {service} and {incident_id}?",
        context=f"Current incident: {incident.get('title')} / {query_text}",
        service=service,
    )

    pattern_summary = _summarise_reflection(reflection)
    lessons = []
    for result in similar_results + successful_results + failed_results:
        text = (result.get("text") or "")
        normalized = text.lower()
        if "lessons" in normalized or "never" in normalized or "always" in normalized or "avoid" in normalized:
            lessons.append({
                "lesson": text,
                "supporting_evidence": [result.get("id") or result.get("memory_id") or "memory-unknown"],
                "classification": "historical_fact",
            })
    if not lessons:
        local_lessons = _local_memory_retrieval(incident, limit=5)["lessons"]
        for item in local_lessons:
            lessons.append({
                "lesson": item.get("text") or item.get("content") or "",
                "supporting_evidence": [item.get("id") or item.get("memory_id") or "memory-unknown"],
                "classification": "historical_fact",
            })

    historical_root_causes = []
    for result in similar_results:
        cause = result.get("metadata", {}).get("root_cause") or result.get("root_cause")
        if cause:
            historical_root_causes.append({
                "root_cause": cause,
                "supporting_evidence": [result.get("id") or result.get("memory_id") or "memory-unknown"],
                "classification": "historical_fact",
                "service": result.get("service") or (result.get("metadata") or {}).get("service"),
            })
        elif result.get("text"):
            historical_root_causes.append({
                "root_cause": result.get("text"),
                "supporting_evidence": [result.get("id") or result.get("memory_id") or "memory-unknown"],
                "classification": "historical_fact",
                "service": result.get("service") or (result.get("metadata") or {}).get("service"),
            })

    if not historical_root_causes:
        for item in _local_memory_retrieval(incident, limit=5)["root_causes"]:
            historical_root_causes.append({
                "root_cause": item.get("text") or item.get("content") or "",
                "supporting_evidence": [item.get("id") or item.get("memory_id") or "memory-unknown"],
                "classification": "historical_fact",
                "service": item.get("service"),
            })

    successful_fixes = []
    for result in successful_results:
        successful_fixes.append({
            "action": result.get("metadata", {}).get("action_type") or result.get("text") or "successful remediation",
            "supporting_evidence": [result.get("id") or result.get("memory_id") or "memory-unknown"],
            "classification": "historical_fact",
            "service": result.get("service") or (result.get("metadata") or {}).get("service"),
        })

    failed_fixes = []
    for result in failed_results:
        failed_fixes.append({
            "action": result.get("metadata", {}).get("action_type") or result.get("text") or "failed remediation",
            "supporting_evidence": [result.get("id") or result.get("memory_id") or "memory-unknown"],
            "classification": "historical_fact",
            "service": result.get("service") or (result.get("metadata") or {}).get("service"),
        })

    memory_sources = _build_memory_sources([similar_results, successful_results, failed_results])
    if reflection.get("based_on"):
        memory_sources.append({
            "memory_id": "reflective-synthesis",
            "service": service or "",
            "content": pattern_summary["pattern"],
            "classification": pattern_summary["classification"],
            "source": "Hindsight reflect",
            "type": "reflective_summary",
            "supporting_evidence": pattern_summary["supporting_evidence"],
        })

    if not memory_sources:
        memory_sources = [{
            "memory_id": "memory-unavailable",
            "service": service or "",
            "content": "Information unavailable: no historical memory was retrieved from Hindsight for this incident.",
            "classification": "historical_fact",
            "source": "Hindsight recall",
            "type": "memory_gap",
            "supporting_evidence": [],
        }]

    confidence = _score_memory_confidence(
        seed_count=len([item for item in memory_sources if item.get("memory_id") and item.get("memory_id") != "memory-unavailable"]),
        sources=memory_sources,
    )

    return {
        "similar_incidents": _as_memory_entry_list(similar_results),
        "historical_root_causes": historical_root_causes,
        "successful_fixes": successful_fixes,
        "failed_fixes": failed_fixes,
        "engineer_lessons": lessons,
        "historical_patterns": [pattern_summary],
        "memory_confidence": confidence,
        "memory_sources": memory_sources,
    }


__all__ = ["assess_incident_memory"]
