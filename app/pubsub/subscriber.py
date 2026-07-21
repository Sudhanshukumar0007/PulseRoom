import asyncio
from uuid import UUID
from loguru import logger
import app.core.redis as redis_module

_room_tasks: dict[UUID, asyncio.Task] = {}

async def _listen(room_id:UUID,manager):
    if redis_module.redis_client is None:
        logger.error(f"Cannot subscribe to room {room_id}: Redis is unavailable")
        return

    pubsub = redis_module.redis_client.pubsub()
    try:
        await pubsub.subscribe(f"room:{room_id}")
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            await manager.broadcast(room_id, message["data"])
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.exception(f"Room subscriber for {room_id} stopped unexpectedly: {e}")
    finally:
        await pubsub.unsubscribe(f"room:{room_id}")
        await pubsub.aclose()
    
def ensure_room_subscriber(room_id: UUID, manager) -> None:
    if room_id not in _room_tasks or _room_tasks[room_id].done():
        _room_tasks[room_id] = asyncio.create_task(_listen(room_id, manager))
        
def stop_room_subscriber(room_id: UUID) -> None:
    task = _room_tasks.pop(room_id, None)
    if task:
        task.cancel()
