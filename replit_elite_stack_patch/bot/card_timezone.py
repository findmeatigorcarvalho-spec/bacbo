"""One display clock for live Bac Bo cards: Pawtucket, Rhode Island.

Database timestamps are UTC-naive strings.  Museum posters intentionally keep
their historical timestamps untouched; this module is for live cards only.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

PAWTUCKET_TZ_NAME = "America/New_York"
PAWTUCKET_TZ = ZoneInfo(PAWTUCKET_TZ_NAME)


def parse_db_utc(value: str | None) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    raw = raw[:19].replace("T", " ")
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def pawtucket_time(value: str | None, *, seconds: bool = False) -> str:
    """UTC DB text → a single human clock in Pawtucket, with DST handled."""
    dt = parse_db_utc(value)
    if dt is None:
        return "--:--"
    return dt.astimezone(PAWTUCKET_TZ).strftime("%H:%M:%S" if seconds else "%H:%M")


def pawtucket_forensic(value: str | None) -> str:
    """UTC DB text → dated forensic display, never UTC/BRT."""
    dt = parse_db_utc(value)
    if dt is None:
        return "—"
    return dt.astimezone(PAWTUCKET_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
