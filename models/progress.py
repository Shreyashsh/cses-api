from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel, Field

from .submission import Submission


class Progress(BaseModel):
    user_id: str
    solved: List[str] = Field(default_factory=list)
    submissions: List[Submission] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserProgress(BaseModel):
    user_id: str
    total_solved: int
    solved_problems: List[str]
    recent_submissions: List[Submission]
