from pydantic import BaseModel,Field,EmailStr,ConfigDict
from typing import Annotated
from uuid import UUID

class UserRegister(BaseModel):
    name:Annotated[str,Field(...,description="Name of the user:-",examples=["Sudhanshu Kumar"])]
    email:Annotated[EmailStr,Field(...,description="Email of the user ",examples=["Sudhanshu@gmail.com"])]
    password:Annotated[str,Field(...,min_length=6,description="Password of the user must be atleast 6 characters ",examples = ["sudhanshu@123"] )]

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:UUID
    name:str
    email:EmailStr

class Token(BaseModel):
    access_token:str
    token_type:str = "bearer"