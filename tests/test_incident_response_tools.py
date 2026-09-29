import json

import pytest

from backend.app.tools import (
    execute_tool,
    get_incident_details,
    get_service_metrics,
    get_service_logs,
    get_recent_deployments,
    get_service_dependencies,
    get_recent_incident_events,
    recall_similar_incidents,
    recall_failed_fixes,
    recall_successful_fixes,
    get_runbook,
    propose_remediation,
    simulate_remediation,
    record_engineer_feedback,
    list_tool_specs,
)


@pytest.mark.parametrize(
    "tool_name, payload, expected_key",
    [
        ("get_incident_details", {"incident_id": "INC-H102"}, "incident"),
        ("get_service_metrics", {"service": "payment-api", "limit": 2}, "metric_history"),
        ("get_service_logs", {"service": "database", "limit": 2}, "logs"),
        ("get_recent_deployments", {"service": "api-gateway", "limit": 2}, "deployments"),
        ("get_service_dependencies", {"service": "order-service"}, "dependencies"),
        ("get_recent_incident_events", {"service": "user-service", "limit": 3}, "events"),
        ("recall_similar_incidents", {"query": "thread starvation payment api", "service": "payment-api", "limit": 3}, "matches"),
        ("recall_failed_fixes", {"service": "database", "action_type": "RESTART_DATABASE", "limit": 2}, "matches"),
        ("recall_successful_fixes", {"service": "database", "action_type": "SCALE_CONNECTION_POOL", "limit": 2}, "matches"),
        ("get_runbook", {"service": "payment-api", "scenario": "thread-starvation"}, "runbook"),
        ("propose_remediation", {"service": "payment-api", "symptom_summary": "Payment API thread starvation and latency spike", "max_options": 2}, "recommendations"),
        ("simulate_remediation", {"service": "payment-api", "action_type": "ENABLE_CIRCUIT_BREAKER", "dry_run": True}, "predicted_outcome"),
        ("record_engineer_feedback", {"incident_id": "INC-H102", "engineer_id": "eng_amy", "rating": 5, "comments": "Circuit breaker worked well and should remain a standard response."}, "record"),
    ],
)
def test_tool_registry_and_execution(tool_name, payload, expected_key):
    result = execute_tool(tool_name, payload)
    assert result["ok"] is True, result
    assert expected_key in result["data"], result


def test_list_tool_specs_returns_all_known_tools():
    specs = list_tool_specs()
    assert len(specs) == 13
    assert {spec["name"] for spec in specs} == {
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
    }


def test_invalid_tool_and_invalid_input_fail_safely():
    bad_tool = execute_tool("does_not_exist", {})
    assert bad_tool["ok"] is False
    assert bad_tool["error"]["code"] == "unknown_tool"

    bad_input = execute_tool("get_incident_details", {"incident_id": "DROP TABLE users;--"})
    assert bad_input["ok"] is False
    assert bad_input["error"]["code"] == "validation_error"

    extra_argument = execute_tool(
        "get_service_metrics",
        {"service": "payment-api", "unexpected": "must not be ignored"},
    )
    assert extra_argument["ok"] is False
    assert extra_argument["error"]["code"] == "validation_error"
    assert "must not be ignored" not in json.dumps(extra_argument)


def test_recall_helpers_are_deterministic_for_service_specific_queries():
    payment_matches = recall_similar_incidents({"query": "thread starvation payment api", "service": "payment-api", "limit": 3})
    assert payment_matches["ok"] is True
    assert payment_matches["data"]["matches"]
    assert payment_matches["data"]["matches"][0]["incident_id"] == "INC-H102"

    db_matches = recall_failed_fixes({"service": "database", "action_type": "RESTART_DATABASE", "limit": 3})
    assert db_matches["ok"] is True
    assert any(match["incident_id"] == "INC-H101" for match in db_matches["data"]["matches"])

    bench_matches = recall_successful_fixes({"service": "database", "action_type": "SCALE_CONNECTION_POOL", "limit": 3})
    assert bench_matches["ok"] is True
    assert any(match["incident_id"] == "INC-H101" for match in bench_matches["data"]["matches"])


def test_helper_functions_return_valid_json_like_structures():
    incident = get_incident_details({"incident_id": "INC-H101"})
    assert incident["ok"] is True
    assert isinstance(incident["data"]["incident"], dict)

    metrics = get_service_metrics({"service": "database", "limit": 2})
    assert metrics["ok"] is True
    assert isinstance(metrics["data"]["metric_history"], list)

    runbook = get_runbook({"service": "order-service"})
    assert runbook["ok"] is True
    assert "allowed_actions" in runbook["data"]


def test_simulation_requires_dry_run_mode():
    live_run = simulate_remediation({"service": "order-service", "action_type": "ROUTE_DEAD_LETTER_QUEUE", "dry_run": False})
    assert live_run["ok"] is False
    assert live_run["error"]["code"] == "unsafe_mode"
