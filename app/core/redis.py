from redis.asyncio import Redis
from app.core.config import settings

redis_client:Redis | None = None

async def get_redis()->Redis:
    if redis_client is None:
        raise RuntimeError("Redis client is not initialised")
    return redis_client