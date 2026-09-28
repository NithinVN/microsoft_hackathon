from backend.app.agents import diagnose_incident
from backend.app.agents.blast_radius_agent import assess_blast_radius
from backend.app.agents.incident_memory_agent import assess_incident_memory
from backend.app.agents.investigation_agent import investigate_incident
from backend.app.tools import get_runbook


def test_diagnosis_agent_with_strong_evidence():
    investigation = investigate_incident("INC-H102")
    blast_radius = assess_blast_radius("INC-H102")
    memory = assess_incident_memory("INC-H102")
    runbook = get_runbook({"service": "payment-api"})

    result = diagnose_incident(investigation, blast_radius, memory, runbook)

    assert result["primary_hypothesis"]
    assert result["confidence"] >= 0.7
    assert result["historical_matches"]
    assert result["supporting_evidence"]
    assert any(item.get("source") == "current telemetry" for item in result["supporting_evidence"])
    assert any(item.get("source") == "Hindsight" for item in result["supporting_evidence"])
    assert any(item.get("source") == "runbook" for item in result["supporting_evidence"])
    assert result["recommended_next_checks"]


def test_diagnosis_agent_handles_conflicting_evidence():
    investigation = {
        "incident_id": "INC-CONFLICT",
        "current_state": "Payment API latency elevated and thread pool utilization high.",
        "symptoms": ["Payment authorization latency spiked to 9,400ms", "Worker thread saturation reached 98%"],
        "abnormal_signals": ["thread starvation", "latency spike"],
        "evidence": [
            {"item": "Thread utilization is 98% and queue backlog is elevated.", "classification": "fact", "source": "current telemetry"},
            {"item": "Database connection saturation is observed in another service.", "classification": "fact", "source": "current telemetry"},
        ],
        "candidate_causes": [
            {"cause": "Database connection exhaustion is the primary cause.", "status": "fact", "classification": "fact", "source": "current telemetry"},
            {"cause": "Downstream payment gateway latency is the primary cause.", "status": "hypothesis", "classification": "hypothesis", "source": "similar incident match"},
        ],
    }
    blast_radius = {
        "directly_affected_services": ["payment-api", "database"],
        "potentially_affected_services": ["order-service"],
        "severity_assessment": "High: dependency path spans multiple critical services.",
        "user_impact": "Customer-facing payment flows are likely degraded.",
        "evidence": [
            {"service": "payment-api", "reason": "Directly affected service.", "source": "incident signals", "classification": "fact"},
            {"service": "database", "reason": "Likely secondary impact path.", "source": "dependency graph", "classification": "hypothesis"},
        ],
    }
    memory = {
        "similar_incidents": [{"incident_id": "INC-H101", "root_cause": "Unclosed database sessions caused connection exhaustion."}],
        "historical_root_causes": [{"text": "Unclosed database sessions caused connection exhaustion."}],
        "memory_sources": [
            {"memory_id": "memory-db", "service": "database", "content": "Historical database connection exhaustion and pool saturation caused checkouts to fail.", "classification": "historical_fact", "source": "Hindsight", "type": "root_cause", "supporting_evidence": ["INC-H101"]},
        ],
        "memory_confidence": 0.72,
    }
    runbook = get_runbook({"service": "database"})

    result = diagnose_incident(investigation, blast_radius, memory, runbook)

    assert result["contradicting_evidence"]
    assert result["confidence"] < 0.8
    assert "payment" in result["primary_hypothesis"].lower() or "database" in result["primary_hypothesis"].lower()
    assert any(item.get("source") == "current telemetry" for item in result["contradicting_evidence"])


def test_diagnosis_agent_handles_insufficient_evidence():
    investigation = {
        "incident_id": "INC-UNKNOWN",
        "current_state": "Information unavailable: no matching incident was found.",
        "symptoms": [],
        "abnormal_signals": [],
        "candidate_causes": [{"cause": "Information unavailable: no matching incident was found.", "status": "hypothesis", "classification": "hypothesis", "source": "missing evidence"}],
        "evidence": [],
    }
    blast_radius = {
        "directly_affected_services": [],
        "potentially_affected_services": [],
        "severity_assessment": "Information unavailable: no service or dependency evidence was available.",
        "user_impact": "Information unavailable: no service context was available for this incident.",
        "evidence": [],
    }
    memory = {
        "similar_incidents": [],
        "historical_root_causes": [],
        "memory_sources": [],
        "memory_confidence": 0,
    }

    result = diagnose_incident(investigation, blast_radius, memory, None)

    assert "Information unavailable" in result["primary_hypothesis"]
    assert result["confidence"] <= 0.25
    assert not result["supporting_evidence"]
    assert result["alternative_hypotheses"]
    assert result["recommended_next_checks"]
