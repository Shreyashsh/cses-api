import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, problems, progress, submissions
from services import (ProblemFetcher, ProgressTracker, SessionManager,
                      SolutionSubmitter)

load_dotenv()


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
    problems.set_services(session_manager, problem_fetcher)
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
async def root():
    return {"message": "CSES API", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
