import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def mock_services():
    """Mock all service dependencies."""
    # Create mock session manager
    mock_session_manager = MagicMock()
    mock_client = MagicMock()
    mock_session_manager.get_session.return_value = mock_client

    # Create mock problem fetcher
    mock_problem_fetcher = MagicMock()
    mock_problem_fetcher.fetch_categories = AsyncMock()
    mock_problem_fetcher.fetch_category_problems = AsyncMock()
    mock_problem_fetcher.fetch_problem = AsyncMock()

    # Patch both services
    with patch("routers.problems._session_manager", mock_session_manager):
        with patch("routers.problems._problem_fetcher", mock_problem_fetcher):
            yield mock_session_manager, mock_problem_fetcher


@pytest.fixture
def client():
    """Create a test client."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.mark.asyncio
async def test_list_categories_success(client, mock_services):
    """Should return categories when fetch succeeds."""
    _, mock_problem_fetcher = mock_services
    # Match ProblemCategory model structure: name, slug, problem_count
    mock_categories = [
        {"name": "Introduction", "slug": "introductory-problems", "problem_count": 10},
        {"name": "Sorting", "slug": "sorting", "problem_count": 10},
    ]
    mock_problem_fetcher.fetch_categories.return_value = mock_categories

    response = client.get("/problems?user_id=test_user")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Introduction"


@pytest.mark.asyncio
async def test_list_categories_error(client, mock_services):
    """Should return 502 on error."""
    _, mock_problem_fetcher = mock_services
    mock_problem_fetcher.fetch_categories.side_effect = Exception("Network error")

    response = client.get("/problems?user_id=test_user")

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_list_problems_in_category_success(client, mock_services):
    """Should return problems when fetch succeeds."""
    _, mock_problem_fetcher = mock_services
    mock_problems = [
        {"id": "apio", "name": "APIO 2008"},
    ]
    mock_problem_fetcher.fetch_category_problems.return_value = mock_problems

    response = client.get("/problems/intro?user_id=test_user")

    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "intro"
    assert len(data["problems"]) == 1


@pytest.mark.asyncio
async def test_list_problems_in_category_error(client, mock_services):
    """Should return 502 on error."""
    _, mock_problem_fetcher = mock_services
    mock_problem_fetcher.fetch_category_problems.side_effect = Exception(
        "Network error"
    )

    response = client.get("/problems/intro?user_id=test_user")

    assert response.status_code == 502
