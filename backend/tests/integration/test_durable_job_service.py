import pytest
from app.models.entities import DurableJobStatus

pytestmark = pytest.mark.integration


def test_durable_job_can_be_claimed_once(client):
    container = client.app.state.container
    with container.session_factory() as session:
        job = container.durable_jobs.enqueue(
            session,
            job_type="merge",
            lock_key="cocoon:test:merge",
            payload_json={"example": True},
            cocoon_id=None,
        )
        session.commit()
        job_id = job.id

    with container.session_factory() as session:
        claimed = container.durable_jobs.claim_next(session, "worker-a")
        assert claimed is not None
        assert claimed.id == job_id
        assert claimed.status == DurableJobStatus.running
        session.commit()

    with container.session_factory() as session:
        second = container.durable_jobs.claim_next(session, "worker-b")
        assert second is None
        session.commit()
