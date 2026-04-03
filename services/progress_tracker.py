import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

from models.progress import Progress, UserProgress
from models.submission import Submission


class ProgressTracker:
    """Tracks user progress in-memory."""

    def __init__(self):
        self.progress: Dict[str, Progress] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, user_id: str) -> asyncio.Lock:
        """Get or create lock for user. Uses dict.setdefault for atomicity."""
        return self._locks.setdefault(user_id, asyncio.Lock())

    def get_progress(self, user_id: str) -> Optional[Progress]:
        return self.progress.get(user_id)

    def _ensure_progress(self, user_id: str) -> Progress:
        """Get or create Progress for user. Should be called within a lock."""
        if user_id not in self.progress:
            progress = Progress(user_id=user_id)
            self.progress[user_id] = progress
        return self.progress[user_id]

    async def add_submission(self, user_id: str, submission: Submission) -> None:
        """Add submission thread-safely using per-user locks."""
        lock = self._get_lock(user_id)
        async with lock:
            progress = self._ensure_progress(user_id)
            progress.submissions.append(submission)

            if submission.verdict.status == "Accepted":
                if submission.problem_id not in progress.solved:
                    progress.solved.append(submission.problem_id)

            progress.last_updated = datetime.now(timezone.utc)

    def get_user_progress(self, user_id: str) -> Optional[UserProgress]:
        progress = self.progress.get(user_id)
        if not progress:
            return None

        return UserProgress(
            user_id=user_id,
            total_solved=len(progress.solved),
            solved_problems=progress.solved,
            recent_submissions=progress.submissions[-10:],
            last_updated=progress.last_updated,
        )

    def get_submission_by_id(
        self, user_id: str, submission_id: str
    ) -> Optional[Submission]:
        progress = self.progress.get(user_id)
        if not progress:
            return None

        for s in progress.submissions:
            if s.id == submission_id:
                return s
        return None
