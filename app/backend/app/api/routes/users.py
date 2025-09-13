from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserOut, UserUpdate
from app.schemas.openapi import ERROR_RESPONSES

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserOut, responses=ERROR_RESPONSES)
async def get_me(current: User = Depends(get_current_user)):
    return current

@router.patch("/me", response_model=UserOut, responses=ERROR_RESPONSES)
async def update_me(
    payload: UserUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(current, k, v)
    await db.commit()
    await db.refresh(current)
    return current
