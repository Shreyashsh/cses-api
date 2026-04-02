# models/user_id.py
from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator


class UserIdParam(BaseModel):
    """Validated user ID parameter."""

    user_id: str = Field(..., min_length=1, max_length=64)

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """Validate user_id format - only alphanumeric, underscore, hyphen."""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Invalid user_id format. Only alphanumeric, underscore, and hyphen allowed."
            )
        return v


def validate_user_id(user_id: str) -> UserIdParam:
    """Validate user_id and return UserIdParam or raise 422."""
    try:
        return UserIdParam(user_id=user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=str(e),
        )
