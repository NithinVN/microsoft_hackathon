from backend.app.knowledge.rag_service import ingest_runbooks, retrieve_runbook_knowledge


def test_ingest_runbooks_creates_document_index():
    index = ingest_runbooks()

    assert index["documents"]
    document_names = {doc["document_name"] for doc in index["documents"]}
    assert "postgresql-connection-pool-troubleshooting.md" in document_names
    assert "kubernetes-service-troubleshooting.md" in document_names


def test_retrieve_runbook_knowledge_returns_sectioned_matches():
    result = retrieve_runbook_knowledge("connection pool exhaustion and idle sessions", service="database")

    assert result["documents"]
    first = result["documents"][0]
    assert "document_name" in first
    assert "relevant_section" in first
    assert "retrieved_text" in first
    assert "relevance_info" in first
    assert "database" in first["document_name"].lower() or "database" in first["retrieved_text"].lower()
    assert first["retrieved_text"]


def test_diagnosis_agent_uses_rag_runbook_evidence():
    investigation = {
        "incident_id": "INC-RAG-1",
        "current_state": "The database is saturated and the payment API is timing out.",
        "symptoms": ["Active database connections pinned at 100/100 max capacity", "Gateway timeouts across checkout"],
        "candidate_causes": [{"cause": "Database connection exhaustion from unchecked session churn.", "status": "hypothesis", "classification": "hypothesis", "source": "current telemetry"}],
        "evidence": [{"item": "Connection saturation is observed under a traffic spike.", "classification": "fact", "source": "current telemetry"}],
    }
    blast_radius = {
        "directly_affected_services": ["database", "payment-api"],
        "potentially_affected_services": ["api-gateway"],
        "severity_assessment": "High",
        "user_impact": "Checkout is degraded",
        "evidence": [],
    }
    memory = {
        "similar_incidents": [{"incident_id": "INC-H101", "root_cause": "Unclosed database sessions caused pool exhaustion."}],
        "memory_sources": [{"memory_id": "INC-H101", "content": "Connection saturation from unclosed sessions caused gateway timeouts.", "classification": "historical_fact", "source": "Hindsight", "type": "root_cause"}],
        "memory_confidence": 0.7,
    }

    from backend.app.agents.diagnosis_agent import diagnose_incident

    rag_result = retrieve_runbook_knowledge("connection pool exhaustion and database session churn", service="database")
    result = diagnose_incident(investigation, blast_radius, memory, rag_result)

    assert result["supporting_evidence"]
    assert any(item.get("source") == "runbook" for item in result["supporting_evidence"])
    assert result["confidence"] > 0.4
