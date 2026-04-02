import pytest
import httpx
from services.session_manager import SessionManager


@pytest.mark.asyncio
async def test_session_cleanup_on_expiry_mismatch():
    """Session should be cleaned up if expiry is missing."""
    manager = SessionManager()
    user_id = "test_user"
    
    # Create a mock session directly (simulating a session without going through login)
    manager.sessions[user_id] = httpx.AsyncClient(base_url="https://cses.fi")
    manager.session_expiry[user_id] = None  # Simulate missing expiry
    
    # Getting session should clean up orphaned session
    result = manager.get_session(user_id)
    assert result is None
    assert user_id not in manager.sessions
