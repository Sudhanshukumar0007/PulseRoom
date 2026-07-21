"""
WebSocket integration tests.

These need REAL Postgres + Redis running (docker compose up -d) since the
endpoint touches both directly — this isn't mocked out. Uses FastAPI's
TestClient (sync) rather than httpx.AsyncClient, since websocket_connect()
isn't supported on the async client the same way.
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _register_and_login(client: TestClient, name: str) -> dict:
    email = f"{name}_{uuid.uuid4().hex[:8]}@test.com"
    password = "testpass123"

    reg = client.post("/auth/register", json={"name": name, "email": email, "password": password})
    assert reg.status_code == 200

    login = client.post("/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200

    return {"token": login.json()["access_token"], "user_id": reg.json()["id"]}


def _create_room(client: TestClient, token: str, name: str) -> str:
    resp = client.post("/rooms/", json={"name": name}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    return resp.json()["id"]


def test_ws_rejects_connection_without_token(client):
    user = _register_and_login(client, "NoTokenTest")
    room_id = _create_room(client, user["token"], "No Token Room")

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/{room_id}"):
            pass
    assert exc.value.code == 1008


def test_ws_rejects_non_member(client):
    owner = _register_and_login(client, "Owner")
    outsider = _register_and_login(client, "Outsider")
    room_id = _create_room(client, owner["token"], "Members Only Room")

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/{room_id}?token={outsider['token']}"):
            pass
    assert exc.value.code == 1008


def test_ws_member_connects_and_gets_greeting(client):
    user = _register_and_login(client, "Greeted")
    room_id = _create_room(client, user["token"], "Greeting Room")

    with client.websocket_connect(f"/ws/{room_id}?token={user['token']}") as ws:
        first_message = ws.receive_text()
        assert "Connected as" in first_message
        assert "Greeted" in first_message


def test_ws_broadcasts_chat_between_two_members(client):
    userA = _register_and_login(client, "Alice")
    userB = _register_and_login(client, "Bob")
    room_id = _create_room(client, userA["token"], "Broadcast Room")

    client.post(f"/rooms/{room_id}/join", headers={"Authorization": f"Bearer {userB['token']}"})

    with client.websocket_connect(f"/ws/{room_id}?token={userA['token']}") as wsA:
        wsA.receive_text()  # "Connected as Alice"

        with client.websocket_connect(f"/ws/{room_id}?token={userB['token']}") as wsB:
            wsB.receive_text()  # "Connected as Bob"
            wsA.receive_json()  # "Bob joined the chat" system message picked up by A

            import json
            wsA.send_text(json.dumps({"type": "chat", "content": "hello from alice"}))

            received = wsB.receive_json()
            while received["type"] != "chat":
                received = wsB.receive_json()

            assert received["type"] == "chat"
            assert received["sender"] == "Alice"
            assert received["content"] == "hello from alice"
