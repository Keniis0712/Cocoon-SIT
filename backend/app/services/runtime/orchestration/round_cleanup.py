from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditArtifact,
    AuditLink,
    AuditRun,
    AuditStep,
    FailedRound,
    MemoryChunk,
    MemoryTag,
    Message,
    MessageTag,
)
from app.services.workspace.targets import build_target_filter


class RoundCleanupService:
    """Deletes stale rows that must be removed before edit/retry replays."""

    def _delete_message_related_rows(self, session: Session, message_ids: list[str]) -> None:
        if not message_ids:
            return
        action_ids = select(Message.action_id).where(Message.id.in_(message_ids))
        run_ids = select(AuditRun.id).where(AuditRun.action_id.in_(action_ids))
        memories = list(
            session.scalars(select(MemoryChunk).where(MemoryChunk.source_message_id.in_(message_ids))).all()
        )
        for memory in memories:
            session.query(MemoryTag).filter(MemoryTag.memory_chunk_id == memory.id).delete()
            session.delete(memory)
        session.query(MessageTag).filter(MessageTag.message_id.in_(message_ids)).delete()
        session.query(FailedRound).filter(FailedRound.action_id.in_(action_ids)).delete(
            synchronize_session=False
        )
        session.query(AuditLink).filter(AuditLink.run_id.in_(run_ids)).delete(
            synchronize_session=False
        )
        session.query(AuditArtifact).filter(AuditArtifact.run_id.in_(run_ids)).delete(
            synchronize_session=False
        )
        session.query(AuditStep).filter(AuditStep.run_id.in_(run_ids)).delete(
            synchronize_session=False
        )
        session.query(AuditRun).filter(AuditRun.id.in_(run_ids)).delete(synchronize_session=False)
        session.query(Message).filter(Message.id.in_(message_ids)).delete(synchronize_session=False)
        session.flush()

    def cleanup_for_edit(
        self,
        session: Session,
        *args,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
        edited_message_id: str | None = None,
    ) -> None:
        if args:
            if len(args) != 2 or cocoon_id is not None or chat_group_id is not None or edited_message_id is not None:
                raise TypeError("cleanup_for_edit() accepts either legacy positional args or keyword target args")
            cocoon_id = args[0]
            edited_message_id = args[1]
        if edited_message_id is None:
            raise TypeError("cleanup_for_edit() missing required edited_message_id")
        target = session.get(Message, edited_message_id)
        if not target:
            return
        later_messages = list(
            session.scalars(
                select(Message)
                .where(
                    build_target_filter(Message, cocoon_id=cocoon_id, chat_group_id=chat_group_id),
                    Message.created_at > target.created_at,
                )
                .order_by(Message.created_at.asc())
            ).all()
        )
        self._delete_message_related_rows(session, [item.id for item in later_messages])

    def cleanup_for_retry(
        self,
        session: Session,
        *args,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
        message_id: str | None = None,
    ) -> None:
        if args:
            if len(args) > 2 or cocoon_id is not None or chat_group_id is not None:
                raise TypeError("cleanup_for_retry() accepts either legacy positional args or keyword target args")
            cocoon_id = args[0]
            if len(args) == 2:
                message_id = args[1]
        query = (
            select(Message)
            .where(
                build_target_filter(Message, cocoon_id=cocoon_id, chat_group_id=chat_group_id),
                Message.role == "assistant",
            )
            .order_by(Message.created_at.desc())
        )
        if message_id:
            anchor = session.get(Message, message_id)
            if anchor:
                query = select(Message).where(
                    build_target_filter(Message, cocoon_id=cocoon_id, chat_group_id=chat_group_id),
                    Message.role == "assistant",
                    Message.created_at >= anchor.created_at,
                ).order_by(Message.created_at.desc())
        latest = session.scalars(query.limit(1)).first()
        if latest:
            self._delete_message_related_rows(session, [latest.id])
