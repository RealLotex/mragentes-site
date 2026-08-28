from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import pytest

from tests.support.contracts import trace_message
from tests.support.planned import planned_callable, planned_signature


TARGET = "scripts/archive/encryption.py"


class FakeArchiveRunner:
    def __init__(self, *, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, argv: list[str] | tuple[str, ...], **_: Any) -> object:
        tokens = tuple(map(str, argv))
        self.calls.append(tokens)
        if self.fail_on and any(self.fail_on in token for token in tokens):
            raise RuntimeError(f"synthetic {self.fail_on} failure")
        return type("Completed", (), {"returncode": 0, "stdout": b"", "stderr": b""})()


@pytest.mark.trace("ARCH-AGE-001")
@pytest.mark.red_expected
def test_encryption_module_exposes_key_space_encrypt_verify_and_restore_api() -> None:
    expected = {
        "assert_key_permissions": ("key_path", "archive_root"),
        "assert_space": ("path", "required_bytes"),
        "encrypt_archive": ("source_paths", "output_path", "key_path", "runner"),
        "verify_archive": ("archive_path", "key_path", "runner"),
        "restore_sample": ("archive_path", "key_path", "destination", "member", "runner"),
    }
    for symbol, parameters in expected.items():
        planned_signature(TARGET, symbol, parameters, "ARCH-AGE-001")


@pytest.mark.trace("ARCH-AGE-002")
@pytest.mark.red_expected
def test_key_must_be_regular_owned_0600_and_outside_archive(tmp_path: Path) -> None:
    validate = planned_callable(TARGET, "assert_key_permissions", "ARCH-AGE-002")
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    key = tmp_path / "keys" / "archive.agekey"
    key.parent.mkdir()
    key.write_text("AGE-SECRET-KEY-1SYNTHETIC", encoding="utf-8")
    key.chmod(0o600)
    assert validate(key, archive_root) is None, trace_message(
        "ARCH-AGE-002", "valid 0600 key was rejected"
    )
    key.chmod(0o644)
    with pytest.raises((PermissionError, ValueError)):
        validate(key, archive_root)
    inside = archive_root / "inside.agekey"
    inside.write_text("synthetic", encoding="utf-8")
    inside.chmod(0o600)
    with pytest.raises((PermissionError, ValueError)):
        validate(inside, archive_root)


@pytest.mark.trace("ARCH-AGE-003")
@pytest.mark.red_expected
def test_space_gate_handles_exact_limit_insufficient_and_filesystem_error(tmp_path: Path) -> None:
    assert_space = planned_callable(TARGET, "assert_space", "ARCH-AGE-003")

    class Stat:
        f_bavail = 100
        f_frsize = 4096

    assert assert_space(tmp_path, 409_600, statvfs=lambda _: Stat()) is None, trace_message(
        "ARCH-AGE-003", "exact free-space boundary was rejected"
    )
    with pytest.raises(OSError):
        assert_space(tmp_path, 409_601, statvfs=lambda _: Stat())

    def broken(_: Path) -> object:
        raise OSError("synthetic statvfs failure")

    with pytest.raises(OSError, match="statvfs"):
        assert_space(tmp_path, 1, statvfs=broken)


@pytest.mark.trace("ARCH-AGE-004")
@pytest.mark.red_expected
def test_encrypt_pipeline_uses_argv_no_shell_no_key_material_and_no_overwrite(tmp_path: Path) -> None:
    encrypt = planned_callable(TARGET, "encrypt_archive", "ARCH-AGE-004")
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.txt").write_text("fixture", encoding="utf-8")
    key = tmp_path / "archive.agekey"
    key.write_text("AGE-SECRET-KEY-1SYNTHETIC", encoding="utf-8")
    key.chmod(0o600)
    output = tmp_path / "snapshot.tar.zst.age"
    runner = FakeArchiveRunner()
    returned = encrypt([source], output, key, runner=runner, temp_dir=tmp_path / "work")
    assert Path(returned) == output, trace_message("ARCH-AGE-004", "wrong archive destination")
    flattened = "\n".join(" ".join(call) for call in runner.calls)
    assert "AGE-SECRET-KEY-1SYNTHETIC" not in flattened, trace_message(
        "ARCH-AGE-004", "private key material entered command arguments"
    )
    assert all("shell=True" not in call for call in runner.calls), trace_message(
        "ARCH-AGE-004", "archive pipeline used a shell"
    )
    output.write_bytes(b"already exists")
    with pytest.raises(FileExistsError):
        encrypt([source], output, key, runner=runner, temp_dir=tmp_path / "work-2")


@pytest.mark.trace("ARCH-AGE-005")
@pytest.mark.red_expected
def test_verify_archive_classifies_wrong_key_truncation_and_checksum_mismatch(tmp_path: Path) -> None:
    verify = planned_callable(TARGET, "verify_archive", "ARCH-AGE-005")
    archive = tmp_path / "snapshot.tar.zst.age"
    archive.write_bytes(b"synthetic-ciphertext")
    key = tmp_path / "archive.agekey"
    key.write_text("AGE-SECRET-KEY-1SYNTHETIC", encoding="utf-8")
    key.chmod(0o600)
    expected = hashlib.sha256(archive.read_bytes()).hexdigest()
    report = verify(archive, key, runner=FakeArchiveRunner(), expected_checksum=expected)
    assert report["ok"] is True, trace_message("ARCH-AGE-005", "valid fixture was rejected")
    mismatch = verify(archive, key, runner=FakeArchiveRunner(), expected_checksum="0" * 64)
    assert mismatch["ok"] is False and mismatch["reason"] == "checksum_mismatch", trace_message(
        "ARCH-AGE-005", "checksum mismatch was not classified"
    )
    wrong_key = verify(archive, tmp_path / "missing.agekey", runner=FakeArchiveRunner())
    assert wrong_key["ok"] is False and wrong_key["reason"] == "key_unavailable", trace_message(
        "ARCH-AGE-005", "missing key was not classified safely"
    )


@pytest.mark.trace("ARCH-AGE-006")
@pytest.mark.red_expected
def test_restore_sample_is_confined_deterministic_and_blocks_traversal(tmp_path: Path) -> None:
    restore = planned_callable(TARGET, "restore_sample", "ARCH-AGE-006")
    archive = tmp_path / "snapshot.tar.zst.age"
    archive.write_bytes(b"synthetic-ciphertext")
    key = tmp_path / "archive.agekey"
    key.write_text("AGE-SECRET-KEY-1SYNTHETIC", encoding="utf-8")
    key.chmod(0o600)
    destination = tmp_path / "restore"
    runner = FakeArchiveRunner()
    restored = restore(
        archive,
        key,
        destination,
        member="workspace/README.md",
        runner=runner,
    )
    restored_path = Path(restored).resolve(strict=False)
    assert os.path.commonpath([restored_path, destination.resolve()]) == str(
        destination.resolve()
    ), trace_message("ARCH-AGE-006", "sample escaped restore directory")
    with pytest.raises(ValueError):
        restore(archive, key, destination, member="../../escape", runner=runner)
