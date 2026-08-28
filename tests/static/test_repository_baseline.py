from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.support.contracts import ROOT, trace_message
from tests.support.git_tree import tracked_paths


def git_text(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.mark.trace("GIT-CANON-001")
@pytest.mark.baseline_green
def test_remote_is_clean_canonical_https_url() -> None:
    remote = git_text("remote", "get-url", "origin")
    assert remote.removesuffix(".git") == "https://github.com/RealLotex/mragentes-site"


@pytest.mark.trace("GIT-CANON-002")
@pytest.mark.baseline_green
def test_changes_use_an_expected_repository_branch() -> None:
    branch = (
        os.environ.get("GITHUB_HEAD_REF")
        or os.environ.get("GITHUB_REF_NAME")
        or git_text("branch", "--show-current")
    )
    assert branch == "main" or branch.startswith(("codex/", "automation/")), trace_message(
        "GIT-CANON-002", f"unexpected working branch: {branch}"
    )


@pytest.mark.trace("GIT-CANON-003")
@pytest.mark.baseline_green
def test_clone_started_from_audited_head() -> None:
    baseline = "d2b6b8fd90afd4ac01dd3a525e1d7455a43b9851"
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", baseline, "HEAD"],
        cwd=ROOT,
        check=False,
    )
    assert result.returncode == 0, trace_message(
        "GIT-CANON-003", "audited RED baseline is no longer an ancestor of HEAD"
    )


@pytest.mark.trace("PORT-CHECKOUT-001")
@pytest.mark.red_expected
def test_every_index_path_is_materialized() -> None:
    missing = [path for path in tracked_paths() if not os.path.lexists(ROOT / path)]
    assert not missing, trace_message(
        "PORT-CHECKOUT-001", f"tracked paths are not materialized: {missing}"
    )


@pytest.mark.trace("DISK-SPACE-001")
@pytest.mark.baseline_green
def test_workspace_has_minimum_free_space() -> None:
    stats = os.statvfs(ROOT)
    free = stats.f_bavail * stats.f_frsize
    minimum = 15 * 1024**3
    assert free >= minimum, trace_message(
        "DISK-SPACE-001", f"free space below 15 GiB: {free}"
    )


@pytest.mark.trace("GIT-CANON-004")
@pytest.mark.baseline_green
def test_index_exists_and_is_nonempty() -> None:
    index = ROOT / ".git" / "index"
    assert index.is_file() and index.stat().st_size > 0
