# ExternalWakeupService

Source: `backend/app/services/plugins/external_wakeup_service.py`

## Purpose

- Converts validated external plugin event envelopes into the existing wakeup pipeline.
- Keeps plugin-originated events aligned with the same `WakeupTask + DurableJob + ChatRuntime` flow used by other scheduled runtime work.

## Accepted Envelope

Required outer fields:

- `target_type`: `cocoon` or `chat_group`
- `target_id`
- `summary`

Optional outer fields:

- `dedupe_key`
- `payload`

## Current Responsibilities

- reject disabled plugins or disabled events
- validate target existence
- dedupe by `(plugin_id, event_name, dedupe_key)`
- create immediate wakeups through `SchedulerNode`
- record `PluginDispatchRecord`

## Wakeup Payload Additions

The created wakeup payload stores:

- `source_kind = "plugin"`
- `plugin_id`
- `plugin_version`
- `plugin_event`
- `external_payload`
- `summary`
- `dedupe_key`

## Notes

- v1 only creates wakeups. Plugins do not directly write messages into the workspace timeline.
