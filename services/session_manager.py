from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import asyncio
import httpx
from bs4 import BeautifulSoup


class SessionManager:
    """Manages CSES session cookies per user."""

    def __init__(self, base_url: str = "https://cses.fi"):
        self.base_url = base_url
        self.sessions: Dict[str, httpx.AsyncClient] = {}
        self.session_expiry: Dict[str, datetime] = {}

    async def create_session(self, user_id: str, username: str, password: str) -> bool:
        """Initialize CSES session with credentials."""
        client = httpx.AsyncClient(
            base_url=self.base_url,
            cookies=httpx.Cookies(),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )

        try:
            # Fetch login page to get CSRF token
            login_page = await client.get("/login")
            if login_page.status_code != 200:
                await client.aclose()
                return False

            # Extract CSRF token using BeautifulSoup (more robust than regex)
            soup = BeautifulSoup(login_page.text, "html.parser")
            csrf_input = soup.find("input", {"name": "csrf_token"})
            if not csrf_input or not csrf_input.get("value"):
                await client.aclose()
                return False

            csrf_token = csrf_input["value"]

            # Attempt login with correct field names (nick, pass)
            response = await client.post(
                "/login",
                data={
                    "csrf_token": csrf_token,
                    "nick": username,
                    "pass": password,
                },
                follow_redirects=True,
            )

            # Check if login succeeded by looking for logout link
            if response.status_code == 200 and "logout" in response.text.lower():
                self.sessions[user_id] = client
                self.session_expiry[user_id] = datetime.now(timezone.utc) + timedelta(
                    hours=2
                )
                return True

        except Exception:
            pass  # Fall through to cleanup

        await client.aclose()
        return False

    def get_session(self, user_id: str) -> Optional[httpx.AsyncClient]:
        """Get session for user, checking expiry."""
        if user_id not in self.sessions:
            return None

        expiry = self.session_expiry.get(user_id)
        if expiry is None or datetime.now(timezone.utc) > expiry:
            client = self.sessions.pop(user_id, None)
            self.session_expiry.pop(user_id, None)
            if client:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(client.aclose())
                except RuntimeError:
                    # No running loop; schedule close on next available loop
                    asyncio.ensure_future(client.aclose())
            return None

        return self.sessions[user_id]

    async def close_session(self, user_id: str) -> None:
        """Close and remove user session."""
        if user_id in self.sessions:
            await self.sessions[user_id].aclose()
            del self.sessions[user_id]
        if user_id in self.session_expiry:
            del self.session_expiry[user_id]

    async def close_all(self) -> None:
        """Close all sessions (on shutdown)."""
        for client in self.sessions.values():
            await client.aclose()
        self.sessions.clear()
        self.session_expiry.clear()
