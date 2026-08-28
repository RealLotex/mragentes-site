from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from tests.support.contracts import load_python_target


TARGET = "scripts/social/ledger.py"
NOW = "2026-08-26T16:00:00+00:00"


@dataclass
class FakeMeta:
    failures: dict[str, str] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)
    recent: dict[str, list[dict]] = field(
        default_factory=lambda: {"facebook": [], "instagram": []}
    )

    def publish(self, platform: str) -> dict:
        self.calls.append(platform)
        if platform in self.failures:
            raise TimeoutError(self.failures[platform])
        remote_id = f"{platform}-{len(self.calls)}"
        return {
            "platform": platform,
            "remote_id": remote_id,
            "permalink": f"https://{platform}.example/{remote_id}",
        }


def _module(trace_id: str):
    return load_python_target(TARGET, trace_id)


def _acquire(module, path: Path, *, kind: str = "daily_owned", key: str | None = None):
    key = key or f"social:{kind}:2026-08-26"
    return module.acquire(
        path,
        dedupe_key=key,
        content_hash=f"sha256:{kind}-content",
        kind=kind,
        local_date="2026-08-26",
        run_id=key,
        now=NOW,
    )


def _publish_and_checkpoint(module, path: Path, key: str, meta: FakeMeta, platform: str) -> dict:
    remote = meta.publish(platform)
    module.checkpoint(
        path,
        dedupe_key=key,
        platform=platform,
        remote_id=remote["remote_id"],
        permalink=remote["permalink"],
        now=NOW,
    )
    return remote


@pytest.mark.trace("SOCIAL-RECOVER-005")
@pytest.mark.red_expected
def test_complete_run_rerun_skips_both_meta_platforms(tmp_path: Path) -> None:
    module = _module("SOCIAL-RECOVER-005")
    ledger_path = tmp_path / "ledger.json"
    key = "social:daily_owned:2026-08-26"
    meta = FakeMeta()
    assert _acquire(module, ledger_path)["decision"] == "acquired"
    for platform in ("facebook", "instagram"):
        _publish_and_checkpoint(module, ledger_path, key, meta, platform)
    module.complete(ledger_path, dedupe_key=key, now=NOW)

    second = _acquire(module, ledger_path)

    assert second["decision"] == "skip_complete"
    assert module.recovery_plan(second["entry"])["decision"] == "skip_complete"
    assert meta.calls == ["facebook", "instagram"]


@pytest.mark.trace("SOCIAL-RECOVER-006")
@pytest.mark.red_expected
def test_partial_run_recovery_publishes_only_missing_instagram(tmp_path: Path) -> None:
    module = _module("SOCIAL-RECOVER-006")
    ledger_path = tmp_path / "ledger.json"
    key = "social:daily_owned:2026-08-26"
    meta = FakeMeta(failures={"instagram": "temporary timeout"})
    _acquire(module, ledger_path)
    _publish_and_checkpoint(module, ledger_path, key, meta, "facebook")
    with pytest.raises(TimeoutError):
        meta.publish("instagram")
    module.mark_partial(
        ledger_path,
        dedupe_key=key,
        platform="instagram",
        category="retryable",
        reason="temporary timeout",
        now=NOW,
    )

    entry = module.load_ledger(ledger_path)["entries"][key]
    plan = module.recovery_plan(entry)
    assert plan == {"decision": "publish_missing", "platforms": ["instagram"]}
    meta.failures.clear()
    for platform in plan["platforms"]:
        _publish_and_checkpoint(module, ledger_path, key, meta, platform)
    module.complete(ledger_path, dedupe_key=key, now=NOW)

    assert meta.calls == ["facebook", "instagram", "instagram"]
    assert meta.calls.count("facebook") == 1
    assert module.load_ledger(ledger_path)["entries"][key]["status"] == "complete"


