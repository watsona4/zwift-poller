"""OAuth2 token management for Zwift API."""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp

logger = logging.getLogger(__name__)

AUTH_URL = "https://secure.zwift.com/auth/realms/zwift/tokens/access/codes"
CLIENT_ID = "Zwift_Mobile_Link"


@dataclass
class TokenData:
    """OAuth2 token data."""

    access_token: str = ""
    refresh_token: str = ""
    access_expiry: float = 0.0
    refresh_expiry: float = 0.0

    def is_access_valid(self, margin: int = 60) -> bool:
        """Check if access token is still valid."""
        return self.access_token and time.time() < (self.access_expiry - margin)

    def is_refresh_valid(self, margin: int = 60) -> bool:
        """Check if refresh token is still valid."""
        return self.refresh_token and time.time() < (self.refresh_expiry - margin)


@dataclass
class AuthManager:
    """Manages Zwift OAuth2 authentication."""

    username: str
    password: str
    token_file: str
    refresh_margin: int = 60
    _tokens: TokenData = field(default_factory=TokenData)
    _session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession()
        self._load_tokens()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
            self._session = None

    def _load_tokens(self) -> None:
        """Load tokens from file if exists."""
        path = Path(self.token_file)
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self._tokens = TokenData(
                    access_token=data.get("access_token", ""),
                    refresh_token=data.get("refresh_token", ""),
                    access_expiry=data.get("access_expiry", 0.0),
                    refresh_expiry=data.get("refresh_expiry", 0.0),
                )
                logger.info("Loaded tokens from %s", self.token_file)
            except Exception as e:
                logger.warning("Failed to load tokens: %s", e)

    def _save_tokens(self) -> None:
        """Save tokens to file."""
        path = Path(self.token_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "access_token": self._tokens.access_token,
                    "refresh_token": self._tokens.refresh_token,
                    "access_expiry": self._tokens.access_expiry,
                    "refresh_expiry": self._tokens.refresh_expiry,
                }
            )
        )
        logger.debug("Saved tokens to %s", self.token_file)

    def _parse_token_response(self, data: dict) -> None:
        """Parse and store token response."""
        now = time.time()

        # Zwift sometimes returns expiry in milliseconds
        access_expires_in = data.get("expires_in", 0)
        if access_expires_in > 1_000_000:
            access_expires_in = access_expires_in // 1000

        refresh_expires_in = data.get("refresh_expires_in", 0)
        if refresh_expires_in > 1_000_000:
            refresh_expires_in = refresh_expires_in // 1000

        self._tokens = TokenData(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token", ""),
            access_expiry=now + access_expires_in - 5,
            refresh_expiry=now + refresh_expires_in - 5,
        )
        self._save_tokens()

    async def _password_grant(self) -> bool:
        """Authenticate with username/password."""
        if not self._session:
            return False

        logger.info("Authenticating with password grant")
        try:
            async with self._session.post(
                AUTH_URL,
                data={
                    "client_id": CLIENT_ID,
                    "grant_type": "password",
                    "username": self.username,
                    "password": self.password,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._parse_token_response(data)
                    logger.info("Password grant successful")
                    return True
                else:
                    text = await resp.text()
                    logger.error("Password grant failed: %d - %s", resp.status, text)
                    return False
        except Exception as e:
            logger.error("Password grant error: %s", e)
            return False

    async def _refresh_grant(self) -> bool:
        """Refresh access token using refresh token."""
        if not self._session or not self._tokens.refresh_token:
            return False

        logger.info("Refreshing access token")
        try:
            async with self._session.post(
                AUTH_URL,
                data={
                    "client_id": CLIENT_ID,
                    "grant_type": "refresh_token",
                    "refresh_token": self._tokens.refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._parse_token_response(data)
                    logger.info("Token refresh successful")
                    return True
                else:
                    text = await resp.text()
                    logger.warning("Token refresh failed: %d - %s", resp.status, text)
                    return False
        except Exception as e:
            logger.warning("Token refresh error: %s", e)
            return False

    async def ensure_valid_token(self) -> str | None:
        """Ensure we have a valid access token, refreshing or re-authenticating as needed.

        Returns the access token if successful, None otherwise.
        """
        # Check if current access token is valid
        if self._tokens.is_access_valid(self.refresh_margin):
            return self._tokens.access_token

        # Try refresh if refresh token is valid
        if self._tokens.is_refresh_valid(self.refresh_margin):
            if await self._refresh_grant():
                return self._tokens.access_token

        # Fall back to password grant
        if await self._password_grant():
            return self._tokens.access_token

        return None

    @property
    def access_token(self) -> str:
        """Get current access token."""
        return self._tokens.access_token
