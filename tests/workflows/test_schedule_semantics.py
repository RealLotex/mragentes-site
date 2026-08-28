from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from tests.support.contracts import require_target, trace_message


SCHEDULES = [
    ("TASK-NEWS-001", ".automation/schedules/news.json", {0, 1, 2, 3, 4, 5, 6}, "18:00"),
    ("TASK-BLOG-001", ".automation/schedules/blog.json", {2, 6}, "12:00"),
    ("TASK-SOCIAL-001", ".automation/schedules/social.json", {0, 1, 2, 3, 4, 5, 6}, "13:00"),
    ("TASK-RECOVERY-001", ".automation/schedules/recovery.json", {0, 1, 2, 3, 4, 5, 6}, "13:15"),
]


@pytest.mark.parametrize("case", SCHEDULES, ids=[item[0] for item in SCHEDULES])
@pytest.mark.trace("TASK-CONTRACT-001")
@pytest.mark.red_expected
def test_scheduled_descriptor_is_paused_native_and_scoped(case: tuple) -> None:
    case_id, relative_path, _weekdays, _time = case
    descriptor = json.loads(require_target(relative_path, "TASK-CONTRACT-001").read_text(encoding="utf-8"))
    assert descriptor["timezone"] == "America/Cordoba", trace_message(
        "TASK-CONTRACT-001", f"wrong timezone: {case_id}"
    )
    assert descriptor["status"] == "paused", trace_message(
        "TASK-CONTRACT-001", f"task is not initially paused: {case_id}"
    )
    assert descriptor["worktree"] is True and descriptor["project"] == "MR Agentes", trace_message(
        "TASK-CONTRACT-001", f"task is not scoped to MR Agentes worktree: {case_id}"
    )
    assert "/home/openclaw" not in json.dumps(descriptor), trace_message(
        "TASK-CONTRACT-001", f"task references frozen source: {case_id}"
    )


@pytest.mark.parametrize("case", SCHEDULES, ids=[item[0] for item in SCHEDULES])
@pytest.mark.trace("TASK-SCHEDULE-001")
@pytest.mark.red_expected
def test_scheduled_descriptor_matches_weekdays_and_local_time(case: tuple) -> None:
    case_id, relative_path, weekdays, local_time = case
    descriptor = json.loads(require_target(relative_path, "TASK-SCHEDULE-001").read_text(encoding="utf-8"))
    assert set(descriptor["weekdays"]) == weekdays, trace_message(
        "TASK-SCHEDULE-001", f"wrong weekdays: {case_id}"
    )
    assert descriptor["local_time"] == local_time, trace_message(
        "TASK-SCHEDULE-001", f"wrong local time: {case_id}"
    )
    datetime.fromisoformat(f"2026-08-26T{local_time}:00").replace(tzinfo=ZoneInfo("America/Cordoba"))


@pytest.mark.trace("TASK-BRANCH-001")
@pytest.mark.red_expected
def test_scheduled_tasks_push_only_to_automation_branches() -> None:
    branches = []
    for _, relative_path, _, _ in SCHEDULES:
        descriptor = json.loads(require_target(relative_path, "TASK-BRANCH-001").read_text(encoding="utf-8"))
        branches.append(descriptor["branch_template"])
    assert all(value.startswith("automation/") and "main" not in value for value in branches), trace_message(
        "TASK-BRANCH-001", f"unsafe task branch templates: {branches}"
    )


@pytest.mark.trace("TASK-RECOVERY-002")
@pytest.mark.red_expected
def test_recovery_uses_guarded_github_rerun_instead_of_direct_meta_publish() -> None:
    descriptor = json.loads(
        require_target(
            ".automation/schedules/recovery.json", "TASK-RECOVERY-002"
        ).read_text(encoding="utf-8")
    )
    prompt = descriptor["prompt"]
    assert "conector de GitHub" in prompt and "reintentar sólo los jobs fallidos" in prompt, (
        trace_message("TASK-RECOVERY-002", "recovery cannot resume a failed guarded workflow")
    )
    assert "in_progress" in prompt and "uncertain" in prompt, trace_message(
        "TASK-RECOVERY-002", "recovery does not fail closed for active or uncertain effects"
    )
    assert descriptor["permissions"]["workflow_rerun"] == [
        "social-daily.yml",
        "social-note.yml",
    ], trace_message("TASK-RECOVERY-002", "recovery may rerun an unscoped workflow")
    assert descriptor["permissions"]["external_publish"] is False, trace_message(
        "TASK-RECOVERY-002", "recovery is allowed to call Meta directly"
    )
