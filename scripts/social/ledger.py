"""Durable, local publication ledger for the social automation.

The ledger deliberately stores only operational metadata.  Captions, access
tokens, request bodies and remote credentials never belong in this file.  All
mutations are serialized through a sidecar lock and committed with an atomic
``os.replace`` so a crash cannot leave a half-written JSON document behind.
"""

from __future__ import annotations

import copy
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import tempfile
import threading
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
PLATFORMS = ("facebook", "instagram")
KINDS = frozenset({"blog_note", "daily_owned"})

_DEDUPE_RE = re.compile(
    r"^social:(?:blog_note|daily_owned):[A-Za-z0-9][A-Za-z0-9._:-]{0,479}$"
)
_HASH_RE = re.compile(r"^sha256:[^\s]{1,512}$")
_LOCAL_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ENTRY_FIELDS = frozenset(
    {
        "dedupe_key",
        "content_hash",
        "kind",
        "local_date",
        "run_id",
        "status",
        "created_at",
        "updated_at",
        "completed_at",
        "migrated_at",
        "platforms",
    }
)
_PLATFORM_FIELDS = frozenset(
    {
        "status",
        "remote_id",
        "permalink",
        "confirmed_at",
        "category",
        "reason_hash",
        "observed_at",
    }
)
_ENTRY_STATUSES = frozenset({"in_progress", "partial", "complete"})
_PLATFORM_STATUSES = frozenset({"pending", "confirmed", "failed", "uncertain"})
_FAILURE_CATEGORIES = frozenset({"retryable", "permanent", "uncertain"})

_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


class LedgerError(RuntimeError):
    """Base class for ledger failures."""


class LedgerCorrupt(LedgerError):
    """The on-disk document cannot be trusted."""


class LedgerConflict(LedgerError):
    """A requested mutation disagrees with already-persisted evidence."""


def _empty_ledger() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "entries": {}}


def _path(value: os.PathLike[str] | str) -> Path:
    candidate = Path(value)
    if not candidate.name:
        raise ValueError("ledger path must name a file")
    return candidate


def _thread_lock_for(path: Path) -> threading.RLock:
    key = os.path.abspath(os.fspath(path))
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def _exclusive(path: Path) -> Iterator[None]:
    """Serialize a read/modify/write transaction across threads and processes."""

    path.parent.mkdir(parents=True, exist_ok=True)
    thread_lock = _thread_lock_for(path)
    lock_path = path.with_name(f".{path.name}.lock")
    with thread_lock:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


def _parse_time(value: Any, field: str) -> dt.datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a timezone-aware ISO timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def _validate_dedupe_key(value: Any) -> str:
    if not isinstance(value, str) or not _DEDUPE_RE.fullmatch(value):
        raise ValueError("invalid dedupe key")
    return value


def _validate_hash(value: Any, field: str = "content hash") -> str:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise ValueError(f"invalid {field}")
    return value


def _validate_platform(platform: Any) -> str:
    if platform not in PLATFORMS:
        raise ValueError(f"unsupported platform: {platform!r}")
    return str(platform)


def _validate_nonempty(value: Any, field: str, *, maximum: int = 1024) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _validate_platform_record(record: Any, *, location: str) -> None:
    if not isinstance(record, dict):
        raise LedgerCorrupt(f"corrupt ledger: {location} must be an object")
    extra = set(record) - _PLATFORM_FIELDS
    if extra:
        raise LedgerCorrupt(f"corrupt ledger: unsupported fields in {location}: {sorted(extra)}")
    status = record.get("status")
    if status not in _PLATFORM_STATUSES:
        raise LedgerCorrupt(f"corrupt ledger: invalid platform status in {location}")
    if status == "confirmed":
        try:
            _validate_nonempty(record.get("remote_id"), "remote id")
            _parse_time(record.get("confirmed_at"), f"{location}.confirmed_at")
        except ValueError as exc:
            raise LedgerCorrupt(f"corrupt ledger: {exc}") from exc
        permalink = record.get("permalink")
        if not isinstance(permalink, str) or len(permalink) > 2048:
            raise LedgerCorrupt(f"corrupt ledger: invalid permalink in {location}")
    elif "remote_id" in record or "confirmed_at" in record or "permalink" in record:
        raise LedgerCorrupt(f"corrupt ledger: unconfirmed {location} contains remote evidence")
    if status in {"failed", "uncertain"}:
        category = record.get("category")
        if category not in _FAILURE_CATEGORIES:
            raise LedgerCorrupt(f"corrupt ledger: invalid failure category in {location}")
        reason_hash = record.get("reason_hash")
        try:
            _validate_hash(reason_hash, "reason hash")
            _parse_time(record.get("observed_at"), f"{location}.observed_at")
        except ValueError as exc:
            raise LedgerCorrupt(f"corrupt ledger: {exc}") from exc


