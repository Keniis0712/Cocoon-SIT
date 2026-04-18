# Schema Structure

Source: `backend/app/schemas/`

## Purpose

- Documents the domain-based schema package layout.
- Replaces the old flat schema file layout with grouped request/response modules.

## Packages

- `access/`: auth, users, roles, groups, invites.
- `catalog/`: characters, providers, models, embedding providers, prompt templates, tags.
- `workspace/`: cocoons, checkpoints, workspace jobs.
- `observability/`: audits, artifacts, insights.
- `realtime/`: websocket event payloads.
- `common.py`: shared base response and ORM helpers.

## Notes

- The old flat files under `backend/app/schemas/*.py` have been removed.
- New imports should target the domain package directly, for example `app.schemas.catalog.prompts`.
