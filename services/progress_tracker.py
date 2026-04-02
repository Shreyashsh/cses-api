import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from models.progress import Progress, UserProgress
from models.submission import Submission


class ProgressTracker:
    """Tracks user progress in-memory."""

    def __init__(self):
        self.progress: Dict[str, Progress] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, user_id: str) -> asyncio.Lock:
        """Get or create lock for user."""
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]

    def get_progress(self, user_id: str) -> Optional[Progress]:
        return self.progress.get(user_id)

    def create_progress(self, user_id: str) -> Progress:
        progress = Progress(user_id=user_id)
        self.progress[user_id] = progress
        return progress

    async def add_submission(self, user_id: str, submission: Submission) -> None:
        """Add submission thread-safely using per-user locks."""
        lock = self._get_lock(user_id)
        async with lock:
            if user_id not in self.progress:
                self.create_progress(user_id)

            self.progress[user_id].submissions.append(submission)

            if submission.verdict.status == "Accepted":
                if submission.problem_id not in self.progress[user_id].solved:
                    self.progress[user_id].solved.append(submission.problem_id)

            self.progress[user_id].last_updated = datetime.utcnow()

    def get_user_progress(self, user_id: str) -> Optional[UserProgress]:
        progress = self.progress.get(user_id)
        if not progress:
            return None

        return UserProgress(
            user_id=user_id,
            total_solved=len(progress.solved),
            solved_problems=progress.solved,
            recent_submissions=progress.submissions[-10:],
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
