from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tests.fixtures.factories import news_item, queue_document, write_json
from tests.support.contracts import trace_message
from tests.support.planned import planned_callable


TARGET = "scripts/automation/news_queue.py"


def _accepted(existing: list[dict[str, object]], candidates: list[dict[str, object]], trace_id: str):
    deduplicate = planned_callable(TARGET, "deduplicate", trace_id)
    result = deduplicate(copy.deepcopy(existing), copy.deepcopy(candidates))
    assert isinstance(result, list), trace_message(trace_id, "deduplicate must return a list")
    return result


def _queue_path(tmp_path: Path, *items: dict[str, object]) -> Path:
    return write_json(tmp_path / "queue.json", queue_document(*items))


@pytest.mark.trace("NEWS-DEDUP-001")
@pytest.mark.red_expected
def test_exact_canonical_url_duplicate_is_removed() -> None:
    existing = [news_item(item_id="news-v1-existing", url="https://example.test/a")]
    candidate = news_item(item_id="news-v1-new", url="https://example.test/a")
    assert _accepted(existing, [candidate], "NEWS-DEDUP-001") == [], trace_message(
        "NEWS-DEDUP-001", "exact URL duplicate was accepted"
    )


@pytest.mark.trace("NEWS-DEDUP-002")
@pytest.mark.red_expected
def test_tracking_and_query_order_variants_are_url_duplicates() -> None:
    existing = [news_item(url="https://example.test/a?id=7&utm_source=rss")]
    candidate = news_item(url="https://EXAMPLE.TEST:443/a?fbclid=fake&id=7")
    assert _accepted(existing, [candidate], "NEWS-DEDUP-002") == [], trace_message(
        "NEWS-DEDUP-002", "canonical URL duplicate was accepted"
    )


@pytest.mark.trace("NEWS-DEDUP-003")
@pytest.mark.red_expected
def test_normalized_title_entity_and_date_detect_same_event_across_sources() -> None:
    existing = [
        news_item(
            title="Ágora IA lanza Modelo Uno",
            entity="Ágora IA",
            url="https://source-a.test/story",
        )
    ]
    candidate = news_item(
        title="Agora IA: lanza el modelo UNO",
        entity="Agora IA",
        url="https://source-b.test/noticia",
    )
    assert _accepted(existing, [candidate], "NEWS-DEDUP-003") == [], trace_message(
        "NEWS-DEDUP-003", "same cross-source event was accepted"
    )


@pytest.mark.trace("NEWS-DEDUP-004")
@pytest.mark.red_expected
def test_same_entity_with_different_date_or_event_remains_distinct() -> None:
    existing = [news_item(title="Ágora lanza Modelo Uno", entity="Ágora")]
    candidates = [
        news_item(
            item_id="news-v1-two",
            title="Ágora lanza Modelo Dos",
            entity="Ágora",
            url="https://example.test/modelo-dos",
        ),
        news_item(
            item_id="news-v1-update",
            title="Ágora actualiza Modelo Uno",
            entity="Ágora",
            url="https://example.test/modelo-uno-update",
            published_at="2026-09-24T13:30:00Z",
        ),
    ]
    accepted = _accepted(existing, candidates, "NEWS-DEDUP-004")
    assert [item["id"] for item in accepted] == ["news-v1-two", "news-v1-update"], trace_message(
        "NEWS-DEDUP-004", "different events were collapsed"
    )


@pytest.mark.trace("NEWS-DEDUP-005")
@pytest.mark.red_expected
def test_duplicates_inside_same_candidate_batch_are_removed_stably() -> None:
    first = news_item(item_id="news-v1-first", url="https://example.test/a")
    duplicate = news_item(item_id="news-v1-second", url="https://example.test/a?utm_source=x")
    result = _accepted([], [first, duplicate], "NEWS-DEDUP-005")
    assert [item["id"] for item in result] == ["news-v1-first"], trace_message(
        "NEWS-DEDUP-005", "batch duplicate was not reduced to first occurrence"
    )


@pytest.mark.trace("NEWS-DEDUP-006")
@pytest.mark.red_expected
def test_consumed_history_prevents_readding_previously_published_event() -> None:
    consumed = news_item(
        status="consumed",
        consumed_by="blog-note-1",
        consumed_at="2026-08-25T12:00:00Z",
    )
    candidate = news_item(status="pending", item_id="news-v1-reseen")
    assert _accepted([consumed], [candidate], "NEWS-DEDUP-006") == [], trace_message(
        "NEWS-DEDUP-006", "consumed event was re-added"
    )


