"""Fail-closed local preflight checks shared by scheduled automation runs."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


def assert_safe_root(
    root: str | Path,
    allowed_root: str | Path,
    *,
    marker: str = ".git",
) -> Path:
    """Resolve a repository root and prove it is a marked strict descendant."""

    allowed = Path(allowed_root).resolve(strict=True)
    candidate = Path(root).resolve(strict=True)
    try:
        relative = candidate.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("repository root is outside the configured project directory") from exc
    if relative == Path("."):
        raise ValueError("the allowed project container is not itself a repository target")
    if not isinstance(marker, str) or not marker or Path(marker).is_absolute() or ".." in Path(marker).parts:
        raise ValueError("repository marker is invalid")
    if not (candidate / marker).exists():
        raise ValueError(f"repository marker is missing: {marker}")
    return candidate


def _git_changes(root: Path) -> str:
    """Read tracked and untracked changes without the broad porcelain status walk."""

    tracked = subprocess.run(
        ["git", "diff", "--name-status", "--no-renames", "HEAD", "--"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    lines = [f" M {line.split(chr(9))[-1]}" for line in tracked.splitlines() if line]
    lines.extend(f"?? {line}" for line in untracked.splitlines() if line)
    return "\n".join(lines)


def assert_clean_base(
    root: str | Path,
    *,
    allowed_paths: Sequence[str] = (),
    status_provider: Callable[[Path], str] = _git_changes,
) -> dict[str, Any]:
    """Accept only explicitly allowlisted local TDD changes."""

    repository = Path(root).resolve(strict=True)
    raw = status_provider(repository)
    if not isinstance(raw, str):
        raise TypeError("status provider must return text")
    allowed = tuple(Path(prefix).as_posix().rstrip("/") + "/" for prefix in allowed_paths)
    changes: list[dict[str, str]] = []
    rejected: list[str] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        if len(line) < 4:
            raise RuntimeError("dirty base report is malformed")
        status = line[:2]
        path = line[3:].replace("\\", "/")
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[1]
        changes.append({"status": status, "path": path})
        if not any(path == prefix[:-1] or path.startswith(prefix) for prefix in allowed):
            rejected.append(path)
    if rejected:
        raise RuntimeError(f"repository base is dirty outside allowed paths: {rejected}")
    return {"clean": True, "changes": changes}


def assert_disk_space(
    path: str | Path,
    required_bytes: int,
    *,
    statvfs: Callable[[str | Path], Any] = os.statvfs,
) -> dict[str, int]:
    if isinstance(required_bytes, bool) or not isinstance(required_bytes, int) or required_bytes < 0:
        raise ValueError("required_bytes must be a nonnegative integer")
    stats = statvfs(path)
    available = int(stats.f_bavail) * int(stats.f_frsize)
    if available < required_bytes:
        raise OSError(f"insufficient disk space: need {required_bytes}, have {available}")
    return {
        "available_bytes": available,
        "required_bytes": required_bytes,
        "headroom_bytes": available - required_bytes,
    }


def _enabled(value: Any) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "on"}


def assert_no_live_side_effects(environment: Mapping[str, Any]) -> dict[str, Any]:
    """Prove a test/dry-run context contains no live publication authority."""

    if not isinstance(environment, Mapping):
        raise TypeError("environment must be a mapping")
    normalized = {str(key).upper(): value for key, value in environment.items()}
    if not _enabled(normalized.get("DRY_RUN", "0")):
        raise PermissionError("dry-run mode is required")
    if _enabled(normalized.get("SOCIAL_LOCAL_PUBLISH", "0")):
        raise PermissionError("local live publication is forbidden in preflight")
    environment_name = str(normalized.get("ENVIRONMENT", "test")).casefold()
    if environment_name in {"prod", "production", "live"}:
        raise PermissionError("production environment is forbidden in dry-run preflight")
    authority_markers = ("TOKEN", "SECRET", "PASSWORD", "PRIVATE_KEY", "AUTHORIZATION")
    if any(
        value not in (None, "") and any(marker in key for marker in authority_markers)
        for key, value in normalized.items()
    ):
        raise PermissionError("live credential-shaped environment value is forbidden")
    return {"safe": True, "environment": environment_name}


def _parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError("timestamp must be text")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return parsed


def _rfc3339(value: datetime) -> str:
    normalized = value.astimezone(UTC).replace(microsecond=0).isoformat()
    return normalized.replace("+00:00", "Z")


def _lock_document(owner: str, now: str, ttl_seconds: int) -> dict[str, str]:
    if not isinstance(owner, str) or not owner.strip() or len(owner) > 200:
        raise ValueError("lock owner is invalid")
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be a positive integer")
    acquired = _parse_timestamp(now)
    return {
        "owner": owner,
        "acquired_at": _rfc3339(acquired),
        "expires_at": _rfc3339(acquired + timedelta(seconds=ttl_seconds)),
    }


def _write_descriptor(descriptor: int, document: dict[str, str]) -> None:
    content = (json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def acquire_lock(
    lock_path: str | Path,
    owner: str,
    now: str,
    *,
    ttl_seconds: int = 3600,
) -> dict[str, Any]:
    """Atomically create a lock or reclaim it only after its recorded expiry."""

    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = _lock_document(owner, now, ttl_seconds)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        descriptor = -1
    if descriptor >= 0:
        _write_descriptor(descriptor, document)
        return {"acquired": True, "owner": owner, "reclaimed_from": None}

    guard = path.with_name(f".{path.name}.reclaim")
    try:
        guard_descriptor = os.open(guard, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise BlockingIOError("another process is checking the existing lock") from exc
    os.close(guard_descriptor)
    try:
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            existing_owner = existing["owner"]
            expires_at = _parse_timestamp(existing["expires_at"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise BlockingIOError("existing lock is malformed and requires manual review") from exc
        if _parse_timestamp(now) <= expires_at:
            raise BlockingIOError(f"lock is held by {existing_owner}")

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            _write_descriptor(descriptor, document)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return {"acquired": True, "owner": owner, "reclaimed_from": existing_owner}
    finally:
        guard.unlink(missing_ok=True)


def release_lock(lock_path: str | Path, owner: str) -> dict[str, Any]:
    path = Path(lock_path)
    if not path.exists():
        return {"released": False, "reason": "absent"}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PermissionError("cannot release malformed lock") from exc
    if document.get("owner") != owner:
        raise PermissionError("only the recorded owner can release the lock")
    path.unlink()
    return {"released": True}
