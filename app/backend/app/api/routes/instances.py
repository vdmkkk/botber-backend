from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.bot import Bot
from app.models.bot_instance import UserBotInstance
from app.models.enums import InstanceStatus
from app.schemas.bot_instance import InstanceCreate, InstanceUpdate, InstanceOut
from app.services.external_hooks import create_remote_instance, notify_instance_created

router = APIRouter(prefix="/instances", tags=["instances"])

@router.get("", response_model=list[InstanceOut])
async def list_instances(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(UserBotInstance).where(UserBotInstance.user_id == user.id))
    return list(res.scalars())

@router.get("/{iid}", response_model=InstanceOut)
async def get_instance(iid: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    inst = await db.get(UserBotInstance, iid)
    if not inst or inst.user_id != user.id:
        raise HTTPException(404, "Not found")
    return inst

@router.post("", response_model=InstanceOut)
async def create_instance(data: InstanceCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    bot = await db.get(Bot, data.bot_id)
    if not bot:
        raise HTTPException(400, "Invalid bot")

    # 1) Create remote instance to obtain instance_id (placeholder for now)
    try:
        remote_id = await create_remote_instance(activation_code=bot.activation_code, config=data.config or {})
    except Exception as e:
        raise HTTPException(502, f"Failed to create remote instance: {e}")

    # 2) Persist locally
    inst = UserBotInstance(
        user_id=user.id,
        bot_id=bot.id,
        instance_id=remote_id,  # NEW
        title=data.title,
        config=data.config or {},
        status=InstanceStatus.active,
        next_charge_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db.add(inst)
    await db.commit()
    await db.refresh(inst)

    # 3) Notify external (optional)
    await notify_instance_created(inst.id, {"user_id": user.id, "bot_id": bot.id, "remote_instance_id": remote_id})
    return inst

@router.put("/{iid}", response_model=InstanceOut)
async def update_instance(iid: int, data: InstanceUpdate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    inst = await db.get(UserBotInstance, iid)
    if not inst or inst.user_id != user.id:
        raise HTTPException(404, "Not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(inst, k, v)
    await db.commit()
    await db.refresh(inst)
    return inst

@router.delete("/{iid}")
async def delete_instance(iid: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    inst = await db.get(UserBotInstance, iid)
    if not inst or inst.user_id != user.id:
        raise HTTPException(404, "Not found")
    await db.delete(inst)
    await db.commit()
    return {"message": "Deleted"}

@router.patch("/{iid}/pause", response_model=InstanceOut)
async def pause_instance(iid: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    inst = await db.get(UserBotInstance, iid)
    if not inst or inst.user_id != user.id:
        raise HTTPException(404, "Not found")
    inst.status = InstanceStatus.paused
    await db.commit()
    await db.refresh(inst)
    return inst

@router.patch("/{iid}/resume", response_model=InstanceOut)
async def resume_instance(iid: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    inst = await db.get(UserBotInstance, iid)
    if not inst or inst.user_id != user.id:
        raise HTTPException(404, "Not found")
    inst.status = InstanceStatus.active
    inst.next_charge_at = datetime.now(timezone.utc) + timedelta(days=1)
    await db.commit()
    await db.refresh(inst)
    return inst
