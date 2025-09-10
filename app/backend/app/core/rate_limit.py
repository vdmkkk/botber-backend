from typing import Optional
from app.core.redis import redis_client

async def cooldown_key(prefix: str, key: str) -> str:
    return f"{prefix}:{key}"

async def set_cooldown(prefix: str, key: str, seconds: int) -> bool:
    r = redis_client()
    ck = await cooldown_key(prefix, key)
    # NX = only set if not exists
    return bool(await r.set(ck, "1", ex=seconds, nx=True))

# ---- Login throttling helpers ----

def _fail_key(email: str) -> str:
    return f"login:fail:{email.lower()}"

def _block_key(email: str) -> str:
    return f"login:block:{email.lower()}"

async def incr_failure(email: str, window_seconds: int) -> int:
    r = redis_client()
    key = _fail_key(email)
    # increment and ensure TTL set (only when first created)
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, window_seconds)
    return count

async def reset_failures(email: str) -> None:
    r = redis_client()
    await r.delete(_fail_key(email))

async def is_blocked(email: str) -> bool:
    r = redis_client()
    return bool(await r.exists(_block_key(email)))

async def set_block(email: str, block_seconds: int) -> None:
    r = redis_client()
    await r.set(_block_key(email), "1", ex=block_seconds)

async def block_ttl(email: str) -> Optional[int]:
    r = redis_client()
    ttl = await r.ttl(_block_key(email))
    return ttl if ttl and ttl > 0 else None
