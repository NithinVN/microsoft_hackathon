"""Tests for Hindsight Organizational Memory Service.

Verifies:
1. create_memory_bank()
2. retain_incident()
3. retain_root_cause()
4. retain_successful_fix()
5. retain_failed_fix()
6. retain_engineer_feedback()
7. retain_postmortem()
8. recall_similar_incidents()
9. recall_failed_remediations()
10. recall_successful_remediations()
11. reflect_on_incident_history()
12. Graceful error handling and health checks
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from backend.app.memory.hindsight_service import HindsightService


@pytest.fixture
def mock_hindsight_client():
    """Returns a mock official Hindsight client."""
    client = MagicMock()
    
    # Mock get_version
    version_obj = MagicMock()
    version_obj.version = "0.10.1"
    client.get_version.return_value = version_obj
    
    # Mock get_bank_config
    client.get_bank_config.return_value = {"bank_id": "test-bank", "name": "Test Bank"}
    
    # Mock create_bank
    create_resp = MagicMock()
    create_resp.to_dict.return_value = {"bank_id": "test-bank", "created": True}
    client.create_bank.return_value = create_resp
    
    # Mock retain
    retain_resp = MagicMock()
    retain_resp.success = True
    retain_resp.bank_id = "test-bank"
    retain_resp.items_count = 1
    retain_resp.operation_id = "op-12345"
    client.retain.return_value = retain_resp
    
    # Mock recall
    recall_item = MagicMock()
    recall_item.id = "mem-1"
    recall_item.text = "Sample incident content regarding payment pool starvation."
    recall_item.type = "memory"
    recall_item.tags = ["incident", "service:payment-api", "warning:failed_fix"]
    recall_item.metadata = {"incident_id": "INC-101", "service": "payment-api"}
    recall_item.context = "Production triage"
    score_obj = MagicMock()
    score_obj.combined_score = 0.94
    recall_item.scores = score_obj
    
    recall_resp = MagicMock()
    recall_resp.results = [recall_item]
    client.recall.return_value = recall_resp
    
    # Mock reflect
    reflect_resp = MagicMock()
    reflect_resp.text = "Payment API connection starvation is typically caused by unclosed DB sessions. Do NOT hard restart."
    fact_mock = MagicMock()
    fact_mock.to_dict.return_value = {"fact": "Restarting DB caused cascading TCP storm."}
    reflect_resp.based_on = [fact_mock]
    reflect_resp.usage = {"tokens": 120}
    client.reflect.return_value = reflect_resp
    
    return client


@pytest.fixture
def hindsight_svc(mock_hindsight_client):
    """Creates a HindsightService with a mocked client."""
    service = HindsightService(
        base_url="https://api.hindsight.cloud",
        api_key="mock_key",
        bank_id="test-bank",
    )
    service._client = mock_hindsight_client
    return service


def test_hindsight_health_check_healthy(hindsight_svc, mock_hindsight_client):
    """Verifies Hindsight health check when connection is established."""
    health = hindsight_svc.check_health()
    assert health["healthy"] is True
    assert health["status"] == "connected"
    assert health["version"] == "0.10.1"
    assert health["bank_id"] == "test-bank"
    mock_hindsight_client.get_version.assert_called_once()


def test_hindsight_health_check_unreachable():
    """Verifies graceful handling during health check when Hindsight server is unreachable."""
    service = HindsightService(base_url="http://invalid-unreachable-url.test", api_key="test")
    client_mock = MagicMock()
    client_mock.get_version.side_effect = ConnectionError("Connection refused")
    service._client = client_mock
    
    health = service.check_health()
    assert health["healthy"] is False
    assert health["status"] == "unreachable"
    assert "Connection refused" in health["error"]


def test_create_memory_bank(hindsight_svc, mock_hindsight_client):
    """Verifies memory bank creation via Hindsight API."""
    res = hindsight_svc.create_memory_bank()
    assert res["success"] is True
    assert res["bank_id"] == "test-bank"
    mock_hindsight_client.create_bank.assert_called_once()


def test_retain_incident(hindsight_svc, mock_hindsight_client):
    """Verifies retaining incident record into Hindsight."""
    incident_data = {
        "incident_id": "INC-400",
        "title": "Redis Cache Eviction Surge",
        "affected_service": "cart-service",
        "severity": "high",
        "status": "resolved",
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "description": "Cart items dropped due to memory max reached.",
        "symptoms": ["Cache eviction rate +400%"],
        "root_cause": "TTL not set on user session keys.",
        "resolution": "Set 24h TTL policy and evicted stale keys.",
    }
    
    res = hindsight_svc.retain_incident(incident_data)
    assert res["success"] is True
    assert res["bank_id"] == "test-bank"
    mock_hindsight_client.retain.assert_called_once()
    
    call_kwargs = mock_hindsight_client.retain.call_args[1]
    assert call_kwargs["bank_id"] == "test-bank"
    assert "incident:INC-400" in call_kwargs["tags"]
    assert "service:cart-service" in call_kwargs["tags"]
    assert call_kwargs["metadata"]["incident_id"] == "INC-400"


def test_retain_root_cause(hindsight_svc, mock_hindsight_client):
    """Verifies retaining root cause analysis."""
    res = hindsight_svc.retain_root_cause(
        incident_id="INC-400",
        service="cart-service",
        root_cause="Missing TTL on Redis session hashes.",
        evidence={"keys_scanned": 1500000},
    )
    assert res["success"] is True
    call_kwargs = mock_hindsight_client.retain.call_args[1]
    assert "root_cause" in call_kwargs["tags"]
    assert call_kwargs["metadata"]["type"] == "root_cause"


def test_retain_successful_fix(hindsight_svc, mock_hindsight_client):
    """Verifies retaining successful remediation fix."""
    res = hindsight_svc.retain_successful_fix(
        incident_id="INC-400",
        service="cart-service",
        action_type="SET_REDIS_TTL",
        parameters={"ttl_seconds": 86400},
        rationale="Applies 24h expiration on session keys",
        outcome_notes="Memory usage stabilized at 45%",
    )
    assert res["success"] is True
    call_kwargs = mock_hindsight_client.retain.call_args[1]
    assert "outcome:successful" in call_kwargs["tags"]
    assert call_kwargs["metadata"]["outcome"] == "successful"


def test_retain_failed_fix(hindsight_svc, mock_hindsight_client):
    """Verifies retaining failed remediation fix with safety warning tags."""
    res = hindsight_svc.retain_failed_fix(
        incident_id="INC-400",
        service="cart-service",
        action_type="FLUSH_ALL_REDIS",
        parameters={"async": False},
        failure_reason="Flushed active customer carts causing checkout failure for 12,000 active sessions.",
        unintended_consequences="Immediate 100% loss of checkout funnel for 15 minutes.",
    )
    assert res["success"] is True
    call_kwargs = mock_hindsight_client.retain.call_args[1]
    assert "warning:failed_fix" in call_kwargs["tags"]
    assert "outcome:failed" in call_kwargs["tags"]
    assert call_kwargs["metadata"]["type"] == "failed_fix"


def test_retain_engineer_feedback(hindsight_svc, mock_hindsight_client):
    """Verifies retaining engineer feedback in memory."""
    res = hindsight_svc.retain_engineer_feedback(
        incident_id="INC-400",
        service="cart-service",
        engineer_id="eng_sarah",
        rating="5_stars",
        feedback_text="Agent correctly identified TTL omission within 2 minutes.",
    )
    assert res["success"] is True
    call_kwargs = mock_hindsight_client.retain.call_args[1]
    assert "feedback" in call_kwargs["tags"]
    assert call_kwargs["metadata"]["engineer_id"] == "eng_sarah"


def test_retain_postmortem(hindsight_svc, mock_hindsight_client):
    """Verifies retaining postmortem report and preventive action items."""
    res = hindsight_svc.retain_postmortem(
        incident_id="INC-400",
        service="cart-service",
        executive_summary="Redis cache overflow resulted in degraded cart service for 18 minutes.",
        root_cause_analysis="Session keys were created without TTL expiration.",
        lessons_learned=["Always enforce max TTL on cache keys in config templates."],
        preventive_actions=["Add CI linter check for redis.set without ex parameter."],
    )
    assert res["success"] is True
    call_kwargs = mock_hindsight_client.retain.call_args[1]
    assert "postmortem" in call_kwargs["tags"]
    assert "lessons_learned" in call_kwargs["tags"]


def test_recall_similar_incidents(hindsight_svc, mock_hindsight_client):
    """Verifies recalling historical incidents by semantic query."""
    results = hindsight_svc.recall_similar_incidents(
        query="Redis memory exhaustion and evicted keys",
        service="cart-service",
        limit=5,
    )
    assert len(results) == 1
    assert results[0]["id"] == "mem-1"
    assert results[0]["score"] == 0.94
    mock_hindsight_client.recall.assert_called_once()


def test_recall_failed_remediations(hindsight_svc, mock_hindsight_client):
    """Verifies recalling failed fixes to warn before remediation execution."""
    results = hindsight_svc.recall_failed_remediations(
        service="cart-service",
        action_type="FLUSH_ALL_REDIS",
    )
    assert len(results) == 1
    assert "warning:failed_fix" in results[0]["tags"]


def test_recall_successful_remediations(hindsight_svc, mock_hindsight_client):
    """Verifies recalling verified past successful fixes."""
    results = hindsight_svc.recall_successful_remediations(
        service="cart-service",
        action_type="SET_REDIS_TTL",
    )
    assert len(results) == 1


def test_recall_organizational_memories_returns_source_records(hindsight_svc):
    result = hindsight_svc.recall_organizational_memories(
        query="connection pool saturation",
        service="payment-api",
        limit=3,
    )

    assert result["status"] == "available"
    assert result["bank_id"] == "test-bank"
    assert result["retrieved_memories"][0]["id"] == "mem-1"
    assert result["retrieved_memories"][0]["source"] == "Hindsight"
    assert result["agent_evidence"]
    assert set(result["categories"]) == {
        "historical_incidents",
        "root_causes",
        "successful_fixes",
        "failed_fixes",
        "engineer_feedback",
        "postmortem_lessons",
    }


def test_recall_organizational_memories_does_not_fallback_when_unavailable(hindsight_svc, monkeypatch):
    monkeypatch.setattr(hindsight_svc, "check_health", lambda: {"healthy": False, "status": "unreachable"})

    result = hindsight_svc.recall_organizational_memories(
        query="connection pool saturation",
        service="payment-api",
    )

    assert result["status"] == "unavailable"
    assert result["retrieved_memories"] == []
    assert all(not records for records in result["categories"].values())


def test_reflect_on_incident_history(hindsight_svc, mock_hindsight_client):
    """Verifies synthesized cognitive reflection across incident history."""
    reflection = hindsight_svc.reflect_on_incident_history(
        query="What remediations should be avoided for cart-service?",
        service="cart-service",
    )
    assert reflection["success"] is True
    assert "Do NOT hard restart" in reflection["text"]
    assert len(reflection["based_on"]) == 1
    mock_hindsight_client.reflect.assert_called_once()


def test_graceful_degradation_on_api_exception():
    """Verifies that API errors do not crash callers and return graceful fallback responses."""
    service = HindsightService(base_url="https://api.hindsight.cloud", api_key="dummy")
    client_mock = MagicMock()
    client_mock.retain.side_effect = Exception("HTTP 503 Service Unavailable")
    client_mock.recall.side_effect = Exception("HTTP 500 Internal Error")
    client_mock.reflect.side_effect = Exception("HTTP 408 Request Timeout")
    service._client = client_mock
    
    # Test retain error resilience
    retain_res = service.retain_incident({"incident_id": "INC-ERR", "affected_service": "auth"})
    assert retain_res["success"] is False
    assert "503" in retain_res["error"]
    
    # Test recall error resilience (returns empty list, doesn't crash)
    recall_res = service.recall_similar_incidents("auth error")
    assert recall_res == []
    
    # Test reflect error resilience
    reflect_res = service.reflect_on_incident_history("auth failure patterns")
    assert reflect_res["success"] is False
    assert "failed" in reflect_res["text"].lower()
