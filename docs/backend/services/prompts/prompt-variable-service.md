# PromptVariableService

Source: `backend/app/services/prompts/prompt_variable_service.py`

## Purpose

- Synchronizes prompt-variable declarations from the code registry into persistent metadata rows.
- Ensures admin tooling can inspect allowed variables before any manual template edits.

## Public Interface

- `sync_registry_defaults(session)`

## Interactions

- Called by `PromptTemplateService.ensure_defaults()`.
- Reads variable declarations from `registry.py`.

## Notes

- This service only inserts missing metadata rows. It does not remove historical variables.
