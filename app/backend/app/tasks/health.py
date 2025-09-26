import asyncio
from sqlalchemy import select
from app.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.models.bot_instance import UserBotInstance
from app.models.enums import InstanceStatus
from app.models.instance_status_event import InstanceStatusEvent
from app.services.external_client import ext_health  # implement GET /instances/{id}/health if not present

@celery_app.task(name="app.tasks.health.scan_and_dispatch")
def scan_and_dispatch():
    asyncio.run(_scan())

async def _scan():
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(UserBotInstance.id, UserBotInstance.instance_id))).all()
        for iid, remote_id in rows:
            poll_instance.apply_async(kwargs={"iid": iid, "remote_id": remote_id})

@celery_app.task(name="app.tasks.health.poll_instance", bind=True, max_retries=3, default_retry_delay=30)
def poll_instance(self, iid: int, remote_id: str):
    asyncio.run(_poll(iid, remote_id))

async def _poll(iid: int, remote_id: str):
    async with AsyncSessionLocal() as db:
        inst = await db.get(UserBotInstance, iid)
        if not inst:
            return
        try:
            data = await ext_health(remote_id)  # -> {"status": "active"|"inactive"|...}
            new_s = InstanceStatus(data.get("status", "unknown"))
        except Exception:
            new_s = InstanceStatus.unknown

        if new_s != inst.status:
            prev = inst.status
            inst.status = new_s
            db.add(InstanceStatusEvent(instance_id=iid, from_status=prev.value if prev else None, to_status=new_s.value))
        await db.commit()
