from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect, status
from app.core.config import settings
from fastapi.responses import HTMLResponse
from loguru import logger
from app.websockets.auth import get_current_user_ws
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
from app.db.session import AsyncSessionLocal, get_db
import json
from app.presence.typing import set_typing_indicator
from app.pubsub.publisher import publish_message
from app.pubsub.subscriber import ensure_room_subscriber, stop_room_subscriber
from app.services.message_service import save_message, get_recent_messages, get_messages_since
from app.core.rate_limit import is_rate_limited

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        redis_module.redis_client = from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        await redis_module.redis_client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning(f"Redis unavailable at startup - cache disabled {e}")
    yield

    if redis_module.redis_client:
        await redis_module.redis_client.aclose()

def _create_base_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
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

app = _create_base_app()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>PulseRoom Debug Chat</title>
        <style>
            body { font-family: sans-serif; padding: 20px; }
            #controls { margin-bottom: 15px; }
            button { margin-right: 8px; padding: 4px 10px; }
            #typing-label { color: #888; font-style: italic; height: 20px; }
            .system { color: #888; font-style: italic; }
            .msg-id { font-size: 0.75em; color: #aaa; margin-left: 8px; }
        </style>
    </head>
    <body>
        <h1>WebSocket Chat (Debug)</h1>
        <h2>Your name: <span id="ws-id">connecting...</span></h2>
        <h3>Connected to: <span id="host-label"></span> | Room: <span id="room-label"></span></h3>

        <div id="controls">
            <button onclick="location.reload()">Reconnect / New Token</button>
        </div>

        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off" style="width: 300px;"/>
            <button>Send</button>
        </form>
        <div id="typing-label"></div>
        <ul id="messages"></ul>

        <script>
            // Manually prompt for credentials on every page load
            var token = prompt("Paste your access token:");
            var roomId = prompt("Paste the room ID:");
            var lastSeenId = prompt("Enter last_seen_message_id (Optional: leave blank to load normal history):");

            var ws; // Declare websocket globally for the input handlers

            if (!token || !roomId) {
                alert("Token and Room ID are required to connect. Please refresh the page and try again.");
            } else {
                document.querySelector("#host-label").textContent = window.location.host;
                document.querySelector("#room-label").textContent = roomId;

                // ---- URL construction with last_seen_message_id ----
                var wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
                var wsUrl = `${wsProtocol}//${window.location.host}/ws/${roomId}?token=${token}`;
                
                if (lastSeenId && lastSeenId.trim() !== "") {
                    wsUrl += `&last_seen_message_id=${lastSeenId.trim()}`;
                }
                
                ws = new WebSocket(wsUrl);

                ws.onopen = function() {
                    console.log("WebSocket opened. Starting heartbeats.");
                    setInterval(function() {
                        if (ws.readyState === WebSocket.OPEN) {
                            ws.send(JSON.stringify({ type: "ping" }));
                        }
                    }, 15000);
                };

                var typingClearTimer = null;

                ws.onmessage = function(event) {
                    var data;
                    try {
                        data = JSON.parse(event.data);
                    } catch (e) {
                        if (event.data.startsWith("Connected as ")) {
                            document.querySelector("#ws-id").textContent = event.data.replace("Connected as ", "");
                        } else {
                            appendMessage(event.data, true);
                        }
                        return;
                    }

                    if (data.type === "chat") {
                        // Display message ID nicely so you can copy it for testing the last_seen function
                        appendChatMessage(data.sender || 'Unknown', data.content || "", data.id);
                    } else if (data.type === "typing") {
                        document.querySelector("#typing-label").textContent = `${data.user} is typing...`;
                        clearTimeout(typingClearTimer);
                        typingClearTimer = setTimeout(function() {
                            document.querySelector("#typing-label").textContent = "";
                        }, 3000);
                    } else if (data.type === "system") {
                        appendMessage(data.content, true);
                    } else {
                        appendMessage(JSON.stringify(data), true);
                    }
                };

                ws.onclose = function(event) {
                    console.log("Closed:", event.code, event.reason);
                    document.querySelector("#ws-id").textContent = "disconnected";
                    appendMessage(`Connection closed (code ${event.code})`, true);
                };
            }

            function appendMessage(text, isSystem) {
                var messages = document.getElementById("messages");
                var li = document.createElement("li");
                if (isSystem) li.className = "system";
                li.appendChild(document.createTextNode(text));
                messages.appendChild(li);
            }
            
            function appendChatMessage(sender, content, id) {
                var messages = document.getElementById("messages");
                var li = document.createElement("li");
                li.appendChild(document.createTextNode(`${sender}: ${content}`));
                if (id) {
                    var idSpan = document.createElement("span");
                    idSpan.className = "msg-id";
                    idSpan.textContent = ` [ID: ${id}]`;
                    li.appendChild(idSpan);
                }
                messages.appendChild(li);
            }

            var typingSendTimeout = null;
            document.getElementById("messageText").addEventListener("input", function() {
                if (ws && ws.readyState === WebSocket.OPEN && !typingSendTimeout) {
                    ws.send(JSON.stringify({ type: "typing" }));
                }
                clearTimeout(typingSendTimeout);
                typingSendTimeout = setTimeout(function() { typingSendTimeout = null; }, 3000);
            });

            function sendMessage(event) {
                event.preventDefault();
                var input = document.getElementById("messageText");
                if (ws && ws.readyState === WebSocket.OPEN && input.value.trim() !== "") {
                    ws.send(JSON.stringify({ type: "chat", content: input.value }));
                    input.value = "";
                }
            }
        </script>
    </body>
</html>
"""

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[UUID, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: UUID):
        await websocket.accept()
        self.active_connections.setdefault(room_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: UUID):
        if room_id in self.active_connections:
            if websocket in self.active_connections[room_id]:
                self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast(self, room_id: UUID, message: str):
        for connection in list(self.active_connections.get(room_id, [])):
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"Removing failed websocket from room {room_id}: {e}")
                self.disconnect(connection, room_id)

manager = ConnectionManager()

MAX_CHAT_CONTENT_LENGTH = 1024


@app.get("/")
async def get():
    return HTMLResponse(html)

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    await handle_websocket(websocket, room_id, db)


async def handle_websocket(websocket: WebSocket, room_id: UUID, db: AsyncSession):
    if redis_module.redis_client is None:
        await websocket.close(code=1013)
        return

    user = await get_current_user_ws(websocket, db)
    if user is None:
        return
    if not await is_room_member(db, room_id, user.id):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    # Check for last_seen_message_id in query parameters
    last_seen_str = websocket.query_params.get("last_seen_message_id")
    last_seen_id = None
    if last_seen_str:
        try:
            last_seen_id = UUID(last_seen_str)
        except ValueError:
            logger.warning(f"Invalid UUID for last_seen_message_id: {last_seen_str}")
            pass
            
    ensure_room_subscriber(room_id, manager)
    await manager.connect(websocket, room_id)
    await websocket.send_text(f"Connected as {user.name}")
    
    # Use get_messages_since if we have a valid last_seen_id
    if last_seen_id:
        recent = await get_messages_since(db, room_id, last_seen_id, limit=50)
    else:
        recent = await get_recent_messages(db, room_id, limit=50)
        
    for msg in recent:
        sender_name = msg.sender.name if msg.sender else str(msg.sender_id)

        # Include the ID so the client can save it
        await websocket.send_text(json.dumps({
            "type": "chat",
            "id": str(msg.id),
            "sender": sender_name,
            "content": msg.content,
        }))   
    
    await add_or_refresh_user_presence(room_id, user.id)
    
    await publish_message(room_id, json.dumps({
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
                await publish_message(room_id, json.dumps({
                    "type": "typing",
                    "user": user.name
                }))

            elif msg_type == "chat":
                if await is_rate_limited(user.id):
                    await websocket.send_text(json.dumps({
                        "type": "system",
                        "content": "You're sending messages too fast. Slow down."
                    }))
                    continue  # drop this message, don't save or publish it

                
                # Save the message and capture the returned instance
                content = msg.get("content")
                if not isinstance(content, str):
                    await websocket.send_text(json.dumps({
                        "type": "system",
                        "content": "Message content must be text."
                    }))
                    continue

                content = content.strip()
                if not content:
                    await websocket.send_text(json.dumps({
                        "type": "system",
                        "content": "Message content cannot be empty."
                    }))
                    continue

                if len(content) > MAX_CHAT_CONTENT_LENGTH:
                    await websocket.send_text(json.dumps({
                        "type": "system",
                        "content": f"Message content cannot exceed {MAX_CHAT_CONTENT_LENGTH} characters."
                    }))
                    continue

                saved_msg = await save_message(db, room_id, user.id, content)
                
                # Prepare payload
                payload = {
                    "type": "chat", 
                    "sender": user.name, 
                    "content": content
                }
                
                # If save_message returns the model instance, broadcast its ID
                # (so active clients can update their local lastSeenId in real-time)
                if saved_msg and hasattr(saved_msg, "id"):
                    payload["id"] = str(saved_msg.id)
                    
                await publish_message(room_id, json.dumps(payload))
                        
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
        logger.info("Connection closed")
        
        await remove_user_presence(room_id, user.id)
        
        await publish_message(room_id, json.dumps({
            "type": "system",
            "content": f"{user.name} left the chat"
        }))
        if room_id not in manager.active_connections:  
            stop_room_subscriber(room_id)


def create_app() -> FastAPI:
    new_app = _create_base_app()
    new_app.add_api_route("/", get, methods=["GET"], response_class=HTMLResponse)
    new_app.add_api_websocket_route("/ws/{room_id}", websocket_endpoint)
    return new_app