def _validate_entry(key: str, entry: Any) -> None:
    if not isinstance(entry, dict):
        raise LedgerCorrupt(f"corrupt ledger: entry {key!r} must be an object")
    missing = {
        "dedupe_key",
        "content_hash",
        "kind",
        "local_date",
        "run_id",
        "status",
        "created_at",
        "updated_at",
        "platforms",
    } - set(entry)
    extra = set(entry) - _ENTRY_FIELDS
    if missing or extra:
        raise LedgerCorrupt(
            f"corrupt ledger entry {key!r}: missing={sorted(missing)}, extra={sorted(extra)}"
        )
    try:
        validated_key = _validate_dedupe_key(key)
        _validate_dedupe_key(entry["dedupe_key"])
        _validate_hash(entry["content_hash"])
        _validate_nonempty(entry["run_id"], "run id", maximum=512)
        _parse_time(entry["created_at"], "created_at")
        _parse_time(entry["updated_at"], "updated_at")
    except ValueError as exc:
        raise LedgerCorrupt(f"corrupt ledger entry {key!r}: {exc}") from exc
    if entry["dedupe_key"] != validated_key:
        raise LedgerCorrupt(f"corrupt ledger: entry key disagrees with dedupe key {key!r}")
    if entry["kind"] not in KINDS:
        raise LedgerCorrupt(f"corrupt ledger: invalid kind in {key!r}")
    if not isinstance(entry["local_date"], str) or not _LOCAL_DATE_RE.fullmatch(
        entry["local_date"]
    ):
        raise LedgerCorrupt(f"corrupt ledger: invalid local date in {key!r}")
    try:
        dt.date.fromisoformat(entry["local_date"])
    except ValueError as exc:
        raise LedgerCorrupt(f"corrupt ledger: invalid local date in {key!r}") from exc
    if entry["status"] not in _ENTRY_STATUSES:
        raise LedgerCorrupt(f"corrupt ledger: invalid entry status in {key!r}")
    platforms = entry["platforms"]
    if not isinstance(platforms, dict) or set(platforms) != set(PLATFORMS):
        raise LedgerCorrupt(f"corrupt ledger: entry {key!r} has extra or missing platforms")
    for platform in PLATFORMS:
        _validate_platform_record(platforms[platform], location=f"{key}.{platform}")
    for timestamp in ("completed_at", "migrated_at"):
        if timestamp in entry:
            try:
                _parse_time(entry[timestamp], timestamp)
            except ValueError as exc:
                raise LedgerCorrupt(f"corrupt ledger entry {key!r}: {exc}") from exc
    if entry["status"] == "complete":
        if "completed_at" not in entry or any(
            platforms[platform]["status"] != "confirmed" for platform in PLATFORMS
        ):
            raise LedgerCorrupt(f"corrupt ledger: complete entry {key!r} lacks confirmations")
    elif "completed_at" in entry:
        raise LedgerCorrupt(f"corrupt ledger: incomplete entry {key!r} has completed_at")


