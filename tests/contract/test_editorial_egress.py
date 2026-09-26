from __future__ import annotations

import json

import pytest

from tests.support.contracts import require_target


@pytest.mark.trace("GITHUB-EGRESS-001")
@pytest.mark.red_expected
def test_one_cli_contract_limits_editorial_git_delivery() -> None:
    contract = json.loads(
        require_target(".automation/github/editorial-egress.json", "GITHUB-EGRESS-001").read_text(
            encoding="utf-8"
        )
    )
    assert contract["provider"] == "gh_cli"
    assert contract["owner"] == "scripts/automation/editorial_release.py"
    assert contract["repository"] == "RealLotex/mragentes-site"
    assert contract["base_branch"] == "main"
    assert contract["branch_template"] == "automation/editorial/{date}"
    assert contract["workspace"] == {
        "mode": "temporary_worktree",
        "root": "/var/tmp",  # noqa: S108 - fixed system temporary directory contract
        "base_ref": "origin/main",
    }
    assert contract["authentication"]["method"] == "gh_os_keyring"
    assert contract["authentication"]["repository_secrets"] is False
    assert contract["delivery"]["paths"] == 6
    assert contract["delivery"]["commits"] == 1
    assert contract["delivery"]["force_push"] is False
    assert contract["on_ambiguous_remote_state"] == "needs_review"
