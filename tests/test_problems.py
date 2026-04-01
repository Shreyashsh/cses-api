import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_list_categories(client):
    response = client.get("/problems")
    assert response.status_code in [200, 401]


def test_list_problems_in_category(client):
    response = client.get("/problems/introductory-problems")
    assert response.status_code in [200, 401]


def test_get_problem_details(client):
    response = client.get("/problems/introductory-problems/weird-algorithm")
    assert response.status_code in [200, 401]
