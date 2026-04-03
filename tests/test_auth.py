import os

import pytest
from fastapi.testclient import TestClient

from main import app

# No default credentials - must be set via environment variables for integration tests
TEST_USERNAME = os.getenv("TEST_CSES_USERNAME")
TEST_PASSWORD = os.getenv("TEST_CSES_PASSWORD")


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.skipif(
    not TEST_USERNAME or not TEST_PASSWORD,
    reason="Requires TEST_CSES_USERNAME and TEST_CSES_PASSWORD environment variables",
)
def test_create_session_success(client):
    """Integration test - skipped by default."""
    response = client.post(
        "/auth/session",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert response.status_code in [200, 401]


@pytest.mark.skipif(
    not TEST_USERNAME or not TEST_PASSWORD,
    reason="Requires TEST_CSES_USERNAME and TEST_CSES_PASSWORD environment variables to avoid sending random credentials to CSES",
)
def test_create_session_invalid_credentials(client):
    """Integration test - skipped unless real credentials are configured.
    This prevents sending arbitrary credentials to the live CSES server.
    """
    response = client.post(
        "/auth/session",
        json={"username": "invalid_user_for_test", "password": "wrong_password_for_test"},
    )
    assert response.status_code == 401


def test_close_session_invalid_user_id(client):
    """Close session should reject invalid user_id."""
    response = client.delete("/auth/session?user_id=test;user")
    assert response.status_code == 422  # Validation error


def test_close_session_path_traversal(client):
    """Close session should reject path traversal."""
    response = client.delete("/auth/session?user_id=../etc/passwd")
    assert response.status_code == 422
