from __future__ import annotations

from types import SimpleNamespace

from app.services.runtime.orchestration.chat_runtime import ChatRuntime
from app.services.runtime.types import MemoryCandidate, MetaDecision, TagReference


def _meta(*, decision: str = "continue", candidates: list[MemoryCandidate] | None = None) -> MetaDecision:
    return MetaDecision(
        decision=decision,
        relation_delta=0,
        persona_patch={},
        tag_ops=[],
        internal_thought="",
        memory_candidates=candidates or [],
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
        persist_memory_candidates=lambda *args, **kwargs: (
            calls.append(("persist_memory_candidates", args[3], kwargs.get("source_message")))
            or [SimpleNamespace(id="memory-1"), SimpleNamespace(id="memory-2")]
        ),
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
            "memories": [],
        }
    ]


def test_chat_runtime_memory_node_persists_candidates_and_records_artifact():
    runtime, calls = _runtime()
    state = {
        "session": "session",
        "action": SimpleNamespace(id="action-1"),
        "audit_run": SimpleNamespace(id="audit-1"),
        "context": SimpleNamespace(),
        "meta": _meta(
            candidates=[
                MemoryCandidate(
                    scope="session",
                    summary="short summary",
                    content="long content",
                    tags=[TagReference(tag="focus")],
                )
            ]
        ),
        "message": SimpleNamespace(id="message-1"),
    }

    result = runtime._run_memory_node(state)

    assert [memory.id for memory in result["memories"]] == ["memory-1", "memory-2"]
    assert ("persist_memory_candidates", state["meta"].memory_candidates, state["message"]) in calls
    assert any(call[0] == "artifact" and call[1] == "memory_persistence" for call in calls)
    artifact_call = next(call for call in calls if call[0] == "artifact" and call[1] == "memory_persistence")
    assert artifact_call[2] == {
        "memory_chunk_ids": ["memory-1", "memory-2"],
        "candidate_count": 1,
        "persisted_count": 2,
    }


def test_chat_runtime_routes_silence_and_memory_candidates():
    runtime, _calls = _runtime()
    valid_candidates = [MemoryCandidate(scope="session", summary="kept", content="saved")]
    blank_candidates = [MemoryCandidate(scope="session", summary="   ", content="saved")]

    assert runtime._route_after_scheduler({"meta": _meta(decision="continue", candidates=valid_candidates)}) == "generator_node"
    assert runtime._route_after_scheduler({"meta": _meta(decision="silence", candidates=valid_candidates)}) == "memory_node"
    assert runtime._route_after_scheduler({"meta": _meta(decision="silence", candidates=blank_candidates)}) == "side_effects"
    assert runtime._route_after_generator({"meta": _meta(candidates=valid_candidates)}) == "memory_node"
    assert runtime._route_after_generator({"meta": _meta(candidates=blank_candidates)}) == "side_effects"
    assert runtime._has_memory_candidates(valid_candidates) is True
    assert runtime._has_memory_candidates(blank_candidates) is False


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
        "memories": [SimpleNamespace(id="memory-1")],
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
