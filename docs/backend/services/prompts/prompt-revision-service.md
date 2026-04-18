# PromptRevisionService

Source: `backend/app/services/prompts/prompt_revision_service.py`

## Purpose

- Owns prompt-template lookup and revisioned persistence.
- Validates placeholders against the registered variable set before saving.
- Creates a new `PromptTemplateRevision` for every successful update.

## Public Interface

- `ensure_default_templates(session)`
- `list_templates(session)`
- `get_template(session, template_type)`
- `get_active_revision(session, template)`
- `upsert_template(session, template_type, name, description, content, actor_user_id)`

## Interactions

- Used by `PromptTemplateService`.
- Used indirectly by prompt-template admin APIs through the facade.

## Notes

- Updates are append-only at the revision layer; the active revision pointer is moved forward instead of editing history in place.
