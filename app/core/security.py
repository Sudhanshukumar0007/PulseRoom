import bcrypt
from jose import jwt,JWTError
from app.core.config import settings
from datetime import datetime,timedelta,timezone

def hash_pwd(plain_pwd:str):
    pwd_bytes = plain_pwd.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes,salt).decode("utf-8")

def verify_pwd(plain_pwd:str,hashed_pwd:str):
    try:
        return bcrypt.checkpw(
            plain_pwd.encode("utf-8"),
            hashed_pwd.encode("utf-8")
        )
    except Exception:
        return False

def create_access_token(data:dict):
    copy_data = data.copy()
    copy_data["exp"] =  datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(copy_data,settings.SECRET_KEY,settings.ALGORITHM)

def decode_access_token(token:str) -> dict |None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None

    