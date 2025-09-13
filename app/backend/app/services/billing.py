from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Iterable, Tuple

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.models.bot_instance import UserBotInstance
from app.models.instance_status_event import InstanceStatusEvent
from app.models.bot import Bot
from app.models.user import User
from app.models.enums import InstanceStatus
from app.services.external_client import ext_deactivate_instance
from app.core.config import settings
from app.core.locks import RedisLock

SECONDS_PER_DAY = 86400

BILLABLE = set(settings.BILLABLE_STATUSES or ("active",))

def _ceil_div(n: int, d: int) -> int:
    return (n + d - 1) // d

def _periods_from_events(
    events: list[InstanceStatusEvent],
    window_start: datetime,
    window_end: datetime,
    start_status: InstanceStatus,
) -> list[Tuple[datetime, datetime, InstanceStatus]]:
    """
    Build contiguous status periods within [window_start, window_end),
    starting from start_status and applying events in order.
    """
    periods: list[Tuple[datetime, datetime, InstanceStatus]] = []
    cur_start = window_start
    cur_status = start_status

    for ev in events:
        t = ev.changed_at
        # ignore events outside window or at/before start
        if t is None or t <= cur_start or t >= window_end:
            # but if it sets a new status before window_end and after start, we still need to update status
            if t and t <= window_start and ev.to_status:
                try:
                    cur_status = InstanceStatus(ev.to_status)
                except Exception:
                    cur_status = InstanceStatus.unknown
            continue
        # close current slice at event time
        periods.append((cur_start, t, cur_status))
        # start a new slice with new status
        try:
            cur_status = InstanceStatus(ev.to_status)
        except Exception:
            cur_status = InstanceStatus.unknown
        cur_start = t

    # tail
    if cur_start < window_end:
        periods.append((cur_start, window_end, cur_status))
    return periods

async def _starting_status(
    db: AsyncSession,
    inst: UserBotInstance,
    window_start: datetime,
) -> InstanceStatus:
    """
    Determine status at window_start: take the latest event <= window_start, else instance.status.
    """
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
    res = await db.execute(q)
    ev = res.scalar()
    if ev:
        try:
            return InstanceStatus(ev.to_status)
        except Exception:
            return InstanceStatus.unknown
    return inst.status

async def _bill_once_for_period(
    db: AsyncSession,
    inst: UserBotInstance,
    user: User,
    bot: Bot,
    period_end: datetime,
) -> bool:
    """
    Bill for [period_end - 24h, period_end). Returns True if billed or no charge,
    False if insufficient (status updated).
    """
    period_start = period_end - timedelta(days=1)
    # Clip to instance lifetime
    if inst.created_at and period_end <= inst.created_at:
        # instance didn't exist — no charge, move schedule forward
        inst.last_charge_at = period_end
        inst.next_charge_at = period_end + timedelta(days=1)
        return True

    window_start = max(period_start, inst.created_at or period_start)

    # Fetch events in window (and just before)
    q = (
        select(InstanceStatusEvent)
        .where(
            and_(
                InstanceStatusEvent.instance_id == inst.id,
                InstanceStatusEvent.changed_at >= window_start - timedelta(days=30),  # small cushion
                InstanceStatusEvent.changed_at <= period_end,
            )
        )
        .order_by(InstanceStatusEvent.changed_at.asc())
    )
    res = await db.execute(q)
    events = list(res.scalars())

    # Determine starting status at window_start
    start_status = await _starting_status(db, inst, window_start)

    # Build periods and sum billable seconds
    periods = _periods_from_events(events, window_start, period_end, start_status)
    billable_seconds = 0
    for a, b, s in periods:
        if s.value in BILLABLE:
            billable_seconds += int((b - a).total_seconds())

    # Compute prorated charge: ceil( rate * billable_seconds / (30*86400) )
    numerator = bot.rate * billable_seconds
    denominator = 30 * SECONDS_PER_DAY
    charge = _ceil_div(numerator, denominator) if numerator > 0 else 0

    # Update scheduling markers first
    inst.last_charge_at = period_end
    inst.next_charge_at = period_end + timedelta(days=1)

    if charge == 0:
        return True  # nothing to bill for this period

    # Check balance
    if user.balance < charge:
        # Mark instance as not_enough_balance (only if changed) and best-effort deactivate remote
        prev = inst.status
        if prev != InstanceStatus.not_enough_balance:
            inst.status = InstanceStatus.not_enough_balance
            db.add(
                InstanceStatusEvent(
                    instance_id=inst.id,
                    from_status=prev.value if prev else None,
                    to_status=InstanceStatus.not_enough_balance.value,
                )
            )
            # Do not await here inside a DB txn; we’ll do it after commit in caller.
        return False

    # Deduct
    user.balance -= charge
    return True

async def _bill_instance_until_caught_up(
    db: AsyncSession,
    inst: UserBotInstance,
    user: User,
    bot: Bot,
    now: datetime,
) -> Tuple[bool, bool]:
    """
    Processes all due periods up to 'now'.
    Returns (ok, deactivated_remote):
      ok=True if all periods billed/zero-charged; ok=False if stopped due to insufficient funds.
      deactivated_remote=True if we changed status to not_enough_balance and should deactivate remotely.
    """
    deact = False
    # If schedule isn't set, initialize
    if not inst.next_charge_at:
        base = (inst.created_at or now) + timedelta(days=1)
        inst.next_charge_at = base

    # Iterate missed periods
    while inst.next_charge_at and inst.next_charge_at <= now:
        period_end = inst.next_charge_at
        ok = await _bill_once_for_period(db, inst, user, bot, period_end)
        if not ok:
            deact = True
            break  # stop further billing until user tops up

    return (not deact), deact

async def process_due_instances(now: datetime | None = None):
    """
    Entry point: scan all instances with next_charge_at <= now and bill.
    Protected by a Redis lock so only one worker runs at a time.
    """
    now = now or datetime.now(timezone.utc)

    # lock
    lock = RedisLock("billing:lock", settings.BILLING_LOCK_TTL_SECONDS)
    async with lock as acquired:
        if not acquired:
            return  # another worker is active

        async with async_session() as db:
            # Fetch due instances + join user & bot
            q = (
                select(UserBotInstance, User, Bot)
                .join(User, User.id == UserBotInstance.user_id)
                .join(Bot, Bot.id == UserBotInstance.bot_id)
                .where(UserBotInstance.next_charge_at <= now)
                .order_by(UserBotInstance.id.asc())
            )
            res = await db.execute(q)
            rows = res.all()

            # We’ll best-effort deactivate remote after commit if needed
            to_deactivate: list[str] = []

            for inst, user, bot in rows:
                try:
                    await db.begin()
                    ok, need_deact = await _bill_instance_until_caught_up(db, inst, user, bot, now)
                    await db.commit()
                    if need_deact:
                        to_deactivate.append(inst.instance_id)
                except Exception:
                    await db.rollback()
                    # continue to next instance; could log error

            # Best-effort remote deactivation outside transaction
            for rid in to_deactivate:
                try:
                    await ext_deactivate_instance(rid)
                except Exception:
                    pass
