# PulseRoom

PulseRoom is a FastAPI backend for room-based realtime chat. It supports authenticated users, rooms, room membership, WebSocket chat, Redis-backed fan-out across multiple app instances, ephemeral presence and typing indicators, persisted message history, reconnect history replay, and per-user message rate limiting.

The project is intentionally backend-first. The `/` route serves a small debug chat page for manual WebSocket testing, but the main product surface is the HTTP API and WebSocket protocol.

## What It Does

- Registers and authenticates users with JWT access tokens.
- Creates chat rooms and automatically joins the room creator.
- Lets authenticated users join rooms and list their rooms/members.
- Accepts WebSocket connections only from authenticated room members.
- Persists chat messages in PostgreSQL.
- Replays recent messages when a user connects.
- Supports reconnect catch-up with `last_seen_message_id`.
- Broadcasts live room events through Redis Pub/Sub so multiple app instances can serve the same room.
- Tracks presence and typing state in Redis using TTL keys.
- Applies a Redis-backed sliding-window message rate limit.
- Provides `/health` for database and Redis health checks.

## Architecture

```text
Client
  |
  | HTTP: register, login, rooms
  | WS: /ws/{room_id}?token=...
  v
FastAPI app instance
  |
  | SQLAlchemy async
  v
PostgreSQL
  - users
  - rooms
  - room_members
  - messages

FastAPI app instance
  |
  | Redis async client
  v
Redis
  - Pub/Sub channels: room:{room_id}
  - Presence keys: presence:{room_id}:{user_id}
  - Typing keys: typing:{room_id}:{user_id}
  - Rate-limit sorted sets
```

For horizontal scaling, each app instance keeps only its own local WebSocket connections in memory. When a message or room event is produced, the app publishes it to Redis. Every active instance subscribed to that room receives the event and forwards it to its local WebSocket clients.

## Tech Stack

- FastAPI
- SQLAlchemy async
- PostgreSQL with `asyncpg`
- Redis async client
- Alembic migrations
- JWT auth with `python-jose`
- `bcrypt` password hashing
- `uv` for dependency management
- Pytest and pytest-asyncio
- Docker and Docker Compose

## Project Layout

```text
app/
  api/v1/              HTTP routes for auth and rooms
  core/                config, security, Redis, rate limiting
  db/                  SQLAlchemy engine/session/base
  models/              SQLAlchemy models
  presence/            Redis presence and typing helpers
  pubsub/              Redis publish/subscribe helpers
  schemas/             Pydantic request/response schemas
  services/            business logic for users, rooms, messages
  websockets/          WebSocket auth helper
  main.py              FastAPI app, health route, debug page, WebSocket endpoint

migrations/            Alembic migration environment and revisions
tests/                 HTTP and WebSocket integration tests
docker-compose.yml     Local Postgres + Redis + two app instances
Dockerfile             App container image
```

## Requirements

- Python 3.14
- `uv`
- PostgreSQL
- Redis

For local development, Docker Compose is the easiest way to run PostgreSQL and Redis.

## Environment Variables

Create a local `.env` file:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/pulseroom
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=replace-this-with-a-long-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_TIME=7
DEBUG=false
```

Do not commit `.env`. It is ignored by git and excluded from Docker builds.

## Local Setup

Install dependencies:

```bash
uv sync --frozen
```

Start PostgreSQL and Redis:

```bash
docker compose up -d postgres redis
```

Apply migrations:

```bash
uv run alembic upgrade head
```

Run the app:

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000
```

The root page is only a debug client. Use the API endpoints to register, log in, create a room, then paste the token and room ID into the debug page.

## Docker Compose

Run the full local stack:

```bash
docker compose up --build
```

Compose starts:

- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`
- A migration container that runs `alembic upgrade head`
- App instance 1 on `localhost:8000`
- App instance 2 on `localhost:8001`

This setup is useful for testing Redis Pub/Sub fan-out across two app instances.

## API Overview

### Auth

Register:

```http
POST /auth/register
Content-Type: application/json

