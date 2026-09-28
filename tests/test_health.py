from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient):
    """Test root endpoint provides service metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "IncidentMind"
    assert data["version"] == "1.0.0"
    assert data["api_v1_prefix"] == "/api/v1"
    assert data["health"] == "/api/v1/health"


def test_api_v1_health_endpoint(client: TestClient):
    """Test /api/v1/health endpoint returns healthy status and service flags."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "IncidentMind"
    assert "timestamp" in data
    assert "services" in data
    assert data["services"]["api"] == "operational"
    assert "model_configured" in data["services"]


def test_root_health_alias(client: TestClient):
    """Test convenience /health alias matches /api/v1/health."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_liveness_and_readiness(client: TestClient):
    """Test /api/v1/health/live and /api/v1/health/ready probes."""
    live_resp = client.get("/api/v1/health/live")
    assert live_resp.status_code == 200
    assert live_resp.json() == {"status": "alive"}

    ready_resp = client.get("/api/v1/health/ready")
    assert ready_resp.status_code == 200
    assert ready_resp.json() == {"status": "ready"}


def test_cors_preflight(client: TestClient):
    """Test CORS headers on preflight requests."""
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
