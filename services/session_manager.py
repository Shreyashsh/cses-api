import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("cses_api.session_manager")


class SessionManager:
    """Manages CSES session cookies per user with SQLite persistence."""

    def __init__(
        self, base_url: str = "https://cses.fi", db_path: str = "data/sessions.db"
    ):
        self.base_url = base_url
        self.sessions: Dict[str, httpx.AsyncClient] = {}
        self.session_expiry: Dict[str, datetime] = {}
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    user_id TEXT PRIMARY KEY,
                    cookie_data TEXT,
                    expires_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_expires_at
                ON sessions(expires_at)
            """)
            conn.commit()
        # Clean up expired sessions on startup
        self._cleanup_expired_sessions()

    def _cleanup_expired_sessions(self) -> None:
        """Remove expired sessions from the database."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
            conn.commit()

    def _save_session_to_db(
        self, user_id: str, cookie_data: str, expires_at: datetime
    ) -> None:
        """Persist session cookies to SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions (user_id, cookie_data, expires_at)
                VALUES (?, ?, ?)
                """,
                (user_id, cookie_data, expires_at.isoformat()),
            )
            conn.commit()

    def _load_session_from_db(self, user_id: str) -> Optional[str]:
        """Load session cookies from SQLite. Returns None if expired or missing."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT cookie_data FROM sessions WHERE user_id = ? AND expires_at >= ?",
                (user_id, now),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def _delete_session_from_db(self, user_id: str) -> None:
        """Remove session from SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            conn.commit()

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
                expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
                self.sessions[user_id] = client
                self.session_expiry[user_id] = expires_at

                # Persist cookies to SQLite for restart recovery
                cookie_data = "; ".join(f"{k}={v}" for k, v in client.cookies.items())
                self._save_session_to_db(user_id, cookie_data, expires_at)
                return True
            else:
                logger.warning(f"Login failed for user {user_id}: no logout link found")

        except httpx.RequestError as e:
            logger.error(f"Network error during login for user {user_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during login for user {user_id}: {e}")

        await client.aclose()
        return False

    def get_session(self, user_id: str) -> Optional[httpx.AsyncClient]:
        """Get session for user, checking expiry. Restores from SQLite if expired."""
        if user_id in self.sessions:
            expiry = self.session_expiry.get(user_id)
            if expiry and datetime.now(timezone.utc) <= expiry:
                return self.sessions[user_id]

            # Session expired in memory, close it
            client = self.sessions.pop(user_id, None)
            self.session_expiry.pop(user_id, None)
            if client:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(client.aclose())
                except RuntimeError:
                    asyncio.run(client.aclose())

        # Try to restore from SQLite
        cookie_data = self._load_session_from_db(user_id)
        if cookie_data:
            cookies = httpx.Cookies()
            for pair in cookie_data.split("; "):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    cookies.set(key, value)

            client = httpx.AsyncClient(
                base_url=self.base_url,
                cookies=cookies,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                timeout=httpx.Timeout(30.0, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
            # Verify the restored session is still valid by checking cookies exist
            if cookies:
                expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
                self.sessions[user_id] = client
                self.session_expiry[user_id] = expires_at
                return client
            else:
                client.aclose()

        return None

    async def close_session(self, user_id: str) -> None:
        """Close and remove user session."""
        if user_id in self.sessions:
            await self.sessions[user_id].aclose()
            del self.sessions[user_id]
        if user_id in self.session_expiry:
            del self.session_expiry[user_id]
        self._delete_session_from_db(user_id)

    async def close_all(self) -> None:
        """Close all sessions (on shutdown)."""
        for client in self.sessions.values():
            await client.aclose()
        self.sessions.clear()
        self.session_expiry.clear()
