# ChatDispatchWorkerService

Source: `backend/app/worker/chat_dispatch_worker_service.py`

## Purpose

- Consumes queued chat dispatch envelopes.
- Loads the corresponding `ActionDispatch`.
- Marks it running and forwards the work to `ChatRuntime`.

## Public Interface

- `process_next() -> bool`

## Interactions

- Used by `WorkerRuntime.process_next_chat_dispatch()`.
- Pulls messages from `ChatDispatchQueue`.
- Executes business orchestration through `ChatRuntime`.

## Notes

- Queue acknowledgement happens only after the database transaction completes.
