import uuid
from typing import Optional
from app.core.redis import redis_client  # <-- use your existing factory

class RedisLock:
    def __init__(self, key: str, ttl_seconds: int):
        self.key = key
        self.ttl = ttl_seconds
        self._token: Optional[str] = None

    async def __aenter__(self):
        self._token = uuid.uuid4().hex
        r = redis_client()  # <-- no await, returns redis.asyncio.Redis
        # SET key token NX EX ttl
        acquired = await r.set(self.key, self._token, nx=True, ex=self.ttl)
        return bool(acquired)

    async def __aexit__(self, exc_type, exc, tb):
        if not self._token:
            return
        r = redis_client()
        # compare-and-delete
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
