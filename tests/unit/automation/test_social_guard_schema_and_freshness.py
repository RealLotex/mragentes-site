from __future__ import annotations

import copy
from pathlib import Path

import pytest

from tests.fixtures.factories import social_draft, write_json
from tests.support.contracts import trace_message
from tests.support.planned import planned_callable, planned_signature


TARGET = "scripts/automation/social_guard.py"


def _validate(draft: dict[str, object], trace_id: str) -> dict[str, object]:
    validate = planned_callable(TARGET, "validate_social_draft", trace_id)
    result = validate(copy.deepcopy(draft))
    assert isinstance(result, dict), trace_message(trace_id, "social validator must return mapping")
    return result


@pytest.mark.trace("SOCIAL-SCHEMA-001")
@pytest.mark.red_expected
def test_social_guard_exposes_complete_planned_api() -> None:
    signatures = {
        "social_run_id": ("local_date", "kind"),
        "content_hash": ("draft",),
        "validate_social_draft": ("draft",),
        "recent_topic_hashes": ("records", "since"),
        "ensure_fresh": ("draft", "recent_records"),
        "classify_completion": ("platforms", "records"),
        "recovery_plan": ("completion", "remote_matches"),
    }
    for symbol, parameters in signatures.items():
        planned_signature(TARGET, symbol, parameters, "SOCIAL-SCHEMA-001")


@pytest.mark.trace("SOCIAL-SCHEMA-002")
@pytest.mark.red_expected
def test_social_run_id_separates_date_kind_and_blog_subject() -> None:
    run_id = planned_callable(TARGET, "social_run_id", "SOCIAL-SCHEMA-002")
    daily = run_id("2026-08-26", "daily_owned")
    blog = run_id("2026-08-26", "blog_note", subject="2026-08-26-modelo")
    assert daily == "social:daily_owned:2026-08-26", trace_message(
        "SOCIAL-SCHEMA-002", f"unexpected daily run id: {daily}"
    )
    assert blog == "social:blog_note:2026-08-26:2026-08-26-modelo", trace_message(
        "SOCIAL-SCHEMA-002", f"unexpected blog run id: {blog}"
    )
    assert daily != blog, trace_message("SOCIAL-SCHEMA-002", "social kinds collide")


@pytest.mark.trace("SOCIAL-SCHEMA-003")
@pytest.mark.red_expected
def test_content_hash_is_canonical_stable_and_changes_with_copy_or_asset() -> None:
    content_hash = planned_callable(TARGET, "content_hash", "SOCIAL-SCHEMA-003")
    draft = social_draft()
    reordered = {key: draft[key] for key in reversed(draft)}
    first = content_hash(draft)
    assert first == content_hash(copy.deepcopy(draft)) == content_hash(reordered), trace_message(
        "SOCIAL-SCHEMA-003", "hash depends on mapping order or process object"
    )
    changed_copy = copy.deepcopy(draft)
    changed_copy["captions"]["facebook"] += " Cambio."
    changed_asset = copy.deepcopy(draft)
    changed_asset["asset"]["sha256"] = "b" * 64
    assert len({first, content_hash(changed_copy), content_hash(changed_asset)}) == 3, trace_message(
        "SOCIAL-SCHEMA-003", "material social changes did not change hash"
    )


@pytest.mark.trace("SOCIAL-SCHEMA-004")
@pytest.mark.red_expected
def test_minimal_complete_daily_owned_draft_is_accepted_without_mutation() -> None:
    draft = social_draft()
    original = copy.deepcopy(draft)
    result = _validate(draft, "SOCIAL-SCHEMA-004")
    assert result["kind"] == "daily_owned", trace_message(
        "SOCIAL-SCHEMA-004", "valid daily draft kind changed"
    )
    assert draft == original, trace_message("SOCIAL-SCHEMA-004", "validator mutated draft")


