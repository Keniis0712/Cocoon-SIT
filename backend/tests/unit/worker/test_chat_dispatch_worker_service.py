from datetime import UTC, datetime, timedelta
import time
from types import SimpleNamespace

from app.models import ActionDispatch, FailedRound
from app.models.entities import ActionStatus
from app.worker.chat_dispatch_worker_service import ChatDispatchWorkerService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def _realtime_hub():
    return SimpleNamespace(publish=lambda *args, **kwargs: None)


class _Queue:
    def __init__(self, envelope=None):
        self.envelope = envelope
        self.acked = []

    def consume_next(self):
        envelope = self.envelope
        self.envelope = None
        return envelope

    def ack(self, envelope):
        self.acked.append(envelope)


def test_chat_dispatch_worker_service_handles_empty_and_missing_actions():
    session_factory = _session_factory()
    empty_queue = _Queue(envelope=None)
    worker = ChatDispatchWorkerService(
        session_factory=session_factory,
        chat_queue=empty_queue,
        chat_runtime=SimpleNamespace(run=lambda **kwargs: None),
        realtime_hub=_realtime_hub(),
    )

    assert worker.process_next() is False

    missing_envelope = SimpleNamespace(action_id="missing")
    missing_queue = _Queue(envelope=missing_envelope)
    worker = ChatDispatchWorkerService(
        session_factory=session_factory,
        chat_queue=missing_queue,
        chat_runtime=SimpleNamespace(run=lambda **kwargs: None),
        realtime_hub=_realtime_hub(),
    )

    assert worker.process_next() is False
    assert missing_queue.acked == [missing_envelope]


def test_chat_dispatch_worker_service_processes_success_and_failure_paths():
    session_factory = _session_factory()

    with session_factory() as session:
        success_action = ActionDispatch(cocoon_id="c1", event_type="chat", payload_json={})
        failed_action = ActionDispatch(cocoon_id="c1", event_type="chat", payload_json={})
        session.add_all([success_action, failed_action])
        session.commit()
        success_action_id = success_action.id
        failed_action_id = failed_action.id

    success_envelope = SimpleNamespace(action_id=success_action_id)
    success_queue = _Queue(envelope=success_envelope)

    def _run_success(session, action):
        action.status = ActionStatus.completed

    success_worker = ChatDispatchWorkerService(
        session_factory=session_factory,
        chat_queue=success_queue,
        chat_runtime=SimpleNamespace(run=_run_success),
        realtime_hub=_realtime_hub(),
    )

    assert success_worker.process_next() is True
    assert success_queue.acked == [success_envelope]
    with session_factory() as session:
        persisted = session.get(ActionDispatch, success_action_id)
        assert persisted is not None
        assert persisted.status == ActionStatus.completed

    failed_envelope = SimpleNamespace(action_id=failed_action_id)
    failed_queue = _Queue(envelope=failed_envelope)
    failed_worker = ChatDispatchWorkerService(
        session_factory=session_factory,
        chat_queue=failed_queue,
        chat_runtime=SimpleNamespace(run=lambda **kwargs: (_ for _ in ()).throw(ValueError("runtime boom"))),
        realtime_hub=_realtime_hub(),
    )

    assert failed_worker.process_next() is True
    assert failed_queue.acked == [failed_envelope]
    with session_factory() as session:
        persisted = session.get(ActionDispatch, failed_action_id)
        failed_round = session.query(FailedRound).filter(FailedRound.action_id == failed_action_id).one()
        assert persisted is not None
        assert persisted.status == ActionStatus.failed
        assert persisted.error_text == "runtime boom"
        assert failed_round.reason == "runtime boom"


def test_chat_dispatch_worker_service_acks_when_action_disappears_after_runtime_failure():
    session_factory = _session_factory()

    with session_factory() as session:
        action = ActionDispatch(cocoon_id="c1", event_type="chat", payload_json={})
        session.add(action)
        session.commit()
        action_id = action.id

    envelope = SimpleNamespace(action_id=action_id)
    queue = _Queue(envelope=envelope)

    def _run_missing(session, action):
        session.delete(action)
        session.commit()
        raise ValueError("runtime boom")

    worker = ChatDispatchWorkerService(
        session_factory=session_factory,
        chat_queue=queue,
        chat_runtime=SimpleNamespace(run=_run_missing),
        realtime_hub=_realtime_hub(),
    )

    assert worker.process_next() is True
    assert queue.acked == [envelope]


