import pytest


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_room_auto_joins_creator(client, registered_user):
    resp = await client.post(
        "/rooms/",
        json={"name": "Creator's Room"},
        headers=auth_headers(registered_user["token"]),
    )
    assert resp.status_code == 200
    room = resp.json()
    assert room["name"] == "Creator's Room"

    my_rooms = await client.get("/rooms/me", headers=auth_headers(registered_user["token"]))
    assert my_rooms.status_code == 200
    room_ids = [r["id"] for r in my_rooms.json()]
    assert room["id"] in room_ids


@pytest.mark.asyncio
async def test_second_user_can_join_room(client, registered_user):
    # second user, created inline rather than via the shared fixture
    import uuid
    email = f"joiner_{uuid.uuid4().hex[:8]}@test.com"
    await client.post("/auth/register", json={"name": "Joiner", "email": email, "password": "pass1234"})
    login = await client.post("/auth/login", data={"username": email, "password": "pass1234"})
    joiner_token = login.json()["access_token"]

    room_resp = await client.post(
        "/rooms/",
        json={"name": "Shared Room"},
        headers=auth_headers(registered_user["token"]),
    )
    room_id = room_resp.json()["id"]

    join_resp = await client.post(f"/rooms/{room_id}/join", headers=auth_headers(joiner_token))
    assert join_resp.status_code == 200

    joiner_rooms = await client.get("/rooms/me", headers=auth_headers(joiner_token))
    room_ids = [r["id"] for r in joiner_rooms.json()]
    assert room_id in room_ids


@pytest.mark.asyncio
async def test_joining_same_room_twice_rejected(client, registered_user):
    import uuid
    email = f"twice_{uuid.uuid4().hex[:8]}@test.com"
    await client.post("/auth/register", json={"name": "Twice", "email": email, "password": "pass1234"})
    login = await client.post("/auth/login", data={"username": email, "password": "pass1234"})
    token = login.json()["access_token"]

    room_resp = await client.post(
        "/rooms/", json={"name": "Room X"}, headers=auth_headers(registered_user["token"])
    )
    room_id = room_resp.json()["id"]

    first_join = await client.post(f"/rooms/{room_id}/join", headers=auth_headers(token))
    assert first_join.status_code == 200

    second_join = await client.post(f"/rooms/{room_id}/join", headers=auth_headers(token))
    assert second_join.status_code == 400


@pytest.mark.asyncio
async def test_joining_nonexistent_room_returns_404(client, registered_user):
    import uuid
    fake_room_id = str(uuid.uuid4())
    resp = await client.post(f"/rooms/{fake_room_id}/join", headers=auth_headers(registered_user["token"]))
    assert resp.status_code == 404