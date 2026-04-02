import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from models.problem import Problem, ProblemCategory
from services.retry import retry_async


class ProblemFetcher:
    """Fetches and caches CSES problems."""

    def __init__(self, cache_dir: str = "cache/problems"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, problem_id: str) -> Path:
        return self.cache_dir / f"{problem_id}.json"

    def _is_cache_valid(self, cache_path: Path, max_age_hours: int = 24) -> bool:
        if not cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.utcnow() - mtime
        return age < timedelta(hours=max_age_hours)

    def get_from_cache(self, problem_id: str) -> Optional[Problem]:
        """Fetch problem from cache if valid."""
        cache_path = self._get_cache_path(problem_id)
        if not self._is_cache_valid(cache_path):
            return None

        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return Problem(**data)

    def save_to_cache(self, problem: Problem) -> None:
        """Save problem to cache."""
        cache_path = self._get_cache_path(problem.id)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(problem.model_dump(by_alias=True), f, indent=2, default=str)

    def parse_problem_page(self, html: str, category: str) -> Problem:
        """Parse CSES problem HTML into Problem model."""
        soup = BeautifulSoup(html, "html.parser")

        # Extract problem ID from URL or content
        url_elem = soup.find("meta", {"property": "og:url"})
        problem_id = url_elem["content"].split("/")[-1] if url_elem else "unknown"

        # Extract title
        title_elem = soup.find("h1")
        title = title_elem.get_text(strip=True) if title_elem else "Unknown"

        # Extract description
        desc_elem = soup.find("div", class_="problem-content")
        description = desc_elem.get_text(strip=True) if desc_elem else None

        # Extract input/output format
        input_format = None
        output_format = None
        for section in soup.find_all("h3"):
            text = section.get_text(strip=True).lower()
            if "input" in text:
                input_elem = section.find_next_sibling()
                input_format = input_elem.get_text(strip=True) if input_elem else None
            elif "output" in text:
                output_elem = section.find_next_sibling()
                output_format = (
                    output_elem.get_text(strip=True) if output_elem else None
                )

        # Extract examples
        examples = []
        for example in soup.find_all("div", class_="example"):
            ex_data = {"input": "", "output": ""}
            pre_tags = example.find_all("pre")
            if len(pre_tags) >= 2:
                ex_data["input"] = pre_tags[0].get_text(strip=True)
                ex_data["output"] = pre_tags[1].get_text(strip=True)
            if ex_data["input"] or ex_data["output"]:
                examples.append(ex_data)

        return Problem(
            id=problem_id,
            title=title,
            category=category,
            description=description,
            input_format=input_format,
            output_format=output_format,
            examples=examples,
            cached_at=datetime.utcnow(),
        )

    @retry_async(max_attempts=3, backoff_factor=0.5)
    async def fetch_problem(
        self, client: httpx.AsyncClient, problem_id: str, category: str
    ) -> Problem:
        """Fetch problem from CSES, using cache if available."""
        cached = self.get_from_cache(problem_id)
        if cached:
            return cached

        url = f"/problemset/task/{problem_id}"
        response = await client.get(url)
        response.raise_for_status()

        problem = self.parse_problem_page(response.text, category)
        self.save_to_cache(problem)
        return problem

    def parse_category_page(self, html: str, category_name: str) -> List[dict]:
        """Parse CSES category page to list problems."""
        soup = BeautifulSoup(html, "html.parser")
        problems = []

        for task in soup.find_all("div", class_="task"):
            link = task.find("a")
            if link:
                problem_id = link["href"].split("/")[-1]
                title = link.get_text(strip=True)
                problems.append({"id": problem_id, "title": title})

        return problems

    async def fetch_category_problems(
        self, client: httpx.AsyncClient, category_slug: str
    ) -> List[dict]:
        """Fetch list of problems in a category."""
        url = f"/problemset/category/{category_slug}"
        response = await client.get(url)
        response.raise_for_status()
        return self.parse_category_page(response.text, category_slug)

    async def fetch_categories(
        self, client: httpx.AsyncClient
    ) -> List[ProblemCategory]:
        """Fetch all problem categories."""
        response = await client.get("/problemset")
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        categories = []
        seen = set()

        # Categories are in h2 tags, count tasks after each h2
        for h2 in soup.find_all("h2"):
            name = h2.get_text(strip=True)
            if name in seen:
                continue
            seen.add(name)

            # Count unique problems in this category
            problem_ids = set()
            for elem in h2.find_next_siblings():
                for link in elem.find_all(
                    "a", href=lambda x: x and "/problemset/task/" in str(x)
                ):
                    href = link["href"]
                    problem_id = href.split("/")[-1]
                    problem_ids.add(problem_id)

            slug = name.lower().replace(" ", "-")
            categories.append(
                ProblemCategory(name=name, slug=slug, problem_count=len(problem_ids))
            )

        return categories
