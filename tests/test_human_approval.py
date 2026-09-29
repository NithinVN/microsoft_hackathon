import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.main import app


def test_human_approval_requires_operator_token_outside_development(client: TestClient):
    payload = {
        "engineer": "eng_amy",
        "action": "approve",
        "original_recommendation": "Increase database connection pool from 50 to 100",
        "reason": "Reviewed the runbook and blast radius.",
    }

    with patch.object(settings, "APP_ENV", "staging"), patch.object(settings, "OPERATOR_API_TOKEN", "operator-token-for-tests"):
        unauthorized = client.post("/api/v1/incidents/1/approval", json=payload)
        authorized = client.post(
            "/api/v1/incidents/1/approval",
            json=payload,
            headers={"Authorization": "Bearer operator-token-for-tests"},
        )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 404


def test_human_approval_does_not_claim_unverified_recovery(client: TestClient):
    incident_id = f"INC-APP-{uuid.uuid4().hex[:6]}"

    create = client.post(
        "/api/v1/incidents",
        json={
            "incident_id": incident_id,
            "title": "Database connection starvation",
            "description": "Payments failing due to saturated DB pool",
            "severity": "SEV-1",
            "status": "DETECTED",
            "source": "simulator",
            "affected_service": "database",
            "symptoms": ["DB connections 98%", "Error rate 37%"],
            "metadata": {"env": "prod"},
        },
    )
    assert create.status_code == 201, create.text
    incident_id_db = create.json()["id"]

    response = client.post(
        f"/api/v1/incidents/{incident_id_db}/approval",
        json={
            "engineer": "eng_amy",
            "action": "approve",
            "original_recommendation": "Increase database connection pool from 50 to 100",
            "reason": "Historical evidence and runbook both support increasing the pool safely.",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["engineer"] == "eng_amy"
    assert body["action"] == "approve"
    assert body["original_recommendation"] == "Increase database connection pool from 50 to 100"
    assert body["execution_result"]["mode"] == "simulated"
    assert body["execution_result"]["recovered"] is False
    assert body["execution_result"]["status"] == "APPROVED_PENDING_SIMULATION"
    assert "No live command execution" in body["execution_result"]["details"]


def test_human_approval_records_modified_recommendation_without_shell_execution(client: TestClient):
    incident_id = f"INC-APP-{uuid.uuid4().hex[:6]}"

    create = client.post(
        "/api/v1/incidents",
        json={
            "incident_id": incident_id,
            "title": "Queue backlog issue",
            "description": "Retry loop saturating workers",
            "severity": "SEV-2",
            "status": "DETECTED",
            "source": "simulator",
            "affected_service": "notification-service",
            "symptoms": ["Queue backlog elevated", "Error rate peaked at 23%"],
            "metadata": {"env": "prod"},
        },
    )
    assert create.status_code == 201, create.text
    incident_id_db = create.json()["id"]

    response = client.post(
        f"/api/v1/incidents/{incident_id_db}/approval",
        json={
            "engineer": "eng_riley",
            "action": "modify",
            "original_recommendation": "Increase worker concurrency to 150",
            "modified_recommendation": "Increase worker concurrency to 110 and enable retry backoff",
            "reason": "We need bounded growth to avoid retry storms.",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["action"] == "modify"
    assert body["modified_recommendation"] == "Increase worker concurrency to 110 and enable retry backoff"
    assert body["execution_result"]["mode"] == "simulated"
    assert body["execution_result"]["recovered"] is False
    assert "shell" not in body["execution_result"]["details"].lower()
