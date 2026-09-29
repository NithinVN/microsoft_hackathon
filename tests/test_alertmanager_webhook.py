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

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def client():
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


def load_payload(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_firing_alert_creates_normalized_incident_on_shared_pipeline(client: TestClient):
    response = client.post("/api/v1/webhooks/alertmanager", json=load_payload("alertmanager_firing.json"))

    assert response.status_code == 200
    result = response.json()
    assert result["created"] == 1
    incident_id = result["results"][0]["incident_id"]

    incident_response = client.get(f"/api/v1/incidents/{incident_id}")
    assert incident_response.status_code == 200
    incident = incident_response.json()
    assert incident["source"] == "alertmanager"
    assert incident["severity"] == "SEV-1"
    assert incident["status"] == "DETECTED"
    assert incident["affected_service"] == "payment-api"
    assert incident["detected_at"].startswith("2026-09-29T10:15:00")
    assert incident["metadata"]["alert_labels"]["environment"] == "production"
    assert incident["metadata"]["alert_annotations"]["runbook_url"].endswith("/errors")
    assert "PIPELINE_INITIALIZED" in [event["event_type"] for event in incident["events"]]


def test_repeated_firing_fingerprint_is_idempotent(client: TestClient):
    payload = load_payload("alertmanager_firing.json")
    first = client.post("/api/v1/webhooks/alertmanager", json=payload)
    second = client.post("/api/v1/webhooks/alertmanager", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["created"] == 0
    assert second.json()["ignored"] == 1
    incidents = client.get("/api/v1/incidents", params={"status": "DETECTED"}).json()
    assert len([incident for incident in incidents if incident["source"] == "alertmanager"]) == 1


def test_resolved_alert_closes_existing_incident(client: TestClient):
    firing = client.post("/api/v1/webhooks/alertmanager", json=load_payload("alertmanager_firing.json"))
    incident_id = firing.json()["results"][0]["incident_id"]

    response = client.post("/api/v1/webhooks/alertmanager", json=load_payload("alertmanager_resolved.json"))

    assert response.status_code == 200
    assert response.json()["resolved"] == 1
    incident = client.get(f"/api/v1/incidents/{incident_id}").json()
    assert incident["status"] == "RESOLVED"
    assert incident["resolved_at"].startswith("2026-09-29T10:23:15")
    assert incident["metadata"]["alertmanager_resolution"]["endsAt"].startswith("2026-09-29T10:23:15")
    assert "ALERT_RESOLVED" in [event["event_type"] for event in incident["events"]]


def test_invalid_alertmanager_payload_returns_validation_error(client: TestClient):
    response = client.post(
        "/api/v1/webhooks/alertmanager",
        json={"status": "firing", "alerts": [{"labels": {"service": "payment-api"}}]},
    )

    assert response.status_code == 422


def test_alertmanager_webhook_requires_secret_in_production(client: TestClient):
    payload = load_payload("alertmanager_firing.json")
    with patch.object(settings, "APP_ENV", "production"), patch.object(settings, "ALERTMANAGER_WEBHOOK_SECRET", ""):
        response = client.post("/api/v1/webhooks/alertmanager", json=payload)

    assert response.status_code == 503


def test_alertmanager_webhook_checks_configured_secret(client: TestClient):
    payload = load_payload("alertmanager_firing.json")
    secret = "test-alertmanager-secret-482"
    with patch.object(settings, "APP_ENV", "production"), patch.object(settings, "ALERTMANAGER_WEBHOOK_SECRET", secret):
        missing = client.post("/api/v1/webhooks/alertmanager", json=payload)
        accepted = client.post(
            "/api/v1/webhooks/alertmanager",
            json=payload,
            headers={"X-Alertmanager-Webhook-Secret": secret},
        )

    assert missing.status_code == 401
    assert accepted.status_code == 200
