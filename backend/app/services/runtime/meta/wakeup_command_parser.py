"""Wakeup command parser used by the runtime meta stage."""

from __future__ import annotations

import re


class WakeupCommandParser:
    """Parses explicit user wakeup commands into scheduling hints."""

    def parse(self, latest_content: str) -> dict | None:
        """Return a scheduling hint when the user message encodes `/wakeup`."""
        match = re.match(
            r"^\s*/wakeup\s+(?P<amount>\d+)\s*(?P<unit>[smhdSMHD]?)\s*(?P<reason>.*)$",
            latest_content,
        )
        if not match:
            return None

        amount = int(match.group("amount"))
        unit = (match.group("unit") or "m").lower()
        multiplier = {
            "s": 1,
            "m": 60,
            "h": 60 * 60,
            "d": 60 * 60 * 24,
        }[unit]
        reason = match.group("reason").strip() or "Scheduled by /wakeup command"
        return {
            "delay_seconds": amount * multiplier,
            "reason": reason,
            "payload_json": {
                "scheduled_by": "meta_command",
                "command": latest_content[:200],
            },
        }
