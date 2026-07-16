from fastapi import Depends,HTTPException,status
from fastapi.security import OAuth2PasswordBearer
from app.db.session import get_db
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl = "/auth/login")

async def get_current_user(
        token:str=Depends(oauth2_scheme),
        db:AsyncSession = Depends(get_db)
)->User:
    credentials_exception = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={'WWW-Authenticate':"Bearer"}
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id : str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id==user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    
    return user
