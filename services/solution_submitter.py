from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup

from models.submission import Submission, SubmissionVerdict


class SolutionSubmitter:
    """Submits solutions to CSES."""

    def __init__(self):
        self.language_map = {
            "python3": "4",
            "python": "4",
            "cpp": "1",
            "cpp17": "1",
            "cpp20": "5",
            "java": "2",
            "javascript": "3",
            "rust": "6",
        }

    async def submit_file(
        self,
        client,
        problem_id: str,
        file_content: bytes,
        filename: str,
        language: str = "python3",
    ) -> Submission:
        """Submit solution file to CSES."""
        submit_url = f"/problemset/task/{problem_id}/submit"
        response = await client.get(submit_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        csrf_input = soup.find("input", {"name": "csrf_token"})
        csrf_token = csrf_input["value"] if csrf_input else ""

        language_code = self.language_map.get(language, "4")

        files = {"file": (filename, file_content, "text/plain")}
        data = {"csrf_token": csrf_token, "language": language_code}

        submit_response = await client.post(
            submit_url, data=data, files=files, follow_redirects=True
        )
        submit_response.raise_for_status()

        submission = await self._parse_submission(
            submit_response.text, problem_id, language
        )

        return submission

    async def _parse_submission(
        self, html: str, problem_id: str, language: str
    ) -> Submission:
        """Parse submission result page."""
        soup = BeautifulSoup(html, "html.parser")

        verdict_elem = soup.find("div", class_="verdict")
        status = verdict_elem.get_text(strip=True) if verdict_elem else "Pending"

        score_elem = soup.find("span", class_="score")
        score = int(score_elem.get_text(strip=True)) if score_elem else None

        time_elem = soup.find("span", class_="time")
        memory_elem = soup.find("span", class_="memory")

        submission_id = datetime.utcnow().isoformat()

        return Submission(
            id=submission_id,
            problem_id=problem_id,
            language=language,
            verdict=SubmissionVerdict(
                status=status,
                score=score,
                time=time_elem.get_text(strip=True) if time_elem else None,
                memory=memory_elem.get_text(strip=True) if memory_elem else None,
            ),
        )
