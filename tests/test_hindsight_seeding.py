"""Tests for historical incident dataset and Hindsight seeding pipeline.

Verifies:
1. Dataset contains >= 20 realistic incidents across all 6 core services.
2. Every incident contains all required fields:
   - incident ID, timestamp, service, symptoms, alerts, metrics,
   - deployment context, root cause, actions attempted, successful actions,
   - failed actions, resolution time, final outcome, engineer feedback, lessons learned.
3. Dataset contains both successful and failed remediation attempts.
4. Seeding pipeline correctly formats and retains incidents into Hindsight.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock

from backend.app.memory.hindsight_service import HindsightService
from scripts.seed_hindsight import load_historical_incidents, local_recall_incidents


def test_local_recall_matches_expected_incidents():
    """Verifies that local recall can surface matching historical incidents from the dataset without a live Hindsight API."""
    incidents = load_historical_incidents()
    results = local_recall_incidents("stripe webhook latency worker thread pool exhaustion", service="payment-api", limit=3)

    assert len(results) >= 1
    assert any(item["service"] == "payment-api" for item in results)
    assert any(item["incident_id"] == "INC-H102" for item in results)

    db_results = local_recall_incidents("active connections exhausted max_connections gateway timeout", service="database", limit=3)
    assert len(db_results) >= 1
    assert any(item["incident_id"] == "INC-H101" for item in db_results)


def test_historical_dataset_schema_and_diversity():
    """Verifies that the historical dataset contains at least 20 diverse incidents with all fields."""
    incidents = load_historical_incidents()
    assert len(incidents) >= 20, f"Expected >= 20 incidents, got {len(incidents)}"

    required_fields = [
        "incident_id",
        "timestamp",
        "service",
        "title",
        "severity",
        "status",
        "symptoms",
        "alerts",
        "relevant_metrics",
        "deployment_context",
        "root_cause",
        "actions_attempted",
        "successful_actions",
        "failed_actions",
        "resolution_time_minutes",
        "final_outcome",
        "engineer_feedback",
        "lessons_learned",
    ]

    expected_services = {
        "payment-api",
        "order-service",
        "user-service",
        "notification-service",
        "database",
        "api-gateway",
    }

    found_services = set()
    total_successful_actions = 0
    total_failed_actions = 0

    for inc in incidents:
        for field in required_fields:
            assert field in inc, f"Missing required field '{field}' in incident {inc.get('incident_id')}"

        assert isinstance(inc["symptoms"], list) and len(inc["symptoms"]) > 0
        assert isinstance(inc["alerts"], list) and len(inc["alerts"]) > 0
        assert isinstance(inc["relevant_metrics"], dict) and len(inc["relevant_metrics"]) > 0
        assert isinstance(inc["deployment_context"], dict)
        assert isinstance(inc["actions_attempted"], list) and len(inc["actions_attempted"]) > 0
        assert isinstance(inc["lessons_learned"], list) and len(inc["lessons_learned"]) > 0
        assert isinstance(inc["engineer_feedback"], dict)

        found_services.add(inc["service"])
        total_successful_actions += len(inc["successful_actions"])
        total_failed_actions += len(inc["failed_actions"])

    # Verify service coverage
    for expected_svc in expected_services:
        assert expected_svc in found_services, f"Expected service '{expected_svc}' not found in dataset"

    # Verify both successful and failed remediation attempts are represented
    assert total_successful_actions >= 20, f"Expected >= 20 successful actions, got {total_successful_actions}"
    assert total_failed_actions >= 15, f"Expected >= 15 failed actions for safety guards, got {total_failed_actions}"


def test_seeding_retains_all_memory_units():
    """Verifies that seeding retains incident context, root causes, fixes, feedback, and postmortems."""
    incidents = load_historical_incidents()
    mock_client = MagicMock()
    
    retain_resp = MagicMock()
    retain_resp.success = True
    retain_resp.bank_id = "test-bank"
    retain_resp.items_count = 1
    mock_client.retain.return_value = retain_resp

    service = HindsightService(bank_id="test-bank")
    service._client = mock_client

    retained_count = 0
    for inc in incidents:
        service.retain_incident(inc)
        retained_count += 1

        if inc.get("root_cause"):
            service.retain_root_cause(inc["incident_id"], inc["service"], inc["root_cause"])
            retained_count += 1

        for action in inc.get("actions_attempted", []):
            if action.get("outcome") == "successful":
                service.retain_successful_fix(
                    incident_id=inc["incident_id"],
                    service=inc["service"],
                    action_type=action["action_type"],
                    parameters=action.get("parameters", {}),
                    rationale="Test rationale",
                    outcome_notes="Test outcome",
                )
                retained_count += 1
            elif action.get("outcome") == "failed":
                service.retain_failed_fix(
                    incident_id=inc["incident_id"],
                    service=inc["service"],
                    action_type=action["action_type"],
                    parameters=action.get("parameters", {}),
                    failure_reason=action.get("reason", "failed"),
                )
                retained_count += 1

        fb = inc.get("engineer_feedback", {})
        if fb:
            service.retain_engineer_feedback(
                incident_id=inc["incident_id"],
                service=inc["service"],
                engineer_id=fb.get("engineer", "eng"),
                rating=fb.get("rating", "5_stars"),
                feedback_text=fb.get("comment", ""),
            )
            retained_count += 1

        if inc.get("lessons_learned"):
            service.retain_postmortem(
                incident_id=inc["incident_id"],
                service=inc["service"],
                executive_summary=inc.get("final_outcome", ""),
                root_cause_analysis=inc.get("root_cause", ""),
                lessons_learned=inc.get("lessons_learned", []),
                preventive_actions=["Action 1"],
            )
            retained_count += 1

    assert mock_client.retain.call_count == retained_count
    assert retained_count >= 120, f"Expected >= 120 memory units, got {retained_count}"