@pytest.mark.trace("SOCIAL-SCHEMA-005")
@pytest.mark.red_expected
def test_blog_note_kind_requires_note_slug_url_and_deploy_commit() -> None:
    validate = planned_callable(TARGET, "validate_social_draft", "SOCIAL-SCHEMA-005")
    complete = social_draft(
        kind="blog_note",
        run_id="social-blog-note-2026-08-26-modelo",
        dedupe_key="blog_note:2026-08-26:sha256:content-92a1",
        note_slug="2026-08-26-modelo",
        note_url="https://mragentes.com.ar/notas/2026-08-26-modelo/",
        deploy_sha="a" * 40,
    )
    assert validate(complete)["note_slug"] == "2026-08-26-modelo", trace_message(
        "SOCIAL-SCHEMA-005", "complete blog-note draft rejected"
    )
    for missing in ("note_slug", "note_url", "deploy_sha"):
        candidate = dict(complete)
        candidate.pop(missing)
        with pytest.raises(ValueError):
            validate(candidate)


@pytest.mark.trace("SOCIAL-SCHEMA-005B")
@pytest.mark.red_expected
def test_blog_note_accepts_canonical_unicode_slug_and_deployed_stock_asset() -> None:
    validate = planned_callable(TARGET, "validate_social_draft", "SOCIAL-SCHEMA-005B")
    candidate = social_draft(
        kind="blog_note",
        run_id="social:blog_note:2026-08-26:automatización-canónica",
        dedupe_key="blog_note:2026-08-26:sha256:content-92a1",
        asset={
            "path": "static/images/stock/nota-segura.webp",
            "sha256": "a" * 64,
            "alt": "Imagen principal de la nota",
        },
        note_slug="automatización-canónica",
        note_url="https://mragentes.com.ar/notas/automatizaci%C3%B3n-can%C3%B3nica/",
        deploy_sha="a" * 40,
    )
    assert validate(candidate)["note_slug"] == "automatización-canónica"

    daily = social_draft(
        asset={
            "path": "static/images/stock/no-permitida.webp",
            "sha256": "a" * 64,
            "alt": "Imagen",
        }
    )
    with pytest.raises(ValueError, match="allowlist"):
        validate(daily)


@pytest.mark.trace("SOCIAL-SCHEMA-006")
@pytest.mark.red_expected
def test_both_platform_captions_are_required_nonempty_and_platform_specific() -> None:
    validate = planned_callable(TARGET, "validate_social_draft", "SOCIAL-SCHEMA-006")
    base = social_draft()
    for captions in (
        {},
        {"facebook": "Texto"},
        {"instagram": "Texto"},
        {"facebook": "", "instagram": "Texto"},
        {"facebook": "Mismo texto", "instagram": "Mismo texto"},
    ):
        with pytest.raises(ValueError):
            validate(dict(base, captions=captions))


@pytest.mark.trace("SOCIAL-SCHEMA-006B")
@pytest.mark.red_expected
def test_social_captions_reject_double_serialized_line_breaks() -> None:
    validate = planned_callable(TARGET, "validate_social_draft", "SOCIAL-SCHEMA-006B")
    base = social_draft()
    captions = {
        "facebook": "Primer párrafo.\\n\\nSegundo párrafo.",
        "instagram": "Texto distinto. #IA",
    }
    with pytest.raises(ValueError, match="serialized line-break"):
        validate(dict(base, captions=captions))


@pytest.mark.trace("SOCIAL-SCHEMA-007")
@pytest.mark.red_expected
def test_social_asset_requires_allowlisted_relative_path_sha256_and_alt() -> None:
    validate = planned_callable(TARGET, "validate_social_draft", "SOCIAL-SCHEMA-007")
    base = social_draft()
    invalid_assets = (
        {"path": "../../escape.png", "sha256": "a" * 64, "alt": "Descripción"},
        {"path": "/tmp/absolute.png", "sha256": "a" * 64, "alt": "Descripción"},
        {"path": "static/images/social/x.exe", "sha256": "a" * 64, "alt": "Descripción"},
        {"path": "static/images/social/x.png", "sha256": "short", "alt": "Descripción"},
        {"path": "static/images/social/x.png", "sha256": "a" * 64, "alt": ""},
    )
    for asset in invalid_assets:
        with pytest.raises(ValueError):
            validate(dict(base, asset=asset))


