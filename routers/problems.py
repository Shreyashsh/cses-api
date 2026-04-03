import logging
import re
from typing import List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Request, status

from limiter import limiter
from models.problem import Problem, ProblemCategory, ProblemList
from models.user_id import UserIdParam, validate_user_id

logger = logging.getLogger("cses_api.problems")

router = APIRouter(prefix="/problems", tags=["Problems"])

_session_manager = None
_problem_fetcher = None

# Validate category: alphanumeric with hyphens, no path traversal
CATEGORY_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-_]*$")


def set_services(manager, fetcher):
    global _session_manager, _problem_fetcher
    _session_manager = manager
    _problem_fetcher = fetcher


def get_client(params: UserIdParam = Depends(validate_user_id)) -> httpx.AsyncClient:
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


@router.get("", response_model=List[ProblemCategory])
@limiter.limit("30/minute")
async def list_categories(request: Request, client=Depends(get_client)):
    """List all problem categories."""
    logger.info("Fetching categories")
    try:
        categories = await _problem_fetcher.fetch_categories(client)
        logger.info(f"Fetched {len(categories)} categories")
        return categories
    except Exception as e:
        logger.exception(f"Failed to fetch categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch categories from CSES. Please try again later.",
        )


@router.get("/{category}", response_model=ProblemList)
@limiter.limit("30/minute")
async def list_problems(
    request: Request,
    category: str = Path(..., min_length=1, max_length=100),
    client=Depends(get_client),
):
    """List all problems in a category."""
    if not CATEGORY_PATTERN.match(category):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid category format. Only alphanumeric characters, hyphens, and underscores are allowed.",
        )
    logger.info(f"Fetching problems for category: {category}")
    try:
        problems = await _problem_fetcher.fetch_category_problems(client, category)
        logger.info(f"Fetched {len(problems)} problems for category: {category}")
        return ProblemList(category=category, problems=problems)
    except Exception as e:
        logger.exception(f"Failed to fetch problems for category {category}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch problems from CSES. Please try again later.",
        )


@router.get("/{category}/{problem_id}", response_model=Problem)
@limiter.limit("30/minute")
async def get_problem(
    request: Request,
    category: str = Path(..., min_length=1, max_length=100),
    problem_id: str = Path(..., min_length=1, max_length=100),
    client=Depends(get_client),
):
    """Fetch problem details (cached)."""
    if not CATEGORY_PATTERN.match(category):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid category format. Only alphanumeric characters, hyphens, and underscores are allowed.",
        )
    logger.info(f"Fetching problem {problem_id} in category: {category}")
    try:
        problem = await _problem_fetcher.fetch_problem(client, problem_id, category)
        logger.info(f"Fetched problem: {problem_id}")
        return problem
    except Exception as e:
        logger.exception(f"Failed to fetch problem {problem_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch problem data from CSES. Please try again later.",
        )
