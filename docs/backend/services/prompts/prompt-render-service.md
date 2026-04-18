# PromptRenderService

Source: `backend/app/services/prompts/prompt_render_service.py`

## Purpose

- Resolves the active prompt-template revision and renders it with sanitized runtime variables.
- Enforces that all required placeholders are provided at render time.

## Public Interface

- `render(session, template_type, variables) -> tuple[PromptTemplate, PromptTemplateRevision, dict, str]`

## Interactions

- Used by `PromptTemplateService.render()`.
- Called by runtime modules such as `MetaNode`, `PromptAssemblyService`, and memory compaction jobs.

## Notes

- The returned sanitized snapshot is intended for audit storage and debug visibility.
