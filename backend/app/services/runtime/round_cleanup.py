from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditArtifact, AuditRun, FailedRound, MemoryChunk, MemoryTag, Message, MessageTag


class RoundCleanupService:
    """Deletes stale rows that must be removed before edit/retry replays."""

    def _delete_message_related_rows(self, session: Session, message_ids: list[str]) -> None:
        if not message_ids:
            return
        memories = list(
            session.scalars(select(MemoryChunk).where(MemoryChunk.source_message_id.in_(message_ids))).all()
        )
        for memory in memories:
            session.query(MemoryTag).filter(MemoryTag.memory_chunk_id == memory.id).delete()
            session.delete(memory)
        session.query(MessageTag).filter(MessageTag.message_id.in_(message_ids)).delete()
        session.query(FailedRound).filter(FailedRound.action_id.in_(
            select(Message.action_id).where(Message.id.in_(message_ids))
        )).delete(synchronize_session=False)
        for artifact in session.scalars(
            select(AuditArtifact).where(AuditArtifact.run_id.in_(
                select(AuditRun.id).where(AuditRun.action_id.in_(
                    select(Message.action_id).where(Message.id.in_(message_ids))
                ))
            ))
        ).all():
            session.delete(artifact)
        session.query(AuditRun).filter(AuditRun.action_id.in_(
            select(Message.action_id).where(Message.id.in_(message_ids))
        )).delete(synchronize_session=False)
        session.query(Message).filter(Message.id.in_(message_ids)).delete(synchronize_session=False)
        session.flush()

    def cleanup_for_edit(self, session: Session, cocoon_id: str, edited_message_id: str) -> None:
        target = session.get(Message, edited_message_id)
        if not target:
            return
        later_messages = list(
            session.scalars(
                select(Message)
                .where(Message.cocoon_id == cocoon_id, Message.created_at > target.created_at)
                .order_by(Message.created_at.asc())
            ).all()
        )
        self._delete_message_related_rows(session, [item.id for item in later_messages])

    def cleanup_for_retry(self, session: Session, cocoon_id: str, message_id: str | None = None) -> None:
        query = select(Message).where(Message.cocoon_id == cocoon_id, Message.role == "assistant").order_by(Message.created_at.desc())
        if message_id:
            anchor = session.get(Message, message_id)
            if anchor:
                query = select(Message).where(
                    Message.cocoon_id == cocoon_id,
                    Message.role == "assistant",
                    Message.created_at >= anchor.created_at,
                ).order_by(Message.created_at.desc())
        latest = session.scalars(query.limit(1)).first()
        if latest:
            self._delete_message_related_rows(session, [latest.id])
