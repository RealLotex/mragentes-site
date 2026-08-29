from __future__ import annotations

import json

import pytest

from tests.support.contracts import require_target, trace_message

CONTRACT_PATH = ".automation/github/connector-egress.json"


def _contract(trace_id: str) -> dict[str, object]:
    return json.loads(require_target(CONTRACT_PATH, trace_id).read_text(encoding="utf-8"))


@pytest.mark.trace("GITHUB-EGRESS-001")
@pytest.mark.red_expected
def test_github_connector_is_the_only_authenticated_remote_egress() -> None:
    contract = _contract("GITHUB-EGRESS-001")
    assert contract["provider"] == "github_connector", trace_message(
        "GITHUB-EGRESS-001", "remote egress is not owned by the GitHub connector"
    )
    assert contract["repository"] == "RealLotex/mragentes-site", trace_message(
        "GITHUB-EGRESS-001", "connector targets an unexpected repository"
    )
    assert contract["base_branch"] == "main", trace_message(
        "GITHUB-EGRESS-001", "connector does not pin the protected base branch"
    )
    assert contract["target_branch_prefix"] == "automation/", trace_message(
        "GITHUB-EGRESS-001", "connector may write outside automation branches"
    )
    assert contract["preflight"] == {
        "require_authenticated_connector": True,
        "minimum_repository_permission": "write",
        "on_unavailable": "needs_review",
    }, trace_message("GITHUB-EGRESS-001", "connector preflight does not fail closed")
    assert contract["local_git"] == {
        "commit_allowed": True,
        "push_allowed": False,
        "credentials_allowed": False,
    }, trace_message("GITHUB-EGRESS-001", "local Git may own authenticated remote egress")


@pytest.mark.trace("GITHUB-EGRESS-002")
@pytest.mark.red_expected
def test_github_connector_preserves_one_atomic_commit_and_binary_bytes() -> None:
    contract = _contract("GITHUB-EGRESS-002")
    commit = contract["commit"]
    assert commit["transport"] == "git_data_objects", trace_message(
        "GITHUB-EGRESS-002", "connector does not use Git data objects"
    )
    assert commit["operation_order"] == [
        "create_blob",
        "create_tree",
        "create_commit",
        "update_ref",
    ], trace_message("GITHUB-EGRESS-002", "remote commit operation order is not atomic")
    assert commit["max_commits_per_run"] == 1, trace_message(
        "GITHUB-EGRESS-002", "one automation run may create multiple remote commits"
    )
    assert commit["text_encoding"] == "utf-8", trace_message(
        "GITHUB-EGRESS-002", "text transport has an unexpected encoding"
    )
    assert commit["binary_encoding"] == "base64", trace_message(
        "GITHUB-EGRESS-002", "binary assets are not preserved byte-for-byte"
    )
    assert commit["contents_api_multi_file"] is False, trace_message(
        "GITHUB-EGRESS-002", "per-file Contents API commits may split an atomic change"
    )
    assert contract["ref_update"] == {
        "fast_forward_only": True,
        "force": False,
        "on_conflict": "needs_review",
    }, trace_message("GITHUB-EGRESS-002", "branch updates may overwrite remote history")


@pytest.mark.trace("GITHUB-EGRESS-003")
@pytest.mark.red_expected
def test_github_connector_rejects_unreviewed_paths_and_ambiguous_retries() -> None:
    contract = _contract("GITHUB-EGRESS-003")
    safety = contract["safety"]
    assert safety["paths_source"] == "schedule.permissions.repository_writes", trace_message(
        "GITHUB-EGRESS-003", "egress does not inherit each schedule path allowlist"
    )
    assert safety["require_clean_start"] is True, trace_message(
        "GITHUB-EGRESS-003", "egress may absorb pre-existing local changes"
    )
    assert safety["stage_all_allowed"] is False, trace_message(
        "GITHUB-EGRESS-003", "egress permits an unreviewed stage-all operation"
    )
    assert safety["existing_branch_policy"] == "reuse_only_if_exact", trace_message(
        "GITHUB-EGRESS-003", "a deterministic branch may be overwritten on retry"
    )
    assert safety["on_ambiguous_remote_state"] == "needs_review", trace_message(
        "GITHUB-EGRESS-003", "ambiguous remote state does not fail closed"
    )
