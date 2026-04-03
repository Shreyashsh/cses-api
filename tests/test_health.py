from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_check_cache_status():
    """Health check should report cache status."""
    response = client.get("/health")
    assert response.status_code in [200, 503]
    data = response.json()
    assert "status" in data
    assert "checks" in data
    assert "cache" in data["checks"]


def test_health_check_structure():
    """Health check should return structured response."""
    response = client.get("/health")
    data = response.json()
    assert "status" in data
    assert data["status"] in ["healthy", "degraded", "unhealthy"]
