from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.db.base import Base
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.schemas.incident import (
    ActionExecutionCreate,
    DiagnosisCreate,
    EngineerFeedbackCreate,
    IncidentCreate,
    IncidentEventCreate,
    IncidentUpdate,
    InvestigationCreate,
    PostmortemCreate,
    RemediationActionCreate,
)

# Test-specific in-memory async SQLite engine
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Provides a fresh isolated database session with created schema for each test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_incident_creation(db_session: AsyncSession):
    """Test creating an operational incident with validation, symptoms, and initial timeline event."""
    repo = IncidentRepository(db_session)

    incident_in = IncidentCreate(
        incident_id="INC-7041",
        title="PostgreSQL Connection Pool Starvation in Payment Gateway",
        description="Pool saturated at 100/100 connections. P99 latency reached 4200ms.",
        severity="SEV-1",
        status="DETECTED",
        source="simulator",
        affected_service="payment-processor",
        symptoms=["P99 latency > 4000ms", "504 Gateway Timeouts on /charge", "Pool saturation 100%"],
        metadata={"region": "us-east-1", "tier": 1},
    )

    incident = await repo.create_incident(incident_in)
    assert incident.id is not None
    assert incident.incident_id == "INC-7041"
    assert incident.severity == "SEV-1"
    assert incident.status == "DETECTED"
    assert incident.affected_service == "payment-processor"
    assert len(incident.symptoms) == 3
    assert "Pool saturation 100%" in incident.symptoms

    # Verify automatic chronological initial detection event creation
    retrieved = await repo.get_incident_by_id(incident.id)
    assert retrieved is not None
    assert len(retrieved.events) == 1
    assert retrieved.events[0].event_type == "INCIDENT_DETECTED"
    assert retrieved.events[0].actor == "simulator"


@pytest.mark.asyncio
async def test_incident_retrieval_and_update(db_session: AsyncSession):
    """Test retrieving by business incident_id, listing, and updating operational status."""
    repo = IncidentRepository(db_session)

    # Create 2 incidents
    await repo.create_incident(
        IncidentCreate(
            incident_id="INC-100",
            title="Redis Cache Stampede",
            severity="SEV-2",
            affected_service="catalog-service",
            symptoms=["Cache hit ratio dropped to 11%"],
        )
    )
    await repo.create_incident(
        IncidentCreate(
            incident_id="INC-200",
            title="Database Latency Spike",
            severity="SEV-1",
            affected_service="payment-processor",
            symptoms=["Queue depth > 300"],
        )
    )

    # Retrieve by business ID
    inc = await repo.get_incident_by_incident_id("INC-100")
    assert inc is not None
    assert inc.affected_service == "catalog-service"
    assert "Cache hit ratio dropped to 11%" in inc.symptoms

    # List filtered by severity
    sev1_list = await repo.list_incidents(severity="SEV-1")
    assert len(sev1_list) == 1
    assert sev1_list[0].incident_id == "INC-200"

    # Update incident status and symptoms
    updated = await repo.update_incident(
        inc.id,
        IncidentUpdate(
            status="INVESTIGATING",
            description="Investigation agent active",
            symptoms=["Cache hit ratio dropped to 11%", "Read replica CPU at 96%"],
        ),
    )
    assert updated is not None
    assert updated.status == "INVESTIGATING"
    assert updated.description == "Investigation agent active"
    assert len(updated.symptoms) == 2


@pytest.mark.asyncio
async def test_event_creation_and_chronological_timeline(db_session: AsyncSession):
    """Test recording timeline events and preserving chronological order."""
    repo = IncidentRepository(db_session)

    incident = await repo.create_incident(
        IncidentCreate(
            incident_id="INC-300",
            title="Worker Node OOM Throttling",
            severity="SEV-2",
            affected_service="billing-worker",
        )
    )

    # Add events in sequence
    e1 = await repo.add_event(
        incident.id,
        IncidentEventCreate(
            event_type="AGENT_DISPATCHED",
            actor="IncidentOrchestrator",
            message="Dispatched Investigation and Blast Radius agents.",
        ),
    )
    e2 = await repo.add_event(
        incident.id,
        IncidentEventCreate(
            event_type="TELEMETRY_ANOMALY_CONFIRMED",
            actor="InvestigationAgent",
            message="Confirmed memory leak in billing worker pods.",
            payload={"memory_mb": 4096, "threshold_mb": 2048},
        ),
    )

    retrieved = await repo.get_incident_by_id(incident.id)
    assert retrieved is not None
    assert len(retrieved.events) == 3
    event_types = [event.event_type for event in retrieved.events]
    assert event_types == ["INCIDENT_DETECTED", "AGENT_DISPATCHED", "TELEMETRY_ANOMALY_CONFIRMED"]


