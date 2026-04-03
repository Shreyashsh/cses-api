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
    "testing",  # Initial state
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
    ) -> Submission:
        """Submit solution file to CSES with retry logic."""
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

        # The response should be a redirect to the result page
        if submit_response.status_code not in (301, 302, 303, 307, 308):
            return await self._parse_submission(
                submit_response.text, problem_id, language
            )

        # Get the redirect location
        location = submit_response.headers.get("location", "")
        if not location:
            return await self._parse_submission(
                submit_response.text, problem_id, language
            )

        # Convert to relative if absolute
        if location.startswith("http"):
            from urllib.parse import urlparse

            location = urlparse(location).path

        # Wait briefly for CSES to process, then poll the result page
        await asyncio.sleep(2)

        submission = await self._poll_for_verdict(
            client, location, problem_id, language
        )

        return submission

    async def _poll_for_verdict(
        self, client, result_url: str, problem_id: str, language: str
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
                    id=self._generate_submission_id(problem_id),
                    problem_id=problem_id,
                    language=language,
                    verdict=SubmissionVerdict(
                        status="Judgement Timeout",
                        message=f"Timed out after {poll_count} polls. Last status: {last_status}. URL: {result_url}",
                    ),
                )

            submission = await self._parse_submission_from_url(
                client, result_url, problem_id, language
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
        self, client, url: str, problem_id: str, language: str
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
                    id=self._generate_submission_id(problem_id),
                    problem_id=problem_id,
                    language=language,
                    verdict=SubmissionVerdict(status=f"HTTP {response.status_code}"),
                )
            response.raise_for_status()
            return await self._parse_submission(response.text, problem_id, language)
        except Exception as e:
            import logging

            logger = logging.getLogger("cses_api.submitter")
            logger.warning(f"Error fetching result URL {url}: {e}")
            return Submission(
                id=self._generate_submission_id(problem_id),
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
