from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from tests.support.contracts import ROOT, require_target, trace_message


def workflow(relative_path: str, trace_id: str) -> tuple[Path, str, dict]:
    path = require_target(relative_path, trace_id)
    source = path.read_text(encoding="utf-8")
    parsed = yaml.load(source, Loader=yaml.BaseLoader)  # noqa: S506 - scalar-only loader
    assert isinstance(parsed, dict), trace_message(trace_id, "workflow root must be a mapping")
    return path, source, parsed


def action_references(source: str) -> list[str]:
    return re.findall(r"(?m)^\s*-?\s*uses:\s*([^\s#]+)", source)


def job_run_commands(job: dict) -> str:
    return "\n".join(
        str(step.get("run", "")) for step in job.get("steps", []) if isinstance(step, dict)
    )


@pytest.mark.trace("WF-CI-001")
@pytest.mark.red_expected
def test_ci_workflow_is_read_only_by_default_and_scopes_merge_permissions() -> None:
    _, source, parsed = workflow(".github/workflows/ci.yml", "WF-CI-001")
    assert "pull_request" in source and "contents: read" in source, trace_message(
        "WF-CI-001", "CI lacks PR trigger or read-only contents permission"
    )
    jobs = parsed.get("jobs", {})
    assert "test" in jobs and "merge_automation" in jobs
    checkout = jobs["test"].get("steps", [])[0]
    assert checkout.get("with", {}).get("fetch-depth") == "0", trace_message(
        "WF-CI-001", "CI shallow checkout cannot prove ancestry from the audited baseline"
    )
    merge = jobs["merge_automation"]
    assert merge.get("needs") == "test", trace_message(
        "WF-CI-001", "automation merge is not downstream from the complete test job"
    )
    assert merge.get("permissions") == {
        "contents": "write",
        "pull-requests": "write",
    }, trace_message("WF-CI-001", "write permissions are not isolated to the merge job")


@pytest.mark.trace("WF-INTAKE-001")
@pytest.mark.red_expected
def test_automation_intake_requires_scoped_branches_and_pr_gate() -> None:
    _, source, _ = workflow(".github/workflows/automation-intake.yml", "WF-INTAKE-001")
    for term in (
        "automation/news/**",
        "automation/blog/**",
        "automation/social/**",
        "automation/recovery/**",
        "pull-requests: write",
    ):
        assert term in source, trace_message("WF-INTAKE-001", f"intake lacks: {term}")
    assert "git push origin HEAD:main" not in source, trace_message(
        "WF-INTAKE-001", "intake pushes directly to main"
    )


@pytest.mark.trace("WF-INTAKE-002")
@pytest.mark.red_expected
def test_automation_merge_happens_only_after_ci_without_auto_merge_dependency() -> None:
    _, intake_source, _ = workflow(
        ".github/workflows/automation-intake.yml", "WF-INTAKE-002"
    )
    _, ci_source, parsed_ci = workflow(".github/workflows/ci.yml", "WF-INTAKE-002")
    assert "contents: read" in intake_source and "pull-requests: write" in intake_source, trace_message(
        "WF-INTAKE-002", "intake lacks least-privilege permissions to open its PR"
    )
    assert "gh pr merge" not in intake_source and "--auto" not in intake_source, trace_message(
        "WF-INTAKE-002", "intake still depends on repository auto-merge"
    )
    merge_job = parsed_ci.get("jobs", {}).get("merge_automation", {})
    merge_commands = job_run_commands(merge_job)
    merge_lines = [line.strip() for line in merge_commands.splitlines() if "gh pr merge" in line]
    assert len(merge_lines) == 1, trace_message(
        "WF-INTAKE-002", "CI must contain exactly one explicit automation PR merge command"
    )
    assert "--squash" in merge_lines[0] and "--delete-branch" in merge_lines[0], trace_message(
        "WF-INTAKE-002", "post-CI merge must squash and delete the automation branch"
    )
    condition = str(merge_job.get("if", ""))
    assert "startsWith(github.head_ref, 'automation/')" in condition, trace_message(
        "WF-INTAKE-002", "merge job is not restricted to automation branches"
    )
    assert "github.event.pull_request.head.repo.full_name == github.repository" in condition, trace_message(
        "WF-INTAKE-002", "merge job does not reject branches from other repositories"
    )
    combined = intake_source + "\n" + ci_source
    assert not re.search(r"(?m)^\s*git\s+push\b", combined), trace_message(
        "WF-INTAKE-002", "workflows must never push Git commits directly"
    )
    assert "--force" not in combined, trace_message(
        "WF-INTAKE-002", "automation merge contains a force option"
    )


