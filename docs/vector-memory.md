# Vector Memory And Test Strategy

## Summary

The current vector-memory implementation keeps SQLite as the default local test database and enables semantic retrieval only when the backend runs against Postgres with the `vector` extension available.

## Embedding Provider Rules

- The system may store multiple `EmbeddingProvider` records.
- Supported provider kinds are `local_cpu` and `openai_compatible`.
- The web UI exposes all configured providers on `/embedding-providers`.
- Only one provider may be enabled at a time.
- Enabling a provider is an atomic backend operation that disables every other embedding provider in the same transaction.
- If no provider is enabled, runtime execution continues without vector retrieval.
- If the database ever contains more than one enabled embedding provider, runtime treats that as invalid state and raises an error.

## Persistence Model

- `memory_chunks` remains the canonical long-term memory table.
- `memory_embeddings` stores vector materialization for a chunk, including:
  - `memory_chunk_id`
  - `embedding_provider_id`
  - `model_name`
  - `dimensions`
  - `embedding`
  - `created_at`
- `MemoryChunk.embedding_ref` points at the persisted embedding record.
- New assistant output, compaction summaries, pull summaries, and merge summaries follow the same write order:
  1. create `MemoryChunk`
  2. generate embeddings if an active provider exists
  3. persist `memory_embeddings`
  4. backfill `embedding_ref`

## Retrieval Rules

- Retrieval always filters by `cocoon_id`, scope, and tag visibility before scoring.
- Isolated tags remain hard visibility boundaries for messages, memories, pull candidates, and merge candidates.
- Postgres vector retrieval combines semantic similarity with recency.
- SQLite never attempts vector ranking and falls back to non-vector visible-memory retrieval.

## Test Strategy

- The default `pytest` path uses SQLite.
- Vector-specific tests are marked with `@pytest.mark.pgvector`.
- Those tests skip automatically unless `COCOON_PGVECTOR_TEST_DATABASE_URL` is set.
- The current integration entry point is `backend/tests/integration/test_pgvector_memory.py`.
- Recommended command:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/integration/test_pgvector_memory.py -q
```

## Practical Notes

- Local development can keep SQLite for most work.
- Run the pgvector integration tests when changing retrieval, embedding-provider activation, or vector persistence behavior.
- The frontend should describe embedding providers as "multiple configs, single active provider" rather than as a multi-active pool.
