# Model Structure

Source: `backend/app/models/`

## Purpose

- Documents the split of the former monolithic `entities.py` file into domain-oriented model modules.
- Keeps import compatibility for existing callers.

## Modules

- `identity.py`: shared ID/time helpers.
- `enums.py`: shared status and type enums.
- `access.py`: users, roles, sessions, invites, groups.
- `catalog.py`: characters, providers, models, tags.
- `workspace.py`: cocoons, messages, memory, session state.
- `jobs.py`: action dispatch, durable jobs, wakeups, pull/merge jobs, checkpoints.
- `audit.py`: audit runs, steps, artifacts, links.
- `prompts.py`: prompt templates, revisions, variables.

## Compatibility

- `backend/app/models/entities.py` now acts as a compatibility export layer.
- `backend/app/models/__init__.py` continues to expose the same top-level model names used across the codebase.
