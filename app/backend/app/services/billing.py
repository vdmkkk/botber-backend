from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.bot import Bot
from app.models.bot_instance import UserBotInstance
from app.models.enums import InstanceStatus

def daily_cost(rate: int) -> int:
    # ceil(rate / 30)
    return (rate + 29) // 30

async def run_daily_billing(db: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    q = select(UserBotInstance).where(
        UserBotInstance.status == InstanceStatus.active,
        (UserBotInstance.next_charge_at == None) | (UserBotInstance.next_charge_at <= now)  # noqa: E711
    )
    res = await db.execute(q)
    instances = list(res.scalars())

    for inst in instances:
        bot = await db.get(Bot, inst.bot_id)
        user = await db.get(User, inst.user_id)
        if not bot or not user:
            continue

        cost = daily_cost(bot.rate)
        if user.balance >= cost:
            user.balance -= cost
            inst.last_charge_at = now
            inst.next_charge_at = now + timedelta(days=1)
        else:
            inst.status = InstanceStatus.not_enough_balance
    await db.commit()
