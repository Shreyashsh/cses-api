import logging
import os
import re
from pathlib import Path as FilePath
from typing import Optional

import httpx
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Request,
    UploadFile,
    status,
)

from limiter import limiter
from models.submission import Submission
from models.user_id import UserIdParam, validate_user_id

logger = logging.getLogger("cses_api.submissions")

router = APIRouter(prefix="/problems", tags=["Submissions"])

MAX_FILE_SIZE = 1024 * 1024  # 1MB
ALLOWED_EXTENSIONS = {
    ".py",
    ".cpp",
    ".c",
    ".java",
    ".js",
    ".rs",
    ".go",
    ".rb",
    ".cs",
    ".pas",
}

# CSES problem IDs are numeric
PROBLEM_ID_PATTERN = re.compile(r"^\d{1,10}$")


def get_session_manager(request: Request):
    """Get session manager from app state."""
    return request.app.state.session_manager


def get_solution_submitter(request: Request):
    """Get solution submitter from app state."""
    return request.app.state.solution_submitter


def get_progress_tracker(request: Request):
    """Get progress tracker from app state."""
    return request.app.state.progress_tracker


def get_client_and_user(
    params: UserIdParam = Depends(validate_user_id),
    session_manager=Depends(get_session_manager),
) -> httpx.AsyncClient:
    if not session_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session manager not initialized",
        )

    client = session_manager.get_session(params.user_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please re-authenticate.",
        )

    return client


@router.post("/{problem_id}/submit", response_model=Submission)
@limiter.limit("30/minute")
async def submit_solution(
    request: Request,
    problem_id: str,
    params: UserIdParam = Depends(validate_user_id),
    language: str = Form("python3"),
    file: Optional[UploadFile] = File(None),
    client=Depends(get_client_and_user),
    solution_submitter=Depends(get_solution_submitter),
    progress_tracker=Depends(get_progress_tracker),
):
    """Submit solution file to CSES."""
    if not PROBLEM_ID_PATTERN.match(problem_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid problem_id format. Only numeric IDs are allowed.",
        )

    logger.info(f"Submitting solution for problem: {problem_id}, language: {language}")
    if not file:
        logger.warning(f"No file provided for problem: {problem_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided. Upload a code file.",
        )

    try:
        # Read only up to MAX_FILE_SIZE + 1 bytes to detect oversized files
        file_content = await file.read(MAX_FILE_SIZE + 1)
        filename = file.filename or "solution.py"

        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // 1024}KB.",
            )

        ext = FilePath(filename).suffix.lower()
        if ext and ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        submission = await solution_submitter.submit_file(
            client=client,
            problem_id=problem_id,
            file_content=file_content,
            filename=filename,
            language=language,
            progress_tracker=progress_tracker,
            user_id=params.user_id,
        )

        # Note: add_submission is now handled by the background polling task
        logger.info(f"Submission queued for problem {problem_id}: {submission.id}")

        return submission
    except Exception as e:
        logger.exception(f"Submission failed for problem {problem_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Submission failed. Please try again later.",
        )
