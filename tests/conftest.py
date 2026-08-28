from __future__ import annotations

import builtins
import io
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.support.safety import (
    SOURCE_HOME,
    assert_command_allowed,
    assert_not_source_path,
    is_within,
)


def _mode_writes(mode: str) -> bool:
    return any(flag in mode for flag in ("w", "a", "x", "+"))


@pytest.fixture(autouse=True)
def isolated_test_process(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    sandbox_home = tmp_path / "home"
    sandbox_config = tmp_path / "xdg-config"
    sandbox_cache = tmp_path / "xdg-cache"
    sandbox_home.mkdir()
    sandbox_config.mkdir()
    sandbox_cache.mkdir()

    monkeypatch.setenv("HOME", str(sandbox_home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(sandbox_config))
    monkeypatch.setenv("XDG_CACHE_HOME", str(sandbox_cache))
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.delenv("META_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    sys.dont_write_bytecode = True

    real_builtin_open = builtins.open
    real_io_open = io.open
    real_popen = subprocess.Popen

    def checked_file(file: Any, mode: str) -> None:
        if isinstance(file, int):
            return
        path = assert_not_source_path(os.fsdecode(file))
        if _mode_writes(mode) and not is_within(path, tmp_path):
            raise PermissionError(f"[SRC-IMM-003] test write outside tmp root: {path}")

    def guarded_builtin_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any):
        checked_file(file, mode)
        return real_builtin_open(file, mode, *args, **kwargs)

    def guarded_io_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any):
        checked_file(file, mode)
        return real_io_open(file, mode, *args, **kwargs)

    def guarded_popen(args: Any, *popen_args: Any, **kwargs: Any):
        cwd = Path(kwargs.get("cwd") or os.getcwd()).resolve(strict=False)
        assert_not_source_path(cwd)
        assert_command_allowed(args, cwd, tmp_path)
        return real_popen(args, *popen_args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_builtin_open)
    monkeypatch.setattr(io, "open", guarded_io_open)
    monkeypatch.setattr(subprocess, "Popen", guarded_popen)

    yield

    assert SOURCE_HOME != sandbox_home


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        trace_markers = list(item.iter_markers(name="trace"))
        if len(trace_markers) != 1 or len(trace_markers[0].args) != 1:
            raise pytest.UsageError(f"untraced or multiply traced test: {item.nodeid}")
        state_count = sum(
            bool(list(item.iter_markers(name=name)))
            for name in ("baseline_green", "red_expected", "external_blocked")
        )
        if state_count != 1:
            raise pytest.UsageError(f"test must declare exactly one initial state: {item.nodeid}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item: pytest.Item):
    outcome = yield
    excinfo = outcome.excinfo
    if not excinfo or not issubclass(excinfo[0], (Exception, pytest.fail.Exception)):
        return
    marker = item.get_closest_marker("trace")
    if not marker or not marker.args:
        return
    trace_id = str(marker.args[0])
    message = str(excinfo[1]) or excinfo[0].__name__
    if not message.startswith(f"[{trace_id}]"):
        outcome.force_exception(AssertionError(f"[{trace_id}] {message}"))
