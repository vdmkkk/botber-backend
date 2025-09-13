import asyncio
from typing import Optional
from app.core.redis import get_redis  # reuse your existing redis connection factory

class RedisLock:
    def __init__(self, key: str, ttl_seconds: int):
        self.key = key
        self.ttl = ttl_seconds
        self._token: Optional[str] = None

    async def __aenter__(self):
        import uuid
        self._token = uuid.uuid4().hex
        r = await get_redis()
        # SET key token NX EX ttl
        acquired = await r.set(self.key, self._token, nx=True, ex=self.ttl)
        if not acquired:
            return False
        return True

    async def __aexit__(self, exc_type, exc, tb):
        if self._token is None:
            return
        r = await get_redis()
        # Basic safe unlock: compare token then delete
        lua = """
        if redis.call('GET', KEYS[1]) == ARGV[1] then
            return redis.call('DEL', KEYS[1])
        else
            return 0
        end
        """
        try:
            await r.eval(lua, 1, self.key, self._token)
        except Exception:
            pass
