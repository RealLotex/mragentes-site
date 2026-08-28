from __future__ import annotations

import copy
import inspect
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tests.support.contracts import load_python_target, trace_message


LEGACY_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "social" / "legacy_state.json"
TARGET = "scripts/social/ledger.py"
NOW = "2026-08-26T16:00:00+00:00"


def _ledger(trace_id: str):
    return load_python_target(TARGET, trace_id)


def _require_api(module, trace_id: str, *names: str) -> None:
    missing = [name for name in names if not callable(getattr(module, name, None))]
    assert not missing, trace_message(trace_id, f"missing ledger callables: {missing}")


def _acquire(module, path: Path, **overrides):
    values = {
        "dedupe_key": "social:daily_owned:2026-08-26",
        "content_hash": "sha256:content-one",
        "kind": "daily_owned",
        "local_date": "2026-08-26",
        "run_id": "social:daily_owned:2026-08-26",
        "now": NOW,
    }
    values.update(overrides)
    return module.acquire(path, **values)


@pytest.mark.trace("SOCIAL-LEDGER-001")
@pytest.mark.red_expected
def test_ledger_module_exposes_path_based_atomic_api_with_injected_time() -> None:
    module = _ledger("SOCIAL-LEDGER-001")
    required = (
        "load_ledger",
        "save_ledger",
        "migrate_legacy_state",
        "acquire",
        "checkpoint",
        "complete",
        "mark_partial",
        "find_recent_match",
        "recovery_plan",
    )
    _require_api(module, "SOCIAL-LEDGER-001", *required)
    for name in ("acquire", "checkpoint", "complete", "mark_partial"):
        signature = inspect.signature(getattr(module, name))
        assert "path" in signature.parameters, trace_message(
            "SOCIAL-LEDGER-001", f"{name} must persist through a path"
        )
        assert "now" in signature.parameters, trace_message(
            "SOCIAL-LEDGER-001", f"{name} must receive injected time"
        )


