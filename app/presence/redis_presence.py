from uuid import UUID
from loguru import logger
import app.core.redis as redis_module
# if User doesn't ping under this time redis deletes them this is what we call TTL
PRESENCE_TTL = 30

async def add_or_refresh_user_presence(room_id: UUID, user_id: UUID) -> None:
    """Adds a user to the room's active presence set in Redis."""
    if not redis_module.redis_client:
        return
        
    key = f"presence:{room_id}:{user_id}"
    try:
        await redis_module.redis_client.set(key,"online",ex = PRESENCE_TTL)
    except Exception as e:
        logger.error(f"Failed to add presence for user {user_id}: {e}")

async def remove_user_presence(room_id: UUID, user_id: UUID) -> None:
    """Removes a user from the room's active presence set in Redis."""
    if not redis_module.redis_client:
        return
        
    key = f"presence:{room_id}:{user_id}"
    try:
        await redis_module.redis_client.delete(key)
    except Exception as e:
        logger.error(f"Failed to remove presence for user {user_id}: {e}")

async def get_active_users_in_room(room_id: UUID) -> list[str]:
    """Finds all active users by scanning for their individual keys."""
    if not redis_module.redis_client:
        return []
        
    pattern = f"presence:{room_id}:*"
    try:
        # Find all keys matching the room pattern
        keys = await redis_module.redis_client.keys(pattern)
        # Split the key string to extract just the user_id at the end
        return [key.split(":")[-1] for key in keys]
    except Exception as e:
        logger.error(f"Failed to get presence for room {room_id}: {e}")
        return []