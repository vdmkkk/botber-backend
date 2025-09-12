from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_session_user_id, extend_session
from app.db.session import get_db
from app.models.user import User
from app.core.exceptions import raise_error
from app.core.error_codes import ErrorCode

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
    x_refresh_token: str | None = Header(default=None, alias="X-Refresh-Token"),
) -> User:
    # Auth rule: frontend sends both headers; we require a valid session token.
    if not x_session_token:
        raise_error(ErrorCode.UNAUTHORIZED, status.HTTP_401_UNAUTHORIZED, "Missing session token")
    user_id = await get_session_user_id(x_session_token)
    if not user_id:
        raise_error(ErrorCode.UNAUTHORIZED, status.HTTP_401_UNAUTHORIZED, "Invalid session")

    # Allow refresh JWT to be expired for normal routes; we don't validate here.
    await extend_session(x_session_token)  # sliding TTL on access
    user = await db.get(User, user_id)
    if not user:
        raise_error(ErrorCode.UNAUTHORIZED, status.HTTP_401_UNAUTHORIZED, "User not found")
    return user

def require_admin(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")):
    if not x_admin_key or x_admin_key != settings.ADMIN_API_KEY:
        raise_error(ErrorCode.ADMIN_TOKEN_INVALID, status.HTTP_401_UNAUTHORIZED, "Admin token invalid")
