from types import SimpleNamespace

from app.services.runtime.reply_delivery_service import ReplyDeliveryService
from app.services.runtime.types import ContextPackage, GenerationOutput, RuntimeEvent


def test_deliver_streams_reply_persists_message_and_records_artifacts():
    publish_calls = []
    audit_artifact_calls = []
    link_calls = []
    persisted_calls = []
    message = SimpleNamespace(id="message-1")
    context = ContextPackage(
        runtime_event=RuntimeEvent(
            event_type="chat",
            cocoon_id="cocoon-1",
            chat_group_id=None,
            action_id="action-1",
            payload={},
        ),
        conversation=SimpleNamespace(),
        character=SimpleNamespace(),
        session_state=SimpleNamespace(active_tags_json=[]),
        visible_messages=[],
        memory_context=[],
    )
    generation = GenerationOutput(
        rendered_prompt="prompt",
        chunks=["hello", " world"],
        reply_text="hello world",
        raw_response={"raw": True},
        structured_output={"reply_text": "hello world"},
        usage={"prompt_tokens": 3, "completion_tokens": 2},
        provider_kind="mock",
        model_name="gpt-test",
    )
    service = ReplyDeliveryService(
        side_effects=SimpleNamespace(
            persist_generated_message=lambda session, ctx, action, payload: (
                persisted_calls.append((session, ctx, action, payload)) or message
            )
        ),
        audit_service=SimpleNamespace(
            record_json_artifact=lambda *args, **kwargs: (
                audit_artifact_calls.append((args, kwargs)) or SimpleNamespace(id="artifact-1")
            ),
            record_link=lambda *args, **kwargs: link_calls.append((args, kwargs)),
        ),
        realtime_hub=SimpleNamespace(publish=lambda channel_key, payload: publish_calls.append((channel_key, payload))),
        plugin_im_delivery_service=SimpleNamespace(enqueue_reply=lambda *args, **kwargs: None),
    )
    action = SimpleNamespace(id="action-1")
    audit_run = SimpleNamespace(id="audit-1")
    generator_step = SimpleNamespace(id="step-1")

    result = service.deliver(
        session="session",
        context=context,
        action=action,
        audit_run=audit_run,
        generator_step=generator_step,
        generation=generation,
    )

    assert result is message
    assert [item[1]["type"] for item in publish_calls] == ["reply_started", "reply_chunk", "reply_chunk", "reply_done"]
    assert publish_calls[0][0] == "cocoon:cocoon-1"
    assert publish_calls[1][1]["text"] == "hello"
    assert publish_calls[2][1]["chat_group_id"] is None
    assert publish_calls[3][1]["final_message_id"] == "message-1"
    assert persisted_calls == [("session", context, action, generation)]
    assert audit_artifact_calls[0][0][3] == "generator_output"
    assert audit_artifact_calls[0][0][4]["structured_output"] == {"reply_text": "hello world"}
    assert audit_artifact_calls[0][1]["metadata_json"] == {
        "provider_kind": "mock",
        "model_name": "gpt-test",
        "prompt_tokens": 3,
        "completion_tokens": 2,
    }
    assert link_calls[0][0][2] == "produced_by"
    assert link_calls[0][1]["target_artifact_id"] == "artifact-1"
