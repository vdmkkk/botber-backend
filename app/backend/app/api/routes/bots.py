from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.bot import Bot
from app.schemas.bot import BotCreate, BotUpdate, BotOut
from app.core.exceptions import raise_error
from app.core.error_codes import ErrorCode

router = APIRouter(prefix="/bots", tags=["bots"])

@router.get("", response_model=list[BotOut])
async def list_bots(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Bot))
    return list(res.scalars())

@router.post("", dependencies=[Depends(require_admin)], response_model=BotOut)
async def create_bot(data: BotCreate, db: AsyncSession = Depends(get_db)):
    b = Bot(**data.model_dump())
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return b

@router.put("/{bot_id}", dependencies=[Depends(require_admin)], response_model=BotOut)
async def update_bot(bot_id: int, data: BotUpdate, db: AsyncSession = Depends(get_db)):
    bot = await db.get(Bot, bot_id)
    if not bot:
        raise_error(ErrorCode.BOT_NOT_FOUND, status.HTTP_404_NOT_FOUND, "Not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(bot, k, v)
    await db.commit()
    await db.refresh(bot)
    return bot

@router.delete("/{bot_id}", dependencies=[Depends(require_admin)])
async def delete_bot(bot_id: int, db: AsyncSession = Depends(get_db)):
    bot = await db.get(Bot, bot_id)
    if not bot:
        raise_error(ErrorCode.BOT_NOT_FOUND, status.HTTP_404_NOT_FOUND, "Not found")
    await db.delete(bot)
    await db.commit()
    return {"message": "Deleted"}
