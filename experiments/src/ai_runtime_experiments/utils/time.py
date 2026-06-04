from __future__ import annotations

import time
from datetime import datetime, timezone


def utc_now_iso_z(*, now: datetime | None = None) -> str:
    """Return an ISO-8601 UTC timestamp string with a `Z` suffix."""

    dt = now or datetime.now(timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def monotonic_ns() -> int:
    """Return a monotonic timestamp in nanoseconds."""

    return time.monotonic_ns()
