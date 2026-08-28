from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.contracts import trace_message
from tests.support.planned import planned_callable, planned_signature


TARGET = "scripts/automation/preflight.py"


@pytest.mark.trace("PREFLIGHT-001")
@pytest.mark.red_expected
def test_preflight_module_exposes_every_planned_guard_and_lock_function() -> None:
    signatures = {
        "assert_safe_root": ("root", "allowed_root"),
        "assert_clean_base": ("root",),
        "assert_disk_space": ("path", "required_bytes"),
        "assert_no_live_side_effects": ("environment",),
        "acquire_lock": ("lock_path", "owner", "now"),
        "release_lock": ("lock_path", "owner"),
    }
    for symbol, parameters in signatures.items():
        planned_signature(TARGET, symbol, parameters, "PREFLIGHT-001")


@pytest.mark.trace("PREFLIGHT-002")
@pytest.mark.red_expected
def test_safe_root_accepts_real_descendant_with_repository_marker(tmp_path: Path) -> None:
    assert_safe_root = planned_callable(TARGET, "assert_safe_root", "PREFLIGHT-002")
    allowed = tmp_path / "projects"
    root = allowed / "mragentes-site"
    (root / ".git").mkdir(parents=True)
    result = assert_safe_root(root, allowed_root=allowed, marker=".git")
    assert Path(result) == root.resolve(), trace_message(
        "PREFLIGHT-002", "safe canonical repository root was rejected"
    )


@pytest.mark.trace("PREFLIGHT-003")
@pytest.mark.red_expected
def test_safe_root_rejects_missing_marker_parent_and_relative_escape(tmp_path: Path) -> None:
    assert_safe_root = planned_callable(TARGET, "assert_safe_root", "PREFLIGHT-003")
    allowed = tmp_path / "projects"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    for root in (allowed, outside, allowed / ".." / "outside"):
        with pytest.raises(ValueError):
            assert_safe_root(root, allowed_root=allowed, marker=".git")


@pytest.mark.trace("PREFLIGHT-004")
@pytest.mark.red_expected
def test_safe_root_rejects_symlink_that_resolves_outside_allowed_root(tmp_path: Path) -> None:
    assert_safe_root = planned_callable(TARGET, "assert_safe_root", "PREFLIGHT-004")
    allowed = tmp_path / "projects"
    outside = tmp_path / "outside"
    (outside / ".git").mkdir(parents=True)
    allowed.mkdir()
    link = allowed / "linked-repo"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        assert_safe_root(link, allowed_root=allowed, marker=".git")


@pytest.mark.trace("PREFLIGHT-005")
@pytest.mark.red_expected
def test_clean_base_accepts_empty_status_and_returns_normalized_summary(tmp_path: Path) -> None:
    assert_clean = planned_callable(TARGET, "assert_clean_base", "PREFLIGHT-005")
    result = assert_clean(tmp_path, status_provider=lambda _: "")
    assert result == {"clean": True, "changes": []}, trace_message(
        "PREFLIGHT-005", f"clean status summary is wrong: {result}"
    )


@pytest.mark.trace("PREFLIGHT-006")
@pytest.mark.red_expected
def test_clean_base_allows_declared_tdd_paths_and_rejects_product_dirt(tmp_path: Path) -> None:
    assert_clean = planned_callable(TARGET, "assert_clean_base", "PREFLIGHT-006")
    allowed = "?? tests/unit/new_test.py\n?? .testplan/evidence.json\n"
    result = assert_clean(tmp_path, allowed_paths=("tests/", ".testplan/"), status_provider=lambda _: allowed)
    assert result["clean"] is True, trace_message("PREFLIGHT-006", "declared TDD paths were rejected")
    dirty = " M scripts/publish_blog.py\n"
    with pytest.raises(RuntimeError, match="dirty"):
        assert_clean(tmp_path, allowed_paths=("tests/",), status_provider=lambda _: dirty)


@pytest.mark.trace("PREFLIGHT-007")
@pytest.mark.red_expected
def test_disk_space_accepts_exact_boundary_and_reports_headroom(tmp_path: Path) -> None:
    assert_disk = planned_callable(TARGET, "assert_disk_space", "PREFLIGHT-007")

    class Stat:
        f_bavail = 10
        f_frsize = 4096

    result = assert_disk(tmp_path, required_bytes=40_960, statvfs=lambda _: Stat())
    assert result == {"available_bytes": 40_960, "required_bytes": 40_960, "headroom_bytes": 0}, trace_message(
        "PREFLIGHT-007", f"disk boundary summary is wrong: {result}"
    )


