from .auth import router as auth_router
from .problems import router as problems_router
from .progress import router as progress_router
from .submissions import router as submissions_router

__all__ = ["auth_router", "problems_router", "submissions_router", "progress_router"]
