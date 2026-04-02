import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from limiter import limiter
from models.user_id import UserIdParam, validate_user_id

logger = logging.getLogger('cses_api.auth')

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
@limiter.limit("30/minute")
async def create_session(request: Request, request_data: SessionRequest):
    """Initialize CSES session with credentials."""
    logger.info(f"Creating session for user: {request_data.username}")
    if not _session_manager:
        logger.error("Session manager not initialized")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session manager not initialized",
        )

    user_id = request_data.username.lower().replace(" ", "_")

    success = await _session_manager.create_session(
        user_id=user_id,
        username=request_data.username,
        password=request_data.password,
    )

    if not success:
        logger.warning(f"Failed to create session for user: {request_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid CSES credentials",
        )

    logger.info(f"Session created successfully for user: {user_id}")
    return SessionResponse(user_id=user_id, message="Session created successfully")


@router.delete("/session")
@limiter.limit("30/minute")
async def close_session(request: Request, params: UserIdParam = Depends(validate_user_id)):
    """Close CSES session."""
    logger.info(f"Closing session for user: {params.user_id}")
    if not _session_manager:
        logger.error("Session manager not initialized")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session manager not initialized",
        )

    await _session_manager.close_session(params.user_id)
    logger.info(f"Session closed for user: {params.user_id}")
    return {"message": "Session closed"}
