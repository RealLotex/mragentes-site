from __future__ import annotations

import copy
import re

import pytest

from tests.fixtures.factories import news_item
from tests.support.contracts import trace_message
from tests.support.planned import planned_callable, planned_signature


TARGET = "scripts/automation/news_queue.py"


def _validated(item: dict[str, object], trace_id: str) -> dict[str, object]:
    validate = planned_callable(TARGET, "validate_news_item", trace_id)
    result = validate(copy.deepcopy(item))
    assert isinstance(result, dict), trace_message(trace_id, "validator must return a mapping")
    return result


@pytest.mark.trace("NEWS-SCHEMA-001")
@pytest.mark.red_expected
def test_news_queue_exposes_all_planned_entrypoints() -> None:
    signatures = {
        "canonicalize_url": ("url",),
        "stable_news_id": ("item",),
        "validate_news_item": ("item",),
        "load_queue": ("path",),
        "deduplicate": ("existing", "candidates"),
        "append_items": ("queue_path", "items"),
        "reserve_items": ("queue_path", "run_id"),
        "consume_items": ("queue_path", "run_id", "note_id"),
        "migrate_markdown_queue": ("markdown_path", "queue_path"),
    }
    for symbol, parameters in signatures.items():
        planned_signature(TARGET, symbol, parameters, "NEWS-SCHEMA-001")


@pytest.mark.trace("NEWS-SCHEMA-002")
@pytest.mark.red_expected
def test_minimal_valid_news_item_is_accepted_without_mutating_input() -> None:
    item = news_item(tags=[])
    original = copy.deepcopy(item)
    result = _validated(item, "NEWS-SCHEMA-002")
    assert item == original, trace_message("NEWS-SCHEMA-002", "validator mutated its input")
    assert result["id"] == original["id"], trace_message(
        "NEWS-SCHEMA-002", "validator changed stable id"
    )


@pytest.mark.trace("NEWS-SCHEMA-003")
@pytest.mark.red_expected
def test_complete_news_item_preserves_evidence_tags_and_optional_editorial_fields() -> None:
    item = news_item(
        summary="Resumen comprobable.",
        language="es",
        geography="AR",
        priority=3,
        editorial_notes="Relacionar con automatización PyME.",
    )
    result = _validated(item, "NEWS-SCHEMA-003")
    for key in ("evidence", "tags", "summary", "language", "geography", "priority"):
        assert result[key] == item[key], trace_message(
            "NEWS-SCHEMA-003", f"complete field was lost: {key}"
        )


@pytest.mark.trace("NEWS-SCHEMA-004")
@pytest.mark.red_expected
def test_required_news_fields_cannot_be_missing_blank_or_null() -> None:
    validate = planned_callable(TARGET, "validate_news_item", "NEWS-SCHEMA-004")
    for key, replacement in (
        ("id", None),
        ("title", "  "),
        ("canonical_url", None),
        ("source", ""),
        ("published_at", None),
        ("status", None),
    ):
        candidate = news_item()
        candidate[key] = replacement
        with pytest.raises((TypeError, ValueError)):
            validate(candidate)


@pytest.mark.trace("NEWS-SCHEMA-005")
@pytest.mark.red_expected
def test_unknown_or_dangerous_fields_are_rejected() -> None:
    validate = planned_callable(TARGET, "validate_news_item", "NEWS-SCHEMA-005")
    for key in ("token", "authorization", "raw_html", "subscriber_endpoint", "unexpected"):
        candidate = news_item(**{key: "synthetic"})
        with pytest.raises(ValueError):
            validate(candidate)


@pytest.mark.trace("NEWS-SCHEMA-006")
@pytest.mark.red_expected
def test_news_status_enum_and_transition_metadata_are_closed() -> None:
    validate = planned_callable(TARGET, "validate_news_item", "NEWS-SCHEMA-006")
    valid = ("pending", "reserved", "consumed", "rejected")
    for status in valid:
        candidate = news_item(status=status)
        if status == "reserved":
            candidate.update(reserved_by="blog-2026-08-26", reserved_at="2026-08-26T12:00:00Z")
        if status == "consumed":
            candidate.update(consumed_by="blog-note-1", consumed_at="2026-08-26T12:30:00Z")
        assert validate(candidate)["status"] == status, trace_message(
            "NEWS-SCHEMA-006", f"valid status rejected: {status}"
        )
    with pytest.raises(ValueError):
        validate(news_item(status="published"))


