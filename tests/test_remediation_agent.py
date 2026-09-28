from backend.app.agents.remediation_agent import (
    approve_action,
    build_remediation_plan,
    modify_action,
    reject_action,
)


def test_build_remediation_plan_uses_simulation_and_historical_support():
    investigation = {
        "incident_id": "INC-H102",
        "symptoms": ["Payment authorization latency spiked to 9,400ms", "Worker thread saturation reached 98%"],
        "abnormal_signals": ["thread starvation", "latency spike"],
    }
    blast_radius = {
        "directly_affected_services": ["payment-api"],
        "potentially_affected_services": ["api-gateway"],
    }
    diagnosis = {
        "primary_hypothesis": "Downstream payment gateway latency is causing thread starvation in payment-api.",
        "confidence": 0.82,
        "supporting_evidence": [
            {"evidence": "Thread utilization is 98% and outbound HTTP calls are slow.", "source": "current telemetry"},
            {"evidence": "Check worker thread utilization and outbound timeout configuration.", "source": "runbook"},
        ],
        "historical_matches": ["INC-H102"],
    }
    memory = {
        "similar_incidents": [{"incident_id": "INC-H102", "root_cause": "Downstream payment gateway latency caused thread starvation."}],
        "memory_sources": [{"memory_id": "INC-H102", "content": "Circuit breakers and async retries reduced latency by failing fast.", "classification": "historical_fact", "source": "Hindsight"}],
        "memory_confidence": 0.75,
    }
    runbooks = {
        "documents": [{
            "document_name": "api-latency-troubleshooting.md",
            "relevant_section": "Common response patterns",
            "retrieved_text": "Add client-side timeout limits and circuit breakers for outbound dependencies.",
            "relevance_info": {"score": 0.9},
        }]
    }

    result = build_remediation_plan(investigation, blast_radius, diagnosis, memory, runbooks)

    assert result["recommended_actions"]
    assert result["risk_level"]
    assert result["rollback_plan"]
    assert result["verification_steps"]
    assert all(action["required_approval"] for action in result["recommended_actions"])
    assert all(action["mode"] == "simulation" for action in result["recommended_actions"])
    assert result["historical_support"]


def test_approve_reject_and_modify_actions():
    plan = {
        "recommended_actions": [{
            "action": "ENABLE_CIRCUIT_BREAKER",
            "reason": "Stop threads piling up on slow upstream calls.",
            "expected_outcome": "Reduce queue backlog.",
            "risk": "medium",
            "historical_evidence": ["INC-H102"],
            "required_approval": "human approval required",
            "status": "pending",
            "mode": "simulation",
        }]
    }

    approved = approve_action(plan, 0, "sre-alex")
    assert approved["recommended_actions"][0]["status"] == "approved"
    assert approved["recommended_actions"][0]["approved_by"] == "sre-alex"

    rejected = reject_action(plan, 0, "Not safe for this incident")
    assert rejected["recommended_actions"][0]["status"] == "rejected"
    assert rejected["recommended_actions"][0]["rejection_reason"] == "Not safe for this incident"

    modified = modify_action(plan, 0, "ENABLE_CIRCUIT_BREAKER_AND_RETRY_QUEUE")
    assert modified["recommended_actions"][0]["action"] == "ENABLE_CIRCUIT_BREAKER_AND_RETRY_QUEUE"
    assert modified["recommended_actions"][0]["status"] == "pending"
    assert modified["recommended_actions"][0]["required_approval"] == "human approval required"


def test_remediation_agents_refuse_unsafe_auto_execution():
    plan = build_remediation_plan(
        investigation={"symptoms": ["API latency elevated"], "incident_id": "INC-TEST"},
        blast_radius={"directly_affected_services": ["database"]},
        diagnosis={"primary_hypothesis": "Database connection exhaustion exists.", "confidence": 0.6},
        memory={"memory_sources": [{"memory_id": "INC-H101", "content": "Increase pool headroom and drain idle sessions.", "source": "Hindsight"}]},
        runbooks={"documents": [{"document_name": "postgresql-connection-pool-troubleshooting.md", "relevant_section": "Recovery steps", "retrieved_text": "Increase max_connections only after connection drain and idle cleanup.", "relevance_info": {"score": 0.8}}]},
    )

    assert all(action["mode"] == "simulation" for action in plan["recommended_actions"])
    assert all("human approval" in str(action["required_approval"]).lower() for action in plan["recommended_actions"])
    assert "no production execution" in plan["why"].lower()
