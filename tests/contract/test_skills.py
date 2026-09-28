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
    for term in (
        "editorial_release.py",
        "needs_review",
        "No hagas pasos Git manuales",
        "ni llames a Meta",
    ):
        assert term.casefold() in text.casefold(), trace_message(
            "SKILL-CONTRACT-001", f"skill lacks safety term: {term}"
        )


@pytest.mark.trace("SKILL-EDITORIAL-002")
@pytest.mark.red_expected
def test_editorial_skill_enforces_one_atomic_news_note_and_social_asset() -> None:
    text = require_target(SKILL, "SKILL-EDITORIAL-002").read_text(encoding="utf-8").casefold()
    for term in (
        "una nota",
        "un hecho",
        "un anuncio",
        "facebook",
        "instagram",
        "json",
        "editorial_release.py",
    ):
        assert term in text, trace_message(
            "SKILL-EDITORIAL-002", f"skill lacks transaction term: {term}"
        )


@pytest.mark.trace("SKILL-ISOLATION-003")
@pytest.mark.red_expected
def test_editorial_skill_delegates_git_isolation_to_one_script() -> None:
    text = require_target(SKILL, "SKILL-ISOLATION-003").read_text(encoding="utf-8").casefold()
    for term in (
        "/var/tmp",  # noqa: S108 - documented dedicated temporary filesystem
        "worktree",
        "un solo comando",
        "gh",
        "pr",
    ):
        assert term in text, trace_message(
            "SKILL-ISOLATION-003", f"skill lacks isolation term: {term}"
        )


@pytest.mark.trace("SKILL-IDEMPOTENCY-004")
@pytest.mark.red_expected
def test_editorial_skill_has_safe_same_day_idempotency() -> None:
    text = require_target(SKILL, "SKILL-IDEMPOTENCY-004").read_text(encoding="utf-8").casefold()
    for term in (
        "skipped_valid",
        "needs_review",
    ):
        assert term in text, trace_message(
            "SKILL-IDEMPOTENCY-004", f"skill lacks idempotency term: {term}"
        )


@pytest.mark.trace("SKILL-PUBLICATION-005")
@pytest.mark.red_expected
def test_editorial_skill_waits_for_completed_publication() -> None:
    text = require_target(SKILL, "SKILL-PUBLICATION-005").read_text(encoding="utf-8").casefold()
    assert "published:" in text
    assert "no informes el pr como publicación terminada" in text
