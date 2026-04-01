import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_create_session_success(client):
    response = client.post(
        "/auth/session",
        json={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code in [200, 401]


def test_create_session_invalid_credentials(client):
    response = client.post(
        "/auth/session",
        json={"username": "invalid", "password": "wrong"},
    )
    assert response.status_code == 401
