from __future__ import annotations

import os

import pytest

from tests.support.contracts import trace_message
from tests.support.git_tree import assert_all_components_fit, git_bytes, tree_paths


ECRYPTFS_COMPONENT_LIMIT = 143


@pytest.mark.trace("PORT-PATH-001")
@pytest.mark.red_expected
def test_every_head_tree_component_fits_the_target_ecryptfs_limit() -> None:
    assert_all_components_fit(tree_paths(), ECRYPTFS_COMPONENT_LIMIT, "PORT-PATH-001")


@pytest.mark.trace("PORT-CHECKOUT-001")
@pytest.mark.red_expected
def test_checkout_has_no_tracked_paths_missing_from_worktree() -> None:
    deleted = [
        os.fsdecode(item)
        for item in git_bytes("ls-files", "--deleted", "-z").split(b"\0")
        if item
    ]
    assert not deleted, trace_message(
        "PORT-CHECKOUT-001", f"tracked paths cannot be materialized: {deleted}"
    )
