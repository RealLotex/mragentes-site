"""Validation of the fourteen-day shadow-run evidence required before cutover."""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable


REQUIRED_DAYS = 14


def validate_soak(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Summarize unique successful local dates; never infer missing evidence."""

    observed_dates: set[str] = set()
    invalid = 0
    for record in records:
        if not isinstance(record, dict):
            invalid += 1
            continue
        local_date = record.get("local_date")
        status = record.get("status")
        try:
            canonical = date.fromisoformat(local_date).isoformat() if isinstance(local_date, str) else ""
        except ValueError:
            canonical = ""
        if canonical and canonical == local_date and status in {"success", "skipped_valid"}:
            observed_dates.add(canonical)
        else:
            invalid += 1
    observed = len(observed_dates)
    return {
        "required_days": REQUIRED_DAYS,
        "observed_days": observed,
        "missing_days": max(0, REQUIRED_DAYS - observed),
        "invalid_records": invalid,
        "complete": observed >= REQUIRED_DAYS and invalid == 0,
    }
