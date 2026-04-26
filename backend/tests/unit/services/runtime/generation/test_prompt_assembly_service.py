from types import SimpleNamespace

from app.services.runtime.generation.prompt_assembly_service import (
    PromptAssemblyService,
    _CONTEXT_HEADINGS,
    _GLOBAL_RULES_HEADING,
)
from app.services.runtime.types import ContextPackage, RuntimeEvent


def _build_context(*, event_type="chat", target_type="chat_group", include_source_messages=True):
    runtime_event = RuntimeEvent(
        event_type=event_type,
        cocoon_id="cocoon-1" if target_type == "cocoon" else None,
        chat_group_id="group-1" if target_type == "chat_group" else None,
        action_id="action-1",
        payload={},
    )
    visible_messages = [
        SimpleNamespace(role="user", content="hello", is_retracted=False, sender_user_id="user-1"),
        SimpleNamespace(role="assistant", content="prior", is_retracted=True, sender_user_id=None),
    ]
    return ContextPackage(
        runtime_event=runtime_event,
        conversation=SimpleNamespace(selected_model_id="model-1"),
        character=SimpleNamespace(),
        session_state=SimpleNamespace(),
        visible_messages=visible_messages,
        memory_context=[SimpleNamespace(scope="room", summary="sum", content="memory")],
        external_context=(
            {
                "source_messages": [
                    SimpleNamespace(role="user", content="pulled", is_retracted=False, sender_user_id=None)
                ],
                "source_memories": [SimpleNamespace(scope="external", summary="s2", content="m2")],
                "merge_context": {"source": "cocoon-2"},
            }
            if include_source_messages
            else {
                "source_memories": [SimpleNamespace(scope="external", summary="s2", content="m2")],
                "merge_context": {"source": "cocoon-2"},
            }
        ),
    )


def test_build_assembles_chat_prompt_and_formats_messages(monkeypatch):
    monkeypatch.setattr(
        "app.services.runtime.generation.prompt_assembly_service.build_runtime_prompt_variables",
        lambda context, provider_capabilities, include_wakeup_context=True: {
            "provider_capabilities": provider_capabilities
        },
    )
    calls = []
    prompt_service = SimpleNamespace(
        render=lambda **kwargs: calls.append(kwargs)
        or (
            {"template_type": kwargs["template_type"]},
            {"revision_id": f"{kwargs['template_type']}-rev"},
            dict(kwargs["variables"]),
            f"{kwargs['template_type']} prompt",
        )
    )

    result = PromptAssemblyService(prompt_service).build(
        session=object(),
        context=_build_context(include_source_messages=False),
        provider_capabilities={"streaming": True},
    )

    assert [call["template_type"] for call in calls] == ["system", "generator"]
    assert result.combined_prompt == "system prompt\n\ngenerator prompt"
    assert result.system.summary_prefix == "system"
    assert result.event.summary_prefix == "generator"
    assert result.messages[0] == {"role": "user", "content": "[speaker:participant_1] hello"}
    assert "[system note: this message was later retracted]" in result.messages[1]["content"]


def test_build_trims_repeated_character_context_from_system_prompt(monkeypatch):
    monkeypatch.setattr(
        "app.services.runtime.generation.prompt_assembly_service.build_runtime_prompt_variables",
        lambda context, provider_capabilities, include_wakeup_context=True: {
            "provider_capabilities": provider_capabilities
        },
    )
    prompt_service = SimpleNamespace(
        render=lambda **kwargs: (
            {"template_type": kwargs["template_type"]},
            {"revision_id": f"{kwargs['template_type']}-rev"},
            dict(kwargs["variables"]),
            (
                f"You are acting as the current Cocoon-SIT character.\n\n"
                f"{_CONTEXT_HEADINGS[0]}system-character\n\n"
                f"{_CONTEXT_HEADINGS[1]}system-state\n\n"
                "Provider capabilities: {}\n\n"
                f"{_GLOBAL_RULES_HEADING}\n1. stay in character"
                if kwargs["template_type"] == "system"
                else (
                    "Please generate the current character reply.\n\n"
                    f"{_CONTEXT_HEADINGS[0]}event-character\n\n"
                    f"{_CONTEXT_HEADINGS[1]}event-state"
                )
            ),
        )
    )

    result = PromptAssemblyService(prompt_service).build(
        session=object(),
        context=_build_context(include_source_messages=False),
        provider_capabilities={},
    )

    assert "system-character" not in result.combined_prompt
    assert "system-state" not in result.combined_prompt
    assert _GLOBAL_RULES_HEADING in result.combined_prompt
    assert "event-character" in result.combined_prompt
    assert result.combined_prompt.count(_CONTEXT_HEADINGS[0]) == 1


