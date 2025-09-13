import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session
from app.models.bot_instance import UserBotInstance
from app.models.enums import InstanceStatus
from app.models.instance_status_event import InstanceStatusEvent
from app.services.external_client import ext_health
from app.core.config import settings

def _normalize_status(s: str) -> InstanceStatus:
    s = (s or "").lower()
    if s in InstanceStatus.__members__:
        return InstanceStatus[s]
    # map external string → enum value
    try:
        return InstanceStatus(s)  # may raise
    except Exception:
        return InstanceStatus.unknown

async def _handle_instance(db: AsyncSession, inst: UserBotInstance, new_status: InstanceStatus):
    if inst.status == new_status:
        return
    prev = inst.status.value
    inst.status = new_status
    db.add(InstanceStatusEvent(instance_id=inst.id, from_status=prev, to_status=new_status.value))

async def poll_once():
    sem = asyncio.Semaphore(settings.HEALTH_CONCURRENCY)
    async with async_session() as db:
        res = await db.execute(select(UserBotInstance))
        instances = list(res.scalars())

        async def check(inst: UserBotInstance):
            async with sem:
                try:
                    s = await ext_health(inst.instance_id)
                    ns = _normalize_status(s)
                    await _handle_instance(db, inst, ns)
                except Exception:
                    # mark unknown on failure
                    await _handle_instance(db, inst, InstanceStatus.unknown)

        await asyncio.gather(*(check(i) for i in instances))
        await db.commit()

async def run_poller(stop_event: asyncio.Event):
    try:
        while not stop_event.is_set():
            await poll_once()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=settings.HEALTH_POLL_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                continue
    except asyncio.CancelledError:
        pass
