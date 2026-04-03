import asyncio

import pytest

from services.solution_submitter import SolutionSubmitter


@pytest.mark.asyncio
async def test_submission_ids_are_unique():
    """Concurrent submissions should have unique IDs."""
    submitter = SolutionSubmitter()

    async def submit():
        # Generate submission ID
        return submitter._generate_submission_id("problem_1")

    # Generate 100 IDs concurrently
    ids = await asyncio.gather(*[submit() for _ in range(100)])

    # All IDs should be unique
    assert len(set(ids)) == 100
