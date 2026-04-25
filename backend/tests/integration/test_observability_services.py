import pytest
from app.models import ActionDispatch
from app.schemas.observability.artifacts import ArtifactCleanupResult
from app.schemas.observability.audits import AuditRunDetail, AuditRunOut
from app.schemas.observability.insights import InsightsDashboard

pytestmark = pytest.mark.integration


def test_audit_query_service_returns_typed_run_views(client, default_cocoon_id):
    container = client.app.state.container

    with container.session_factory() as session:
        action = ActionDispatch(cocoon_id=default_cocoon_id, event_type="chat", payload_json={})
        session.add(action)
        session.flush()
        run = container.audit_service.start_run(session, default_cocoon_id, None, action, "chat")
        step = container.audit_service.start_step(session, run, "generator")
        artifact = container.audit_service.record_json_artifact(
            session,
            run,
            step,
            "snapshot",
            {"ok": True},
        )
        container.audit_service.record_link(
            session,
            run,
            "produced_by",
            source_step_id=step.id,
            target_artifact_id=artifact.id,
        )
        session.commit()
        run_id = run.id

    with container.session_factory() as session:
        listing = container.audit_query_service.list_runs(session)
        detail = container.audit_query_service.get_run_detail(session, run_id)

        assert listing
        assert isinstance(listing[0], AuditRunOut)
        assert isinstance(detail, AuditRunDetail)
        assert detail.run.id == run_id
        assert detail.steps
        assert detail.artifacts
        assert detail.links


def test_artifact_admin_service_lists_and_cleans_artifacts(client, default_cocoon_id):
    container = client.app.state.container

    with container.session_factory() as session:
        run = container.audit_service.start_run(session, default_cocoon_id, None, None, "artifact-admin")
        artifact = container.audit_service.record_json_artifact(
            session,
            run,
            None,
            "cleanup",
            {"value": 1},
        )
        session.commit()
        artifact_id = artifact.id

    with container.session_factory() as session:
        listing = container.artifact_admin_service.list_artifacts(session)
        result = container.artifact_admin_service.cleanup_manual(session, [artifact_id])
        session.commit()

        assert listing
        assert isinstance(result, ArtifactCleanupResult)
        assert result.deleted == 1
        stored = session.get(type(artifact), artifact_id)
        assert stored is not None
        assert stored.deleted_at is not None


def test_insight_query_service_returns_dashboard(client, default_cocoon_id):
    container = client.app.state.container

    with container.session_factory() as session:
        session.add(ActionDispatch(cocoon_id=default_cocoon_id, event_type="chat", payload_json={}))
        session.commit()

    with container.session_factory() as session:
        dashboard = container.insight_query_service.dashboard(session)
        assert isinstance(dashboard, InsightsDashboard)
        assert dashboard.summary.total_runs >= 0
        assert dashboard.summary.total_messages >= 0
        assert isinstance(dashboard.token_usage.series, list)
        assert isinstance(dashboard.memory.growth, list)
        assert isinstance(dashboard.runtime.status_distribution, list)
