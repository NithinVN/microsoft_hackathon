import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def client():
    # Setup isolated test engine
    test_engine = create_async_engine(TEST_DB_URL, echo=False)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    import asyncio

    async def init_tables():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(init_tables())

    async def override_get_db():
        async with test_session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    asyncio.run(test_engine.dispose())


def test_api_incident_lifecycle(client: TestClient):
    """Test incident creation, event addition, remediation, and retrieval via REST API."""
    unique_id = f"INC-API-{uuid.uuid4().hex[:6]}"

    # 1. Create incident with symptoms
    payload = {
        "incident_id": unique_id,
        "title": "API Gateway Connection Spike",
        "description": "Upstream latency degraded",
        "severity": "SEV-1",
        "status": "DETECTED",
        "source": "simulator",
        "affected_service": "api-gateway",
        "symptoms": ["P99 latency > 3000ms", "504 Gateway Timeout"],
        "metadata": {"env": "prod"},
    }
    create_resp = client.post("/api/v1/incidents", json=payload)
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["incident_id"] == unique_id
    assert len(data["symptoms"]) == 2
    assert "P99 latency > 3000ms" in data["symptoms"]
    incident_pk = data["id"]
    assert len(data["events"]) >= 1

    # 2. Get incident by business ID
    get_resp = client.get(f"/api/v1/incidents/{unique_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["affected_service"] == "api-gateway"
    assert "P99 latency > 3000ms" in get_resp.json()["symptoms"]

    # 3. Add timeline event
    event_payload = {
        "event_type": "INVESTIGATION_STARTED",
        "actor": "IncidentOrchestrator",
        "message": "Orchestrator dispatched investigation agent.",
        "payload": {"step": 2},
    }
    event_resp = client.post(f"/api/v1/incidents/{incident_pk}/events", json=event_payload)
    assert event_resp.status_code == 201
    assert event_resp.json()["event_type"] == "INVESTIGATION_STARTED"

    # 4. Add candidate remediation
    rem_payload = {
        "action_key": "scale_connections",
        "title": "Scale connection pool to 200",
        "description": "Increase pool size to absorb incoming burst",
        "command_template": "pgbouncer_ctl reload --max-clients 200",
        "safety_level": "SAFE",
        "historical_precedent": "SUCCESS_BEFORE",
        "is_recommended": True,
    }
    rem_resp = client.post(f"/api/v1/incidents/{incident_pk}/remediations", json=rem_payload)
    assert rem_resp.status_code == 201
    assert rem_resp.json()["action_key"] == "scale_connections"


    # 5. Store postmortem
    pm_payload = {
        "title": "API Gateway Latency Postmortem",
        "duration_minutes": 15,
        "root_cause": "Database connection saturation caused upstream 504 timeouts.",
        "trigger_event": "Batch marketing email campaign",
        "corrective_actions": ["Increase baseline pool", "Add circuit breaker"],
        "timeline": [{"time": "12:00", "event": "Alert fired"}],
        "hindsight_retained": True,
        "hindsight_memory_id": "MEM-API-001",
    }
    pm_resp = client.post(f"/api/v1/incidents/{incident_pk}/postmortem", json=pm_payload)
    assert pm_resp.status_code == 201
    assert pm_resp.json()["hindsight_retained"] is True

    # 6. List incidents
    list_resp = client.get("/api/v1/incidents?severity=SEV-1")
    assert list_resp.status_code == 200
    incidents = list_resp.json()
    assert any(i["incident_id"] == unique_id for i in incidents)


def test_organizational_memory_route_preserves_current_incident_context(client: TestClient, monkeypatch):
    from backend.app.api.v1.endpoints import incidents

    monkeypatch.setattr(
        incidents.hindsight_service,
        "recall_organizational_memories",
        lambda **kwargs: {
            "status": "available",
            "bank_id": "test-bank",
            "health": {"healthy": True, "status": "connected"},
            "categories": {},
            "retrieved_memories": [{"id": "memory-1", "text": "Observed pool starvation."}],
            "agent_evidence": [{"id": "memory-1", "text": "Observed pool starvation."}],
        },
    )

    response = client.get(
        "/api/v1/incidents/organizational-memory",
        params={
            "incident_id": "INC-7041",
            "service": "payment-processor",
            "query": "connection pool saturation",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["current_incident"] == {
        "incident_id": "INC-7041",
        "service": "payment-processor",
        "query": "connection pool saturation",
    }
    assert body["retrieved_memories"][0]["id"] == "memory-1"
