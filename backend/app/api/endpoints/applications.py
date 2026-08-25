from typing import Optional
import asyncio
import logging
from fastapi import APIRouter, Depends, Query
from app.api.dependencies import get_current_user
from app.services.job_app_repository import get_job_app_repo

router = APIRouter()

logger = logging.getLogger(__name__)

@router.get("")
async def list_applications(
    status: Optional[str] = Query(None, description="Filter by status"),
    user_id: str = Depends(get_current_user),
):
    repo = get_job_app_repo()
    return await repo.get_applications_for_user(user_id=user_id, status=status)

