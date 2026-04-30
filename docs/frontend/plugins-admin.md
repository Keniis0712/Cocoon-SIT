# Frontend Plugin Admin

Updated: 2026-04-19

## Purpose

Documents the frontend admin surface for the backend plugin system exposed under `/api/v1/admin/plugins`.

## Backend Contract Now Available

The frontend can already rely on these admin actions:

- list plugins
- list shared dependency packages
- fetch plugin detail
- install plugin zip
- update plugin zip
- enable/disable plugin
- delete plugin
- update plugin-level config
- update event-level config
- enable/disable plugin events

## Current UI

The plugin admin UI is now wired and available under the admin plugins route.

Implemented frontend pieces:

- `frontend/src/pages/AdminPlugins.tsx`
- `frontend/src/api/admin-plugins.ts`
- `frontend/src/api/types/plugins.ts`

Current screen capabilities:

- browse installed plugins
- inspect plugin detail, versions, runtime state, and events
- upload zip files for install or update
- enable/disable plugins
- delete plugins
- edit plugin-level config from backend JSON Schema
- edit event-level config from backend JSON Schema
- enable/disable individual events
- inspect the shared dependency warehouse, including per-package version size and reference count

## Form Rendering

Both plugin-level config and event-level config are now backed by JSON Schema from the backend.

Frontend responsibilities:

- render schema-driven forms
- preserve unknown config keys when editing
- support file upload for install/update
- display active version, events, enable state, and runtime state
- display shared warehouse package inventory and deduplicated package reuse

## Route Boundary

- Admin plugin management lives at `/admin/plugins`
- The separate `/plugins` screen is the workspace/user-facing plugin binding and per-target configuration surface

## Remaining Gaps

- The schema renderer currently handles common object/enum/boolean/number/string cases and falls back to raw JSON for more complex schemas.
- Shared warehouse data is currently read-only in the UI; cleanup remains automatic on plugin deletion rather than a manual admin action.
