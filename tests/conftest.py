import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture
def client():
    """Synchronous test client for testing FastAPI endpoints."""
    with TestClient(app) as test_client:
        yield test_client
