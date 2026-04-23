# ExternalWakeupService

Source: `backend/app/services/plugins/external_wakeup_service.py`

## Purpose

- Converts validated external plugin event envelopes into the existing wakeup pipeline.
- Keeps plugin-originated events aligned with the same `WakeupTask + DurableJob + ChatRuntime` flow used by other scheduled runtime work.

## Accepted Envelope

Required outer fields:

- `summary`

Optional outer fields:

- `payload`

## Current Responsibilities

- reject disabled plugins or disabled events
- fan out the plugin event to configured `plugin_target_bindings`
- skip bindings whose target no longer exists
- skip users who cannot currently receive this plugin because of visibility, personal disablement, or unresolved plugin errors
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
- `target_binding_id`

## Notes

- v1 only creates wakeups. Plugins do not directly write messages into the workspace timeline.
- Plugins do not choose wakeup targets. Each user binds their own manageable cocoons or chat groups to visible plugins.
