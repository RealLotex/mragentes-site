from __future__ import annotations

import copy
from pathlib import Path

import pytest

from tests.fixtures.factories import news_item
from tests.support.contracts import trace_message
from tests.support.planned import planned_callable, planned_signature


TARGET = "scripts/automation/blog_guard.py"


def _slug(title: str, trace_id: str, **kwargs: object) -> str:
    portable_slug = planned_callable(TARGET, "portable_slug", trace_id)
    result = portable_slug(title, **kwargs)
    assert isinstance(result, str), trace_message(trace_id, "portable_slug must return text")
    return result


def _select(items: list[dict[str, object]], trace_id: str, **kwargs: object):
    select = planned_callable(TARGET, "select_news", trace_id)
    result = select(copy.deepcopy(items), **kwargs)
    assert isinstance(result, list), trace_message(trace_id, "select_news must return a list")
    return result


@pytest.mark.trace("BLOG-SLUG-001")
@pytest.mark.red_expected
def test_blog_guard_exposes_all_planned_entrypoints() -> None:
    signatures = {
        "portable_slug": ("title", "max_component_bytes", "prefix", "suffix"),
        "blog_run_id": ("local_date", "slug"),
        "find_existing_note": ("content_dir", "run_id", "local_date"),
        "select_news": ("items", "run_id", "count"),
        "build_front_matter": ("title", "local_date", "description", "image", "image_alt", "tags", "sources", "automation_id"),
        "validate_front_matter": ("front_matter",),
        "build_atomic_change": ("root", "run_id", "note_relative_path", "note_content", "asset_source", "asset_relative_path", "queue_path", "queue_document"),
    }
    for symbol, parameters in signatures.items():
        planned_signature(TARGET, symbol, parameters, "BLOG-SLUG-001")


@pytest.mark.trace("BLOG-SLUG-002")
@pytest.mark.red_expected
def test_short_ascii_slug_is_readable_and_stable() -> None:
    first = _slug(
        "Automatización simple para PyMEs",
        "BLOG-SLUG-002",
        max_component_bytes=143,
        prefix="2026-08-26-",
        suffix=".md",
    )
    second = _slug(
        "Automatización simple para PyMEs",
        "BLOG-SLUG-002",
        max_component_bytes=143,
        prefix="2026-08-26-",
        suffix=".md",
    )
    assert first == second == "automatizacion-simple-para-pymes", trace_message(
        "BLOG-SLUG-002", f"unexpected readable slug: {first}"
    )


@pytest.mark.trace("BLOG-SLUG-003")
@pytest.mark.red_expected
def test_unicode_accents_punctuation_and_emoji_normalize_to_ascii() -> None:
    observed = _slug(
        "¡Ñandú, IA & corazón! 🤖",
        "BLOG-SLUG-003",
        max_component_bytes=143,
        prefix="2026-08-26-",
        suffix=".md",
    )
    assert observed == "nandu-ia-corazon", trace_message(
        "BLOG-SLUG-003", f"Unicode slug is not normalized: {observed}"
    )
    assert observed.isascii(), trace_message("BLOG-SLUG-003", "slug is not ASCII")


@pytest.mark.trace("BLOG-SLUG-004")
@pytest.mark.red_expected
def test_slug_reserves_date_prefix_and_extension_within_143_bytes() -> None:
    title = (
        "OpenAI pausa su entrenamiento por cibercapacidad crítica Claude diseña proteínas "
        "que funcionan y Qwen corona a China la semana en que la IA se puso frenos a sí misma"
    )
    prefix = "2026-08-23-"
    suffix = ".md"
    observed = _slug(
        title,
        "BLOG-SLUG-004",
        max_component_bytes=143,
        prefix=prefix,
        suffix=suffix,
    )
    basename = f"{prefix}{observed}{suffix}"
    assert len(basename.encode("utf-8")) <= 143, trace_message(
        "BLOG-SLUG-004", f"portable basename still exceeds limit: {len(basename.encode('utf-8'))}"
    )


@pytest.mark.trace("BLOG-SLUG-005")
@pytest.mark.red_expected
def test_slug_never_splits_multibyte_character_when_budget_is_tight() -> None:
    observed = _slug(
        "á" * 200,
        "BLOG-SLUG-005",
        max_component_bytes=31,
        prefix="2026-08-26-",
        suffix=".md",
    )
    encoded = observed.encode("utf-8")
    assert encoded.decode("utf-8") == observed, trace_message(
        "BLOG-SLUG-005", "slug cut a UTF-8 sequence"
    )
    assert len(("2026-08-26-" + observed + ".md").encode("utf-8")) <= 31, trace_message(
        "BLOG-SLUG-005", "tight budget was exceeded"
    )


