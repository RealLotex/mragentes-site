from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from tests.support.contracts import ROOT, trace_message
from tests.support.git_tree import git_bytes, tracked_paths, tree_paths


EXPECTED_REMOTE = "https://github.com/RealLotex/mragentes-site.git"
EXPECTED_BASELINE_HEAD = "d2b6b8fd90afd4ac01dd3a525e1d7455a43b9851"


@pytest.mark.trace("GIT-CANON-001")
@pytest.mark.baseline_green
def test_canonical_remote_is_exact_https_repository_without_credentials() -> None:
    remote = git_bytes("remote", "get-url", "origin").decode().strip()
    parsed = urlsplit(remote)
    assert remote == EXPECTED_REMOTE, trace_message(
        "GIT-CANON-001", f"unexpected canonical remote: {remote}"
    )
    assert parsed.username is None and parsed.password is None, trace_message(
        "GIT-CANON-001", "origin contains userinfo"
    )
    assert not parsed.query and not parsed.fragment, trace_message(
        "GIT-CANON-001", "origin contains query or fragment"
    )


@pytest.mark.trace("GIT-CANON-002")
@pytest.mark.baseline_green
def test_tdd_work_happens_on_dedicated_migration_branch() -> None:
    branch = git_bytes("branch", "--show-current").decode().strip()
    assert branch == "codex/migration-tdd", trace_message(
        "GIT-CANON-002", f"unexpected working branch: {branch}"
    )


@pytest.mark.trace("GIT-CANON-003")
@pytest.mark.baseline_green
def test_git_index_and_baseline_head_are_sane() -> None:
    head = git_bytes("rev-parse", "HEAD").decode().strip()
    assert re.fullmatch(r"[0-9a-f]{40}", head), trace_message(
        "GIT-CANON-003", "HEAD is not a full object id"
    )
    ancestry = git_bytes("merge-base", "--is-ancestor", EXPECTED_BASELINE_HEAD, "HEAD")
    assert ancestry == b"", trace_message(
        "GIT-CANON-003", "audited RED baseline is no longer an ancestor of HEAD"
    )
    assert (ROOT / ".git" / "index").is_file(), trace_message(
        "GIT-CANON-003", "Git index is absent"
    )


@pytest.mark.trace("GIT-CANON-004")
@pytest.mark.baseline_green
def test_repository_has_no_unexpected_submodules() -> None:
    gitmodules = ROOT / ".gitmodules"
    submodule_entries = git_bytes("config", "--file", str(gitmodules), "--get-regexp", "path") \
        if gitmodules.is_file() else b""
    assert not submodule_entries, trace_message(
        "GIT-CANON-004", "unexpected submodule paths are configured"
    )


@pytest.mark.trace("GIT-CANON-005")
@pytest.mark.baseline_green
def test_index_inventory_matches_head_tree_using_nul_protocol() -> None:
    index = sorted(tracked_paths())
    tree = sorted(tree_paths())
    assert index == tree, trace_message(
        "GIT-CANON-005", "index and HEAD inventory differ"
    )


@pytest.mark.trace("GIT-CANON-006")
@pytest.mark.baseline_green
def test_repository_has_no_forced_push_refspec_to_main() -> None:
    entries = git_bytes("config", "--null", "--list").decode().split("\0")
    configured = [
        entry.partition("\n")[2]
        for entry in entries
        if entry.partition("\n")[0] == "remote.origin.push"
    ]
    dangerous = [line for line in configured if line.startswith("+") or line.endswith(":main")]
    assert not dangerous, trace_message(
        "GIT-CANON-006", f"dangerous push refspec configured: {dangerous}"
    )
