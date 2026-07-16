from fastapi import HTTPException,status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.schemas.room import RoomCreate
from app.models.user import User
from datetime import datetime,timezone
from app.models.room import Room
from app.models.room_member import RoomMember
from uuid import UUID

async def create_room(db: AsyncSession, user: User, data: RoomCreate):
    # 1. Create the room
    room = Room(
        name=data.name,
        created_by=user.id,
        created_at=datetime.now(timezone.utc)
    )
    db.add(room)
    
    # 2. Flush the session to populate room.id
    await db.flush() 
    
    # 3. Now room.id has a valid UUID, so we can create the membership
    membership = RoomMember(
        room_id=room.id, 
        user_id=user.id,
        joined_at=datetime.now(timezone.utc)
    )
    db.add(membership)
    
    # 4. Commit the transaction permanently
    await db.commit()
    
    return room

async def join_room(db: AsyncSession, user: User, room_id: UUID):
    room = await db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room does not exist")

    if await is_room_member(db, room_id, user.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already a member")

    membership = RoomMember(
        room_id=room_id,
        user_id=user.id,
        joined_at=datetime.now(timezone.utc)
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership

async def get_user_rooms(
    db: AsyncSession, 
    user_id: UUID, 
    skip: int = 0, 
    limit: int = 50
):
    result = await db.execute(
        select(Room)
        .join(RoomMember, RoomMember.room_id == Room.id)
        .where(RoomMember.user_id == user_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def is_room_member(db:AsyncSession,room_id:UUID,user_id:UUID):
    result = await db.execute(
        select(RoomMember)
        .where(RoomMember.room_id==room_id,RoomMember.user_id==user_id)
    )
    return result.scalar_one_or_none() is not None
async def get_room_members(
    db: AsyncSession, 
    room_id: UUID, 
    user_id: UUID, 
    skip: int = 0, 
    limit: int = 50
):
    membership_check = await is_room_member(db, room_id, user_id)
    if not membership_check:
        raise HTTPException(status_code=403, detail="You are not a member of this room")
        
    stmt = (
        select(User)
        .join(RoomMember, User.id == RoomMember.user_id)
        .where(RoomMember.room_id == room_id)
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    return result.scalars().all()