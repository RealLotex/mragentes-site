from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.fixtures.factories import news_item, queue_document, write_json
from tests.support.contracts import require_target, trace_message
from tests.support.planned import planned_callable


TARGET = "scripts/automation/news_queue.py"
LEGACY_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "news" / "legacy_queue.md"


def _legacy_copy(tmp_path: Path, content: str | None = None) -> Path:
    path = tmp_path / "cola_diaria.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = LEGACY_FIXTURE.read_text(encoding="utf-8") if content is None else content
    path.write_text(text, encoding="utf-8")
    return path


def _migrate(tmp_path: Path, trace_id: str, **kwargs: object):
    migrate = planned_callable(TARGET, "migrate_markdown_queue", trace_id)
    markdown = kwargs.pop("markdown_path") if "markdown_path" in kwargs else _legacy_copy(tmp_path)
    queue = kwargs.pop("queue_path", tmp_path / "news-queue.json")
    audit = kwargs.pop("audit_path", tmp_path / "migration-audit.json")
    report = migrate(markdown, queue, audit_path=audit, **kwargs)
    return report, queue, audit


@pytest.mark.trace("NEWS-MIGRATE-001")
@pytest.mark.red_expected
def test_legacy_markdown_migration_parses_every_checkbox_entry(tmp_path: Path) -> None:
    report, queue, _ = _migrate(tmp_path, "NEWS-MIGRATE-001")
    document = json.loads(queue.read_text(encoding="utf-8"))
    assert report["parsed"] == 2 and len(document["items"]) == 2, trace_message(
        "NEWS-MIGRATE-001", f"not every legacy entry was parsed: {report}"
    )


@pytest.mark.trace("NEWS-MIGRATE-002")
@pytest.mark.red_expected
def test_checked_legacy_entry_maps_to_consumed_and_unchecked_to_pending(tmp_path: Path) -> None:
    _, queue, _ = _migrate(tmp_path, "NEWS-MIGRATE-002")
    items = json.loads(queue.read_text(encoding="utf-8"))["items"]
    statuses = {item["title"]: item["status"] for item in items}
    assert statuses == {
        "Un laboratorio publica un modelo verificable": "pending",
        "Una plataforma agrega auditoría de agentes": "consumed",
    }, trace_message("NEWS-MIGRATE-002", f"legacy checkbox mapping is wrong: {statuses}")


@pytest.mark.trace("NEWS-MIGRATE-003")
@pytest.mark.red_expected
def test_migrated_ids_are_stable_across_paths_line_endings_and_runs(tmp_path: Path) -> None:
    first_report, first_queue, _ = _migrate(tmp_path / "first", "NEWS-MIGRATE-003")
    text = LEGACY_FIXTURE.read_text(encoding="utf-8").replace("\n", "\r\n")
    second_report, second_queue, _ = _migrate(
        tmp_path / "second",
        "NEWS-MIGRATE-003",
        markdown_path=_legacy_copy(tmp_path / "second", text),
    )
    first_ids = [item["id"] for item in json.loads(first_queue.read_text(encoding="utf-8"))["items"]]
    second_ids = [item["id"] for item in json.loads(second_queue.read_text(encoding="utf-8"))["items"]]
    assert first_ids == second_ids, trace_message(
        "NEWS-MIGRATE-003", "IDs depend on path or line endings"
    )
    assert first_report["parsed"] == second_report["parsed"], trace_message(
        "NEWS-MIGRATE-003", "migration count changed with line endings"
    )


@pytest.mark.trace("NEWS-MIGRATE-004")
@pytest.mark.red_expected
def test_migration_preserves_source_url_and_explicit_evidence(tmp_path: Path) -> None:
    _, queue, _ = _migrate(tmp_path, "NEWS-MIGRATE-004")
    first = next(
        item
        for item in json.loads(queue.read_text(encoding="utf-8"))["items"]
        if item["title"] == "Un laboratorio publica un modelo verificable"
    )
    assert first["source"] == "Example Research", trace_message(
        "NEWS-MIGRATE-004", "source label was lost"
    )
    assert first["canonical_url"] == "https://example.test/news/modelo", trace_message(
        "NEWS-MIGRATE-004", "source URL was not canonicalized"
    )
    assert first["evidence"][0]["url"] == "https://example.test/research/model-card", trace_message(
        "NEWS-MIGRATE-004", "evidence URL was lost"
    )


@pytest.mark.trace("NEWS-MIGRATE-005")
@pytest.mark.red_expected
def test_existing_automated_note_marks_matching_pending_item_consumed(tmp_path: Path) -> None:
    note = tmp_path / "content" / "notas" / "2026-08-26-modelo.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "---\nautomation_news_ids:\n  - news-v1-8b714b8c\n---\n\nContenido\n",
        encoding="utf-8",
    )
    _, queue, _ = _migrate(tmp_path, "NEWS-MIGRATE-005", used_note_paths=[note])
    items = json.loads(queue.read_text(encoding="utf-8"))["items"]
    migrated = next(item for item in items if item["id"] == "news-v1-8b714b8c")
    assert migrated["status"] == "consumed", trace_message(
        "NEWS-MIGRATE-005", "note history did not consume matching item"
    )
    assert migrated["consumed_by"] == note.stem, trace_message(
        "NEWS-MIGRATE-005", "consuming note was not audited"
    )


