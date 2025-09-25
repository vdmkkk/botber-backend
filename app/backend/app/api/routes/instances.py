from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, status, Header, Query, BackgroundTasks
from app.core.config import settings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.bot import Bot
from app.models.bot_instance import UserBotInstance
from app.models.enums import InstanceStatus
from app.models.instance_status_event import InstanceStatusEvent
from app.models.knowledge import KnowledgeBase, KnowledgeEntry
from app.schemas.bot_instance import InstanceCreate, InstanceUpdate, InstanceOut, InstanceStatusUpdate, InstanceDetailOut
from app.schemas.stats import StatusEventOut, StatusStatsOut
from app.services.status_stats import compute_status_stats
from app.schemas.knowledge import KBEntryCreate, KBEntryOut
from app.services.external_client import (
    ext_create_instance, ext_patch_instance, ext_delete_instance,
    ext_activate_instance, ext_deactivate_instance,
)
from app.core.exceptions import raise_error
from app.core.error_codes import ErrorCode
from app.schemas.openapi import ERROR_RESPONSES
from app.core.redis import get_session_user_id
from sqlalchemy.orm import selectinload

from app.schemas.knowledge import KBEntryCreate, KBEntryOut
from app.services.external_client import kb_ingest, kb_delete_by_ids
from app.services.kb_watcher import watch_kb_execution
from app.core.exceptions import raise_error
from app.core.error_codes import ErrorCode
from sqlalchemy import select
from app.models.enums import KBDataType, KBLangHint, KBEntryStatus

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

