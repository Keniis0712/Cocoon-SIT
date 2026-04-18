# PromptTemplateService

Source: `backend/app/services/prompts/service.py`

## Purpose

- Acts as the facade for prompt metadata, revision persistence, and runtime rendering.
- Keeps existing callers stable while prompt internals are split into smaller services.

## Public Interface

- `ensure_defaults(session)`
- `list_templates(session)`
- `get_template(session, template_type)`
- `get_active_revision(session, template)`
- `upsert_template(session, template_type, name, description, content, actor_user_id)`
- `render(session, template_type, variables)`

## Interactions

- Used by prompt-template admin APIs, runtime prompt assembly, meta evaluation, and memory compaction.
- Delegates to `PromptVariableService`, `PromptRevisionService`, and `PromptRenderService`.

## Notes

- The facade remains intentionally thin so upstream modules do not need to know about the internal split.
