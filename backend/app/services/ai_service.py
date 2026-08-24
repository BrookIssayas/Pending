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


class Pass1Item(BaseModel):
    email_id: str
    is_job_related: bool
    company_normalized: Optional[str] = None

class Pass2Event(BaseModel):
    email_id: str
    inferred_status: Literal["Applied", "Interviewing", "Rejected", "Offer"]

class Pass2Application(BaseModel):
    company_normalized: str
    matches_existing_index: Optional[int] = None
    role_title: Optional[str] = None
    final_status: Literal["Applied", "Interviewing", "Rejected", "Offer"]
    events: list[Pass2Event]

class Pass2Response(BaseModel):
    applications: list[Pass2Application]


class AIService:
    """Two-pass Gemini classification, scoped to one user's emails at a time."""

    def __init__(self):
        settings = get_settings()
        self.repo = get_job_app_repo()
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def classify_user_emails(self, user_id: str, emails: list[dict]) -> None:
        if not emails:
            return

        pass1_results = await self._run_pass1(emails)
        job_related = [r for r in pass1_results if r.is_job_related and r.company_normalized]
        if not job_related:
            logger.info("No job-related emails for user %s", user_id)
            return

        emails_by_id = {e["id"]: e for e in emails}

        by_company: dict[str, list[dict]] = defaultdict(list)
        for result in job_related:
            email = emails_by_id.get(result.email_id)
            if email is None:
                logger.warning("Pass 1 returned unknown email_id %s for user %s", result.email_id, user_id)
                continue
            by_company[result.company_normalized].append(email)

        if not by_company:
            return

        company_groups = []
        for company_normalized, company_emails in by_company.items():
            candidates = await self.repo.find_candidate_applications(
                user_id=user_id, company_normalized=company_normalized
            )
            company_groups.append({
                "company_normalized": company_normalized,
                "candidates": candidates,
                "emails": sorted(
                    company_emails,
                    key=lambda e: e.get("received_at") or datetime.min.replace(tzinfo=timezone.utc),
                ),
            })

        pass2_response = await self._run_pass2(company_groups)
        if pass2_response is None:
            return

        await self._write_results(user_id, company_groups, pass2_response, emails_by_id)

    async def _run_pass1(self, emails: list[dict]) -> list[Pass1Item]:
        blocks = [
            f'--- EMAIL:{e["id"]} ---\n'
            f'From: {e.get("sender") or "unknown"}\n'
            f'Subject: {e.get("subject") or "(no subject)"}\n'
            f'{e["body"]}'
            for e in emails
        ]
        prompt = f"""For each email below, determine:
                    1. is_job_related: true ONLY if the email reports on a job application
                    the person has — application confirmations, interview
                    invitations/scheduling, rejections, or offers.

                    Set this to FALSE for anything else related to job platforms, even though it
                    may look adjacent to a job search, including:
                    - Account/registration emails: "Verify your email", "Welcome to [platform]",
                        "Complete your profile"
                    - Reminders or nudges: "Don't forget to finish your application", "Your
                        application is incomplete"
                    - Job recommendations or alerts: "Jobs you may be interested in", "New
                        postings matching your search"
                    - Marketing or newsletter content from job boards or ATS platforms
                    - Password resets, security alerts, or other account-management emails
                    - General correspondence that doesn't reference a specific application's
                        status (e.g. a recruiter cold-outreach message before any application
                        exists)

                    These should be FALSE even if they come from a known job platform or ATS
                    sender (Greenhouse, Workday, LinkedIn, etc.) — the sender alone does not
                    make an email job-related; it must report an actual status update on a
                    specific submitted application.

                    2. company_normalized: the hiring company's name, lowercased, with legal suffixes
                    (Inc/LLC/Corp/Ltd) removed. Null if not job-related.

                    Include every email exactly once, using its EMAIL id.
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
            return response.parsed or []

        try:
            return await asyncio.to_thread(_call)
        except Exception as error:
            logger.error("Pass 1 classification failed: %s", error)
            return []

    async def _run_pass2(self, company_groups: list[dict]) -> Optional[Pass2Response]:
        blocks = []
        for group in company_groups:
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
                f'=== COMPANY: {group["company_normalized"]} ===\n'
                f'Existing applications at this company:\n{candidates_text}\n\n'
                f'New emails at this company (chronological order):\n{emails_text}'
            )

        prompt = f"""For each company, you are given any existing applications already on
                    file, plus new emails received from that company. Determine how the new emails
                    map onto applications, and each application's final status.

                    - Multiple new emails at the same company usually belong to the SAME application
                    (e.g. an online assessment invite, a confirmation the OA was completed, and a
                    later rejection are typically one application's lifecycle) — group them
                    together rather than treating each as a separate application.
                    - Only treat emails as separate applications if they clearly indicate different
                    roles, or there's no reasonable way they refer to the same role.
                    - If an existing application is listed and a new email plausibly continues it
                    (role matches, or role is unstated), attach the new email(s) to that existing
                    application instead of creating a new one.
                    - role_title only needs to be extracted for NEW applications (no matches_existing_index).
                    - final_status must reflect where the application ends up after considering ALL
                    of its new emails together in chronological order — a later rejection
                    overrides an earlier interview invite, for example.
                    - For each email, also record its own inferred_status (what that specific email
                    indicates on its own) for audit history, even if it differs from final_status.

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
            return response.parsed

        try:
            return await asyncio.to_thread(_call)
        except Exception as error:
            logger.error("Pass 2 classification failed: %s", error)
            return None

    async def _write_results(
        self, user_id: str, company_groups: list[dict],
        pass2_response: Pass2Response, emails_by_id: dict[str, dict],
    ) -> None:
        candidates_by_company = {g["company_normalized"]: g["candidates"] for g in company_groups}

        for app in pass2_response.applications:
            candidates = candidates_by_company.get(app.company_normalized, [])
            latest_time = self._latest_received_at(app.events, emails_by_id)

            if app.matches_existing_index is not None:
                if not (0 <= app.matches_existing_index < len(candidates)):
                    logger.warning(
                        "Pass 2 gave out-of-range candidate index %s for company %s (user %s)",
                        app.matches_existing_index, app.company_normalized, user_id,
                    )
                    continue
                application_id = candidates[app.matches_existing_index]["id"]
                await self.repo.update_status(
                    application_id=application_id, new_status=app.final_status,
                    last_email_at=latest_time,
                )
            else:
                created = await self.repo.create_application(
                    user_id=user_id, company_normalized=app.company_normalized,
                    role_title=app.role_title, status=app.final_status,
                    last_email_at=latest_time,
                )
                if created is None:
                    logger.error("Failed to create application for company %s (user %s)", app.company_normalized, user_id)
                    continue
                application_id = created["id"]

            for event in app.events:
                email = emails_by_id.get(event.email_id)
                if email is None:
                    continue
                await self.repo.record_app(
                    application_id=application_id, user_id=user_id,
                    gmail_message_id=email["id"], inferred_status=event.inferred_status,
                    subject=email.get("subject"), received_at=email.get("received_at"),
                    summary=email["body"][:200],
                )

    @staticmethod
    def _latest_received_at(events: list[Pass2Event], emails_by_id: dict[str, dict]) -> datetime:
        times = [
            emails_by_id[e.email_id]["received_at"]
            for e in events
            if e.email_id in emails_by_id and emails_by_id[e.email_id].get("received_at")
        ]
        return max(times) if times else datetime.now(timezone.utc)

if __name__ == "__main__":
    import asyncio
    import logging

    from app.services.email_ingestion_service import EmailIngestionService

    logging.basicConfig(level=logging.INFO)

    async def main():
        ingestion = EmailIngestionService()
        ai_service = AIService()

        user_emails = await ingestion.fetch_all_user_emails()

        for user_id, emails in user_emails.items():
            print(f"\n=== User: {user_id} ({len(emails)} emails fetched) ===")
            if not emails:
                print("  No new emails.")
                continue

            try:
                await ai_service.classify_user_emails(user_id, emails)
                await ingestion.confirm_synced(user_id)
            except Exception as error:
                print(f"  Classification failed: {error}")
                continue

            def _fetch_applications():
                return (
                    ai_service.repo.client.table("job_applications")
                    .select("*")
                    .eq("user_id", user_id)
                    .execute()
                )

            result = await asyncio.to_thread(_fetch_applications)
            applications = result.data

            if not applications:
                print("  No job applications detected.")
            else:
                for app in applications:
                    print(f"  [{app['status']}] {app['company_normalized']} — {app.get('role_title') or 'unknown role'}")

    asyncio.run(main())