@pytest.mark.trace("NEWS-SCHEMA-007")
@pytest.mark.red_expected
def test_all_news_timestamps_require_rfc3339_timezone_and_real_calendar_dates() -> None:
    validate = planned_callable(TARGET, "validate_news_item", "NEWS-SCHEMA-007")
    valid = news_item(published_at="2026-08-24T10:30:00-03:00")
    assert validate(valid)["published_at"].endswith("-03:00"), trace_message(
        "NEWS-SCHEMA-007", "valid offset timestamp was not preserved"
    )
    for invalid in ("2026-08-24", "2026-08-24T10:30:00", "2026-02-30T10:30:00Z"):
        with pytest.raises(ValueError):
            validate(news_item(published_at=invalid))


@pytest.mark.trace("NEWS-SCHEMA-008")
@pytest.mark.red_expected
def test_news_urls_allow_public_http_https_only() -> None:
    validate = planned_callable(TARGET, "validate_news_item", "NEWS-SCHEMA-008")
    assert validate(news_item(url="https://example.test/report"))["canonical_url"], trace_message(
        "NEWS-SCHEMA-008", "public HTTPS URL was rejected"
    )
    for invalid in (
        "file:///etc/passwd",
        "data:text/plain,secret",
        "ftp://example.test/file",
        "http://127.0.0.1/private",
        "http://169.254.169.254/latest/meta-data",
    ):
        with pytest.raises(ValueError):
            validate(news_item(url=invalid))


@pytest.mark.trace("NEWS-SCHEMA-009")
@pytest.mark.red_expected
def test_evidence_requires_public_url_and_nonempty_specific_claim() -> None:
    validate = planned_callable(TARGET, "validate_news_item", "NEWS-SCHEMA-009")
    with pytest.raises(ValueError):
        validate(news_item(evidence=[]))
    with pytest.raises(ValueError):
        validate(news_item(evidence=[{"url": "https://example.test/e", "claim": ""}]))
    with pytest.raises(ValueError):
        validate(news_item(evidence=[{"url": "http://127.0.0.1/e", "claim": "Dato"}]))


@pytest.mark.trace("NEWS-SCHEMA-010")
@pytest.mark.red_expected
def test_news_text_and_collection_limits_fail_closed() -> None:
    validate = planned_callable(TARGET, "validate_news_item", "NEWS-SCHEMA-010")
    invalid_items = (
        news_item(title="x" * 501),
        news_item(source="x" * 201),
        news_item(tags=[f"tag-{index}" for index in range(51)]),
        news_item(evidence=[{"url": f"https://example.test/{index}", "claim": "dato"} for index in range(51)]),
    )
    for item in invalid_items:
        with pytest.raises(ValueError):
            validate(item)


@pytest.mark.trace("NEWS-SCHEMA-011")
@pytest.mark.red_expected
def test_schema_version_accepts_current_and_rejects_unknown_future_version() -> None:
    validate = planned_callable(TARGET, "validate_news_item", "NEWS-SCHEMA-011")
    assert validate(news_item(schema_version=1))["schema_version"] == 1, trace_message(
        "NEWS-SCHEMA-011", "current schema was rejected"
    )
    for version in (0, 2, "1", None):
        with pytest.raises((TypeError, ValueError)):
            validate(news_item(schema_version=version))


@pytest.mark.trace("NEWS-SCHEMA-012")
@pytest.mark.red_expected
def test_reserved_and_consumed_items_require_matching_audit_fields() -> None:
    validate = planned_callable(TARGET, "validate_news_item", "NEWS-SCHEMA-012")
    with pytest.raises(ValueError):
        validate(news_item(status="reserved"))
    with pytest.raises(ValueError):
        validate(news_item(status="consumed", consumed_by="note-1"))
    with pytest.raises(ValueError):
        validate(news_item(status="pending", reserved_by="run-1", reserved_at="2026-08-26T12:00:00Z"))


@pytest.mark.trace("NEWS-ID-001")
@pytest.mark.red_expected
def test_canonical_url_casefolds_scheme_host_and_removes_default_port() -> None:
    canonicalize = planned_callable(TARGET, "canonicalize_url", "NEWS-ID-001")
    observed = canonicalize("HTTPS://EXAMPLE.TEST:443/Research")
    assert observed == "https://example.test/Research", trace_message(
        "NEWS-ID-001", f"unexpected canonical URL: {observed}"
    )


