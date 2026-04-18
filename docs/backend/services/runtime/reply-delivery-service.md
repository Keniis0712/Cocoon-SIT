# ReplyDeliveryService

Source: `backend/app/services/runtime/reply_delivery_service.py`

## Purpose

- Delivers generated output to realtime subscribers.
- Persists the final assistant or system message plus memory entries.
- Records the output artifact and audit link for the generator step.

## Public Interface

- `deliver(session, context, action, audit_run, generator_step, generation) -> Message`

## Interactions

- Called by `ChatRuntime` after `GeneratorNode.generate(...)`.
- Uses `SideEffects` to persist messages and memory.
- Uses `RealtimeHub` to emit `reply_started`, `reply_chunk`, and `reply_done`.
- Uses `AuditService` to record the generator output artifact.

## Notes

- This service only handles output delivery. Prompt assembly and model invocation remain inside `GeneratorNode`.
