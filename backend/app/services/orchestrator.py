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
        succeeded_user_ids = await self.ai.classify_users_in_chunks(user_emails)

        for user_id in succeeded_user_ids:
            await self.ingestion.confirm_synced(user_id)

if __name__ == "__main__":
    import asyncio
    import logging

    async def main():
        orchestrator = DailySyncOrchestrator()
        await orchestrator.run()

    asyncio.run(main())