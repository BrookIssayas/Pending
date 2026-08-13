import logging
from typing import Optional

from googleapiclient.discovery import Resource

from app.services.google_auth_service import GoogleAuthService

logger = logging.getLogger(__name__)


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

    def get_service(self) -> Resource:
        """Returns the Gmail API service client."""
        return self.service


# --- Main Execution (for testing) ---

if __name__ == "__main__":
    import asyncio

    async def main():
        print("Initializing GmailService...")
        gmail_service_instance = await GmailService.create(user_id="97345709-7b19-48a6-bfc7-0079aeabb946")
        service_client = gmail_service_instance.get_service()

        print("GmailService initialized successfully and service client obtained.")
        try:
            results = service_client.users().labels().list(userId="me").execute()
            labels = results.get("labels", [])
            if not labels:
                print("No labels found via GmailService.")
            else:
                print("Labels (via GmailService):")
                for label in labels:
                    print(label["name"])
        except Exception as e:
            print(f"Error during test API call via GmailService: {e}")

    asyncio.run(main())