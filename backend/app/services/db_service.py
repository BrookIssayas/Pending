import asyncio
import logging
from typing import Optional
from datetime import datetime, timezone

from app.core.supabase_client import get_supabase_admin_client
from postgrest import APIResponse

logger = logging.getLogger(__name__)

PAGE_SIZE = 200

class DBService:
    """Service for database operations."""

    def __init__(self) -> None:
        """Initializes the DBService."""
        self.client = get_supabase_admin_client()

    async def get_all_user_ids(self) -> list[str]:
        """Fetch all user IDs from Supabase Auth, paginating through admin.list_users()."""
        def _list_all_sync() -> list[str]:
            ids: list[str] = []
            page = 1
            while True:
                response = self.client.auth.admin.list_users(page=page, per_page=PAGE_SIZE)
                
                users = response if isinstance(response, list) else getattr(response, "users", [])
                if not users:
                    break
                ids.extend(user.id for user in users)
                if len(users) < PAGE_SIZE:
                    break
                page += 1
            return ids

        try:
            user_ids = await asyncio.to_thread(_list_all_sync)
            logger.info("Fetched %d user IDs from Supabase Auth", len(user_ids))
            return user_ids
        except Exception as error:
            logger.error("Failed to fetch user IDs from Supabase Auth: %s", error)
            return []

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
                "updated_at": datetime.now(timezone.utc).isoformat()
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
