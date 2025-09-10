import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(p: str) -> str:
    return pwd_ctx.hash(p)

def verify_password(p: str, hashed: str) -> bool:
    return pwd_ctx.verify(p, hashed)

def create_refresh_jwt(user_id: int, session_id: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.JWT_REFRESH_MINUTES)
    payload = {"sub": str(user_id), "sid": session_id, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)

def decode_refresh_jwt(token: str, verify_exp: bool = True) -> Optional[dict]:
    options = {"verify_exp": verify_exp}
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG], options=options)
    except Exception:
        return None

def gen_code(n: int = 6) -> str:
    # numeric code, easy for email input
    return "".join(secrets.choice("0123456789") for _ in range(n))

def gen_slug(nbytes: int = 24) -> str:
    # URL-safe token for password reset
    return secrets.token_urlsafe(nbytes)
