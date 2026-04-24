# MessageService

Source: `backend/app/services/workspace/message_service.py`

## Purpose

- Provides workspace-level message querying and formatting helpers.
- Keeps message retrieval rules and read-model assembly out of route handlers.

## Public Interface

- Message listing and lookup helpers exposed by `MessageService`

## Notes

- `MessageService` handles reads.
- `MessageDispatchService` handles enqueue/write-side behavior for chat actions.
