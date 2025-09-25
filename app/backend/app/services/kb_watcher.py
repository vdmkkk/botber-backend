import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models.knowledge import KnowledgeEntry, KnowledgeBase
from app.models.bot_instance import UserBotInstance
from app.services.external_client import kb_status
from app.core.config import settings
from app.models.enums import KBEntryStatus

async def _update_entry_done(db: AsyncSession, entry: KnowledgeEntry, entity_id: str):
    entry.external_entry_id = entity_id
    entry.execution_id = None
    entry.status = KBEntryStatus.done
    await db.commit()

async def _delete_entry(db: AsyncSession, entry: KnowledgeEntry):
    await db.delete(entry)
    await db.commit()

async def watch_kb_execution(entry_id: int):
    """Polls external /kb/status every 30s for 30min; on done writes external_entry_id; on timeout deletes entry."""
    interval = settings.KB_POLL_INTERVAL_SECONDS
    timeout = settings.KB_POLL_TIMEOUT_SECONDS
    deadline = asyncio.get_event_loop().time() + timeout

    async with AsyncSessionLocal() as db:
        entry = await db.get(KnowledgeEntry, entry_id)
        if not entry or not entry.execution_id:
            return
        # get instance.remote_id through kb -> instance
        kb = await db.get(KnowledgeBase, entry.kb_id)
        if not kb:
            return
        inst = await db.get(UserBotInstance, kb.instance_id)
        if not inst:
            return
        instance_remote_id = inst.instance_id

    while asyncio.get_event_loop().time() < deadline:
        async with AsyncSessionLocal() as db:
            entry = await db.get(KnowledgeEntry, entry_id)
            if not entry or entry.status != "in_progress" or not entry.execution_id:
                return  # already resolved or removed
            kb = await db.get(KnowledgeBase, entry.kb_id)
            inst = await db.get(UserBotInstance, kb.instance_id) if kb else None
            if not inst:
                return

            status, entity_ids = await kb_status(instance_id=inst.instance_id, execution_id=entry.execution_id)
            if status == KBEntryStatus.done and entity_ids:
                await _update_entry_done(db, entry, entity_ids[0])
                return
            elif status in {"unknown", "failed"}:
                await _delete_entry(db, entry)
                return
        await asyncio.sleep(interval)

    # timed out – delete silently
    async with AsyncSessionLocal() as db:
        entry = await db.get(KnowledgeEntry, entry_id)
        if entry and entry.status == KBEntryStatus.in_progress:
            await _delete_entry(db, entry)

async def rehydrate_pending_watchers():
    """On startup: restart watchers for entries stuck in in_progress."""
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(KnowledgeEntry.id).where(KnowledgeEntry.status == "in_progress"))
        ids = [row[0] for row in res.fetchall()]
    for eid in ids:
        asyncio.create_task(watch_kb_execution(eid))
