from collections import defaultdict
import asyncio
import logging
from datetime import datetime, timezone
from typing import Literal, Optional
from google import genai
from google.genai import types
from pydantic import BaseModel
from app.core.config import get_settings

from app.services.job_app_repository import get_job_app_repo

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3.6-flash"
CHUNK_SIZE = 20

GEMINI_RETRY_ATTEMPTS = 3  
GEMINI_RETRY_INITIAL_DELAY = 1.0  
GEMINI_RETRY_MAX_DELAY = 60.0  
GEMINI_RETRY_STATUS_CODES = [500, 502, 503, 504]


class Pass1Item(BaseModel):
    user_id: str
    email_id: str
    is_job_related: bool
    company_normalized: Optional[str] = None


class Pass2Event(BaseModel):
    email_id: str
    inferred_status: Literal["Applied", "Interviewing", "Rejected", "Offer"]


class Pass2Application(BaseModel):
    user_id: str
    company_normalized: str
    matches_existing_index: Optional[int] = None
    role_title: Optional[str] = None
    final_status: Literal["Applied", "Interviewing", "Rejected", "Offer"]
    events: list[Pass2Event]


class Pass2Response(BaseModel):
    applications: list[Pass2Application]


class AIService:
    """Two-pass Gemini classification, chunked into fixed-size user groups.

    RPD cost: 2 calls per chunk. At CHUNK_SIZE=20 and a 20 RPD budget, that's
    up to 10 chunks/day = up to 200 users — assuming each chunk's combined
    prompt stays under Gemini's TPM limit, which has not yet been verified
    against real email volume.
    """

    def __init__(self):
        settings = get_settings()
        self.repo = get_job_app_repo()
        self.client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(
                    attempts=GEMINI_RETRY_ATTEMPTS,
                    initial_delay=GEMINI_RETRY_INITIAL_DELAY,
                    max_delay=GEMINI_RETRY_MAX_DELAY,
                    http_status_codes=GEMINI_RETRY_STATUS_CODES,
                ),
            ),
        )

    async def classify_users_in_chunks(
        self, user_emails: dict[str, list[dict]], chunk_size: int = CHUNK_SIZE
    ) -> set[str]:
        """Splits users into fixed-size chunks, classifies each chunk with its
        own pass 1 + pass 2 call pair. Returns the user_ids whose chunk
        succeeded — only those should have their sync watermark advanced.
        A failed chunk doesn't affect any other chunk.
        """
        user_ids = list(user_emails.keys())
        chunks = [user_ids[i:i + chunk_size] for i in range(0, len(user_ids), chunk_size)]

        succeeded: set[str] = set()

        for chunk_num, chunk_user_ids in enumerate(chunks, start=1):
            chunk_emails = {uid: user_emails[uid] for uid in chunk_user_ids}
            try:
                await self._classify_chunk(chunk_emails)
                succeeded.update(chunk_user_ids)
            except Exception as error:
                logger.error(
                    "Chunk %d/%d failed (%d users) — will retry next run: %s",
                    chunk_num, len(chunks), len(chunk_user_ids), error,
                )
                # deliberately not added to `succeeded` — sync watermark stays put for these users

        return succeeded

    async def _classify_chunk(self, user_emails: dict[str, list[dict]]) -> None:
        all_emails: list[tuple[str, dict]] = [
            (user_id, email) for user_id, emails in user_emails.items() for email in emails
        ]
        if not all_emails:
            return

        pass1_results = await self._run_pass1(all_emails)
        job_related = [r for r in pass1_results if r.is_job_related and r.company_normalized]
        if not job_related:
            logger.info("No job-related emails in this chunk (%d users)", len(user_emails))
            return

        emails_by_key = {(uid, e["id"]): e for uid, e in all_emails}

        by_user_company: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for result in job_related:
            email = emails_by_key.get((result.user_id, result.email_id))
            if email is None:
                logger.warning(
                    "Pass 1 returned unknown (user_id, email_id): (%s, %s)",
                    result.user_id, result.email_id,
                )
                continue
            by_user_company[(result.user_id, result.company_normalized)].append(email)


        if not by_user_company:
            return

        groups = []
        for (user_id, company_normalized), company_emails in by_user_company.items():
            candidates = await self.repo.find_candidate_applications(
                user_id=user_id, company_normalized=company_normalized
            )
            groups.append({
                "user_id": user_id,
                "company_normalized": company_normalized,
                "candidates": candidates,
                "emails": sorted(
                    company_emails,
                    key=lambda e: e.get("received_at") or datetime.min.replace(tzinfo=timezone.utc),
                ),
            })

        pass2_response = await self._run_pass2(groups)
        if pass2_response is None:
            return

        await self._write_results(groups, pass2_response, emails_by_key)

    async def _run_pass1(self, all_emails: list[tuple[str, dict]]) -> list[Pass1Item]:
        blocks = [
            f'--- USER:{user_id} EMAIL:{e["id"]} ---\n'
            f'From: {e.get("sender") or "unknown"}\n'
            f'Subject: {e.get("subject") or "(no subject)"}\n'
            f'{e["body"]}'
            for user_id, e in all_emails
        ]
        prompt = f"""You will see emails from multiple users, each tagged with a USER id
                and an EMAIL id. For each email, determine:

                1. is_job_related: true ONLY if the email reports on a job application the
                person has — application confirmations, interview invitations/scheduling,
                rejections, or offers.

                Set this to FALSE for anything else related to job platforms, including:
                - Account/registration emails: "Verify your email", "Welcome to [platform]"
                - Reminders or nudges: "Don't forget to finish your application"
                - Job recommendations or alerts: "Jobs you may be interested in"
                - Marketing or newsletter content from job boards or ATS platforms
                - Password resets, security alerts, or account-management emails
                - General correspondence that doesn't reference a specific application's
                    status (e.g. recruiter cold-outreach before any application exists)

                FALSE even from a known ATS sender (Greenhouse, Workday, LinkedIn) unless
                it reports an actual status update on a specific submitted application.

                2. company_normalized: the hiring company's name, lowercased, with legal
                suffixes (Inc/LLC/Corp/Ltd) removed. Null if not job-related.

                Include every email exactly once, using its USER id and EMAIL id together.

                {"\n\n".join(blocks)}"""

        def _call():
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=list[Pass1Item],
                ),
            )

            if response.parsed is None:
                raise ValueError(
                    f"Pass 1 returned no parsed output "
                    f"(finish_reason={getattr(response.candidates[0], 'finish_reason', 'unknown') if response.candidates else 'no candidates'})"
                )
            return response.parsed
        return await asyncio.to_thread(_call)

    async def _run_pass2(self, groups: list[dict]) -> Optional[Pass2Response]:
        blocks = []
        for group in groups:
            candidates = group["candidates"]
            candidates_text = (
                "\n".join(
                    f'  [{i}] role_title: "{c.get("role_title") or "unknown"}", '
                    f'status: "{c["status"]}", last_email: {c["last_email_at"]}'
                    for i, c in enumerate(candidates)
                )
                if candidates else "  None — no existing application at this company."
            )
            emails_text = "\n\n".join(
                f'  EMAIL:{e["id"]} (received: {e.get("received_at") or "unknown"})\n'
                f'  Subject: {e.get("subject") or "(no subject)"}\n'
                f'  {e["body"]}'
                for e in group["emails"]
            )
            blocks.append(
                f'=== USER:{group["user_id"]} COMPANY:{group["company_normalized"]} ===\n'
                f'Existing applications at this company:\n{candidates_text}\n\n'
                f'New emails at this company (chronological order):\n{emails_text}'
            )

        prompt = f"""Each block below is one USER's emails at one COMPANY. Treat each
                USER+COMPANY block completely independently — never merge or compare across
                different USER ids, even if two users applied to the same company.

                For each block, determine how the new emails map onto applications, and each
                application's final status.

                - Multiple new emails at the same company usually belong to the SAME
                application — group them rather than treating each as separate.
                - Only treat emails as separate applications if they clearly indicate
                different roles, or there's no reasonable way they refer to the same role.
                - If an existing application is listed and a new email plausibly continues it,
                attach it instead of creating a new one.
                - role_title only needs to be extracted for NEW applications.
                - final_status must reflect where the application ends up after considering
                ALL of its new emails in chronological order.
                - Also record each email's own inferred_status for audit history.
                - Always include the USER id in your response, matching the block it came from.

                {"\n\n".join(blocks)}"""

        def _call():
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=Pass2Response,
                ),
            )
            if response.parsed is None:
                            raise ValueError(
                                f"Pass 2 returned no parsed output "
                                f"(finish_reason={getattr(response.candidates[0], 'finish_reason', 'unknown') if response.candidates else 'no candidates'})"
                            )
            return response.parsed


        return await asyncio.to_thread(_call)

    async def _write_results(
        self, groups: list[dict], pass2_response: Pass2Response,
        emails_by_key: dict[tuple[str, str], dict],
    ) -> None:
        candidates_by_key = {
            (g["user_id"], g["company_normalized"]): g["candidates"] for g in groups
        }

        for app in pass2_response.applications:
            key = (app.user_id, app.company_normalized)
            candidates = candidates_by_key.get(key, [])
            latest_time = self._latest_received_at(app.user_id, app.events, emails_by_key)
            if app.matches_existing_index is not None:
                if not (0 <= app.matches_existing_index < len(candidates)):
                    logger.warning(
                        "Pass 2 gave out-of-range candidate index %s for user %s company %s",
                        app.matches_existing_index, app.user_id, app.company_normalized,
                    )
                    continue
                application_id = candidates[app.matches_existing_index]["id"]
                await self.repo.update_status(
                    application_id=application_id, new_status=app.final_status,
                    last_email_at=latest_time,
                )
            else:
                created = await self.repo.create_application(
                    user_id=app.user_id, company_normalized=app.company_normalized,
                    role_title=app.role_title, status=app.final_status,
                    last_email_at=latest_time,
                )
                if created is None:
                    logger.error(
                        "Failed to create application for company %s (user %s)",
                        app.company_normalized, app.user_id,
                    )
                    continue
                application_id = created["id"]

            for event in app.events:
                email = emails_by_key.get((app.user_id, event.email_id))
                if email is None:
                    continue
                await self.repo.record_app(
                    application_id=application_id, user_id=app.user_id,
                    gmail_message_id=email["id"], inferred_status=event.inferred_status,
                    subject=email.get("subject"), received_at=email.get("received_at"),
                    summary=email["body"][:200],
                )

    @staticmethod
    def _latest_received_at(
        user_id: str, events: list[Pass2Event], emails_by_key: dict[tuple[str, str], dict],
    ) -> datetime:
        times = [
            emails_by_key[(user_id, e.email_id)]["received_at"]
            for e in events
            if (user_id, e.email_id) in emails_by_key
            and emails_by_key[(user_id, e.email_id)].get("received_at")
        ]
        return max(times) if times else datetime.now(timezone.utc)