def _validated_copy(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise LedgerCorrupt("corrupt ledger: root must be an object")
    if set(document) != {"schema_version", "entries"}:
        raise LedgerCorrupt("corrupt ledger: unknown root fields or missing entries")
    if document.get("schema_version") != SCHEMA_VERSION:
        raise LedgerCorrupt("corrupt ledger schema version")
    entries = document.get("entries")
    if not isinstance(entries, dict):
        raise LedgerCorrupt("corrupt ledger: entries must be an object")
    for key, entry in entries.items():
        if not isinstance(key, str):
            raise LedgerCorrupt("corrupt ledger: entry keys must be strings")
        _validate_entry(key, entry)
    return copy.deepcopy(document)


def _load_unlocked(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_ledger()
    try:
        raw = path.read_text(encoding="utf-8")
        document = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LedgerCorrupt(f"corrupt ledger JSON at {path.name}") from exc
    return _validated_copy(document)


def load_ledger(path: os.PathLike[str] | str) -> dict[str, Any]:
    """Load and validate a ledger, returning an empty document if absent."""

    return _load_unlocked(_path(path))


def _save_unlocked(document: Mapping[str, Any], path: Path) -> dict[str, Any]:
    checked = _validated_copy(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(checked, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            os.chmod(temporary_name, 0o600)
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
    return checked


def save_ledger(
    document: Mapping[str, Any], path: os.PathLike[str] | str
) -> dict[str, Any]:
    """Validate and atomically persist a complete ledger document."""

    destination = _path(path)
    checked = _validated_copy(document)
    with _exclusive(destination):
        return _save_unlocked(checked, destination)


def _content_fingerprint(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _legacy_key(kind: str, source_key: str, record: Mapping[str, Any]) -> str:
    suffix = record.get("date") if kind == "daily_owned" else source_key
    if not isinstance(suffix, str):
        raise LedgerCorrupt(f"legacy ledger entry {source_key!r} has no usable date")
    key = f"social:{kind}:{suffix}"
    try:
        return _validate_dedupe_key(key)
    except ValueError as exc:
        raise LedgerCorrupt(f"legacy ledger entry {source_key!r} has an unsafe key") from exc


def migrate_legacy_state(
    legacy: Mapping[str, Any],
    path: os.PathLike[str] | str,
    *,
    kinds: Mapping[str, str],
    now: str,
) -> dict[str, Any]:
    """Import the old state shape exactly once without mutating its input."""

    _parse_time(now, "now")
    if not isinstance(legacy, Mapping) or not isinstance(legacy.get("published"), Mapping):
        raise LedgerCorrupt("legacy ledger is corrupt: published must be an object")
    if not isinstance(kinds, Mapping):
        raise ValueError("kinds must map every legacy key to a typed kind")
    published = legacy["published"]
    destination = _path(path)
    candidates: list[tuple[str, dict[str, Any]]] = []
    for source_key in sorted(published):
        record = published[source_key]
        if not isinstance(source_key, str) or not isinstance(record, Mapping):
            raise LedgerCorrupt("legacy ledger entries must be named objects")
        kind = kinds.get(source_key)
        if kind not in KINDS:
            raise ValueError(f"missing or invalid kind for legacy key {source_key!r}")
        local_date = record.get("date")
        if not isinstance(local_date, str) or not _LOCAL_DATE_RE.fullmatch(local_date):
            raise LedgerCorrupt(f"legacy ledger entry {source_key!r} has invalid date")
        try:
            dt.date.fromisoformat(local_date)
        except ValueError as exc:
            raise LedgerCorrupt(f"legacy ledger entry {source_key!r} has invalid date") from exc
        dedupe_key = _legacy_key(kind, source_key, record)
        platforms: dict[str, dict[str, Any]] = {}
        for platform in PLATFORMS:
            remote_id = record.get(platform)
            if isinstance(remote_id, str) and remote_id.strip():
                platforms[platform] = {
                    "status": "confirmed",
                    "remote_id": remote_id,
                    "permalink": "",
                    "confirmed_at": now,
                }
            else:
                platforms[platform] = {"status": "pending"}
        complete_entry = all(
            platforms[platform]["status"] == "confirmed" for platform in PLATFORMS
        )
        fingerprint_input = {
            "legacy_key": source_key,
            "kind": kind,
            "date": local_date,
            "images": copy.deepcopy(record.get("images", [])),
        }
        entry: dict[str, Any] = {
            "dedupe_key": dedupe_key,
            "content_hash": _content_fingerprint(fingerprint_input),
            "kind": kind,
            "local_date": local_date,
            "run_id": f"migration:{dedupe_key}",
            "status": "complete" if complete_entry else "partial",
            "created_at": now,
            "updated_at": now,
            "migrated_at": now,
            "platforms": platforms,
        }
        if complete_entry:
            entry["completed_at"] = now
        candidates.append((dedupe_key, entry))

    with _exclusive(destination):
        document = _load_unlocked(destination)
        changed = False
        for dedupe_key, candidate in candidates:
            existing = document["entries"].get(dedupe_key)
            if existing is None:
                document["entries"][dedupe_key] = candidate
                changed = True
            elif existing != candidate:
                raise LedgerConflict(f"migration conflict for dedupe key {dedupe_key}")
        if changed:
            _save_unlocked(document, destination)
        return copy.deepcopy(document)


def acquire(
    path: os.PathLike[str] | str,
    *,
    dedupe_key: str,
    content_hash: str,
    kind: str,
    local_date: str,
    run_id: str,
    now: str,
) -> dict[str, Any]:
    """Create an idempotency owner or resume its existing incomplete run."""

    key = _validate_dedupe_key(dedupe_key)
    digest = _validate_hash(content_hash)
    if kind not in KINDS:
        raise ValueError(f"invalid social content kind: {kind!r}")
    if not isinstance(local_date, str) or not _LOCAL_DATE_RE.fullmatch(local_date):
        raise ValueError("local_date must be an ISO date")
    try:
        dt.date.fromisoformat(local_date)
    except ValueError as exc:
        raise ValueError("local_date must be an ISO date") from exc
    owner = _validate_nonempty(run_id, "run id", maximum=512)
    _parse_time(now, "now")
    destination = _path(path)
    with _exclusive(destination):
        document = _load_unlocked(destination)
        existing = document["entries"].get(key)
        if existing is not None:
            if existing["content_hash"] != digest:
                raise LedgerConflict(f"content hash conflict for dedupe key {key}")
            if existing["kind"] != kind or existing["local_date"] != local_date:
                raise LedgerConflict(f"content metadata conflict for dedupe key {key}")
            decision = "skip_complete" if existing["status"] == "complete" else "resume"
            return {"decision": decision, "entry": copy.deepcopy(existing)}
        entry = {
            "dedupe_key": key,
            "content_hash": digest,
            "kind": kind,
            "local_date": local_date,
            "run_id": owner,
            "status": "in_progress",
            "created_at": now,
            "updated_at": now,
            "platforms": {platform: {"status": "pending"} for platform in PLATFORMS},
        }
        document["entries"][key] = entry
        _save_unlocked(document, destination)
        return {"decision": "acquired", "entry": copy.deepcopy(entry)}


def _entry_for_mutation(document: dict[str, Any], dedupe_key: str) -> dict[str, Any]:
    key = _validate_dedupe_key(dedupe_key)
    try:
        return document["entries"][key]
    except KeyError as exc:
        raise LedgerConflict(f"unknown dedupe key {key}") from exc


def checkpoint(
    path: os.PathLike[str] | str,
    *,
    dedupe_key: str,
    platform: str,
    remote_id: str,
    permalink: str,
    now: str,
) -> dict[str, Any]:
    """Persist one confirmed remote publication before attempting the next."""

    platform = _validate_platform(platform)
    remote_id = _validate_nonempty(remote_id, "remote id")
    if not isinstance(permalink, str) or len(permalink) > 2048:
        raise ValueError("permalink must be a string")
    _parse_time(now, "now")
    destination = _path(path)
    with _exclusive(destination):
        document = _load_unlocked(destination)
        entry = _entry_for_mutation(document, dedupe_key)
        current = entry["platforms"][platform]
        if current["status"] == "confirmed":
            if current["remote_id"] != remote_id:
                raise LedgerConflict(f"remote id conflict for {platform}")
            if current.get("permalink", "") == permalink:
                return copy.deepcopy(entry)
            if entry["status"] == "complete" or (
                current.get("permalink") and permalink != current.get("permalink")
            ):
                raise LedgerConflict(f"remote permalink conflict for {platform}")
        elif entry["status"] == "complete":
            raise LedgerConflict("complete ledger entries are frozen")
        entry["platforms"][platform] = {
            "status": "confirmed",
            "remote_id": remote_id,
            "permalink": permalink,
            "confirmed_at": now,
        }
        entry["status"] = (
            "partial"
            if any(
                state["status"] in {"failed", "uncertain"}
                for state in entry["platforms"].values()
            )
            else "in_progress"
        )
        entry["updated_at"] = now
        _save_unlocked(document, destination)
        return copy.deepcopy(entry)


def complete(
    path: os.PathLike[str] | str,
    *,
    dedupe_key: str,
    now: str,
) -> dict[str, Any]:
    """Freeze a run only after both requested platforms are confirmed."""

    _parse_time(now, "now")
    destination = _path(path)
    with _exclusive(destination):
        document = _load_unlocked(destination)
        entry = _entry_for_mutation(document, dedupe_key)
        if entry["status"] == "complete":
            return copy.deepcopy(entry)
        missing = [
            platform
            for platform in PLATFORMS
            if entry["platforms"][platform]["status"] != "confirmed"
        ]
        if missing:
            raise ValueError(f"missing platform confirmations: {', '.join(missing)}")
        entry["status"] = "complete"
        entry["completed_at"] = now
        entry["updated_at"] = now
        _save_unlocked(document, destination)
        return copy.deepcopy(entry)


def mark_partial(
    path: os.PathLike[str] | str,
    *,
    dedupe_key: str,
    platform: str,
    category: str,
    reason: str,
    now: str,
) -> dict[str, Any]:
    """Record a failed/uncertain platform without persisting raw error text."""

    platform = _validate_platform(platform)
    if category not in _FAILURE_CATEGORIES:
        raise ValueError(f"invalid failure category: {category!r}")
    if not isinstance(reason, str):
        raise ValueError("reason must be a string")
    _parse_time(now, "now")
    reason_hash = "sha256:" + hashlib.sha256(reason.encode("utf-8")).hexdigest()
    desired = {
        "status": "uncertain" if category == "uncertain" else "failed",
        "category": category,
        "reason_hash": reason_hash,
        "observed_at": now,
    }
    destination = _path(path)
    with _exclusive(destination):
        document = _load_unlocked(destination)
        entry = _entry_for_mutation(document, dedupe_key)
        if entry["status"] == "complete":
            raise LedgerConflict("complete ledger entries are frozen")
        current = entry["platforms"][platform]
        if current["status"] == "confirmed":
            raise LedgerConflict(f"confirmed {platform} checkpoint cannot be downgraded")
        if current == desired:
            return copy.deepcopy(entry)
        if current["status"] in {"failed", "uncertain"}:
            raise LedgerConflict(f"conflicting partial evidence for {platform}")
        entry["platforms"][platform] = desired
        entry["status"] = "partial"
        entry["updated_at"] = now
        _save_unlocked(document, destination)
        return copy.deepcopy(entry)


def _matching_time(value: Any) -> dt.datetime | None:
    try:
        return _parse_time(value, "created_at")
    except ValueError:
        return None


def find_recent_match(
    expected: Mapping[str, Any],
    recent: Iterable[Mapping[str, Any]],
    *,
    tolerance_seconds: int | float,
) -> dict[str, Any]:
    """Reconcile a lost checkpoint, stopping if remote evidence is ambiguous."""

    if not isinstance(expected, Mapping):
        raise ValueError("expected match descriptor must be an object")
    platform = _validate_platform(expected.get("platform"))
    caption_hash = _validate_hash(expected.get("caption_hash"), "caption hash")
    expected_asset_hash = expected.get("asset_hash")
    asset_hash = (
        _validate_hash(expected_asset_hash, "asset hash")
        if expected_asset_hash is not None
        else None
    )
    expected_time = _parse_time(expected.get("created_at"), "created_at")
    if not isinstance(tolerance_seconds, int | float) or tolerance_seconds < 0:
        raise ValueError("tolerance_seconds must be non-negative")
    matches: list[dict[str, Any]] = []
    for candidate in recent:
        if not isinstance(candidate, Mapping):
            continue
        if (
            candidate.get("platform") != platform
            or candidate.get("caption_hash") != caption_hash
            or (asset_hash is not None and candidate.get("asset_hash") != asset_hash)
        ):
            continue
        candidate_time = _matching_time(candidate.get("created_at"))
        remote_id = candidate.get("remote_id")
        if candidate_time is None or not isinstance(remote_id, str) or not remote_id.strip():
            continue
        if abs((candidate_time - expected_time).total_seconds()) <= tolerance_seconds:
            matches.append(copy.deepcopy(dict(candidate)))
    if not matches:
        return {"decision": "none", "match": None}
    if len(matches) == 1:
        return {"decision": "matched", "match": matches[0]}
    return {"decision": "needs_review", "matches": matches}


def recovery_plan(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Return a fail-closed, side-effect-free plan for an interrupted run."""

    if not isinstance(entry, Mapping) or not isinstance(entry.get("platforms"), Mapping):
        return {"decision": "needs_review", "platforms": []}
    platforms = entry["platforms"]
    if set(platforms) - set(PLATFORMS):
        return {"decision": "needs_review", "platforms": []}
    states: dict[str, Mapping[str, Any]] = {}
    for platform in PLATFORMS:
        state = platforms.get(platform, {"status": "pending"})
        if not isinstance(state, Mapping):
            return {"decision": "needs_review", "platforms": []}
        states[platform] = state
    if entry.get("status") == "complete":
        if all(states[platform].get("status") == "confirmed" for platform in PLATFORMS):
            return {"decision": "skip_complete", "platforms": []}
        return {"decision": "needs_review", "platforms": []}
    retry: list[str] = []
    for platform in PLATFORMS:
        state = states[platform]
        status = state.get("status")
        if status == "confirmed":
            continue
        if status == "pending" or (
            status == "failed" and state.get("category") == "retryable"
        ):
            retry.append(platform)
            continue
        return {"decision": "needs_review", "platforms": []}
    if retry:
        return {"decision": "publish_missing", "platforms": retry}
    return {"decision": "complete", "platforms": []}


__all__ = [
    "LedgerConflict",
    "LedgerCorrupt",
    "LedgerError",
    "acquire",
    "checkpoint",
    "complete",
    "find_recent_match",
    "load_ledger",
    "mark_partial",
    "migrate_legacy_state",
    "recovery_plan",
    "save_ledger",
]
