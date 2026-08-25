import asyncio
import logging
from datetime import datetime

from app.core.supabase_client import get_supabase_admin_client

logger = logging.getLogger(__name__)


class JobApplicationRepository:
    def __init__(self):
        self.client = get_supabase_admin_client()
        
    async def find_candidate_applications(self, user_id: str, company_normalized: str) -> list[dict]:
        """Finds all existing job applications for a user that matches a specific company"""

        def _query():
            response = (
                self.client.table("job_applications")
                .select("id, role_title, status, last_email_at")
                .eq("user_id", user_id)
                .eq("company_normalized", company_normalized)
                .execute()
            )
            return response.data

        try:
            return await asyncio.to_thread(_query)
        except Exception as error:
            logger.error("Failed to look up candidates for user %s: %s", user_id, error)
            return []

    async def create_application(
        self, user_id: str, company_normalized: str, role_title: str | None,
         status: str, last_email_at: datetime,
    ) -> dict | None:
        """If application not found in user's portal, then create a new job application post for them."""

        def _insert():
            response = (
                self.client.table("job_applications")
                .insert({
                    "user_id": user_id,
                    "company_normalized": company_normalized,
                    "role_title": role_title,
                    "status": status,
                    "last_email_at": last_email_at.isoformat(),
                })
                .execute()
            )
            return response.data[0] if response.data else None

        try:
            return await asyncio.to_thread(_insert)
        except Exception as error:
            logger.error("Failed to create application for user %s: %s", user_id, error)
            return None

    async def update_status(self, application_id: str, new_status: str, last_email_at: datetime) -> None:
        """Updates status of existing job application if a follow-up email is found."""

        def _update():
            self.client.table("job_applications").update({
                "status": new_status,
                "last_email_at": last_email_at.isoformat(),
            }).eq("id", application_id).execute()

        try:
            await asyncio.to_thread(_update)
        except Exception as error:
            logger.error("Failed to update application %s: %s", application_id, error)

    async def record_app(
        self, application_id: str, user_id: str, gmail_message_id: str,
        inferred_status: str, subject: str | None = None,
        received_at: datetime | None = None, summary: str | None = None,
    ) -> None:
        """Records user job application history"""
        
        def _insert():
            self.client.table("job_application_history").upsert({
                "application_id": application_id,
                "user_id": user_id,
                "gmail_message_id": gmail_message_id,
                "subject": subject,
                "received_at": received_at.isoformat() if received_at else None,
                "summary": summary,
                "inferred_status": inferred_status,
            }, on_conflict="user_id,gmail_message_id").execute()

        try:
            await asyncio.to_thread(_insert)
        except Exception as error:
            logger.error(
                "Failed to record event for message %s (user %s): %s",
                gmail_message_id, user_id, error,
            )
    async def get_applications_for_user(self, user_id: str, status: str | None = None) -> list[dict]:
        def _query():
            query = self.client.table("job_applications").select("*").eq("user_id", user_id)
            if status:
                query = query.eq("status", status)
            response = query.order("last_email_at", desc=True).execute()
            return response.data

        try:
            return await asyncio.to_thread(_query)
        except Exception as error:
            logger.error("Failed to fetch applications for user %s: %s", user_id, error)
            return []

def get_job_app_repo() -> JobApplicationRepository:
    return JobApplicationRepository()