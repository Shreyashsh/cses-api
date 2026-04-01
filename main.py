import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from services import (
    SessionManager,
    ProblemFetcher,
    SolutionSubmitter,
    ProgressTracker,
)
from routers import auth_router, problems_router, submissions_router, progress_router

load_dotenv()


session_manager = None
problem_fetcher = None
solution_submitter = None
progress_tracker = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global session_manager, problem_fetcher, solution_submitter, progress_tracker

    session_manager = SessionManager(base_url=os.getenv("CSES_BASE_URL", "https://cses.fi"))
    problem_fetcher = ProblemFetcher(cache_dir=os.getenv("CACHE_DIR", "cache/problems"))
    solution_submitter = SolutionSubmitter()
    progress_tracker = ProgressTracker()

    auth_router.set_session_manager(session_manager)
    problems_router.set_services(session_manager, problem_fetcher)
    submissions_router.set_services(session_manager, solution_submitter, progress_tracker)
    progress_router.set_progress_tracker(progress_tracker)

    yield

    if session_manager:
        await session_manager.close_all()


app = FastAPI(
    title="CSES Problem Set API",
    description="API for fetching CSES problems, submitting solutions, and tracking progress",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(problems_router)
app.include_router(submissions_router)
app.include_router(progress_router)


@app.get("/")
async def root():
    return {"message": "CSES API", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
