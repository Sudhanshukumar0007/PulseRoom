from fastapi import WebSocket, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.security import decode_access_token
from app.models.user import User


async def get_current_user_ws(websocket:WebSocket,db:AsyncSession)->User | None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
    
    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
    user_id = payload.get("sub")
    if user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
    
    result = await db.execute(select(User).where(User.id==user_id))
    user = result.scalar_one_or_none()

    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
    return user