# Workspace Targets

Source: `backend/app/services/workspace/targets.py`

## Purpose

- Normalizes workspace target identifiers used by message dispatch, realtime delivery, and plugin integrations.
- Encodes the shared "cocoon vs chat group" targeting rules in one place.

## Public Interface

- Target parsing and formatting helpers in `targets.py`

## Notes

- Keep target-shape changes centralized here so websocket events, jobs, and plugin delivery stay aligned.
