# InsightQueryService

Source: `backend/app/services/observability/insight_query_service.py`

## Purpose

- Builds typed insight summaries from aggregate database queries.

## Public Interface

- `summary(session) -> InsightsSummary`

## Interactions

- Used by `api/routes/observability/insights.py`.
- Aggregates counts from actions, durable jobs, audit runs, messages, memory chunks, and users.
