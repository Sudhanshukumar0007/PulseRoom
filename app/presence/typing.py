from uuid import UUID
from loguru import logger
import app.core.redis as redis_module

TYPING_TTL = 5  # seconds - short, since typing indicators should expire fast

async def set_typing_indicator(room_id: UUID, user_id: UUID, user_name: str) -> None:
    if not redis_module.redis_client:
        return
    key = f"typing:{room_id}:{user_id}"
    try:
        await redis_module.redis_client.set(key, user_name, ex=TYPING_TTL)
    except Exception as e:
        logger.error(f"Failed to set typing indicator for {user_id}: {e}")
