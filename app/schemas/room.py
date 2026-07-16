from pydantic import BaseModel,Field
from typing import Annotated
from uuid import UUID
from datetime import datetime

class RoomCreate(BaseModel):
    name:Annotated[str,Field(...,description = "Name of the room",examples = ["lovers","haters"])]

class RoomResponse(BaseModel):
    id:UUID
    name:str
    created_by:UUID
    created_at:datetime

class RoomMemberResponse(BaseModel):
    id:UUID
    room_id:UUID
    user_id:UUID
    joined_at:datetime

