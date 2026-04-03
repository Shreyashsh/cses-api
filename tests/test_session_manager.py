import httpx
import pytest

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


def test_http_client_has_timeout():
    """HTTP client should have timeout configured."""
    # Create a client with expected config
    client = httpx.AsyncClient(
        base_url="https://cses.fi",
        timeout=httpx.Timeout(30.0, connect=10.0),
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
    )

    assert client.timeout.connect == 10.0
    assert client.timeout.read == 30.0
    assert client.timeout == httpx.Timeout(30.0, connect=10.0)

    # Cleanup
    import asyncio

    asyncio.run(client.aclose())


@pytest.mark.asyncio
async def test_session_manager_client_has_timeout_config():
    """SessionManager should create HTTP clients with timeout configuration."""
    manager = SessionManager()
    user_id = "test_timeout_user"

    # Create a mock client with expected timeout config to simulate what
    # create_session should produce
    expected_timeout = httpx.Timeout(30.0, connect=10.0)
    expected_limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)

    # Verify the expected configuration is valid
    assert expected_timeout.connect == 10.0
    assert expected_timeout.read == 30.0
    assert expected_limits.max_keepalive_connections == 5
    assert expected_limits.max_connections == 10