@router.get("/{iid}", response_model=InstanceDetailOut)
async def get_instance(iid: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # eager-load KB and its entries in one shot
    res = await db.execute(
        select(UserBotInstance)
        .options(
            selectinload(UserBotInstance.knowledge_base).selectinload(KnowledgeBase.entries)
        )
        .where(UserBotInstance.id == iid)
    )
    inst = res.scalar_one_or_none()
    if not inst or inst.user_id != user.id:
        raise_error(ErrorCode.INSTANCE_NOT_FOUND, status.HTTP_404_NOT_FOUND, "Not found")

    # The response model will serialize `inst` and include `kb` (knowledge_base renamed below)
    # We rename relationship field to match schema: kb = inst.knowledge_base
    # Easiest is to construct a dict:
    return InstanceDetailOut(
        id=inst.id,
        user_id=inst.user_id,
        bot_id=inst.bot_id,
        instance_id=inst.instance_id,
        title=inst.title,
        config=inst.config,
        status=inst.status,          # Pydantic will serialize Enum
        last_charge_at=inst.last_charge_at,
        next_charge_at=inst.next_charge_at,
        created_at=inst.created_at,
        updated_at=inst.updated_at,
        kb=inst.knowledge_base,      # this matches KnowledgeBaseOut (from_attributes=True)
    )

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
        inst = UserBotInstance(
            user_id=user.id,
            bot_id=bot.id,
            instance_id=remote_id,
            title=data.title,
            config=data.config or {},
            status=InstanceStatus.active,
            next_charge_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        db.add(inst)
        await db.flush()
        # create an empty KB mapped to this instance
        db.add(KnowledgeBase(instance_id=inst.id))
        await _record_status_change(db, inst.id, None, InstanceStatus.active.value)
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
    print(vars_payload)

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
        # await db.begin()
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
        # await db.begin()
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

@router.patch("/{iid}/status", response_model=InstanceOut)
async def set_instance_status(
    iid: int,
    payload: InstanceStatusUpdate,
    db: AsyncSession = Depends(get_db),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
    x_refresh_token: str | None = Header(default=None, alias="X-Refresh-Token"),
):
    # ---- Auth: admin OR (session + refresh)
    is_admin = False
    if x_admin_token:
        if x_admin_token != settings.ADMIN_TOKEN:
            raise_error(ErrorCode.ADMIN_TOKEN_INVALID, status.HTTP_401_UNAUTHORIZED, "Admin token invalid")
        is_admin = True
    else:
        # require both tokens present
        if not x_session_token or not x_refresh_token:
            raise_error(ErrorCode.TOKEN_MISSING, status.HTTP_401_UNAUTHORIZED, "Missing session/refresh token")
        uid = await get_session_user_id(x_session_token)
        if not uid:
            raise_error(ErrorCode.SESSION_INVALID, status.HTTP_401_UNAUTHORIZED, "Invalid session")

    # ---- Load instance
    inst = await db.get(UserBotInstance, iid)
    if not inst:
        raise_error(ErrorCode.INSTANCE_NOT_FOUND, status.HTTP_404_NOT_FOUND, "Not found")

    # Non-admin users must own the instance
    if not is_admin:
        # uid is set above
        if inst.user_id != uid:
            raise_error(ErrorCode.FORBIDDEN, status.HTTP_403_FORBIDDEN, "Forbidden")

    desired = payload.status
    # Accept "paused" but store as "inactive" to align with external API
    external_target = desired
    if desired == InstanceStatus.paused:
        external_target = InstanceStatus.inactive

    # ---- External action (only for active/inactive transitions)
    # (other statuses are local-only state changes)
    did_external = None
    try:
        if external_target == InstanceStatus.active:
            await ext_activate_instance(inst.instance_id)
            did_external = "activate"
        elif external_target == InstanceStatus.inactive:
            await ext_deactivate_instance(inst.instance_id)
            did_external = "deactivate"
    except Exception as e:
        raise_error(
            ErrorCode.EXTERNAL_API_ERROR,
            status.HTTP_502_BAD_GATEWAY,
            user_message="Failed to change remote status",
            details={"error": str(e)},
        )

    # ---- Persist local change + event (atomic unit)
    prev_status = inst.status
    try:
        # map paused -> inactive for storage
        new_status = external_target
        inst.status = new_status

        # keep resume behavior: when becoming active, reset next charge window
        if new_status == InstanceStatus.active:
            inst.next_charge_at = datetime.now(timezone.utc) + timedelta(days=1)

        db.add(
            InstanceStatusEvent(
                instance_id=inst.id,
                from_status=prev_status.value if prev_status else None,
                to_status=new_status.value,
            )
        )

        await db.commit()
        await db.refresh(inst)
        return inst

    except Exception as db_exc:
        await db.rollback()
        # compensate remote if we made an external call
        try:
            if did_external == "activate":
                await ext_deactivate_instance(inst.instance_id)
            elif did_external == "deactivate":
                await ext_activate_instance(inst.instance_id)
        except Exception:
            pass
        raise_error(
            ErrorCode.DATABASE_ERROR,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            user_message="Failed to save status",
            details={"error": str(db_exc)},
        )

# ---------- Knowledge Base endpoints ----------



@router.post("/{iid}/kb/entries", response_model=KBEntryOut)
async def kb_add_entry(
    iid: int,
    payload: KBEntryCreate,
    background: BackgroundTasks,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inst = await db.get(UserBotInstance, iid)
    if not inst or inst.user_id != user.id:
        raise_error(ErrorCode.INSTANCE_NOT_FOUND, status.HTTP_404_NOT_FOUND, "Not found")

    # ensure KB row exists
    res = await db.execute(select(KnowledgeBase).where(KnowledgeBase.instance_id == iid))
    kb = res.scalar()
    if not kb:
        kb = KnowledgeBase(instance_id=iid)
        db.add(kb)
        await db.flush()

    data_type = (payload.data_type or KBDataType.document)
    lang_hint = (payload.lang_hint or KBLangHint.ru)

    # call external ingest (returns execution_id) – /kb/ingest per spec
    try:
        exec_id = await kb_ingest(
            instance_id=inst.instance_id,
            url=payload.content,
            data_type=data_type.value,
            lang_hint=lang_hint.value,
        )
    except Exception as e:
        raise_error(
            ErrorCode.EXTERNAL_API_ERROR,
            status.HTTP_502_BAD_GATEWAY,
            user_message="Failed to submit entry to KB",
            details={"error": str(e)},
        )

    # create local entry as in_progress with execution_id
    entry = KnowledgeEntry(
        kb_id=kb.id,
        content=payload.content,
        data_type=data_type,
        lang_hint=lang_hint,
        execution_id=exec_id,
        status=KBEntryStatus.in_progress,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    # start watcher
    if background is not None:
        background.add_task(watch_kb_execution, entry.id)
    else:
        # fallback: still spawn a task
        asyncio.create_task(watch_kb_execution(entry.id))

    return entry


@router.delete("/{iid}/kb/entries/{entry_id}")
async def kb_delete_entry_route(iid: int, entry_id: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    inst = await db.get(UserBotInstance, iid)
    if not inst or inst.user_id != user.id:
        raise_error(ErrorCode.INSTANCE_NOT_FOUND, status.HTTP_404_NOT_FOUND, "Not found")

    entry = await db.get(KnowledgeEntry, entry_id)
    if not entry:
        raise_error(ErrorCode.NOT_FOUND, status.HTTP_404_NOT_FOUND, "Entry not found")

    # If we already have external_entity_id, delete upstream first
    if entry.external_entry_id:
        try:
            await kb_delete_by_ids(instance_id=inst.instance_id, entity_ids=[entry.external_entry_id])
        except Exception as e:
            raise_error(
                ErrorCode.EXTERNAL_API_ERROR,
                status.HTTP_502_BAD_GATEWAY,
                user_message="Failed to delete KB entry remotely",
                details={"error": str(e)},
            )

    await db.delete(entry)
    await db.commit()
    return {"message": "Deleted"}

@router.get("/{iid}/status-events", response_model=list[StatusEventOut])
async def get_status_events(
    iid: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    from_dt: datetime | None = Query(None, alias="from"),
    to_dt: datetime | None = Query(None, alias="to"),
):
    inst = await db.get(UserBotInstance, iid)
    if not inst or inst.user_id != user.id:
        raise_error(ErrorCode.INSTANCE_NOT_FOUND, status.HTTP_404_NOT_FOUND, "Not found")

    q = select(InstanceStatusEvent).where(InstanceStatusEvent.instance_id == iid)
    if from_dt:
        q = q.where(InstanceStatusEvent.changed_at >= from_dt)
    if to_dt:
        q = q.where(InstanceStatusEvent.changed_at <= to_dt)
    q = q.order_by(InstanceStatusEvent.changed_at.desc()).offset(offset).limit(limit)

    res = await db.execute(q)
    return list(res.scalars())


@router.get("/{iid}/stats", response_model=StatusStatsOut)
async def get_instance_stats(
    iid: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    from_dt: datetime = Query(..., alias="from"),
    to_dt: datetime = Query(..., alias="to"),
    include_segments: bool = Query(False),
):
    if to_dt <= from_dt:
        raise_error(ErrorCode.VALIDATION_ERROR, status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid time window")

    inst = await db.get(UserBotInstance, iid)
    if not inst or inst.user_id != user.id:
        raise_error(ErrorCode.INSTANCE_NOT_FOUND, status.HTTP_404_NOT_FOUND, "Not found")

    stats = await compute_status_stats(db, inst, from_dt, to_dt, include_segments=include_segments)
    return StatusStatsOut(**stats)