from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.contracts import trace_message
from tests.support.safety import (
    assert_command_allowed,
    assert_not_source_path,
    is_within,
    resolved_path,
)


@pytest.mark.trace("SRC-IMM-001")
@pytest.mark.baseline_green
def test_source_home_literal_is_rejected_before_io(tmp_path: Path) -> None:
    with pytest.raises(PermissionError, match=r"^\[SRC-IMM-001\]"):
        assert_not_source_path("/home/openclaw")
    safe = assert_not_source_path(tmp_path)
    assert safe == tmp_path.resolve(), trace_message("SRC-IMM-001", "tmp root was rejected")


@pytest.mark.trace("SRC-IMM-002")
@pytest.mark.baseline_green
def test_source_home_descendant_and_normalized_traversal_are_rejected(tmp_path: Path) -> None:
    candidates = (
        "/home/openclaw/.openclaw/workspace",
        "/home/marcos/../openclaw/.config",
        Path("/home") / "openclaw" / ".." / "openclaw" / "state.db",
    )
    for candidate in candidates:
        with pytest.raises(PermissionError, match=r"^\[SRC-IMM-001\]"):
            assert_not_source_path(candidate)
    assert not is_within(tmp_path.resolve(), Path("/home/openclaw")), trace_message(
        "SRC-IMM-002", "temporary test root resolves under the frozen source"
    )


@pytest.mark.trace("SRC-IMM-003")
@pytest.mark.baseline_green
def test_symlink_resolving_to_source_home_is_rejected_without_dereferencing_data(
    tmp_path: Path,
) -> None:
    link = tmp_path / "frozen-source"
    link.symlink_to("/home/openclaw", target_is_directory=True)
    with pytest.raises(PermissionError, match=r"^\[SRC-IMM-001\]"):
        assert_not_source_path(link / "workspace")


@pytest.mark.trace("SRC-IMM-004")
@pytest.mark.baseline_green
def test_commands_addressing_source_account_or_home_are_rejected(tmp_path: Path) -> None:
    commands = (
        ["git", "-C", "/home/openclaw/project", "status"],
        ["python3", "/home/openclaw/job.py"],
        "bash -lc 'test -d /home/openclaw'",
    )
    for command in commands:
        with pytest.raises(PermissionError, match=r"^\[SRC-IMM-002\]"):
            assert_command_allowed(command, tmp_path, tmp_path)


@pytest.mark.trace("SRC-IMM-005")
@pytest.mark.baseline_green
def test_account_and_scheduler_management_commands_are_rejected(tmp_path: Path) -> None:
    commands = (
        ["sudo", "-u", "openclaw", "true"],
        ["su", "openclaw"],
        ["runuser", "-u", "openclaw", "--", "id"],
        ["crontab", "-u", "openclaw", "-l"],
        ["systemctl", "--user", "status"],
        ["wrangler", "deploy"],
    )
    for command in commands:
        with pytest.raises(PermissionError, match=r"^\[SRC-IMM-002\]"):
            assert_command_allowed(command, tmp_path, tmp_path)


@pytest.mark.trace("SRC-IMM-006")
@pytest.mark.baseline_green
def test_safe_read_only_git_commands_in_temporary_repo_are_allowed(tmp_path: Path) -> None:
    tokens = assert_command_allowed(["git", "status", "--porcelain"], tmp_path, tmp_path)
    assert tokens == ["git", "status", "--porcelain"], trace_message(
        "SRC-IMM-006", "safe temporary git command was rewritten"
    )


@pytest.mark.trace("SRC-IMM-007")
@pytest.mark.baseline_green
def test_git_push_outside_temporary_root_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / "not-writable-by-test"
    with pytest.raises(PermissionError, match=r"^\[GIT-CANON-006\]"):
        assert_command_allowed(["git", "push", "origin", "main"], outside, tmp_path)


@pytest.mark.trace("SRC-IMM-008")
@pytest.mark.baseline_green
def test_local_preserved_archive_path_is_not_confused_with_source_account() -> None:
    archive = resolved_path(
        "/home/marcos/Documents/ChatGPT/OpenClaw/archive/openclaw-home"
    )
    accepted = assert_not_source_path(archive)
    assert accepted == archive, trace_message(
        "SRC-IMM-008", "local preserved archive was mistaken for the frozen account"
    )
