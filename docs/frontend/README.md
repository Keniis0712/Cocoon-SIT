# Frontend Docs

Updated: 2026-04-19

## Scope

This directory holds frontend-facing architecture and implementation notes, organized in the same split style as `docs/backend/`.

Current coverage:

- [structure.md](./structure.md): source tree layout and layer boundaries
- [api-structure.md](./api-structure.md): API wrapper layout, adapters, and type modules
- [workspaces.md](./workspaces.md): cocoon/chat-group workspace architecture and shared runtime behavior
- [state-and-realtime.md](./state-and-realtime.md): Zustand session state and websocket flow
- [plugins-admin.md](./plugins-admin.md): admin plugin management UI and schema-driven forms

## Current Theme

The frontend is moving from a page-heavy structure toward a clearer split:

- `pages/` for route entry orchestration
- `features/` for domain UI blocks
- `api/` for backend contract adaptation
- `hooks/` and `store/` for shared runtime behavior

## Notes

- The maintained frontend notes live in this directory; removed repo-root drafts should be treated as obsolete.
- The current priority is to keep cocoon and chat-group chat flows structurally aligned without forcing them into one monolithic page.
