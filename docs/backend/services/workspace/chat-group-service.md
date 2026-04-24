# ChatGroupService

Source: `backend/app/services/workspace/chat_group_service.py`

## Purpose

- Owns CRUD-style chat-group operations and membership-aware room setup.
- Provides a service-layer home for chat-group reads and mutations that should not live inside API routes.

## Public Interface

- Chat-group creation, lookup, update, and membership-related helpers exposed by `ChatGroupService`

## Notes

- This service complements `message_dispatch_service.py` and `workspace_realtime_service.py`.
- Route handlers should delegate business rules here instead of duplicating room validation logic.
