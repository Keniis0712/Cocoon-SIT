import pytest
from fastapi import HTTPException

from app.services.workspace.cocoon_tag_service import CocoonTagService


class _FakeSession:
    def __init__(self, binding=None):
        self.binding = binding
        self.added = []
        self.deleted = []
        self.flush_count = 0

    def scalar(self, statement):
        return self.binding

    def add(self, value):
        self.added.append(value)

    def delete(self, value):
        self.deleted.append(value)

    def flush(self):
        self.flush_count += 1


def test_bind_tag_returns_existing_or_updates_session_state(monkeypatch):
    existing = object()
    session = _FakeSession(binding=existing)
    monkeypatch.setattr("app.services.workspace.cocoon_tag_service.get_session_state", lambda *args, **kwargs: None)

    assert CocoonTagService().bind_tag(session, "c1", "focus") is existing

    state = type("_State", (), {"active_tags_json": []})()
    session = _FakeSession()
    monkeypatch.setattr("app.services.workspace.cocoon_tag_service.get_session_state", lambda *args, **kwargs: state)

    binding = CocoonTagService().bind_tag(session, "c1", "focus")

    assert binding.cocoon_id == "c1"
    assert binding.tag_id == "focus"
    assert state.active_tags_json == ["focus"]
    assert session.added == [binding]


def test_unbind_tag_updates_state_and_raises_when_missing(monkeypatch):
    state = type("_State", (), {"active_tags_json": ["focus", "other"]})()
    binding = type("_Binding", (), {"cocoon_id": "c1", "tag_id": "focus"})()
    session = _FakeSession(binding=binding)
    monkeypatch.setattr("app.services.workspace.cocoon_tag_service.get_session_state", lambda *args, **kwargs: state)

    removed = CocoonTagService().unbind_tag(session, "c1", "focus")

    assert removed is binding
    assert state.active_tags_json == ["other"]
    assert session.deleted == [binding]

    with pytest.raises(HTTPException) as exc:
        CocoonTagService().unbind_tag(_FakeSession(binding=None), "c1", "focus")
    assert exc.value.status_code == 404