@pytest.mark.trace("NEWS-DEDUP-007")
@pytest.mark.red_expected
def test_reserved_event_is_not_available_to_another_run() -> None:
    reserved = news_item(
        status="reserved",
        reserved_by="blog-run-a",
        reserved_at="2026-08-26T12:00:00Z",
    )
    candidate = news_item(status="pending", item_id="news-v1-reseen")
    assert _accepted([reserved], [candidate], "NEWS-DEDUP-007") == [], trace_message(
        "NEWS-DEDUP-007", "reserved event was duplicated"
    )


@pytest.mark.trace("NEWS-DEDUP-008")
@pytest.mark.red_expected
def test_rejected_event_can_only_return_with_explicit_new_evidence() -> None:
    rejected = news_item(status="rejected", rejection_reason="unverified")
    unchanged = news_item(item_id="news-v1-unchanged")
    stronger = news_item(
        item_id="news-v1-stronger",
        evidence=[
            {"url": "https://example.test/research/model-card", "claim": "Ficha técnica"},
            {"url": "https://example.test/regulator/filing", "claim": "Registro oficial"},
        ],
        reconsider_rejected=True,
    )
    assert _accepted([rejected], [unchanged], "NEWS-DEDUP-008") == [], trace_message(
        "NEWS-DEDUP-008", "rejected item returned without new evidence"
    )
    accepted = _accepted([rejected], [stronger], "NEWS-DEDUP-008")
    assert [item["id"] for item in accepted] == ["news-v1-stronger"], trace_message(
        "NEWS-DEDUP-008", "explicitly strengthened item could not be reconsidered"
    )


@pytest.mark.trace("NEWS-DEDUP-009")
@pytest.mark.red_expected
def test_deduplication_does_not_mutate_inputs_and_is_repeatable() -> None:
    existing = [news_item(item_id="news-v1-existing")]
    candidates = [news_item(item_id="news-v1-new", url="https://example.test/new")]
    before_existing = copy.deepcopy(existing)
    before_candidates = copy.deepcopy(candidates)
    first = _accepted(existing, candidates, "NEWS-DEDUP-009")
    second = _accepted(existing, candidates, "NEWS-DEDUP-009")
    assert first == second, trace_message("NEWS-DEDUP-009", "dedupe is not deterministic")
    assert existing == before_existing and candidates == before_candidates, trace_message(
        "NEWS-DEDUP-009", "dedupe mutated caller data"
    )


@pytest.mark.trace("NEWS-DEDUP-010")
@pytest.mark.red_expected
def test_same_stable_id_with_different_payload_fails_as_collision() -> None:
    deduplicate = planned_callable(TARGET, "deduplicate", "NEWS-DEDUP-010")
    existing = [news_item(item_id="news-v1-collision", title="Evento A")]
    candidate = news_item(
        item_id="news-v1-collision",
        title="Evento B",
        url="https://example.test/other",
    )
    with pytest.raises(ValueError, match="collision"):
        deduplicate(existing, [candidate])


@pytest.mark.trace("NEWS-SELECT-001")
@pytest.mark.red_expected
def test_reserve_selects_requested_pending_count_and_persists_owner(tmp_path: Path) -> None:
    reserve = planned_callable(TARGET, "reserve_items", "NEWS-SELECT-001")
    path = _queue_path(
        tmp_path,
        news_item(item_id="news-v1-a", url="https://a.test/1"),
        news_item(item_id="news-v1-b", url="https://b.test/2"),
        news_item(item_id="news-v1-c", url="https://c.test/3"),
    )
    selected = reserve(path, run_id="blog-run-1", count=2, now="2026-08-26T12:00:00Z")
    assert len(selected) == 2, trace_message("NEWS-SELECT-001", "wrong selection count")
    persisted = json.loads(path.read_text(encoding="utf-8"))
    reserved = [item for item in persisted["items"] if item["status"] == "reserved"]
    assert len(reserved) == 2 and {item["reserved_by"] for item in reserved} == {"blog-run-1"}, trace_message(
        "NEWS-SELECT-001", "reservation owner was not persisted"
    )


@pytest.mark.trace("NEWS-SELECT-002")
@pytest.mark.red_expected
def test_reserve_allows_zero_when_no_item_meets_quality_gate(tmp_path: Path) -> None:
    reserve = planned_callable(TARGET, "reserve_items", "NEWS-SELECT-002")
    path = _queue_path(tmp_path, news_item(status="rejected", rejection_reason="unverified"))
    selected = reserve(path, run_id="blog-run-1", count=3, now="2026-08-26T12:00:00Z")
    assert selected == [], trace_message("NEWS-SELECT-002", "non-pending item was selected")


