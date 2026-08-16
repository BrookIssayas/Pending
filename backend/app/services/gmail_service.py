import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from app.services.google_auth_service import GoogleAuthService

logger = logging.getLogger(__name__)

RETRYABLE_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "backendError"}
BATCH_LIMIT = 50
THROTTLE_SECONDS = 2.0
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2.0

RETRYABLE_STATUSES = {429, 500, 502, 503, 504}

class GmailService:
    """Service for interacting with the Gmail API."""

    def __init__(self, user_id: str, auth_service: GoogleAuthService, service: Resource):
        self.user_id = user_id
        self.auth_service = auth_service
        self.service = service

    @classmethod
    async def create(cls, user_id: str) -> "GmailService":
        auth_service = GoogleAuthService(user_id)
        service = await auth_service.initialize_service()
        return cls(user_id, auth_service, service)

    async def get_user_messages(self, filter_time: datetime) -> list[dict]:
        """Fetch full message data for all messages newer than filter_time.

        Paginates through messages.list, then fetches each message via
        batched, throttled, retry-safe calls to messages.get.
        """
        query = f"after:{int(filter_time.timestamp())}"
        message_ids = await self._list_message_ids(query)
        logger.info("Found %d messages for user %s since %s", len(message_ids), self.user_id, filter_time)

        if not message_ids:
            return []

        messages, failed_ids = await self._fetch_messages_in_batches(message_ids)

        if failed_ids:
            logger.warning(
                "Gave up on %d message(s) for user %s after %d retries: %s",
                len(failed_ids), self.user_id, MAX_RETRIES, failed_ids,
            )

        return messages

    async def _list_message_ids(self, query: str) -> list[str]:
        """Paginate messages.list to collect all matching message IDs."""

        def _list_all() -> list[str]:
            ids = []
            request = self.service.users().messages().list(userId="me", q=query, maxResults=500)
            while request is not None:
                response = request.execute()
                ids.extend(m["id"] for m in response.get("messages", []))
                request = self.service.users().messages().list_next(request, response)
            return ids

        try:
            return await asyncio.to_thread(_list_all)
        except HttpError as error:
            logger.error("Error listing messages for user %s: %s", self.user_id, error)
            return []

    async def _fetch_messages_in_batches(self, message_ids: list[str]) -> tuple[list[dict], list[str]]:
        """Fetch messages via batch requests, retrying retryable failures with backoff."""
        messages: list[dict] = []
        ids_to_fetch = message_ids
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_RETRIES + 1):
            if not ids_to_fetch:
                break

            if attempt > 0:
                logger.info(
                    "Retrying %d message(s) for user %s, attempt %d...",
                    len(ids_to_fetch), self.user_id, attempt,
                )
                await asyncio.sleep(retry_delay)
                retry_delay *= 2

            fetched, retryable_failures, permanent_failures = await self._run_batches(ids_to_fetch)
            messages.extend(fetched)

            for msg_id, exception in permanent_failures:
                logger.error("Permanently failed to fetch message %s for user %s", msg_id, self.user_id, self._describe_error(exception))

            ids_to_fetch = retryable_failures

        return messages, ids_to_fetch

    async def _run_batches(self, message_ids: list[str]) -> tuple[list[dict], list[str], list[str]]:
        """Execute one throttled pass of batched messages.get calls over message_ids."""
        fetched: list[dict] = []
        retryable_failures: list[str] = []
        permanent_failures: list[str] = []

        def _process_message(request_id, response, exception):
            if exception is not None:
                if self._is_retryable_error(exception):
                    retryable_failures.append(request_id)
                else:
                    permanent_failures.append((request_id, exception))
            else:
                fetched.append(response)

        def _run_all_batches():
            for i in range(0, len(message_ids), BATCH_LIMIT):
                chunk = message_ids[i:i + BATCH_LIMIT]
                batch = self.service.new_batch_http_request(callback=_process_message)
                for msg_id in chunk:
                    batch.add(
                        self.service.users().messages().get(userId="me", id=msg_id),
                        request_id=msg_id,
                    )
                batch.execute()
                if i + BATCH_LIMIT < len(message_ids):
                    time.sleep(THROTTLE_SECONDS)

        await asyncio.to_thread(_run_all_batches)
        return fetched, retryable_failures, permanent_failures

    @staticmethod
    def _is_retryable_error(exception: Exception) -> bool:
        if not isinstance(exception, HttpError):
            return False
        if exception.resp.status in RETRYABLE_STATUSES:
            return True
        try:
            reason = exception.error_details[0].get("reason", "")
        except (AttributeError, IndexError, KeyError, TypeError):
            reason = ""
        return reason in RETRYABLE_REASONS
    @staticmethod
    def _describe_error(exception: Exception) -> str:
        if isinstance(exception, HttpError):
            try:
                reason = exception.error_details[0].get("reason", "unknown")
            except (AttributeError, IndexError, KeyError, TypeError):
                reason = "unknown"
            return f"status={exception.resp.status} reason={reason}"
        return f"{type(exception).__name__}: {exception}"

# --- Main Execution (for testing) ---

if __name__ == "__main__":
    import asyncio

    async def main():
        print("Initializing GmailService...")
        gmail_service_instance = await GmailService.create(user_id="97345709-7b19-48a6-bfc7-0079aeabb946")
        print("GmailService initialized successfully and service client obtained.")
        try:
            messages = await gmail_service_instance.get_user_messages(datetime.now() - timedelta(days=7))
            for x in messages:
                print(x["snippet"])
        except Exception as e:
            print(f"Error during test API call via GmailService: {e}")

    asyncio.run(main())