@pytest.mark.trace("SOCIAL-SCHEMA-008")
@pytest.mark.red_expected
def test_dedupe_key_must_match_kind_date_and_computed_content_hash() -> None:
    validate = planned_callable(TARGET, "validate_social_draft", "SOCIAL-SCHEMA-008")
    base = social_draft()
    assert validate(base)["dedupe_key"] == base["dedupe_key"], trace_message(
        "SOCIAL-SCHEMA-008", "valid dedupe key rejected"
    )
    for value in ("", "daily_owned:latest:x", "blog_note:2026-08-26:x", "daily_owned:2026-08-26:wrong"):
        with pytest.raises(ValueError):
            validate(dict(base, dedupe_key=value))


@pytest.mark.trace("SOCIAL-SCHEMA-009")
@pytest.mark.red_expected
def test_social_created_at_is_timezone_aware_and_matches_run_local_date() -> None:
    validate = planned_callable(TARGET, "validate_social_draft", "SOCIAL-SCHEMA-009")
    base = social_draft()
    for value in ("2026-08-26", "2026-08-26T12:00:00", "2026-02-30T12:00:00Z", "2026-08-27T12:00:00Z"):
        with pytest.raises(ValueError):
            validate(dict(base, created_at=value))


@pytest.mark.trace("SOCIAL-SCHEMA-010")
@pytest.mark.red_expected
def test_unknown_runtime_secret_and_remote_result_fields_are_rejected() -> None:
    validate = planned_callable(TARGET, "validate_social_draft", "SOCIAL-SCHEMA-010")
    base = social_draft()
    for key in ("access_token", "api_secret", "cookie", "facebook_post_id", "worker_url", "unexpected"):
        with pytest.raises(ValueError):
            validate({**base, key: "synthetic"})


@pytest.mark.trace("SOCIAL-SCHEMA-011")
@pytest.mark.red_expected
def test_caption_topic_alt_and_collection_limits_are_enforced() -> None:
    validate = planned_callable(TARGET, "validate_social_draft", "SOCIAL-SCHEMA-011")
    base = social_draft()
    invalid = (
        dict(base, topic="x" * 501),
        dict(base, captions={"facebook": "x" * 63207, "instagram": "Texto #IA"}),
        dict(base, captions={"facebook": "Texto", "instagram": "x" * 2201}),
        dict(base, asset={**base["asset"], "alt": "x" * 501}),
    )
    for candidate in invalid:
        with pytest.raises(ValueError):
            validate(candidate)


@pytest.mark.trace("SOCIAL-SCHEMA-011B")
@pytest.mark.red_expected
def test_social_copy_rejects_weekly_formulas_and_colloquial_register() -> None:
    validate = planned_callable(TARGET, "validate_social_draft", "SOCIAL-SCHEMA-011B")
    base = social_draft()
    invalid = (
        dict(base, topic="La semana en que cambió la automatización"),
        dict(base, captions={"facebook": "No vendemos humo.", "instagram": "Análisis técnico. #IA"}),
        dict(base, captions={"facebook": "Análisis técnico.", "instagram": "Vos podés revisar el proceso. #IA"}),
    )
    for candidate in invalid:
        with pytest.raises(ValueError):
            validate(candidate)


@pytest.mark.trace("SOCIAL-SCHEMA-012")
@pytest.mark.red_expected
def test_social_schema_version_and_kind_enums_are_closed() -> None:
    validate = planned_callable(TARGET, "validate_social_draft", "SOCIAL-SCHEMA-012")
    base = social_draft()
    for version in (0, 2, "1", None):
        with pytest.raises((TypeError, ValueError)):
            validate(dict(base, schema_version=version))
    for kind in ("daily", "blog", "story", "", None):
        with pytest.raises((TypeError, ValueError)):
            validate(dict(base, kind=kind))


