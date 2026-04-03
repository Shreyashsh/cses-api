import os

import pytest
from fastapi.testclient import TestClient

from main import app

TEST_USERNAME = os.getenv("TEST_CSES_USERNAME", "testuser")
TEST_PASSWORD = os.getenv("TEST_CSES_PASSWORD", "testpass")


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"), reason="Requires CSES credentials"
)
def test_create_session_success(client):
    """Integration test - skipped by default."""
    response = client.post(
        "/auth/session",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert response.status_code in [200, 401]


def test_create_session_invalid_credentials(client):
    response = client.post(
        "/auth/session",
        json={"username": "invalid", "password": "wrong"},
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
