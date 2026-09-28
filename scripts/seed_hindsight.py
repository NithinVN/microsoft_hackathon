"""IncidentMind - Hindsight Organizational Memory Seeding Script.

Loads 22+ realistic production incidents across payment-api, order-service,
user-service, notification-service, database, and API gateway into Hindsight Cloud.

Retains:
1. Incident Records (Symptoms, Alerts, Telemetry, Context)
2. Root Cause Diagnoses
3. Verified Successful Remediations (for Time Machine past matches)
4. Disastrous Failed Fixes (for Failed-Fix Time Machine safety warnings)
5. Senior Engineer Feedback & Ratings
6. Postmortem Analyses & Organizational Lessons Learned

After seeding, executes diagnostic recall queries to demonstrate memory retrieval.

Usage:
    python scripts/seed_hindsight.py
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is in pythonpath
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.memory.hindsight_service import hindsight_service


def load_historical_incidents() -> List[Dict[str, Any]]:
    """Loads rich historical incident dataset from JSON file."""
    data_path = Path(__file__).resolve().parent.parent / "data" / "historical_incidents.json"
    if not data_path.exists():
        raise FileNotFoundError(f"Historical incident dataset not found at: {data_path}")

    with open(data_path, "r", encoding="utf-8") as f:
        incidents = json.load(f)
    return incidents


def _incident_search_text(incident: Dict[str, Any]) -> str:
    """Build a normalized searchable text blob for a historical incident."""
    parts = [
        incident.get("incident_id", ""),
        incident.get("title", ""),
        incident.get("service", ""),
        " ".join(incident.get("symptoms", []) or []),
        " ".join(incident.get("alerts", []) or []),
        incident.get("root_cause", ""),
        incident.get("final_outcome", ""),
        " ".join(incident.get("lessons_learned", []) or []),
    ]
    return " ".join(part for part in parts if part)


def local_recall_incidents(query: str, service: str | None = None, limit: int = 5) -> List[Dict[str, Any]]:
    """Return local match results from the dataset when the live Hindsight bank is unavailable."""
    query_tokens = [token.lower() for token in str(query).replace("-", " ").split() if token.strip()]
    matches: List[Dict[str, Any]] = []

    for incident in load_historical_incidents():
        if service and incident.get("service") != service:
            continue

        search_text = _incident_search_text(incident).lower()
        score = 0
        for token in query_tokens:
            if token in search_text:
                score += 2
        if incident.get("service", "").lower() in query.lower():
            score += 3
        if incident.get("title", "").lower() in query.lower():
            score += 5

        if score > 0:
            incident_id = incident.get("incident_id")
            matches.append({
                "id": incident_id,
                "incident_id": incident_id,
                "service": incident.get("service"),
                "title": incident.get("title"),
                "score": score,
                "tags": [incident.get("service"), incident.get("severity", "")],
                "text": (
                    f"{incident.get('incident_id')} | {incident.get('service')} | "
                    f"{incident.get('title')} | root cause: {incident.get('root_cause', '')}"
                )[:400],
            })

    matches.sort(key=lambda item: item["score"], reverse=True)
    return matches[:limit]


def local_failed_remediation_recall(service: str | None = None, action_type: str | None = None, limit: int = 5) -> List[Dict[str, Any]]:
    """Return local failed-fix warnings from the dataset without requiring a live Hindsight recall."""
    matches: List[Dict[str, Any]] = []
    for incident in load_historical_incidents():
        if service and incident.get("service") != service:
            continue
        for action in incident.get("actions_attempted", []):
            if action.get("outcome") != "failed":
                continue
            if action_type and action.get("action_type", "").lower() != str(action_type).lower():
                continue
            matches.append({
                "id": incident.get("incident_id"),
                "service": incident.get("service"),
                "tags": ["warning:failed_fix", f"service:{incident.get('service')}"],
                "text": (
                    f"Failed remediation on {incident.get('incident_id')} ({incident.get('service')}): "
                    f"{action.get('action_type')} failed because {action.get('reason', '')}"
                )[:400],
            })
            break
    return matches[:limit]


def seed_hindsight_memory_bank():
    """Main seeding pipeline for Hindsight organizational memory bank."""
    print("=" * 80)
    print("IncidentMind: Seeding Hindsight Cloud Institutional Memory Bank")
    print("=" * 80)
    print(f"Target Hindsight URL:  {settings.HINDSIGHT_BASE_URL}")
    print(f"Target Memory Bank ID: {settings.HINDSIGHT_BANK_ID}")
    print("-" * 80)

    # 1. Load Dataset
    incidents = load_historical_incidents()
    print(f"Loaded {len(incidents)} rich historical incidents across core services:")
    services_count = {}
    for inc in incidents:
        svc = inc.get("service", "unknown")
        services_count[svc] = services_count.get(svc, 0) + 1
    for svc, count in services_count.items():
        print(f"  - {svc:22}: {count} incidents")
    print("-" * 80)

    # 2. Initialize Memory Bank
    print("\n[Step 1/3] Initializing Hindsight Memory Bank...")
    bank_resp = hindsight_service.create_memory_bank(
        name=f"IncidentMind SRE Memory ({settings.HINDSIGHT_BANK_ID})",
        mission=(
            "Enterprise Site Reliability Engineering institutional memory. "
            "Stores incident forensic timelines, root causes, proven successful fixes, "
            "dangerous failed fixes to avoid, engineer feedback, and postmortems."
        ),
    )
    print(f"Memory Bank Status: {'Ready' if bank_resp.get('success') else 'API Warning'}")
    if not bank_resp.get("success"):
        print(f"  Note: {bank_resp.get('error')}")

    # 3. Retain Incidents, Root Causes, Fixes, Feedback, and Postmortems
    print("\n[Step 2/3] Retaining Historical Incidents & Memory Units into Hindsight...")
    total_retained = 0
    successful_fixes_retained = 0
    failed_fixes_retained = 0

    for idx, inc in enumerate(incidents, start=1):
        inc_id = inc["incident_id"]
        svc = inc["service"]
        title = inc["title"]
        print(f"  [{idx:02d}/{len(incidents)}] Retaining {inc_id} ({svc}): {title[:40]}...")

        # A. Retain Incident Context
        hindsight_service.retain_incident(inc)
        total_retained += 1

        # B. Retain Root Cause Knowledge
        if inc.get("root_cause"):
            hindsight_service.retain_root_cause(
                incident_id=inc_id,
                service=svc,
                root_cause=inc["root_cause"],
                evidence={
                    "metrics": inc.get("relevant_metrics", {}),
                    "alerts": inc.get("alerts", []),
                    "deployment": inc.get("deployment_context", {}),
                },
            )
            total_retained += 1

        # C. Retain Attempted Actions (both Successful and Failed)
        for action in inc.get("actions_attempted", []):
            action_type = action.get("action_type", "UNKNOWN_ACTION")
            params = action.get("parameters", {})
            outcome = action.get("outcome", "unknown")
            reason = action.get("reason", "")

            if outcome == "successful":
                hindsight_service.retain_successful_fix(
                    incident_id=inc_id,
                    service=svc,
                    action_type=action_type,
                    parameters=params,
                    rationale=f"Resolved incident {inc_id} by {reason}",
                    outcome_notes=inc.get("final_outcome", "Successfully resolved."),
                )
                successful_fixes_retained += 1
                total_retained += 1
            elif outcome == "failed":
                hindsight_service.retain_failed_fix(
                    incident_id=inc_id,
                    service=svc,
                    action_type=action_type,
                    parameters=params,
                    failure_reason=reason,
                    unintended_consequences=f"Failed attempt during incident {inc_id}: {reason}",
                )
                failed_fixes_retained += 1
                total_retained += 1

        # D. Retain Senior Engineer Feedback
        fb = inc.get("engineer_feedback", {})
        if fb:
            hindsight_service.retain_engineer_feedback(
                incident_id=inc_id,
                service=svc,
                engineer_id=fb.get("engineer", "sre_team"),
                rating=fb.get("rating", "5_stars"),
                feedback_text=fb.get("comment", ""),
                tags=[f"engineer:{fb.get('engineer', 'sre_team')}"],
            )
            total_retained += 1

        # E. Retain Postmortem Analysis
        if inc.get("lessons_learned") or inc.get("final_outcome"):
            hindsight_service.retain_postmortem(
                incident_id=inc_id,
                service=svc,
                executive_summary=inc.get("final_outcome", ""),
                root_cause_analysis=inc.get("root_cause", ""),
                lessons_learned=inc.get("lessons_learned", []),
                preventive_actions=[
                    f"Implement automated alerting and runbook validation for {svc}.",
                    *(inc.get("lessons_learned", [])[:1]),
                ],
            )
            total_retained += 1

    print("\n" + "-" * 80)
    print("Hindsight Seeding Summary:")
    print(f"  Total Historical Incidents:     {len(incidents)}")
    print(f"  Total Memory Units Retained:    {total_retained}")
    print(f"  Successful Fixes Retained:      {successful_fixes_retained}")
    print(f"  Failed-Fix Warnings Retained:   {failed_fixes_retained} (Critical Safety Guards)")
    print("-" * 80)

    # 4. Demonstrate Incident Time Machine Recall Queries
    print("\n[Step 3/3] Executing Verification Recall Queries on Hindsight Memory...")

    test_queries = [
        {
            "category": "1. Database Pool Saturation & Timeouts",
            "service": "database",
            "query": "504 gateway timeout active connections exhausted max_connections",
            "candidate_action": "RESTART_DATABASE",
        },
        {
            "category": "2. Payment Outbound Third-Party Degradation",
            "service": "payment-api",
            "query": "stripe webhook latency worker thread pool exhaustion 9400ms",
            "candidate_action": "SCALE_POD_REPLICAS",
        },
        {
            "category": "3. Redis Cache Thrashing & Database Stampede",
            "service": "user-service",
            "query": "redis maxmemory eviction surge cache miss db lockup",
            "candidate_action": "FLUSH_ALL_REDIS",
        },
        {
            "category": "4. Kafka Consumer Group Poison Pill",
            "service": "order-service",
            "query": "consumer group lag crashloopbackoff malformed message deserialize error",
            "candidate_action": "RESTART_SERVICE",
        },
        {
            "category": "5. Ingress TLS Certificate Expiration",
            "service": "api-gateway",
            "query": "SSL_ERROR_EXPIRED_CERT_DATE traffic drop TLS handshake failed",
            "candidate_action": "ROTATE_TLS_CERTIFICATE_SECRET",
        },
    ]

    for q in test_queries:
        print("\n" + "=" * 60)
        print(f"Test Query: {q['category']}")
        print(f"Target Service:     {q['service']}")
        print(f"Query Text:         '{q['query']}'")
        print(f"Candidate Fix:      '{q['candidate_action']}'")
        print("-" * 60)

        # Recall Similar Incidents
        similar_incidents = hindsight_service.recall_similar_incidents(
            query=q["query"],
            service=q["service"],
            limit=2,
        )
        if not similar_incidents:
            similar_incidents = local_recall_incidents(q["query"], service=q["service"], limit=2)
            print("  [Local offline fallback active] Relevant historical incidents retrieved from dataset.")
        print(f"Recalled Similar Incidents: {len(similar_incidents)} match(es)")
        for idx, inc in enumerate(similar_incidents, start=1):
            print(f"  [Incident #{idx}] ID: {inc.get('id')} | Score: {inc.get('score')}")
            print(f"  Tags: {inc.get('tags')}")
            print(f"  Content:\n    {inc.get('text', '')[:160]}...\n")

        # Recall Failed Fix Warnings (Incident Time Machine Safety Guard)
        failed_warnings = hindsight_service.recall_failed_remediations(
            service=q["service"],
            action_type=q["candidate_action"],
        )
        if not failed_warnings:
            failed_warnings = local_failed_remediation_recall(
                service=q["service"],
                action_type=q["candidate_action"],
                limit=2,
            )
            print("  [Local offline fallback active] Failed-fix warnings retrieved from incident history.")
        print(f"Incident Time Machine Failed-Fix Warnings: {len(failed_warnings)} warning(s)")
        if failed_warnings:
            for idx, warn in enumerate(failed_warnings, start=1):
                print(f"  [⚠️ FAILED_BEFORE WARNING #{idx}]")
                print(f"  Tags: {warn.get('tags')}")
                print(f"  Warning Reason:\n    {warn.get('text', '')[:220]}...\n")
        else:
            print("  (No dangerous failed-fix records detected for this specific candidate action)")

    print("\n" + "=" * 80)
    print("Hindsight Seeding & Multi-Query Verification Completed.")
    print("=" * 80)
    hindsight_service.close()


if __name__ == "__main__":
    seed_hindsight_memory_bank()