@pytest.mark.trace("NEWS-MIGRATE-006")
@pytest.mark.red_expected
def test_partial_or_malformed_legacy_entry_is_reported_not_silently_dropped(tmp_path: Path) -> None:
    malformed = "# Cola\n\n- [ ] **2026-08-20 — Sin fuente**\n  Texto incompleto\n"
    report, queue, audit = _migrate(
        tmp_path,
        "NEWS-MIGRATE-006",
        markdown_path=_legacy_copy(tmp_path, malformed),
    )
    assert report["parsed"] == 0 and report["exceptions"] == 1, trace_message(
        "NEWS-MIGRATE-006", "malformed entry was silently accepted or dropped"
    )
    assert json.loads(queue.read_text(encoding="utf-8"))["items"] == [], trace_message(
        "NEWS-MIGRATE-006", "malformed entry entered structured queue"
    )
    assert json.loads(audit.read_text(encoding="utf-8"))["exceptions"][0]["line"] == 3, trace_message(
        "NEWS-MIGRATE-006", "audit does not identify malformed source line"
    )


@pytest.mark.trace("NEWS-MIGRATE-007")
@pytest.mark.red_expected
def test_second_migration_is_idempotent_and_does_not_rewrite_queue(tmp_path: Path) -> None:
    report, queue, audit = _migrate(tmp_path, "NEWS-MIGRATE-007")
    before_queue = queue.read_bytes()
    before_audit = audit.read_bytes()
    migrate = planned_callable(TARGET, "migrate_markdown_queue", "NEWS-MIGRATE-007")
    second = migrate(_legacy_copy(tmp_path), queue, audit_path=audit)
    assert second["added"] == 0 and second["unchanged"] == report["parsed"], trace_message(
        "NEWS-MIGRATE-007", "second run was not classified as unchanged"
    )
    assert queue.read_bytes() == before_queue and audit.read_bytes() == before_audit, trace_message(
        "NEWS-MIGRATE-007", "idempotent migration rewrote outputs"
    )


@pytest.mark.trace("NEWS-MIGRATE-008")
@pytest.mark.red_expected
def test_migration_handles_unicode_titles_sources_and_urls(tmp_path: Path) -> None:
    markdown = (
        "# Cola\n\n"
        "- [ ] **2026-08-24 — Ñandú IA publica evaluación en Córdoba**  \n"
        "  Fuente: [Investigación Pública](https://ejemplo.test/investigaci%C3%B3n)  \n"
        "  Evidencia: [Informe](https://ejemplo.test/informe)\n"
    )
    _, queue, _ = _migrate(
        tmp_path,
        "NEWS-MIGRATE-008",
        markdown_path=_legacy_copy(tmp_path, markdown),
    )
    item = json.loads(queue.read_text(encoding="utf-8"))["items"][0]
    assert item["title"] == "Ñandú IA publica evaluación en Córdoba", trace_message(
        "NEWS-MIGRATE-008", "Unicode title was corrupted"
    )
    assert item["source"] == "Investigación Pública", trace_message(
        "NEWS-MIGRATE-008", "Unicode source was corrupted"
    )


@pytest.mark.trace("NEWS-MIGRATE-009")
@pytest.mark.red_expected
def test_migrated_queue_has_version_revision_and_stable_order(tmp_path: Path) -> None:
    _, queue, _ = _migrate(tmp_path, "NEWS-MIGRATE-009")
    document = json.loads(queue.read_text(encoding="utf-8"))
    assert document["schema_version"] == 1 and document["revision"] == 1, trace_message(
        "NEWS-MIGRATE-009", "queue version or revision missing"
    )
    keys = [item["published_at"] for item in document["items"]]
    assert keys == sorted(keys), trace_message(
        "NEWS-MIGRATE-009", "migrated queue order is unstable"
    )


@pytest.mark.trace("NEWS-MIGRATE-010")
@pytest.mark.red_expected
def test_migration_audit_is_sanitized_relative_and_complete(tmp_path: Path) -> None:
    report, _, audit = _migrate(tmp_path, "NEWS-MIGRATE-010")
    data = json.loads(audit.read_text(encoding="utf-8"))
    serialized = json.dumps(data, ensure_ascii=False)
    assert str(tmp_path) not in serialized, trace_message(
        "NEWS-MIGRATE-010", "audit leaked an absolute temporary path"
    )
    assert "authorization" not in serialized.lower(), trace_message(
        "NEWS-MIGRATE-010", "audit contains credential-shaped field"
    )
    assert data["summary"] == report, trace_message(
        "NEWS-MIGRATE-010", "audit summary and return value diverge"
    )


