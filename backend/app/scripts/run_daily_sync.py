import asyncio
import logging

from app.services.orchestrator import DailySyncOrchestrator  

logging.basicConfig(level=logging.INFO)

async def main():
    orchestrator = DailySyncOrchestrator()
    await orchestrator.run()

if __name__ == "__main__":
    asyncio.run(main())