# StatePatchService

Source: `backend/app/services/runtime/orchestration/state_patch_service.py`

## Purpose

- Applies the `MetaDecision` state patch to `SessionState`.
- Broadcasts the resulting state snapshot to workspace subscribers.

## Public Interface

- `apply_and_publish(session, context, meta, action_id) -> SessionState`

## Interactions

- Called by `ChatRuntime` after `MetaNode` evaluation.
- Uses `SideEffects` for persistence.
- Uses `RealtimeHub` for the `state_patch` event.

## Notes

- Persistence and broadcasting are coupled here on purpose so the payload matches the committed state mutation.
