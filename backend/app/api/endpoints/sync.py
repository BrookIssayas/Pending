# app/api/routes/sync.py
# CHANGED: now requires auth (matching /applications' pattern) since
# the response is per-user. I don't have your actual auth dependency
# — swap get_current_user for whatever /applications uses to extract
# the user from the bearer token.

from fastapi import APIRouter, Depends
from app.services.sync_service import get_sync_service
from app.services.sync_schedule_service import get_next_sync_estimate
from app.api.dependencies import get_current_user  

router = APIRouter()


@router.get("/next-refresh")
async def next_refresh(user_id=Depends(get_current_user)) -> dict:
    import traceback
    try:
        sync_service = get_sync_service()
        last_synced_at = await sync_service.get_last_sync_time(user_id=user_id)
        next_sync_at = get_next_sync_estimate(last_synced_at)
        return {
            "next_sync_at": next_sync_at.isoformat(),
            "last_synced_at": last_synced_at.isoformat() if last_synced_at else None,
        }
    except Exception:
        traceback.print_exc()
        raise