import pytest

from app.models.entities import ActionStatus
from app.worker.jobs.runtime_action_service import RuntimeActionService


class _FakeSession:
    def __init__(self):
        self.added = []
        self.flush_count = 0

    def add(self, value):
        self.added.append(value)

    def flush(self):
        self.flush_count += 1


def test_create_runtime_action_accepts_keyword_targets():
    session = _FakeSession()

    action = RuntimeActionService().create_runtime_action(
        session,
        event_type="wakeup",
        payload_json={"reason": "idle"},
        cocoon_id="cocoon-1",
    )

    assert action.cocoon_id == "cocoon-1"
    assert action.chat_group_id is None
    assert action.event_type == "wakeup"
    assert action.status == ActionStatus.running
    assert action.payload_json == {"reason": "idle"}
    assert action.started_at.tzinfo is None
    assert session.added == [action]
    assert session.flush_count == 1


def test_create_runtime_action_supports_legacy_positional_signatures():
    session = _FakeSession()
    service = RuntimeActionService()

    action_without_target = service.create_runtime_action(session, "pull", {"source": "c2"})
    action_with_target = service.create_runtime_action(session, "cocoon-2", "merge", {"source": "c3"})

    assert action_without_target.event_type == "pull"
    assert action_without_target.payload_json == {"source": "c2"}
    assert action_with_target.cocoon_id == "cocoon-2"
    assert action_with_target.event_type == "merge"
    assert action_with_target.payload_json == {"source": "c3"}


def test_create_runtime_action_rejects_invalid_argument_shapes():
    service = RuntimeActionService()

    with pytest.raises(TypeError):
        service.create_runtime_action(_FakeSession(), "one", "two", "three", "four")

    with pytest.raises(TypeError):
        service.create_runtime_action(_FakeSession(), cocoon_id="c1")
