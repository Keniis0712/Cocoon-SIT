# PluginRuntimeManager

Source: `backend/app/services/plugins/manager.py`

## Purpose

- Coordinates short-lived event polling and long-running plugin processes.
- Starts when the app container starts and stops during shutdown.
- Bridges plugin runtime outputs back into the main system through `ExternalWakeupService`.

## Execution Model

### External `short_lived`

- Scheduled by the manager using `ProcessPoolExecutor`
- Each run loads the plugin through the bootstrap manifest
- Returns `None` for no event, or an event envelope dict for wakeup creation
- Newly installed events default to manual-only scheduling
- Automatic schedules are stored in admin-managed event schedule fields, not in `plugin.json`
- Supported schedule modes:
  - `manual`: never runs automatically; admin can trigger a run manually
  - `interval`: runs every configured number of seconds
  - `cron`: runs on a 5-field cron expression in server time

### External `daemon`

- All daemon events from one plugin run inside a single child process
- The child process loads the plugin once and starts all daemon functions as `asyncio` tasks
- Child heartbeats and event envelopes are returned through an IPC queue

### IM Plugins

- IM plugins run as their own long-running process
- They use the same bootstrap path but a separate IM SDK

## Current Responsibilities

- start/stop runtime supervision thread
- lazily create the short-lived process pool
- spawn external daemon processes
- spawn IM plugin processes
- consume heartbeat/event IPC messages
- schedule short-lived runs based on event schedule settings
- write `PluginRunState`

## Notes

- The current implementation assumes Windows-compatible spawn semantics.
- Updating an event schedule recalculates the next automatic run but does not run the event immediately.
- Manual runs do not update the stored in-memory `next_run` for automatic schedules.
- Backend tests now run these paths using the real backend virtualenv under `backend/.venv`.
- If plugin tables are not present yet during startup, the manager now skips plugin synchronization instead of continuously spamming database errors while migrations catch up.