@pytest.mark.trace("BLOG-SLUG-006")
@pytest.mark.red_expected
def test_truncated_slug_adds_stable_collision_hash() -> None:
    title = "Modelo verificable " * 30
    first = _slug(
        title,
        "BLOG-SLUG-006",
        max_component_bytes=70,
        prefix="2026-08-26-",
        suffix=".md",
    )
    second = _slug(
        title,
        "BLOG-SLUG-006",
        max_component_bytes=70,
        prefix="2026-08-26-",
        suffix=".md",
    )
    assert first == second, trace_message("BLOG-SLUG-006", "truncation hash is unstable")
    stem, separator, digest = first.rpartition("-")
    assert stem and separator and len(digest) >= 8 and all(c in "0123456789abcdef" for c in digest), trace_message(
        "BLOG-SLUG-006", f"truncated slug lacks stable hex suffix: {first}"
    )


@pytest.mark.trace("BLOG-SLUG-007")
@pytest.mark.red_expected
def test_long_titles_with_same_prefix_do_not_collide() -> None:
    common = "Una noticia muy importante sobre inteligencia artificial " * 10
    first = _slug(
        common + "evento alfa",
        "BLOG-SLUG-007",
        max_component_bytes=80,
        prefix="2026-08-26-",
        suffix=".md",
    )
    second = _slug(
        common + "evento beta",
        "BLOG-SLUG-007",
        max_component_bytes=80,
        prefix="2026-08-26-",
        suffix=".md",
    )
    assert first != second, trace_message("BLOG-SLUG-007", "long title collision was not prevented")


@pytest.mark.trace("BLOG-SLUG-008")
@pytest.mark.red_expected
def test_empty_or_symbol_only_title_fails_closed() -> None:
    portable_slug = planned_callable(TARGET, "portable_slug", "BLOG-SLUG-008")
    for title in ("", "   ", "🤖🚀", "---"):
        with pytest.raises(ValueError):
            portable_slug(title, max_component_bytes=143, prefix="2026-08-26-", suffix=".md")


@pytest.mark.trace("BLOG-SLUG-009")
@pytest.mark.red_expected
def test_impossible_component_budget_is_rejected_not_silently_overflowed() -> None:
    portable_slug = planned_callable(TARGET, "portable_slug", "BLOG-SLUG-009")
    for budget in (0, 10, -1):
        with pytest.raises(ValueError):
            portable_slug(
                "Título válido",
                max_component_bytes=budget,
                prefix="2026-08-26-",
                suffix=".md",
            )


@pytest.mark.trace("BLOG-SLUG-010")
@pytest.mark.red_expected
def test_existing_short_slug_is_not_rewritten_and_legacy_alias_is_preservable() -> None:
    portable_slug = planned_callable(TARGET, "portable_slug", "BLOG-SLUG-010")
    result = portable_slug(
        "modelo-verificable",
        max_component_bytes=143,
        prefix="2026-08-26-",
        suffix=".md",
        already_slug=True,
        legacy_path="/notas/2026-08-26-modelo-verificable/",
    )
    assert result == {
        "slug": "modelo-verificable",
        "legacy_alias": "/notas/2026-08-26-modelo-verificable/",
        "truncated": False,
    }, trace_message("BLOG-SLUG-010", f"short legacy slug changed: {result}")


@pytest.mark.trace("BLOG-SELECT-001")
@pytest.mark.red_expected
def test_blog_run_id_is_timezone_date_kind_and_slug_stable() -> None:
    run_id = planned_callable(TARGET, "blog_run_id", "BLOG-SELECT-001")
    first = run_id("2026-08-26", "modelo-verificable")
    second = run_id("2026-08-26", "modelo-verificable")
    assert first == second == "blog:2026-08-26:modelo-verificable", trace_message(
        "BLOG-SELECT-001", f"unexpected blog run id: {first}"
    )


@pytest.mark.trace("BLOG-SELECT-002")
@pytest.mark.red_expected
def test_find_existing_note_returns_unique_matching_automation_id(tmp_path: Path) -> None:
    find_existing = planned_callable(TARGET, "find_existing_note", "BLOG-SELECT-002")
    content = tmp_path / "notas"
    content.mkdir()
    expected = content / "2026-08-26-modelo.md"
    expected.write_text(
        "---\nautomation_id: \"blog:2026-08-26:modelo\"\ndate: 2026-08-26\n---\n",
        encoding="utf-8",
    )
    found = find_existing(
        content,
        run_id="blog:2026-08-26:modelo",
        local_date="2026-08-26",
    )
    assert Path(found) == expected, trace_message("BLOG-SELECT-002", "matching note was not found")


