# app/services/sync_schedule_service.py
# CHANGED: next-sync estimate now snaps to the next fixed-schedule
# occurrence after the user's last actual sync, instead of a rolling
# +24h offset — keeps the displayed time anchored to the intended
# schedule rather than drifting with each day's actual completion time.

from datetime import datetime, timezone, timedelta

SYNC_HOUR_UTC = 21  # 7:00 UTC = midnight PDT (drifts to 11pm Pacific during
                    # PST months). Fallback only, used before any sync
                 # has ever completed for this user.
SYNC_MINUTE_UTC = 22


def _next_scheduled_occurrence_after(anchor: datetime) -> datetime:
    candidate = anchor.replace(hour=SYNC_HOUR_UTC, minute=SYNC_MINUTE_UTC, second=0, microsecond=0)
    if candidate <= anchor:
        candidate += timedelta(days=1)
    return candidate


def get_next_sync_estimate(last_actual_sync: datetime | None, now: datetime | None = None) -> datetime:
    """Estimates this user's next sync time. Anchored to the fixed daily
    schedule, computed relative to their last actual successful sync
    (or now, if they've never synced) — not a rolling +24h from actual
    completion time, so the estimate stays aligned with the intended
    schedule rather than tracking each day's variable duration.
    """
    anchor = last_actual_sync if last_actual_sync is not None else (now or datetime.now(timezone.utc))
    return _next_scheduled_occurrence_after(anchor)