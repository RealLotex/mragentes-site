from __future__ import annotations

import os
import subprocess
from pathlib import Path

from tests.support.contracts import ROOT, trace_message


def git_bytes(*args: str, cwd: Path = ROOT) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )
    return completed.stdout


def tracked_paths(cwd: Path = ROOT) -> list[str]:
    return [
        os.fsdecode(item)
        for item in git_bytes("ls-files", "-z", cwd=cwd).split(b"\0")
        if item
    ]


def tree_paths(cwd: Path = ROOT, revision: str = "HEAD") -> list[str]:
    return [
        os.fsdecode(item)
        for item in git_bytes("ls-tree", "-rz", "--name-only", revision, cwd=cwd).split(b"\0")
        if item
    ]


def component_overruns(paths: list[str], limit: int) -> list[tuple[str, str, int]]:
    return [
        (path, component, len(component.encode("utf-8")))
        for path in paths
        for component in Path(path).parts
        if len(component.encode("utf-8")) > limit
    ]


def assert_all_components_fit(paths: list[str], limit: int, trace_id: str) -> None:
    offenders = component_overruns(paths, limit)
    assert not offenders, trace_message(
        trace_id, f"tracked component exceeds {limit} bytes: {offenders}"
    )
