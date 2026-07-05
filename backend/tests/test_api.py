# pytest integration tests
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify root endpoint status and metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert "BuildFlow" in data["message"]


def test_health_endpoint():
    """Verify health check endpoint reports SQLite project counts."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["data_loaded"] is True
    assert data["project_count"] > 0


def test_analytics_overview():
    """Verify analytics overview returns projects statistics."""
    response = client.get("/api/analytics/overview")
    assert response.status_code == 200
    data = response.json()
    assert "total_projects" in data
    assert data["total_projects"] > 0
    assert "status_distribution" in data


def test_chat_api_fallback():
    """Verify posting to chat agent triggers correct response structures."""
    payload = {"message": "Show me a budget summary", "session_id": "test_api_session"}
    response = client.post("/api/chat/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "session_id" in data
    assert data["session_id"] == "test_api_session"
    assert "method" in data