@pytest.mark.trace("NEWS-ID-002")
@pytest.mark.red_expected
def test_canonical_url_removes_known_tracking_parameters_only() -> None:
    canonicalize = planned_callable(TARGET, "canonicalize_url", "NEWS-ID-002")
    url = "https://example.test/a?id=7&utm_source=rss&fbclid=fake&utm_medium=social"
    observed = canonicalize(url)
    assert observed == "https://example.test/a?id=7", trace_message(
        "NEWS-ID-002", f"tracking parameters remain: {observed}"
    )


@pytest.mark.trace("NEWS-ID-003")
@pytest.mark.red_expected
def test_canonical_url_sorts_query_without_losing_repeated_values() -> None:
    canonicalize = planned_callable(TARGET, "canonicalize_url", "NEWS-ID-003")
    first = canonicalize("https://example.test/a?b=2&a=3&a=1")
    second = canonicalize("https://example.test/a?a=1&b=2&a=3")
    assert first == second == "https://example.test/a?a=1&a=3&b=2", trace_message(
        "NEWS-ID-003", f"query ordering is unstable: {first!r}, {second!r}"
    )


@pytest.mark.trace("NEWS-ID-004")
@pytest.mark.red_expected
def test_canonical_url_drops_fragment_and_normalizes_empty_path() -> None:
    canonicalize = planned_callable(TARGET, "canonicalize_url", "NEWS-ID-004")
    assert canonicalize("https://example.test#section") == "https://example.test/", trace_message(
        "NEWS-ID-004", "fragment or empty path was not normalized"
    )


@pytest.mark.trace("NEWS-ID-005")
@pytest.mark.red_expected
def test_canonical_url_preserves_semantically_significant_parameters() -> None:
    canonicalize = planned_callable(TARGET, "canonicalize_url", "NEWS-ID-005")
    first = canonicalize("https://example.test/report?id=7&lang=es")
    second = canonicalize("https://example.test/report?id=8&lang=es")
    assert first != second and "id=7" in first and "id=8" in second, trace_message(
        "NEWS-ID-005", "significant query parameter was discarded"
    )


@pytest.mark.trace("NEWS-ID-006")
@pytest.mark.red_expected
def test_canonical_url_handles_idn_and_unicode_path_deterministically() -> None:
    canonicalize = planned_callable(TARGET, "canonicalize_url", "NEWS-ID-006")
    first = canonicalize("https://ejemplo.测试/Investigación/IA")
    second = canonicalize("https://xn--ejemplo-9za.test/Investigacio%CC%81n/IA")
    assert canonicalize(first) == first, trace_message(
        "NEWS-ID-006", "canonical URL is not idempotent"
    )
    assert all(ord(character) < 128 for character in first), trace_message(
        "NEWS-ID-006", f"canonical URL is not ASCII-safe: {first}"
    )
    assert isinstance(second, str) and second, trace_message(
        "NEWS-ID-006", "encoded Unicode URL produced an empty result"
    )


@pytest.mark.trace("NEWS-ID-007")
@pytest.mark.red_expected
def test_canonical_url_rejects_credentials_invalid_and_private_destinations() -> None:
    canonicalize = planned_callable(TARGET, "canonicalize_url", "NEWS-ID-007")
    for invalid in (
        "not a url",
        "https://user:password@example.test/report",
        "http://localhost/report",
        "http://10.0.0.2/report",
        "file:///tmp/report",
    ):
        with pytest.raises(ValueError):
            canonicalize(invalid)


@pytest.mark.trace("NEWS-ID-008")
@pytest.mark.red_expected
def test_stable_news_id_matches_equivalent_event_and_separates_real_differences() -> None:
    stable_id = planned_callable(TARGET, "stable_news_id", "NEWS-ID-008")
    base = news_item(url="https://example.test/a?utm_source=rss&id=7")
    equivalent = news_item(url="https://EXAMPLE.test:443/a?id=7&fbclid=fake")
    later_event = news_item(
        url="https://example.test/a?id=7",
        published_at="2026-08-25T13:30:00Z",
    )
    first = stable_id(base)
    assert first == stable_id(copy.deepcopy(base)) == stable_id(equivalent), trace_message(
        "NEWS-ID-008", "equivalent event produced different IDs"
    )
    assert first != stable_id(later_event), trace_message(
        "NEWS-ID-008", "different dated event collided"
    )
    assert re.fullmatch(r"news-v1-[0-9a-f]{8,64}", first), trace_message(
        "NEWS-ID-008", f"stable ID format is invalid: {first}"
    )
