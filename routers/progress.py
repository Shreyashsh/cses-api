import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from limiter import limiter
from models.progress import UserProgress
from models.submission import Submission
from models.user_id import UserIdParam, validate_user_id

logger = logging.getLogger("cses_api.progress")

router = APIRouter(prefix="/progress", tags=["Progress"])

_progress_tracker = None

# Submission IDs follow pattern: {problem_id}_{timestamp}_{uuid_hex}
SUBMISSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")


def set_progress_tracker(tracker):
    global _progress_tracker
    _progress_tracker = tracker


@router.get("", response_model=UserProgress)
@limiter.limit("30/minute")
async def get_progress(
    request: Request, params: UserIdParam = Depends(validate_user_id)
):
    """Get user progress."""
    logger.info(f"Fetching progress for user: {params.user_id}")
    progress = _progress_tracker.get_user_progress(params.user_id)
    if not progress:
        logger.info(
            f"No progress found for user: {params.user_id}, returning empty progress"
        )
        progress = UserProgress(
            user_id=params.user_id,
            total_solved=0,
            solved_problems=[],
            recent_submissions=[],
            last_updated=datetime.now(timezone.utc),
        )
    return progress


@router.get("/submissions/{submission_id}", response_model=Submission)
@limiter.limit("30/minute")
async def get_submission(
    request: Request,
    submission_id: str,
    params: UserIdParam = Depends(validate_user_id),
):
    """Get specific submission by ID."""
    if not SUBMISSION_ID_PATTERN.match(submission_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid submission_id format.",
        )

    logger.info(f"Fetching submission {submission_id} for user: {params.user_id}")
    submission = _progress_tracker.get_submission_by_id(params.user_id, submission_id)
    if not submission:
        logger.warning(
            f"Submission {submission_id} not found for user: {params.user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found",
        )
    return submission
