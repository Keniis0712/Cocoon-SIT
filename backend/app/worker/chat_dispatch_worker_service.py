from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import ActionDispatch, AuditRun, FailedRound
from app.models.entities import ActionStatus
from app.services.jobs.chat_dispatch import ChatDispatchQueue
from app.services.realtime.hub import RealtimeHub
from app.services.runtime.errors import RuntimeActionAbortedError
from app.services.runtime.orchestration.chat_runtime import ChatRuntime
from app.services.workspace.message_dispatch_base import MessageDispatchBase


class ChatDispatchWorkerService(MessageDispatchBase):
    """Consumes chat dispatches and runs them through the runtime."""

    CHAT_ACTION_TIMEOUT_SECONDS = 30
    CHAT_ACTION_MAX_TIMEOUT_ATTEMPTS = 3

    logger = logging.getLogger(__name__)

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        chat_queue: ChatDispatchQueue,
        chat_runtime: ChatRuntime,
        realtime_hub: RealtimeHub,
        chat_action_timeout_seconds: int | None = None,
        chat_action_max_timeout_attempts: int | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.chat_queue = chat_queue
        self.chat_runtime = chat_runtime
        self.realtime_hub = realtime_hub
        self.chat_action_timeout_seconds = (
            chat_action_timeout_seconds or self.CHAT_ACTION_TIMEOUT_SECONDS
        )
        self.chat_action_max_timeout_attempts = (
            chat_action_max_timeout_attempts or self.CHAT_ACTION_MAX_TIMEOUT_ATTEMPTS
        )
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="chat-dispatch")

    def process_next(self) -> bool:
        envelope = self.chat_queue.consume_next()
        if envelope:
            self.logger.info(
                "Worker consumed chat dispatch envelope action_id=%s event_type=%s cocoon_id=%s chat_group_id=%s",
                envelope.action_id,
                getattr(envelope, "event_type", None),
                getattr(envelope, "cocoon_id", None),
                getattr(envelope, "chat_group_id", None),
            )
        with self.session_factory() as session:
            if envelope and not session.get(ActionDispatch, envelope.action_id):
                self.logger.warning(
                    "Worker could not find ActionDispatch action_id=%s; acknowledging envelope",
                    envelope.action_id,
                )
            action = self._claim_next_ready_action(session)
            if not action:
                session.commit()
                if envelope:
                    self.chat_queue.ack(envelope)
                return False
            self.logger.info(
                "Worker starting runtime action_id=%s event_type=%s status=%s payload_keys=%s",
                action.id,
                action.event_type,
                action.status,
                sorted((action.payload_json or {}).keys()),
            )
            action_id = action.id
            session.commit()
        future = self._executor.submit(self._run_action_session, action_id)
        try:
            future.result(timeout=self.chat_action_timeout_seconds)
        except FutureTimeoutError:
            self._handle_timed_out_action(action_id)
        if envelope:
            self.chat_queue.ack(envelope)
        return True

    def _run_action_session(self, action_id: str) -> dict[str, str] | None:
        with self.session_factory() as session:
            action = session.get(ActionDispatch, action_id)
            if not action or action.status != ActionStatus.running:
                session.commit()
                return {"status": "aborted", "action_id": action_id}
            try:
                self.chat_runtime.run(session=session, action=action)
            except RuntimeActionAbortedError:
                session.rollback()
                session.commit()
                return {"status": "aborted", "action_id": action_id}
            except Exception as exc:  # noqa: BLE001
                self.logger.exception(
                    "Worker runtime failed action_id=%s event_type=%s cocoon_id=%s chat_group_id=%s",
                    action.id,
                    action.event_type,
                    action.cocoon_id,
                    action.chat_group_id,
                )
                session.rollback()
                action = session.get(ActionDispatch, action_id)
                if not action:
                    session.commit()
                    return {"status": "missing", "action_id": action_id}
                action.status = ActionStatus.failed
                action.error_text = str(exc)
                session.add(
                    FailedRound(
                        cocoon_id=action.cocoon_id,
                        chat_group_id=action.chat_group_id,
                        action_id=action.id,
                        event_type=action.event_type,
                        reason=str(exc),
                    )
                )
                self._finish_latest_audit_run(session, action.id, ActionStatus.failed)
                session.commit()
                return {"status": "failed", "action_id": action_id}
            self.logger.info(
                "Worker runtime completed action_id=%s event_type=%s",
                action.id,
                action.event_type,
            )
            session.commit()
            return {"status": "completed", "action_id": action_id}

    def _handle_timed_out_action(self, action_id: str) -> None:
        with self.session_factory() as session:
            action = session.get(ActionDispatch, action_id)
            if not action or action.status != ActionStatus.running:
                session.commit()
                return
            attempt = int((action.payload_json or {}).get("chat_retry_attempt") or 1)
            error_text = (
                f"timed out after {self.chat_action_timeout_seconds} seconds "
                f"(attempt {attempt}/{self.chat_action_max_timeout_attempts})"
            )
            action.status = ActionStatus.failed
            action.error_text = error_text
            action.finished_at = datetime.now(UTC).replace(tzinfo=None)
            session.add(
                FailedRound(
                    cocoon_id=action.cocoon_id,
                    chat_group_id=action.chat_group_id,
                    action_id=action.id,
                    event_type=action.event_type,
                    reason="timeout",
                )
            )
            self._finish_latest_audit_run(session, action.id, ActionStatus.failed)
            if attempt < self.chat_action_max_timeout_attempts:
                payload_json = dict(action.payload_json or {})
                payload_json["chat_retry_attempt"] = attempt + 1
                payload_json["chat_retry_parent_action_id"] = action.id
                retry = ActionDispatch(
                    cocoon_id=action.cocoon_id,
                    chat_group_id=action.chat_group_id,
                    event_type="chat",
                    status=ActionStatus.queued,
                    debounce_until=datetime.now(UTC).replace(tzinfo=None),
                    payload_json=payload_json,
                )
                session.add(retry)
                session.flush()
                self._commit_then_enqueue(
                    session,
                    action=retry,
                    cocoon_id=retry.cocoon_id,
                    chat_group_id=retry.chat_group_id,
                    event_type="chat",
                    payload=dict(retry.payload_json),
                )
                return
            session.commit()

    def _finish_latest_audit_run(self, session: Session, action_id: str, status: str) -> None:
        audit_run = session.scalar(
            select(AuditRun).where(AuditRun.action_id == action_id).order_by(AuditRun.started_at.desc())
        )
        if not audit_run or audit_run.status != ActionStatus.running:
            return
        audit_run.status = status
        audit_run.finished_at = datetime.now(UTC).replace(tzinfo=None)
        session.flush()
