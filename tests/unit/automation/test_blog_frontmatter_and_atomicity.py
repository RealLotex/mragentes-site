from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from tests.fixtures.factories import news_item, queue_document, write_json
from tests.support.contracts import require_target, trace_message
from tests.support.planned import planned_callable


TARGET = "scripts/automation/blog_guard.py"


def _front_matter(trace_id: str, **overrides: object) -> dict[str, object]:
    build = planned_callable(TARGET, "build_front_matter", trace_id)
    values: dict[str, object] = {
        "title": "Un modelo verificable cambia la conversación",
        "local_date": "2026-08-26",
        "description": "Qué cambia cuando un modelo publica evidencia verificable.",
        "image": "/images/stock/modelo-verificable.webp",
        "image_alt": "Diagrama abstracto de un modelo y sus controles.",
        "tags": ["ia", "modelos"],
        "sources": ["https://example.test/research/model-card"],
        "automation_id": "blog:2026-08-26:modelo-verificable",
        "aliases": [],
    }
    values.update(overrides)
    result = build(**values)
    assert isinstance(result, dict), trace_message(trace_id, "front matter must be a mapping")
    return result


def _validate(front_matter: dict[str, object], trace_id: str) -> dict[str, object]:
    validate = planned_callable(TARGET, "validate_front_matter", trace_id)
    result = validate(copy.deepcopy(front_matter))
    assert isinstance(result, dict), trace_message(trace_id, "validator must return a mapping")
    return result


def _atomic_fixture(tmp_path: Path) -> dict[str, object]:
    root = tmp_path / "repo"
    (root / "content" / "notas").mkdir(parents=True)
    (root / "static" / "images" / "stock").mkdir(parents=True)
    (root / "data").mkdir()
    source = root / "inbox" / "source.webp"
    source.parent.mkdir()
    source.write_bytes(b"RIFFsynthetic-WEBP")
    reserved = news_item(
        status="reserved",
        reserved_by="blog:2026-08-26:modelo",
        reserved_at="2026-08-26T11:00:00Z",
    )
    queue_path = write_json(root / "data" / "news-queue.json", queue_document(reserved))
    note = Path("content/notas/2026-08-26-modelo.md")
    asset = Path("static/images/stock/modelo.webp")
    return {
        "root": root,
        "run_id": "blog:2026-08-26:modelo",
        "note_relative_path": note,
        "note_content": "---\nautomation_id: blog:2026-08-26:modelo\n---\n\nContenido\n",
        "asset_source": source,
        "asset_relative_path": asset,
        "queue_path": queue_path,
        "queue_document": queue_document(
            {
                **reserved,
                "status": "consumed",
                "consumed_by": note.stem,
                "consumed_at": "2026-08-26T12:00:00Z",
            },
            revision=2,
        ),
    }


@pytest.mark.trace("BLOG-FM-001")
@pytest.mark.red_expected
def test_front_matter_contains_closed_required_schema() -> None:
    result = _front_matter("BLOG-FM-001")
    required = {
        "schema_version",
        "title",
        "date",
        "description",
        "image",
        "image_alt",
        "tags",
        "sources",
        "automation_id",
        "draft",
        "aliases",
    }
    assert set(result) == required, trace_message(
        "BLOG-FM-001", f"front matter fields differ: {set(result) ^ required}"
    )


@pytest.mark.trace("BLOG-FM-002")
@pytest.mark.red_expected
def test_front_matter_date_uses_cordoba_offset_not_naive_or_utc_midnight() -> None:
    result = _front_matter("BLOG-FM-002", local_date="2026-08-26")
    assert result["date"] == "2026-08-26T12:00:00-03:00", trace_message(
        "BLOG-FM-002", f"unexpected Córdoba publication date: {result['date']}"
    )


