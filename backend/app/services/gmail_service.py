import asyncio
import logging
import time
import base64
from datetime import datetime, timedelta
from typing import Optional
import html2text
import re

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError

from app.services.google_auth_service import GoogleAuthService

logger = logging.getLogger(__name__)

RETRYABLE_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "backendError"}
BATCH_LIMIT = 50
THROTTLE_SECONDS = 2.0
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2.0

RETRYABLE_STATUSES = {429, 500, 502, 503, 504}

def html_to_text(html):
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    h.body_width = 0
    text = h.handle(html)

    INVISIBLE_CHARS = re.compile(
        '['
        '\u200a-\u200f'   # zero-width space, ZWNJ, ZWJ, LRM, RLM
        '\u2060-\u2064'   # word joiner, invisible operators
        '\u034f'          # combining grapheme joiner
        '\ufeff'          # BOM / zero-width no-break space
        '\u00ad'          # soft hyphen
        ']'
    )

    text = INVISIBLE_CHARS.sub('', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[<>]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()[:500]
    return text

def base64url_decode(payload):
    # Decode using the URL-safe method
    decoded_bytes = base64.urlsafe_b64decode(payload)
    return decoded_bytes.decode('utf-8')

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
            request = self.service.users().messages().list(userId="me", q=query, maxResults=500, includeSpamTrash=False)
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
        except RefreshError as error:
            logger.warning(
                "Google token refresh failed for user %s (likely revoked): %s",
                self.user_id, error,
            )
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
    def get_message_body(payload):
        """Recursively find text/plain, fall back to text/html."""
        if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
            return base64url_decode(payload["body"]["data"]), "plain"

        if payload.get("mimeType") == "text/html" and payload.get("body", {}).get("data"):
            return base64url_decode(payload["body"]["data"]), "html"

        plain_fallback = None
        for part in payload.get("parts", []) or []:
            body, kind = GmailService.get_message_body(part)
            if kind == "plain":
                return body, "plain"
            if kind == "html" and plain_fallback is None:
                return html_to_text(body), "html"

        return plain_fallback, "html" if plain_fallback else None

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