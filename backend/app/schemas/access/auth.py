from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RoleOut(ORMModel):
    id: str
    name: str
    permissions_json: dict[str, bool]


class RoleCreate(BaseModel):
    name: str = Field(min_length=1)
    permissions_json: dict[str, bool] = Field(default_factory=dict)


class RoleUpdate(BaseModel):
    name: str | None = None
    permissions_json: dict[str, bool] | None = None


class UserOut(ORMModel):
    id: str
    username: str
    email: str | None
    role_id: str | None
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    username: str = Field(min_length=1)
    email: EmailStr | None = None
    password: str = Field(min_length=4)
    role_id: str | None = None
    is_active: bool = True


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1)
    email: EmailStr | None = None
    role_id: str | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=4)
