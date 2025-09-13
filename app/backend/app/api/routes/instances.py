from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.bot import Bot
from app.models.bot_instance import UserBotInstance
from app.models.enums import InstanceStatus
from app.models.instance_status_event import InstanceStatusEvent
from app.models.knowledge import KnowledgeBase, KnowledgeEntry
from app.schemas.bot_instance import InstanceCreate, InstanceUpdate, InstanceOut
from app.schemas.knowledge import KBEntryCreate, KBEntryOut
from app.services.external_client import (
    ext_create_instance, ext_patch_instance, ext_delete_instance,
    ext_activate_instance, ext_deactivate_instance, ext_health,
    kb_create_entry, kb_delete_entry,
)
from app.core.exceptions import raise_error
from app.core.error_codes import ErrorCode
from app.schemas.openapi import ERROR_RESPONSES

router = APIRouter(prefix="/instances", tags=["instances"])

def _vars_from_config(cfg: dict | None) -> dict:
    cfg = cfg or {}
    out = {}
    if "telegram_bot_api_key" in cfg and cfg["telegram_bot_api_key"]:
        out["telegram_bot_api_key"] = cfg["telegram_bot_api_key"]
    return out

async def _record_status_change(db: AsyncSession, inst_id: int, from_s: str | None, to_s: str):
    db.add(InstanceStatusEvent(instance_id=inst_id, from_status=from_s, to_status=to_s))

@router.get("", response_model=list[InstanceOut], responses=ERROR_RESPONSES)
async def list_instances(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(UserBotInstance).where(UserBotInstance.user_id == user.id))
    return list(res.scalars())

