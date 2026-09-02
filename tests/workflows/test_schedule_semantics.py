from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from tests.support.contracts import require_target, trace_message

SCHEDULES = [
    ("TASK-NEWS-001", ".automation/schedules/news.json", {0, 1, 2, 3, 4, 5, 6}, "18:00"),
    ("TASK-BLOG-001", ".automation/schedules/blog.json", {2, 6}, "12:00"),
    ("TASK-SOCIAL-001", ".automation/schedules/social.json", {0, 1, 2, 3, 4, 5, 6}, "15:00"),
    ("TASK-RECOVERY-001", ".automation/schedules/recovery.json", {0, 1, 2, 3, 4, 5, 6}, "15:15"),
]

AUTOMATION_IDS = {
    "TASK-NEWS-001": "mr-agentes-noticias",
    "TASK-BLOG-001": "mr-agentes-blog",
    "TASK-SOCIAL-001": "mr-agentes-social-diario",
    "TASK-RECOVERY-001": "mr-agentes-recuperaci-n-social",
}

LIVE_RRULES = {
    "TASK-NEWS-001": "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA,SU;BYHOUR=18;BYMINUTE=0;BYSECOND=0",
    "TASK-BLOG-001": "RRULE:FREQ=WEEKLY;BYDAY=WE,SU;BYHOUR=12;BYMINUTE=0;BYSECOND=0",
    "TASK-SOCIAL-001": (
        "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA,SU;"
        "BYHOUR=15;BYMINUTE=0;BYSECOND=0"
    ),
    "TASK-RECOVERY-001": (
        "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA,SU;"
        "BYHOUR=15;BYMINUTE=15;BYSECOND=0"
    ),
}

CONNECTOR_CONTRACT = ".automation/github/connector-egress.json"


@pytest.mark.parametrize("case", SCHEDULES, ids=[item[0] for item in SCHEDULES])
@pytest.mark.trace("TASK-CONTRACT-001")
@pytest.mark.red_expected
def test_scheduled_descriptor_is_active_registered_and_scoped(case: tuple) -> None:
    case_id, relative_path, _weekdays, _time = case
    descriptor = json.loads(
        require_target(relative_path, "TASK-CONTRACT-001").read_text(encoding="utf-8")
    )
    assert descriptor["timezone"] == "America/Cordoba", trace_message(
        "TASK-CONTRACT-001", f"wrong timezone: {case_id}"
    )
    assert descriptor.get("status") == "active", trace_message(
        "TASK-CONTRACT-001", f"task is not active: {case_id}"
    )
    assert descriptor.get("registered") is True, trace_message(
        "TASK-CONTRACT-001", f"task is not registered: {case_id}"
    )
    assert descriptor["project"] == "MR Agentes", trace_message(
        "TASK-CONTRACT-001", f"task is not scoped to MR Agentes: {case_id}"
    )
    assert "/home/openclaw" not in json.dumps(descriptor), trace_message(
        "TASK-CONTRACT-001", f"task references frozen source: {case_id}"
    )


@pytest.mark.parametrize("case", SCHEDULES, ids=[item[0] for item in SCHEDULES])
@pytest.mark.trace("TASK-CONTRACT-002")
@pytest.mark.red_expected
def test_scheduled_descriptor_uses_local_execution_without_legacy_worktree(case: tuple) -> None:
    case_id, relative_path, _weekdays, _time = case
    descriptor = json.loads(
        require_target(relative_path, "TASK-CONTRACT-002").read_text(encoding="utf-8")
    )
    assert descriptor.get("execution_environment") == "local", trace_message(
        "TASK-CONTRACT-002", f"task does not use the local execution environment: {case_id}"
    )
    assert "worktree" not in descriptor, trace_message(
        "TASK-CONTRACT-002", f"task still exposes the obsolete worktree field: {case_id}"
    )


@pytest.mark.parametrize("case", SCHEDULES, ids=[item[0] for item in SCHEDULES])
@pytest.mark.trace("TASK-CONTRACT-003")
@pytest.mark.red_expected
def test_scheduled_descriptor_has_stable_native_automation_id(case: tuple) -> None:
    case_id, relative_path, _weekdays, _time = case
    descriptor = json.loads(
        require_target(relative_path, "TASK-CONTRACT-003").read_text(encoding="utf-8")
    )
    assert descriptor.get("automation_id") == AUTOMATION_IDS[case_id], trace_message(
        "TASK-CONTRACT-003", f"task has an unexpected native automation ID: {case_id}"
    )


