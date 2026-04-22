from types import SimpleNamespace

from app.services.runtime.side_effects import SideEffects
from app.services.runtime.types import MetaDecision


class _FakeSession:
    def __init__(self):
        self.flush_count = 0

    def flush(self):
        self.flush_count += 1


def _meta(relation_delta: int) -> MetaDecision:
    return MetaDecision(
        decision="reply",
        relation_delta=relation_delta,
        persona_patch={},
        tag_ops=[],
        internal_thought="test",
    )


def test_apply_state_patch_clamps_relation_score_to_configured_range():
    service = SideEffects(audit_service=SimpleNamespace(), memory_service=SimpleNamespace())
    session = _FakeSession()
    context = SimpleNamespace(
        session_state=SimpleNamespace(relation_score=99, persona_json={}, active_tags_json=[]),
        runtime_event=SimpleNamespace(event_type="chat"),
        external_context={},
    )

    updated = service.apply_state_patch(session, context, _meta(10))

    assert updated.relation_score == 100
    assert session.flush_count == 1

    updated = service.apply_state_patch(session, context, _meta(-500))

    assert updated.relation_score == 0


def test_apply_state_patch_uses_default_relation_score_when_state_is_missing():
    service = SideEffects(audit_service=SimpleNamespace(), memory_service=SimpleNamespace())
    session = _FakeSession()
    context = SimpleNamespace(
        session_state=SimpleNamespace(relation_score=None, persona_json={}, active_tags_json=[]),
        runtime_event=SimpleNamespace(event_type="chat"),
        external_context={},
    )

    updated = service.apply_state_patch(session, context, _meta(5))

    assert updated.relation_score == 55
