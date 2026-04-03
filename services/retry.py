import asyncio
from functools import wraps
from typing import Awaitable, Callable, TypeVar

import httpx

T = TypeVar("T")

TRANSIENT_ERRORS = (httpx.RequestError,)


def retry_async(max_attempts: int = 3, backoff_factor: float = 2.0):
    """Retry decorator for async functions with exponential backoff."""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except TRANSIENT_ERRORS as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(backoff_factor**attempt)
                except Exception:
                    # Don't retry on non-transient errors
                    raise
            raise last_exception

        return wrapper

    return decorator
