import logging
from app.services.email_ingestion_service import EmailIngestionService
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)

class DailySyncOrchestrator:
    def __init__(self):
        self.ingestion = EmailIngestionService()
        self.ai = AIService()

    async def run(self):
        user_emails = await self.ingestion.fetch_all_user_emails()

        for user_id, emails in user_emails.items():
            try:
                await self.ai.classify_user_emails(user_id, emails)
                await self.ingestion.confirm_synced(user_id)
            except Exception as error:
                logger.error("Classification failed for user %s: %s", user_id, error)
