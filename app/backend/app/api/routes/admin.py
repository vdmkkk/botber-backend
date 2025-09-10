from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserOut

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

@router.get("/users", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User))
    return list(res.scalars())

@router.get("/users/{uid}", response_model=UserOut)
async def get_user(uid: int, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(404, "Not found")
    return user

@router.patch("/users/{uid}", response_model=UserOut)
async def patch_user(uid: int, data: dict, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(404, "Not found")
    # Allow editing arbitrary fields (balance & profile edits)
    for k, v in data.items():
        if hasattr(user, k) and v is not None:
            setattr(user, k, v)
    await db.commit()
    await db.refresh(user)
    return user
