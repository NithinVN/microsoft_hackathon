from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _dedupe_strings(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    deduped: List[str] = []
    for value in values:
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _candidate_cause_texts(investigation: Optional[Dict[str, Any]]) -> List[str]:
    if not investigation:
        return []
    candidates: List[str] = []
    for item in investigation.get("candidate_causes", []) or []:
        if not isinstance(item, dict):
            continue
        text = _normalize_text(item.get("cause"))
        if text and "information unavailable" not in text.lower():
            candidates.append(text)
    return candidates


def _current_evidence_entries(investigation: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if not investigation:
        return entries

    for item in investigation.get("evidence", []) or []:
        if not isinstance(item, dict):
            continue
        text = _normalize_text(item.get("item") or item.get("detail") or item.get("reason"))
        if not text:
            continue
        source = _normalize_text(item.get("source") or "current telemetry")
        if source.lower() == "runbook":
            continue
        if source.lower() == "hindsight":
            continue
        entries.append({
            "evidence": text,
            "source": "current telemetry",
            "classification": _normalize_text(item.get("classification") or "fact"),
        })

    for text in _candidate_cause_texts(investigation):
        entries.append({
            "evidence": text,
            "source": "current telemetry",
            "classification": "hypothesis",
        })

    return entries


def _hindsight_evidence_entries(memory: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if not memory:
        return entries

    for item in memory.get("memory_sources", []) or []:
        if not isinstance(item, dict):
            continue
        content = _normalize_text(item.get("content"))
        if not content:
            continue
        entries.append({
            "evidence": content,
            "source": "Hindsight",
            "classification": _normalize_text(item.get("classification") or "historical_fact"),
            "memory_id": _normalize_text(item.get("memory_id") or "memory-unknown"),
        })

    for item in memory.get("similar_incidents", []) or []:
        if not isinstance(item, dict):
            continue
        text = _normalize_text(item.get("text") or item.get("root_cause") or item.get("incident_id") or "similar historical incident")
        if text:
            entries.append({
                "evidence": text,
                "source": "Hindsight",
                "classification": "historical_fact",
                "memory_id": _normalize_text(item.get("incident_id") or "similar-incident"),
            })

    return entries


def _runbook_evidence_entries(runbook: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if not runbook:
        return entries

    if isinstance(runbook, dict) and runbook.get("documents"):
        for document in runbook["documents"] or []:
            if not isinstance(document, dict):
                continue
            doc_name = _normalize_text(document.get("document_name"))
            section = _normalize_text(document.get("relevant_section"))
            text = _normalize_text(document.get("retrieved_text"))
            if not text:
                continue
            details = [part for part in [doc_name, section, text] if part]
            entries.append({
                "evidence": " | ".join(details[:3]),
                "source": "runbook",
                "classification": "operational_guidance",
                "document_name": doc_name,
                "relevant_section": section,
                "relevance_info": document.get("relevance_info", {}),
            })
        if entries:
            return entries

    if isinstance(runbook, dict) and runbook.get("data") and isinstance(runbook["data"], dict):
        payload = runbook["data"]
    else:
        payload = runbook

    runbook_text = _normalize_text(payload.get("runbook"))
    if runbook_text:
        entries.append({
            "evidence": runbook_text,
            "source": "runbook",
            "classification": "operational_guidance",
        })

    for step in payload.get("steps", []) or []:
        text = _normalize_text(step)
        if text:
            entries.append({
                "evidence": text,
                "source": "runbook",
                "classification": "operational_guidance",
            })

    return entries


def _historical_matches(memory: Optional[Dict[str, Any]]) -> List[str]:
    matches: List[str] = []
    if not memory:
        return matches

    for incident in memory.get("similar_incidents", []) or []:
        if not isinstance(incident, dict):
            continue
        item_id = _normalize_text(incident.get("incident_id") or incident.get("id") or incident.get("memory_id"))
        if item_id:
            matches.append(item_id)
    for entry in memory.get("memory_sources", []) or []:
        if not isinstance(entry, dict):
            continue
        item_id = _normalize_text(entry.get("memory_id"))
        if item_id and item_id not in matches:
            matches.append(item_id)
    return matches


def _candidate_rank(investigation: Dict[str, Any], blast_radius: Dict[str, Any], memory: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
    candidates = _candidate_cause_texts(investigation)
    if not candidates:
        return (
            "Information unavailable: no reliable root-cause hypothesis could be derived from current telemetry, dependency evidence, or historical memory.",
            [],
            [],
        )

    ranked: List[Tuple[str, int]] = []
    for cause in candidates:
        score = 0
        lc = cause.lower()
        if any(token in lc for token in ["thread", "latency", "timeout", "payment", "gateway", "database", "pool", "deserialization", "poison", "queue", "circuit"]):
            score += 3
        if any(token in lc for token in ["payment", "gateway", "thread", "database", "deserialization", "poison", "connection"]):
            score += 1

        if blast_radius and isinstance(blast_radius, dict):
            service_names = (blast_radius.get("directly_affected_services") or []) + (blast_radius.get("potentially_affected_services") or [])
            if any(service in lc.lower() for service in [str(item).lower() for item in service_names]):
                score += 2

        if memory and isinstance(memory, dict):
            memory_sources = memory.get("memory_sources", []) or []
            if any(cause.lower() in str(source.get("content", "")).lower() for source in memory_sources if isinstance(source, dict)):
                score += 3
            if memory.get("similar_incidents"):
                score += 1

        ranked.append((cause, score))

    ranked.sort(key=lambda pair: pair[1], reverse=True)

    selected = ranked[0][0]
    alternatives = [item for item, _ in ranked[1:] if item != selected]
    return selected, ranked[0:1], alternatives


def diagnose_incident(
    investigation: Optional[Dict[str, Any]],
    blast_radius: Optional[Dict[str, Any]],
    memory: Optional[Dict[str, Any]],
    runbook: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if investigation is None:
        investigation = {}
    if blast_radius is None:
        blast_radius = {}
    if memory is None:
        memory = {}

    current_evidence = _current_evidence_entries(investigation)
    hindsight_evidence = _hindsight_evidence_entries(memory)
    runbook_evidence = _runbook_evidence_entries(runbook)

    if not investigation and not blast_radius and not memory and not runbook:
        return {
            "primary_hypothesis": "Information unavailable: no reliable root-cause hypothesis could be derived from the available evidence.",
            "confidence": 0.0,
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "historical_matches": [],
            "alternative_hypotheses": [
                "Current telemetry may reveal a service-level failure once logs or metrics are available.",
                "A dependency or upstream outage may be driving the observed symptoms once broader service data arrives.",
            ],
            "recommended_next_checks": [
                "Collect fresh service logs and metric snapshots for the affected service.",
                "Confirm whether downstream dependencies or upstream providers are experiencing abnormal behavior.",
                "Retrieve the service-specific runbook and compare its guidance against the active symptoms.",
            ],
        }

    selected_hypothesis, _, alternatives = _candidate_rank(investigation, blast_radius, memory)
    if "information unavailable" in selected_hypothesis.lower():
        confidence = 0.1
        supporting: List[Dict[str, Any]] = []
        contradicting = [
            {"evidence": item["evidence"], "source": item["source"], "classification": item["classification"]}
            for item in current_evidence[:3]
        ]
        historical_matches = _historical_matches(memory)
        return {
            "primary_hypothesis": selected_hypothesis,
            "confidence": round(confidence, 2),
            "supporting_evidence": supporting,
            "contradicting_evidence": contradicting,
            "historical_matches": historical_matches,
            "alternative_hypotheses": alternatives or [
                "The issue may be caused by a dependency failure, upstream provider degradation, or another service not yet evidenced in the current telemetry.",
            ],
            "recommended_next_checks": [
                "Collect the affected service's recent logs, metrics, and dependency health before making a diagnostic claim.",
                "Check whether a similar outcome has occurred in Hindsight and compare it to the current signal set.",
                "Review the service runbook to determine the next approved validation step.",
            ],
        }

    supporting: List[Dict[str, Any]] = []
    for item in current_evidence:
        if item["evidence"].lower() == selected_hypothesis.lower():
            supporting.append({**item, "source": "current telemetry"})
        elif item["source"] == "current telemetry":
            supporting.append({**item})
    for item in hindsight_evidence:
        if selected_hypothesis.lower() in item["evidence"].lower() or any(token in item["evidence"].lower() for token in ["payment", "thread", "database", "gateway", "queue", "deserialization", "connection"] if token in selected_hypothesis.lower()):
            supporting.append({
                "evidence": item["evidence"],
                "source": "Hindsight",
                "classification": item["classification"],
            })
    for item in runbook_evidence:
        text = item.get("evidence", "").lower()
        hypothesis_tokens = [token for token in selected_hypothesis.lower().split() if len(token) > 3]
        if not hypothesis_tokens:
            supporting.append({
                "evidence": item["evidence"],
                "source": "runbook",
                "classification": item["classification"],
            })
            continue
        if any(token in text for token in hypothesis_tokens):
            supporting.append({
                "evidence": item["evidence"],
                "source": "runbook",
                "classification": item["classification"],
            })
        elif any(token in text for token in ["connection", "database", "latency", "timeout", "queue", "retry", "rollback", "dependency", "memory"]):
            supporting.append({
                "evidence": item["evidence"],
                "source": "runbook",
                "classification": item["classification"],
            })

    if not supporting:
        supporting = [
            {"evidence": selected_hypothesis, "source": "current telemetry", "classification": "hypothesis"}
        ]

    conflicting: List[Dict[str, Any]] = []
    for item in current_evidence:
        if item["evidence"].lower() != selected_hypothesis.lower() and any(other.lower() in item["evidence"].lower() for other in ["database", "payment", "gateway", "thread", "queue", "connection", "deserialization"]) and item["evidence"].lower() not in selected_hypothesis.lower():
            conflicting.append({**item})
    for candidate in alternatives:
        conflicting.append({
            "evidence": candidate,
            "source": "current telemetry",
            "classification": "hypothesis",
        })

    confidence = 0.45
    confidence += 0.15 * min(2, len([entry for entry in supporting if entry.get("source") == "current telemetry"]))
    confidence += 0.12 * min(2, len([entry for entry in supporting if entry.get("source") == "Hindsight"]))
    confidence += 0.08 * min(2, len([entry for entry in supporting if entry.get("source") == "runbook"]))
    if memory.get("memory_confidence"):
        confidence += min(0.18, float(memory.get("memory_confidence", 0)) * 0.2)
    if conflicting:
        confidence -= min(0.22, 0.08 * len(conflicting))
    if alternatives and conflicting:
        confidence = min(confidence, 0.79)
    if not (current_evidence or hindsight_evidence or runbook_evidence):
        confidence = 0.1
    confidence = max(0.0, min(0.96, round(confidence, 2)))

    recommended_next_checks = [
        "Validate the active logs and metrics for the identified service before treating the hypothesis as a confirmed root cause.",
        "Check whether the same pattern appears in Hindsight and compare known-fix outcomes with the current recovery strategy.",
        "Confirm the runbook's guardrails and next-step checks against the current system state.",
    ]
    if runbook_evidence:
        recommended_next_checks.append("Apply the approved runbook steps in the order they are listed and stop if any guardrail is violated.")
    if blast_radius.get("directly_affected_services"):
        recommended_next_checks.append("Review the dependency chain around the directly affected services to rule out secondary blast-radius contributors.")

    primary_hypothesis = selected_hypothesis
    if memory.get("similar_incidents"):
        primary_hypothesis = f"The strongest current hypothesis is {selected_hypothesis}; historical similarity is relevant but not conclusive, because the current telemetry still needs direct validation."

    return {
        "primary_hypothesis": primary_hypothesis,
        "confidence": confidence,
        "supporting_evidence": _dedupe_supporting(supporting),
        "contradicting_evidence": _dedupe_supporting(conflicting),
        "historical_matches": _historical_matches(memory),
        "alternative_hypotheses": alternatives or [
            "The issue may be caused by a dependency failure, upstream provider degradation, or another service not yet evidenced in the current telemetry.",
        ],
        "recommended_next_checks": _dedupe_strings(recommended_next_checks),
    }


def _dedupe_supporting(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        evidence = _normalize_text(item.get("evidence"))
        source = _normalize_text(item.get("source"))
        if not evidence:
            continue
        key = f"{source}|{evidence}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append({
            "evidence": evidence,
            "source": source or "current telemetry",
            "classification": _normalize_text(item.get("classification") or "hypothesis"),
        })
    return deduped


__all__ = ["diagnose_incident"]
