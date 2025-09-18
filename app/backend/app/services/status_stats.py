from __future__ import annotations
from datetime import datetime
from typing import List, Tuple
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instance_status_event import InstanceStatusEvent
from app.models.bot_instance import UserBotInstance
from app.models.enums import InstanceStatus
from app.core.config import settings

BILLABLE = set(settings.BILLABLE_STATUSES or ("active",))

def _clip_window_to_lifespan(
    inst: UserBotInstance, window_start: datetime, window_end: datetime
) -> tuple[datetime, datetime]:
    """
    Move window_start forward to the instance's created_at, and (optionally)
    clip window_end to a terminal timestamp if you have one (e.g., deleted_at).
    """
    created_at = getattr(inst, "created_at", None)
    if created_at:
        window_start = max(window_start, created_at)

    # If your model has a terminal timestamp, uncomment:
    # for attr in ("deleted_at", "archived_at", "deactivated_at"):
    #     dt = getattr(inst, attr, None)
    #     if dt:
    #         window_end = min(window_end, dt)

    return window_start, window_end

async def _starting_status(
    db: AsyncSession, inst: UserBotInstance, window_start: datetime
) -> InstanceStatus:
    q = (
        select(InstanceStatusEvent)
        .where(
            and_(
                InstanceStatusEvent.instance_id == inst.id,
                InstanceStatusEvent.changed_at <= window_start,
            )
        )
        .order_by(InstanceStatusEvent.changed_at.desc())
        .limit(1)
    )
    ev = (await db.execute(q)).scalar()
    if ev:
        try:
            return InstanceStatus(ev.to_status)
        except Exception:
            return InstanceStatus.unknown
    # If no prior events at/after creation, the instance existed and has this status
    return inst.status

def _build_periods(
    events: list[InstanceStatusEvent],
    window_start: datetime,
    window_end: datetime,
    start_status: InstanceStatus,
) -> list[tuple[datetime, datetime, InstanceStatus]]:
    periods: list[tuple[datetime, datetime, InstanceStatus]] = []
    cur_t = window_start
    cur_s = start_status
    for ev in events:
        t = ev.changed_at
        if not t or t <= cur_t:
            continue
        if t >= window_end:
            break
        periods.append((cur_t, t, cur_s))
        try:
            cur_s = InstanceStatus(ev.to_status)
        except Exception:
            cur_s = InstanceStatus.unknown
        cur_t = t
    if cur_t < window_end:
        periods.append((cur_t, window_end, cur_s))
    return periods

async def compute_status_stats(
    db: AsyncSession,
    inst: UserBotInstance,
    window_start: datetime,
    window_end: datetime,
    include_segments: bool = False,
):
    # 👇 NEW: clip the requested window to the instance lifetime
    window_start, window_end = _clip_window_to_lifespan(inst, window_start, window_end)

    # If the instance did not exist during the requested window → empty stats
    if window_start >= window_end:
        return {
            "window_start": window_start,
            "window_end": window_end,
            "total_seconds": 0,
            "seconds_by_status": {},
            "uptime_seconds": 0,
            "uptime_percent": 0.0,
            "segments": [] if include_segments else None,
        }

    # Pull only events within the clipped window
    q = (
        select(InstanceStatusEvent)
        .where(
            and_(
                InstanceStatusEvent.instance_id == inst.id,
                InstanceStatusEvent.changed_at >= window_start,
                InstanceStatusEvent.changed_at <= window_end,
            )
        )
        .order_by(InstanceStatusEvent.changed_at.asc())
    )
    events = list((await db.execute(q)).scalars())

    start_status = await _starting_status(db, inst, window_start)
    periods = _build_periods(events, window_start, window_end, start_status)

    seconds_by_status: dict[str, int] = {}
    uptime_seconds = 0
    for a, b, s in periods:
        secs = int((b - a).total_seconds())
        seconds_by_status[s.value] = seconds_by_status.get(s.value, 0) + secs
        if s.value in BILLABLE:
            uptime_seconds += secs

    total_seconds = int((window_end - window_start).total_seconds())
    uptime_percent = (uptime_seconds / total_seconds * 100.0) if total_seconds > 0 else 0.0

    segments = None
    if include_segments:
        from app.schemas.stats import StatusSegmentOut
        segments = [
            StatusSegmentOut(start=a, end=b, status=s, seconds=int((b - a).total_seconds()))
            for a, b, s in periods
        ]

    return {
        "window_start": window_start,
        "window_end": window_end,
        "total_seconds": total_seconds,
        "seconds_by_status": seconds_by_status,
        "uptime_seconds": uptime_seconds,
        "uptime_percent": round(uptime_percent, 4),
        "segments": segments,
    }
