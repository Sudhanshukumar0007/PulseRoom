

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.main import app
from app.core.config import settings
from app.db.session import get_db

# dedicated test engine -- NullPool avoids the cross-event-loop connection reuse bug
test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)


async def _override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# swap the REST dependency for the whole test session
app.dependency_overrides[get_db] = _override_get_db


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncSession:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def registered_user(client):
    """Creates a user via the real /auth/register endpoint and returns (email, password, token)."""
    import uuid
    email = f"user_{uuid.uuid4().hex[:8]}@test.com"
    password = "testpass123"

    resp = await client.post("/auth/register", json={
        "name": "Test User",
        "email": email,
        "password": password,
    })
    assert resp.status_code == 200, resp.text

    login_resp = await client.post("/auth/login", data={
        "username": email,
        "password": password,
    })
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]

    return {"email": email, "password": password, "token": token, "user_id": resp.json()["id"]}
