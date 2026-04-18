# WorkerRuntime

Source: `backend/app/worker/runtime.py`

## Purpose

- Provides the top-level worker facade used by tests, scripts, and the worker container.
- Delegates chat-dispatch handling and durable-job handling to dedicated worker services.

## Public Interface

- `process_next_chat_dispatch() -> bool`
- `process_next_durable_job() -> bool`

## Interactions

- Composes `ChatDispatchWorkerService` and `DurableJobWorkerService`.
- Built by `WorkerContainer`.

## Notes

- `WorkerRuntime` no longer owns the detailed execution logic; it is a coordination shell.