@pytest.mark.parametrize("case", SCHEDULES, ids=[item[0] for item in SCHEDULES])
@pytest.mark.trace("TASK-SCHEDULE-001")
@pytest.mark.red_expected
def test_scheduled_descriptor_matches_weekdays_and_local_time(case: tuple) -> None:
    case_id, relative_path, weekdays, local_time = case
    descriptor = json.loads(
        require_target(relative_path, "TASK-SCHEDULE-001").read_text(encoding="utf-8")
    )
    assert set(descriptor["weekdays"]) == weekdays, trace_message(
        "TASK-SCHEDULE-001", f"wrong weekdays: {case_id}"
    )
    assert descriptor["local_time"] == local_time, trace_message(
        "TASK-SCHEDULE-001", f"wrong local time: {case_id}"
    )
    assert descriptor["rrule"] == LIVE_RRULES[case_id], trace_message(
        "TASK-SCHEDULE-001", f"descriptor RRULE differs from the live automation: {case_id}"
    )
    datetime.fromisoformat(f"2026-08-26T{local_time}:00").replace(tzinfo=ZoneInfo("America/Cordoba"))


@pytest.mark.trace("TASK-BRANCH-001")
@pytest.mark.red_expected
def test_scheduled_tasks_push_only_to_automation_branches() -> None:
    branches = []
    for _, relative_path, _, _ in SCHEDULES:
        descriptor = json.loads(
            require_target(relative_path, "TASK-BRANCH-001").read_text(encoding="utf-8")
        )
        branches.append(descriptor["branch_template"])
    assert all(
        value.startswith("automation/") and "main" not in value for value in branches
    ), trace_message("TASK-BRANCH-001", f"unsafe task branch templates: {branches}")


@pytest.mark.parametrize("case", SCHEDULES, ids=[item[0] for item in SCHEDULES])
@pytest.mark.trace("TASK-EGRESS-001")
@pytest.mark.red_expected
def test_scheduled_tasks_require_connector_egress_without_local_git_push(case: tuple) -> None:
    case_id, relative_path, _weekdays, _time = case
    descriptor = json.loads(
        require_target(relative_path, "TASK-EGRESS-001").read_text(encoding="utf-8")
    )
    permissions = descriptor["permissions"]
    assert permissions.get("remote_egress") == {
        "provider": "github_connector",
        "contract": CONNECTOR_CONTRACT,
    }, trace_message("TASK-EGRESS-001", f"task lacks connector egress: {case_id}")
    assert "git_push" not in permissions, trace_message(
        "TASK-EGRESS-001", f"task still grants ambiguous local Git push: {case_id}"
    )
    prompt = descriptor["prompt"]
    assert "conector de GitHub" in prompt and CONNECTOR_CONTRACT in prompt, trace_message(
        "TASK-EGRESS-001", f"task prompt does not route delivery through the connector: {case_id}"
    )
    assert "no uses git push local" in prompt.lower(), trace_message(
        "TASK-EGRESS-001", f"task prompt permits local credential fallback: {case_id}"
    )


@pytest.mark.trace("TASK-BLOG-VISUAL-001")
@pytest.mark.red_expected
def test_blog_schedule_requires_a_relevant_stock_photo_for_the_note_template() -> None:
    descriptor = json.loads(
        require_target(".automation/schedules/blog.json", "TASK-BLOG-VISUAL-001").read_text(
            encoding="utf-8"
        )
    )
    prompt = descriptor["prompt"].casefold()
    assert "proveedor de stock" in prompt and "pexels" in prompt, trace_message(
        "TASK-BLOG-VISUAL-001", "blog automation lacks a relevant stock-photo source"
    )
    assert "fallback" in prompt and "generada" in prompt, trace_message(
        "TASK-BLOG-VISUAL-001", "blog automation lacks a controlled background fallback"
    )
    assert "plantilla nota" in prompt and "nunca" in prompt, trace_message(
        "TASK-BLOG-VISUAL-001", "blog automation can publish a raw background instead of the branded template"
    )
    assert "render-note-announcement" in prompt, trace_message(
        "TASK-BLOG-VISUAL-001", "blog automation does not render the mandatory branded social asset"
    )
    assert "static/images/social/**" in descriptor["permissions"]["repository_writes"], trace_message(
        "TASK-BLOG-VISUAL-001", "blog automation cannot commit the rendered branded announcement"
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
    assert descriptor["permissions"]["workflow_rerun"] == ["social-daily.yml", "social-note.yml"], (
        trace_message("TASK-RECOVERY-002", "recovery may rerun an unscoped workflow")
    )
    assert "wait_for_publication" in prompt and "notify_deployed_note quedó skipped" in prompt, (
        trace_message("TASK-RECOVERY-002", "recovery cannot safely resume a pre-egress deploy gate")
    )
    assert ".automation/publication/retries/<slug>/<run_id>.json" in prompt and (
        ".automation/publication/retries/**" in descriptor["permissions"]["repository_writes"]
    ), trace_message("TASK-RECOVERY-002", "recovery cannot create an audited deploy recovery request")
    assert descriptor["permissions"]["external_publish"] is False, trace_message(
        "TASK-RECOVERY-002", "recovery is allowed to call Meta directly"
    )
