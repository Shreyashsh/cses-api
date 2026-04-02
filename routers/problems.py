from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status

from limiter import limiter
from models.problem import Problem, ProblemCategory, ProblemList
from models.user_id import UserIdParam, validate_user_id

router = APIRouter(prefix="/problems", tags=["Problems"])

_session_manager = None
_problem_fetcher = None


def set_services(manager, fetcher, limiter_instance=None):
    global _session_manager, _problem_fetcher
    _session_manager = manager
    _problem_fetcher = fetcher


def get_client(params: UserIdParam = Depends(validate_user_id)):
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
    try:
        categories = await _problem_fetcher.fetch_categories(client)
        return categories
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch categories: {str(e)}",
        )


@router.get("/{category}", response_model=ProblemList)
@limiter.limit("30/minute")
async def list_problems(
    request: Request, category: str, client=Depends(get_client)
):
    """List all problems in a category."""
    try:
        problems = await _problem_fetcher.fetch_category_problems(client, category)
        return ProblemList(category=category, problems=problems)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch problems: {str(e)}",
        )


@router.get("/{category}/{problem_id}", response_model=Problem)
@limiter.limit("30/minute")
async def get_problem(
    request: Request,
    category: str,
    problem_id: str,
    client=Depends(get_client),
):
    """Fetch problem details (cached)."""
    try:
        problem = await _problem_fetcher.fetch_problem(client, problem_id, category)
        return problem
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch problem: {str(e)}",
        )
