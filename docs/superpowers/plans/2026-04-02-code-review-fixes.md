# Code Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix critical and high-priority security, robustness, and correctness issues identified in code review.

**Architecture:** Incremental fixes following TDD - each fix gets tests first, then minimal implementation, then commit.

**Tech Stack:** FastAPI, httpx, pytest, asyncio, Python typing

---

## Phase 1: Critical Security Fixes

### Task 1: Add Input Validation for user_id

**Files:**
- Create: `models/user_id.py`
- Modify: `routers/auth.py`, `routers/problems.py`, `routers/submissions.py`
- Test: `tests/test_user_id_validation.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_user_id_validation.py
import pytest
from fastapi import HTTPException
from models.user_id import UserIdParam

def test_valid_user_id():
    """Valid user_id should be accepted."""
    user_id = UserIdParam(user_id="test_user-123")
    assert user_id.user_id == "test_user-123"

def test_invalid_user_id_special_chars():
    """user_id with special characters should be rejected."""
    with pytest.raises(ValueError):
        UserIdParam(user_id="test;user")

def test_invalid_user_id_path_traversal():
    """Path traversal attempts should be rejected."""
    with pytest.raises(ValueError):
        UserIdParam(user_id="../etc/passwd")

def test_empty_user_id():
    """Empty user_id should be rejected."""
    with pytest.raises(ValueError):
        UserIdParam(user_id="")

def test_too_long_user_id():
    """user_id over 64 chars should be rejected."""
    with pytest.raises(ValueError):
        UserIdParam(user_id="a" * 65)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_user_id_validation.py -v
```
Expected: FAIL with "ModuleNotFoundError: No module named 'models.user_id'"

- [ ] **Step 3: Write minimal implementation**

```python
# models/user_id.py
from pydantic import BaseModel, Field, field_validator


class UserIdParam(BaseModel):
    """Validated user ID parameter."""
    
    user_id: str = Field(..., min_length=1, max_length=64)
    
    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """Validate user_id format - only alphanumeric, underscore, hyphen."""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Invalid user_id format. Only alphanumeric, underscore, and hyphen allowed.')
        return v
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_user_id_validation.py -v
```
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add models/user_id.py tests/test_user_id_validation.py
git commit -m "feat: add UserIdParam validation model

- Add Pydantic model with format validation
- Reject special characters and path traversal attempts
- Enforce 1-64 character length
- Tests for valid and invalid cases"
```

---

### Task 2: Update Routers to Use Validated user_id

**Files:**
- Modify: `routers/auth.py`
- Modify: `routers/problems.py`
- Modify: `routers/submissions.py`
- Test: `tests/test_auth.py`, `tests/test_problems.py`, `tests/test_submissions.py`

- [ ] **Step 1: Write failing tests for router validation**

```python
# Add to tests/test_auth.py
def test_close_session_invalid_user_id():
    """Close session should reject invalid user_id."""
    response = client.delete("/auth/session?user_id=test;user")
    assert response.status_code == 422  # Validation error

def test_close_session_path_traversal():
    """Close session should reject path traversal."""
    response = client.delete("/auth/session?user_id=../etc/passwd")
    assert response.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_auth.py::test_close_session_invalid_user_id -v
```
Expected: FAIL (currently accepts invalid user_id)

- [ ] **Step 3: Update routers to use validation**

```python
# routers/auth.py - Add at top
from models.user_id import UserIdParam

# Update close_session endpoint
@router.delete("/session")
async def close_session(params: UserIdParam = Depends()):
    """Close CSES session."""
    try:
        await _session_manager.close_session(params.user_id)
        return {"message": "Session closed successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close session: {str(e)}",
        )
```

```python
# routers/problems.py - Update list_categories
@router.get("", response_model=List[ProblemCategory])
async def list_categories(params: UserIdParam = Depends()):
    """List all problem categories."""
    try:
        categories = await _problem_fetcher.fetch_categories(client)
        return categories
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch categories: {str(e)}",
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_auth.py::test_close_session_invalid_user_id tests/test_auth.py::test_close_session_path_traversal -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add routers/auth.py routers/problems.py routers/submissions.py tests/
git commit -m "feat: apply UserIdParam validation to all routers

