from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, status
from app.core.config import settings
from fastapi.responses import HTMLResponse
from loguru import logger
from app.websockets.auth import get_current_user_ws
from app.db.session import get_db
from uuid import UUID
from app.services.room_service import is_room_member
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.auth import router as auth_router
from app.api.v1.room import router as rooms_router
from redis.asyncio import from_url
from contextlib import asynccontextmanager
import app.core.redis as redis_module
from app.presence.redis_presence import add_or_refresh_user_presence, remove_user_presence
from sqlalchemy import text
from app.core.redis import get_redis
from app.db.session import AsyncSessionLocal
import json
from app.presence.typing import set_typing_indicator

@asynccontextmanager
async def lifespan(app:FastAPI):
    try:
        redis_module.redis_client = from_url(
            settings.REDIS_URL,
            decode_responses = True,
        )
        await redis_module.redis_client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning(f"Redis unavailable at startup - cache disabled {e}")
    yield

    if redis_module.redis_client:
        await redis_module.redis_client.aclose()

def create_app() ->FastAPI:
    app = FastAPI(
        title = settings.APP_NAME,
        version = settings.VERSION,
        debug  = settings.DEBUG,
        lifespan = lifespan,
        # docs_url = None,
        # redoc_url = None
    )
    
    @app.get("/health")
    async def health():
        health_status = {
            "status": "healthy",
            "version": settings.VERSION,
            "database": "healthy",
            "redis": "healthy",
        }
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            health_status["database"] = "unhealthy"
            health_status["status"] = "degraded"

        try:
            redis = await get_redis()
            await redis.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            health_status["redis"] = "unhealthy"
            health_status["status"] = "degraded"

        return health_status
        
    app.include_router(auth_router)
    app.include_router(rooms_router)
    return app

app = create_app()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
        <style>
            .system-msg { color: #888; font-style: italic; font-size: 0.9em; }
            #typing-indicator { height: 20px; color: #888; font-style: italic; font-size: 0.85em; margin-top: 5px; }
        </style>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <h2>Your name: <span id="ws-id">connecting...</span></h2>
        <h3>Room: <span id="room-label"></span></h3>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        
        <!-- Typing indicator display area -->
        <div id="typing-indicator"></div>
        
        <ul id='messages'>
        </ul>
        <script>
            var token = prompt("Paste your access token:");
            var roomId = prompt("Paste the room ID:");
            document.querySelector("#room-label").textContent = roomId;

            var ws = new WebSocket(`ws://localhost:8000/ws/${roomId}?token=${token}`);

            ws.onopen = function(event) {
                console.log("WebSocket opened. Starting heartbeats.");
                setInterval(function() {
                    if (ws.readyState === WebSocket.OPEN) {
                        ws.send(JSON.stringify({type: "ping"}));
                    }
                }, 15000);
            };

            ws.onmessage = function(event) {
                if (event.data.startsWith("Connected as ")) {
                    document.querySelector("#ws-id").textContent = event.data.replace("Connected as ", "");
                    return;
                }

                var data;
                try {
                    data = JSON.parse(event.data);
                } catch (e) {
                    console.error("Received plain text message that couldn't be parsed:", event.data);
                    return;
                }

                // Handle incoming typing indicators
                if (data.type === "typing") {
                    var indicator = document.getElementById("typing-indicator");
                    indicator.textContent = `${data.user} is typing...`;
                    
                    // Clear it after 3 seconds to match the backend TTL
                    clearTimeout(indicator.timeout);
                    indicator.timeout = setTimeout(() => {
                        indicator.textContent = "";
                    }, 3000);
                    return; // Don't add typing events to the chat history
                }

                var messages = document.getElementById('messages');
                var message = document.createElement('li');
                
                if (data.type === "chat") {
                    message.textContent = `${data.user}: ${data.content}`;
                } else if (data.type === "system") {
                    message.textContent = `ℹ️ ${data.content}`;
                    message.className = "system-msg";
                } else {
                    message.textContent = JSON.stringify(data);
                }
                
                messages.appendChild(message);
            };

            function sendMessage(event) {
                var input = document.getElementById("messageText");
                if (input.value.trim() !== '') {
                    ws.send(JSON.stringify({type: "chat", content: input.value}));
                    input.value = '';
                }
                event.preventDefault();
            }

            // --- DAY 8: Typing Indicator Throttling ---
            var typingTimeout = null;
            document.getElementById("messageText").addEventListener("input", function() {
                if (!typingTimeout) {
                    if (ws.readyState === WebSocket.OPEN) {
                        ws.send(JSON.stringify({type: "typing"}));
                    }
                }
                clearTimeout(typingTimeout);
                typingTimeout = setTimeout(function() { typingTimeout = null; }, 3000);
            });
        </script>
    </body>
</html>
"""

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[UUID,list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: UUID):
        await websocket.accept()
        self.active_connections.setdefault(room_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: UUID):
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast(self, room_id: UUID, message: str):
        for connection in self.active_connections.get(room_id, []):
            await connection.send_text(message)

manager = ConnectionManager()


@app.get("/")
async def get():
    return HTMLResponse(html)

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    user = await get_current_user_ws(websocket, db)
    if user is None:
        return
    if not await is_room_member(db, room_id, user.id):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
        
    await manager.connect(websocket, room_id)
    await websocket.send_text(f"Connected as {user.name}")   
    
    await add_or_refresh_user_presence(room_id, user.id)
    
    await manager.broadcast(room_id, json.dumps({
        "type": "system",
        "content": f"{user.name} joined the chat"
    }))
    
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue  

            msg_type = msg.get("type")

            if msg_type == "ping":
                await add_or_refresh_user_presence(room_id, user.id)
            elif msg_type == "typing":
                await set_typing_indicator(room_id, user.id, user.name)
                await manager.broadcast(room_id, json.dumps({
                    "type": "typing",
                    "user": user.name
                }))

            elif msg_type == "chat":
                await manager.broadcast(room_id, json.dumps({
                    "type": "chat",
                    "user": user.name,
                    "content": msg.get("content"),
                }))
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
        logger.info("Connection closed")
        
        await remove_user_presence(room_id, user.id)
        
        await manager.broadcast(room_id, json.dumps({
            "type": "system",
            "content": f"{user.name} left the chat"
        }))