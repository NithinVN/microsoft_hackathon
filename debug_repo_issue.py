import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.db.base import Base
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.schemas.incident import (
    ActionExecutionCreate,
    DiagnosisCreate,
    EngineerFeedbackCreate,
    IncidentCreate,
    IncidentUpdate,
    RemediationActionCreate,
)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

async def main():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        repo = IncidentRepository(session)
        incident = await repo.create_incident(IncidentCreate(
            incident_id="INC-700",
            title="Redis Connection Storm",
            description="Redis connection saturation caused checkout errors during peak traffic.",
            severity="SEV-1",
            status="INVESTIGATING",
            affected_service="payment-api",
            symptoms=["Checkout error rate above 20%", "Queue depth rose to 900"],
        ))
        print('created', incident.id)
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
        print('before update, incident dict', incident.status, incident.resolved_at)
        try:
            resolved = await repo.update_incident(
                incident.id,
                IncidentUpdate(status='RESOLVED', resolved_at=datetime.now(timezone.utc), description='Recovered after pool expansion.'),
            )
            print('resolved ok', resolved)
            if resolved and resolved.postmortem:
                print('postmortem title', resolved.postmortem.title)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            print('EXC TYPE', type(exc))

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

asyncio.run(main())