@pytest.mark.trace("BLOG-FM-003")
@pytest.mark.red_expected
def test_front_matter_roundtrip_escapes_quotes_colons_newlines_and_unicode() -> None:
    title = 'IA: "prueba"\ncon Ñandú'
    description = "Línea uno: evidencia\nLínea dos"
    result = _front_matter("BLOG-FM-003", title=title, description=description)
    rendered = yaml.safe_dump(result, allow_unicode=True, sort_keys=False)
    loaded = yaml.safe_load(rendered)
    assert loaded["title"] == title and loaded["description"] == description, trace_message(
        "BLOG-FM-003", "YAML round-trip corrupted escaped text"
    )


@pytest.mark.trace("BLOG-FM-004")
@pytest.mark.red_expected
def test_description_is_nonempty_plain_text_with_search_snippet_limit() -> None:
    validate = planned_callable(TARGET, "validate_front_matter", "BLOG-FM-004")
    valid = _front_matter("BLOG-FM-004", description="Dato comprobable en menos de 160 caracteres.")
    assert validate(valid)["description"], trace_message("BLOG-FM-004", "valid description rejected")
    for invalid in ("", "x" * 161, "<script>alert(1)</script>"):
        candidate = dict(valid, description=invalid)
        with pytest.raises(ValueError):
            validate(candidate)


@pytest.mark.trace("BLOG-FM-005")
@pytest.mark.red_expected
def test_image_path_is_site_relative_stock_asset_and_alt_is_descriptive() -> None:
    validate = planned_callable(TARGET, "validate_front_matter", "BLOG-FM-005")
    valid = _front_matter("BLOG-FM-005")
    assert validate(valid)["image"].startswith("/images/stock/"), trace_message(
        "BLOG-FM-005", "valid stock asset rejected"
    )
    invalid_pairs = (
        ("https://tracker.test/pixel.png", "Descripción suficiente"),
        ("/images/stock/a.webp", ""),
        ("../../secret.png", "Descripción suficiente"),
    )
    for image, alt in invalid_pairs:
        with pytest.raises(ValueError):
            validate(dict(valid, image=image, image_alt=alt))


@pytest.mark.trace("BLOG-FM-006")
@pytest.mark.red_expected
def test_sources_are_public_canonical_unique_and_nonempty() -> None:
    validate = planned_callable(TARGET, "validate_front_matter", "BLOG-FM-006")
    valid = _front_matter(
        "BLOG-FM-006",
        sources=["https://example.test/a", "https://example.test/b"],
    )
    assert len(validate(valid)["sources"]) == 2, trace_message(
        "BLOG-FM-006", "valid source list rejected"
    )
    for sources in (
        [],
        ["https://example.test/a", "https://example.test/a?utm_source=x"],
        ["http://127.0.0.1/private"],
        ["file:///tmp/source"],
    ):
        with pytest.raises(ValueError):
            validate(dict(valid, sources=sources))


@pytest.mark.trace("BLOG-FM-007")
@pytest.mark.red_expected
def test_tags_are_normalized_unique_bounded_and_safe() -> None:
    validate = planned_callable(TARGET, "validate_front_matter", "BLOG-FM-007")
    result = validate(_front_matter("BLOG-FM-007", tags=["IA", "automatización", "IA"]))
    assert result["tags"] == ["ia", "automatizacion"], trace_message(
        "BLOG-FM-007", f"tags were not normalized: {result['tags']}"
    )
    for tags in ([], ["x" * 51], ["ia", "<script>"], [str(i) for i in range(21)]):
        with pytest.raises(ValueError):
            validate(_front_matter("BLOG-FM-007", tags=tags))


@pytest.mark.trace("BLOG-FM-008")
@pytest.mark.red_expected
def test_automated_note_is_never_draft_and_boolean_type_is_strict() -> None:
    validate = planned_callable(TARGET, "validate_front_matter", "BLOG-FM-008")
    valid = _front_matter("BLOG-FM-008")
    assert valid["draft"] is False, trace_message("BLOG-FM-008", "builder created a draft")
    for draft in (True, "false", 0, None):
        with pytest.raises((TypeError, ValueError)):
            validate(dict(valid, draft=draft))


