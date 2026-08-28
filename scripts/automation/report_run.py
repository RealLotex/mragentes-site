"""Sanitized, deterministic run reports for local and scheduled automations."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


_REPORT_FIELDS = {
    "schema_version",
    "run_id",
    "kind",
    "status",
    "started_at",
    "finished_at",
    "checks",
    "effects",
    "summary",
}
_CHECK_STATUS = {"passed", "failed", "skipped", "warning"}
_EFFECT_STATUS = {"planned", "confirmed", "partial", "failed", "skipped", "uncertain"}
_FINAL_STATUS = {"success", "failed", "partial", "skipped", "needs_review"}
_SENSITIVE_KEYS = (
    "token",
    "secret",
    "password",
    "authorization",
    "private_key",
    "cookie",
    "caption",
)


def _text(value: Any, field: str, maximum: int = 500) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    if len(value) > maximum or "\x00" in value:
        raise ValueError(f"{field} exceeds its limit")
    return value


def _timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not re.search(r"(?:Z|[+-]\d{2}:\d{2})$", value):
        raise ValueError(f"{field} must include an RFC3339 timezone")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return value


def new_report(run_id: str, kind: str, started_at: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": _text(run_id, "run_id", 250),
        "kind": _text(kind, "kind", 100),
        "status": "running",
        "started_at": _timestamp(started_at, "started_at"),
        "finished_at": None,
        "checks": [],
        "effects": [],
        "summary": {},
    }


def _running(report: dict[str, Any]) -> None:
    if not isinstance(report, dict) or report.get("status") != "running":
        raise ValueError("report is not in the running state")


def add_check(
    report: dict[str, Any],
    name: str,
    status: str,
    *,
    duration_ms: int | None = None,
    detail: Any = None,
    required: bool = False,
) -> dict[str, Any]:
    _running(report)
    name = _text(name, "check name", 150)
    if status not in _CHECK_STATUS:
        raise ValueError("unknown check status")
    if any(check.get("name") == name for check in report.get("checks", [])):
        raise ValueError("check name already exists")
    if duration_ms is not None and (
        isinstance(duration_ms, bool) or not isinstance(duration_ms, int) or duration_ms < 0
    ):
        raise ValueError("duration_ms must be a nonnegative integer")
    if not isinstance(required, bool):
        raise TypeError("required must be boolean")
    entry: dict[str, Any] = {"name": name, "status": status}
    if duration_ms is not None:
        entry["duration_ms"] = duration_ms
    if detail is not None:
        entry["detail"] = redact(detail)
    if required:
        entry["required"] = True
    report.setdefault("checks", []).append(entry)
    return report


def _safe_external_id(value: Any) -> str:
    text = _text(value, "external_id", 2000)
    if re.fullmatch(r"[0-9a-f]{40}", text):
        return text
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def add_effect(
    report: dict[str, Any],
    kind: str,
    status: str,
    *,
    target: str | None = None,
    external_id: str | None = None,
    detail: Any = None,
) -> dict[str, Any]:
    _running(report)
    entry: dict[str, Any] = {"kind": _text(kind, "effect kind", 100), "status": status}
    if status not in _EFFECT_STATUS:
        raise ValueError("unknown effect status")
    if target is not None:
        entry["target"] = redact(_text(target, "effect target", 1000))
    if external_id is not None:
        entry["external_id"] = _safe_external_id(external_id)
    if detail is not None:
        entry["detail"] = redact(detail)
    report.setdefault("effects", []).append(entry)
    return report


def _redacted_url(value: str, *, endpoint: bool = False) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return "[REDACTED]"
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "[REDACTED]" if endpoint else value
    hostname = parsed.hostname.casefold()
    netloc = hostname if port is None else f"{hostname}:{port}"
    path = "/[REDACTED]" if endpoint else (parsed.path or "/")
    return urlunsplit((parsed.scheme.casefold(), netloc, path, "", ""))


def redact(value: Any, *, _key: str = "") -> Any:
    """Return a recursively sanitized copy suitable for durable reports."""

    normalized_key = _key.casefold().replace("-", "_")
    if any(marker in normalized_key for marker in _SENSITIVE_KEYS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(key): redact(item, _key=str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, _key=normalized_key) for item in value]
    if isinstance(value, tuple):
        return [redact(item, _key=normalized_key) for item in value]
    if isinstance(value, str):
        if "BEGIN PRIVATE KEY" in value or re.search(r"\b(?:ghp_|EAA)[A-Za-z0-9_-]{20,}", value):
            return "[REDACTED]"
        if "endpoint" in normalized_key:
            return _redacted_url(value, endpoint=True)
        if "url" in normalized_key or re.match(r"^https?://", value, re.IGNORECASE):
            return _redacted_url(value)
        return value
    return deepcopy(value)


def finalize(
    report: dict[str, Any], status: str, finished_at: str
) -> dict[str, Any]:
    _running(report)
    if status not in _FINAL_STATUS:
        raise ValueError("illegal final report status")
    finished = _timestamp(finished_at, "finished_at")
    if status == "success":
        failed_required = [
            check
            for check in report.get("checks", [])
            if check.get("required") is True and check.get("status") != "passed"
        ]
        uncertain_effects = [
            effect
            for effect in report.get("effects", [])
            if effect.get("status") not in {"confirmed", "skipped"}
        ]
        if failed_required or uncertain_effects:
            raise ValueError("success requires passed checks and confirmed effects")
    report["status"] = status
    report["finished_at"] = finished
    return report


def _validated_report(report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict) or set(report) != _REPORT_FIELDS:
        raise ValueError("report does not match the closed schema")
    if report.get("schema_version") != 1 or isinstance(report.get("schema_version"), bool):
        raise ValueError("unsupported report schema")
    _text(report.get("run_id"), "run_id", 250)
    _text(report.get("kind"), "kind", 100)
    _timestamp(report.get("started_at"), "started_at")
    if report.get("status") == "running":
        if report.get("finished_at") is not None:
            raise ValueError("running report has a finish time")
    elif report.get("status") in _FINAL_STATUS:
        _timestamp(report.get("finished_at"), "finished_at")
    else:
        raise ValueError("report status is invalid")
    if not isinstance(report.get("checks"), list) or not isinstance(report.get("effects"), list):
        raise ValueError("checks and effects must be lists")
    if not isinstance(report.get("summary"), dict):
        raise ValueError("summary must be a mapping")
    return redact(report)


def write_report(report: dict[str, Any], output_path: str | Path) -> Path:
    """Create a final sanitized report atomically and never overwrite evidence."""

    output = Path(output_path)
    if output.exists():
        raise FileExistsError(f"report already exists: {output.name}")
    sanitized = _validated_report(deepcopy(report))
    content = (
        json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, output)
        except FileExistsError:
            raise FileExistsError(f"report already exists: {output.name}")
    finally:
        temporary.unlink(missing_ok=True)
    return output
