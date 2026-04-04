import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from models.problem import Problem, ProblemCategory, ProblemSummary
from services.retry import retry_async


class ProblemFetcher:
    """Fetches and caches CSES problems."""

    def __init__(self, cache_dir: str = "cache/problems"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, problem_id: str) -> Path:
        return self.cache_dir / f"{problem_id}.json"

    def _get_category_cache_path(self, category_slug: str) -> Path:
        return self.cache_dir / f"cat_{category_slug}.json"

    def _get_categories_list_path(self) -> Path:
        return self.cache_dir / "_categories_list.json"

    def _is_cache_valid(self, cache_path: Path, max_age_hours: int = 24) -> bool:
        if not cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc)
        age = datetime.now(timezone.utc) - mtime
        return age < timedelta(hours=max_age_hours)

    def get_from_cache(self, problem_id: str) -> Optional[Problem]:
        """Fetch problem from cache if valid."""
        cache_path = self._get_cache_path(problem_id)
        if not self._is_cache_valid(cache_path):
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return Problem(**data)
        except (json.JSONDecodeError, ValueError):
            cache_path.unlink(missing_ok=True)
            return None

    def save_to_cache(self, problem: Problem) -> None:
        """Save problem to cache atomically."""
        cache_path = self._get_cache_path(problem.id)
        data = problem.model_dump()
        fd, tmp_path = tempfile.mkstemp(dir=self.cache_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp_path, cache_path)
        except Exception:
            os.unlink(tmp_path)
            raise

    @staticmethod
    def _clean_latex(text: str) -> str:
        """Clean LaTeX syntax from text."""
        if not text:
            return text
        
        # Clean up LaTeX patterns
        replacements = [
            ("\\rightarrow", " -> "),
            ("\\ldots", ", ..."),
            ("\\dots", "..."),
            ("\\leq", "<="),
            ("\\le", "<="),
            ("\\geq", ">="),
            ("\\ge", ">="),
            ("\\times", "*"),
            ("\\div", "/"),
            ("\\cdot", "*"),
            ("\\frac{", ""),
            ("\\limits", ""),
            ("\\sum", "Σ"),
            ("\\n", " "),
            ("\\", ""),
            ("{", ""),
            ("}", ""),
            ("_", ""),  # Remove subscripts
        ]
        
        for old, new in replacements:
            text = text.replace(old, new)
        
        return text

    def _extract_clean_text(self, soup) -> str:
        """Extract clean, human-readable text from a BeautifulSoup element."""
        if not soup:
            return ""

        # First pass: replace all math spans with cleaned text
        for math_span in soup.find_all("span", class_=lambda c: c and "math" in c):
            raw_text = math_span.get_text(strip=True)
            clean_text = self._clean_latex(raw_text)
            math_span.replace_with(clean_text)

        # Get text with preserved line breaks for block elements
        lines = []
        for elem in soup.children:
            if elem.name in ("p", "h1", "h2", "h3", "div", "ul", "ol"):
                text = elem.get_text(separator=" ", strip=True)
                if text:
                    # Clean up extra spaces before punctuation
                    text = re.sub(r'\s+([.,;:!?)])', r'\1', text)
                    # Final LaTeX cleanup for any remaining patterns
                    text = self._clean_latex(text)
                    lines.append(text)
            elif hasattr(elem, "get_text"):
                text = elem.get_text(separator=" ", strip=True)
                if text:
                    text = re.sub(r'\s+([.,;:!?)])', r'\1', text)
                    text = self._clean_latex(text)
                    lines.append(text)
            elif isinstance(elem, str):
                text = elem.strip()
                if text:
                    lines.append(text)

        return "\n\n".join(lines) if lines else ""

    def parse_problem_page(self, html: str, category: str, problem_id: str) -> Problem:
        """Parse CSES problem HTML into Problem model."""
        # Fix encoding issues - ensure proper UTF-8
        html = html.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        
        soup = BeautifulSoup(html, "html.parser")

        # Extract title from H1
        title_elem = soup.find("h1")
        title = title_elem.get_text(strip=True) if title_elem else "Unknown"

        # Extract description as clean text
        desc_elem = soup.find("div", class_="md")
        description = None
        if desc_elem:
            # Create a working copy
            desc_clone = BeautifulSoup(str(desc_elem), "html.parser")
            
            # Remove <pre> blocks (examples) from description
            for pre in desc_clone.find_all("pre"):
                pre.decompose()
            
            # Remove everything from "Input" heading onwards
            input_heading = desc_clone.find("h1", id="input")
            if input_heading:
                to_remove = []
                elem = input_heading
                while elem:
                    to_remove.append(elem)
                    elem = elem.find_next_sibling()
                for elem in to_remove:
                    elem.decompose()
            
            description = self._extract_clean_text(desc_clone)

        # Extract input/output format as clean text
        input_format = None
        output_format = None
        if desc_elem:
            input_h1 = desc_elem.find("h1", id="input")
            if input_h1:
                parts = []
                sibling = input_h1.find_next_sibling()
                while sibling and sibling.name != "h1":
                    if sibling.name in ("p", "ul", "ol"):
                        text = sibling.get_text(separator=" ", strip=True)
                        parts.append(self._clean_latex(text))
                    sibling = sibling.find_next_sibling()
                input_format = "\n".join(parts) if parts else None

            output_h1 = desc_elem.find("h1", id="output")
            if output_h1:
                parts = []
                sibling = output_h1.find_next_sibling()
                while sibling and sibling.name != "h1":
                    if sibling.name in ("p", "ul", "ol"):
                        text = sibling.get_text(separator=" ", strip=True)
                        parts.append(self._clean_latex(text))
                    sibling = sibling.find_next_sibling()
                output_format = "\n".join(parts) if parts else None

        # Extract examples from <pre> tags - pair them as input/output
        examples = []
        pre_tags = desc_elem.find_all("pre") if desc_elem else []
        # Group pre tags into pairs (input, output)
        for i in range(0, len(pre_tags) - 1, 2):
            examples.append(
                {
                    "input": pre_tags[i].get_text(strip=True),
                    "output": pre_tags[i + 1].get_text(strip=True),
                }
            )

        return Problem(
            id=problem_id,
            title=title,
            category=category,
            description=description,
            input_format=input_format,
            output_format=output_format,
            examples=examples,
            cached_at=datetime.now(timezone.utc),
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

        problem = self.parse_problem_page(response.text, category, problem_id)
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
    ) -> List[ProblemSummary]:
        """Fetch list of problems in a category by filtering from the main problemset page, with caching."""
        cache_path = self._get_category_cache_path(category_slug)
        if self._is_cache_valid(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [ProblemSummary(**item) for item in data]
            except (json.JSONDecodeError, ValueError):
                cache_path.unlink(missing_ok=True)

        response = await client.get("/problemset")
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        problems: List[ProblemSummary] = []

        # Find category heading and collect problems under it
        for h2 in soup.find_all("h2"):
            heading_text = h2.get_text(strip=True)
            heading_slug = heading_text.lower().replace(" ", "-")

            if heading_slug == category_slug:
                # Problems are in the next <ul class="task-list">
                task_list = h2.find_next_sibling("ul", class_="task-list")
                if task_list:
                    for li in task_list.find_all("li"):
                        link = li.find("a")
                        if link and link.get("href"):
                            href = link["href"]
                            # Extract problem ID from URL
                            if "/problemset/task/" in href:
                                problem_id = href.split("/")[-1]
                                title = link.get_text(strip=True)
                                problems.append(ProblemSummary(id=problem_id, title=title))
                break

        # Cache the result
        self._save_category_problems_to_cache(cache_path, problems)
        return problems

    def _save_category_problems_to_cache(
        self, cache_path: Path, problems: List[ProblemSummary]
    ) -> None:
        """Save category problems to cache atomically."""
        data = [p.model_dump() for p in problems]
        fd, tmp_path = tempfile.mkstemp(dir=self.cache_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp_path, cache_path)
        except Exception:
            os.unlink(tmp_path)
            raise

    async def fetch_categories(
        self, client: httpx.AsyncClient
    ) -> List[ProblemCategory]:
        """Fetch all problem categories using single-pass DOM traversal with caching."""
        cache_path = self._get_categories_list_path()
        if self._is_cache_valid(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [ProblemCategory(**item) for item in data]
            except (json.JSONDecodeError, ValueError):
                cache_path.unlink(missing_ok=True)

        response = await client.get("/problemset")
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Single pass: track current category and collect unique problem IDs
        category_problems: dict[str, set[str]] = {}
        current_category: str | None = None
        seen_categories: set[str] = set()

        for elem in soup.find_all(["h2", "a"]):
            if elem.name == "h2":
                name = elem.get_text(strip=True)
                if name not in seen_categories:
                    seen_categories.add(name)
                    category_problems[name] = set()
                current_category = name
            elif current_category and elem.get("href"):
                href = elem["href"]
                if "/problemset/task/" in href:
                    problem_id = href.split("/")[-1]
                    category_problems[current_category].add(problem_id)

        categories = []
        seen_in_output: set[str] = set()
        for h2 in soup.find_all("h2"):
            name = h2.get_text(strip=True)
            if name in seen_in_output:
                continue
            seen_in_output.add(name)
            slug = name.lower().replace(" ", "-")
            categories.append(
                ProblemCategory(name=name, slug=slug, problem_count=len(category_problems.get(name, set())))
            )

        # Cache the result
        self._save_categories_to_cache(categories)
        return categories

    def _save_categories_to_cache(self, categories: List[ProblemCategory]) -> None:
        """Save category list to cache atomically."""
        cache_path = self._get_categories_list_path()
        data = [cat.model_dump() for cat in categories]
        fd, tmp_path = tempfile.mkstemp(dir=self.cache_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp_path, cache_path)
        except Exception:
            os.unlink(tmp_path)
            raise
