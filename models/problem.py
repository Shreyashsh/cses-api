from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Problem(BaseModel):
    id: str
    title: str
    category: str
    description: Optional[str] = None
    input_format: Optional[str] = Field(None, alias="input_format")
    output_format: Optional[str] = Field(None, alias="output_format")
    examples: List[dict] = Field(default_factory=list)
    difficulty: Optional[str] = None
    cached_at: Optional[datetime] = None


class ProblemCategory(BaseModel):
    name: str
    slug: str
    problem_count: int


class ProblemList(BaseModel):
    category: str
    problems: List[dict]
