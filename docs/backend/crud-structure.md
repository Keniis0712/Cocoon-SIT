# CRUD Structure

Source: `backend/app/crud/`

## Purpose

- Documents the domain-based organization of read/write helper modules.

## Packages

- `workspace/`: cocoon, message, session-state, and action-dispatch helpers.
- `catalog/`: provider and prompt-template listing helpers.
- `jobs/`: durable job enqueue helpers.

## Notes

- The old flat CRUD files have been removed.
- New imports should use the domain package path, for example `app.crud.workspace.cocoons`.