def test_build_uses_pull_sources_and_memory_context(monkeypatch):
    monkeypatch.setattr(
        "app.services.runtime.generation.prompt_assembly_service.build_runtime_prompt_variables",
        lambda context, provider_capabilities, include_wakeup_context=True: {"base": True},
    )
    calls = []
    prompt_service = SimpleNamespace(
        render=lambda **kwargs: calls.append(kwargs)
        or (
            {"template_type": kwargs["template_type"]},
            {"revision_id": kwargs["template_type"]},
            dict(kwargs["variables"]),
            f"{kwargs['template_type']} prompt",
        )
    )

    result = PromptAssemblyService(prompt_service).build(
        session=object(),
        context=_build_context(event_type="pull", target_type="cocoon"),
        provider_capabilities={"streaming": True},
    )

    assert calls[1]["template_type"] == "pull"
    assert calls[1]["variables"]["memory_context"] == [
        {"scope": "external", "summary": "s2", "content": "m2"}
    ]
    assert result.event.summary_prefix == "pull"
    assert result.messages == [{"role": "user", "content": "pulled"}]


def test_build_uses_merge_context_for_merge_rounds(monkeypatch):
    monkeypatch.setattr(
        "app.services.runtime.generation.prompt_assembly_service.build_runtime_prompt_variables",
        lambda context, provider_capabilities, include_wakeup_context=True: {"base": True},
    )
    calls = []
    prompt_service = SimpleNamespace(
        render=lambda **kwargs: calls.append(kwargs)
        or (
            {"template_type": kwargs["template_type"]},
            {"revision_id": kwargs["template_type"]},
            dict(kwargs["variables"]),
            f"{kwargs['template_type']} prompt",
        )
    )

    result = PromptAssemblyService(prompt_service).build(
        session=object(),
        context=_build_context(event_type="merge"),
        provider_capabilities={"streaming": True},
    )

    assert calls[1]["template_type"] == "merge"
    assert calls[1]["variables"]["merge_context"] == {"source": "cocoon-2"}
    assert result.event.summary_prefix == "merge"


def test_build_prefers_external_sender_display_name_for_group_speaker(monkeypatch):
    monkeypatch.setattr(
        "app.services.runtime.generation.prompt_assembly_service.build_runtime_prompt_variables",
        lambda context, provider_capabilities, include_wakeup_context=True: {
            "provider_capabilities": provider_capabilities
        },
    )
    prompt_service = SimpleNamespace(
        render=lambda **kwargs: (
            {"template_type": kwargs["template_type"]},
            {"revision_id": f"{kwargs['template_type']}-rev"},
            dict(kwargs["variables"]),
            f"{kwargs['template_type']} prompt",
        )
    )
    context = _build_context(include_source_messages=False)
    context.visible_messages = [
        SimpleNamespace(
            role="user",
            content="hello from im",
            is_retracted=False,
            sender_user_id=None,
            external_sender_id="member-qq",
            external_sender_display_name="Bob",
        ),
        SimpleNamespace(role="assistant", content="prior", is_retracted=False, sender_user_id=None),
    ]

    result = PromptAssemblyService(prompt_service).build(
        session=object(),
        context=context,
        provider_capabilities={"streaming": True},
    )

    assert result.messages[0] == {"role": "user", "content": "[speaker:Bob] hello from im"}
