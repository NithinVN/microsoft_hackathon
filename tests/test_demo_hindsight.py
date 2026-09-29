from unittest.mock import patch


def test_demo_retention_uses_local_demo_memory_when_hindsight_is_unconfigured(client):
    with patch("backend.app.api.v1.endpoints.incidents.hindsight_service.is_configured", False):
        response = client.post("/api/v1/incidents/demo/retain")
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "unavailable"
    assert result["retained"] is False
    assert "memory fixture" in result["message"]


def test_demo_retention_writes_incident_fix_and_postmortem_to_hindsight(client):
    success = {"success": True, "bank_id": "incidentmind-memory"}
    with patch("backend.app.api.v1.endpoints.incidents.hindsight_service.is_configured", True), \
         patch("backend.app.api.v1.endpoints.incidents.hindsight_service.retain_incident", return_value=success) as retain_incident, \
         patch("backend.app.api.v1.endpoints.incidents.hindsight_service.retain_successful_fix", return_value=success) as retain_fix, \
         patch("backend.app.api.v1.endpoints.incidents.hindsight_service.retain_postmortem", return_value=success) as retain_postmortem:
        response = client.post("/api/v1/incidents/demo/retain")
    assert response.status_code == 200
    assert response.json()["retained"] is True
    assert retain_incident.call_args.args[0]["incident_id"] == "INC-DEMO-001"
    assert retain_fix.call_args.kwargs["action_type"] == "CORRECT_DATABASE_CONNECTION_POOL"
    assert "lessons_learned" in retain_postmortem.call_args.kwargs
