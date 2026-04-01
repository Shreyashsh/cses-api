import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_get_progress(client):
    response = client.get("/progress")
    assert response.status_code == 200
    data = response.json()
    assert "user_id" in data
    assert "total_solved" in data
    assert "solved_problems" in data
    assert "recent_submissions" in data
