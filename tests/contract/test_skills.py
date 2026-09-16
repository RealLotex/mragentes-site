from __future__ import annotations

import re

import pytest

from tests.support.contracts import require_target, trace_message


SKILL = ".agents/skills/mragentes-editorial-publisher/SKILL.md"


@pytest.mark.trace("SKILL-CONTRACT-001")
@pytest.mark.red_expected
def test_editorial_skill_has_native_contract_and_safety_limits() -> None:
    text = require_target(SKILL, "SKILL-CONTRACT-001").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert re.search(r"(?m)^name:\s*mragentes-editorial-publisher\s*$", text)
    for term in ("dry-run", "needs_review", "no usa git push local", "no llama a Meta"):
        assert term.casefold() in text.casefold(), trace_message(
            "SKILL-CONTRACT-001", f"skill lacks safety term: {term}"
        )


@pytest.mark.trace("SKILL-EDITORIAL-002")
@pytest.mark.red_expected
def test_editorial_skill_enforces_one_atomic_news_note_and_social_asset() -> None:
    text = require_target(SKILL, "SKILL-EDITORIAL-002").read_text(encoding="utf-8").casefold()
    for term in (
        "una nota",
        "2 o 3 ítems",
        "un anuncio",
        "facebook",
        "instagram",
        "atómico",
        "blog_guard",
        "hugo",
    ):
        assert term in text, trace_message(
            "SKILL-EDITORIAL-002", f"skill lacks transaction term: {term}"
        )


@pytest.mark.trace("SKILL-ISOLATION-003")
@pytest.mark.red_expected
def test_editorial_skill_isolates_itself_before_checking_cleanliness() -> None:
    text = require_target(SKILL, "SKILL-ISOLATION-003").read_text(encoding="utf-8").casefold()
    for term in (
        "git fetch --no-tags origin main",
        "mktemp -d",
        "git worktree add --detach",
        "checkout compartido",
        "no es un bloqueo",
        "worktree aislado",
        "git status --porcelain",
        "github_get_repo",
        'repository_full_name="reallotex/mragentes-site"',
        "permissions.push",
        "automation/editorial/yyyy-mm-dd",
    ):
        assert term in text, trace_message(
            "SKILL-ISOLATION-003", f"skill lacks isolation term: {term}"
        )


@pytest.mark.trace("SKILL-IDEMPOTENCY-004")
@pytest.mark.red_expected
def test_editorial_skill_has_safe_same_day_idempotency() -> None:
    text = require_target(SKILL, "SKILL-IDEMPOTENCY-004").read_text(encoding="utf-8").casefold()
    for term in (
        "artefactos completos de la fecha ya existen",
        "skipped_valid",
        "estado parcial",
        "needs_review",
    ):
        assert term in text, trace_message(
            "SKILL-IDEMPOTENCY-004", f"skill lacks idempotency term: {term}"
        )
