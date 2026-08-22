import asyncio
import logging
from typing import Any, Optional

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.discovery import Resource

from app.core.config import get_settings
from app.core.constants import OAuth
from app.services.db_service import get_db_service

logger = logging.getLogger(__name__)

class GoogleAuthService:
    """Service for connecting with Google Auth."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.db_service = get_db_service()
        self.gmail_service: Resource | None = None

    async def _get_credentials(self) -> Optional[Credentials]:
        token_data = await self.db_service.get_provider_token(
            user_id=self.user_id, provider=OAuth.GOOGLE
        )
        if not token_data or not token_data.get("access_token"):
            logger.warning(f"No Google OAuth token found for user {self.user_id}")
            return None

        settings = get_settings()
        credentials = Credentials(
            token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=["https://www.googleapis.com/auth/gmail.readonly"]
        )

        return credentials

    async def initialize_service(self) -> Resource:
        if self.gmail_service:
            return self.gmail_service

        credentials = await self._get_credentials()
        if not credentials:
            raise ConnectionError(
                "Could not initialize Gmail service: missing credentials."
            )

        loop = asyncio.get_running_loop()
        self.gmail_service = await loop.run_in_executor(
            None, lambda: build("gmail", "v1", credentials=credentials)
        )
        return self.gmail_service