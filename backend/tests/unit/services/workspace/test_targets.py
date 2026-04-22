from app.models import SessionState
from app.services.workspace.targets import (
    build_target_filter,
    ensure_session_state,
    get_session_state,
    resolve_target_type,
    target_channel_key,
)


class _FakeSession:
    def __init__(self, scalar_result=None):
        self.scalar_result = scalar_result
        self.statements = []
        self.added = []
        self.flush_count = 0

    def scalar(self, statement):
        self.statements.append(statement)
        return self.scalar_result

    def add(self, value):
        self.added.append(value)

    def flush(self):
        self.flush_count += 1


def test_resolve_target_type_and_channel_key_support_both_target_kinds():
    assert resolve_target_type(cocoon_id="c1") == ("cocoon", "c1")
    assert resolve_target_type(chat_group_id="g1") == ("chat_group", "g1")
    assert target_channel_key(cocoon_id="c1") == "cocoon:c1"
    assert target_channel_key(chat_group_id="g1") == "chat_group:g1"


def test_resolve_target_type_requires_exactly_one_target():
    try:
        resolve_target_type()
    except ValueError as exc:
        assert "Exactly one" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing target")

    try:
        resolve_target_type(cocoon_id="c1", chat_group_id="g1")
    except ValueError as exc:
        assert "Exactly one" in str(exc)
    else:
        raise AssertionError("Expected ValueError for duplicate target")


def test_build_target_filter_uses_matching_columns():
    cocoon_filter = build_target_filter(SessionState, cocoon_id="c1")
    group_filter = build_target_filter(SessionState, chat_group_id="g1")

    assert "session_states.cocoon_id" in str(cocoon_filter)
    assert "session_states.chat_group_id IS NULL" in str(cocoon_filter)
    assert "session_states.chat_group_id" in str(group_filter)
    assert "session_states.cocoon_id IS NULL" in str(group_filter)


def test_get_session_state_queries_scalar_with_target_filter():
    existing = SessionState(cocoon_id="c1", persona_json={}, active_tags_json=[])
    session = _FakeSession(scalar_result=existing)

    result = get_session_state(session, cocoon_id="c1")

    assert result is existing
    assert len(session.statements) == 1
    assert "session_states.cocoon_id" in str(session.statements[0])


def test_ensure_session_state_returns_existing_state_without_mutation():
    existing = SessionState(chat_group_id="g1", persona_json={}, active_tags_json=["tag-1"])
    session = _FakeSession(scalar_result=existing)

    result = ensure_session_state(session, chat_group_id="g1")

    assert result is existing
    assert session.added == []
    assert session.flush_count == 0


def test_ensure_session_state_creates_and_flushes_missing_state():
    session = _FakeSession()

    result = ensure_session_state(session, cocoon_id="c-new")

    assert result.cocoon_id == "c-new"
    assert result.chat_group_id is None
    assert result.persona_json == {}
    assert result.active_tags_json == []
    assert session.added == [result]
    assert session.flush_count == 1
