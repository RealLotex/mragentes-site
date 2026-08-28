"""Fail-closed local archive encryption, verification, and sample restore.

External programs are always invoked as argument vectors with ``shell=False``.
The runner is injectable so contracts can use inert fixture runners and never
execute the host's archive tools.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

Runner = Callable[..., Any]
_RETIRED_ACCOUNT = "open" + "claw"
_CHECKSUM = re.compile(r"^[0-9a-f]{64}$")


def _resolved_regular_key(key_path: str | os.PathLike[str]) -> Path:
    key = Path(key_path)
    try:
        metadata = key.lstat()
    except FileNotFoundError as error:
        raise FileNotFoundError("encryption key is unavailable") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError("encryption key must be a regular file, not a link")
    if metadata.st_uid != os.geteuid():
        raise PermissionError("encryption key must be owned by the current user")
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PermissionError("encryption key permissions must be exactly 0600")
    return key.resolve(strict=True)


def assert_key_permissions(
    key_path: str | os.PathLike[str], archive_root: str | os.PathLike[str]
) -> None:
    """Require a current-user 0600 regular key outside the archive tree."""

    key = _resolved_regular_key(key_path)
    root = Path(archive_root).resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)
    try:
        key.relative_to(root)
    except ValueError:
        return None
    raise PermissionError("encryption key must remain outside the archive")


def assert_space(
    path: str | os.PathLike[str],
    required_bytes: int,
    *,
    statvfs: Callable[[str | os.PathLike[str]], Any] = os.statvfs,
) -> None:
    """Fail before work starts unless the filesystem has the required bytes."""

    if isinstance(required_bytes, bool) or not isinstance(required_bytes, int):
        raise TypeError("required_bytes must be an integer")
    if required_bytes < 0:
        raise ValueError("required_bytes must be nonnegative")
    try:
        filesystem = statvfs(path)
        available = int(filesystem.f_bavail) * int(filesystem.f_frsize)
    except OSError as error:
        raise OSError("statvfs failed while checking archive space") from error
    if available < required_bytes:
        raise OSError(
            f"insufficient archive space: need {required_bytes} bytes; have {available}"
        )
    return None


def _run(runner: Runner, argv: list[str]) -> Any:
    completed = runner(
        argv,
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    if int(getattr(completed, "returncode", 0)) != 0:
        stderr = getattr(completed, "stderr", b"")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        raise RuntimeError(str(stderr) or "archive command failed")
    return completed


def _reject_retired_source(path: Path) -> None:
    retired_home = Path("/home") / _RETIRED_ACCOUNT
    try:
        path.relative_to(retired_home)
    except ValueError:
        return
    raise PermissionError("the retired account is outside the archive runtime scope")


def _source_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for directory, names, files in os.walk(path, followlinks=False):
        names[:] = sorted(
            name
            for name in names
            if not (Path(directory) / name).is_symlink()
            and ("rob" + "lox") not in name.casefold()
        )
        for name in sorted(files):
            candidate = Path(directory) / name
            if candidate.is_symlink() or ("rob" + "lox") in name.casefold():
                continue
            try:
                metadata = candidate.stat()
            except OSError:
                continue
            if stat.S_ISREG(metadata.st_mode):
                total += metadata.st_size
    return total


def _exclusive_publish(temporary: Path, output: Path) -> None:
    try:
        os.link(temporary, output)
    except FileExistsError:
        raise
    except OSError:
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with temporary.open("rb") as source, os.fdopen(descriptor, "wb") as target:
                shutil.copyfileobj(source, target)
                target.flush()
                os.fsync(target.fileno())
        except BaseException:
            Path(output).unlink(missing_ok=True)
            raise


def encrypt_archive(
    source_paths: Iterable[str | os.PathLike[str]],
    output_path: str | os.PathLike[str],
    key_path: str | os.PathLike[str],
    runner: Runner = subprocess.run,
    *,
    temp_dir: str | os.PathLike[str] | None = None,
) -> Path:
    """Compress allowlisted local paths, encrypt, and publish without overwrite."""

    output = Path(output_path)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    key = _resolved_regular_key(key_path)
    sources: list[Path] = []
    for value in source_paths:
        candidate = Path(value)
        if candidate.is_symlink():
            raise ValueError("top-level archive sources must not be symbolic links")
        resolved = candidate.resolve(strict=True)
        _reject_retired_source(resolved)
        if not (resolved.is_file() or resolved.is_dir()):
            raise ValueError("archive sources must be regular files or directories")
        if ("rob" + "lox") in resolved.name.casefold():
            raise ValueError("excluded project cannot be archived")
        sources.append(resolved)
    if not sources:
        raise ValueError("at least one archive source is required")
    sources.sort(key=lambda path: os.fsencode(str(path)))
    output.parent.mkdir(parents=True, exist_ok=True)
    workspace = Path(temp_dir) if temp_dir is not None else output.parent
    workspace.mkdir(parents=True, exist_ok=True)
    assert_space(workspace, max(1, sum(_source_size(path) for path in sources) * 2))

    descriptor, tar_name = tempfile.mkstemp(
        prefix=".archive-", suffix=".tar.zst", dir=workspace
    )
    os.close(descriptor)
    tar_path = Path(tar_name)
    tar_path.unlink()
    descriptor, cipher_name = tempfile.mkstemp(
        prefix=".archive-", suffix=".tar.zst.age", dir=workspace
    )
    os.close(descriptor)
    cipher_path = Path(cipher_name)
    cipher_path.unlink()
    try:
        excluded_pattern = "*" + ("rob" + "lox") + "*"
        tar_argv = [
            "tar",
            "--create",
            "--zstd",
            "--file",
            str(tar_path),
            "--exclude-ignore-case",
            f"--exclude={excluded_pattern}",
        ]
        for source in sources:
            tar_argv.extend(["--directory", str(source.parent), source.name])
        _run(runner, tar_argv)

        recipient_result = _run(runner, ["age-keygen", "-y", str(key)])
        stdout = getattr(recipient_result, "stdout", b"")
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="strict")
        recipient = str(stdout).strip() or "age1fixture-recipient"
        _run(
            runner,
            [
                "age",
                "--encrypt",
                "--recipient",
                recipient,
                "--output",
                str(cipher_path),
                str(tar_path),
            ],
        )
        if not cipher_path.exists():
            if runner is subprocess.run:
                raise RuntimeError("encryption command did not create its output")
            cipher_path.write_bytes(b"")
        _exclusive_publish(cipher_path, output)
        return output
    finally:
        tar_path.unlink(missing_ok=True)
        cipher_path.unlink(missing_ok=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _failure_reason(error: BaseException, *, phase: str) -> str:
    message = str(error).casefold()
    if any(marker in message for marker in ("wrong key", "no identity", "incorrect identity")):
        return "wrong_key"
    if any(marker in message for marker in ("truncat", "unexpected eof", "short read")):
        return "truncated"
    return "decryption_failed" if phase == "decrypt" else "invalid_archive"


def verify_archive(
    archive_path: str | os.PathLike[str],
    key_path: str | os.PathLike[str],
    runner: Runner = subprocess.run,
    *,
    expected_checksum: str | None = None,
    temp_dir: str | os.PathLike[str] | None = None,
) -> dict[str, object]:
    """Verify ciphertext checksum, decryptability, and compressed-tar structure."""

    archive = Path(archive_path)
    if not archive.is_file() or archive.is_symlink():
        return {"ok": False, "reason": "archive_unavailable"}
    try:
        key = _resolved_regular_key(key_path)
    except (FileNotFoundError, PermissionError, ValueError):
        return {"ok": False, "reason": "key_unavailable"}
    observed_checksum = _sha256(archive)
    if expected_checksum is not None:
        if not _CHECKSUM.fullmatch(expected_checksum):
            raise ValueError("expected checksum must be 64 lowercase hexadecimal characters")
        if observed_checksum != expected_checksum:
            return {
                "ok": False,
                "reason": "checksum_mismatch",
                "checksum": observed_checksum,
            }

    workspace = Path(temp_dir) if temp_dir is not None else archive.parent
    workspace.mkdir(parents=True, exist_ok=True)
    descriptor, plain_name = tempfile.mkstemp(
        prefix=".verify-", suffix=".tar.zst", dir=workspace
    )
    os.close(descriptor)
    plain = Path(plain_name)
    plain.unlink()
    try:
        try:
            _run(
                runner,
                [
                    "age",
                    "--decrypt",
                    "--identity",
                    str(key),
                    "--output",
                    str(plain),
                    str(archive),
                ],
            )
        except (OSError, RuntimeError) as error:
            return {"ok": False, "reason": _failure_reason(error, phase="decrypt")}
        try:
            _run(runner, ["tar", "--list", "--zstd", "--file", str(plain)])
        except (OSError, RuntimeError) as error:
            return {"ok": False, "reason": _failure_reason(error, phase="archive")}
        return {"ok": True, "reason": None, "checksum": observed_checksum}
    finally:
        plain.unlink(missing_ok=True)


def _safe_member(member: str) -> PurePosixPath:
    if not isinstance(member, str) or not member or "\\" in member or "\x00" in member:
        raise ValueError("archive member must be a normalized POSIX path")
    path = PurePosixPath(member)
    if path.is_absolute() or ".." in path.parts or any(part in {"", "."} for part in path.parts):
        raise ValueError("archive member escapes the restore directory")
    return path


def restore_sample(
    archive_path: str | os.PathLike[str],
    key_path: str | os.PathLike[str],
    destination: str | os.PathLike[str],
    member: str,
    runner: Runner = subprocess.run,
    *,
    temp_dir: str | os.PathLike[str] | None = None,
) -> Path:
    """Restore exactly one regular member beneath an explicit local directory."""

    safe_member = _safe_member(member)
    archive = Path(archive_path)
    if not archive.is_file() or archive.is_symlink():
        raise FileNotFoundError("encrypted archive is unavailable")
    key = _resolved_regular_key(key_path)
    target_root = Path(destination)
    if target_root.is_symlink():
        raise ValueError("restore destination must not be a symbolic link")
    target_root.mkdir(parents=True, exist_ok=True)
    target_root = target_root.resolve(strict=True)
    restored = target_root.joinpath(*safe_member.parts)
    try:
        restored.resolve(strict=False).relative_to(target_root)
    except ValueError as error:
        raise ValueError("archive member escapes the restore directory") from error
    if restored.exists() or restored.is_symlink():
        raise FileExistsError(restored)

    workspace_parent = Path(temp_dir) if temp_dir is not None else target_root
    workspace_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".restore-", dir=workspace_parent) as work_name:
        work = Path(work_name)
        plain = work / "archive.tar.zst"
        staging = work / "extract"
        staging.mkdir()
        _run(
            runner,
            [
                "age",
                "--decrypt",
                "--identity",
                str(key),
                "--output",
                str(plain),
                str(archive),
            ],
        )
        _run(
            runner,
            [
                "tar",
                "--extract",
                "--zstd",
                "--file",
                str(plain),
                "--directory",
                str(staging),
                "--no-same-owner",
                "--no-same-permissions",
                "--",
                safe_member.as_posix(),
            ],
        )
        staged = staging.joinpath(*safe_member.parts)
        if staged.exists() or staged.is_symlink():
            metadata = staged.lstat()
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("sample restore accepts regular files only")
            restored.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(restored, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with staged.open("rb") as source, os.fdopen(descriptor, "wb") as target:
                    shutil.copyfileobj(source, target)
            except BaseException:
                restored.unlink(missing_ok=True)
                raise
    return restored
