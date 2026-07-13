from fastapi import FastAPI,WebSocket,WebSocketDisconnect,Depends
from app.core.config import settings
from fastapi.responses import HTMLResponse
from loguru import logger
from app.websockets.auth import get_current_user_ws
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.auth import router as auth_router
def create_app() ->FastAPI:
    app = FastAPI(
        title = settings.APP_NAME,
        version = settings.VERSION,
        debug  = settings.DEBUG,
        # docs_url = None,
        # redoc_url = None
    )
    app.include_router(auth_router)
    return app

app = create_app()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <h2>Your name: <span id="ws-id">connecting...</span></h2>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var token = prompt("Paste your access token:");
            var ws = new WebSocket(`ws://localhost:8000/ws?token=${token}`);

            ws.onmessage = function(event) {
                if (event.data.startsWith("Connected as ")) {
                    document.querySelector("#ws-id").textContent = event.data.replace("Connected as ", "");
                    return;
                }
                var messages = document.getElementById('messages');
                var message = document.createElement('li');
                var content = document.createTextNode(event.data);
                message.appendChild(content);
                messages.appendChild(message);
            };

            ws.onclose = function(event) {
                console.log("Closed:", event.code, event.reason);
                document.querySelector("#ws-id").textContent = "disconnected";
            };

            function sendMessage(event) {
                var input = document.getElementById("messageText");
                ws.send(input.value);
                input.value = '';
                event.preventDefault();
            }
        </script>
    </body>
</html>
"""


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()





@app.get("/")
async def get():
    return HTMLResponse(html)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket,db:AsyncSession = Depends(get_db)):
    user = await get_current_user_ws(websocket,db)
    if user is None:
        return
    await manager.connect(websocket)
    await websocket.send_text(f"Connected as {user.name}")   
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"{user.name} says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Connection closed")
        await manager.broadcast(f"{user.name} left the chat")