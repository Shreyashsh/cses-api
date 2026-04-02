from typing import List

from fastapi import APIRouter, HTTPException, Request, status

from limiter import limiter
from models.progress import UserProgress
from models.submission import Submission

router = APIRouter(prefix="/progress", tags=["Progress"])

_progress_tracker = None


def set_progress_tracker(tracker):
    global _progress_tracker
    _progress_tracker = tracker


@router.get("", response_model=UserProgress)
@limiter.limit("30/minute")
async def get_progress(request: Request, user_id: str = "default"):
    """Get user progress."""
    progress = _progress_tracker.get_user_progress(user_id)
    if not progress:
        progress = UserProgress(
            user_id=user_id,
            total_solved=0,
            solved_problems=[],
            recent_submissions=[],
        )
    return progress


@router.get("/submissions/{submission_id}", response_model=Submission)
@limiter.limit("30/minute")
async def get_submission(request: Request, submission_id: str, user_id: str = "default"):
    """Get specific submission by ID."""
    submission = _progress_tracker.get_submission_by_id(user_id, submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found",
        )
    return submission
