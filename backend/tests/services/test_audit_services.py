from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from app.models import ActionDispatch, AuditArtifact, AuditLink, AuditRun, AuditStep
from app.models.entities import ActionStatus


def test_audit_run_service_creates_and_finishes_run_and_step(client, default_cocoon_id):
    container = client.app.state.container

    with container.session_factory() as session:
        action = ActionDispatch(cocoon_id=default_cocoon_id, event_type="chat", payload_json={})
        session.add(action)
        session.flush()

        run = container.audit_service.run_service.start_run(session, default_cocoon_id, action, "chat")
        step = container.audit_service.run_service.start_step(session, run, "context_builder")
        container.audit_service.run_service.finish_step(session, step, ActionStatus.completed)
        container.audit_service.run_service.finish_run(session, run, ActionStatus.completed)
        session.commit()

        persisted_run = session.get(AuditRun, run.id)
        persisted_step = session.get(AuditStep, step.id)
        assert persisted_run is not None
        assert persisted_run.status == ActionStatus.completed
        assert persisted_step is not None
        assert persisted_step.status == ActionStatus.completed


def test_audit_artifact_and_link_services_record_metadata(client, default_cocoon_id):
    container = client.app.state.container

    with container.session_factory() as session:
        run = container.audit_service.start_run(session, default_cocoon_id, None, "artifact-test")
        step = container.audit_service.start_step(session, run, "generator")
        artifact = container.audit_service.artifact_service.record_json_artifact(
            session,
            run,
            step,
            "snapshot",
            {"value": 1},
            summary="artifact summary",
        )
        link = container.audit_service.link_service.record_link(
            session,
            run,
            "produced_by",
            source_step_id=step.id,
            target_artifact_id=artifact.id,
        )
        session.commit()

        stored_artifact = session.get(AuditArtifact, artifact.id)
        stored_link = session.get(AuditLink, link.id)
        assert stored_artifact is not None
        assert stored_artifact.summary == "artifact summary"
        assert stored_artifact.storage_path is not None
        assert Path(stored_artifact.storage_path).exists()
        assert stored_link is not None
        assert stored_link.relation == "produced_by"


def test_audit_cleanup_service_deletes_expired_artifacts(client, default_cocoon_id):
    container = client.app.state.container

    with container.session_factory() as session:
        run = container.audit_service.start_run(session, default_cocoon_id, None, "cleanup-test")
        artifact = container.audit_service.record_json_artifact(
            session,
            run,
            None,
            "cleanup",
            {"expired": True},
        )
        artifact.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
        storage_path = artifact.storage_path
        session.commit()

    assert storage_path is not None
    assert Path(storage_path).exists()

    with container.session_factory() as session:
        cleaned = container.audit_service.cleanup_service.cleanup_expired_artifacts(session)
        session.commit()
        assert cleaned == 1
        artifact = session.scalars(select(AuditArtifact).where(AuditArtifact.storage_path == storage_path)).first()
        assert artifact is not None
        assert artifact.deleted_at is not None
