from types import SimpleNamespace

from app.models import ActionDispatch
from app.services.runtime.round_preparation_service import RoundPreparationService


def test_prepare_cleans_up_edit_rounds_and_starts_audit_run():
    calls = []
    audit_service = SimpleNamespace(
        start_run=lambda **kwargs: calls.append(("audit", kwargs)) or "audit-run"
    )
    round_cleanup = SimpleNamespace(
        cleanup_for_edit=lambda *args, **kwargs: calls.append(("edit", args, kwargs)),
        cleanup_for_retry=lambda *args, **kwargs: calls.append(("retry", args, kwargs)),
    )
    action = ActionDispatch(
        id="action-1",
        cocoon_id="cocoon-1",
        event_type="edit",
        payload_json={"message_id": "msg-1"},
    )

    event, audit_run = RoundPreparationService(audit_service, round_cleanup).prepare(object(), action)

    assert calls[0][0] == "edit"
    assert calls[0][2]["edited_message_id"] == "msg-1"
    assert calls[1][0] == "audit"
    assert event.event_type == "edit"
    assert event.cocoon_id == "cocoon-1"
    assert event.payload == {"message_id": "msg-1"}
    assert audit_run == "audit-run"


def test_prepare_cleans_up_retry_rounds():
    calls = []
    audit_service = SimpleNamespace(
        start_run=lambda **kwargs: calls.append(("audit", kwargs)) or "audit-run"
    )
    round_cleanup = SimpleNamespace(
        cleanup_for_edit=lambda *args, **kwargs: calls.append(("edit", args, kwargs)),
        cleanup_for_retry=lambda *args, **kwargs: calls.append(("retry", args, kwargs)),
    )
    action = ActionDispatch(
        id="action-2",
        chat_group_id="group-1",
        event_type="retry",
        payload_json={"message_id": "msg-2"},
    )

    event, audit_run = RoundPreparationService(audit_service, round_cleanup).prepare(object(), action)

    assert calls[0][0] == "retry"
    assert calls[0][2]["message_id"] == "msg-2"
    assert event.chat_group_id == "group-1"
    assert audit_run == "audit-run"


def test_prepare_skips_cleanup_for_regular_chat_rounds():
    calls = []
    session = object()
    audit_service = SimpleNamespace(
        start_run=lambda **kwargs: calls.append(("audit", kwargs)) or "audit-run"
    )
    round_cleanup = SimpleNamespace(
        cleanup_for_edit=lambda *args, **kwargs: calls.append(("edit", args, kwargs)),
        cleanup_for_retry=lambda *args, **kwargs: calls.append(("retry", args, kwargs)),
    )
    action = ActionDispatch(
        id="action-3",
        cocoon_id="cocoon-2",
        event_type="chat",
        payload_json={"text": "hi"},
    )

    event, audit_run = RoundPreparationService(audit_service, round_cleanup).prepare(session, action)

    assert calls == [("audit", calls[0][1])]
    assert calls[0][1]["session"] is session
    assert calls[0][1]["cocoon_id"] == "cocoon-2"
    assert calls[0][1]["chat_group_id"] is None
    assert calls[0][1]["action"] is action
    assert calls[0][1]["operation_type"] == "chat"
    assert event.action_id == "action-3"
    assert audit_run == "audit-run"
