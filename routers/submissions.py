from typing import Optional

from fastapi import (APIRouter, Depends, File, Form, HTTPException, UploadFile,
                     status)

from models.submission import Submission

router = APIRouter(prefix="/problems", tags=["Submissions"])

_session_manager = None
_solution_submitter = None
_progress_tracker = None


def set_services(manager, submitter, tracker):
    global _session_manager, _solution_submitter, _progress_tracker
    _session_manager = manager
    _solution_submitter = submitter
    _progress_tracker = tracker


def get_client_and_user(user_id: str):
    if not _session_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session manager not initialized",
        )

    client = _session_manager.get_session(user_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please re-authenticate.",
        )

    return client


@router.post("/{problem_id}/submit", response_model=Submission)
async def submit_solution(
    problem_id: str,
    language: str = Form("python3"),
    file: Optional[UploadFile] = File(None),
    client=Depends(lambda: get_client_and_user("default")),
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

        _progress_tracker.add_submission("default", submission)

        return submission
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Submission failed: {str(e)}",
        )
