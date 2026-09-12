from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from tests.support.contracts import require_target, trace_message


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.trace("EDITORIAL-KISS-001")
@pytest.mark.red_expected
def test_only_one_native_editorial_schedule_is_enabled() -> None:
    schedules = sorted(path.name for path in (ROOT / ".automation/schedules").glob("*.json"))
    assert schedules == ["editorial.json"], trace_message(
        "EDITORIAL-KISS-001", f"expected one schedule, found {schedules}"
    )

    descriptor = json.loads(
        require_target(".automation/schedules/editorial.json", "EDITORIAL-KISS-001").read_text(
            encoding="utf-8"
        )
    )
    assert descriptor["automation_id"] == "mr-agentes-noticias"
    assert descriptor["name"] == "MR Agentes — Editorial diario"
    assert descriptor["status"] == "active" and descriptor["registered"] is True
    assert descriptor["timezone"] == "America/Cordoba"
    assert descriptor["weekdays"] == [0, 1, 2, 3, 4, 5, 6]
    assert descriptor["local_time"] == "18:00"
    assert descriptor["conversation"] == "new"
    assert descriptor["workspace"] == "worktree"
    assert descriptor["skill"] == "mragentes-editorial-publisher"
    assert descriptor["branch_template"] == "automation/editorial/{run_id}"
    assert descriptor["output"] == {
        "notes_per_run": 1,
        "facebook_posts_per_note": 1,
        "instagram_posts_per_note": 1,
    }


@pytest.mark.trace("EDITORIAL-KISS-002")
@pytest.mark.red_expected
def test_one_skill_owns_the_complete_local_editorial_transaction() -> None:
    skill_dirs = sorted(path.name for path in (ROOT / ".agents/skills").iterdir() if path.is_dir())
    assert skill_dirs == ["mragentes-editorial-publisher"], trace_message(
        "EDITORIAL-KISS-002", f"expected one skill, found {skill_dirs}"
    )
    source = require_target(
        ".agents/skills/mragentes-editorial-publisher/SKILL.md", "EDITORIAL-KISS-002"
    ).read_text(encoding="utf-8")
    for term in (
        "name: mragentes-editorial-publisher",
        "dry-run",
        "una nota",
        "Facebook",
        "Instagram",
        "atómico",
        "needs_review",
        "no uses git push local",
    ):
        assert term.casefold() in source.casefold(), trace_message(
            "EDITORIAL-KISS-002", f"editorial skill lacks {term!r}"
        )


@pytest.mark.trace("EDITORIAL-KISS-003")
@pytest.mark.red_expected
def test_deploy_owns_both_post_publication_effects_without_dispatch_chains() -> None:
    obsolete = {
        "notify-note.yml",
        "social-daily.yml",
        "social-note.yml",
        "social.yml",
    }
    workflows = {path.name for path in (ROOT / ".github/workflows").glob("*.yml")}
    assert workflows.isdisjoint(obsolete), trace_message(
        "EDITORIAL-KISS-003", f"obsolete workflows remain: {sorted(workflows & obsolete)}"
    )

    path = require_target(".github/workflows/deploy.yml", "EDITORIAL-KISS-003")
    source = path.read_text(encoding="utf-8")
    parsed = yaml.load(source, Loader=yaml.BaseLoader)
    jobs = parsed["jobs"]
    assert {"wait_for_publication", "publish_meta", "notify_push"} <= set(jobs)
    assert jobs["publish_meta"]["needs"] == ["wait_for_publication", "detect_changes"]
    assert jobs["notify_push"]["needs"] == ["wait_for_publication", "detect_changes"]
    assert jobs["publish_meta"]["environment"] == "meta-testing"
    assert jobs["notify_push"]["environment"] == "cloudflare-production"
    assert "scripts.social deliver-note" in source
    assert "scripts.notifications.notify_deployed_note" in source
    assert "gh workflow run" not in source
    assert "daily_drafts" not in source


@pytest.mark.trace("EDITORIAL-KISS-004")
@pytest.mark.red_expected
def test_only_editorial_branches_enter_the_automation_gate() -> None:
    intake = require_target(
        ".github/workflows/automation-intake.yml", "EDITORIAL-KISS-004"
    ).read_text(encoding="utf-8")
    assert "automation/editorial/**" in intake
    for obsolete in (
        "automation/news/**",
        "automation/blog/**",
        "automation/social/**",
        "automation/recovery/**",
    ):
        assert obsolete not in intake


@pytest.mark.trace("EDITORIAL-KISS-005")
@pytest.mark.red_expected
def test_connector_clean_start_is_satisfied_by_a_dedicated_worktree() -> None:
    contract = json.loads(
        require_target(
            ".automation/github/connector-egress.json", "EDITORIAL-KISS-005"
        ).read_text(encoding="utf-8")
    )
    assert contract["safety"]["require_clean_start"] is True
    assert contract["workspace"]["mode"] == "dedicated_worktree"
    assert contract["workspace"]["base_ref"] == "origin/main"