@router.get("/{iid}", response_model=InstanceOut, responses=ERROR_RESPONSES)
async def get_instance(iid: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    inst = await db.get(UserBotInstance, iid)
    if not inst or inst.user_id != user.id:
        raise_error(ErrorCode.INSTANCE_NOT_FOUND, status.HTTP_404_NOT_FOUND, "Not found")
    return inst

@router.post("", response_model=InstanceOut, responses=ERROR_RESPONSES)
async def create_instance(data: InstanceCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    bot = await db.get(Bot, data.bot_id)
    if not bot:
        raise_error(ErrorCode.BOT_NOT_FOUND, status.HTTP_400_BAD_REQUEST, "Invalid bot")

    # 1) ask external to create (get remote id). If this fails, we do nothing locally.
    vars_payload = _vars_from_config(data.config)
    try:
        remote_id = await ext_create_instance(activation_code=bot.activation_code, vars=vars_payload)
    except Exception as e:
        raise_error(
            ErrorCode.INSTANCE_CREATION_FAILED,
            status.HTTP_502_BAD_GATEWAY,
            user_message="Failed to create remote instance",
            details={"error": str(e)},
        )

    # 2) persist atomically; on DB failure, compensate by deleting remote instance
    try:
        await db.begin()
        inst = UserBotInstance(
            user_id=user.id,
            bot_id=bot.id,
            instance_id=remote_id,
            title=data.title,
            config=data.config or {},
            status=InstanceStatus.provisioning,
            next_charge_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        db.add(inst)
        await db.flush()
        # create an empty KB mapped to this instance
        db.add(KnowledgeBase(instance_id=inst.id))
        await _record_status_change(db, inst.id, None, InstanceStatus.provisioning.value)
        await db.commit()
        await db.refresh(inst)
        return inst
    except Exception as db_exc:
        await db.rollback()
        try:
            await ext_delete_instance(remote_id)
        except Exception:
            # log but swallow — we cannot keep the external resource silently
            pass
        raise_error(
            ErrorCode.DATABASE_ERROR,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            user_message="Failed to save instance",
            details={"error": str(db_exc)},
        )

@router.put("/{iid}", response_model=InstanceOut, responses=ERROR_RESPONSES)
async def update_instance(iid: int, data: InstanceUpdate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    inst = await db.get(UserBotInstance, iid)
    if not inst or inst.user_id != user.id:
        raise_error(ErrorCode.INSTANCE_NOT_FOUND, status.HTTP_404_NOT_FOUND, "Not found")

    old_config = dict(inst.config or {})
    new_config = {**old_config, **(data.config or {})} if data.config is not None else old_config
    vars_payload = _vars_from_config(new_config)

    # call external first; if ext fails, do nothing locally
    try:
        await ext_patch_instance(inst.instance_id, vars=vars_payload)
    except Exception as e:
        raise_error(
            ErrorCode.EXTERNAL_API_ERROR,
            status.HTTP_502_BAD_GATEWAY,
            user_message="Failed to update remote instance",
            details={"error": str(e)},
        )

    # now update local; if local commit fails, attempt to revert external to old vars
    try:
        await db.begin()
        if data.title is not None:
            inst.title = data.title
        if data.config is not None:
            inst.config = new_config
        await db.commit()
        await db.refresh(inst)
        return inst
    except Exception as db_exc:
        await db.rollback()
        # compensate: try to revert external config
        try:
            await ext_patch_instance(inst.instance_id, vars=_vars_from_config(old_config))
        except Exception:
            pass
        raise_error(
            ErrorCode.DATABASE_ERROR,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            user_message="Failed to save instance changes",
            details={"error": str(db_exc)},
        )

@router.delete("/{iid}", responses=ERROR_RESPONSES)
async def delete_instance(iid: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    inst = await db.get(UserBotInstance, iid)
    if not inst or inst.user_id != user.id:
        raise_error(ErrorCode.INSTANCE_NOT_FOUND, status.HTTP_404_NOT_FOUND, "Not found")

    # prepare data in case we need to compensate (re-create)
    bot = await db.get(Bot, inst.bot_id)
    old_vars = _vars_from_config(inst.config)
    old_title = inst.title

    try:
        await db.begin()
        # local delete (not committed yet)
        await db.delete(inst)
        # external delete
        await ext_delete_instance(inst.instance_id)
        # commit local
        await db.commit()
        return {"message": "Deleted"}
    except Exception as exc:
        await db.rollback()
        # try to compensate if external succeeded but DB failed
        # We don't know where it failed; best-effort re-create externally if local still exists missing.
        try:
            # check if instance still exists locally
            again = await db.get(UserBotInstance, iid)
            if again is None and bot:
                # re-create remote (id will be different; we can't restore exact id)
                await ext_create_instance(activation_code=bot.activation_code, vars=old_vars)
        except Exception:
            pass
        raise_error(
            ErrorCode.DATABASE_ERROR,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            user_message="Failed to delete instance",
            details={"error": str(exc)},
        )

@router.patch("/{iid}/pause", response_model=InstanceOut, responses=ERROR_RESPONSES)
async def pause_instance(iid: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    inst = await db.get(UserBotInstance, iid)
    if not inst or inst.user_id != user.id:
        raise_error(ErrorCode.INSTANCE_NOT_FOUND, status.HTTP_404_NOT_FOUND, "Not found")

    try:
        await ext_deactivate_instance(inst.instance_id)
    except Exception as e:
        raise_error(
            ErrorCode.EXTERNAL_API_ERROR,
            status.HTTP_502_BAD_GATEWAY,
            user_message="Failed to deactivate remote instance",
            details={"error": str(e)},
        )

    prev = inst.status.value
    try:
        await db.begin()
        inst.status = InstanceStatus.inactive
        await _record_status_change(db, inst.id, prev, InstanceStatus.inactive.value)
        await db.commit()
        await db.refresh(inst)
        return inst
    except Exception as db_exc:
        await db.rollback()
        # compensate: re-activate remotely
        try:
            await ext_activate_instance(inst.instance_id)
        except Exception:
            pass
        raise_error(
            ErrorCode.DATABASE_ERROR,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            user_message="Failed to save pause",
            details={"error": str(db_exc)},
        )

@router.patch("/{iid}/resume", response_model=InstanceOut, responses=ERROR_RESPONSES)
async def resume_instance(iid: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    inst = await db.get(UserBotInstance, iid)
    if not inst or inst.user_id != user.id:
        raise_error(ErrorCode.INSTANCE_NOT_FOUND, status.HTTP_404_NOT_FOUND, "Not found")

    try:
        await ext_activate_instance(inst.instance_id)
    except Exception as e:
        raise_error(
            ErrorCode.EXTERNAL_API_ERROR,
            status.HTTP_502_BAD_GATEWAY,
            user_message="Failed to activate remote instance",
            details={"error": str(e)},
        )

    prev = inst.status.value
    try:
        await db.begin()
        inst.status = InstanceStatus.active
        inst.next_charge_at = datetime.now(timezone.utc) + timedelta(days=1)
        await _record_status_change(db, inst.id, prev, InstanceStatus.active.value)
        await db.commit()
        await db.refresh(inst)
        return inst
    except Exception as db_exc:
        await db.rollback()
        # compensate: deactivate remotely
        try:
            await ext_deactivate_instance(inst.instance_id)
        except Exception:
            pass
        raise_error(
            ErrorCode.DATABASE_ERROR,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            user_message="Failed to save resume",
            details={"error": str(db_exc)},
        )

# ---------- Knowledge Base endpoints ----------

@router.post("/{iid}/kb/entries", response_model=KBEntryOut, responses=ERROR_RESPONSES)
async def kb_add_entry(iid: int, payload: KBEntryCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    inst = await db.get(UserBotInstance, iid)
    if not inst or inst.user_id != user.id:
        raise_error(ErrorCode.INSTANCE_NOT_FOUND, status.HTTP_404_NOT_FOUND, "Not found")

    # find/create kb
    res = await db.execute(select(KnowledgeBase).where(KnowledgeBase.instance_id == iid))
    kb = res.scalar()
    if not kb:
        kb = KnowledgeBase(instance_id=iid)
        db.add(kb)
        await db.flush()

    # call external first
    try:
        ext_id = await kb_create_entry(instance_id=inst.instance_id, content=payload.content)
    except Exception as e:
        raise_error(
            ErrorCode.EXTERNAL_API_ERROR,
            status.HTTP_502_BAD_GATEWAY,
            user_message="Failed to create KB entry remotely",
            details={"error": str(e)},
        )

    # persist local; compensate external on failure
    try:
        await db.begin()
        entry = KnowledgeEntry(kb_id=kb.id, content=payload.content, external_entry_id=ext_id)
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry
    except Exception as db_exc:
        await db.rollback()
        try:
            await kb_delete_entry(instance_id=inst.instance_id, entry_id=ext_id)
        except Exception:
            pass
        raise_error(
            ErrorCode.DATABASE_ERROR,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            user_message="Failed to save KB entry",
            details={"error": str(db_exc)},
        )

@router.delete("/{iid}/kb/entries/{entry_id}", responses=ERROR_RESPONSES)
async def kb_delete_entry_route(iid: int, entry_id: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    inst = await db.get(UserBotInstance, iid)
    if not inst or inst.user_id != user.id:
        raise_error(ErrorCode.INSTANCE_NOT_FOUND, status.HTTP_404_NOT_FOUND, "Not found")

    entry = await db.get(KnowledgeEntry, entry_id)
    if not entry:
        raise_error(ErrorCode.NOT_FOUND, status.HTTP_404_NOT_FOUND, "Entry not found")

    # external delete first; if ok, delete local
    try:
        if entry.external_entry_id:
            await kb_delete_entry(instance_id=inst.instance_id, entry_id=entry.external_entry_id)
    except Exception as e:
        raise_error(
            ErrorCode.EXTERNAL_API_ERROR,
            status.HTTP_502_BAD_GATEWAY,
            user_message="Failed to delete KB entry remotely",
            details={"error": str(e)},
        )

    try:
        await db.begin()
        await db.delete(entry)
        await db.commit()
        return {"message": "Deleted"}
    except Exception as db_exc:
        await db.rollback()
        # best-effort: re-create remotely? we don't have content anymore; skip
        raise_error(
            ErrorCode.DATABASE_ERROR,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            user_message="Failed to delete KB entry locally",
            details={"error": str(db_exc)},
        )