@pytest.mark.trace("SOCIAL-LEDGER-002")
@pytest.mark.red_expected
def test_load_ledger_initializes_missing_file_but_fails_closed_on_corruption(tmp_path: Path) -> None:
    module = _ledger("SOCIAL-LEDGER-002")
    missing = tmp_path / "missing.json"
    assert module.load_ledger(missing) == {"schema_version": 1, "entries": {}}

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{bad", encoding="utf-8")
    error_type = getattr(module, "LedgerCorrupt", RuntimeError)
    with pytest.raises(error_type, match="corrupt|JSON|ledger"):
        module.load_ledger(corrupt)


@pytest.mark.trace("SOCIAL-LEDGER-003")
@pytest.mark.red_expected
def test_migrate_legacy_state_is_idempotent_typed_and_preserves_confirmed_ids(
    tmp_path: Path,
) -> None:
    module = _ledger("SOCIAL-LEDGER-003")
    legacy = json.loads(LEGACY_FIXTURE.read_text(encoding="utf-8"))
    legacy_before = copy.deepcopy(legacy)
    destination = tmp_path / "ledger.json"
    kinds = {"nota-historica": "blog_note", "pieza-diaria": "daily_owned"}

    first = module.migrate_legacy_state(legacy, destination, kinds=kinds, now=NOW)
    second = module.migrate_legacy_state(legacy, destination, kinds=kinds, now=NOW)

    assert first == second == module.load_ledger(destination)
    assert legacy == legacy_before
    assert len(first["entries"]) == 2
    by_kind = {entry["kind"]: entry for entry in first["entries"].values()}
    assert by_kind["blog_note"]["platforms"]["facebook"]["remote_id"] == "fb-note-1"
    assert by_kind["blog_note"]["platforms"]["instagram"]["remote_id"] == "ig-note-1"
    assert by_kind["daily_owned"]["platforms"]["facebook"]["remote_id"] == "fb-daily-1"
    assert by_kind["daily_owned"]["status"] == "partial"


@pytest.mark.trace("SOCIAL-LEDGER-004")
@pytest.mark.red_expected
def test_acquire_creates_once_then_resumes_same_incomplete_run(tmp_path: Path) -> None:
    module = _ledger("SOCIAL-LEDGER-004")
    target = tmp_path / "ledger.json"

    first = _acquire(module, target)
    second = _acquire(module, target, run_id="replacement-run-must-not-win")
    stored = module.load_ledger(target)["entries"]["social:daily_owned:2026-08-26"]

    assert first["decision"] == "acquired"
    assert second["decision"] == "resume"
    assert first["entry"]["run_id"] == stored["run_id"] == "social:daily_owned:2026-08-26"
    assert stored["content_hash"] == "sha256:content-one"
    assert stored["status"] == "in_progress"


@pytest.mark.trace("SOCIAL-LEDGER-005")
@pytest.mark.red_expected
def test_acquire_skips_complete_same_hash_and_rejects_same_key_different_hash(tmp_path: Path) -> None:
    module = _ledger("SOCIAL-LEDGER-005")
    target = tmp_path / "ledger.json"
    _acquire(module, target)
    for platform, remote_id in (("facebook", "fb-1"), ("instagram", "ig-1")):
        module.checkpoint(
            target,
            dedupe_key="social:daily_owned:2026-08-26",
            platform=platform,
            remote_id=remote_id,
            permalink=f"https://{platform}.example/{remote_id}",
            now=NOW,
        )
    module.complete(target, dedupe_key="social:daily_owned:2026-08-26", now=NOW)

    assert _acquire(module, target)["decision"] == "skip_complete"
    conflict_type = getattr(module, "LedgerConflict", RuntimeError)
    with pytest.raises(conflict_type, match="hash|content|conflict"):
        _acquire(module, target, content_hash="sha256:different")


@pytest.mark.trace("SOCIAL-LEDGER-006")
@pytest.mark.red_expected
def test_concurrent_acquire_serializes_to_one_entry_and_one_owner(tmp_path: Path) -> None:
    module = _ledger("SOCIAL-LEDGER-006")
    target = tmp_path / "ledger.json"

    def invoke(index: int):
        return _acquire(module, target, run_id=f"run-{index}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(invoke, (1, 2)))

    assert sorted(result["decision"] for result in results) == ["acquired", "resume"]
    ledger = module.load_ledger(target)
    assert list(ledger["entries"]) == ["social:daily_owned:2026-08-26"]
    assert ledger["entries"]["social:daily_owned:2026-08-26"]["run_id"] in {"run-1", "run-2"}


@pytest.mark.trace("SOCIAL-LEDGER-007")
@pytest.mark.red_expected
def test_checkpoint_records_platform_independently_and_is_idempotent(tmp_path: Path) -> None:
    module = _ledger("SOCIAL-LEDGER-007")
    target = tmp_path / "ledger.json"
    _acquire(module, target)
    kwargs = {
        "dedupe_key": "social:daily_owned:2026-08-26",
        "platform": "facebook",
        "remote_id": "fb-1",
        "permalink": "https://facebook.example/fb-1",
        "now": NOW,
    }

    first = module.checkpoint(target, **kwargs)
    second = module.checkpoint(target, **kwargs)

    assert first == second
    entry = module.load_ledger(target)["entries"][kwargs["dedupe_key"]]
    assert entry["platforms"]["facebook"] == {
        "status": "confirmed",
        "remote_id": "fb-1",
        "permalink": "https://facebook.example/fb-1",
        "confirmed_at": NOW,
    }
    assert entry["platforms"].get("instagram", {}).get("status") != "confirmed"


@pytest.mark.trace("SOCIAL-LEDGER-008")
@pytest.mark.red_expected
def test_checkpoint_rejects_unknown_platform_empty_id_and_conflicting_remote_id(tmp_path: Path) -> None:
    module = _ledger("SOCIAL-LEDGER-008")
    target = tmp_path / "ledger.json"
    key = "social:daily_owned:2026-08-26"
    _acquire(module, target)
    for platform, remote_id in (("tiktok", "remote"), ("facebook", "")):
        with pytest.raises(ValueError, match="platform|remote|id"):
            module.checkpoint(
                target,
                dedupe_key=key,
                platform=platform,
                remote_id=remote_id,
                permalink="",
                now=NOW,
            )

    module.checkpoint(
        target,
        dedupe_key=key,
        platform="facebook",
        remote_id="fb-1",
        permalink="",
        now=NOW,
    )
    conflict_type = getattr(module, "LedgerConflict", RuntimeError)
    with pytest.raises(conflict_type, match="remote|conflict|facebook"):
        module.checkpoint(
            target,
            dedupe_key=key,
            platform="facebook",
            remote_id="fb-2",
            permalink="",
            now=NOW,
        )


@pytest.mark.trace("SOCIAL-LEDGER-009")
@pytest.mark.red_expected
def test_complete_requires_all_requested_platforms_and_then_freezes_entry(tmp_path: Path) -> None:
    module = _ledger("SOCIAL-LEDGER-009")
    target = tmp_path / "ledger.json"
    key = "social:daily_owned:2026-08-26"
    _acquire(module, target)
    module.checkpoint(
        target,
        dedupe_key=key,
        platform="facebook",
        remote_id="fb-1",
        permalink="",
        now=NOW,
    )
    with pytest.raises(ValueError, match="instagram|missing|platform"):
        module.complete(target, dedupe_key=key, now=NOW)

    module.checkpoint(
        target,
        dedupe_key=key,
        platform="instagram",
        remote_id="ig-1",
        permalink="",
        now=NOW,
    )
    completed = module.complete(target, dedupe_key=key, now=NOW)
    assert completed["status"] == "complete"
    assert completed["completed_at"] == NOW


@pytest.mark.trace("SOCIAL-LEDGER-010")
@pytest.mark.red_expected
def test_mark_partial_preserves_confirmed_platform_and_marks_uncertain_without_secrets(
    tmp_path: Path,
) -> None:
    module = _ledger("SOCIAL-LEDGER-010")
    target = tmp_path / "ledger.json"
    key = "social:daily_owned:2026-08-26"
    _acquire(module, target)
    module.checkpoint(
        target,
        dedupe_key=key,
        platform="facebook",
        remote_id="fb-1",
        permalink="",
        now=NOW,
    )
    secret = "EAAB-secret-sentinel"
    partial = module.mark_partial(
        target,
        dedupe_key=key,
        platform="instagram",
        category="uncertain",
        reason=f"timeout access_token={secret}",
        now=NOW,
    )

    assert partial["status"] == "partial"
    assert partial["platforms"]["facebook"]["remote_id"] == "fb-1"
    assert partial["platforms"]["instagram"]["status"] == "uncertain"
    assert secret not in json.dumps(module.load_ledger(target))


@pytest.mark.trace("SOCIAL-LEDGER-011")
@pytest.mark.red_expected
def test_find_recent_match_requires_platform_hashes_and_time_tolerance() -> None:
    module = _ledger("SOCIAL-LEDGER-011")
    expected = {
        "platform": "facebook",
        "caption_hash": "sha256:caption-one",
        "asset_hash": "sha256:asset-one",
        "created_at": "2026-08-26T16:00:00+00:00",
    }
    recent = [
        {
            "platform": "facebook",
            "remote_id": "too-old",
            "caption_hash": "sha256:caption-one",
            "asset_hash": "sha256:asset-one",
            "created_at": "2026-08-26T14:00:00+00:00",
        },
        {
            "platform": "facebook",
            "remote_id": "match",
            "caption_hash": "sha256:caption-one",
            "asset_hash": "sha256:asset-one",
            "created_at": "2026-08-26T16:02:00+00:00",
            "permalink": "https://facebook.example/match",
        },
        {
            "platform": "instagram",
            "remote_id": "wrong-platform",
            "caption_hash": "sha256:caption-one",
            "asset_hash": "sha256:asset-one",
            "created_at": "2026-08-26T16:01:00+00:00",
        },
    ]

    outcome = module.find_recent_match(expected, recent, tolerance_seconds=900)

    assert outcome["decision"] == "matched"
    assert outcome["match"]["remote_id"] == "match"


@pytest.mark.trace("SOCIAL-LEDGER-012")
@pytest.mark.red_expected
def test_find_recent_match_returns_none_or_needs_review_for_ambiguity() -> None:
    module = _ledger("SOCIAL-LEDGER-012")
    expected = {
        "platform": "instagram",
        "caption_hash": "sha256:caption-one",
        "asset_hash": "sha256:asset-one",
        "created_at": "2026-08-26T16:00:00+00:00",
    }
    assert module.find_recent_match(expected, [], tolerance_seconds=900) == {
        "decision": "none",
        "match": None,
    }
    candidates = [
        {
            **expected,
            "remote_id": remote_id,
            "created_at": f"2026-08-26T16:0{minute}:00+00:00",
        }
        for remote_id, minute in (("ig-1", 1), ("ig-2", 2))
    ]
    ambiguous = module.find_recent_match(expected, candidates, tolerance_seconds=900)
    assert ambiguous["decision"] == "needs_review"
    assert {match["remote_id"] for match in ambiguous["matches"]} == {"ig-1", "ig-2"}


@pytest.mark.trace("SOCIAL-LEDGER-013")
@pytest.mark.red_expected
def test_recovery_plan_skips_complete_retries_only_missing_and_blocks_uncertain() -> None:
    module = _ledger("SOCIAL-LEDGER-013")
    base = {
        "dedupe_key": "social:daily_owned:2026-08-26",
        "kind": "daily_owned",
        "platforms": {
            "facebook": {"status": "confirmed", "remote_id": "fb-1"},
            "instagram": {"status": "confirmed", "remote_id": "ig-1"},
        },
    }
    complete = {**base, "status": "complete"}
    assert module.recovery_plan(complete)["decision"] == "skip_complete"

    partial = copy.deepcopy(base)
    partial["status"] = "partial"
    partial["platforms"]["instagram"] = {"status": "failed", "category": "retryable"}
    assert module.recovery_plan(partial) == {
        "decision": "publish_missing",
        "platforms": ["instagram"],
    }

    uncertain = copy.deepcopy(partial)
    uncertain["platforms"]["instagram"] = {"status": "uncertain"}
    assert module.recovery_plan(uncertain)["decision"] == "needs_review"
    assert module.recovery_plan(uncertain)["platforms"] == []


@pytest.mark.trace("SOCIAL-LEDGER-014")
@pytest.mark.red_expected
def test_save_ledger_is_atomic_if_final_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _ledger("SOCIAL-LEDGER-014")
    target = tmp_path / "ledger.json"
    original = {"schema_version": 1, "entries": {"safe": {"status": "complete"}}}
    target.write_text(json.dumps(original) + "\n", encoding="utf-8")

    def fail_replace(*args, **kwargs):
        del args, kwargs
        raise OSError("simulated atomic replace failure")

    if hasattr(module, "os"):
        monkeypatch.setattr(module.os, "replace", fail_replace)
    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failure"):
        module.save_ledger({"schema_version": 1, "entries": {}}, target)
    assert json.loads(target.read_text(encoding="utf-8")) == original


@pytest.mark.trace("SOCIAL-LEDGER-015")
@pytest.mark.red_expected
def test_ledger_rejects_unknown_schema_extra_platforms_and_invalid_dedupe_key(tmp_path: Path) -> None:
    module = _ledger("SOCIAL-LEDGER-015")
    invalid_documents = (
        {"schema_version": 999, "entries": {}},
        {"schema_version": 1, "entries": [], "extra": True},
    )
    error_type = getattr(module, "LedgerCorrupt", RuntimeError)
    for index, document in enumerate(invalid_documents):
        target = tmp_path / f"invalid-{index}.json"
        target.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(error_type, match="schema|ledger|entries"):
            module.load_ledger(target)

    with pytest.raises(ValueError, match="dedupe|key"):
        _acquire(module, tmp_path / "ledger.json", dedupe_key="../unsafe")


@pytest.mark.trace("SOCIAL-LEDGER-016")
@pytest.mark.red_expected
def test_complete_ledger_contains_only_operational_metadata_never_tokens_or_caption_body(
    tmp_path: Path,
) -> None:
    module = _ledger("SOCIAL-LEDGER-016")
    target = tmp_path / "ledger.json"
    _acquire(module, target)
    for platform in ("facebook", "instagram"):
        module.checkpoint(
            target,
            dedupe_key="social:daily_owned:2026-08-26",
            platform=platform,
            remote_id=f"{platform}-1",
            permalink=f"https://{platform}.example/1",
            now=NOW,
        )
    module.complete(target, dedupe_key="social:daily_owned:2026-08-26", now=NOW)

    serialized = target.read_text(encoding="utf-8")
    assert "access_token" not in serialized
    assert "META_ACCESS_TOKEN" not in serialized
    assert "caption" not in serialized
    assert len(serialized) < 8_000
