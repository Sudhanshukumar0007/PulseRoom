from fastapi import HTTPException,status
from sqlalchemy.ext.asyncio import AsyncSession 
from app.schemas.user import UserRegister,UserResponse
from app.core.security import (
    hash_pwd,verify_pwd,create_access_token
)
from sqlalchemy import select
from app.models.user import User

async def get_user_by_email(db:AsyncSession,email:str) -> User | None:
    existing = await db.execute(select(User).where(User.email==email))
    return existing.scalar_one_or_none()


async def register_user(db:AsyncSession,user:UserRegister):
    existing = await get_user_by_email(db,user.email)
    if existing :
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = "Email already registered"
        )
    hashed_pwd = hash_pwd(user.password)
    user = User(
        name = user.name,
        email = user.email,
        hashed_password = hashed_pwd
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
async def login_user(db:AsyncSession,email:str,pwd:str):
    user = await get_user_by_email(db,email)
    if not user or not verify_pwd(pwd,user.hashed_password):
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Invalid email or password"
        )
    access_token = create_access_token({"sub":str(user.id)})
    return {
        "access_token":access_token,
        "token_type":"bearer"
    }
