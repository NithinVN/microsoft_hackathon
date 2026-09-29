from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.config import settings
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.tools.incident_response_tools import clear_runtime_incidents

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def client():
    clear_runtime_incidents()
    engine = create_async_engine(TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def init_tables():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(init_tables())

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())
    clear_runtime_incidents()


def load_payload(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_firing_common_alert_creates_normalized_incident(client: TestClient):
    payload = load_payload("azure_monitor_metric_firing.json")
    response = client.post("/api/v1/webhooks/azure-monitor", json=payload)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "accepted"
    assert result["action"] == "created"
    assert result["created"] == 1
    assert result["service"] == "payment-api"
    assert result["severity"] == "SEV-1"
    incident_id = result["incident_id"]
    assert incident_id.startswith("INC-AZ-")

    # Verify incident in storage via REST API
    incident_res = client.get(f"/api/v1/incidents/{incident_id}")
    assert incident_res.status_code == 200
    incident = incident_res.json()
    assert incident["source"] == "azure-monitor"
    assert incident["severity"] == "SEV-1"
    assert incident["status"] == "DETECTED"
    assert incident["affected_service"] == "payment-api"
    assert incident["detected_at"].startswith("2026-09-29T10:15:00")
    assert any("CPU percentage" in s for s in incident["symptoms"])
    assert incident["metadata"]["schema_id"] == "azureMonitorCommonAlertSchema"

    # Verify pipeline handoff event with actor=IncidentOrchestrator
    event_types = [event["event_type"] for event in incident["events"]]
    actors = [event["actor"] for event in incident["events"]]
    assert "PIPELINE_INITIALIZED" in event_types
    assert "IncidentOrchestrator" in actors


def test_repeated_firing_alert_is_idempotent(client: TestClient):
    payload = load_payload("azure_monitor_metric_firing.json")
    first = client.post("/api/v1/webhooks/azure-monitor", json=payload)
    second = client.post("/api/v1/webhooks/azure-monitor", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["action"] == "created"
    assert second.json()["action"] == "already_firing"
    assert second.json()["created"] == 0
    assert second.json()["ignored"] == 1

    incidents = client.get("/api/v1/incidents", params={"status": "DETECTED"}).json()
    azure_incidents = [inc for inc in incidents if inc["source"] == "azure-monitor"]
    assert len(azure_incidents) == 1


def test_resolved_alert_closes_existing_incident(client: TestClient):
    firing_payload = load_payload("azure_monitor_metric_firing.json")
    resolved_payload = load_payload("azure_monitor_metric_resolved.json")

    firing = client.post("/api/v1/webhooks/azure-monitor", json=firing_payload)
    assert firing.status_code == 200
    incident_id = firing.json()["incident_id"]

    resolved = client.post("/api/v1/webhooks/azure-monitor", json=resolved_payload)
    assert resolved.status_code == 200
    res_body = resolved.json()
    assert res_body["action"] == "resolved"
    assert res_body["resolved"] == 1

    incident_res = client.get(f"/api/v1/incidents/{incident_id}")
    incident = incident_res.json()
    assert incident["status"] == "RESOLVED"
    assert incident["resolved_at"].startswith("2026-09-29T10:28:45")
    assert "ALERT_RESOLVED" in [e["event_type"] for e in incident["events"]]
    assert "AzureMonitor" in [e["actor"] for e in incident["events"]]


def test_unmatched_resolved_alert_handled_gracefully(client: TestClient):
    resolved_payload = load_payload("azure_monitor_metric_resolved.json")
    response = client.post("/api/v1/webhooks/azure-monitor", json=resolved_payload)

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "unmatched_resolved"
    assert body["ignored"] == 1
    assert body["created"] == 0


def test_log_analytics_sev0_alert_normalizes_to_sev1(client: TestClient):
    payload = load_payload("azure_monitor_log_firing.json")
    response = client.post("/api/v1/webhooks/azure-monitor", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "created"
    assert body["severity"] == "SEV-1"
    assert body["service"] == "payment-api"

    incident = client.get(f"/api/v1/incidents/{body['incident_id']}").json()
    assert incident["severity"] == "SEV-1"
    assert "PaymentGateway5xxErrorSpike" in incident["title"]


def test_classic_alert_payload_normalizes_correctly(client: TestClient):
    payload = load_payload("azure_monitor_classic_firing.json")
    response = client.post("/api/v1/webhooks/azure-monitor", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "created"
    assert body["service"] == "database"
    assert body["severity"] == "SEV-1"

    incident = client.get(f"/api/v1/incidents/{body['incident_id']}").json()
    assert incident["affected_service"] == "database"
    assert incident["severity"] == "SEV-1"
    assert incident["source"] == "azure-monitor"


def test_invalid_azure_payload_returns_422(client: TestClient):
    response = client.post("/api/v1/webhooks/azure-monitor", json={})
    assert response.status_code == 422

    response2 = client.post("/api/v1/webhooks/azure-monitor", json={"schemaId": "custom", "data": {}})
    assert response2.status_code == 422


def test_authentication_with_configured_secret(client: TestClient):
    payload = load_payload("azure_monitor_metric_firing.json")
    secret = "azure-test-webhook-secret-987"

    with patch.object(settings, "AZURE_WEBHOOK_SECRET", secret):
        # 1. Missing secret should be rejected
        unauth_resp = client.post("/api/v1/webhooks/azure-monitor", json=payload)
        assert unauth_resp.status_code == 401
        assert "Invalid or missing Azure webhook authentication credentials" in unauth_resp.json()["detail"]

        # 2. Invalid secret should be rejected
        wrong_resp = client.post("/api/v1/webhooks/azure-monitor", json=payload, params={"code": "wrong-secret"})
        assert wrong_resp.status_code == 401

        # 3. Valid secret via query parameter (?code=...)
        auth_query_resp = client.post("/api/v1/webhooks/azure-monitor", json=payload, params={"code": secret})
        assert auth_query_resp.status_code == 200
        assert auth_query_resp.json()["action"] == "created"

        # 4. Valid secret via X-Azure-Webhook-Secret header
        auth_header_resp = client.post(
            "/api/v1/webhooks/azure-monitor",
            json=load_payload("azure_monitor_log_firing.json"),
            headers={"X-Azure-Webhook-Secret": secret},
        )
        assert auth_header_resp.status_code == 200
        assert auth_header_resp.json()["action"] == "created"

        # 5. Valid secret via Authorization: Bearer <secret>
        auth_bearer_resp = client.post(
            "/api/v1/webhooks/azure-monitor",
            json=load_payload("azure_monitor_classic_firing.json"),
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert auth_bearer_resp.status_code == 200
        assert auth_bearer_resp.json()["action"] == "created"


def test_orchestrator_execution_on_webhook(client: TestClient):
    payload = load_payload("azure_monitor_metric_firing.json")
    response = client.post("/api/v1/webhooks/azure-monitor?orchestrate=true", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "created"
    assert body["orchestrator_status"] in {"completed", "completed_with_warnings"}
    assert body["orchestrator_step"] == "END"


def test_missing_azure_config_leaves_app_working(client: TestClient):
    # Verify unconfigured Azure secret allows normal execution without exceptions
    with patch.object(settings, "AZURE_WEBHOOK_SECRET", ""):
        # 1. Health check works
        health_resp = client.get("/api/v1/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "healthy"

        # 2. Azure Monitor webhook accepts alerts in open/dev mode
        payload = load_payload("azure_monitor_metric_firing.json")
        webhook_resp = client.post("/api/v1/webhooks/azure-monitor", json=payload)
        assert webhook_resp.status_code == 200
        assert webhook_resp.json()["action"] == "created"

        # 3. Alertmanager webhook works
        am_resp = client.post("/api/v1/webhooks/alertmanager", json=load_payload("alertmanager_firing.json"))
        assert am_resp.status_code == 200
        assert am_resp.json()["created"] == 1

        # 4. Simulator works
        sim_resp = client.post("/api/v1/incidents/simulate", json={"scenario": "payment_api_latency"})
        assert sim_resp.status_code == 201
        assert sim_resp.json()["success"] is True
