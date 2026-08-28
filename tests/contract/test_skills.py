from __future__ import annotations

import re

import pytest

from tests.support.contracts import require_target, trace_message


SKILLS = [
    ("SKILL-NEWS-001", ".agents/skills/mragentes-news-scout/SKILL.md", "mragentes-news-scout"),
    ("SKILL-BLOG-001", ".agents/skills/mragentes-blog-publisher/SKILL.md", "mragentes-blog-publisher"),
    ("SKILL-SOCIAL-001", ".agents/skills/mragentes-social-manager/SKILL.md", "mragentes-social-manager"),
]


@pytest.mark.parametrize("case", SKILLS, ids=[item[0] for item in SKILLS])
@pytest.mark.trace("SKILL-CONTRACT-001")
@pytest.mark.red_expected
def test_skill_has_native_contract_and_safety_limits(case: tuple[str, str, str]) -> None:
    case_id, relative_path, expected_name = case
    path = require_target(relative_path, "SKILL-CONTRACT-001")
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), trace_message(
        "SKILL-CONTRACT-001", f"missing skill front matter: {case_id}"
    )
    assert re.search(rf"(?m)^name:\s*{re.escape(expected_name)}\s*$", text), trace_message(
        "SKILL-CONTRACT-001", f"wrong skill name: {case_id}"
    )
    assert "/home/openclaw" not in text, trace_message(
        "SKILL-CONTRACT-001", f"skill references frozen source: {case_id}"
    )
    assert "dry-run" in text.lower(), trace_message(
        "SKILL-CONTRACT-001", f"skill lacks dry-run contract: {case_id}"
    )


@pytest.mark.trace("SKILL-NEWS-002")
@pytest.mark.red_expected
def test_news_skill_cannot_publish_blog_or_external_channels() -> None:
    path = require_target(".agents/skills/mragentes-news-scout/SKILL.md", "SKILL-NEWS-002")
    text = path.read_text(encoding="utf-8").lower()
    assert "no meta" in text and "no cloudflare" in text and "no nota" in text, trace_message(
        "SKILL-NEWS-002", "news skill lacks explicit side-effect prohibitions"
    )


@pytest.mark.trace("SKILL-BLOG-002")
@pytest.mark.red_expected
def test_blog_skill_enforces_atomic_note_asset_and_queue() -> None:
    path = require_target(".agents/skills/mragentes-blog-publisher/SKILL.md", "SKILL-BLOG-002")
    text = path.read_text(encoding="utf-8").lower()
    for term in ("atómico", "asset", "consumed", "hugo"):
        assert term in text, trace_message("SKILL-BLOG-002", f"blog skill lacks term: {term}")


@pytest.mark.trace("SKILL-SOCIAL-002")
@pytest.mark.red_expected
def test_social_skill_separates_daily_and_recovery_modes() -> None:
    path = require_target(".agents/skills/mragentes-social-manager/SKILL.md", "SKILL-SOCIAL-002")
    text = path.read_text(encoding="utf-8").lower()
    assert "daily_owned" in text and "recovery" in text and "needs_review" in text, trace_message(
        "SKILL-SOCIAL-002", "social skill does not define safe modes"
    )
