# WebSocket Event Protocol

Supported events:

- `dispatch_queued`
- `reply_started`
- `reply_chunk`
- `reply_done`
- `state_patch`
- `job_status`
- `error`

All events are emitted per cocoon channel and are treated as append-only facts for the frontend workspace.

Normal reply rounds follow this order:

1. `dispatch_queued`
2. initial `state_patch`
3. `reply_started`
4. `reply_chunk*`
5. `reply_done`
6. final `state_patch`

Silent rounds may emit only:

1. `dispatch_queued`
2. `state_patch`

`state_patch` now carries the latest session snapshot, including `current_wakeup_task_id` when present.

WebSocket clients must authenticate before subscribing. Browser clients should pass the same access token used for REST
calls through the `access_token` query parameter on `WS /api/v1/cocoons/{id}/ws`.
