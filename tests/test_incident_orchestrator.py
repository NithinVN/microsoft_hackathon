from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from backend.app.orchestration.incident_orchestrator import IncidentOrchestrator, OrchestratorState


@pytest.fixture
def orchestrator() -> IncidentOrchestrator:
    return IncidentOrchestrator()


def test_incident_orchestrator_successful_workflow(orchestrator: IncidentOrchestrator):
    state = orchestrator.run("INC-H101")

    assert isinstance(state, OrchestratorState)
    assert state.current_step == "END"
    assert state.status in {"completed", "completed_with_warnings"}
    assert state.incident is not None
    assert state.investigation is not None
    assert state.blast_radius is not None
    assert state.memory is not None
    assert state.diagnosis is not None
    assert state.what_if is not None
    assert state.remediation_plan is not None
    assert state.execution is not None
    assert state.verification is not None
    assert state.postmortem is not None
    assert state.transition_log
    assert any(entry["step"] == "START" for entry in state.transition_log)
    assert any(entry["step"] == "END" for entry in state.transition_log)
    assert state.timeline


def test_incident_orchestrator_handles_hindsight_unavailable(orchestrator: IncidentOrchestrator):
    with patch("backend.app.orchestration.incident_orchestrator.hindsight_service.is_configured", False):
        state = orchestrator.run("INC-H101")

    assert state.status in {"completed", "completed_with_warnings"}
    assert state.hindsight_status == "unavailable"
    assert any("Hindsight unavailable" in item for item in state.errors)


def test_incident_orchestrator_rejected_remediation_is_blocked(orchestrator: IncidentOrchestrator):
    state = orchestrator.run("INC-H101", approval_override={"approved": False, "reason": "reject for safety"})

    assert state.status == "blocked"
    assert state.current_step == "HUMAN_APPROVAL"
    assert any("rejected remediation" in item.lower() for item in state.errors)


def test_incident_orchestrator_handles_invalid_agent_output(orchestrator: IncidentOrchestrator):
    with patch("backend.app.orchestration.incident_orchestrator.investigate_incident", return_value={"bad": "shape"}):
        state = orchestrator.run("INC-H101")

    assert state.status == "failed"
    assert any("invalid agent output" in item.lower() for item in state.errors)
