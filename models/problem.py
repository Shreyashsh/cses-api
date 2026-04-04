from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Problem(BaseModel):
    id: str
    title: str
    category: str
    description: Optional[str] = None
    input_format: Optional[str] = None
    output_format: Optional[str] = None
    examples: List[dict] = Field(default_factory=list)
    difficulty: Optional[str] = None
    cached_at: Optional[datetime] = None


class ProblemCategory(BaseModel):
    name: str
    slug: str
    problem_count: int


class ProblemSummary(BaseModel):
    """Lightweight problem info for listings."""

    id: str
    title: str


class ProblemList(BaseModel):
    category: str
    problems: List[ProblemSummary]
