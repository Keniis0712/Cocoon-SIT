from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActionDispatch


def get_action_by_client_request_id(session: Session, client_request_id: str) -> ActionDispatch | None:
    return session.scalar(
        select(ActionDispatch).where(ActionDispatch.client_request_id == client_request_id)
    )