@pytest.mark.trace("BLOG-SELECT-003")
@pytest.mark.red_expected
def test_find_existing_note_returns_none_without_match_and_rejects_duplicates(tmp_path: Path) -> None:
    find_existing = planned_callable(TARGET, "find_existing_note", "BLOG-SELECT-003")
    content = tmp_path / "notas"
    content.mkdir()
    assert find_existing(content, run_id="blog:2026-08-26:x", local_date="2026-08-26") is None, trace_message(
        "BLOG-SELECT-003", "empty directory produced a match"
    )
    for name in ("a.md", "b.md"):
        (content / name).write_text(
            "---\nautomation_id: \"blog:2026-08-26:x\"\ndate: 2026-08-26\n---\n",
            encoding="utf-8",
        )
    with pytest.raises(ValueError, match="multiple"):
        find_existing(content, run_id="blog:2026-08-26:x", local_date="2026-08-26")


@pytest.mark.trace("BLOG-SELECT-004")
@pytest.mark.red_expected
def test_select_news_returns_two_or_three_pending_items_including_older_news() -> None:
    items = [
        news_item(item_id="news-v1-old", published_at="2026-08-18T12:00:00Z", url="https://a.test/old"),
        news_item(item_id="news-v1-mid", published_at="2026-08-22T12:00:00Z", url="https://b.test/mid"),
        news_item(item_id="news-v1-new", published_at="2026-08-25T12:00:00Z", url="https://c.test/new"),
    ]
    selected = _select(items, "BLOG-SELECT-004", run_id="blog-run-1", count=3)
    assert len(selected) == 3 and "news-v1-old" in {item["id"] for item in selected}, trace_message(
        "BLOG-SELECT-004", "older verified news was not selectable"
    )


@pytest.mark.trace("BLOG-SELECT-005")
@pytest.mark.red_expected
def test_select_news_maximizes_entity_source_and_topic_variety() -> None:
    items = [
        news_item(item_id="news-v1-a1", source="A", entity="A", tags=["modelos"], url="https://a.test/1"),
        news_item(item_id="news-v1-a2", source="A", entity="A", tags=["modelos"], url="https://a.test/2"),
        news_item(item_id="news-v1-b", source="B", entity="B", tags=["regulacion"], url="https://b.test/1"),
    ]
    selected = _select(items, "BLOG-SELECT-005", run_id="blog-run-1", count=2)
    assert {item["entity"] for item in selected} == {"A", "B"}, trace_message(
        "BLOG-SELECT-005", "selection did not diversify entities"
    )


@pytest.mark.trace("BLOG-SELECT-006")
@pytest.mark.red_expected
def test_select_news_excludes_consumed_rejected_and_foreign_reserved_items() -> None:
    items = [
        news_item(item_id="pending", url="https://a.test/pending"),
        news_item(item_id="consumed", status="consumed", consumed_by="note", consumed_at="2026-08-25T12:00:00Z", url="https://a.test/consumed"),
        news_item(item_id="rejected", status="rejected", rejection_reason="bad", url="https://a.test/rejected"),
        news_item(item_id="reserved", status="reserved", reserved_by="other", reserved_at="2026-08-26T12:00:00Z", url="https://a.test/reserved"),
    ]
    selected = _select(items, "BLOG-SELECT-006", run_id="blog-run-1", count=3)
    assert [item["id"] for item in selected] == ["pending"], trace_message(
        "BLOG-SELECT-006", "unavailable queue state was selected"
    )


@pytest.mark.trace("BLOG-SELECT-007")
@pytest.mark.red_expected
def test_select_news_is_deterministic_and_does_not_mutate_queue_items() -> None:
    items = [
        news_item(item_id=f"news-v1-{letter}", url=f"https://{letter}.test/story")
        for letter in "dcba"
    ]
    original = copy.deepcopy(items)
    first = _select(items, "BLOG-SELECT-007", run_id="blog-run-1", count=3)
    second = _select(list(reversed(items)), "BLOG-SELECT-007", run_id="blog-run-1", count=3)
    assert [item["id"] for item in first] == [item["id"] for item in second], trace_message(
        "BLOG-SELECT-007", "selection depends on input order"
    )
    assert items == original, trace_message("BLOG-SELECT-007", "selection mutated queue")


@pytest.mark.trace("BLOG-SELECT-008")
@pytest.mark.red_expected
def test_select_news_allows_explicit_skip_when_fewer_than_two_quality_items() -> None:
    selected = _select(
        [news_item(item_id="only")],
        "BLOG-SELECT-008",
        run_id="blog-run-1",
        count=3,
        minimum=2,
    )
    assert selected == [], trace_message(
        "BLOG-SELECT-008", "single item should produce an explicit no-publication selection"
    )