@pytest.mark.trace("WF-DEPLOY-001")
@pytest.mark.red_expected
def test_deploy_runs_tests_before_uploading_pages_artifact() -> None:
    _, source, parsed = workflow(".github/workflows/deploy.yml", "WF-DEPLOY-001")
    ci_steps = parsed.get("jobs", {}).get("ci", {}).get("steps", [])
    ci_commands = "\n".join(
        str(step.get("run", "")) for step in ci_steps if isinstance(step, dict)
    )
    assert "pytest" in ci_commands, trace_message(
        "WF-DEPLOY-001", "deploy CI does not execute the Python contracts"
    )
    assert "npm ci" in ci_commands and "npm run test" in ci_commands, trace_message(
        "WF-DEPLOY-001", "deploy CI does not block Pages and effects on JavaScript contracts"
    )
    test_position = min(
        (
            source.find(term)
            for term in ("pytest", "npm run test", "needs: ci")
            if source.find(term) >= 0
        ),
        default=-1,
    )
    upload_position = source.find("upload-pages-artifact")
    assert 0 <= test_position < upload_position, trace_message(
        "WF-DEPLOY-001", "Pages artifact is uploaded without a prior test gate"
    )


@pytest.mark.trace("WF-DEPLOY-002")
@pytest.mark.red_expected
def test_deploy_actions_are_pinned_by_commit_sha() -> None:
    _, source, _ = workflow(".github/workflows/deploy.yml", "WF-DEPLOY-002")
    unpinned = [ref for ref in action_references(source) if not re.search(r"@[0-9a-f]{40}$", ref)]
    assert not unpinned, trace_message("WF-DEPLOY-002", f"unpinned actions: {unpinned}")


@pytest.mark.trace("WF-DEPLOY-003")
@pytest.mark.red_expected
def test_deploy_health_gate_precedes_external_effects() -> None:
    _, source, _ = workflow(".github/workflows/deploy.yml", "WF-DEPLOY-003")
    assert "wait_for_publication" in source, trace_message(
        "WF-DEPLOY-003", "deploy has no URL/image/marker health gate"
    )
    assert "social-note" in source and "notify_deployed_note" in source, trace_message(
        "WF-DEPLOY-003", "deploy does not invoke post-deploy effects"
    )


@pytest.mark.trace("WF-DEPLOY-004")
@pytest.mark.red_expected
def test_deploy_detects_only_new_notes_and_daily_drafts_from_git_history() -> None:
    _, source, parsed = workflow(".github/workflows/deploy.yml", "WF-DEPLOY-004")
    detect_job = parsed.get("jobs", {}).get("detect_changes", {})
    assert detect_job, trace_message("WF-DEPLOY-004", "deploy lacks a detect_changes job")
    outputs = detect_job.get("outputs", {})
    assert {"note_slugs", "daily_drafts"}.issubset(outputs), trace_message(
        "WF-DEPLOY-004", "detect_changes does not expose both typed output arrays"
    )
    assert "scripts/automation/detect_changes.py" in source, trace_message(
        "WF-DEPLOY-004", "deploy bypasses the tested Git change detector"
    )
    assert "fetch-depth: 0" in source, trace_message(
        "WF-DEPLOY-004", "change detection does not fetch the required Git history"
    )


@pytest.mark.trace("WF-DEPLOY-005")
@pytest.mark.red_expected
def test_deploy_dispatches_content_effects_but_never_redeploys_worker_for_a_note() -> None:
    _, source, _ = workflow(".github/workflows/deploy.yml", "WF-DEPLOY-005")
    for target in ("social-note.yml", "social-daily.yml", "notify-note.yml"):
        assert target in source, trace_message("WF-DEPLOY-005", f"deploy never dispatches {target}")
    assert "note_slug" in source and "daily_drafts" in source, trace_message(
        "WF-DEPLOY-005", "deploy dispatches without typed note/draft identifiers"
    )
    assert not re.search(r"gh\s+workflow\s+run\s+push-worker\.yml", source), trace_message(
        "WF-DEPLOY-005", "a content publication incorrectly redeploys the Push Worker"
    )


