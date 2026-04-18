# RedisChatDispatchQueue

Source: `backend/app/services/jobs/redis_chat_dispatch_queue.py`

## Purpose

- Provides a Redis Streams-backed chat dispatch queue for multi-worker deployments.
- Preserves structured payloads through `ChatDispatchCodec`.

## Public Interface

- `enqueue(action_id, cocoon_id, event_type, payload)`
- `consume_next()`
- `ack(envelope)`

## Interactions

- Implements `ChatDispatchQueue`.
- Used by the app container when `chat_dispatch_backend=redis`.