@pytest.mark.trace("SOCIAL-FRESH-001")
@pytest.mark.red_expected
def test_recent_topic_hashes_filters_window_and_daily_owned_kind() -> None:
    recent_hashes = planned_callable(TARGET, "recent_topic_hashes", "SOCIAL-FRESH-001")
    records = [
        {"kind": "daily_owned", "topic_hash": "recent", "created_at": "2026-08-25T12:00:00Z"},
        {"kind": "daily_owned", "topic_hash": "old", "created_at": "2026-06-01T12:00:00Z"},
        {"kind": "blog_note", "topic_hash": "blog", "created_at": "2026-08-25T12:00:00Z"},
    ]
    observed = recent_hashes(records, since="2026-07-27T00:00:00Z", kind="daily_owned")
    assert observed == {"recent"}, trace_message(
        "SOCIAL-FRESH-001", f"freshness window is wrong: {observed}"
    )


@pytest.mark.trace("SOCIAL-FRESH-002")
@pytest.mark.red_expected
def test_same_recent_topic_is_rejected_even_if_punctuation_changes() -> None:
    ensure = planned_callable(TARGET, "ensure_fresh", "SOCIAL-FRESH-002")
    draft = social_draft(topic="Cómo validar una automatización antes de publicarla")
    recent = [
        {
            "kind": "daily_owned",
            "topic": "¿Cómo validar una automatización antes de publicarla?",
            "topic_hash": draft["topic_hash"],
            "content_hash": "different",
            "asset_sha256": "b" * 64,
            "created_at": "2026-08-25T12:00:00Z",
        }
    ]
    with pytest.raises(ValueError, match="topic"):
        ensure(draft, recent, window_days=30)


@pytest.mark.trace("SOCIAL-FRESH-003")
@pytest.mark.red_expected
def test_same_recent_copy_is_rejected_under_new_topic_label() -> None:
    ensure = planned_callable(TARGET, "ensure_fresh", "SOCIAL-FRESH-003")
    draft = social_draft(topic="Etiqueta nueva", topic_hash="new-topic")
    recent = [
        {
            "kind": "daily_owned",
            "topic_hash": "old-topic",
            "content_hash": draft["content_hash"],
            "asset_sha256": "b" * 64,
            "created_at": "2026-08-25T12:00:00Z",
        }
    ]
    with pytest.raises(ValueError, match="content"):
        ensure(draft, recent, window_days=30)


@pytest.mark.trace("SOCIAL-FRESH-004")
@pytest.mark.red_expected
def test_same_recent_media_is_rejected_even_with_new_copy() -> None:
    ensure = planned_callable(TARGET, "ensure_fresh", "SOCIAL-FRESH-004")
    draft = social_draft(topic_hash="new-topic", content_hash="new-content")
    recent = [
        {
            "kind": "daily_owned",
            "topic_hash": "old-topic",
            "content_hash": "old-content",
            "asset_sha256": draft["asset"]["sha256"],
            "created_at": "2026-08-25T12:00:00Z",
        }
    ]
    with pytest.raises(ValueError, match="asset"):
        ensure(draft, recent, window_days=30)


@pytest.mark.trace("SOCIAL-FRESH-005")
@pytest.mark.red_expected
def test_blog_note_does_not_block_daily_piece_merely_by_publication_kind() -> None:
    ensure = planned_callable(TARGET, "ensure_fresh", "SOCIAL-FRESH-005")
    draft = social_draft(topic_hash="daily-topic", content_hash="daily-content")
    recent = [
        {
            "kind": "blog_note",
            "topic_hash": "blog-topic",
            "content_hash": "blog-content",
            "asset_sha256": "b" * 64,
            "created_at": "2026-08-25T12:00:00Z",
        }
    ]
    assert ensure(draft, recent, window_days=30)["fresh"] is True, trace_message(
        "SOCIAL-FRESH-005", "unrelated blog announcement blocked daily content"
    )