@pytest.mark.trace("BLOG-FM-009")
@pytest.mark.red_expected
def test_automation_id_has_closed_format_and_cannot_be_blank() -> None:
    validate = planned_callable(TARGET, "validate_front_matter", "BLOG-FM-009")
    valid = _front_matter("BLOG-FM-009")
    assert validate(valid)["automation_id"] == "blog:2026-08-26:modelo-verificable", trace_message(
        "BLOG-FM-009", "valid automation ID changed"
    )
    for value in ("", "blog/latest", "social:2026-08-26:x", "blog:2026-8-26:x"):
        with pytest.raises(ValueError):
            validate(dict(valid, automation_id=value))


@pytest.mark.trace("BLOG-FM-010")
@pytest.mark.red_expected
def test_legacy_aliases_are_absolute_local_unique_and_not_canonical_path() -> None:
    validate = planned_callable(TARGET, "validate_front_matter", "BLOG-FM-010")
    valid = _front_matter(
        "BLOG-FM-010",
        aliases=["/notas/2026-08-23-titulo-anterior-muy-largo/"],
    )
    assert validate(valid)["aliases"] == valid["aliases"], trace_message(
        "BLOG-FM-010", "valid legacy alias rejected"
    )
    for aliases in (
        ["https://example.test/notas/old/"],
        ["../../old"],
        ["/notas/old/", "/notas/old/"],
    ):
        with pytest.raises(ValueError):
            validate(dict(valid, aliases=aliases))


@pytest.mark.trace("BLOG-FM-011")
@pytest.mark.red_expected
def test_unknown_secret_or_runtime_fields_are_rejected() -> None:
    validate = planned_callable(TARGET, "validate_front_matter", "BLOG-FM-011")
    base = _front_matter("BLOG-FM-011")
    for key in ("token", "api_key", "push_endpoint", "raw_html", "run_workspace"):
        with pytest.raises(ValueError):
            validate({**base, key: "synthetic"})


@pytest.mark.trace("BLOG-FM-012")
@pytest.mark.red_expected
def test_front_matter_validation_is_deterministic_and_non_mutating() -> None:
    value = _front_matter("BLOG-FM-012")
    original = copy.deepcopy(value)
    first = _validate(value, "BLOG-FM-012")
    second = _validate(value, "BLOG-FM-012")
    assert first == second, trace_message("BLOG-FM-012", "validation is not deterministic")
    assert value == original, trace_message("BLOG-FM-012", "validation mutated caller input")


@pytest.mark.trace("BLOG-ATOMIC-001")
@pytest.mark.red_expected
def test_atomic_change_commits_note_asset_and_queue_as_one_local_transaction(tmp_path: Path) -> None:
    build = planned_callable(TARGET, "build_atomic_change", "BLOG-ATOMIC-001")
    values = _atomic_fixture(tmp_path)
    report = build(**values, apply=True)
    root = values["root"]
    assert (root / values["note_relative_path"]).is_file(), trace_message(
        "BLOG-ATOMIC-001", "note was not materialized"
    )
    assert (root / values["asset_relative_path"]).is_file(), trace_message(
        "BLOG-ATOMIC-001", "asset was not materialized"
    )
    persisted = json.loads(Path(values["queue_path"]).read_text(encoding="utf-8"))
    assert persisted == values["queue_document"], trace_message(
        "BLOG-ATOMIC-001", "queue consumption was not committed"
    )
    assert report["status"] == "applied", trace_message(
        "BLOG-ATOMIC-001", "transaction report is not applied"
    )


@pytest.mark.trace("BLOG-ATOMIC-QUEUE-CONTRACT-001")
@pytest.mark.red_expected
def test_atomic_change_accepts_the_versioned_automation_news_queue_path(tmp_path: Path) -> None:
    """The current repository contract stores the queue under .automation/news/queue."""

    build = planned_callable(TARGET, "build_atomic_change", "BLOG-ATOMIC-QUEUE-CONTRACT-001")
    values = _atomic_fixture(tmp_path)
    legacy_queue = Path(values["queue_path"])
    current_queue = values["root"] / ".automation" / "news" / "queue" / legacy_queue.name
    current_queue.parent.mkdir(parents=True)
    current_queue.write_bytes(legacy_queue.read_bytes())
    values["queue_path"] = current_queue
    report = build(**values, apply=True)
    assert report["status"] == "applied", trace_message(
        "BLOG-ATOMIC-QUEUE-CONTRACT-001", "versioned automation queue path was rejected"
    )
    assert json.loads(current_queue.read_text(encoding="utf-8")) == values["queue_document"]


