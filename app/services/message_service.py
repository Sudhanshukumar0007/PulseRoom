from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.message import Message

async def save_message(db: AsyncSession, room_id: UUID, sender_id: UUID, content: str) -> Message:
    message = Message(room_id=room_id, sender_id=sender_id, content=content)
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message

async def get_recent_messages(db: AsyncSession, room_id: UUID, limit: int = 50) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.room_id == room_id)
        .options(selectinload(Message.sender))
        .order_by(Message.sent_at.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all())) 

async def get_messages_since(db: AsyncSession, room_id: UUID, since_message_id: UUID | None, limit: int = 100):
    if since_message_id is None:
        return await get_recent_messages(db, room_id, limit=50)  # fallback: normal history

    # need the sent_at of the reference message first
    since_msg_result = await db.execute(
        select(Message).where(
            Message.id == since_message_id,
            Message.room_id == room_id,
        )
    )
    since_msg = since_msg_result.scalar_one_or_none()
    if since_msg is None:
        return await get_recent_messages(db, room_id, limit=50)  # fallback if the id is stale/invalid

    result = await db.execute(
        select(Message)
        .where(Message.room_id == room_id, Message.sent_at > since_msg.sent_at)
        .options(selectinload(Message.sender))
        .order_by(Message.sent_at.asc())
        .limit(limit)
    )
    return result.scalars().all()
