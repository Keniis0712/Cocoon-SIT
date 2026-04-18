# ADR-0001: Cocoon-SIT Monorepo Architecture

## Status

Accepted

## Decision

Use a monorepo with:

- `backend/` for the FastAPI API, worker, runtime, persistence, audit, prompt, and security services.
- `frontend/` for the React/Vite admin console.
- `packages/ts-sdk/` for generated OpenAPI client artifacts consumed by the frontend.
- `deploy/` for Compose and Docker build assets.

## Rationale

- Frontend and backend share a stable contract through OpenAPI.
- Prompt templates, audit flows, and realtime contracts need coordinated evolution.
- Local development stays simple with Docker Compose.

