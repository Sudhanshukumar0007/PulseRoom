from uuid import UUID
from loguru import logger
import app.core.redis as redis_module

async def publish_message(room_id:UUID, message:str) -> None:
    if not redis_module.redis_client:
        logger.warning("Redis unavailable, message not published")
        return 
    try:
        await redis_module.redis_client.publish(f"room:{room_id}", message)
    except Exception as e:
        logger.error(f"Failed to publish to room {room_id}: {e}")

        