from __future__ import annotations

import multiprocessing as mp
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


def _parse_cron_field(
    value: str, *, minimum: int, maximum: int, sunday_alias: bool = False
) -> set[int]:
    values: set[int] = set()
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            raise ValueError("empty cron field")
        step = 1
        if "/" in part:
            part, raw_step = part.split("/", 1)
            step = int(raw_step)
            if step < 1:
                raise ValueError("cron step must be positive")
        if part == "*":
            start, end = minimum, maximum
        elif "-" in part:
            raw_start, raw_end = part.split("-", 1)
            start, end = int(raw_start), int(raw_end)
        else:
            start = end = int(part)
        if start < minimum or start > maximum or end < minimum or end > maximum:
            raise ValueError("cron field out of range")
        if start > end:
            raise ValueError("cron ranges must be ascending")
        raw_values = range(start, end + 1, step)
        if sunday_alias:
            values.update(0 if item == 7 else item for item in raw_values)
        else:
            values.update(raw_values)
    return values


def validate_cron_expression(expression: str) -> str:
    fields = expression.strip().split()
    if len(fields) != 5:
        raise ValueError("cron expression must have 5 fields")
    _parse_cron_field(fields[0], minimum=0, maximum=59)
    _parse_cron_field(fields[1], minimum=0, maximum=23)
    _parse_cron_field(fields[2], minimum=1, maximum=31)
    _parse_cron_field(fields[3], minimum=1, maximum=12)
    _parse_cron_field(fields[4], minimum=0, maximum=7, sunday_alias=True)
    return " ".join(fields)


def next_cron_run(expression: str, after: datetime) -> datetime:
    fields = validate_cron_expression(expression).split()
    minutes = _parse_cron_field(fields[0], minimum=0, maximum=59)
    hours = _parse_cron_field(fields[1], minimum=0, maximum=23)
    days = _parse_cron_field(fields[2], minimum=1, maximum=31)
    months = _parse_cron_field(fields[3], minimum=1, maximum=12)
    weekdays = _parse_cron_field(fields[4], minimum=0, maximum=7, sunday_alias=True)
    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    deadline = candidate + timedelta(days=366)
    while candidate <= deadline:
        cron_weekday = (candidate.weekday() + 1) % 7
        if (
            candidate.minute in minutes
            and candidate.hour in hours
            and candidate.day in days
            and candidate.month in months
            and cron_weekday in weekdays
        ):
            return candidate
        candidate += timedelta(minutes=1)
    raise ValueError("cron expression has no run time in the next year")


@dataclass
class DaemonHandle:
    plugin_id: str
    process_type: str
    process: mp.Process
    outbound_queue: Any
    inbound_queue: Any | None
    version_id: str


@dataclass(frozen=True)
class ShortLivedScope:
    scope_type: str
    scope_id: str
    user_id: str | None
    config_json: dict[str, Any]
