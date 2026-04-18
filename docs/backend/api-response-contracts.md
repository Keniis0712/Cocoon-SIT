# API Response Contracts

Source: `backend/app/api/routes/`

## Purpose

- Documents the move away from ad-hoc `dict` responses in API routes.
- Ensures routes expose explicit response models that match the backend domain packages.

## Current Direction

- `access` routes use typed request/response schemas from `schemas/access/`.
- `workspace` routes use typed enqueue, list, and state schemas from `schemas/workspace/`.
- `observability` routes use typed audit/artifact/insight schemas from `schemas/observability/`.

## Notes

- Audit list/detail, artifact cleanup, tag binding, memory listing, wakeup enqueue, pull enqueue, and merge enqueue now all have explicit response contracts.
- The remaining route cleanup work should follow the same rule: no direct `dict` response unless the route is explicitly returning a free-form payload.
