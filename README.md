# Cocoon-SIT

Monorepo scaffold for the Cocoon-SIT AI workspace platform.

## Layout

- `backend/`: FastAPI API, worker, runtime, persistence, prompt templates, audit, memory, RBAC.
- `frontend/`: React/Vite admin console for workspace runtime, governance, prompt templates, and operations.
- `packages/ts-sdk/`: OpenAPI-driven TypeScript SDK generation target.
- `deploy/`: Docker Compose, Dockerfiles, init scripts, env templates.
- `docs/`: ADRs, event protocol, prompt variable documentation.

## Backend stack

- FastAPI
- SQLAlchemy 2 + Alembic
- Postgres + pgvector
- Redis Streams + Pub/Sub
- Pydantic Settings
- Fernet-based provider secret encryption

## Quick start

1. Copy `deploy/.env.example` to `.env` and adjust values.
2. Install workspace dependencies with `corepack pnpm install`.
3. In `backend/`, activate `.venv` and run `python -m uv run uvicorn app.main:app --reload`.
4. In `backend/`, start the worker with `python -m uv run python -m app.worker.main`.
5. Copy `frontend/.env.example` to `frontend/.env` if you want to change the backend target. In development the frontend now defaults to same-origin requests and uses the Vite dev proxy for `/api`.
6. In `frontend/`, run `corepack pnpm dev`.
7. Sign in at `http://127.0.0.1:5173` with `admin / admin`.

## Docker Compose

- Full stack with bundled frontend:
  - `docker compose -f deploy/docker-compose.yml up --build`
- The `api` image now builds the frontend and serves it as static files on the same origin.
- The Docker `api` service now runs `alembic upgrade head` before startup, so schema changes are applied automatically to existing Postgres volumes.
- The Alembic baseline has been reset to the current schema. If you still have an older local Postgres volume from before this reset, drop it once with `docker compose -f deploy/docker-compose.yml down -v` before bringing the stack back up.
- Open the app at `http://127.0.0.1:8000`.

## Docker Development

- Dev stack with hot reload backend, worker, and Vite:
  - `docker compose -f deploy/docker-compose.dev.yml up --build`
- If you previously started an older dev stack definition, reset old named volumes first:
  - `docker compose -f deploy/docker-compose.dev.yml down -v`
- Development URLs:
  - Frontend: `http://127.0.0.1:5173`
  - Backend API: `http://127.0.0.1:8000`
- The dev frontend uses Vite proxying to reach the Compose `api` service at `http://api:8000`, so backend CORS can stay disabled.

## Contract Sync

- Export and regenerate the TypeScript SDK after backend API changes with `pnpm run sdk:sync`.
- Verify SDK typing and backend regression coverage with `pnpm run sdk:verify`.
- Backend-side contract notes live in `docs/backend/sdk-contract.md`.

## Embedding And Vector Memory

- The admin and web UI can store multiple `EmbeddingProvider` configs, including `local_cpu` and `openai_compatible`.
- The backend enforces single-active behavior: enabling one embedding provider automatically disables the others.
- If no embedding provider is enabled, normal chat and memory flows still work, but vector retrieval is skipped.
- Vector retrieval is implemented for Postgres with the `vector` extension. SQLite remains the default development and test database.
- The `/embedding-providers` page is a "multiple configs, single enabled provider" surface. Multi-active embedding is not supported.

## Testing

- Default backend tests run against SQLite and the in-memory queue/backplane adapters.
- Tests that require Postgres vector retrieval are marked `pgvector` and skip automatically unless `COCOON_PGVECTOR_TEST_DATABASE_URL` is configured.
- Run the pgvector integration tests explicitly from `backend/` with `.\.venv\Scripts\python.exe -m pytest tests/integration/test_pgvector_memory.py -q`.
- Vector-memory implementation and test constraints are documented in `docs/vector-memory.md`.

## Current implementation focus

This repository already includes:

- Monorepo workspace layout
- Running FastAPI application scaffold
- Chat dispatch ledger + queue abstraction
- WebSocket realtime backplane abstraction
- Prompt template management with versioned revisions
- Audit artifact storage abstraction with filesystem implementation
- Durable job table/service skeleton
- Tests for chat flow, prompt templates, provider credential encryption, and durable jobs

## Invite Management

- The admin invite console now uses real backend-backed actions for creating invite codes, revoking unused codes, granting quota, and reading personal or group quota summaries.
- Invite-code creation can consume from a user bucket, a group bucket, or `ADMIN_OVERRIDE`.
- Revoking an unused invite code refunds capacity implicitly by removing that code from summary consumption.
- Quota grants are stored separately from invite codes and appear in the invite grant ledger shown in the frontend.

## Notes

- Production should use Postgres + Redis via Docker Compose.
- Tests run against SQLite and in-memory queue/backplane adapters by default; pgvector coverage is opt-in and uses Postgres.
- Future schema changes should be added as new Alembic revisions after `0001_initial`; `0001_initial` is now the frozen baseline for fresh environments.
- Prompt templates are global and immediately effective, but every save creates an immutable revision.
- The frontend defaults to same-origin API calls; local development uses the Vite proxy to forward `/api` to the backend target.
- Backend CORS is now off by default and only enabled when `COCOON_CORS_ORIGINS` is explicitly configured.
- Worker-only files now live under `backend/app/worker/`; API/shared files stay in `backend/app/api/`, `core/`, and `services/`.
- Artifact cleanup now enqueues durable jobs instead of deleting synchronously from the admin API.
