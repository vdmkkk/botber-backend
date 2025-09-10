import json
import uuid
from datetime import timedelta
from typing import Optional

from redis.asyncio import Redis
from app.core.config import settings

_redis: Optional[Redis] = None

def redis_client() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)
    return _redis

SESSION_PREFIX = "session:"
USER_SESSIONS_PREFIX = "user_sessions:"

def session_key(sid: str) -> str:
    return f"{SESSION_PREFIX}{sid}"

def user_sessions_key(uid: int) -> str:
    return f"{USER_SESSIONS_PREFIX}{uid}"

async def create_session(user_id: int) -> str:
    r = redis_client()
    sid = str(uuid.uuid4())
    ttl = int(timedelta(days=settings.SESSION_TTL_DAYS).total_seconds())
    payload = json.dumps({"user_id": user_id})
    await r.set(session_key(sid), payload, ex=ttl)
    await r.sadd(user_sessions_key(user_id), sid)
    return sid

async def get_session_user_id(sid: str) -> Optional[int]:
    r = redis_client()
    raw = await r.get(session_key(sid))
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return int(data.get("user_id"))
    except Exception:
        return None

async def extend_session(sid: str) -> None:
    r = redis_client()
    ttl = int(timedelta(days=settings.SESSION_TTL_DAYS).total_seconds())
    await r.expire(session_key(sid), ttl)

async def delete_session(sid: str) -> None:
    r = redis_client()
    raw = await r.get(session_key(sid))
    if raw:
        try:
            user_id = int(json.loads(raw).get("user_id"))
            await r.srem(user_sessions_key(user_id), sid)
        except Exception:
            pass
    await r.delete(session_key(sid))

async def delete_all_sessions(user_id: int) -> None:
    r = redis_client()
    key = user_sessions_key(user_id)
    sids = await r.smembers(key)
    if sids:
        await r.delete(*(session_key(s) for s in sids))
    await r.delete(key)