@pytest.mark.trace("WF-PY-DEPS-001")
@pytest.mark.red_expected
@pytest.mark.parametrize(
    ("relative_path", "job_name", "runtime_marker"),
    (
        (
            ".github/workflows/deploy.yml",
            "detect_changes",
            "scripts/automation/detect_changes.py",
        ),
        (
            ".github/workflows/deploy.yml",
            "wait_for_publication",
            "scripts/automation/wait_for_publication.py",
        ),
        (
            ".github/workflows/notify-note.yml",
            "send_notification",
            "scripts.notifications.notify_deployed_note",
        ),
    ),
)
def test_clean_python_jobs_install_hash_locked_runtime_dependencies(
    relative_path: str,
    job_name: str,
    runtime_marker: str,
) -> None:
    _, _, parsed = workflow(relative_path, "WF-PY-DEPS-001")
    job = parsed.get("jobs", {}).get(job_name, {})
    assert job, trace_message(
        "WF-PY-DEPS-001", f"{relative_path}:{job_name} does not exist"
    )
    commands = job_run_commands(job)
    install = "python -m pip install --require-hashes -r requirements-test.lock.txt"
    assert install in commands, trace_message(
        "WF-PY-DEPS-001",
        f"{relative_path}:{job_name} imports PyYAML without installing the locked runtime",
    )
    assert (
        runtime_marker in commands
        and commands.index(install) < commands.index(runtime_marker)
    ), (
        trace_message(
            "WF-PY-DEPS-001",
            f"{relative_path}:{job_name} installs dependencies after running its Python entrypoint",
        )
    )


@pytest.mark.trace("WF-SOCIAL-NOTE-001")
@pytest.mark.red_expected
def test_social_note_is_reusable_and_testing_only() -> None:
    _, source, _ = workflow(".github/workflows/social-note.yml", "WF-SOCIAL-NOTE-001")
    assert "workflow_call" in source and "meta-testing" in source, trace_message(
        "WF-SOCIAL-NOTE-001", "social-note lacks reusable testing contract"
    )


@pytest.mark.trace("WF-SOCIAL-NOTE-002")
@pytest.mark.red_expected
def test_social_note_delivers_the_exact_deployed_slug_through_guarded_cli() -> None:
    _, source, _ = workflow(".github/workflows/social-note.yml", "WF-SOCIAL-NOTE-002")
    assert "python -m scripts.social deliver-note" in source, trace_message(
        "WF-SOCIAL-NOTE-002", "social-note does not call the guarded delivery command"
    )
    for term in ('--slug "$NOTE_SLUG"', '--deploy-sha "$DEPLOY_SHA"'):
        assert term in source, trace_message("WF-SOCIAL-NOTE-002", f"social-note lacks {term}")
    assert "scripts.social recover" not in source, trace_message(
        "WF-SOCIAL-NOTE-002", "social-note only prints a local recovery plan"
    )
    assert "--force" not in source, trace_message(
        "WF-SOCIAL-NOTE-002", "social-note exposes a duplicate-publication override"
    )


@pytest.mark.trace("WF-SOCIAL-DAILY-001")
@pytest.mark.red_expected
def test_social_daily_is_separate_and_idempotent() -> None:
    _, source, _ = workflow(".github/workflows/social-daily.yml", "WF-SOCIAL-DAILY-001")
    for term in ("daily_owned", "dedupe", "concurrency", "meta-testing"):
        assert term in source, trace_message("WF-SOCIAL-DAILY-001", f"daily workflow lacks: {term}")


@pytest.mark.trace("WF-SOCIAL-DAILY-002")
@pytest.mark.red_expected
def test_social_daily_delivers_one_date_scoped_committed_draft() -> None:
    _, source, _ = workflow(".github/workflows/social-daily.yml", "WF-SOCIAL-DAILY-002")
    assert "draft_path" in source, trace_message(
        "WF-SOCIAL-DAILY-002", "social-daily has no committed draft input"
    )
    assert ".automation/social/drafts/" in source, trace_message(
        "WF-SOCIAL-DAILY-002", "social-daily does not constrain the draft namespace"
    )
    assert "python -m scripts.social deliver-draft" in source, trace_message(
        "WF-SOCIAL-DAILY-002", "social-daily does not call the guarded delivery command"
    )
    assert '--draft "$DRAFT_PATH"' in source, trace_message(
        "WF-SOCIAL-DAILY-002", "social-daily does not pass the validated draft path"
    )
    assert "scripts.social recover" not in source and "--force" not in source, trace_message(
        "WF-SOCIAL-DAILY-002", "social-daily can recover-only or override deduplication"
    )


