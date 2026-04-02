from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from limiter import limiter
from models.submission import Submission
from models.user_id import UserIdParam, validate_user_id

router = APIRouter(prefix="/problems", tags=["Submissions"])

_session_manager = None
_solution_submitter = None
_progress_tracker = None


def set_services(manager, submitter, tracker):
    global _session_manager, _solution_submitter, _progress_tracker
    _session_manager = manager
    _solution_submitter = submitter
    _progress_tracker = tracker


def get_client_and_user(params: UserIdParam = Depends(validate_user_id)):
    if not _session_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session manager not initialized",
        )

    client = _session_manager.get_session(params.user_id)
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
):
    """Submit solution file to CSES."""
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided. Upload a code file.",
        )

    try:
        file_content = await file.read()
        filename = file.filename or "solution.py"

        submission = await _solution_submitter.submit_file(
            client=client,
            problem_id=problem_id,
            file_content=file_content,
            filename=filename,
            language=language,
        )

        _progress_tracker.add_submission(params.user_id, submission)

        return submission
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Submission failed: {str(e)}",
        )
