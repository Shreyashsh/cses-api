from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_cors_allows_valid_origin():
    """CORS should allow configured origins."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type",
        }
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers

def test_cors_rejects_invalid_origin():
    """CORS should reject unconfigured origins."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "GET",
        }
    )
    # Should not include access-control-allow-origin for invalid origin
    assert "access-control-allow-origin" not in response.headers