@pytest.mark.asyncio
async def test_investigation_and_diagnosis_storage(db_session: AsyncSession):
    """Test storing investigation telemetry evidence and diagnosis hypothesis."""
    repo = IncidentRepository(db_session)

    incident = await repo.create_incident(
        IncidentCreate(
            incident_id="INC-400",
            title="Kafka Consumer Lag Cascade",
            severity="SEV-2",
            affected_service="notification-dispatcher",
        )
    )

    # Store investigation
    inv = await repo.store_investigation(
        incident.id,
        InvestigationCreate(
            findings="Consumer group lag reached 45,000 messages.",
            telemetry_summary={"lag": 45000, "partition_skew": True},
            correlated_traces=[{"trace_id": "tr-400-a", "duration_ms": 3200}],
        ),
    )
    assert inv.id is not None

    # Store diagnosis
    diag = await repo.store_diagnosis(
        incident.id,
        DiagnosisCreate(
            root_cause_hypothesis="Poison pill JSON message blocking deserializer thread.",
            confidence_score=0.95,
            chain_of_thought=["Lag spike on partition 3", "Deserializer error in logs"],
            risk_assessment="Low risk to discard dead letter message.",
        ),
    )
    assert diag.id is not None
    assert diag.confidence_score == 0.95

    # Check incident associations
    retrieved = await repo.get_incident_by_id(incident.id)
    assert retrieved is not None
    assert len(retrieved.investigations) == 1
    assert len(retrieved.diagnoses) == 1


@pytest.mark.asyncio
async def test_remediation_and_execution_recording(db_session: AsyncSession):
    """Test storing candidate vetted remediation and recording human-approved execution."""
    repo = IncidentRepository(db_session)

    incident = await repo.create_incident(
        IncidentCreate(
            incident_id="INC-500",
            title="Postgres Connection Leak",
            severity="SEV-1",
            affected_service="payment-processor",
        )
    )

    # Store candidate remediation (pre-approved vetted routine - NOT arbitrary shell)
    remediation = await repo.store_remediation(
        incident.id,
        RemediationActionCreate(
            action_key="scale_pool_and_kill_idle",
            title="Expand PgBouncer pool to 250 & Terminate Idle Leaked Connections",
            description="Resize PgBouncer pool without restart and terminate connections idle > 60s.",
            command_template="pgbouncer_ctl reload --max-clients 250 && sql_clean_idle_transactions(idle_sec=60)",
            safety_level="SAFE",
            historical_precedent="SUCCESS_BEFORE",
            is_recommended=True,
        ),
    )
    assert remediation.id is not None
    assert remediation.is_recommended is True

    # Record human approval and execution
    execution = await repo.store_execution_result(
        incident.id,
        ActionExecutionCreate(
            remediation_action_id=remediation.id,
            status="APPROVED",
            approved_by="Principal SRE Jane Doe",
            approval_notes="Approved based on Hindsight INC-419 past success precedent.",
            execution_output="PgBouncer reloaded: max_clients=250. Terminated 42 idle connections.",
            verification_status="VERIFIED_RECOVERED",
        ),
    )
    assert execution.id is not None
    assert execution.status == "APPROVED"
    assert execution.verification_status == "VERIFIED_RECOVERED"

    retrieved = await repo.get_incident_by_id(incident.id)
    assert retrieved is not None
    assert len(retrieved.remediations) == 1
    assert len(retrieved.executions) == 1


