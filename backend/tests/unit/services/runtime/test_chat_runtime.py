from __future__ import annotations

from types import SimpleNamespace

from app.services.runtime.orchestration.chat_runtime import ChatRuntime
from app.services.runtime.types import MetaDecision, TagOperation


def _meta(*, decision: str = "reply") -> MetaDecision:
    return MetaDecision(
        decision=decision,
        relation_delta=0,
        persona_patch={},
        tag_ops=[TagOperation(action="add", tag_index=1)],
        internal_thought="",
    )


def _runtime():
    calls: list[tuple] = []

    def start_step(session, audit_run, name):
        step = SimpleNamespace(id=f"{name}-step")
        calls.append(("start_step", name, step.id))
        return step

    audit_service = SimpleNamespace(
        start_step=start_step,
        record_json_artifact=lambda *args, **kwargs: calls.append(("artifact", args[3], args[4], kwargs)),
        finish_step=lambda session, step, status: calls.append(("finish_step", step.id, status)),
    )
    side_effects = SimpleNamespace(
        record_side_effects_result=lambda *args, **kwargs: calls.append(("record_side_effects_result", kwargs)),
        finish_action=lambda session, action, audit_run, status: calls.append(("finish_action", action.id, status)),
    )
    state_patch_service = SimpleNamespace(
        apply_and_publish=lambda *args, **kwargs: calls.append(("apply_and_publish", kwargs["action_id"])),
        publish_snapshot=lambda **kwargs: calls.append(("publish_snapshot", kwargs)),
    )
    runtime = ChatRuntime(
        context_builder=SimpleNamespace(build=lambda session, event: SimpleNamespace(memory_hits=[])),
        meta_node=SimpleNamespace(evaluate=lambda *args, **kwargs: _meta()),
        generator_node=SimpleNamespace(generate=lambda *args, **kwargs: SimpleNamespace(reply_text="hi")),
        scheduler_node=SimpleNamespace(schedule=lambda *args, **kwargs: {"scheduled": True}),
        round_preparation_service=SimpleNamespace(
            prepare=lambda session, action: (
                SimpleNamespace(action_id=action.id, cocoon_id="cocoon-1", chat_group_id=None),
                SimpleNamespace(id="audit-1"),
            )
        ),
        state_patch_service=state_patch_service,
        reply_delivery_service=SimpleNamespace(
            deliver=lambda *args, **kwargs: calls.append(("deliver", args[2].id)) or SimpleNamespace(id="message-1")
        ),
        side_effects=side_effects,
        audit_service=audit_service,
    )
    return runtime, calls


def test_chat_runtime_run_invokes_graph_with_prepared_state():
    runtime, _calls = _runtime()
    invoked = []
    runtime.graph = SimpleNamespace(invoke=lambda payload: invoked.append(payload))
    action = SimpleNamespace(id="action-1")

    runtime.run("session", action)

    assert invoked == [
        {
            "session": "session",
            "action": action,
            "event": SimpleNamespace(action_id="action-1", cocoon_id="cocoon-1", chat_group_id=None),
            "audit_run": SimpleNamespace(id="audit-1"),
            "message": None,
        }
    ]


def test_chat_runtime_routes_directly_to_side_effects_when_silent():
    runtime, _calls = _runtime()

    assert runtime._route_after_scheduler({"meta": _meta(decision="reply"), "action": SimpleNamespace(id="a1")}) == "generator_node"
    assert runtime._route_after_scheduler({"meta": _meta(decision="silence"), "action": SimpleNamespace(id="a1")}) == "side_effects"
    assert runtime._route_after_generator({"meta": _meta()}) == "side_effects"


def test_chat_runtime_side_effects_node_records_result_and_finishes_action():
    runtime, calls = _runtime()
    state = {
        "session": "session",
        "action": SimpleNamespace(id="action-1"),
        "audit_run": SimpleNamespace(id="audit-1"),
        "context": SimpleNamespace(
            session_state=SimpleNamespace(id="state-1"),
            runtime_event=SimpleNamespace(cocoon_id="cocoon-1", chat_group_id=None),
        ),
        "message": SimpleNamespace(id="message-1"),
        "scheduler_result": {"scheduled": True},
    }

    result = runtime._run_side_effects_node(state)

    assert result == {}
    assert any(call[0] == "record_side_effects_result" for call in calls)
    snapshot_call = next(call for call in calls if call[0] == "publish_snapshot")
    assert snapshot_call[1] == {
        "action_id": "action-1",
        "state": state["context"].session_state,
        "cocoon_id": "cocoon-1",
        "chat_group_id": None,
    }
    assert ("finish_action", "action-1", "completed") in calls
