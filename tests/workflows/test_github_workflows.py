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
    assert set(jobs) == {"test"}, trace_message(
        "WF-CI-001", "CI must test only; the trusted workflow_run gate owns merging"
    )
    checkout = jobs["test"].get("steps", [])[0]
    assert checkout.get("with", {}).get("fetch-depth") == "0", trace_message(
        "WF-CI-001", "CI shallow checkout cannot prove ancestry from the audited baseline"
    )
    assert "gh pr merge" not in source, trace_message(
        "WF-CI-001", "untrusted pull-request CI still owns repository merge authority"
    )


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
    _, intake_source, parsed_intake = workflow(
        ".github/workflows/automation-intake.yml", "WF-INTAKE-002"
    )
    _, ci_source, _ = workflow(".github/workflows/ci.yml", "WF-INTAKE-002")
    assert (
        "contents: read" in intake_source and "pull-requests: write" in intake_source
    ), trace_message(
        "WF-INTAKE-002", "intake lacks least-privilege permissions to open its PR"
    )
    assert "workflow_run" in intake_source and "Contract and site CI" in intake_source, (
        trace_message("WF-INTAKE-002", "intake has no trusted post-CI completion trigger")
    )
    merge_job = parsed_intake.get("jobs", {}).get("merge_verified_automation", {})
    assert merge_job.get("permissions") == {
        "contents": "write",
        "pull-requests": "write",
    }, trace_message("WF-INTAKE-002", "post-CI merge authority is not job-scoped")
    merge_commands = job_run_commands(merge_job)
    merge_lines = [line.strip() for line in merge_commands.splitlines() if "gh pr merge" in line]
    assert len(merge_lines) == 1, trace_message(
        "WF-INTAKE-002", "trusted intake must contain exactly one explicit PR merge command"
    )
    assert all(
        term in merge_lines[0]
        for term in ("--squash", "--delete-branch", "--match-head-commit")
    ), trace_message(
        "WF-INTAKE-002", "post-CI merge must squash and delete the automation branch"
    )
    condition = str(merge_job.get("if", ""))
    for term in (
        "github.event.workflow_run.conclusion == 'success'",
        "github.event.workflow_run.event == 'pull_request'",
        "startsWith(github.event.workflow_run.head_branch, 'automation/')",
        "github.event.workflow_run.head_repository.full_name == github.repository",
    ):
        assert term in condition, trace_message(
            "WF-INTAKE-002", f"post-CI merge condition lacks {term}"
        )
    for term in (
        'pr["base"]["ref"] != "main"',
        'pr["head"]["repo"]["full_name"] != repository',
        'pr["head"]["ref"] != branch',
        'pr["head"]["sha"] != head_sha',
        '"automation" not in labels',
    ):
        assert term in merge_commands, trace_message(
            "WF-INTAKE-002", f"post-CI PR validation lacks {term}"
        )
    assert "--auto" not in intake_source, trace_message(
        "WF-INTAKE-002", "intake depends on disabled repository auto-merge"
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
    ci_job = parsed.get("jobs", {}).get("ci", {})
    ci_steps = ci_job.get("steps", [])
    checkout = ci_steps[0]
    assert checkout.get("with", {}).get("fetch-depth") == "0", trace_message(
        "WF-DEPLOY-001", "deploy CI shallow checkout cannot execute repository ancestry contracts"
    )
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
    assert (
        "peaceiris/actions-hugo@6e295a6a0c9087bf374299e9d67f9d2edab9f18f" in source
    ), trace_message(
        "WF-DEPLOY-002",
        "Hugo setup is not pinned to the verified v3.0.0 commit",
    )
    assert (
        "actions/deploy-pages@d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e" in source
    ), trace_message(
        "WF-DEPLOY-002",
        "Pages deployment is not pinned to the verified v4.0.5 commit",
    )


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
    assert "python -m scripts.automation.detect_changes" in source, trace_message(
        "WF-DEPLOY-004", "deploy bypasses the tested Git change detector"
    )
    assert "scripts.automation.wait_for_publication" in source, trace_message(
        "WF-DEPLOY-004", "deploy health gate is not invoked as an import-safe module"
    )
    assert "python scripts/automation/" not in source, trace_message(
        "WF-DEPLOY-004", "deploy invokes a package script with a broken import root"
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


@pytest.mark.trace("WF-DEPLOY-007")
@pytest.mark.red_expected
def test_deploy_dispatches_workflows_with_an_explicit_repository_without_checkout() -> None:
    _, source, _ = workflow(".github/workflows/deploy.yml", "WF-DEPLOY-007")
    assert '"--repo"' in source and "GITHUB_REPOSITORY" in source, trace_message(
        "WF-DEPLOY-007", "dispatch job relies on a local git checkout that it does not have"
    )


@pytest.mark.trace("WF-DEPLOY-006")
@pytest.mark.red_expected
def test_deploy_never_cancels_an_event_before_its_external_effect_dispatch() -> None:
    _, _, parsed = workflow(".github/workflows/deploy.yml", "WF-DEPLOY-006")
    concurrency = parsed.get("concurrency", {})
    assert concurrency.get("cancel-in-progress") == "false", trace_message(
        "WF-DEPLOY-006", "a later main push can cancel an earlier publication event"
    )


@pytest.mark.trace("WF-PY-DEPS-001")
@pytest.mark.red_expected
@pytest.mark.parametrize(
    ("relative_path", "job_name", "runtime_marker"),
    (
        (
            ".github/workflows/deploy.yml",
            "detect_changes",
            "scripts.automation.detect_changes",
        ),
        (
            ".github/workflows/deploy.yml",
            "wait_for_publication",
            "scripts.automation.wait_for_publication",
        ),
        (
            ".github/workflows/notify-note.yml",
            "send_notification",
            "scripts.notifications.notify_deployed_note",
        ),
        (
            ".github/workflows/social-note.yml",
            "publish_testing_only",
            "scripts.social deliver-note",
        ),
        (
            ".github/workflows/social-daily.yml",
            "publish_daily_owned",
            "scripts.social deliver-draft",
        ),
        (
            ".github/workflows/meta-preflight.yml",
            "validate_meta_testing",
            "scripts.social.meta_preflight",
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
    _, source, parsed = workflow(".github/workflows/social-note.yml", "WF-SOCIAL-NOTE-001")
    assert "workflow_call" in source and "meta-testing" in source, trace_message(
        "WF-SOCIAL-NOTE-001", "social-note lacks reusable testing contract"
    )
    env = parsed.get("jobs", {}).get("publish_testing_only", {}).get("env", {})
    assert env.get("META_GRAPH_VERSION") == "v26.0", trace_message(
        "WF-SOCIAL-NOTE-001", "social-note does not pin the tested Graph API contract"
    )
    assert "vars.META_GRAPH_VERSION" not in source, trace_message(
        "WF-SOCIAL-NOTE-001", "a stale repository variable can override Graph API v26.0"
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
    _, source, parsed = workflow(".github/workflows/social-daily.yml", "WF-SOCIAL-DAILY-001")
    for term in ("daily_owned", "dedupe", "concurrency", "meta-testing"):
        assert term in source, trace_message("WF-SOCIAL-DAILY-001", f"daily workflow lacks: {term}")
    env = parsed.get("jobs", {}).get("publish_daily_owned", {}).get("env", {})
    assert env.get("META_GRAPH_VERSION") == "v26.0", trace_message(
        "WF-SOCIAL-DAILY-001", "daily social flow does not pin Graph API v26.0"
    )
    assert "vars.META_GRAPH_VERSION" not in source, trace_message(
        "WF-SOCIAL-DAILY-001", "a stale repository variable can override Graph API v26.0"
    )


@pytest.mark.trace("WF-META-PREFLIGHT-001")
@pytest.mark.red_expected
def test_meta_preflight_is_manual_read_only_and_fail_closed() -> None:
    _, source, parsed = workflow(
        ".github/workflows/meta-preflight.yml", "WF-META-PREFLIGHT-001"
    )
    triggers = parsed.get("on", {})
    assert set(triggers) == {"workflow_dispatch", "push"}, trace_message(
        "WF-META-PREFLIGHT-001", "Meta preflight has an unexpected trigger surface"
    )
    push = triggers.get("push", {})
    assert push.get("branches") == ["main"], trace_message(
        "WF-META-PREFLIGHT-001", "automatic Meta preflight is not restricted to main"
    )
    assert set(push.get("paths", [])) == {
        ".github/workflows/meta-preflight.yml",
        "scripts/social/meta_preflight.py",
    }, trace_message(
        "WF-META-PREFLIGHT-001", "automatic Meta preflight can run for unrelated changes"
    )
    assert parsed.get("permissions") == {"contents": "read"}, trace_message(
        "WF-META-PREFLIGHT-001", "Meta preflight has write-capable GitHub permissions"
    )
    job = parsed.get("jobs", {}).get("validate_meta_testing", {})
    assert job.get("environment") == "meta-testing", trace_message(
        "WF-META-PREFLIGHT-001", "Meta preflight does not bind the testing environment"
    )
    env = job.get("env", {})
    assert env.get("META_GRAPH_VERSION") == "v26.0"
    assert env.get("META_ENVIRONMENT") == "testing"
    assert env.get("SOCIAL_ENABLED") == "0"
    assert env.get("SOCIAL_DRY_RUN") == "1"
    commands = job_run_commands(job)
    assert "python -m scripts.social.meta_preflight" in commands
    assert "${{ secrets." not in commands, trace_message(
        "WF-META-PREFLIGHT-001", "Meta secret is interpolated into a shell command"
    )
    forbidden = ("deliver-note", "deliver-draft", "publish-nota", "publish-library", "curl ")
    assert not any(term in commands for term in forbidden), trace_message(
        "WF-META-PREFLIGHT-001", "Meta preflight contains a publication-capable command"
    )


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
