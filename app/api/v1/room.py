from fastapi import Depends,APIRouter
from app.db.session import get_db
from app.api.deps import get_current_user
from app.schemas.room import RoomResponse,RoomMemberResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.schemas.user import UserResponse
from uuid import UUID
from app.schemas.room import RoomCreate
from app.services.room_service import(
    create_room,join_room,get_user_rooms,get_room_members
)


router = APIRouter(prefix="/rooms",tags = ["rooms"])

@router.post("/",response_model=RoomResponse)
async def create(data:RoomCreate,db:AsyncSession = Depends(get_db),user:User=Depends(get_current_user)):
    return await create_room(db, user, data)

@router.post("/{room_id}/join", response_model=RoomMemberResponse)
async def join(room_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await join_room(db, user, room_id)

@router.get("/me", response_model=list[RoomResponse])
async def my_rooms(
    skip: int = 0, 
    limit: int = 50, 
    user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    return await get_user_rooms(db, user.id, skip, limit)
@router.get("/{room_id}/members", response_model=list[UserResponse])
async def get_room_member(
    room_id: UUID, 
    skip: int = 0, 
    limit: int = 50, 
    db: AsyncSession = Depends(get_db), 
    user: User = Depends(get_current_user)
):
    return await get_room_members(db, room_id, user.id, skip, limit)
