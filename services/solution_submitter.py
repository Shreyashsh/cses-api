import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from bs4 import BeautifulSoup

from models.submission import Submission, SubmissionVerdict

# Terminal verdicts that indicate final judging state (case-insensitive)
TERMINAL_VERDICTS = {
    "accepted",
    "wrong answer",
    "time limit exceeded",
    "compilation error",
    "compile error",
    "runtime error",
    "output limit exceeded",
    "memory limit exceeded",
    "presentation error",
    "ready",  # CSES shows READY when judging is complete
}


class SolutionSubmitter:
    """Submits solutions to CSES."""

    def __init__(
        self,
        poll_interval: float = 2.0,
        poll_timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout
        self.max_retries = max_retries
        self.language_map = {
            "python3": "Python3",
            "python": "Python3",
            "cpp": "C++",
            "cpp17": "C++",
            "cpp20": "C++",
            "java": "Java",
            "javascript": "Node.js",
            "rust": "Rust",
            "c": "C",
            "pascal": "Pascal",
            "ruby": "Ruby",
            "haskell": "Haskell",
            "scala": "Scala",
            "assembly": "Assembly",
        }
        # Background tasks for polling
        self._pending_submissions: dict[str, dict] = {}
        self._background_tasks: dict[str, asyncio.Task] = {}

    def _generate_submission_id(self, problem_id: str) -> str:
        """Generate unique submission ID."""
        return f"{problem_id}_{datetime.now(timezone.utc).timestamp()}_{uuid.uuid4().hex[:8]}"

    async def submit_file(
        self,
        client,
        problem_id: str,
        file_content: bytes,
        filename: str,
        language: str = "python3",
        progress_tracker=None,
        user_id: str = None,
    ) -> Submission:
        """Submit solution file to CSES with retry logic. Returns immediately with pending status."""
        # First get the submit page for CSRF token
        submit_page_url = f"/problemset/submit/{problem_id}"

        # Retry fetching the submit page for the CSRF token
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await client.get(submit_page_url)
                response.raise_for_status()
                break
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
                continue
        else:
            raise last_error

        soup = BeautifulSoup(response.text, "html.parser")
        csrf_input = soup.find("input", {"name": "csrf_token"})
        csrf_token = csrf_input["value"] if csrf_input else ""

        language_code = self.language_map.get(language, "Python3")

        files = {"file": (filename, file_content, "text/plain")}
        data = {
            "csrf_token": csrf_token,
            "lang": language_code,
            "task": problem_id,
            "type": "course",
            "target": "problemset",
        }

        # Submit to the form action URL (don't follow redirects automatically)
        submit_response = await client.post(
            "/course/send.php",
            data=data,
            files=files,
        )

        # Generate submission ID upfront
        submission_id = self._generate_submission_id(problem_id)

        # Parse the response to get initial submission info
        if submit_response.status_code not in (301, 302, 303, 307, 308):
            submission = await self._parse_submission(
                submit_response.text, problem_id, language
            )
            submission.id = submission_id
            return submission

        # Get the redirect location
        location = submit_response.headers.get("location", "")
        if not location:
            submission = await self._parse_submission(
                submit_response.text, problem_id, language
            )
            submission.id = submission_id
            return submission

        # Convert to relative if absolute
        if location.startswith("http"):
            from urllib.parse import urlparse

            location = urlparse(location).path

        # Create a pending submission record
        submission = Submission(
            id=submission_id,
            problem_id=problem_id,
            language=language,
            verdict=SubmissionVerdict(
                status="Pending",
                message="Submission received. Judging in progress.",
            ),
        )

        # Store pending submission info for background polling
        self._pending_submissions[submission_id] = {
            "client": client,
            "result_url": location,
            "problem_id": problem_id,
            "language": language,
            "progress_tracker": progress_tracker,
            "user_id": user_id,
        }

        # Start background polling task
        task = asyncio.create_task(self._background_poll_submission(submission_id))
        self._background_tasks[submission_id] = task

        return submission

    async def _background_poll_submission(self, submission_id: str) -> None:
        """Background task to poll for final verdict and update progress tracker."""
        import logging

        logger = logging.getLogger("cses_api.submitter")
        pending = self._pending_submissions.get(submission_id)
        if not pending:
            return

        client = pending["client"]
        result_url = pending["result_url"]
        problem_id = pending["problem_id"]
        language = pending["language"]
        progress_tracker = pending.get("progress_tracker")
        user_id = pending.get("user_id")

        try:
            final_submission = await self._poll_for_verdict(
                client, result_url, problem_id, language, submission_id
            )

            # Update progress tracker with final verdict
            if progress_tracker and user_id:
                await progress_tracker.add_submission(user_id, final_submission)
                logger.info(
                    f"Background polling complete for {submission_id}: {final_submission.verdict.status}"
                )

            # Update pending record
            self._pending_submissions[submission_id][
                "final_submission"
            ] = final_submission
        except Exception as e:
            logger.error(f"Background polling failed for {submission_id}: {e}")
            error_submission = Submission(
                id=submission_id,
                problem_id=problem_id,
                language=language,
                verdict=SubmissionVerdict(
                    status="Error",
                    message=f"Polling error: {e}",
                ),
            )
            self._pending_submissions[submission_id][
                "final_submission"
            ] = error_submission
        finally:
            self._background_tasks.pop(submission_id, None)

    def get_pending_submission(self, submission_id: str) -> Optional[dict]:
        """Get pending submission info by ID."""
        return self._pending_submissions.get(submission_id)

    async def _poll_for_verdict(
        self,
        client,
        result_url: str,
        problem_id: str,
        language: str,
        submission_id: str,
    ) -> Submission:
        """Poll CSES for final verdict until terminal state or timeout."""
        import logging

        logger = logging.getLogger("cses_api.submitter")
        loop = asyncio.get_running_loop()
        start_time = loop.time()
        poll_count = 0
        last_status = "Unknown"

        while True:
            elapsed = loop.time() - start_time
            if elapsed >= self.poll_timeout:
                return Submission(
                    id=submission_id,
                    problem_id=problem_id,
                    language=language,
                    verdict=SubmissionVerdict(
                        status="Judgement Timeout",
                        message=f"Timed out after {poll_count} polls. Last status: {last_status}. URL: {result_url}",
                    ),
                )

            submission = await self._parse_submission_from_url(
                client, result_url, problem_id, language, submission_id
            )
            poll_count += 1
            last_status = submission.verdict.status
            logger.info(
                f"Poll {poll_count}: status={submission.verdict.status!r}, result_url={result_url}"
            )
            if submission.verdict.status.lower() in TERMINAL_VERDICTS:
                return submission

            await asyncio.sleep(self.poll_interval)

    async def _parse_submission_from_url(
        self, client, url: str, problem_id: str, language: str, submission_id: str
    ) -> Submission:
        """Fetch and parse submission result from a URL."""
        try:
            response = await client.get(url)
            if response.status_code != 200:
                import logging

                logger = logging.getLogger("cses_api.submitter")
                logger.warning(
                    f"Failed to fetch result URL {url}: status {response.status_code}"
                )
                return Submission(
                    id=submission_id,
                    problem_id=problem_id,
                    language=language,
                    verdict=SubmissionVerdict(status=f"HTTP {response.status_code}"),
                )
            response.raise_for_status()
            submission = await self._parse_submission(
                response.text, problem_id, language
            )
            submission.id = submission_id
            return submission
        except Exception as e:
            import logging

            logger = logging.getLogger("cses_api.submitter")
            logger.warning(f"Error fetching result URL {url}: {e}")
            return Submission(
                id=submission_id,
                problem_id=problem_id,
                language=language,
                verdict=SubmissionVerdict(status=f"Error: {e}"),
            )

    async def _parse_submission(
        self, html: str, problem_id: str, language: str
    ) -> Submission:
        """Parse submission result page."""
        soup = BeautifulSoup(html, "html.parser")

        # Look for status and result in table (CSES result page format)
        status = "Pending"
        result = None
        score = None
        time_val = None
        memory_val = None

        for td in soup.find_all("td"):
            text = td.get_text(strip=True)
            next_td = td.find_next_sibling("td")
            next_text = next_td.get_text(strip=True) if next_td else ""

            if text == "Status:":
                status = next_text
            elif text == "Result:":
                result = next_text
            elif text.startswith("Score:"):
                score_text = text.replace("Score:", "").strip()
                try:
                    score = int(score_text)
                except ValueError:
                    pass
            elif text == "Time:":
                time_val = next_text
            elif text == "Memory:":
                memory_val = next_text

        # Use result as the verdict if available, otherwise status
        verdict_status = result if result else status

        # Fallback: look for verdict div
        if not verdict_status or verdict_status == "Pending":
            verdict_elem = soup.find("div", class_="verdict")
            if verdict_elem:
                verdict_status = verdict_elem.get_text(strip=True)

        # Log when verdict parsing fails to find expected elements
        if not verdict_status or verdict_status == "Pending":
            import logging

            logger = logging.getLogger("cses_api.submitter")
            logger.warning(
                f"Could not parse verdict from submission page for problem {problem_id}. "
                f"Status={status!r}, Result={result!r}. HTML may have changed."
            )

        submission_id = self._generate_submission_id(problem_id)

        return Submission(
            id=submission_id,
            problem_id=problem_id,
            language=language,
            verdict=SubmissionVerdict(
                status=verdict_status,
                score=score,
                time=time_val,
                memory=memory_val,
            ),
        )
