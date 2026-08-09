import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Job-Tracker API",
    description="Easy, accessible job-tracker service.",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add API Routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Return API service status for quick liveness checks."""
    return {"status": "ok", "version": "1.0.0"}