from datetime import datetime
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
    file_path: Optional[str] = None
    verdict: SubmissionVerdict
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
