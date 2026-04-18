# RoundPreparationService

Source: `backend/app/services/runtime/round_preparation_service.py`

## Purpose

- Normalizes one incoming runtime action into a runnable round.
- Applies pre-run cleanup for `edit` and `retry`.
- Opens the audit run used by the rest of the orchestration pipeline.

## Public Interface

- `prepare(session, action) -> tuple[RuntimeEvent, AuditRun]`

## Interactions

- Called by `ChatRuntime` at the start of every round.
- Delegates cleanup to `RoundCleanupService`.
- Delegates audit-run creation to `AuditService`.

## Notes

- This service is intentionally limited to "before the round starts".
- It does not build context or generate replies.
