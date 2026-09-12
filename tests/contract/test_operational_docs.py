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


@pytest.mark.trace("DOCS-OPS-002")
@pytest.mark.red_expected
def test_operations_does_not_pin_a_stale_cloudflare_worker_version() -> None:
    source = require_target("OPERATIONS.md", "DOCS-OPS-002").read_text(encoding="utf-8")
    assert "versión activa 42" not in source, trace_message(
        "DOCS-OPS-002", "operations pins a stale Cloudflare version instead of requiring an API audit"
    )
    assert "versión activa informada por Cloudflare" in source, trace_message(
        "DOCS-OPS-002", "operations does not require the active version reported by Cloudflare"
    )


@pytest.mark.trace("DOCS-KISS-001")
@pytest.mark.red_expected
def test_docs_describe_the_single_editorial_authority_and_inline_effects() -> None:
    architecture = require_target("ARCHITECTURE.md", "DOCS-KISS-001").read_text(encoding="utf-8")
    operations = require_target("OPERATIONS.md", "DOCS-KISS-001").read_text(encoding="utf-8")
    combined = architecture + "\n" + operations
    for term in (
        "una sola automatización",
        "mragentes-editorial-publisher",
        "conversación nueva",
        "worktree",
        "publish_meta",
        "notify_push",
        "una publicación en Facebook",
        "una publicación en Instagram",
    ):
        assert term.casefold() in combined.casefold(), trace_message(
            "DOCS-KISS-001", f"documentation lacks {term!r}"
        )
    for obsolete in ("social-daily.yml", "social-note.yml", "notify-note.yml"):
        assert obsolete not in combined, trace_message(
            "DOCS-KISS-001", f"documentation still routes through {obsolete}"
        )


@pytest.mark.trace("DOCS-META-001")
@pytest.mark.red_expected
def test_operations_explains_meta_testing_as_a_safety_boundary() -> None:
    source = require_target("OPERATIONS.md", "DOCS-META-001").read_text(encoding="utf-8")
    for term in ("meta-testing", "environment de GitHub", "modo testing", "no es producción"):
        assert term.casefold() in source.casefold(), trace_message(
            "DOCS-META-001", f"Meta safety explanation lacks {term!r}"
        )
