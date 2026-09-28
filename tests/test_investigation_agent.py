import pytest

from backend.app.agents.investigation_agent import investigate_incident


@pytest.mark.parametrize(
    "incident_id, expected_service, expected_signal",
    [
        ("INC-H102", "payment-api", "thread starvation"),
        ("INC-H101", "database", "connection pool"),
        ("INC-H103", "order-service", "poison"),
    ],
)
def test_investigation_agent_collects_evidence_for_incident(incident_id, expected_service, expected_signal):
    result = investigate_incident(incident_id)

    assert result["incident_id"] == incident_id
    assert expected_service in result["affected_services"]
    assert result["current_state"]
    assert result["symptoms"]
    assert result["timeline"]
    assert result["evidence"]
    assert result["candidate_causes"]

    normalized_parts = [
        result["current_state"].lower(),
        *[str(item).lower() for item in result["abnormal_signals"]],
        *[str(item).lower() for item in result["candidate_causes"]],
    ]
    normalized_text = " ".join(normalized_parts)
    assert expected_signal in normalized_text or expected_service in normalized_text

    classifications = {entry.get("classification") for entry in result["evidence"]}
    assert "fact" in classifications or "hypothesis" in classifications


def test_investigation_agent_marks_unavailable_information_explicitly():
    result = investigate_incident("INC-DOES-NOT-EXIST")

    assert result["incident_id"] == "INC-DOES-NOT-EXIST"
    assert result["current_state"] == "Information unavailable: no matching incident was found."
    assert result["uncertainties"]
    assert any("Information unavailable" in item or "no matching incident" in item.lower() for item in result["uncertainties"])


def test_investigation_agent_distinguishes_facts_from_hypotheses():
    result = investigate_incident("INC-H104")

    assert result["candidate_causes"]
    assert any(item.get("status") == "hypothesis" for item in result["candidate_causes"])
    assert any(item.get("classification") == "fact" for item in result["evidence"]) or result["timeline"]
    assert any("Information unavailable" in item or "No" in item for item in result["uncertainties"]) or not result["uncertainties"]
