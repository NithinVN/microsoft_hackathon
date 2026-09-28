import pytest

from backend.app.agents.blast_radius_agent import assess_blast_radius


@pytest.mark.parametrize(
    "incident_id, expected_direct, expected_potential",
    [
        ("INC-H101", ["database"], ["payment-api", "order-service", "user-service", "notification-service", "api-gateway"]),
        ("INC-H102", ["payment-api", "order-service", "database", "notification-service", "api-gateway"], ["user-service"]),
        ("INC-H103", ["order-service", "database", "payment-api", "notification-service", "api-gateway"], ["user-service"]),
    ],
)
def test_blast_radius_propagates_through_dependency_graph(incident_id, expected_direct, expected_potential):
    result = assess_blast_radius(incident_id)

    assert result["directly_affected_services"]
    assert set(expected_direct).issubset(set(result["directly_affected_services"]))
    assert set(expected_potential).issubset(set(result["potentially_affected_services"]))
    for service in result["directly_affected_services"] + result["potentially_affected_services"]:
        assert any(item["service"] == service for item in result["evidence"])
        assert any("service" in item["reason"].lower() or "dependency" in item["reason"].lower() for item in result["evidence"] if item["service"] == service)

    assert result["user_impact"]
    assert result["severity_assessment"]


def test_blast_radius_marks_missing_incident_as_unavailable():
    result = assess_blast_radius("INC-DOES-NOT-EXIST")

    assert result["directly_affected_services"] == []
    assert result["potentially_affected_services"] == []
    assert result["unaffected_services"] == []
    assert "Information unavailable" in result["user_impact"]
    assert "Information unavailable" in result["severity_assessment"]
    assert result["evidence"]


def test_blast_radius_explains_why_each_service_is_affected():
    result = assess_blast_radius("INC-H104")

    assert result["directly_affected_services"]
    for item in result["evidence"]:
        assert item["reason"]
        assert "dependency" in item["reason"].lower() or "directly" in item["reason"].lower() or "similar" in item["reason"].lower() or "service" in item["reason"].lower()