@pytest.mark.trace("PREFLIGHT-008")
@pytest.mark.red_expected
def test_disk_space_failure_and_stat_error_create_no_partial_files(tmp_path: Path) -> None:
    assert_disk = planned_callable(TARGET, "assert_disk_space", "PREFLIGHT-008")
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    class Stat:
        f_bavail = 1
        f_frsize = 4096

    with pytest.raises(OSError):
        assert_disk(tmp_path, required_bytes=4097, statvfs=lambda _: Stat())

    def fail(_: Path) -> object:
        raise OSError("synthetic stat failure")

    with pytest.raises(OSError, match="stat"):
        assert_disk(tmp_path, required_bytes=1, statvfs=fail)
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert after == before, trace_message(
        "PREFLIGHT-008", "disk preflight wrote a partial artifact"
    )


@pytest.mark.trace("PREFLIGHT-009")
@pytest.mark.red_expected
def test_live_side_effect_guard_blocks_production_flags_tokens_and_local_publish() -> None:
    guard = planned_callable(TARGET, "assert_no_live_side_effects", "PREFLIGHT-009")
    safe = {"DRY_RUN": "1", "SOCIAL_LOCAL_PUBLISH": "0", "ENVIRONMENT": "test"}
    assert guard(safe) == {"safe": True, "environment": "test"}, trace_message(
        "PREFLIGHT-009", "safe dry-run environment rejected"
    )
    unsafe = (
        {"DRY_RUN": "0"},
        {"SOCIAL_LOCAL_PUBLISH": "1"},
        {"ENVIRONMENT": "production"},
        {"META_ACCESS_TOKEN": "synthetic"},
        {"PUSH_API_TOKEN": "synthetic"},
    )
    for environment in unsafe:
        with pytest.raises(PermissionError):
            guard(environment)


@pytest.mark.trace("PREFLIGHT-010")
@pytest.mark.red_expected
def test_first_lock_is_created_atomically_with_owner_and_expiry(tmp_path: Path) -> None:
    acquire = planned_callable(TARGET, "acquire_lock", "PREFLIGHT-010")
    lock = tmp_path / "news.lock"
    result = acquire(
        lock,
        owner="news-run-1",
        now="2026-08-26T12:00:00Z",
        ttl_seconds=3600,
    )
    data = json.loads(lock.read_text(encoding="utf-8"))
    assert result["acquired"] is True and data["owner"] == "news-run-1", trace_message(
        "PREFLIGHT-010", "lock owner was not persisted"
    )
    assert data["expires_at"] == "2026-08-26T13:00:00Z", trace_message(
        "PREFLIGHT-010", "lock expiry is wrong"
    )


@pytest.mark.trace("PREFLIGHT-011")
@pytest.mark.red_expected
def test_live_competitor_is_blocked_but_expired_lock_can_be_reclaimed_with_audit(tmp_path: Path) -> None:
    acquire = planned_callable(TARGET, "acquire_lock", "PREFLIGHT-011")
    lock = tmp_path / "news.lock"
    lock.write_text(
        json.dumps({"owner": "old-run", "acquired_at": "2026-08-26T10:00:00Z", "expires_at": "2026-08-26T13:00:00Z"}),
        encoding="utf-8",
    )
    with pytest.raises((BlockingIOError, TimeoutError)):
        acquire(lock, owner="new-run", now="2026-08-26T12:00:00Z", ttl_seconds=3600)
    result = acquire(lock, owner="new-run", now="2026-08-26T14:00:00Z", ttl_seconds=3600)
    assert result["acquired"] is True and result["reclaimed_from"] == "old-run", trace_message(
        "PREFLIGHT-011", "expired lock was not reclaimed with audit"
    )


@pytest.mark.trace("PREFLIGHT-012")
@pytest.mark.red_expected
def test_release_lock_requires_owner_and_is_idempotent_after_success(tmp_path: Path) -> None:
    acquire = planned_callable(TARGET, "acquire_lock", "PREFLIGHT-012")
    release = planned_callable(TARGET, "release_lock", "PREFLIGHT-012")
    lock = tmp_path / "news.lock"
    acquire(lock, owner="news-run-1", now="2026-08-26T12:00:00Z", ttl_seconds=3600)
    with pytest.raises(PermissionError):
        release(lock, owner="other-run")
    assert release(lock, owner="news-run-1")["released"] is True, trace_message(
        "PREFLIGHT-012", "owner could not release lock"
    )
    assert release(lock, owner="news-run-1") == {"released": False, "reason": "absent"}, trace_message(
        "PREFLIGHT-012", "second release was not idempotent"
    )