@pytest.mark.trace("NEWS-GIT-001")
@pytest.mark.red_expected
def test_append_items_updates_queue_atomically_and_increments_revision_once(tmp_path: Path) -> None:
    append = planned_callable(TARGET, "append_items", "NEWS-GIT-001")
    queue = write_json(tmp_path / "queue.json", queue_document())
    result = append(
        queue,
        [news_item()],
        lock_path=tmp_path / "queue.lock",
        now="2026-08-26T12:00:00Z",
    )
    document = json.loads(queue.read_text(encoding="utf-8"))
    assert result["added"] == 1 and document["revision"] == 2, trace_message(
        "NEWS-GIT-001", "append did not make one atomic revision"
    )
    assert not list(tmp_path.glob("*.tmp")), trace_message(
        "NEWS-GIT-001", "append left temporary files"
    )


@pytest.mark.trace("NEWS-GIT-002")
@pytest.mark.red_expected
def test_duplicate_append_is_successful_noop_without_byte_rewrite(tmp_path: Path) -> None:
    append = planned_callable(TARGET, "append_items", "NEWS-GIT-002")
    queue = write_json(tmp_path / "queue.json", queue_document(news_item()))
    before = queue.read_bytes()
    result = append(queue, [news_item()], lock_path=tmp_path / "queue.lock")
    assert result["added"] == 0 and result["unchanged"] == 1, trace_message(
        "NEWS-GIT-002", "duplicate append was not a no-op"
    )
    assert queue.read_bytes() == before, trace_message(
        "NEWS-GIT-002", "duplicate append rewrote queue"
    )


@pytest.mark.trace("NEWS-GIT-003")
@pytest.mark.red_expected
def test_live_lock_blocks_competing_append_without_modification(tmp_path: Path) -> None:
    append = planned_callable(TARGET, "append_items", "NEWS-GIT-003")
    queue = write_json(tmp_path / "queue.json", queue_document())
    lock = tmp_path / "queue.lock"
    lock.write_text(
        json.dumps({"owner": "other-run", "acquired_at": "2026-08-26T11:59:00Z"}),
        encoding="utf-8",
    )
    before = queue.read_bytes()
    with pytest.raises((BlockingIOError, TimeoutError)):
        append(queue, [news_item()], lock_path=lock, run_id="news-run-2")
    assert queue.read_bytes() == before, trace_message(
        "NEWS-GIT-003", "lock contention modified queue"
    )


@pytest.mark.trace("NEWS-GIT-004")
@pytest.mark.red_expected
def test_atomic_replace_failure_preserves_original_and_cleans_temporary_file(tmp_path: Path) -> None:
    append = planned_callable(TARGET, "append_items", "NEWS-GIT-004")
    queue = write_json(tmp_path / "queue.json", queue_document())
    before = queue.read_bytes()

    def fail_replace(_: Path, __: Path) -> None:
        raise OSError("synthetic replace failure")

    with pytest.raises(OSError, match="replace"):
        append(queue, [news_item()], lock_path=tmp_path / "queue.lock", replace=fail_replace)
    assert queue.read_bytes() == before, trace_message(
        "NEWS-GIT-004", "failed append corrupted original queue"
    )
    assert not list(tmp_path.glob("*.tmp")), trace_message(
        "NEWS-GIT-004", "failed append left a temporary file"
    )


@pytest.mark.trace("NEWS-GIT-005")
@pytest.mark.red_expected
def test_consume_requires_reservation_owner_and_is_atomic_with_note_id(tmp_path: Path) -> None:
    consume = planned_callable(TARGET, "consume_items", "NEWS-GIT-005")
    reserved = news_item(
        status="reserved",
        reserved_by="blog-run-1",
        reserved_at="2026-08-26T12:00:00Z",
    )
    queue = write_json(tmp_path / "queue.json", queue_document(reserved))
    with pytest.raises(PermissionError):
        consume(queue, run_id="blog-run-other", note_id="note-1")
    result = consume(
        queue,
        run_id="blog-run-1",
        note_id="2026-08-26-modelo",
        now="2026-08-26T12:30:00Z",
    )
    item = json.loads(queue.read_text(encoding="utf-8"))["items"][0]
    assert result["consumed"] == 1 and item["status"] == "consumed", trace_message(
        "NEWS-GIT-005", "owned reservation was not consumed"
    )
    assert item["consumed_by"] == "2026-08-26-modelo", trace_message(
        "NEWS-GIT-005", "note ID was not linked to consumption"
    )


@pytest.mark.trace("NEWS-GIT-006")
@pytest.mark.red_expected
def test_news_queue_module_has_no_git_push_force_or_external_network_side_effects() -> None:
    source = require_target(TARGET, "NEWS-GIT-006").read_text(encoding="utf-8")
    forbidden = ("git push", "--force", "urllib.request", "requests.", "httpx.", "subprocess.run")
    found = [value for value in forbidden if value in source]
    assert not found, trace_message(
        "NEWS-GIT-006", f"news queue owns forbidden external effects: {found}"
    )
