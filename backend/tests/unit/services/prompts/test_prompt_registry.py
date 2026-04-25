import pytest

from app.models.entities import PromptTemplateType
from app.services.prompts.registry import (
    PROMPT_VARIABLES_BY_TYPE,
    get_default_template_payload,
)


def test_prompt_registry_exposes_expected_variable_groups():
    assert "character_settings" in PROMPT_VARIABLES_BY_TYPE[PromptTemplateType.system]
    assert "merge_context" in PROMPT_VARIABLES_BY_TYPE[PromptTemplateType.merge]
    assert "visible_messages" in PROMPT_VARIABLES_BY_TYPE[PromptTemplateType.audit_summary]
    assert "wakeup_context" in PROMPT_VARIABLES_BY_TYPE[PromptTemplateType.meta]
    assert "wakeup_context" in PROMPT_VARIABLES_BY_TYPE[PromptTemplateType.generator]


def test_get_default_template_payload_returns_named_template_and_rejects_unknown_type():
    name, description, content = get_default_template_payload(PromptTemplateType.generator)

    assert isinstance(name, str)
    assert description == ""
    assert isinstance(content, str)

    with pytest.raises(KeyError):
        get_default_template_payload("missing")
