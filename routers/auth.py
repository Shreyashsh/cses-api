from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Authentication"])

_session_manager = None


def set_session_manager(manager):
    global _session_manager
    _session_manager = manager


class SessionRequest(BaseModel):
    username: str
    password: str


class SessionResponse(BaseModel):
    user_id: str
    message: str


@router.post("/session", response_model=SessionResponse)
async def create_session(request: SessionRequest):
    """Initialize CSES session with credentials."""
    if not _session_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session manager not initialized",
        )

    user_id = request.username.lower().replace(" ", "_")

    success = await _session_manager.create_session(
        user_id=user_id,
        username=request.username,
        password=request.password,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid CSES credentials",
        )

    return SessionResponse(user_id=user_id, message="Session created successfully")


@router.delete("/session")
async def close_session(user_id: str):
    """Close CSES session."""
    if not _session_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session manager not initialized",
        )

    await _session_manager.close_session(user_id)
    return {"message": "Session closed"}
