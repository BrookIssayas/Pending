import logging
from typing import Optional

from app.core.supabase_client import get_supabase_client
from postgrest import APIResponse

logger = logging.getLogger(__name__)


class DBService:
    """Service for database operations."""

    def __init__(self) -> None:
        """Initializes the DBService."""
        self.client = get_supabase_client()

    async def upsert_provider_token(
        self,
        user_id: str,
        provider: str,
        access_token: str,
        refresh_token: Optional[str] = None,
    ) -> APIResponse:
        """
        Upserts a provider token for a user.

        Args:
            user_id: The ID of the user.
            provider: The OAuth provider (e.g., 'google').
            access_token: The access token.
            refresh_token: The refresh token (optional).

        Returns:
            The API response from the database operation.
        """
        try:
            response = (
                self.client.table("user_provider_tokens")
                .upsert(
                    {
                        "user_id": user_id,
                        "provider": provider,
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                    },
                    on_conflict="user_id",
                )
                .execute()
            )
            logger.info(f"Successfully upserted token for user {user_id}")
            return response
        except Exception as e:
            logger.error(f"Error upserting provider token for user {user_id}: {e!s}")
            raise


def get_db_service() -> DBService:
    """Returns a singleton instance of the DBService."""
    return DBService()
