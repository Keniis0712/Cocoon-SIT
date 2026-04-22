from types import SimpleNamespace

from app.services.runtime.types import ContextPackage, RuntimeEvent


def test_runtime_event_properties_prefer_chat_group_target():
    event = RuntimeEvent(
        event_type="chat",
        cocoon_id="cocoon-1",
        chat_group_id="group-1",
        action_id="action-1",
        payload={},
    )

    assert event.target_type == "chat_group"
    assert event.target_id == "group-1"
    assert event.channel_key == "chat_group:group-1"


def test_context_package_properties_proxy_runtime_event_and_conversation():
    conversation = SimpleNamespace(name="demo")
    runtime_event = RuntimeEvent(
        event_type="chat",
        cocoon_id="cocoon-1",
        chat_group_id=None,
        action_id="action-1",
        payload={},
    )
    context = ContextPackage(
        runtime_event=runtime_event,
        conversation=conversation,
        character=SimpleNamespace(),
        session_state=SimpleNamespace(),
        visible_messages=[],
        memory_context=[],
    )

    assert context.cocoon is conversation
    assert context.target_type == "cocoon"
    assert context.target_id == "cocoon-1"
    assert context.channel_key == "cocoon:cocoon-1"
