from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.support.contracts import ROOT, trace_message

ACTIVE_RUNTIME_ROOTS = (
    ".agents/skills",
    ".automation",
    ".github/workflows",
    "assets/js/push.js",
    "scripts/automation",
    "scripts/social",
    "skills/instagram-post",
    "static/sw.js",
    "workers/push",
)

FROZEN_RUNTIME_TARGETS = (
    "scripts/push_server.py",
    "scripts/push_server.service",
    "scripts/tests/test_vision_deepseek.py",
)

CANONICAL_DOCUMENTATION = (
    "AGENTS.md",
    "README.md",
    "SECURITY.md",
    "ARCHITECTURE.md",
    "OPERATIONS.md",
)

RETIRED_DOCUMENTATION = (
    "HEARTBEAT.md",
    "IDENTITY.md",
    "SOUL.md",
    "USER.md",
    "TOOLS.md",
    "PLAN_CRON_RETRY.md",
    "PLAN_VISION_DEEPSEEK.md",
    "scripts/cloudflare-worker.js",
)

FORBIDDEN_RUNTIME_REFERENCE = re.compile(
    r"(?i)(?:\bopen[\s_-]*claw\b|\.openclaw(?:/|\\)|/home/openclaw(?:/|\b)|\bgateway\b)"
)


def runtime_files() -> list[Path]:
    files: set[Path] = set()
    for relative in ACTIVE_RUNTIME_ROOTS:
        candidate = ROOT / relative
        if candidate.is_file():
            files.add(candidate)
        elif candidate.is_dir():
            files.update(path for path in candidate.rglob("*") if path.is_file())
    return sorted(files)


@pytest.mark.trace("CUT-INDEP-001")
@pytest.mark.red_expected
def test_active_runtime_has_no_retired_user_or_gateway_dependency() -> None:
    violations: list[str] = []
    for path in runtime_files():
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if FORBIDDEN_RUNTIME_REFERENCE.search(source):
            violations.append(path.relative_to(ROOT).as_posix())
    assert not violations, trace_message(
        "CUT-INDEP-001",
        f"active runtime still references the retired user or gateway: {violations}",
    )


@pytest.mark.trace("CUT-INDEP-002")
@pytest.mark.red_expected
def test_retired_runtime_entrypoints_are_removed_from_final_architecture() -> None:
    remaining = [relative for relative in FROZEN_RUNTIME_TARGETS if (ROOT / relative).exists()]
    assert not remaining, trace_message(
        "CUT-INDEP-002",
        f"retired OpenClaw-only runtime entrypoints remain: {remaining}",
    )


@pytest.mark.trace("CUT-INDEP-003")
@pytest.mark.red_expected
def test_final_documentation_replaces_every_retired_instruction_file() -> None:
    missing = [relative for relative in CANONICAL_DOCUMENTATION if not (ROOT / relative).is_file()]
    remaining = [relative for relative in RETIRED_DOCUMENTATION if (ROOT / relative).exists()]
    assert not missing and not remaining, trace_message(
        "CUT-INDEP-003",
        f"documentation cutover is incomplete; missing={missing}, retired={remaining}",
    )


@pytest.mark.trace("CUT-INDEP-004")
@pytest.mark.red_expected
def test_canonical_documentation_has_no_retired_runtime_dependency() -> None:
    violations: list[str] = []
    for relative in CANONICAL_DOCUMENTATION:
        path = ROOT / relative
        if path.is_file() and FORBIDDEN_RUNTIME_REFERENCE.search(path.read_text(encoding="utf-8")):
            violations.append(relative)
    assert not violations, trace_message(
        "CUT-INDEP-004",
        f"canonical documentation still names a retired runtime dependency: {violations}",
    )


@pytest.mark.trace("CUT-INDEP-005")
@pytest.mark.red_expected
def test_agents_contract_is_brief_codex_native_and_tdd_guarded() -> None:
    source = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    required = ("Codex", "TDD", "RED", "GREEN", "apply_patch", "GitHub")
    forbidden = ("sessions_spawn", "git add .", "git status", "cron tool")
    assert len(source.splitlines()) <= 80, trace_message(
        "CUT-INDEP-005", "AGENTS.md must remain a brief repository contract"
    )
    assert all(token in source for token in required), trace_message(
        "CUT-INDEP-005", f"AGENTS.md is missing one of the required contracts: {required}"
    )
    assert not any(token in source for token in forbidden), trace_message(
        "CUT-INDEP-005", f"AGENTS.md retains an obsolete command: {forbidden}"
    )


@pytest.mark.trace("CUT-INDEP-006")
@pytest.mark.red_expected
def test_operations_documents_the_complete_schedule_and_delivery_contract() -> None:
    source = (ROOT / "OPERATIONS.md").read_text(encoding="utf-8")
    required = (
        "America/Cordoba",
        "0 18 * * *",
        "0 12 * * 0,3",
        "0 15 * * *",
        "15 15 * * *",
        "miércoles",
        "domingo",
        "Facebook",
        "Instagram",
        "Meta",
        "testing",
        "bienvenida",
        "idempotente",
    )
    assert all(token in source for token in required), trace_message(
        "CUT-INDEP-006", f"OPERATIONS.md is missing one of the required contracts: {required}"
    )


@pytest.mark.trace("CUT-INDEP-007")
@pytest.mark.red_expected
def test_architecture_assigns_one_authority_to_each_native_system() -> None:
    source = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
    required = (
        "Codex",
        "automatizaciones nativas",
        "GitHub Actions",
        "GitHub Pages",
        "Cloudflare Worker",
        "Meta Graph API",
        "content/notas/",
        ".automation/",
        "cf_worker.js",
        "static/sw.js",
        "assets/js/push.js",
    )
    assert all(token in source for token in required), trace_message(
        "CUT-INDEP-007", f"ARCHITECTURE.md is missing one of the required boundaries: {required}"
    )
