# InMemoryChatDispatchQueue

Source: `backend/app/services/jobs/in_memory_chat_dispatch_queue.py`

## Purpose

- Provides an in-process chat dispatch queue for tests and single-process development.

## Public Interface

- `enqueue(action_id, cocoon_id, event_type, payload)`
- `consume_next()`
- `ack(envelope)`

## Interactions

- Implements `ChatDispatchQueue`.
- Used by the app container when `chat_dispatch_backend=memory`.