@pytest.mark.trace("BLOG-ATOMIC-002")
@pytest.mark.red_expected
def test_missing_asset_fails_before_any_destination_is_written(tmp_path: Path) -> None:
    build = planned_callable(TARGET, "build_atomic_change", "BLOG-ATOMIC-002")
    values = _atomic_fixture(tmp_path)
    Path(values["asset_source"]).unlink()
    queue_before = Path(values["queue_path"]).read_bytes()
    with pytest.raises(FileNotFoundError):
        build(**values, apply=True)
    root = values["root"]
    assert not (root / values["note_relative_path"]).exists(), trace_message(
        "BLOG-ATOMIC-002", "note survived failed asset preflight"
    )
    assert Path(values["queue_path"]).read_bytes() == queue_before, trace_message(
        "BLOG-ATOMIC-002", "queue changed after asset failure"
    )


@pytest.mark.trace("BLOG-ATOMIC-003")
@pytest.mark.red_expected
def test_failure_during_replace_rolls_back_all_three_destinations(tmp_path: Path) -> None:
    build = planned_callable(TARGET, "build_atomic_change", "BLOG-ATOMIC-003")
    values = _atomic_fixture(tmp_path)
    queue_before = Path(values["queue_path"]).read_bytes()
    calls = 0

    def fail_second_replace(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic second replace failure")
        Path(destination).write_bytes(Path(source).read_bytes())

    with pytest.raises(OSError, match="second replace"):
        build(**values, apply=True, replace=fail_second_replace)
    root = values["root"]
    assert not (root / values["note_relative_path"]).exists(), trace_message(
        "BLOG-ATOMIC-003", "note was not rolled back"
    )
    assert not (root / values["asset_relative_path"]).exists(), trace_message(
        "BLOG-ATOMIC-003", "asset was not rolled back"
    )
    assert Path(values["queue_path"]).read_bytes() == queue_before, trace_message(
        "BLOG-ATOMIC-003", "queue was not rolled back"
    )


@pytest.mark.trace("BLOG-ATOMIC-004")
@pytest.mark.red_expected
def test_same_run_reexecution_is_byte_identical_successful_noop(tmp_path: Path) -> None:
    build = planned_callable(TARGET, "build_atomic_change", "BLOG-ATOMIC-004")
    values = _atomic_fixture(tmp_path)
    first = build(**values, apply=True)
    root = values["root"]
    paths = [
        root / values["note_relative_path"],
        root / values["asset_relative_path"],
        Path(values["queue_path"]),
    ]
    before = [path.read_bytes() for path in paths]
    second = build(**values, apply=True)
    assert second["status"] == "unchanged" and first["run_id"] == second["run_id"], trace_message(
        "BLOG-ATOMIC-004", "same run was not idempotent"
    )
    assert [path.read_bytes() for path in paths] == before, trace_message(
        "BLOG-ATOMIC-004", "same run rewrote files"
    )


@pytest.mark.trace("BLOG-ATOMIC-005")
@pytest.mark.red_expected
def test_existing_different_note_or_asset_causes_conflict_not_overwrite(tmp_path: Path) -> None:
    build = planned_callable(TARGET, "build_atomic_change", "BLOG-ATOMIC-005")
    values = _atomic_fixture(tmp_path)
    note = values["root"] / values["note_relative_path"]
    note.write_text("manual user content", encoding="utf-8")
    with pytest.raises(FileExistsError):
        build(**values, apply=True)
    assert note.read_text(encoding="utf-8") == "manual user content", trace_message(
        "BLOG-ATOMIC-005", "manual note was overwritten"
    )


@pytest.mark.trace("BLOG-ATOMIC-006")
@pytest.mark.red_expected
def test_transaction_rejects_absolute_traversal_and_non_allowlisted_destinations(tmp_path: Path) -> None:
    build = planned_callable(TARGET, "build_atomic_change", "BLOG-ATOMIC-006")
    values = _atomic_fixture(tmp_path)
    invalid_paths = (
        Path("../../escape.md"),
        Path("scripts/runtime.py"),
        Path(".github/workflows/deploy.yml"),
        Path("/tmp/absolute.md"),
    )
    for path in invalid_paths:
        candidate = dict(values, note_relative_path=path)
        with pytest.raises(ValueError):
            build(**candidate, apply=True)


@pytest.mark.trace("BLOG-ATOMIC-007")
@pytest.mark.red_expected
def test_transaction_validates_asset_extension_content_size_and_symlink(tmp_path: Path) -> None:
    build = planned_callable(TARGET, "build_atomic_change", "BLOG-ATOMIC-007")
    values = _atomic_fixture(tmp_path)
    bad_extension = dict(values, asset_relative_path=Path("static/images/stock/modelo.exe"))
    with pytest.raises(ValueError):
        build(**bad_extension, apply=True)
    Path(values["asset_source"]).write_bytes(b"not-an-image")
    with pytest.raises(ValueError):
        build(**values, apply=True)
    external = tmp_path / "external.webp"
    external.write_bytes(b"RIFFsynthetic-WEBP")
    Path(values["asset_source"]).unlink()
    Path(values["asset_source"]).symlink_to(external)
    with pytest.raises(ValueError):
        build(**values, apply=True)


@pytest.mark.trace("BLOG-ATOMIC-008")
@pytest.mark.red_expected
def test_blog_guard_source_has_no_git_meta_push_or_cloudflare_network_effects() -> None:
    source = require_target(TARGET, "BLOG-ATOMIC-008").read_text(encoding="utf-8")
    forbidden = (
        "git push",
        "--force",
        "urllib.request",
        "requests.",
        "facebook",
        "instagram",
        "PUSH_WORKER_URL",
    )
    found = [value for value in forbidden if value in source]
    assert not found, trace_message(
        "BLOG-ATOMIC-008", f"blog guard owns forbidden side effects: {found}"
    )


@pytest.mark.trace("BLOG-ATOMIC-009")
@pytest.mark.red_expected
def test_failure_and_success_leave_no_transaction_temporary_files(tmp_path: Path) -> None:
    build = planned_callable(TARGET, "build_atomic_change", "BLOG-ATOMIC-009")
    values = _atomic_fixture(tmp_path)
    build(**values, apply=True)
    root = values["root"]
    leftovers = [path for path in root.rglob("*") if ".tmp" in path.name or ".txn" in path.name]
    assert not leftovers, trace_message(
        "BLOG-ATOMIC-009", f"transaction left temporary artifacts: {leftovers}"
    )


@pytest.mark.trace("BLOG-ATOMIC-010")
@pytest.mark.red_expected
def test_transaction_report_has_relative_paths_hashes_and_no_content_or_secrets(tmp_path: Path) -> None:
    build = planned_callable(TARGET, "build_atomic_change", "BLOG-ATOMIC-010")
    values = _atomic_fixture(tmp_path)
    report = build(**values, apply=True)
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    assert str(values["root"]) not in serialized, trace_message(
        "BLOG-ATOMIC-010", "transaction report leaked absolute root"
    )
    assert values["note_content"] not in serialized, trace_message(
        "BLOG-ATOMIC-010", "transaction report copied the full note"
    )
    assert set(report["artifacts"]) == {"note", "asset", "queue"}, trace_message(
        "BLOG-ATOMIC-010", "transaction report lacks artifact inventory"
    )
    assert all(len(entry["sha256"]) == 64 for entry in report["artifacts"].values()), trace_message(
        "BLOG-ATOMIC-010", "artifact hash is missing or malformed"
    )
