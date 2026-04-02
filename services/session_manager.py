from datetime import datetime, timedelta
from typing import Dict, Optional

import httpx


class SessionManager:
    """Manages CSES session cookies per user."""

    def __init__(self, base_url: str = "https://cses.fi"):
        self.base_url = base_url
        self.sessions: Dict[str, httpx.AsyncClient] = {}
        self.session_expiry: Dict[str, datetime] = {}

    async def create_session(self, user_id: str, username: str, password: str) -> bool:
        """Initialize CSES session with credentials."""
        import re

        client = httpx.AsyncClient(
            base_url=self.base_url,
            cookies=httpx.Cookies(),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )

        # Fetch login page to get CSRF token
        login_page = await client.get("/login")

        # Extract CSRF token from form
        csrf_match = re.search(
            r'<input[^>]*name="csrf_token"[^>]*value="([^"]*)"',
            login_page.text,
            re.IGNORECASE,
        )
        if not csrf_match:
            await client.aclose()
            return False

        csrf_token = csrf_match.group(1)

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
            self.session_expiry[user_id] = datetime.utcnow() + timedelta(hours=2)
            return True

        await client.aclose()
        return False

    def get_session(self, user_id: str) -> Optional[httpx.AsyncClient]:
        """Get session for user, checking expiry."""
        if user_id not in self.sessions:
            return None

        expiry = self.session_expiry.get(user_id)
        if expiry is None or datetime.utcnow() > expiry:
            # Clean up orphaned or expired session
            if user_id in self.sessions:
                # Schedule async close to prevent resource leak
                import asyncio
                asyncio.create_task(self.sessions[user_id].aclose())
                del self.sessions[user_id]
            if user_id in self.session_expiry:
                del self.session_expiry[user_id]
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
