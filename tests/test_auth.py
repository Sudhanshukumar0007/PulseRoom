import uuid
import pytest


@pytest.mark.asyncio
async def test_register_new_user(client):
    email = f"reg_{uuid.uuid4().hex[:8]}@test.com"
    resp = await client.post("/auth/register", json={
        "name": "New User",
        "email": email,
        "password": "somepassword",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == email
    assert "id" in body
    assert "hashed_password" not in body  # response schema shouldn't leak the hash


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(client):
    email = f"dup_{uuid.uuid4().hex[:8]}@test.com"
    payload = {"name": "Dup User", "email": email, "password": "somepassword"}

    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 200

    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_login_correct_password(client, registered_user):
    resp = await client.post("/auth/login", data={
        "username": registered_user["email"],
        "password": registered_user["password"],
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password_rejected(client, registered_user):
    resp = await client.post("/auth/login", data={
        "username": registered_user["email"],
        "password": "definitely-wrong",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_email_rejected(client):
    resp = await client.post("/auth/login", data={
        "username": f"nobody_{uuid.uuid4().hex[:8]}@test.com",
        "password": "whatever",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_valid_token(client, registered_user):
    # no token at all
    resp = await client.get("/auth/me")
    assert resp.status_code == 401

    # garbage token
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401

    # real token
    resp = await client.get("/auth/me", headers={
        "Authorization": f"Bearer {registered_user['token']}"
    })
    assert resp.status_code == 200
    assert resp.json()["email"] == registered_user["email"]