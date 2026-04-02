from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_submit_solution_file(client):
    code = b'print("Hello, World!")'
    files = {"file": ("solution.py", BytesIO(code), "text/plain")}
    data = {"language": "python3"}

    response = client.post(
        "/problems/weird-algorithm/submit?user_id=testuser",
        files=files,
        data=data,
    )
    assert response.status_code in [200, 400, 401]


def test_submit_no_file(client):
    data = {"language": "python3"}
    response = client.post(
        "/problems/weird-algorithm/submit?user_id=testuser",
        data=data,
    )
    assert response.status_code in [400, 401]


def test_submit_invalid_user_id(client):
    code = b'print("Hello, World!")'
    files = {"file": ("solution.py", BytesIO(code), "text/plain")}
    data = {"language": "python3"}
    response = client.post(
        "/problems/weird-algorithm/submit?user_id=test;user",
        files=files,
        data=data,
    )
    assert response.status_code == 422