{
  "name": "Alice",
  "email": "alice@example.com",
  "password": "secret123"
}
```

Login:

```http
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=alice@example.com&password=secret123
```

Current user:

```http
GET /auth/me
Authorization: Bearer <access_token>
```

### Rooms

Create a room:

```http
POST /rooms/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "General"
}
```

Join a room:

```http
POST /rooms/{room_id}/join
Authorization: Bearer <access_token>
```

List my rooms:

```http
GET /rooms/me
Authorization: Bearer <access_token>
```

List room members:

```http
GET /rooms/{room_id}/members
Authorization: Bearer <access_token>
```

### Health

```http
GET /health
```

The health response reports database and Redis status.

## WebSocket Protocol

Connect:

```text
ws://localhost:8000/ws/{room_id}?token=<access_token>
```

Reconnect with missed-message replay:

```text
ws://localhost:8000/ws/{room_id}?token=<access_token>&last_seen_message_id=<message_id>
```

The user must be authenticated and must already be a member of the room. Redis must be available because live chat fan-out depends on Redis Pub/Sub.

### Client Messages

Ping/presence refresh:

```json
{ "type": "ping" }
```

Typing indicator:

```json
{ "type": "typing" }
```

Chat message:

```json
{ "type": "chat", "content": "hello" }
```

Chat content must be a non-empty string and cannot exceed 1024 characters.

### Server Messages

Greeting:

```text
Connected as Alice
```

Chat:

```json
{
  "type": "chat",
  "id": "message-uuid",
  "sender": "Alice",
  "content": "hello"
}
```

Typing:

```json
{
  "type": "typing",
  "user": "Alice"
}
```

System event:

```json
{
  "type": "system",
  "content": "Alice joined the chat"
}
```

## Testing

The tests expect PostgreSQL and Redis to be running and migrated.

```bash
docker compose up -d postgres redis
uv run alembic upgrade head
uv run pytest
```

Expected result:

```text
15 passed
```

If `uv` warns about hardlinks under WSL or cross-filesystem paths, use:

```bash
export UV_LINK_MODE=copy
```

## CI

GitHub Actions is configured in:

```text
.github/workflows/ci.yml
```

CI starts PostgreSQL and Redis services, installs dependencies with `uv`, runs Alembic migrations, and runs the test suite.

## Deployment Notes

The Dockerfile starts the app with:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

For Render:

- Use the Docker runtime.
- Set environment variables in the Render dashboard.
- Set `DATABASE_URL` to Render PostgreSQL's internal connection string, converted to the async SQLAlchemy form if needed: `postgresql+asyncpg://...`.
- Set `REDIS_URL` to the Redis service URL.
- Set `SECRET_KEY` to a strong generated secret.
- Set `DEBUG=false`.
- Configure the pre-deploy command:

```bash
uv run alembic upgrade head
```

If using Render auto-deploy, choose "After CI Checks Pass" once GitHub Actions is green.

## Current Limitations

- WebSocket auth currently passes the JWT in the query string. This is functional and common for simple WebSocket clients, but URLs can appear in logs and browser history. A production frontend should prefer a safer auth transport such as a short-lived WebSocket ticket or secure cookie flow.
- Redis Pub/Sub is fire-and-forget. Messages are persisted to PostgreSQL, but Pub/Sub itself does not replay events to instances that were offline at publish time.
- The root HTML page is a debug tool, not a production frontend.
- There is no load balancer service in Docker Compose; the two app instances are exposed separately on ports `8000` and `8001`.

## Security Notes

- Passwords are stored as bcrypt hashes.
- JWTs are signed with `SECRET_KEY`; production must use a strong secret.
- Chat content is rendered as text in the debug client to avoid HTML/script execution.
- WebSocket chat rejects non-members.
- Message sending is rate-limited per user through Redis.
