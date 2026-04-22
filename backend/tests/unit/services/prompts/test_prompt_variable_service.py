from types import SimpleNamespace

from app.services.prompts.prompt_variable_service import PromptVariableService


def test_prompt_variable_service_syncs_missing_registry_entries_and_skips_existing():
    added = []
    existing_pairs = {
        ("system", "character_settings"),
    }

    class _Session:
        def scalar(self, query):
            compiled = str(query)
            for template_type, variable_name in existing_pairs:
                if template_type in compiled and variable_name in compiled:
                    return SimpleNamespace()
            return None

        def add(self, item):
            added.append(item)

        def flush(self):
            added.append("flushed")

    service = PromptVariableService()
    service.sync_registry_defaults(_Session())

    assert any(getattr(item, "template_type", None) == "meta" for item in added)
    assert any(getattr(item, "variable_name", None) == "visible_messages" for item in added)
    assert "flushed" in added
