import logging
from typing import Optional

from app.core.supabase_client import get_supabase_admin_client
from postgrest import APIResponse

logger = logging.getLogger(__name__)


class DBService:
    """Service for database operations."""

    def __init__(self) -> None:
        """Initializes the DBService."""
        self.client = get_supabase_admin_client()

    async def get_provider_token(
        self, user_id: str, provider: str
    ) -> Optional[dict]:
        """Retrieves a provider token for a user."""

        try:
            response = (
                self.client.table("user_provider_tokens")
                .select("*")
                .eq("user_id", user_id)
                .eq("provider", provider)
                .maybe_single()
                .execute()
            )
            if response is None or response.data is None:
                return None
            return response.data
        except Exception as e:
            logger.error(
                f"Error fetching provider token for user {user_id}, "
                f"provider {provider}: {e!s}"
            )
            raise
        
    async def upsert_provider_token(
        self,
        user_id: str,
        provider: str,
        access_token: str,
        refresh_token: Optional[str] = None,
    ) -> APIResponse:
        """Upserts a provider token for a user."""

        try:
            payload = {
                "user_id": user_id,
                "provider": provider,
                "access_token": access_token,
            }
            if refresh_token is not None:
                payload["refresh_token"] = refresh_token

            response = (
                self.client.table("user_provider_tokens")
                .upsert(payload, on_conflict="user_id")
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
