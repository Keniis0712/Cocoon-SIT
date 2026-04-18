from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cocoon, Message, SessionState


def list_cocoons(session: Session) -> list[Cocoon]:
    return list(session.scalars(select(Cocoon).order_by(Cocoon.created_at.asc())).all())


def list_messages(session: Session, cocoon_id: str) -> list[Message]:
    return list(
        session.scalars(
            select(Message).where(Message.cocoon_id == cocoon_id).order_by(Message.created_at.asc())
        ).all()
    )


def get_session_state(session: Session, cocoon_id: str) -> SessionState | None:
    return session.get(SessionState, cocoon_id)
