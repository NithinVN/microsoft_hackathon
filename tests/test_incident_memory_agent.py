from backend.app.agents.incident_memory_agent import assess_incident_memory


def test_assess_incident_memory_uses_hindsight_recall_and_reflect(monkeypatch):
    class FakeResult(dict):
        pass

    def fake_get_incident_details(payload):
        return {
            "ok": True,
            "data": {
                "incident": {
                    "incident_id": "INC-H102",
                    "service": "payment-api",
                    "title": "Stripe Third-Party Webhook Latency & Thread Pool Starvation",
                    "symptoms": ["Payment authorization latency spiked", "Worker thread saturation reached 98%"],
                    "alerts": ["PaymentApiLatencyCritical (>5000ms)"],
                    "root_cause": "Downstream payment gateway API experienced regional degradation",
                }
            },
            "error": None,
        }

    def fake_recall_similar_incidents(query, service=None, limit=5, bank_id=None):
        return [
            {
                "id": "mem-120",
                "text": "Payment API thread starvation caused by external latency; enabling circuit breaker fixed it.",
                "metadata": {"incident_id": "INC-H102", "service": "payment-api"},
                "score": 0.93,
                "tags": ["incident", "service:payment-api"],
            }
        ]

    def fake_recall_successful_remediations(service=None, action_type=None, query=None, bank_id=None):
        return [
            {
                "id": "mem-201",
                "text": "ENABLE_CIRCUIT_BREAKER tripped and restored payment API latency.",
                "metadata": {"action_type": "ENABLE_CIRCUIT_BREAKER", "service": "payment-api"},
                "score": 0.88,
                "tags": ["remediation", "outcome:successful"],
            }
        ]

    def fake_recall_failed_remediations(service=None, action_type=None, query=None, bank_id=None):
        return [
            {
                "id": "mem-202",
                "text": "Scaling pods worsened thread starvation and did not fix the underlying issue.",
                "metadata": {"action_type": "SCALE_POD_REPLICAS", "service": "payment-api"},
                "score": 0.8,
                "tags": ["remediation", "outcome:failed"],
            }
        ]

    def fake_reflect_on_incident_history(query, context=None, service=None, bank_id=None):
        return {
            "success": True,
            "text": "Calls to external payment providers should fail fast and queue retries. Avoid scaling beyond the circuit breaker when the bottleneck is external latency.",
            "based_on": [{"id": "mem-120", "text": "external latency pattern"}],
            "usage": {"tokens": 40},
        }

    monkeypatch.setattr("backend.app.agents.incident_memory_agent.get_incident_details", fake_get_incident_details)
    monkeypatch.setattr("backend.app.agents.incident_memory_agent.hindsight_service", type("Svc", (), {
        "recall_similar_incidents": staticmethod(fake_recall_similar_incidents),
        "recall_successful_remediations": staticmethod(fake_recall_successful_remediations),
        "recall_failed_remediations": staticmethod(fake_recall_failed_remediations),
        "reflect_on_incident_history": staticmethod(fake_reflect_on_incident_history),
    }))

    result = assess_incident_memory("INC-H102")

    assert result["similar_incidents"]
    assert result["historical_root_causes"]
    assert result["successful_fixes"]
    assert result["failed_fixes"]
    assert result["engineer_lessons"]
    assert result["historical_patterns"]
    assert result["memory_confidence"] > 0
    assert any(item["memory_id"] == "mem-120" for item in result["memory_sources"])
    assert any(item["content"] for item in result["memory_sources"])
    assert result["memory_sources"]


def test_assess_incident_memory_handles_missing_incident():
    def fake_get_incident_details(payload):
        return {"ok": False, "error": {"code": "incident_not_found"}}

    import backend.app.agents.incident_memory_agent as agent
    agent.get_incident_details = fake_get_incident_details
    agent.hindsight_service = type("Svc", (), {
        "recall_similar_incidents": staticmethod(lambda **kwargs: []),
        "recall_successful_remediations": staticmethod(lambda **kwargs: []),
        "recall_failed_remediations": staticmethod(lambda **kwargs: []),
        "reflect_on_incident_history": staticmethod(lambda **kwargs: {"success": False, "text": "", "based_on": [], "usage": {}}),
    })

    result = agent.assess_incident_memory("INC-UNKNOWN")

    assert result["similar_incidents"] == []
    assert result["historical_root_causes"] == []
    assert result["successful_fixes"] == []
    assert result["failed_fixes"] == []
    assert result["engineer_lessons"] == []
    assert result["historical_patterns"] == []
    assert result["memory_confidence"] == 0
    assert "Information unavailable" in result["memory_sources"][0]["content"]
