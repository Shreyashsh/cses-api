import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from limiter import limiter
from routers import auth, problems, progress, submissions
from services import ProblemFetcher, ProgressTracker, SessionManager, SolutionSubmitter

# Load environment variables from project-specific config file
load_dotenv("cses.properties")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("cses_api")
logger.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_manager = SessionManager(
        base_url=os.getenv("CSES_BASE_URL", "https://cses.fi")
    )
    problem_fetcher = ProblemFetcher(cache_dir=os.getenv("CACHE_DIR", "cache/problems"))
    solution_submitter = SolutionSubmitter()
    progress_tracker = ProgressTracker()

    # Store services in app.state for dependency injection
    app.state.session_manager = session_manager
    app.state.problem_fetcher = problem_fetcher
    app.state.solution_submitter = solution_submitter
    app.state.progress_tracker = progress_tracker

    # Configure trusted proxies for X-Forwarded-For (empty = no proxy trusted)
    proxies = os.getenv("TRUSTED_PROXIES", "")
    app.state.trusted_proxies = {
        p.strip() for p in proxies.split(",") if p.strip()
    } if proxies else set()

    yield

    if session_manager:
        await session_manager.close_all()


app = FastAPI(
    title="CSES Problem Set API",
    description="API for fetching CSES problems, submitting solutions, and tracking progress",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Parse allowed origins from environment variable
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]

# Reject wildcard origins when credentials are allowed (security risk)
if "*" in allowed_origins:
    raise ValueError(
        "Wildcard '*' is not allowed in ALLOWED_ORIGINS with allow_credentials=True. "
        "Specify exact origins instead."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)

app.include_router(auth.router)
app.include_router(problems.router)
app.include_router(submissions.router)
app.include_router(progress.router)


@app.get("/")
@limiter.limit("30/minute")
async def root(request: Request):
    return {"message": "CSES API", "docs": "/docs"}


@app.get("/health")
@limiter.limit("30/minute")
async def health(request: Request):
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
