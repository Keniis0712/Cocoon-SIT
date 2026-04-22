from types import SimpleNamespace

from app.services.audit.service import AuditService


def test_audit_service_delegates_to_component_services():
    calls = []
    run_service = SimpleNamespace(
        start_run=lambda *args: calls.append(("start_run", args[1:])) or "run",
        finish_run=lambda *args: calls.append(("finish_run", args[1:])) or "finished-run",
        start_step=lambda *args: calls.append(("start_step", args[1:])) or "step",
        finish_step=lambda *args: calls.append(("finish_step", args[1:])) or "finished-step",
    )
    artifact_service = SimpleNamespace(
        record_json_artifact=lambda *args: calls.append(("record_json_artifact", args[1:])) or "artifact"
    )
    link_service = SimpleNamespace(
        record_link=lambda *args, **kwargs: calls.append(("record_link", args[1:], kwargs)) or "link"
    )
    cleanup_service = SimpleNamespace(
        cleanup_expired_artifacts=lambda session: calls.append(("cleanup", session)) or 3
    )
    audit_service = AuditService(
        artifact_store=object(),
        settings=object(),
        run_service=run_service,
        artifact_service=artifact_service,
        link_service=link_service,
        cleanup_service=cleanup_service,
    )

    assert audit_service.start_run("session", "cocoon-1", None, "action", "chat") == "run"
    assert audit_service.finish_run("session", "run", "completed") == "finished-run"
    assert audit_service.start_step("session", "run", "step", {"x": 1}) == "step"
    assert audit_service.finish_step("session", "step", "completed") == "finished-step"
    assert (
        audit_service.record_json_artifact("session", "run", "step", "kind", {"payload": True}, "summary", {"x": 1})
        == "artifact"
    )
    assert (
        audit_service.record_link(
            "session",
            "run",
            "produced_by",
            source_artifact_id="a1",
            source_step_id="s1",
            target_artifact_id="a2",
            target_step_id="s2",
        )
        == "link"
    )
    assert audit_service.cleanup_expired_artifacts("session") == 3
    assert calls[-1] == ("cleanup", "session")