@pytest.mark.asyncio
async def test_postmortem_and_feedback_recording(db_session: AsyncSession):
    """Test recording engineer feedback and postmortem with Hindsight retain status."""
    repo = IncidentRepository(db_session)

    incident = await repo.create_incident(
        IncidentCreate(
            incident_id="INC-600",
            title="Redis Memory Exhaustion Outage",
            severity="SEV-2",
            affected_service="session-store",
        )
    )

    # Record engineer feedback
    feedback = await repo.store_feedback(
        incident.id,
        EngineerFeedbackCreate(
            engineer_id="eng_sarah",
            rating=5,
            comments="Failed-Fix warning saved us from running FLUSHALL. Great safety guardrail.",
            accuracy_evaluation="accurate",
        ),
    )
    assert feedback.id is not None
    assert feedback.rating == 5

    # Record postmortem
    postmortem = await repo.store_postmortem(
        incident.id,
        PostmortemCreate(
            title="Redis Memory Exhaustion Incident Postmortem",
            duration_minutes=18,
            root_cause="Unbounded session TTL under promotion traffic.",
            trigger_event="Campaign blast at 12:00 UTC",
            corrective_actions=[
                "Set maxmemory-policy to volatile-lru",
                "Add Redis memory usage alerting at 80%",
            ],
            timeline=[
                {"time": "12:05", "event": "Memory alert fired"},
                {"time": "12:12", "event": "Remediation executed"},
                {"time": "12:23", "event": "Recovery verified"},
            ],
            hindsight_retained=True,
            hindsight_memory_id="MEM-ORG-9901",
        ),
    )
    assert postmortem.id is not None
    assert postmortem.hindsight_retained is True
    assert postmortem.hindsight_memory_id == "MEM-ORG-9901"

    retrieved = await repo.get_incident_by_id(incident.id)
    assert retrieved is not None
    assert retrieved.postmortem is not None
    assert retrieved.postmortem.hindsight_retained is True
    assert len(retrieved.feedbacks) == 1


@pytest.mark.asyncio
async def test_resolved_incident_generates_learning_loop_postmortem(db_session: AsyncSession):
    """Resolved incidents must produce a structured postmortem with action history and Hindsight retention metadata."""
    repo = IncidentRepository(db_session)

    incident = await repo.create_incident(
        IncidentCreate(
            incident_id="INC-700",
            title="Redis Connection Storm",
            description="Redis connection saturation caused checkout errors during peak traffic.",
            severity="SEV-1",
            status="INVESTIGATING",
            affected_service="payment-api",
            symptoms=["Checkout error rate above 20%", "Queue depth rose to 900"],
        )
    )

    await repo.store_diagnosis(
        incident.id,
        DiagnosisCreate(
            agent_name="DiagnosisAgent",
            root_cause_hypothesis="Expired connection pool re-use under promotion traffic caused saturation.",
            confidence_score=0.93,
            chain_of_thought=["Worker counts increased", "Connection pool leak observed"],
            risk_assessment="High customer impact",
        ),
    )

    successful_action = await repo.store_remediation(
        incident.id,
        RemediationActionCreate(
            action_key="scale_pool",
            title="Increase DB pool size",
            description="Scale DB pool and drain stale connections.",
            command_template="scale_pool 250",
            safety_level="SAFE",
            historical_precedent="SUCCESS_BEFORE",
            is_recommended=True,
        ),
    )
    await repo.store_execution_result(
        incident.id,
        ActionExecutionCreate(
            remediation_action_id=successful_action.id,
            status="VERIFIED_RECOVERED",
            approved_by="eng_rose",
            approval_notes="Pool growth fixed the leak.",
            execution_output="Connection pool stabilized; checkout recovered.",
            verification_status="VERIFIED_RECOVERED",
        ),
    )

    failed_action = await repo.store_remediation(
        incident.id,
        RemediationActionCreate(
            action_key="flush_redis",
            title="Flush Redis",
            description="Unsafe flush during live traffic.",
            command_template="flushall",
            safety_level="DANGEROUS",
            historical_precedent="FAILED_BEFORE",
            is_recommended=False,
        ),
    )
    await repo.store_execution_result(
        incident.id,
        ActionExecutionCreate(
            remediation_action_id=failed_action.id,
            status="FAILED",
            approved_by="eng_rose",
            approval_notes="Rejected after historical safeguard.",
            execution_output="Unsafe action rejected; no production impact.",
            verification_status="NOT_APPLICABLE",
        ),
    )

    await repo.store_feedback(
        incident.id,
        EngineerFeedbackCreate(
            engineer_id="eng_rose",
            rating=5,
            comments="The pool expansion worked. We should never flush live Redis again.",
            accuracy_evaluation="accurate",
        ),
    )

    resolved = await repo.update_incident(
        incident.id,
        IncidentUpdate(status="RESOLVED", resolved_at=utcnow(), description="Recovered after pool expansion."),
    )

    assert resolved is not None
    assert resolved.status == "RESOLVED"
    assert resolved.postmortem is not None
    assert resolved.postmortem.root_cause == "Expired connection pool re-use under promotion traffic caused saturation."
    assert resolved.postmortem.what_failed
    assert resolved.postmortem.what_worked
    assert resolved.postmortem.lessons_learned
    assert resolved.postmortem.hindsight_retained is True
    assert resolved.postmortem.hindsight_memory_id is not None
