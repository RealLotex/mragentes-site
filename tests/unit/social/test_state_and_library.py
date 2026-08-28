from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

from scripts.social import library, should_retry_today, state
from scripts.social import templates as template_module


@pytest.mark.trace("SOCIAL-STATE-001")
@pytest.mark.baseline_green
def test_state_load_missing_returns_independent_empty_documents(tmp_path: Path) -> None:
    first = state.load(tmp_path / "missing.json")
    second = state.load(tmp_path / "missing.json")

    assert first["version"] >= 2
    assert first["published"] == {}
    first["published"]["mutated"] = {"facebook": "1"}
    assert second["published"] == {}


@pytest.mark.trace("SOCIAL-STATE-002")
@pytest.mark.baseline_green
def test_state_load_recovers_legacy_missing_fields_and_invalid_json(tmp_path: Path) -> None:
    incomplete = tmp_path / "incomplete.json"
    incomplete.write_text('{"custom": true}', encoding="utf-8")
    loaded = state.load(incomplete)
    assert loaded["custom"] is True
    assert loaded["published"] == {}
    assert loaded["version"] >= 2

    broken = tmp_path / "broken.json"
    broken.write_text("{broken", encoding="utf-8")
    assert state.load(broken)["published"] == {}


@pytest.mark.trace("SOCIAL-STATE-003")
@pytest.mark.baseline_green
def test_state_save_round_trips_unicode_and_terminating_newline(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "state.json"
    payload = {"version": 2, "published": {"día": {"facebook": "á-1"}}}

    state.save(payload, target)

    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert target.read_bytes().endswith(b"\n")


@pytest.mark.trace("SOCIAL-STATE-004")
@pytest.mark.baseline_green
def test_is_published_requires_a_confirmed_platform_identifier() -> None:
    document = {
        "published": {
            "none": {"date": "2026-08-26", "images": ["one.jpg"]},
            "fb": {"facebook": "fb-1"},
            "ig": {"instagram": "ig-1"},
        }
    }

    assert state.is_published("missing", document) is False
    assert state.is_published("none", document) is False
    assert state.is_published("fb", document) is True
    assert state.is_published("ig", document) is True


@pytest.mark.trace("SOCIAL-STATE-005")
@pytest.mark.baseline_green
def test_record_merges_truthy_checkpoints_without_erasing_previous_platform() -> None:
    document = {"version": 2, "published": {}}
    original_results = {"date": "2026-08-26", "facebook": "fb-1", "instagram": ""}

    returned = state.record("daily", original_results, document, save_now=False)
    state.record("daily", {"instagram": "ig-1", "facebook": None}, document, save_now=False)

    assert returned is document
    assert document["published"]["daily"]["facebook"] == "fb-1"
    assert document["published"]["daily"]["instagram"] == "ig-1"
    assert document["published"]["daily"]["date"] == "2026-08-26"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", document["published"]["daily"]["updated"])
    assert original_results == {"date": "2026-08-26", "facebook": "fb-1", "instagram": ""}


@pytest.mark.trace("SOCIAL-STATE-006")
@pytest.mark.red_expected
def test_state_save_is_atomic_when_serialization_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state.json"
    original = '{"version": 2, "published": {"safe": {"facebook": "fb-1"}}}\n'
    target.write_text(original, encoding="utf-8")
    real_write_text = Path.write_text

    def interrupted_write(path: Path, data: str, *args, **kwargs):
        if path == target:
            real_write_text(path, data[:9], *args, **kwargs)
            raise OSError("simulated interrupted write")
        return real_write_text(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", interrupted_write)

    with pytest.raises(OSError, match="interrupted"):
        state.save({"version": 3, "published": {}}, target)
    assert target.read_text(encoding="utf-8") == original


@pytest.mark.trace("SOCIAL-STATE-007")
@pytest.mark.baseline_green
def test_state_contract_distinguishes_kind_date_and_each_platform_checkpoint() -> None:
    document = {"version": 3, "published": {}}

    state.record(
        "social:daily_owned:2026-08-26",
        {
            "kind": "daily_owned",
            "local_date": "2026-08-26",
            "dedupe_key": "social:daily_owned:2026-08-26",
            "content_hash": "sha256:daily",
            "platforms": {"facebook": {"status": "confirmed", "remote_id": "fb-1"}},
        },
        document,
        save_now=False,
    )

    entry = document["published"]["social:daily_owned:2026-08-26"]
    assert entry["kind"] == "daily_owned"
    assert entry["local_date"] == "2026-08-26"
    assert entry["platforms"]["facebook"]["remote_id"] == "fb-1"
    assert entry["platforms"].get("instagram", {}).get("status") != "confirmed"


@pytest.mark.trace("SOCIAL-LIB-001")
@pytest.mark.baseline_green
def test_library_contains_sixteen_unique_versioned_examples() -> None:
    keys = [item["key"] for item in library.LIBRARY]

    assert len(keys) == 16
    assert len(set(keys)) == 16
    assert all(key and key == key.strip() for key in keys)


@pytest.mark.trace("SOCIAL-LIB-002")
@pytest.mark.baseline_green
def test_every_library_entry_references_a_template_and_has_network_copy() -> None:
    for item in library.LIBRARY:
        assert item["template"] in template_module.TEMPLATES
        assert isinstance(item["piece"], dict)
        assert item["piece"].get("title") or item["piece"].get("quote") or item["piece"].get("stat")
        assert set(item.get("caption", {})) >= {"facebook", "instagram"}
        assert all(item["caption"][network].strip() for network in ("facebook", "instagram"))


@pytest.mark.trace("SOCIAL-LIB-003")
@pytest.mark.baseline_green
def test_library_accessors_return_typed_piece_and_captions() -> None:
    key = library.LIBRARY[0]["key"]
    template_key, piece = library.library_piece(key)

    assert template_key == library.entry(key)["template"]
    assert isinstance(piece, template_module.Piece)
    assert piece.title
    assert set(library.captions(key)) >= {"facebook", "instagram"}


@pytest.mark.trace("SOCIAL-LIB-004")
@pytest.mark.baseline_green
def test_library_unknown_key_is_actionable_and_lists_available_keys() -> None:
    with pytest.raises(KeyError) as exc_info:
        library.entry("does-not-exist")

    message = str(exc_info.value)
    assert "does-not-exist" in message
    assert library.LIBRARY[0]["key"] in message


@pytest.mark.trace("SOCIAL-LIB-005")
@pytest.mark.red_expected
def test_library_entries_are_immutable_examples_not_mutable_daily_state() -> None:
    key = library.LIBRARY[0]["key"]
    before = copy.deepcopy(library.entry(key))
    fetched = library.entry(key)
    fetched["piece"]["title"] = "mutation must not leak"

    assert library.entry(key) == before


@pytest.mark.trace("SOCIAL-LIB-006")
@pytest.mark.red_expected
def test_legacy_library_picker_has_no_source_account_or_automatic_daily_rotation() -> None:
    source = Path("scripts/social/pick_library_key.py").read_text(encoding="utf-8")

    assert "/home/openclaw" not in source
    assert "tm_yday" not in source
    assert "doy % len(keys)" not in source


@pytest.mark.trace("SOCIAL-RETRY-001")
@pytest.mark.baseline_green
def test_retry_gate_handles_missing_corrupt_and_legacy_daily_state(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("not-json", encoding="utf-8")
    legacy = tmp_path / "legacy.json"
    legacy.write_text(
        json.dumps({"published": {"piece": {"date": "2026-08-26", "facebook": "fb-1"}}}),
        encoding="utf-8",
    )

    assert should_retry_today.has_post_today(missing, "2026-08-26") is False
    assert should_retry_today.has_post_today(corrupt, "2026-08-26") is False
    assert should_retry_today.has_post_today(legacy, "2026-08-26") is True
    assert should_retry_today.has_post_today(legacy, "2026-08-25") is False


@pytest.mark.trace("SOCIAL-RETRY-002")
@pytest.mark.baseline_green
def test_retry_gate_does_not_count_blog_note_as_daily_owned(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": {
                    "social:blog_note:note-slug": {
                        "kind": "blog_note",
                        "local_date": "2026-08-26",
                        "status": "complete",
                        "platforms": {
                            "facebook": {"status": "confirmed", "remote_id": "fb-note"},
                            "instagram": {"status": "confirmed", "remote_id": "ig-note"},
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    assert should_retry_today.has_post_today(ledger, "2026-08-26") is False


@pytest.mark.trace("SOCIAL-RETRY-003")
@pytest.mark.red_expected
def test_retry_gate_requires_complete_daily_owned_on_both_platforms(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.json"
    document = {
        "schema_version": 1,
        "entries": {
            "daily": {
                "kind": "daily_owned",
                "local_date": "2026-08-26",
                "status": "partial",
                "platforms": {
                    "facebook": {"status": "confirmed", "remote_id": "fb-daily"},
                    "instagram": {"status": "pending"},
                },
            }
        },
    }
    ledger.write_text(json.dumps(document), encoding="utf-8")
    assert should_retry_today.has_post_today(ledger, "2026-08-26") is False

    document["entries"]["daily"]["status"] = "complete"
    document["entries"]["daily"]["platforms"]["instagram"] = {
        "status": "confirmed",
        "remote_id": "ig-daily",
    }
    ledger.write_text(json.dumps(document), encoding="utf-8")
    assert should_retry_today.has_post_today(ledger, "2026-08-26") is True


@pytest.mark.trace("SOCIAL-RETRY-004")
@pytest.mark.baseline_green
def test_retry_main_emits_machine_readable_or_plain_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text('{"published": {}}', encoding="utf-8")
    monkeypatch.setattr(should_retry_today, "STATE", state_path)

    monkeypatch.setattr(sys, "argv", ["should_retry_today.py"])
    assert should_retry_today.main() == 0
    assert json.loads(capsys.readouterr().out) == {"fire": True}

    monkeypatch.setattr(sys, "argv", ["should_retry_today.py", "--plain"])
    assert should_retry_today.main() == 0
    assert capsys.readouterr().out.strip() == "fire"
