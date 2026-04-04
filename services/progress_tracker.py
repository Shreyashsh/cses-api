import asyncio
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from models.progress import Progress, UserProgress
from models.submission import Submission, SubmissionVerdict

logger = logging.getLogger("cses_api.progress_tracker")


class ProgressTracker:
    """Tracks user progress with SQLite persistence."""

    MAX_SUBMISSIONS_PER_USER = 1000  # Evict oldest when exceeded

    def __init__(self, db_path: str = "data/progress.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        # In-memory cache for recent submissions (bounded)
        self._progress_cache: dict[str, Progress] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _init_db(self) -> None:
        """Initialize SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_progress (
                    user_id TEXT PRIMARY KEY,
                    solved_problems TEXT,
                    last_updated TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS submissions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    problem_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES user_progress(user_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_submissions_user_id
                ON submissions(user_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_submissions_submitted_at
                ON submissions(user_id, submitted_at)
            """)
            conn.commit()

    def _get_lock(self, user_id: str) -> asyncio.Lock:
        """Get or create lock for user. Uses dict.setdefault for atomicity."""
        return self._locks.setdefault(user_id, asyncio.Lock())

    def _submission_to_dict(self, submission: Submission) -> dict:
        return {
            "id": submission.id,
            "problem_id": submission.problem_id,
            "language": submission.language,
            "verdict": submission.verdict.model_dump(),
            "submitted_at": submission.submitted_at.isoformat(),
        }

    def _dict_to_submission(self, data: dict) -> Submission:
        return Submission(
            id=data["id"],
            problem_id=data["problem_id"],
            language=data["language"],
            verdict=SubmissionVerdict(**json.loads(data["verdict"])),
            submitted_at=datetime.fromisoformat(data["submitted_at"]),
        )

    def _ensure_progress(self, user_id: str) -> Progress:
        """Get or create Progress for user. Should be called within a lock."""
        if user_id not in self._progress_cache:
            # Try to load from DB
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT solved_problems, last_updated FROM user_progress WHERE user_id = ?",
                    (user_id,),
                )
                row = cursor.fetchone()
                if row:
                    solved = json.loads(row[0]) if row[0] else []
                    last_updated = (
                        datetime.fromisoformat(row[1])
                        if row[1]
                        else datetime.now(timezone.utc)
                    )
                    progress = Progress(
                        user_id=user_id,
                        solved=solved,
                        submissions=[],  # Loaded separately
                        last_updated=last_updated,
                    )
                else:
                    progress = Progress(user_id=user_id)
            self._progress_cache[user_id] = progress
        return self._progress_cache[user_id]

    async def add_submission(self, user_id: str, submission: Submission) -> None:
        """Add submission thread-safely using per-user locks."""
        lock = self._get_lock(user_id)
        async with lock:
            progress = self._ensure_progress(user_id)

            # Persist submission to SQLite
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO submissions (id, user_id, problem_id, language, verdict, submitted_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        submission.id,
                        user_id,
                        submission.problem_id,
                        submission.language,
                        json.dumps(submission.verdict.model_dump()),
                        submission.submitted_at.isoformat(),
                    ),
                )

                # Update solved problems
                if submission.verdict.status.lower() == "accepted":
                    if submission.problem_id not in progress.solved:
                        progress.solved.append(submission.problem_id)
                        conn.execute(
                            "UPDATE user_progress SET solved_problems = ? WHERE user_id = ?",
                            (json.dumps(progress.solved), user_id),
                        )

                # Evict oldest submissions when limit exceeded
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM submissions WHERE user_id = ?",
                    (user_id,),
                )
                count = cursor.fetchone()[0]
                if count > self.MAX_SUBMISSIONS_PER_USER:
                    # Delete oldest submissions beyond limit
                    cursor = conn.execute(
                        """
                        DELETE FROM submissions WHERE id IN (
                            SELECT id FROM submissions WHERE user_id = ?
                            ORDER BY submitted_at ASC
                            LIMIT ?
                        )
                        """,
                        (user_id, count - self.MAX_SUBMISSIONS_PER_USER),
                    )

                conn.commit()

            # Update cache
            progress.submissions.append(submission)
            if len(progress.submissions) > self.MAX_SUBMISSIONS_PER_USER:
                progress.submissions = progress.submissions[
                    -self.MAX_SUBMISSIONS_PER_USER :
                ]

            progress.last_updated = datetime.now(timezone.utc)

            # Upsert user_progress row
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO user_progress (user_id, solved_problems, last_updated)
                    VALUES (?, ?, ?)
                    """,
                    (
                        user_id,
                        json.dumps(progress.solved),
                        progress.last_updated.isoformat(),
                    ),
                )
                conn.commit()

    def get_user_progress(self, user_id: str) -> Optional[UserProgress]:
        progress = self._progress_cache.get(user_id)
        if not progress:
            # Load from DB
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT solved_problems, last_updated FROM user_progress WHERE user_id = ?",
                    (user_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return None

                solved = json.loads(row[0]) if row[0] else []
                last_updated = (
                    datetime.fromisoformat(row[1])
                    if row[1]
                    else datetime.now(timezone.utc)
                )

                # Load recent submissions
                cursor = conn.execute(
                    "SELECT id, problem_id, language, verdict, submitted_at FROM submissions WHERE user_id = ? ORDER BY submitted_at DESC LIMIT 10",
                    (user_id,),
                )
                submissions = [
                    self._dict_to_submission(
                        dict(
                            zip(
                                [
                                    "id",
                                    "problem_id",
                                    "language",
                                    "verdict",
                                    "submitted_at",
                                ],
                                row,
                            )
                        )
                    )
                    for row in cursor.fetchall()
                ]
                submissions.reverse()  # Oldest first

                return UserProgress(
                    user_id=user_id,
                    total_solved=len(solved),
                    solved_problems=solved,
                    recent_submissions=submissions,
                    last_updated=last_updated,
                )

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
        # Check cache first
        progress = self._progress_cache.get(user_id)
        if progress:
            for s in progress.submissions:
                if s.id == submission_id:
                    return s

        # Fall back to DB
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id, problem_id, language, verdict, submitted_at FROM submissions WHERE user_id = ? AND id = ?",
                (user_id, submission_id),
            )
            row = cursor.fetchone()
            if row:
                return self._dict_to_submission(
                    dict(
                        zip(
                            ["id", "problem_id", "language", "verdict", "submitted_at"],
                            row,
                        )
                    )
                )
        return None
