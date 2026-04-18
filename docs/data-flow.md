# Core Data Flow

1. Client sends `POST /api/v1/cocoons/{id}/messages`.
2. API writes the user message and an `ActionDispatch` ledger row.
3. API enqueues a short-lived chat dispatch into Redis Streams or the in-memory test backend.
4. Worker consumes the dispatch, builds runtime context, renders prompt templates, and publishes WS events through the realtime backplane.
5. Side effects persist assistant messages, session state updates, memory chunks, and audit records.
6. Durable jobs such as merge/pull/wakeup/rollback are stored in Postgres and claimed by workers with `SKIP LOCKED`.

