# Container Structure

Source: `backend/app/core/container.py`, `backend/app/core/container_modules.py`

## Purpose

- Documents how the backend dependency graph is assembled.
- Separates the top-level container shell from the domain-specific wiring helpers.

## Structure

- `AppContainer` owns lifecycle, engine/session setup, backend selection, schema bootstrap, and shutdown.
- `container_modules.py` wires services by domain in a fixed order:
  - `wire_infrastructure_services`
  - `wire_security_services`
  - `wire_access_services`
  - `wire_prompt_and_audit_services`
  - `wire_provider_and_catalog_services`
  - `wire_workspace_services`
  - `wire_runtime_services`

## Notes

- This keeps the public container surface stable while making the composition order easier to read and test.
- `WorkerContainer` still extends `AppContainer` and adds worker-only runtime objects on top.
