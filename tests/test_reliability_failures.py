from unittest.mock import patch
import time

import pytest

from backend.app.api.v1.endpoints.health import readiness
from backend.app.orchestration.incident_orchestrator import IncidentOrchestrator
from backend.app.tools import execute_tool


@pytest.mark.asyncio
async def test_postgres_unavailable_reports_degraded_retryable_readiness():
    with patch("backend.app.api.v1.endpoints.health.check_db_health", return_value=False):
        result = await readiness()
    assert result["status"] == "degraded"
    assert result["retryable"] is True
    assert result["services"]["postgresql"] == "unavailable"


@pytest.mark.asyncio
async def test_groq_unconfigured_is_reported_as_fallback_without_breaking_api():
    from backend.app.api.v1.endpoints.health import get_health
    from backend.app.core.config import settings

    with patch.object(settings, "GROQ_API_KEY", ""):
        result = await get_health()
    assert result.status == "healthy"
    assert result.services["groq_configured"] is False


def test_invalid_tool_arguments_return_safe_error_with_diagnostic(caplog):
    result = execute_tool("get_service_metrics", {"service": "; DROP TABLE incidents"})
    assert result["ok"] is False
    assert result["error"]["code"] == "validation_error"
    assert any(getattr(record, "error_code", None) == "validation_error" for record in caplog.records)


def test_failed_tool_call_returns_safe_error_and_logs(caplog):
    from backend.app.tools.incident_response_tools import TOOL_REGISTRY

    spec = TOOL_REGISTRY["get_service_metrics"]
    with patch.object(spec, "function", side_effect=RuntimeError("upstream failed")):
        result = execute_tool("get_service_metrics", {"service": "payment-api"})
    assert result["ok"] is False
    assert result["error"]["code"] == "tool_execution_error"
    assert any("Unexpected tool invocation" in record.message for record in caplog.records)


def test_function_call_exception_is_contained():
    from backend.app.tools.incident_response_tools import TOOL_REGISTRY, IncidentToolError

    spec = TOOL_REGISTRY["get_service_metrics"]
    with patch.object(spec, "function", side_effect=IncidentToolError("function invocation failed")):
        result = execute_tool("get_service_metrics", {"service": "payment-api"})
    assert result["ok"] is False
    assert result["error"]["code"] == "tool_execution_error"


def test_malformed_agent_output_preserves_incident_and_marks_retryable():
    with patch("backend.app.orchestration.incident_orchestrator.diagnose_incident", return_value={"unexpected": "payload"}):
        state = IncidentOrchestrator().run("INC-H101")
    assert state.status == "failed"
    assert state.incident is not None
    assert state.current_step == "END"
    assert any("invalid agent output" in item.lower() for item in state.errors)


def test_remediation_simulation_failure_blocks_without_claiming_recovery():
    failed = {"ok": False, "error": {"code": "simulation_failed"}}
    with patch("backend.app.tools.simulate_remediation", return_value=failed):
        state = IncidentOrchestrator().run("INC-H101", approval_override={"approved": True})
    assert state.status == "blocked"
    assert state.incident is not None
    assert state.execution["status"] == "failed"
    assert state.verification is None
    assert state.retryable is True


def test_rejected_remediation_keeps_incident_and_never_executes():
    state = IncidentOrchestrator().run("INC-H101", approval_override={"approved": False, "reason": "unsafe"})
    assert state.status == "blocked"
    assert state.incident is not None
    assert state.execution is None
    assert state.current_step == "HUMAN_APPROVAL"


def test_analysis_retry_endpoint_reuses_incident_and_stops_at_approval(client):
    response = client.post("/api/v1/incidents/INC-H101/orchestrate")
    assert response.status_code == 200
    state = response.json()
    assert state["incident_id"] == "INC-H101"
    assert state["status"] == "blocked"
    assert state["current_step"] == "HUMAN_APPROVAL"
    assert state["execution"] is None


def test_hindsight_retain_failure_is_reported_without_losing_postmortem():
    with patch("backend.app.orchestration.incident_orchestrator.hindsight_service.is_configured", True), \
         patch("backend.app.orchestration.incident_orchestrator.hindsight_service.retain_incident", return_value={"success": False}), \
         patch("backend.app.orchestration.incident_orchestrator.hindsight_service.retain_root_cause", return_value={"success": False}), \
         patch("backend.app.orchestration.incident_orchestrator.hindsight_service.retain_successful_fix", return_value={"success": False}), \
         patch("backend.app.orchestration.incident_orchestrator.hindsight_service.retain_postmortem", return_value={"success": False}), \
         patch("backend.app.orchestration.incident_orchestrator.hindsight_service.retain_engineer_feedback", return_value={"success": False}):
        state = IncidentOrchestrator().run("INC-H101", approval_override={"approved": True})
    assert state.status == "completed_with_warnings"
    assert state.hindsight_status == "unavailable"
    assert state.postmortem is not None
    assert any("retention failed" in warning.lower() for warning in state.warnings)


def test_azure_webhook_timeout_keeps_created_incident_and_allows_retry(client, monkeypatch):
    from pathlib import Path
    import json
    from backend.app.core.config import settings
    from backend.app.orchestration.incident_orchestrator import IncidentOrchestrator

    payload_path = Path(__file__).parent / "fixtures" / "azure_monitor_metric_firing.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))

    def slow_run(self, incident_id, approval_override=None):
        time.sleep(0.1)
        raise RuntimeError("late orchestrator failure")

    monkeypatch.setattr(settings, "WEBHOOK_ORCHESTRATION_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(IncidentOrchestrator, "run", slow_run)
    response = client.post("/api/v1/webhooks/azure-monitor?orchestrate=true", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["orchestrator_status"] == "timed_out_retryable"
    assert result["orchestrator_retryable"] is True
    assert client.get(f"/api/v1/incidents/{result['incident_id']}").status_code == 200