@pytest.mark.trace("SOCIAL-RECOVER-007")
@pytest.mark.red_expected
def test_crash_after_remote_facebook_before_checkpoint_reconstructs_then_only_publishes_ig(
    tmp_path: Path,
) -> None:
    module = _module("SOCIAL-RECOVER-007")
    ledger_path = tmp_path / "ledger.json"
    key = "social:daily_owned:2026-08-26"
    meta = FakeMeta()
    _acquire(module, ledger_path)

    remote = meta.publish("facebook")
    expected = {
        "platform": "facebook",
        "caption_hash": "sha256:caption",
        "asset_hash": "sha256:asset",
        "created_at": NOW,
    }
    recent = [
        {
            **expected,
            **remote,
            "created_at": "2026-08-26T16:01:00+00:00",
        }
    ]
    match = module.find_recent_match(expected, recent, tolerance_seconds=900)
    assert match["decision"] == "matched"
    module.checkpoint(
        ledger_path,
        dedupe_key=key,
        platform="facebook",
        remote_id=match["match"]["remote_id"],
        permalink=match["match"]["permalink"],
        now=NOW,
    )

    plan = module.recovery_plan(module.load_ledger(ledger_path)["entries"][key])
    assert plan == {"decision": "publish_missing", "platforms": ["instagram"]}
    _publish_and_checkpoint(module, ledger_path, key, meta, "instagram")
    module.complete(ledger_path, dedupe_key=key, now=NOW)
    assert meta.calls == ["facebook", "instagram"]


@pytest.mark.trace("SOCIAL-RECOVER-008")
@pytest.mark.red_expected
def test_ambiguous_remote_matches_stop_for_review_without_any_new_publish(tmp_path: Path) -> None:
    module = _module("SOCIAL-RECOVER-008")
    ledger_path = tmp_path / "ledger.json"
    _acquire(module, ledger_path)
    expected = {
        "platform": "facebook",
        "caption_hash": "sha256:caption",
        "asset_hash": "sha256:asset",
        "created_at": NOW,
    }
    recent = [
        {
            **expected,
            "remote_id": remote_id,
            "created_at": f"2026-08-26T16:0{minute}:00+00:00",
        }
        for remote_id, minute in (("fb-1", 1), ("fb-2", 2))
    ]
    outcome = module.find_recent_match(expected, recent, tolerance_seconds=900)
    meta = FakeMeta()

    assert outcome["decision"] == "needs_review"
    assert meta.calls == []


@pytest.mark.trace("SOCIAL-RECOVER-009")
@pytest.mark.red_expected
def test_blog_note_and_daily_owned_same_date_have_independent_dedupe_and_recovery(
    tmp_path: Path,
) -> None:
    module = _module("SOCIAL-RECOVER-009")
    ledger_path = tmp_path / "ledger.json"
    daily_key = "social:daily_owned:2026-08-26"
    note_key = "social:blog_note:nota-slug"
    _acquire(module, ledger_path, kind="blog_note", key=note_key)
    for platform in ("facebook", "instagram"):
        module.checkpoint(
            ledger_path,
            dedupe_key=note_key,
            platform=platform,
            remote_id=f"note-{platform}",
            permalink="",
            now=NOW,
        )
    module.complete(ledger_path, dedupe_key=note_key, now=NOW)

    daily = _acquire(module, ledger_path, kind="daily_owned", key=daily_key)
    ledger = module.load_ledger(ledger_path)

    assert daily["decision"] == "acquired"
    assert set(ledger["entries"]) == {note_key, daily_key}
    assert ledger["entries"][note_key]["kind"] == "blog_note"
    assert ledger["entries"][daily_key]["kind"] == "daily_owned"
    assert module.recovery_plan(ledger["entries"][daily_key])["platforms"] == [
        "facebook",
        "instagram",
    ]


@pytest.mark.trace("SOCIAL-RECOVER-010")
@pytest.mark.red_expected
def test_uncertain_timeout_never_auto_republishes_until_recent_probe_resolves(tmp_path: Path) -> None:
    module = _module("SOCIAL-RECOVER-010")
    ledger_path = tmp_path / "ledger.json"
    key = "social:daily_owned:2026-08-26"
    _acquire(module, ledger_path)
    module.mark_partial(
        ledger_path,
        dedupe_key=key,
        platform="facebook",
        category="uncertain",
        reason="connection closed after request body",
        now=NOW,
    )
    entry = module.load_ledger(ledger_path)["entries"][key]
    plan = module.recovery_plan(entry)
    meta = FakeMeta()

    assert plan["decision"] == "needs_review"
    assert plan["platforms"] == []
    assert meta.calls == []
