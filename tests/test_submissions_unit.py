from datetime import datetime
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def mock_services():
    """Mock all service dependencies."""
    # Create mock session manager
    mock_session_manager = MagicMock()
    mock_client = MagicMock()
    mock_session_manager.get_session.return_value = mock_client

    # Create mock solution submitter
    mock_solution_submitter = MagicMock()
    mock_solution_submitter.submit_file = AsyncMock()

    # Create mock progress tracker
    mock_progress_tracker = MagicMock()
    mock_progress_tracker.add_submission = AsyncMock()

    # Patch all services
    with patch("routers.submissions._session_manager", mock_session_manager):
        with patch("routers.submissions._solution_submitter", mock_solution_submitter):
            with patch("routers.submissions._progress_tracker", mock_progress_tracker):
                yield mock_session_manager, mock_solution_submitter, mock_progress_tracker


@pytest.fixture
def client():
    """Create a test client."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.mark.asyncio
async def test_submit_solution_success(client, mock_services):
    """Should accept submission when submit succeeds."""
    _, mock_solution_submitter, _ = mock_services
    # Match Submission model structure
    mock_submission = MagicMock()
    mock_submission.id = "12345"
    mock_submission.problem_id = "apio"
    mock_submission.language = "C++"
    mock_submission.file_path = None
    mock_submission.verdict = {"status": "Judging"}
    mock_submission.submitted_at = datetime.utcnow()
    mock_solution_submitter.submit_file.return_value = mock_submission

    files = {"file": ("solution.cpp", BytesIO(b"// solution"), "text/x-c++src")}

    response = client.post("/problems/1234/submit?user_id=test_user", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "12345"


@pytest.mark.asyncio
async def test_submit_solution_network_error(client, mock_services):
    """Should return 502 on network error."""
    _, mock_solution_submitter, _ = mock_services
    mock_solution_submitter.submit_file.side_effect = Exception("Network error")

    files = {"file": ("solution.cpp", BytesIO(b"// solution"), "text/x-c++src")}

    response = client.post("/problems/1234/submit?user_id=test_user", files=files)

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_submit_solution_no_file(client, mock_services):
    """Should return 400 when no file provided."""
    response = client.post(
        "/problems/1234/submit?user_id=test_user", data={"language": "python3"}
    )

    assert response.status_code == 400
