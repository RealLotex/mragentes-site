from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any

SOURCE_HOME = Path("/home/openclaw")
FORBIDDEN_COMMANDS = {"sudo", "su", "runuser", "crontab", "systemctl", "loginctl", "wrangler"}


def resolved_path(value: os.PathLike[str] | str) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def assert_not_source_path(value: os.PathLike[str] | str) -> Path:
    path = resolved_path(value)
    if path == SOURCE_HOME or is_within(path, SOURCE_HOME):
        raise PermissionError("[SRC-IMM-001] access to the frozen source user is forbidden")
    return path


def command_tokens(command: Any) -> list[str]:
    if isinstance(command, (str, bytes)):
        text = command.decode() if isinstance(command, bytes) else command
        return shlex.split(text)
    return [os.fsdecode(part) for part in command]


def assert_command_allowed(command: Any, cwd: Path, writable_root: Path) -> list[str]:
    tokens = command_tokens(command)
    if not tokens:
        raise PermissionError("[SRC-IMM-002] empty subprocess command is forbidden")
    executable = Path(tokens[0]).name
    if executable in FORBIDDEN_COMMANDS or any("/home/openclaw" in token for token in tokens):
        raise PermissionError("[SRC-IMM-002] forbidden source/account command")
    if executable == "git" and "push" in tokens and not is_within(cwd, writable_root):
        raise PermissionError("[GIT-CANON-006] remote git push is forbidden in tests")
    return tokens