@pytest.mark.trace("NEWS-SELECT-003")
@pytest.mark.red_expected
def test_reserve_can_select_verified_news_from_previous_days(tmp_path: Path) -> None:
    reserve = planned_callable(TARGET, "reserve_items", "NEWS-SELECT-003")
    path = _queue_path(
        tmp_path,
        news_item(item_id="news-v1-old", published_at="2026-08-18T12:00:00Z"),
    )
    selected = reserve(path, run_id="blog-run-1", count=1, now="2026-08-26T12:00:00Z")
    assert [item["id"] for item in selected] == ["news-v1-old"], trace_message(
        "NEWS-SELECT-003", "verified older news was discarded"
    )


@pytest.mark.trace("NEWS-SELECT-004")
@pytest.mark.red_expected
def test_reserve_prefers_source_and_entity_diversity(tmp_path: Path) -> None:
    reserve = planned_callable(TARGET, "reserve_items", "NEWS-SELECT-004")
    path = _queue_path(
        tmp_path,
        news_item(item_id="news-v1-a1", source="Source A", entity="Entity A", url="https://a.test/1"),
        news_item(item_id="news-v1-a2", source="Source A", entity="Entity A", url="https://a.test/2"),
        news_item(item_id="news-v1-b", source="Source B", entity="Entity B", url="https://b.test/1"),
    )
    selected = reserve(path, run_id="blog-run-1", count=2, now="2026-08-26T12:00:00Z")
    assert {item["entity"] for item in selected} == {"Entity A", "Entity B"}, trace_message(
        "NEWS-SELECT-004", "selection lacks entity diversity"
    )


@pytest.mark.trace("NEWS-SELECT-005")
@pytest.mark.red_expected
def test_reserve_never_takes_item_owned_by_another_run(tmp_path: Path) -> None:
    reserve = planned_callable(TARGET, "reserve_items", "NEWS-SELECT-005")
    foreign = news_item(
        item_id="news-v1-foreign",
        status="reserved",
        reserved_by="blog-run-other",
        reserved_at="2026-08-26T11:00:00Z",
    )
    path = _queue_path(tmp_path, foreign, news_item(item_id="news-v1-open", url="https://b.test/open"))
    selected = reserve(path, run_id="blog-run-1", count=2, now="2026-08-26T12:00:00Z")
    assert [item["id"] for item in selected] == ["news-v1-open"], trace_message(
        "NEWS-SELECT-005", "foreign reservation was stolen"
    )


@pytest.mark.trace("NEWS-SELECT-006")
@pytest.mark.red_expected
def test_same_run_reservation_is_idempotent(tmp_path: Path) -> None:
    reserve = planned_callable(TARGET, "reserve_items", "NEWS-SELECT-006")
    path = _queue_path(tmp_path, news_item())
    first = reserve(path, run_id="blog-run-1", count=1, now="2026-08-26T12:00:00Z")
    bytes_after_first = path.read_bytes()
    second = reserve(path, run_id="blog-run-1", count=1, now="2026-08-26T12:05:00Z")
    assert first == second, trace_message("NEWS-SELECT-006", "same run selected new items")
    assert path.read_bytes() == bytes_after_first, trace_message(
        "NEWS-SELECT-006", "idempotent reservation rewrote queue"
    )


@pytest.mark.trace("NEWS-SELECT-007")
@pytest.mark.red_expected
def test_reservation_order_is_deterministic_for_same_run_id(tmp_path: Path) -> None:
    reserve = planned_callable(TARGET, "reserve_items", "NEWS-SELECT-007")
    items = [
        news_item(item_id=f"news-v1-{letter}", url=f"https://{letter}.test/news")
        for letter in "dcba"
    ]
    first_path = _queue_path(tmp_path / "first", *items)
    second_path = _queue_path(tmp_path / "second", *reversed(items))
    first = reserve(first_path, run_id="blog-run-1", count=3, now="2026-08-26T12:00:00Z")
    second = reserve(second_path, run_id="blog-run-1", count=3, now="2026-08-26T12:00:00Z")
    assert [item["id"] for item in first] == [item["id"] for item in second], trace_message(
        "NEWS-SELECT-007", "selection depends on input order"
    )


@pytest.mark.trace("NEWS-SELECT-008")
@pytest.mark.red_expected
def test_invalid_selection_count_fails_without_modifying_queue(tmp_path: Path) -> None:
    reserve = planned_callable(TARGET, "reserve_items", "NEWS-SELECT-008")
    path = _queue_path(tmp_path, news_item())
    before = path.read_bytes()
    for count in (-1, 5, "3"):
        with pytest.raises((TypeError, ValueError)):
            reserve(path, run_id="blog-run-1", count=count, now="2026-08-26T12:00:00Z")
    assert path.read_bytes() == before, trace_message(
        "NEWS-SELECT-008", "invalid count modified queue"
    )
