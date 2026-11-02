"""Bar label formatting. Keep in sync with Format.js."""

from __future__ import annotations


def countdown(remaining_seconds: float) -> str:
    """Format time until reset.

    One day or more is ``3d 4h``, including a zero hour part (``1d 0h``).
    Under a day it is hours and minutes, ``4h 12m``. The last hour is
    ``0h 42m``. A non-positive remaining time is ``0h 0m``.
    """
    try:
        remaining = int(remaining_seconds)
    except (TypeError, ValueError):
        return "0h 0m"
    if remaining <= 0:
        return "0h 0m"
    if remaining < 86400:
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        return f"{hours}h {minutes}m"
    days = remaining // 86400
    hours = (remaining % 86400) // 3600
    return f"{days}d {hours}h"


def percent_text(percent: float) -> str:
    try:
        value = float(percent)
    except (TypeError, ValueError):
        return ""
    if value != value or value in (float("inf"), float("-inf")):
        return ""
    rounded = int(value + 0.5) if value >= 0 else 0
    if rounded < 0:
        rounded = 0
    if rounded > 100:
        rounded = 100
    return f"{rounded}%"


def label(percent: float, remaining_seconds: float) -> str:
    used = percent_text(percent)
    if used == "":
        return ""
    return f"{used} · {countdown(remaining_seconds)}"
