import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, and_
from app.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.models.knowledge import KnowledgeEntry, KnowledgeBase
from app.models.bot_instance import UserBotInstance
from app.models.enums import KBEntryStatus
from app.services.external_client import kb_status
from app.core.config import settings

@celery_app.task(name="app.tasks.kb.scan_and_dispatch")
def scan_and_dispatch():
    asyncio.run(_scan())

async def _scan():
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        q = select(KnowledgeEntry.id).where(KnowledgeEntry.status == KBEntryStatus.in_progress)
        ids = [row[0] for row in (await db.execute(q)).all()]
    for eid in ids:
        poll_execution.apply_async(kwargs={"entry_id": eid})

@celery_app.task(name="app.tasks.kb.poll_execution", bind=True, max_retries=100, default_retry_delay=30)
def poll_execution(self, entry_id: int):
    asyncio.run(_poll(entry_id))

async def _poll(entry_id: int):
    async with AsyncSessionLocal() as db:
        entry = await db.get(KnowledgeEntry, entry_id)
        if not entry or entry.status != KBEntryStatus.in_progress or not entry.execution_id:
            return
        kb = await db.get(KnowledgeBase, entry.kb_id)
        inst = await db.get(UserBotInstance, kb.instance_id) if kb else None
        if not inst:
            return

        # timeout after 30 min since creation
        if (datetime.now(timezone.utc) - entry.created_at).total_seconds() > settings.KB_POLL_TIMEOUT_SECONDS:
            await db.delete(entry)
            await db.commit()
            return

        status, entity_ids = await kb_status(instance_id=inst.instance_id, execution_id=entry.execution_id)
        if status == "done" and entity_ids:
            entry.external_entry_id = entity_ids[0]
            entry.execution_id = None
            entry.status = KBEntryStatus.done
            await db.commit()
        elif status in {"unknown", "failed"}:
            await db.delete(entry)
            await db.commit()
        # else still in progress: next beat tick will re-dispatch
