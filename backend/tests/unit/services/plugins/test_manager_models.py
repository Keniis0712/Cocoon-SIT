from __future__ import annotations

from datetime import datetime

from app.services.plugins.manager.models import next_cron_run


def test_next_cron_run_hourly_expression_uses_next_hour_not_next_sunday() -> None:
    after = datetime(2026, 4, 25, 12, 0, 0)

    result = next_cron_run("0 * * * *", after)

    assert result == datetime(2026, 4, 25, 13, 0, 0)


def test_next_cron_run_every_five_minutes_handles_wildcard_weekday() -> None:
    after = datetime(2026, 4, 25, 12, 1, 0)

    result = next_cron_run("*/5 * * * *", after)

    assert result == datetime(2026, 4, 25, 12, 5, 0)


def test_next_cron_run_treats_weekday_seven_as_sunday_alias() -> None:
    after = datetime(2026, 4, 25, 12, 0, 0)

    zero_result = next_cron_run("0 0 * * 0", after)
    seven_result = next_cron_run("0 0 * * 7", after)

    assert zero_result == datetime(2026, 4, 26, 0, 0, 0)
    assert seven_result == zero_result
