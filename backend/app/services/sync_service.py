import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.core.supabase_client import get_supabase_admin_client

logger = logging.getLogger(__name__)

DEFAULT_BACKFILL_DAYS = 7  # how far back to look for users with no prior sync


class UserEmailSyncStateService:
    """Tracks per-user Gmail sync watermarks so each user's processing
    picks up exactly where their last successful run left off."""

    def __init__(self):
        self.client = get_supabase_admin_client()

    async def get_filter_time(self, user_id: str) -> datetime:
        """Returns the timestamp to fetch messages after for this user.
        Falls back to a default backfill window if no prior sync exists."""

        def _get_sync() -> dict | None:
            response = (
                self.client.table("user_email_sync_state")
                .select("last_synced_at, last_sync_status")
                .eq("user_id", user_id)
                .maybe_single()
                .execute()
            )
            return response.data if response else None

        try:
            row = await asyncio.to_thread(_get_sync)
        except Exception as error:
            logger.error("Failed to fetch sync state for user %s: %s", user_id, error)
            row = None

        if row and row.get("last_synced_at"):
            if datetime.fromisoformat(row["last_synced_at"]) < datetime.now(timezone.utc) - timedelta(days=DEFAULT_BACKFILL_DAYS):
                return datetime.fromisoformat(row["last_synced_at"])

        # No prior sync or last sync is too old, so return a default backfill window
        return datetime.now(timezone.utc) - timedelta(days=DEFAULT_BACKFILL_DAYS)

    async def mark_synced(
        self,
        user_id: str,
        synced_at: datetime,
        status: str = "success",
    ) -> None:
        """Upserts the watermark. Call this ONLY after a user's fetch+process
        run actually succeeds — advancing on failure silently skips emails."""

        def _upsert():
            self.client.table("user_email_sync_state").upsert(
                {
                    "user_id": user_id,
                    "last_synced_at": synced_at.isoformat(),
                    "last_sync_status": status,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ).execute()

        try:
            await asyncio.to_thread(_upsert)
        except Exception as error:
            logger.error("Failed to update sync state for user %s: %s", user_id, error)

    async def mark_failed(self, user_id: str) -> None:
        """Records a failed run WITHOUT advancing last_synced_at, so the
        next run retries from the same point rather than skipping emails."""

        def _upsert_status_only():
            self.client.table("user_email_sync_state").upsert(
                {
                    "user_id": user_id,
                    "last_sync_status": "failed",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="user_id",
                ignore_duplicates=False,
            ).execute()

        try:
            await asyncio.to_thread(_upsert_status_only)
        except Exception as error:
            logger.error("Failed to mark sync failure for user %s: %s", user_id, error)

def get_sync_service() -> UserEmailSyncStateService:
    """Returns a singleton instance of the SyncService."""
    return UserEmailSyncStateService()