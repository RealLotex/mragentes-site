from __future__ import annotations

import pytest

from tests.support.contracts import require_target, trace_message


@pytest.mark.trace("DOCS-ARCH-001")
@pytest.mark.red_expected
def test_architecture_documents_connector_egress_and_trusted_intake() -> None:
    source = require_target("ARCHITECTURE.md", "DOCS-ARCH-001").read_text(encoding="utf-8")
    required = (
        ".automation/github/connector-egress.json",
        "create_blob",
        "create_tree",
        "create_commit",
        "update_ref",
        "automation-intake.yml",
        "workflow_run",
        "match-head-commit",
        "no usa git push local",
    )
    assert all(term in source for term in required), trace_message(
        "DOCS-ARCH-001", "architecture does not describe the authenticated atomic egress"
    )


@pytest.mark.trace("DOCS-OPS-001")
@pytest.mark.red_expected
def test_operations_documents_meta_preflight_and_legacy_push_continuity() -> None:
    source = require_target("OPERATIONS.md", "DOCS-OPS-001").read_text(encoding="utf-8")
    required = (
        "meta-preflight.yml",
        "scripts.social.meta_preflight",
        "GET-only",
        "v26.0",
        "legacy",
        "sub:v1",
        "https://",
        "8 suscripciones",
    )
    assert all(term in source for term in required), trace_message(
        "DOCS-OPS-001", "operations do not document provider preflight and legacy KV continuity"
    )
