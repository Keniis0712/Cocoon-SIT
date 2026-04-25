from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, field_serializer


def serialize_utc_datetime(value: datetime) -> str:
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return normalized.isoformat(timespec="seconds").replace("+00:00", "Z")


def validate_timezone_name(value: str | None, *, allow_none: bool = False) -> str | None:
    if value is None:
        return None if allow_none else "UTC"
    candidate = value.strip() or "UTC"
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Invalid timezone") from exc
    return candidate


class UTCModel(BaseModel):
    @field_serializer("*", when_used="json", check_fields=False)
    def serialize_datetime_fields(self, value):
        if isinstance(value, datetime):
            return serialize_utc_datetime(value)
        return value


class ORMModel(UTCModel):
    model_config = ConfigDict(from_attributes=True)


class AcceptedResponse(UTCModel):
    accepted: bool = True
    action_id: str
    status: str
    debounce_until: int | None = None


class MessageResponse(UTCModel):
    message: str


class HealthResponse(UTCModel):
    status: str
    version: str
    now: datetime
