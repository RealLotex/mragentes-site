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
