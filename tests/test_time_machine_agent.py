from fastapi.testclient import TestClient

from backend.app.agents.time_machine_agent import build_time_machine_analysis
from backend.app.main import app


def test_build_time_machine_analysis_returns_historical_precedents_for_candidate_actions():
    result = build_time_machine_analysis("INC-H102")

    assert result
    assert any(item["action"] == "ENABLE_CIRCUIT_BREAKER" for item in result)
    breaker = next(item for item in result if item["action"] == "ENABLE_CIRCUIT_BREAKER")
    assert breaker["historical_attempts"] >= 1
    assert breaker["historical_cases"]
    assert any("Historical evidence shows" in lesson for lesson in breaker["lessons"])
    assert breaker["caveats"]


def test_incident_time_machine_endpoint_returns_structured_json():
    with TestClient(app) as client:
        response = client.get("/api/v1/incidents/INC-H102/time-machine")

    assert response.status_code == 200
    payload = response.json()
    assert payload["incident_id"] == "INC-H102"
    assert payload["service"] == "payment-api"
    assert "historical_action_comparison" in payload
    assert payload["historical_action_comparison"]
    assert any(item["action"] == "ENABLE_CIRCUIT_BREAKER" for item in payload["historical_action_comparison"])
    assert "failed_fix_warning" in payload
