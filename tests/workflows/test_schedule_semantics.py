from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.contracts import ROOT, require_target, trace_message

SCHEDULE = ".automation/schedules/editorial.json"
RRULE = "RRULE:FREQ=DAILY;BYHOUR=5;BYMINUTE=0;BYSECOND=0"


def descriptor() -> dict:
    return json.loads(require_target(SCHEDULE, "TASK-CONTRACT-001").read_text(encoding="utf-8"))


@pytest.mark.trace("TASK-CONTRACT-001")
@pytest.mark.red_expected
def test_one_daily_schedule_runs_at_five_with_luna_xhigh() -> None:
    files = sorted(path.name for path in (ROOT / ".automation/schedules").glob("*.json"))
    assert files == ["editorial.json"]
    task = descriptor()
    assert task["automation_id"] == "mr-agentes-noticias"
    assert task["status"] == "active" and task["registered"] is True
    assert task["timezone"] == "America/Cordoba"
    assert task["weekdays"] == list(range(7))
    assert task["local_times"] == ["05:00"]
    assert task["cron"] == "0 5 * * *" and task["rrule"] == RRULE
    assert task["model"] == "gpt-6-luna" and task["reasoning_effort"] == "xhigh"
    assert "retry" not in task


@pytest.mark.trace("TASK-INPUT-002")
@pytest.mark.red_expected
def test_model_only_researches_and_calls_one_fixed_release_command() -> None:
    task = descriptor()
    assert task["conversation"] == "new"
    assert task["skill"] == "mragentes-editorial-publisher"
    prompt = task["prompt"].casefold()
    for term in ("noticia mainstream", "últimas 48 horas", "imagen", "editorial_release.py"):
        assert term in prompt, trace_message("TASK-INPUT-002", f"prompt lacks {term}")
    for old_step in ("create_blob", "create_tree", "git worktree add", "github_get_repo"):
        assert old_step not in prompt


@pytest.mark.trace("TASK-EGRESS-003")
@pytest.mark.red_expected
def test_one_script_owns_scoped_git_delivery() -> None:
    task = descriptor()
    assert task["workspace"] == "self_managed_worktree"
    assert task["branch_template"] == "automation/editorial/{date}"
    assert task["permissions"]["remote_egress"] == {
        "provider": "gh_cli",
        "contract": ".automation/github/editorial-egress.json",
    }
    assert task["permissions"]["external_publish"] is False
    script = Path(ROOT / "scripts/automation/editorial_release.py").read_text(encoding="utf-8")
    for term in ("worktree", "--cached", "git", "push", "gh", "pr", "create"):
        assert term in script


@pytest.mark.trace("TASK-OUTPUT-004")
@pytest.mark.red_expected
def test_daily_output_remains_one_blog_note_and_one_social_post_per_platform() -> None:
    task = descriptor()
    assert task["notification_policy"] == "default"
    assert task["output"] == {
        "notes_per_run": 1,
        "facebook_posts_per_note": 1,
        "instagram_posts_per_note": 1,
    }
    assert "static/images/stock/**" in task["permissions"]["repository_writes"]
    assert "static/images/social/**" in task["permissions"]["repository_writes"]
