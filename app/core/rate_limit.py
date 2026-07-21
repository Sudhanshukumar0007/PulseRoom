# app/core/rate_limit.py
import time
from uuid import UUID
from loguru import logger
import app.core.redis as redis_module

RATE_LIMIT_MAX_MESSAGES = 10
RATE_LIMIT_WINDOW_SECONDS = 10

async def is_rate_limited(user_id: UUID) -> bool:
    if not redis_module.redis_client:
        return False  

    key = f"ratelimit:{user_id}"
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS

    try:
        pipe = redis_module.redis_client.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)   # prune anything outside the window
        pipe.zadd(key, {str(now): now})                # record this message's timestamp
        pipe.zcard(key)                                 # count what's left in the window
        pipe.expire(key, RATE_LIMIT_WINDOW_SECONDS)     # auto-cleanup if user goes idle
        results = await pipe.execute()
        count = results[2]
        return count > RATE_LIMIT_MAX_MESSAGES
    except Exception as e:
        logger.error(f"Rate limit check failed for {user_id}: {e}")
        return False  # fail open on Redis errors too