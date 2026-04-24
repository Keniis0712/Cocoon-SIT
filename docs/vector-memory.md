# Vector Memory

## Purpose

- Describe how vector retrieval works in this repo.
- Document the split between default SQLite development and optional Postgres `pgvector` coverage.

## Runtime Model

- The memory service can store plain memory records without vector retrieval.
- Vector similarity search is enabled only when the backing database supports the `vector` extension.
- Local development and most tests still default to SQLite.

## Configuration

- Enable an embedding provider in the admin/backend configuration before expecting vector retrieval results.
- Postgres environments need the `vector` extension installed before vector-backed tests or runtime retrieval can succeed.

## Testing

- Default backend tests run without `pgvector`.
- Tests marked for vector retrieval skip unless `COCOON_PGVECTOR_TEST_DATABASE_URL` is configured.
- The dedicated pgvector coverage currently lives in:
  - `backend/tests/integration/test_pgvector_memory.py`
  - `backend/tests/integration/test_pgvector_chat_group_flow.py`

## Generated Data

- `MemoryService` remains the main service entrypoint for memory writes and retrieval orchestration.
- Embedding provider enablement determines whether vector embeddings are written and queried.
