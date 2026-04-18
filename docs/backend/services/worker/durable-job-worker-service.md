# DurableJobWorkerService

Source: `backend/app/worker/durable_job_worker_service.py`

## Purpose

- Claims the next runnable durable job for the current worker.
- Executes the job through `DurableJobExecutor`.
- Publishes lifecycle updates back to realtime listeners.

## Public Interface

- `process_next() -> bool`

## Interactions

- Used by `WorkerRuntime.process_next_durable_job()`.
- Uses `DurableJobService` for claim/finish.
- Uses `DurableJobExecutor` for job-specific execution.
- Uses `RealtimeHub` for `job_status` and `error` events.

## Notes

- Failures are converted into failed durable-job status instead of being raised upward.
