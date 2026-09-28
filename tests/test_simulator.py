import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.schemas.simulator import SimulateIncidentRequest
from backend.app.simulator.engine import IncidentSimulatorEngine
from backend.app.simulator.historical_seeds import get_historical_seeds
from backend.app.simulator.scenarios import get_all_scenarios

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Isolated in-memory database session for testing simulator engine."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def client():
    """Test client with isolated test database dependency override."""
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


@pytest.mark.asyncio
async def test_simulate_all_5_scenarios(db_session: AsyncSession):
    """Verify that all 5 deterministic scenarios generate valid incidents and telemetry."""
    engine = IncidentSimulatorEngine(db_session)

    scenarios = [
        ("database_connection_pool", "SEV-1", "payment-processor"),
        ("payment_api_latency", "SEV-1", "payment-processor"),
        ("memory_leak", "SEV-2", "billing-worker"),
        ("failed_deployment", "SEV-1", "auth-service"),
        ("dependency_service_failure", "SEV-2", "catalog-service"),
    ]

    for scenario_id, expected_sev, expected_service in scenarios:
        req = SimulateIncidentRequest(scenario=scenario_id)
        result = await engine.simulate(req)

        assert result.success is True
        assert result.incident.incident_id.startswith("INC-")
        assert result.incident.severity == expected_sev
        assert result.incident.affected_service == expected_service
        assert len(result.incident.symptoms) >= 1
        assert len(result.live_logs) >= 1
        assert len(result.traces) >= 1
        assert "cpu_usage_pct" in result.telemetry_metrics or "error_rate_pct" in result.telemetry_metrics


@pytest.mark.asyncio
async def test_simulator_db_integrity(db_session: AsyncSession):
    """Verify that simulating an incident creates Service, Deployment, Alert, and Incident records."""
    engine = IncidentSimulatorEngine(db_session)

    req = SimulateIncidentRequest(scenario="database_connection_pool", severity="critical")
    result = await engine.simulate(req)

    # Check incident was stored in DB
    stored_inc = await engine.repo.get_incident_by_id(result.incident.id)
    assert stored_inc is not None
    assert stored_inc.incident_id == result.incident.incident_id
    assert stored_inc.affected_service == "payment-processor"
    assert stored_inc.severity == "SEV-1"

    # Check timeline events recorded
    assert len(stored_inc.events) >= 2
    event_types = [e.event_type for e in stored_inc.events]
    assert "INCIDENT_DETECTED" in event_types
    assert "PIPELINE_INITIALIZED" in event_types

    # Check investigation telemetry was recorded
    assert len(stored_inc.investigations) == 1
    assert "Telemetry anomaly" in stored_inc.investigations[0].findings


def test_simulator_api_endpoints(client: TestClient):
    """Test POST /api/v1/incidents/simulate and scenario catalog endpoints."""
    # 1. Test scenario list
    scenarios_resp = client.get("/api/v1/incidents/simulate/scenarios")
    assert scenarios_resp.status_code == 200
    scenarios = scenarios_resp.json()
    assert len(scenarios) == 5
    scenario_ids = [s["id"] for s in scenarios]
    assert "database_connection_pool" in scenario_ids
    assert "failed_deployment" in scenario_ids

    # 2. Test historical seeds list
    seeds_resp = client.get("/api/v1/incidents/simulate/historical-seeds")
    assert seeds_resp.status_code == 200
    seeds = seeds_resp.json()
    assert len(seeds) >= 4
    assert any(s["hindsight_incident_id"] == "INC-419" for s in seeds)

    # 3. Test triggering simulation via POST /api/v1/incidents/simulate
    sim_payload = {
        "scenario": "database_connection_pool",
        "severity": "critical",
    }
    sim_resp = client.post("/api/v1/incidents/simulate", json=sim_payload)
    assert sim_resp.status_code == 201
    sim_data = sim_resp.json()
    assert sim_data["success"] is True
    assert sim_data["incident"]["affected_service"] == "payment-processor"
    assert sim_data["incident"]["severity"] == "SEV-1"
    assert sim_data["suggested_hindsight_incident"] == "INC-419"

    # 4. Test invalid scenario returns 400 Bad Request
    bad_resp = client.post("/api/v1/incidents/simulate", json={"scenario": "non_existent_scenario"})
    assert bad_resp.status_code == 400
    assert "Unknown scenario" in bad_resp.json()["detail"]
