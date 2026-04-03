import asyncio
from datetime import datetime, timezone

import pytest

from models.submission import Submission, SubmissionVerdict
from services.progress_tracker import ProgressTracker


def create_submission(problem_id: str, status: str = "Accepted") -> Submission:
    """Helper to create a submission."""
    return Submission(
        id=f"sub_{problem_id}_{datetime.now(timezone.utc).timestamp()}",
        problem_id=problem_id,
        language="python3",
        verdict=SubmissionVerdict(status=status),
    )


@pytest.mark.asyncio
async def test_concurrent_submissions_thread_safe():
    """Concurrent submissions should not lose data."""
    tracker = ProgressTracker()
    user_id = "test_user"

    async def add_submission(i):
        submission = create_submission(
            problem_id=f"problem_{i % 3}",
            status="Accepted" if i % 2 == 0 else "Wrong Answer",
        )
        await tracker.add_submission(user_id, submission)

    # Add 10 submissions concurrently
    await asyncio.gather(*[add_submission(i) for i in range(10)])

    # All submissions should be recorded
    assert len(tracker.progress[user_id].submissions) == 10


@pytest.mark.asyncio
async def test_no_duplicate_solved_problems():
    """Same problem solved twice should not duplicate."""
    tracker = ProgressTracker()
    user_id = "test_user"

    async def add_accepted(problem_id):
        submission = create_submission(problem_id=problem_id, status="Accepted")
        await tracker.add_submission(user_id, submission)

    # Add same problem 5 times concurrently
    await asyncio.gather(*[add_accepted("problem_1") for _ in range(5)])

    # Should only have one solved entry
    assert len(tracker.progress[user_id].solved) == 1
    assert "problem_1" in tracker.progress[user_id].solved


@pytest.mark.asyncio
async def test_sequential_submissions_still_work():
    """Sequential submissions should work as before."""
    tracker = ProgressTracker()
    user_id = "test_user"

    submission1 = create_submission(problem_id="problem_1", status="Accepted")
    submission2 = create_submission(problem_id="problem_2", status="Wrong Answer")
    submission3 = create_submission(problem_id="problem_1", status="Accepted")

    await tracker.add_submission(user_id, submission1)
    await tracker.add_submission(user_id, submission2)
    await tracker.add_submission(user_id, submission3)

    # All 3 submissions recorded
    assert len(tracker.progress[user_id].submissions) == 3
    # Only problem_1 in solved (once, no duplicates)
    assert len(tracker.progress[user_id].solved) == 1
    assert "problem_1" in tracker.progress[user_id].solved
