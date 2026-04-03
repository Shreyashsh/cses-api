import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_rate_limiting_triggers():
    """Multiple rapid requests should trigger rate limit."""
    # Make many rapid requests to health endpoint
    rate_limited = False
    for i in range(50):
        response = client.get("/health")
        if response.status_code == 429:
            rate_limited = True
            assert "Rate limit exceeded" in response.json().get("error", "")
            break

    assert rate_limited, "Rate limiting did not trigger after 50 requests"
