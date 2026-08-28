from __future__ import annotations

import json

import pytest

from tests.support.contracts import require_target


def snapshot() -> dict:
    return json.loads(
        require_target(
            ".testplan/external-capabilities.json", "EXTERNAL-SNAPSHOT-001"
        ).read_text(encoding="utf-8")
    )


@pytest.mark.trace("CF-MCP-001")
@pytest.mark.external_blocked
def test_cloudflare_account_connector_block_is_explicit() -> None:
    item = snapshot()["cloudflare_account_mcp"]
    assert item["status"] == "blocked" and "search/execute" in item["reason"]


@pytest.mark.trace("PROJECT-MR-001")
@pytest.mark.external_blocked
def test_mr_agentes_project_registration_block_is_explicit() -> None:
    item = snapshot()["codex_project_mr_agentes"]
    assert item["status"] == "blocked" and "registration" in item["reason"]


@pytest.mark.trace("GIT-AUTH-001")
@pytest.mark.external_blocked
def test_git_remote_write_block_is_explicit_without_importing_old_credentials() -> None:
    item = snapshot()["git_remote_write"]
    assert item["status"] == "blocked" and "credential" in item["reason"].lower()


@pytest.mark.trace("TASK-EXTERNAL-001")
@pytest.mark.external_blocked
def test_scheduled_creation_is_deliberately_blocked_until_green() -> None:
    item = snapshot()["scheduled_tasks"]
    assert item["status"] == "blocked" and "GREEN" in item["reason"]
