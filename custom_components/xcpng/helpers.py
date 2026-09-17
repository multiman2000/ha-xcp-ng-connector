"""Small pure helpers to derive metrics from raw XO REST API payloads."""
from __future__ import annotations

from typing import Any


def host_cpu_usage_percent(stats: dict[str, Any] | None) -> float | None:
    """Average the most recent per-core sample from a /hosts/{id}/stats payload."""
    if not stats:
        return None
    cpus = (stats.get("stats") or {}).get("cpus")
    if not cpus:
        return None
    latest_values = [values[-1] for values in cpus.values() if values]
    if not latest_values:
        return None
    return round(sum(latest_values) / len(latest_values), 1)


def usage_percent(usage: float | int | None, size: float | int | None) -> float | None:
    """Return a 0-100 percentage, guarding against missing/zero totals."""
    if usage is None or not size:
        return None
    return round(usage / size * 100, 1)
