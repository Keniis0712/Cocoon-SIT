# Cocoon-SIT

English | [简体中文](README.zh-CN.md)

Monorepo for the Cocoon-SIT AI workspace platform.

## Repository Layout

- `backend/`: FastAPI API, worker runtime, persistence, prompts, audit, memory, RBAC, plugins
- `frontend/`: React/Vite admin console and workspace UI
- `packages/ts-sdk/`: OpenAPI-based TypeScript SDK
- `plugins/`: local example plugins and packaged plugin artifacts
- `deploy/`: Docker Compose files, Dockerfiles, env templates, init scripts
- `docs/`: maintained architecture and implementation notes

## Stack

### Backend

- FastAPI
- SQLAlchemy 2 + Alembic
- Postgres + pgvector
- Redis Streams + Pub/Sub
- Pydantic Settings
- Fernet-based provider secret encryption

### Frontend

- React 19
- Vite 6
- TypeScript
- Zustand
- i18next

## Quick Start

1. Copy `deploy/.env.example` to `deploy/.env` and adjust values.
2. Install workspace dependencies with `corepack pnpm install`.
3. Start the backend API with `pnpm run backend:dev`.
4. Start the worker with `pnpm run backend:worker`.
5. Copy `frontend/.env.example` to `frontend/.env` if you need a custom backend target.
6. Start the frontend with `pnpm run frontend:dev`.
7. Sign in at `http://127.0.0.1:5173` with `admin / admin`.

The frontend defaults to same-origin API calls in production and uses the Vite dev proxy for `/api` in local development.

## Docker

### Production-style stack

- `docker compose -f deploy/docker-compose.yml up --build`
- The bundled app is published on `http://127.0.0.1:8388`
- The `api` container runs `alembic upgrade head` before startup

### Development stack

- `docker compose -f deploy/docker-compose.dev.yml up --build`
- Frontend: `http://127.0.0.1:5173`
- Backend API: `http://127.0.0.1:8000`

If you previously used older compose definitions, reset stale named volumes with `docker compose ... down -v` before bringing the stack up again.

## SDK Sync

- Regenerate the TypeScript SDK after backend API changes: `pnpm run sdk:sync`
- Verify SDK typing and backend coverage: `pnpm run sdk:verify`

Backend-side SDK notes live in `docs/backend/sdk-contract.md`.

## Memory And Vector Retrieval

- Multiple embedding provider configs can exist, but only one can be enabled at a time.
- If no embedding provider is enabled, normal chat and memory flows still work, but vector retrieval is skipped.
- Vector retrieval is implemented for Postgres with the `vector` extension.
- SQLite remains the default local development and test database.

Implementation notes live in `docs/vector-memory.md`.

## Testing

- Default backend tests run against SQLite and in-memory queue/backplane adapters.
- pgvector integration tests are opt-in and require `COCOON_PGVECTOR_TEST_DATABASE_URL`.
- Run pgvector coverage explicitly from `backend/` with `.\.venv\Scripts\python.exe -m pytest tests/integration/test_pgvector_memory.py -q`.

Useful scripts from the repo root:

- `pnpm run frontend:lint`
- `pnpm run frontend:test`
- `pnpm run backend:test`
- `pnpm run backend:test:api`
- `pnpm run backend:test:integration`
- `pnpm run backend:test:unit`
- `pnpm run frontend:build`
- `pnpm run lint`
- `pnpm run check`

## Current Product Surface

The repository already includes:

- cocoon and chat-group workspaces
- unified runtime orchestration through `ChatRuntime`
- REST + WebSocket realtime flows
- prompt template management with versioned revisions
- audit artifacts and insights surfaces
- invite and quota management
- plugin installation, runtime management, and workspace/plugin bindings
- optional vector memory retrieval

## Notes

- Production should use Postgres + Redis through Docker Compose.
- Prompt templates are global and every save creates an immutable revision.
- Backend CORS is disabled by default and only enabled when `COCOON_CORS_ORIGINS` is configured.
- Worker-only files live under `backend/app/worker/`.
- Maintained implementation notes live under `docs/`; removed repo-root architecture drafts should be considered obsolete.
