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
def test_cloudflare_account_connector_is_ready_without_persisted_credentials() -> None:
    item = snapshot()["cloudflare_account_mcp"]
    assert item == {
        "status": "ready",
        "transport": "official_cloudflare_api_mcp",
        "authentication": "oauth",
        "verified_capabilities": ["search", "execute"],
        "credential_storage": "provider_managed",
    }


@pytest.mark.trace("PROJECT-MR-001")
@pytest.mark.external_blocked
def test_mr_agentes_project_is_registered_for_local_native_automation() -> None:
    item = snapshot()["codex_project_mr_agentes"]
    assert item == {
        "status": "ready",
        "project": "MR Agentes",
        "execution_environment": "local",
        "repository": "RealLotex/mragentes-site",
    }


@pytest.mark.trace("GIT-AUTH-001")
@pytest.mark.external_blocked
def test_git_remote_write_uses_github_connector_without_local_credentials() -> None:
    item = snapshot()["git_remote_write"]
    assert item == {
        "status": "ready",
        "transport": "github_connector",
        "contract": ".automation/github/connector-egress.json",
        "local_credentials": "absent_by_design",
        "local_push": False,
    }


@pytest.mark.trace("TASK-EXTERNAL-001")
@pytest.mark.external_blocked
def test_four_native_automations_are_active_once_each() -> None:
    item = snapshot()["scheduled_tasks"]
    assert item == {
        "status": "ready",
        "authority": "codex_native_automations",
        "execution_environment": "local",
        "registered_count": 4,
        "active_count": 4,
        "duplicate_count": 0,
    }
