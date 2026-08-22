import logging
from datetime import datetime, timedelta
import re
from google import genai
from app.services.gmail_service import html_to_text, GmailService
from app.services.db_service import get_db_service
from app.services.sync_service import get_sync_service

logger = logging.getLogger(__name__)


class EmailIngestionService:
    """Fetches and trims each user's Gmail messages. No AI involved at this stage."""

    def __init__(self):
        self.db_service = get_db_service()
        self.sync_service = get_sync_service()

    async def fetch_all_user_emails(self) -> dict[str, list[dict]]:
        user_ids = await self.db_service.get_all_user_ids()
        user_emails: dict[str, list[dict]] = {}

        for user_id in user_ids:
            filter_time = await self.sync_service.get_filter_time(user_id=user_id)
            run_started_at = datetime.now()

            try:
                service = await GmailService.create(user_id=user_id)
                messages = await service.get_user_messages(filter_time)
            except Exception as error:
                logger.error("Failed to fetch messages for user %s: %s", user_id, error)
                await self.sync_service.mark_failed(user_id)
                continue # skip this user, keep processing the rest

            def summarize_message(msg):
                payload = msg.get("payload", {})
                body, kind = service.get_message_body(payload)
                text = html_to_text(body) if kind == "html" else (body or "")
                text = re.sub(r'\s+', ' ', text).strip()[:500]  # truncate here, always
                return {
                    "id": msg.get("id"),
                    "subject": msg.get("payload", {}).get("headers", []),
                    "body": text
                }
        
            trimmed_messages = [summarize_message(m) for m in messages]
            user_emails[user_id] = trimmed_messages

            self._pending_sync_times = getattr(self, "_pending_sync_times", {})
            self._pending_sync_times[user_id] = run_started_at

        return user_emails

    async def confirm_synced(self, user_id: str):
        """Only called once classification has succeeded for this user's emails"""
        run_started_at = self._pending_sync_times.get(user_id)
        if run_started_at:
            await self.sync_service.mark_synced(user_id, run_started_at)

if __name__ == "__main__":
    import asyncio

    async def main():
        object = EmailIngestionService()
        res = await object.fetch_all_user_emails()

        for k, v in res.items():
            print(f"User: {k}")
            for i in v:
                print(f"Email: {i["body"]}")     

    asyncio.run(main())