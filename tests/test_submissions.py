import pytest
from fastapi.testclient import TestClient
from io import BytesIO
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
        "/problems/weird-algorithm/submit",
        files=files,
        data=data,
    )
    assert response.status_code in [200, 400, 401]