@pytest.mark.trace("WF-PUSH-001")
@pytest.mark.red_expected
def test_notify_note_sends_one_idempotent_event_with_secrets_only_in_env() -> None:
    _, source, parsed = workflow(".github/workflows/notify-note.yml", "WF-PUSH-001")
    assert "workflow_call" in source and "workflow_dispatch" in source, trace_message(
        "WF-PUSH-001", "notify-note is not reusable and manually recoverable"
    )
    job = parsed.get("jobs", {}).get("send_notification", {})
    env = job.get("env", {})
    assert env.get("PUSH_API_TOKEN") == "${{ secrets.PUSH_API_TOKEN }}", trace_message(
        "WF-PUSH-001", "Push API token is not injected through the job environment"
    )
    assert env.get("PUSH_WORKER_URL") == "${{ vars.PUSH_WORKER_URL }}", trace_message(
        "WF-PUSH-001", "public Worker URL is not injected through a scoped Actions variable"
    )
    run_sources = "\n".join(
        str(step.get("run", "")) for step in job.get("steps", []) if isinstance(step, dict)
    )
    assert "python -m scripts.notifications.notify_deployed_note" in run_sources
    assert (
        "send-note" in run_sources and "--token-env PUSH_API_TOKEN" in run_sources
    ), trace_message(
        "WF-PUSH-001", "notify-note bypasses the tested idempotent send-note interface"
    )
    assert "${{ secrets." not in run_sources and "--token " not in run_sources, trace_message(
        "WF-PUSH-001", "a Push secret is interpolated directly into a command"
    )


@pytest.mark.trace("WF-CF-BUILD-001")
@pytest.mark.red_expected
def test_worker_pipeline_tests_staging_before_production() -> None:
    _, source, _ = workflow(".github/workflows/push-worker.yml", "WF-CF-BUILD-001")
    positions = [source.find(term) for term in ("test", "staging", "production")]
    assert all(position >= 0 for position in positions) and positions == sorted(
        positions
    ), trace_message("WF-CF-BUILD-001", "Worker pipeline is not test→staging→production")
    for path in ("cf_worker.js", "assets/js/push.js", "static/sw.js", "tests-js/**"):
        assert path in source, trace_message(
            "WF-CF-BUILD-001", f"Worker pipeline is not triggered by changes to {path}"
        )
    assert "node --check cf_worker.js" in source, trace_message(
        "WF-CF-BUILD-001", "connector handoff does not syntax-check the canonical Worker"
    )
    assert "tests/contract/test_cloudflare_manifest.py" in source, trace_message(
        "WF-CF-BUILD-001", "Worker pipeline does not validate its connector manifest"
    )


@pytest.mark.trace("WF-SOCIAL-LEGACY-001")
@pytest.mark.red_expected
def test_legacy_social_workflow_does_not_interpolate_inputs_in_shell() -> None:
    _, source, _ = workflow(".github/workflows/social.yml", "WF-SOCIAL-LEGACY-001")
    run_blocks = re.findall(r"(?ms)^\s+run:\s*\|\n(.*?)(?=^\s{6}\S|\Z)", source)
    unsafe = [block for block in run_blocks if "${{" in block]
    assert not unsafe, trace_message(
        "WF-SOCIAL-LEGACY-001", "GitHub expressions are interpolated directly in shell"
    )


@pytest.mark.trace("WF-SOCIAL-LEGACY-002")
@pytest.mark.red_expected
def test_legacy_social_workflow_cannot_hide_git_failures() -> None:
    _, source, _ = workflow(".github/workflows/social.yml", "WF-SOCIAL-LEGACY-002")
    assert "git pull --rebase origin main || true" not in source, trace_message(
        "WF-SOCIAL-LEGACY-002", "workflow suppresses rebase failures"
    )
    assert "git push origin HEAD:main" not in source, trace_message(
        "WF-SOCIAL-LEGACY-002", "workflow writes state directly to main"
    )


@pytest.mark.trace("SEC-SCOPE-001")
@pytest.mark.red_expected
def test_every_workflow_uses_minimal_permissions_and_sha_pins() -> None:
    problems: list[str] = []
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        source = path.read_text(encoding="utf-8")
        if "permissions:" not in source:
            problems.append(f"{path.name}:missing permissions")
        for ref in action_references(source):
            if not re.search(r"@[0-9a-f]{40}$", ref):
                problems.append(f"{path.name}:unpinned:{ref}")
    assert not problems, trace_message("SEC-SCOPE-001", f"workflow hardening gaps: {problems}")
