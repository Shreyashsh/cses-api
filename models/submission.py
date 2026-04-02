from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class SubmissionVerdict(BaseModel):
    status: str
    score: Optional[int] = None
    message: Optional[str] = None
    time: Optional[str] = None
    memory: Optional[str] = None


class Submission(BaseModel):
    id: str
    problem_id: str
    language: str
    verdict: SubmissionVerdict
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
