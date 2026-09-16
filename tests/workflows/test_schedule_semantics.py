from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from tests.support.contracts import ROOT, require_target, trace_message


SCHEDULE = ".automation/schedules/editorial.json"
RRULE = "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA,SU;BYHOUR=18,21;BYMINUTE=0;BYSECOND=0"


def descriptor() -> dict:
    return json.loads(require_target(SCHEDULE, "TASK-CONTRACT-001").read_text(encoding="utf-8"))


@pytest.mark.trace("TASK-CONTRACT-001")
@pytest.mark.red_expected
def test_exactly_one_daily_schedule_is_active_registered_and_scoped() -> None:
    files = sorted(path.name for path in (ROOT / ".automation/schedules").glob("*.json"))
    assert files == ["editorial.json"], trace_message(
        "TASK-CONTRACT-001", f"unexpected schedules: {files}"
    )
    task = descriptor()
    assert task["automation_id"] == "mr-agentes-noticias"
    assert task["status"] == "active" and task["registered"] is True
    assert task["project"] == "MR Agentes"
    assert task["timezone"] == "America/Cordoba"
    assert task["weekdays"] == list(range(7))
    assert task["local_times"] == ["18:00", "21:00"] and task["rrule"] == RRULE
    assert task["cron"] == "0 18,21 * * *"
    datetime.fromisoformat("2026-09-11T18:00:00").replace(tzinfo=ZoneInfo("America/Cordoba"))


@pytest.mark.trace("TASK-RETRY-004")
@pytest.mark.red_expected
def test_one_schedule_has_a_same_day_retry_without_duplicate_output() -> None:
    task = descriptor()
    assert task["retry"] == {
        "second_attempt_local_time": "21:00",
        "same_identity": True,
        "successful_first_attempt_becomes_noop": True,
    }
    prompt = task["prompt"].casefold()
    for term in ("segundo intento", "misma identidad", "no-op", "límite de uso"):
        assert term in prompt, trace_message("TASK-RETRY-004", f"prompt lacks {term}")


@pytest.mark.trace("TASK-WORKTREE-001")
@pytest.mark.red_expected
def test_schedule_uses_new_conversation_and_dedicated_worktree() -> None:
    task = descriptor()
    assert task["execution_environment"] == "local"
    assert task["conversation"] == "new"
    assert task["workspace"] == "self_managed_worktree"
    prompt = task["prompt"].casefold()
    assert "conversación nueva" in prompt and "worktree temporal" in prompt
    for term in (
        "git fetch --no-tags origin main",
        "mktemp -d",
        "git worktree add --detach",
        "origin/main",
        "checkout compartido",
        "no es un bloqueo",
        "git status --porcelain",
    ):
        assert term in prompt, trace_message("TASK-WORKTREE-001", f"prompt lacks {term}")


@pytest.mark.trace("TASK-IDEMPOTENCY-002")
@pytest.mark.red_expected
def test_schedule_treats_a_complete_same_day_run_as_successful_noop() -> None:
    prompt = descriptor()["prompt"].casefold()
    for term in (
        "artefactos completos de la fecha ya existen",
        "skipped_valid",
        "estado parcial",
        "needs_review",
    ):
        assert term in prompt, trace_message("TASK-IDEMPOTENCY-002", f"prompt lacks {term}")


@pytest.mark.trace("TASK-MODEL-003")
@pytest.mark.red_expected
def test_schedule_uses_the_owner_selected_model_and_effort() -> None:
    task = descriptor()
    assert task["model"] == "gpt-5.6-sol"
    assert task["reasoning_effort"] == "ultra"


@pytest.mark.trace("TASK-BRANCH-001")
@pytest.mark.red_expected
def test_schedule_has_one_scoped_branch_and_connector_egress() -> None:
    task = descriptor()
    assert task["branch_template"] == "automation/editorial/{date}"
    assert "automation/editorial/yyyy-mm-dd" in task["prompt"].casefold()
    assert task["permissions"]["remote_egress"] == {
        "provider": "github_connector",
        "contract": ".automation/github/connector-egress.json",
    }
    assert task["permissions"]["external_publish"] is False
    prompt = task["prompt"].casefold()
    assert "no uses git push local" in prompt and "no llames a Meta".casefold() in prompt


@pytest.mark.trace("TASK-OUTPUT-001")
@pytest.mark.red_expected
def test_schedule_requires_one_note_and_one_post_per_platform() -> None:
    task = descriptor()
    assert task["skill"] == "mragentes-editorial-publisher"
    assert task["output"] == {
        "notes_per_run": 1,
        "facebook_posts_per_note": 1,
        "instagram_posts_per_note": 1,
    }
    prompt = task["prompt"].casefold()
    for term in ("exactamente una nota", "portada", "anuncio social", "skipped_valid"):
        assert term in prompt, trace_message("TASK-OUTPUT-001", f"prompt lacks {term}")


@pytest.mark.trace("TASK-NOTIFY-005")
@pytest.mark.red_expected
def test_schedule_does_not_silence_business_failures() -> None:
    task = descriptor()
    assert task["notification_policy"] == "default"
    assert "needs_review" in task["prompt"].casefold()


@pytest.mark.trace("TASK-VISUAL-001")
@pytest.mark.red_expected
def test_editorial_task_can_commit_only_the_note_visual_assets() -> None:
    writes = descriptor()["permissions"]["repository_writes"]
    assert "static/images/stock/**" in writes
    assert "static/images/social/**" in writes
    assert ".automation/social/drafts/**" not in writes
