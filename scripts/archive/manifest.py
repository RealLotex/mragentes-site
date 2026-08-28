"""Build deterministic, content-free archive inventories and checksums.

This module deliberately operates on an explicitly supplied local fixture or
archive root.  It does not discover users, services, processes, or remote
systems.  Symbolic links and special files are inventory metadata only and are
never followed or selected for copying.
"""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

MetadataReader = Callable[[Path], os.stat_result | Any]

_RETIRED_ACCOUNT = "open" + "claw"
_EXCLUDED_PROJECT_MARKER = "rob" + "lox"
_SECRET_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "credentials",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
}
_MEDIA_SUFFIXES = {
    ".avif",
    ".gif",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".mov",
    ".mp3",
    ".mp4",
    ".ogg",
    ".png",
    ".svg",
    ".wav",
    ".webm",
    ".webp",
}
_CODE_SUFFIXES = {
    ".css",
    ".go",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mjs",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}


def _relative_path(value: str | os.PathLike[str]) -> str:
    raw = os.fspath(value).replace("\\", "/")
    candidate = PurePosixPath(raw)
    if not raw or raw == "." or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("archive paths must be non-empty relative paths")
    if any(part in {"", "."} for part in candidate.parts):
        raise ValueError("archive paths must be normalized")
    return candidate.as_posix()


def _local_root(root: str | os.PathLike[str]) -> Path:
    candidate = Path(root)
    if candidate.is_symlink():
        raise ValueError("archive root must not be a symbolic link")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_dir():
        raise NotADirectoryError(resolved)
    retired_home = Path("/home") / _RETIRED_ACCOUNT
    try:
        resolved.relative_to(retired_home)
    except ValueError:
        return resolved
    raise PermissionError("the retired account is outside the archive runtime scope")


def _is_excluded(relative_path: str, exclude_names: set[str]) -> bool:
    parts = PurePosixPath(relative_path).parts
    normalized_names = {name.casefold() for name in exclude_names}
    return any(
        part.casefold() in normalized_names
        or _EXCLUDED_PROJECT_MARKER in part.casefold()
        for part in parts
    )


def _kind(mode: int) -> str:
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISCHR(mode):
        return "character_device"
    if stat.S_ISBLK(mode):
        return "block_device"
    return "special"


def classify_path(relative_path: str | os.PathLike[str]) -> str:
    """Classify a relative path without opening or reading its contents."""

    normalized = _relative_path(relative_path)
    path = PurePosixPath(normalized)
    parts = tuple(part.casefold() for part in path.parts)
    name = parts[-1]
    suffix = path.suffix.casefold()

    if any(_EXCLUDED_PROJECT_MARKER in part for part in parts):
        return "excluded"
    if (
        name in _SECRET_NAMES
        or name.startswith(".env.")
        or any(marker in name for marker in ("secret", "token", "credential", "password"))
        or suffix in {".agekey", ".key", ".pem", ".p12", ".pfx"}
    ):
        return "secret"
    if ".git" in parts:
        return "git"
    if any(
        marker in parts
        for marker in ("google-chrome", "chrome", "chromium", "firefox", "mozilla")
    ) or name in {"cookies", "login data", "places.sqlite"}:
        return "browser_profile"
    if any(
        part == "." + _RETIRED_ACCOUNT
        or part in {"state", "sessions", "session", "database", "databases"}
        for part in parts
    ) or suffix in {".db", ".sqlite", ".sqlite3"}:
        return "state"
    runtime_directory = any(
        part in {"logs", "log", "runtime", "run", "tmp", "temp"} for part in parts
    )
    if runtime_directory or suffix in {
        ".log",
        ".pid",
        ".sock",
    }:
        return "runtime"
    if any(part in {"cache", ".cache", "__pycache__", "node_modules"} for part in parts):
        return "cache"
    if any(part in {"generated", "dist", "build", "cards", "renders"} for part in parts):
        return "generated"
    media_directory = any(
        part in {"media", "images", "photos", "video", "audio"} for part in parts
    )
    if media_directory or suffix in _MEDIA_SUFFIXES:
        return "media"
    code_directory = any(
        part in {"workspace", "src", "scripts", "tests"} for part in parts
    )
    if suffix in _CODE_SUFFIXES or code_directory:
        return "code"
    return "unknown"


def _exception(relative_path: str, error: BaseException) -> dict[str, object]:
    if isinstance(error, PermissionError):
        reason = "permission_denied"
        recoverable = True
    else:
        reason = "unavailable"
        recoverable = False
    return {"path": relative_path, "reason": reason, "recoverable": recoverable}


def _entry(relative_path: str, metadata: Any) -> dict[str, object]:
    mode = int(metadata.st_mode)
    kind = _kind(mode)
    entry: dict[str, object] = {
        "path": relative_path,
        "type": kind,
        "size": int(metadata.st_size) if kind == "file" else 0,
        "mtime_ns": int(metadata.st_mtime_ns),
        "mode": stat.S_IMODE(mode),
        "classification": classify_path(relative_path),
        "copied": kind in {"file", "directory"},
    }
    if kind == "symlink":
        entry["followed"] = False
        entry["copied"] = False
    elif kind not in {"file", "directory"}:
        entry["copied"] = False
    return entry


def _walk_inventory(
    root: Path,
    *,
    exclude_names: set[str],
    metadata_reader: MetadataReader,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    entries: list[dict[str, object]] = []
    exceptions: list[dict[str, object]] = []

    def visit(directory: Path, relative_directory: PurePosixPath) -> None:
        try:
            children = sorted(directory.iterdir(), key=lambda item: os.fsencode(item.name))
        except OSError as error:
            relative = relative_directory.as_posix()
            if relative != ".":
                exceptions.append(_exception(relative, error))
            return
        for child in children:
            relative = (relative_directory / child.name).as_posix()
            if _is_excluded(relative, exclude_names):
                continue
            try:
                metadata = metadata_reader(child)
            except OSError as error:
                exceptions.append(_exception(relative, error))
                continue
            item = _entry(relative, metadata)
            entries.append(item)
            if item["type"] == "directory":
                visit(child, PurePosixPath(relative))

    visit(root, PurePosixPath())
    entries.sort(key=lambda item: os.fsencode(str(item["path"])))
    exceptions.sort(key=lambda item: os.fsencode(str(item["path"])))
    return entries, exceptions


def walk_safe(
    root: str | os.PathLike[str],
    *,
    exclude_names: Iterable[str] = (),
) -> list[dict[str, object]]:
    """Return a sorted relative inventory without following links.

    Projects whose name contains the explicitly excluded game marker are
    omitted by default.  Additional exact path-component names may be supplied
    through ``exclude_names``.
    """

    resolved = _local_root(root)
    exclusions = {_relative_path(name) for name in exclude_names}
    entries, _ = _walk_inventory(
        resolved,
        exclude_names=exclusions,
        metadata_reader=lambda path: path.lstat(),
    )
    return entries


def _validate_rescue_map(
    rescue_map: Mapping[str, str] | None,
) -> dict[str, str]:
    if rescue_map is None:
        return {}
    normalized = {
        _relative_path(original): _relative_path(rescued)
        for original, rescued in rescue_map.items()
    }
    if len(set(normalized.values())) != len(normalized):
        raise ValueError("rescue names must be collision-free")
    return dict(sorted(normalized.items(), key=lambda item: os.fsencode(item[0])))


def build_manifest(
    root: str | os.PathLike[str],
    *,
    exclude_names: Iterable[str] = (),
    rescue_map: Mapping[str, str] | None = None,
    unavailable_paths: Iterable[str] = (),
    metadata_reader: MetadataReader | None = None,
) -> dict[str, object]:
    """Build a deterministic manifest containing metadata, never file bytes."""

    resolved = _local_root(root)
    exclusions = {_relative_path(name) for name in exclude_names}
    entries, exceptions = _walk_inventory(
        resolved,
        exclude_names=exclusions,
        metadata_reader=metadata_reader or (lambda path: path.lstat()),
    )
    rescue_names = _validate_rescue_map(rescue_map)
    known_exception_paths = {str(item["path"]) for item in exceptions}
    for value in sorted({_relative_path(path) for path in unavailable_paths}, key=os.fsencode):
        if value not in known_exception_paths:
            exceptions.append(
                {"path": value, "reason": "unavailable", "recoverable": False}
            )
    exceptions.sort(key=lambda item: os.fsencode(str(item["path"])))

    files = [item for item in entries if item["type"] == "file"]
    directories = [item for item in entries if item["type"] == "directory"]
    return {
        "schema_version": 1,
        "entries": entries,
        "exceptions": exceptions,
        "rescue_name_map": rescue_names,
        "summary": {
            "files": len(files),
            "directories": len(directories),
            "bytes": sum(int(item["size"]) for item in files),
            "exceptions": len(exceptions),
        },
    }


def _sha256_file(path: Path) -> str:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("checksums are supported only for regular files")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _contained_file(root: Path, relative_path: str) -> Path:
    normalized = _relative_path(relative_path)
    candidate = root.joinpath(*PurePosixPath(normalized).parts)
    parent = candidate.parent.resolve(strict=True)
    try:
        parent.relative_to(root)
    except ValueError as error:
        raise ValueError("checksum path escapes root") from error
    return candidate


def write_checksums(
    root: str | os.PathLike[str],
    entries: Iterable[Mapping[str, object]],
    output_path: str | os.PathLike[str],
) -> Path:
    """Atomically write sorted SHA-256 records for selected regular files."""

    resolved = _local_root(root)
    selected: dict[str, Path] = {}
    for entry in entries:
        if "path" not in entry:
            raise ValueError("checksum entry lacks path")
        relative = _relative_path(str(entry["path"]))
        if "\n" in relative or "\r" in relative:
            raise ValueError("checksum paths cannot contain line separators")
        candidate = _contained_file(resolved, relative)
        if entry.get("type") not in (None, "file"):
            continue
        if relative in selected:
            raise ValueError("duplicate checksum path")
        selected[relative] = candidate

    lines = [
        f"{_sha256_file(selected[relative])}  {relative}\n"
        for relative in sorted(selected, key=os.fsencode)
    ]
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.writelines(lines)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _read_checksum_file(path: Path) -> tuple[dict[str, str], list[int]]:
    expected: dict[str, str] = {}
    invalid: list[int] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if len(raw) < 67 or raw[64:66] != "  ":
            invalid.append(line_number)
            continue
        digest, relative_raw = raw[:64], raw[66:]
        try:
            relative = _relative_path(relative_raw)
        except ValueError:
            invalid.append(line_number)
            continue
        if (
            len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or relative in expected
        ):
            invalid.append(line_number)
            continue
        expected[relative] = digest
    return expected, invalid


def verify_checksums(
    root: str | os.PathLike[str], checksums_path: str | os.PathLike[str]
) -> dict[str, object]:
    """Compare a checksum set with the complete regular-file inventory."""

    resolved = _local_root(root)
    checksum_file = Path(checksums_path)
    expected, invalid = _read_checksum_file(checksum_file)
    inventory = walk_safe(resolved)
    actual_paths = {
        str(entry["path"])
        for entry in inventory
        if entry["type"] == "file"
    }
    try:
        checksum_relative = checksum_file.resolve(strict=True).relative_to(resolved).as_posix()
    except ValueError:
        checksum_relative = None
    if checksum_relative is not None:
        actual_paths.discard(checksum_relative)

    missing = sorted(set(expected) - actual_paths, key=os.fsencode)
    extra = sorted(actual_paths - set(expected), key=os.fsencode)
    mismatched: list[str] = []
    for relative in sorted(set(expected) & actual_paths, key=os.fsencode):
        try:
            observed = _sha256_file(_contained_file(resolved, relative))
        except (OSError, ValueError):
            mismatched.append(relative)
            continue
        if observed != expected[relative]:
            mismatched.append(relative)
    return {
        "ok": not (missing or extra or mismatched or invalid),
        "missing": missing,
        "extra": extra,
        "mismatched": mismatched,
        "invalid_lines": invalid,
    }