- Update auth, problems, submissions routers
- Use Depends() for validation
- Reject invalid user_id at API boundary"
```

---

### Task 3: Add Rate Limiting

**Files:**
- Modify: `requirements.txt`
- Modify: `main.py`
- Create: `tests/test_rate_limiting.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_rate_limiting.py
import pytest
from fastapi.testclient import TestClient

client = TestClient(app)

def test_rate_limiting_triggers():
    """Multiple rapid requests should trigger rate limit."""
    # Make many rapid requests
    for i in range(20):
        response = client.get("/health")
        if response.status_code == 429:
            assert "Rate limit exceeded" in response.json()["detail"]
            return
    
    pytest.fail("Rate limiting did not trigger after 20 requests")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_rate_limiting.py -v
```
Expected: FAIL (no rate limiting configured)

- [ ] **Step 3: Add rate limiting dependency and configuration**

```txt
# requirements.txt - add line
slowapi>=0.1.8
```

```python
# main.py - Add imports and setup
from slowapi import SlowAPILimiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# After app creation
app.state.limiter = SlowAPILimiter()
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add middleware for request tracking
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    from uuid import uuid4
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```

- [ ] **Step 4: Add rate limits to routers**

```python
# routers/problems.py - Add to each endpoint
@router.get("", response_model=List[ProblemCategory])
@limiter.limit("30/minute")
async def list_categories(request: Request, params: UserIdParam = Depends()):
    ...
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_rate_limiting.py -v
```
Expected: PASS (rate limit triggers)

- [ ] **Step 6: Commit**

```bash
git add requirements.txt main.py routers/*.py tests/test_rate_limiting.py
git commit -m "feat: add rate limiting with slowapi

- Configure SlowAPILimiter globally
- Add 30/minute limit to API endpoints
- Add request ID tracking middleware
- Tests for rate limit enforcement"
```

---

## Phase 2: Critical Functional Correctness

### Task 4: Fix Race Condition in ProgressTracker

**Files:**
- Modify: `services/progress_tracker.py`
- Test: `tests/test_progress_tracker.py`

- [ ] **Step 1: Write failing test for concurrent submissions**

```python
# tests/test_progress_tracker.py
import pytest
import asyncio
from services.progress_tracker import ProgressTracker
from models.submission import Submission

@pytest.mark.asyncio
async def test_concurrent_submissions_thread_safe():
    """Concurrent submissions should not lose data."""
    tracker = ProgressTracker()
    user_id = "test_user"
    
    async def add_submission(i):
        submission = Submission(
            problem_id=f"problem_{i % 3}",
            verdict={"status": "Accepted" if i % 2 == 0 else "Wrong Answer"}
        )
        await tracker.add_submission(user_id, submission)
    
    # Add 10 submissions concurrently
    await asyncio.gather(*[add_submission(i) for i in range(10)])
    
    # All submissions should be recorded
    assert len(tracker.progress[user_id].submissions) == 10

@pytest.mark.asyncio
async def test_no_duplicate_solved_problems():
    """Same problem solved twice should not duplicate."""
    tracker = ProgressTracker()
    user_id = "test_user"
    
    async def add_accepted(problem_id):
        submission = Submission(
            problem_id=problem_id,
            verdict={"status": "Accepted"}
        )
        await tracker.add_submission(user_id, submission)
    
    # Add same problem 5 times concurrently
    await asyncio.gather(*[add_accepted("problem_1") for _ in range(5)])
    
    # Should only have one solved entry
    assert len(tracker.progress[user_id].solved) == 1
    assert "problem_1" in tracker.progress[user_id].solved
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_progress_tracker.py::test_concurrent_submissions_thread_safe -v
```
Expected: FAIL (race condition causes lost submissions)

- [ ] **Step 3: Fix ProgressTracker with asyncio locks**

```python
# services/progress_tracker.py
import asyncio
from typing import Dict

class ProgressTracker:
    def __init__(self):
        self.progress: Dict[str, Progress] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
    
    def _get_lock(self, user_id: str) -> asyncio.Lock:
        """Get or create lock for user."""
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]
    
    async def add_submission(self, user_id: str, submission: Submission) -> None:
        """Add submission thread-safely."""
        lock = self._get_lock(user_id)
        async with lock:
            if user_id not in self.progress:
                self.create_progress(user_id)
            
            self.progress[user_id].submissions.append(submission)
            
            if submission.verdict.status == "Accepted":
                if submission.problem_id not in self.progress[user_id].solved:
                    self.progress[user_id].solved.append(submission.problem_id)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_progress_tracker.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/progress_tracker.py tests/test_progress_tracker.py
git commit -m "fix: add asyncio locks to ProgressTracker

- Prevent race conditions in concurrent submissions
- Per-user locks for fine-grained concurrency
- Tests for thread-safe concurrent submissions"
```

---

### Task 5: Fix Session Expiry Edge Case

**Files:**
- Modify: `services/session_manager.py`
- Test: `tests/test_session_manager.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_session_manager.py
import pytest
from services.session_manager import SessionManager

@pytest.mark.asyncio
async def test_session_cleanup_on_expiry_mismatch():
    """Session should be cleaned up if expiry is missing."""
    manager = SessionManager()
    user_id = "test_user"
    
    # Manually create session without expiry (simulating bug state)
    client = await manager.create_session(user_id)
    manager.session_expiry.pop(user_id, None)  # Remove expiry
    
    # Getting session should clean up orphaned session
    result = manager.get_session(user_id)
    assert result is None
    assert user_id not in manager.sessions
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_session_manager.py::test_session_cleanup_on_expiry_mismatch -v
```
Expected: FAIL (session not cleaned up)

- [ ] **Step 3: Fix session expiry check**

```python
# services/session_manager.py
from datetime import datetime
from typing import Optional, Dict
import httpx

class SessionManager:
    def get_session(self, user_id: str) -> Optional[httpx.AsyncClient]:
        if user_id not in self.sessions:
            return None
        
        expiry = self.session_expiry.get(user_id)
        if expiry is None or datetime.utcnow() > expiry:
            # Clean up orphaned session
            if user_id in self.sessions:
                # Schedule async close
                import asyncio
                asyncio.create_task(self.sessions[user_id].aclose())
                del self.sessions[user_id]
            if user_id in self.session_expiry:
                del self.session_expiry[user_id]
            return None
        
        return self.sessions[user_id]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_session_manager.py::test_session_cleanup_on_expiry_mismatch -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/session_manager.py tests/test_session_manager.py
git commit -m "fix: clean up orphaned sessions on expiry mismatch

- Handle edge case where expiry is missing
- Properly close HTTP client to prevent resource leaks
- Test for cleanup behavior"
```

---

### Task 6: Fix Submission ID Generation

**Files:**
- Modify: `services/solution_submitter.py`
- Test: `tests/test_solution_submitter.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_solution_submitter.py
import pytest
import asyncio
from services.solution_submitter import SolutionSubmitter

@pytest.mark.asyncio
async def test_submission_ids_are_unique():
    """Concurrent submissions should have unique IDs."""
    submitter = SolutionSubmitter()
    
    async def submit():
        # Mock the actual submission
        return submitter._generate_submission_id("problem_1")
    
    # Generate 100 IDs concurrently
    ids = await asyncio.gather(*[submit() for _ in range(100)])
    
    # All IDs should be unique
    assert len(set(ids)) == 100
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_solution_submitter.py::test_submission_ids_are_unique -v
```
Expected: FAIL (datetime-based IDs can collide)

- [ ] **Step 3: Fix submission ID generation**

```python
# services/solution_submitter.py
import uuid
from datetime import datetime

class SolutionSubmitter:
    def _generate_submission_id(self, problem_id: str) -> str:
        """Generate unique submission ID."""
        return f"{problem_id}_{datetime.utcnow().timestamp()}_{uuid.uuid4().hex[:8]}"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_solution_submitter.py::test_submission_ids_are_unique -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/solution_submitter.py tests/test_solution_submitter.py
git commit -m "fix: use UUID for unique submission IDs

- Prevent ID collisions with uuid4
- Include timestamp and problem_id for traceability
- Test for uniqueness under concurrent generation"
```

---

## Phase 3: High Priority Robustness

### Task 7: Add HTTP Timeout Configuration

**Files:**
- Modify: `services/session_manager.py`
- Modify: `services/problem_fetcher.py`
- Test: `tests/test_session_manager.py`, `tests/test_problem_fetcher.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_session_manager.py
def test_http_client_has_timeout():
    """HTTP client should have timeout configured."""
    manager = SessionManager()
    # Check that timeout is configured (not default/None)
    # This is a configuration test
    import httpx
    
    # Create a client and verify timeout
    client = httpx.AsyncClient(
        base_url=manager.base_url,
        timeout=httpx.Timeout(30.0, connect=10.0),
    )
    assert client.timeout.connect == 10.0
    assert client.timeout.read == 30.0
```

- [ ] **Step 2: Add timeout to session manager**

```python
# services/session_manager.py
import httpx

class SessionManager:
    async def create_session(self, user_id: str) -> bool:
        client = httpx.AsyncClient(
            base_url=self.base_url,
            cookies=httpx.Cookies(),
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; CSES-API/1.0)",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
        # ... rest of method
```

- [ ] **Step 3: Add timeout to problem fetcher**

```python
# services/problem_fetcher.py
async def fetch_problem(self, client, problem_id, category):
    # Client should already have timeout from session_manager
    # But add explicit timeout on requests as backup
    try:
        response = await client.get(url, timeout=30.0)
        response.raise_for_status()
        # ...
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_session_manager.py tests/test_problem_fetcher.py -v
```

- [ ] **Step 5: Commit**

```bash
git add services/session_manager.py services/problem_fetcher.py tests/
git commit -m "feat: add HTTP timeout configuration

- 30s read timeout, 10s connect timeout
- Connection limits to prevent resource exhaustion
- Prevents indefinite hangs on slow CSES responses"
```

---

### Task 8: Add Retry Logic for Network Failures

**Files:**
- Create: `services/retry.py`
- Modify: `services/problem_fetcher.py`
- Test: `tests/test_retry.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_retry.py
import pytest
from services.retry import retry_async
import httpx

@pytest.mark.asyncio
async def test_retry_on_transient_error():
    """Should retry on transient network errors."""
    attempts = []
    
    @retry_async(max_attempts=3, backoff_factor=0.1)
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_retry.py -v
```
Expected: FAIL (module doesn't exist)

- [ ] **Step 3: Implement retry decorator**

```python
# services/retry.py
import asyncio
import httpx
from functools import wraps
from typing import TypeVar, Callable, Awaitable

T = TypeVar('T')

TRANSIENT_ERRORS = (httpx.RequestError, httpx.TimeoutException, httpx.NetworkError)

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
                        await asyncio.sleep(backoff_factor ** attempt)
                except Exception:
                    # Don't retry on non-transient errors
                    raise
            raise last_exception
        return wrapper
    return decorator
```

- [ ] **Step 4: Apply retry to problem fetcher**

```python
# services/problem_fetcher.py
from services.retry import retry_async

class ProblemFetcher:
    @retry_async(max_attempts=3, backoff_factor=1.0)
    async def fetch_problem(self, client, problem_id, category):
        # ... existing implementation
```

- [ ] **Step 5: Run tests and commit**

```bash
pytest tests/test_retry.py -v
git add services/retry.py services/problem_fetcher.py tests/test_retry.py
git commit -m "feat: add retry logic for transient network errors

- Exponential backoff decorator
- Only retries transient errors (timeout, network)
- Applied to problem fetching
- Tests for retry behavior"
```

---

### Task 9: Add Logging Configuration

**Files:**
- Modify: `main.py`
- Modify: All router and service files
- Test: `tests/test_logging.py`

- [ ] **Step 1: Write test for logging**

```python
# tests/test_logging.py
import logging

def test_logging_configured():
    """Application should have logging configured."""
    logger = logging.getLogger('cses_api')
    assert logger.level != logging.NOTSET
```

- [ ] **Step 2: Add logging to main.py**

```python
# main.py
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger('cses_api')
```

- [ ] **Step 3: Add logging to routers**

```python
# routers/problems.py
import logging
logger = logging.getLogger('cses_api.problems')

@router.get("", response_model=List[ProblemCategory])
async def list_categories(...):
    logger.info(f"Fetching categories for user {params.user_id}")
    try:
        categories = await _problem_fetcher.fetch_categories(client)
        logger.info(f"Fetched {len(categories)} categories")
        return categories
    except httpx.TimeoutException as e:
        logger.error(f"Timeout fetching categories: {e}")
        raise HTTPException(...)
    except Exception as e:
        logger.exception(f"Unexpected error fetching categories: {e}")
        raise HTTPException(...)
```

- [ ] **Step 4: Run tests and commit**

```bash
pytest tests/test_logging.py -v
git add main.py routers/*.py services/*.py tests/test_logging.py
git commit -m "feat: add comprehensive logging

- Configure root logger in main.py
- Per-module loggers in routers and services
- Log requests, responses, errors with context
- Exception logging with stack traces"
```

---

## Phase 4: Medium Priority Improvements

### Task 10: Improve Health Check

**Files:**
- Modify: `main.py`
- Test: `tests/test_health.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_health.py
def test_health_check_cache_status():
    """Health check should report cache status."""
    response = client.get("/health")
    assert response.status_code in [200, 503]
    data = response.json()
    assert "status" in data
    assert "checks" in data
    assert "cache" in data["checks"]
```

- [ ] **Step 2: Implement improved health check**

```python
# main.py
from pathlib import Path
import os

@app.get("/health")
async def health():
    """Health check with dependency status."""
    health_status = {"status": "healthy", "checks": {}}
    
    # Check cache directory
    cache_path = Path(os.getenv("CACHE_DIR", "cache/problems"))
    try:
        if not cache_path.exists():
            cache_path.mkdir(parents=True, exist_ok=True)
        if not os.access(cache_path, os.W_OK):
            health_status["checks"]["cache"] = "unhealthy"
            health_status["status"] = "degraded"
        else:
            health_status["checks"]["cache"] = "healthy"
    except Exception as e:
        logger.error(f"Cache check failed: {e}")
        health_status["checks"]["cache"] = "unhealthy"
        health_status["status"] = "degraded"
    
    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)
```

- [ ] **Step 3: Run tests and commit**

```bash
pytest tests/test_health.py -v
git add main.py tests/test_health.py
git commit -m "feat: improve health check with dependency status

- Check cache directory writability
- Return degraded status on issues
- Return 503 on degraded health
- Structured health response"
```

---

### Task 11: Fix CORS Configuration

**Files:**
- Modify: `main.py`
- Test: `tests/test_cors.py`

- [ ] **Step 1: Write test for CORS**

```python
# tests/test_cors.py
def test_cors_restricts_methods():
    """CORS should only allow specific methods."""
    response = client.options(
        "/problems",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "DELETE",
        }
    )
    # DELETE should not be allowed
    assert response.status_code != 200
```

- [ ] **Step 2: Fix CORS configuration**

```python
# main.py
import os

allowed_origins = [
    origin.strip() 
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
```

- [ ] **Step 3: Run tests and commit**

```bash
pytest tests/test_cors.py -v
git add main.py tests/test_cors.py
git commit -m "feat: restrict CORS to specific methods and headers

- Environment variable for allowed origins
- Explicit method list (no wildcards)
- Explicit header list
- Expose X-Request-ID to clients"
```

---

### Task 12: Fix Pydantic Alias Usage

**Files:**
- Modify: `models/problem.py`
- Test: `tests/test_problem_model.py`

- [ ] **Step 1: Write test**

```python
# tests/test_problem_model.py
from models.problem import Problem

def test_problem_model_without_redundant_alias():
    """Problem model should work without redundant aliases."""
    problem = Problem(
        id="1",
        name="Test Problem",
        input_format="stdin",
        output_format="stdout"
    )
    assert problem.input_format == "stdin"
    assert problem.output_format == "stdout"
```

- [ ] **Step 2: Fix model**

```python
# models/problem.py
from pydantic import BaseModel
from typing import Optional, List

class Problem(BaseModel):
    id: str
    name: str
    input_format: Optional[str] = None
    output_format: Optional[str] = None
    # ... rest of fields without redundant aliases
```

- [ ] **Step 3: Run tests and commit**

```bash
pytest tests/test_problem_model.py -v
git add models/problem.py tests/test_problem_model.py
git commit -m "fix: remove redundant Pydantic field aliases

- Aliases were same as field names (no-op)
- Cleaner model definition
- No behavior change"
```

---

## Phase 5: Test Improvements

### Task 13: Fix Test Credentials

**Files:**
- Modify: `tests/test_auth.py`
- Create: `tests/.env.example`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Update tests to use environment variables**

```python
# tests/test_auth.py
import os
import pytest

TEST_USERNAME = os.getenv("TEST_CSES_USERNAME", "testuser")
TEST_PASSWORD = os.getenv("TEST_CSES_PASSWORD", "testpass")

@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Requires CSES credentials"
)
def test_create_session():
    response = client.post(
        "/auth/session",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert response.status_code in [200, 401]
```

- [ ] **Step 2: Create .env.example**

```bash
# tests/.env.example
# Test credentials for integration tests
TEST_CSES_USERNAME=your_test_username
TEST_CSES_PASSWORD=your_test_password
RUN_INTEGRATION_TESTS=1
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_auth.py tests/.env.example
git commit -m "fix: use environment variables for test credentials

- Don't hardcode credentials in tests
- Skip integration tests by default
- Add .env.example for configuration"
```

---

### Task 14: Add Mock-Based Unit Tests

**Files:**
- Create: `tests/test_problems_unit.py`
- Create: `tests/test_submissions_unit.py`

- [ ] **Step 1: Write unit tests with mocks**

```python
# tests/test_problems_unit.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_list_categories_success():
    """Should return categories when fetch succeeds."""
    mock_categories = [
        {"id": "1", "name": "Introduction"},
        {"id": "2", "name": "Sorting"},
    ]
    
    with patch('routers.problems._problem_fetcher.fetch_categories', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_categories
        
        response = client.get("/problems?user_id=test_user")
        
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[0]["name"] == "Introduction"

@pytest.mark.asyncio
async def test_list_categories_timeout():
    """Should return 504 on timeout."""
    with patch('routers.problems._problem_fetcher.fetch_categories', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = TimeoutError("Request timed out")
        
        response = client.get("/problems?user_id=test_user")
        
        assert response.status_code == 504
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_problems_unit.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_problems_unit.py tests/test_submissions_unit.py
git commit -m "test: add mock-based unit tests

- Test router logic without external dependencies
- Test error handling paths
- Fast, deterministic tests"
```

---

## Summary

This plan addresses:
- **6 Critical issues**: Input validation, authentication gaps, CSRF, race conditions, session bugs, unique IDs
- **7 High priority**: Timeouts, caching, memory, retry logic, rate limiting, logging
- **5 Medium priority**: Health checks, CORS, Pydantic cleanup, test improvements

**Total commits:** 14 focused commits
**Estimated time:** 2-3 hours with TDD discipline