@pytest.mark.trace("SOCIAL-FRESH-006")
@pytest.mark.red_expected
def test_matching_blog_topic_still_blocks_daily_topic_repetition() -> None:
    ensure = planned_callable(TARGET, "ensure_fresh", "SOCIAL-FRESH-006")
    draft = social_draft()
    recent = [
        {
            "kind": "blog_note",
            "topic_hash": draft["topic_hash"],
            "content_hash": "blog-content",
            "asset_sha256": "b" * 64,
            "created_at": "2026-08-25T12:00:00Z",
        }
    ]
    with pytest.raises(ValueError, match="topic"):
        ensure(draft, recent, window_days=30)


@pytest.mark.trace("SOCIAL-FRESH-007")
@pytest.mark.red_expected
def test_item_outside_freshness_window_does_not_block_reuse() -> None:
    ensure = planned_callable(TARGET, "ensure_fresh", "SOCIAL-FRESH-007")
    draft = social_draft()
    recent = [
        {
            "kind": "daily_owned",
            "topic_hash": draft["topic_hash"],
            "content_hash": draft["content_hash"],
            "asset_sha256": draft["asset"]["sha256"],
            "created_at": "2026-06-01T12:00:00Z",
        }
    ]
    assert ensure(draft, recent, now="2026-08-26T12:00:00Z", window_days=30)["fresh"] is True, trace_message(
        "SOCIAL-FRESH-007", "expired history blocked draft"
    )


@pytest.mark.trace("SOCIAL-FRESH-008")
@pytest.mark.red_expected
def test_hash_collision_with_different_normalized_content_requires_review() -> None:
    ensure = planned_callable(TARGET, "ensure_fresh", "SOCIAL-FRESH-008")
    draft = social_draft(topic="New text", topic_hash="collision")
    recent = [
        {
            "kind": "daily_owned",
            "topic": "Different normalized text",
            "topic_hash": "collision",
            "content_hash": "other",
            "asset_sha256": "b" * 64,
            "created_at": "2026-08-25T12:00:00Z",
        }
    ]
    result = ensure(draft, recent, window_days=30, collision_policy="needs_review")
    assert result["fresh"] is False and result["status"] == "needs_review", trace_message(
        "SOCIAL-FRESH-008", "hash collision was treated as ordinary duplicate"
    )


@pytest.mark.trace("SOCIAL-FRESH-009")
@pytest.mark.red_expected
def test_freshness_result_is_stable_for_same_run_and_input_order() -> None:
    ensure = planned_callable(TARGET, "ensure_fresh", "SOCIAL-FRESH-009")
    draft = social_draft(topic_hash="new-topic", content_hash="new-content")
    recent = [
        {"kind": "daily_owned", "topic_hash": "a", "content_hash": "a", "asset_sha256": "b" * 64, "created_at": "2026-08-25T12:00:00Z"},
        {"kind": "daily_owned", "topic_hash": "b", "content_hash": "b", "asset_sha256": "c" * 64, "created_at": "2026-08-24T12:00:00Z"},
    ]
    first = ensure(draft, recent, now="2026-08-26T12:00:00Z", window_days=30)
    second = ensure(draft, list(reversed(recent)), now="2026-08-26T12:00:00Z", window_days=30)
    assert first == second, trace_message("SOCIAL-FRESH-009", "freshness depends on record order")


@pytest.mark.trace("SOCIAL-FRESH-010")
@pytest.mark.red_expected
def test_recent_topic_reader_handles_empty_corrupt_and_duplicate_records_fail_closed(tmp_path: Path) -> None:
    recent_hashes = planned_callable(TARGET, "recent_topic_hashes", "SOCIAL-FRESH-010")
    empty = tmp_path / "empty.json"
    write_json(empty, [])
    assert recent_hashes(empty, since="2026-07-27T00:00:00Z") == set(), trace_message(
        "SOCIAL-FRESH-010", "empty history did not yield empty set"
    )
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        recent_hashes(corrupt, since="2026-07-27T00:00:00Z")
