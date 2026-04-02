import logging
import os
import sys
from contextlib import asynccontextmanager
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from limiter import limiter
from routers import auth, problems, progress, submissions
from services import ProblemFetcher, ProgressTracker, SessionManager, SolutionSubmitter

load_dotenv()

# Configure logging after imports, before app creation
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger('cses_api')
logger.setLevel(logging.INFO)
# Add handler directly to cses_api logger for explicit configuration
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)


session_manager = None
problem_fetcher = None
solution_submitter = None
progress_tracker = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global session_manager, problem_fetcher, solution_submitter, progress_tracker

    session_manager = SessionManager(
        base_url=os.getenv("CSES_BASE_URL", "https://cses.fi")
    )
    problem_fetcher = ProblemFetcher(cache_dir=os.getenv("CACHE_DIR", "cache/problems"))
    solution_submitter = SolutionSubmitter()
    progress_tracker = ProgressTracker()

    auth.set_session_manager(session_manager)
    problems.set_services(session_manager, problem_fetcher, limiter)
    submissions.set_services(session_manager, solution_submitter, progress_tracker)
    progress.set_progress_tracker(progress_tracker)

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


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    return {"status": "healthy"}


@app.get("/debug/sessions")
@limiter.limit("30/minute")
async def debug_sessions(request: Request):
    """Debug endpoint to see active sessions."""
    if session_manager:
        return {
            "active_sessions": list(session_manager.sessions.keys()),
            "session_expiry": {
                k: v.isoformat() for k, v in session_manager.session_expiry.items()
            },
        }
    return {"error": "Session manager not initialized"}
