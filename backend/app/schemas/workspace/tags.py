from datetime import datetime

from app.schemas.common import ORMModel


class CocoonTagBindingOut(ORMModel):
    id: str
    tag_id: str
    created_at: datetime


class CocoonTagBindResult(ORMModel):
    binding_id: str
    tag_id: str


class ChatGroupTagBindingOut(ORMModel):
    id: str
    tag_id: str
    created_at: datetime


class ChatGroupTagBindResult(ORMModel):
    binding_id: str
    tag_id: str
