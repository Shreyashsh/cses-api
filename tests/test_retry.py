import httpx
import pytest

from services.retry import retry_async


@pytest.mark.asyncio
async def test_retry_on_transient_error():
    """Should retry on transient network errors."""
    attempts = []

    @retry_async(max_attempts=3, backoff_factor=0.01)
    async def flaky_operation():
        attempts.append(1)
        if len(attempts) < 3:
            raise httpx.RequestError("Network error")
        return "success"

    result = await flaky_operation()
    assert result == "success"
    assert len(attempts) == 3


@pytest.mark.asyncio
async def test_no_retry_on_permanent_error():
    """Should not retry on permanent errors."""
    attempts = []

    @retry_async(max_attempts=3)
    async def failing_operation():
        attempts.append(1)
        raise ValueError("Invalid input")

    with pytest.raises(ValueError):
        await failing_operation()

    assert len(attempts) == 1  # No retries


@pytest.mark.asyncio
async def test_exhausts_retries():
    """Should raise error after max attempts."""
    attempts = []

    @retry_async(max_attempts=3, backoff_factor=0.01)
    async def always_fails():
        attempts.append(1)
        raise httpx.TimeoutException("Timeout")

    with pytest.raises(httpx.TimeoutException):
        await always_fails()

    assert len(attempts) == 3  # Tried 3 times