def test_chat_dispatch_worker_service_waits_for_debounce_window_before_running():
    session_factory = _session_factory()

    with session_factory() as session:
        action = ActionDispatch(
            cocoon_id="c1",
            event_type="chat",
            payload_json={},
            debounce_until=datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=30),
        )
        session.add(action)
        session.commit()
        action_id = action.id

    envelope = SimpleNamespace(action_id=action_id)
    queue = _Queue(envelope=envelope)
    calls: list[str] = []

    worker = ChatDispatchWorkerService(
        session_factory=session_factory,
        chat_queue=queue,
        chat_runtime=SimpleNamespace(run=lambda session, action: calls.append(action.id)),
        realtime_hub=_realtime_hub(),
    )

    assert worker.process_next() is False
    assert queue.acked == [envelope]
    assert calls == []

    with session_factory() as session:
        action = session.get(ActionDispatch, action_id)
        assert action is not None
        action.debounce_until = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
        session.commit()

    assert worker.process_next() is True
    assert calls == [action_id]


def test_chat_dispatch_worker_service_times_out_and_enqueues_retry():
    session_factory = _session_factory()

    with session_factory() as session:
        action = ActionDispatch(
            cocoon_id="c1",
            event_type="chat",
            payload_json={"chat_retry_attempt": 1},
            debounce_until=datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1),
        )
        session.add(action)
        session.commit()
        action_id = action.id

    envelope = SimpleNamespace(action_id=action_id)
    queue = _Queue(envelope=envelope)
    queue.enqueue = lambda *args, **kwargs: 1  # type: ignore[attr-defined]

    worker = ChatDispatchWorkerService(
        session_factory=session_factory,
        chat_queue=queue,
        chat_runtime=SimpleNamespace(run=lambda session, action: time.sleep(0.05)),
        realtime_hub=_realtime_hub(),
        chat_action_timeout_seconds=0.01,
        chat_action_max_timeout_attempts=3,
    )

    assert worker.process_next() is True
    assert queue.acked == [envelope]

    with session_factory() as session:
        original = session.get(ActionDispatch, action_id)
        retries = list(
            session.query(ActionDispatch)
            .filter(ActionDispatch.cocoon_id == "c1", ActionDispatch.id != action_id)
            .all()
        )
        failed_round = session.query(FailedRound).filter(FailedRound.action_id == action_id).one()
        assert original is not None
        assert original.status == ActionStatus.failed
        assert "timed out" in str(original.error_text)
        assert failed_round.reason == "timeout"
        assert len(retries) == 1
        assert retries[0].status == ActionStatus.queued
        assert retries[0].payload_json["chat_retry_attempt"] == 2


def test_chat_dispatch_worker_service_blocks_later_chat_when_same_target_is_running():
    session_factory = _session_factory()

    with session_factory() as session:
        running = ActionDispatch(
            cocoon_id="c1",
            event_type="chat",
            status=ActionStatus.running,
            payload_json={"chat_retry_attempt": 1},
            started_at=datetime.now(UTC).replace(tzinfo=None),
        )
        queued = ActionDispatch(
            cocoon_id="c1",
            event_type="chat",
            payload_json={"chat_retry_attempt": 1},
            debounce_until=datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1),
        )
        session.add_all([running, queued])
        session.commit()
        queued_id = queued.id

    envelope = SimpleNamespace(action_id=queued_id)
    queue = _Queue(envelope=envelope)
    worker = ChatDispatchWorkerService(
        session_factory=session_factory,
        chat_queue=queue,
        chat_runtime=SimpleNamespace(run=lambda **kwargs: None),
        realtime_hub=_realtime_hub(),
    )

    assert worker.process_next() is False
    assert queue.acked == [envelope]
