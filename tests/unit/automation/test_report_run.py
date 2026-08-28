from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tests.fixtures.factories import run_report
from tests.support.contracts import trace_message
from tests.support.planned import planned_callable, planned_signature


TARGET = "scripts/automation/report_run.py"


@pytest.mark.trace("REPORT-RUN-001")
@pytest.mark.red_expected
def test_report_module_exposes_every_planned_function() -> None:
    signatures = {
        "new_report": ("run_id", "kind", "started_at"),
        "add_check": ("report", "name", "status"),
        "add_effect": ("report", "kind", "status"),
        "redact": ("value",),
        "finalize": ("report", "status", "finished_at"),
        "write_report": ("report", "output_path"),
    }
    for symbol, parameters in signatures.items():
        planned_signature(TARGET, symbol, parameters, "REPORT-RUN-001")


@pytest.mark.trace("REPORT-RUN-002")
@pytest.mark.red_expected
def test_new_report_has_closed_versioned_running_schema() -> None:
    new_report = planned_callable(TARGET, "new_report", "REPORT-RUN-002")
    report = new_report("news-2026-08-26", "news", "2026-08-26T12:00:00Z")
    assert report == run_report(), trace_message(
        "REPORT-RUN-002", f"unexpected initial report: {report}"
    )


@pytest.mark.trace("REPORT-RUN-003")
@pytest.mark.red_expected
def test_add_check_records_name_status_duration_and_sanitized_detail() -> None:
    add_check = planned_callable(TARGET, "add_check", "REPORT-RUN-003")
    report = run_report()
    returned = add_check(
        report,
        name="schema",
        status="passed",
        duration_ms=17,
        detail="12 items valid",
    )
    assert returned is report, trace_message("REPORT-RUN-003", "add_check replaced report object")
    assert report["checks"] == [
        {"name": "schema", "status": "passed", "duration_ms": 17, "detail": "12 items valid"}
    ], trace_message("REPORT-RUN-003", f"unexpected check record: {report['checks']}")


@pytest.mark.trace("REPORT-RUN-004")
@pytest.mark.red_expected
def test_add_check_rejects_unknown_status_duplicate_name_negative_duration_and_finalized_report() -> None:
    add_check = planned_callable(TARGET, "add_check", "REPORT-RUN-004")
    report = run_report()
    add_check(report, name="schema", status="passed", duration_ms=1)
    for kwargs in (
        {"name": "schema", "status": "passed", "duration_ms": 1},
        {"name": "other", "status": "mystery", "duration_ms": 1},
        {"name": "other", "status": "passed", "duration_ms": -1},
    ):
        with pytest.raises(ValueError):
            add_check(report, **kwargs)
    finalized = run_report(status="success")
    with pytest.raises(ValueError):
        add_check(finalized, name="late", status="passed")


@pytest.mark.trace("REPORT-RUN-005")
@pytest.mark.red_expected
def test_add_effect_records_external_scope_ids_as_hashes_not_raw_payloads() -> None:
    add_effect = planned_callable(TARGET, "add_effect", "REPORT-RUN-005")
    report = run_report()
    result = add_effect(
        report,
        kind="git_commit",
        status="confirmed",
        target="automation/news/run-1",
        external_id="a" * 40,
        detail={"changed_paths": ["data/news-queue.json"]},
    )
    assert result is report, trace_message("REPORT-RUN-005", "add_effect replaced report")
    effect = report["effects"][0]
    assert effect["external_id"] == "a" * 40, trace_message(
        "REPORT-RUN-005", "safe Git object id was not retained"
    )
    assert effect["detail"] == {"changed_paths": ["data/news-queue.json"]}, trace_message(
        "REPORT-RUN-005", "safe effect detail changed"
    )


@pytest.mark.trace("REPORT-RUN-006")
@pytest.mark.red_expected
def test_recursive_redact_covers_tokens_passwords_headers_and_private_keys_without_mutation() -> None:
    redact = planned_callable(TARGET, "redact", "REPORT-RUN-006")
    synthetic = {
        "access_token": "EAA" + "x" * 45,
        "nested": [
            {"authorization": "Bearer synthetic-token-value"},
            {"password": "synthetic-password"},
            "-----BEGIN PRIVATE KEY----- synthetic -----END PRIVATE KEY-----",
        ],
        "safe": "kept",
    }
    original = copy.deepcopy(synthetic)
    result = redact(synthetic)
    serialized = json.dumps(result, ensure_ascii=False).lower()
    assert "synthetic-token-value" not in serialized and "synthetic-password" not in serialized, trace_message(
        "REPORT-RUN-006", "recursive redaction leaked a secret"
    )
    assert result["safe"] == "kept", trace_message("REPORT-RUN-006", "safe value was removed")
    assert synthetic == original, trace_message("REPORT-RUN-006", "redact mutated input")


@pytest.mark.trace("REPORT-RUN-007")
@pytest.mark.red_expected
def test_redact_removes_url_userinfo_query_and_full_push_endpoint() -> None:
    redact = planned_callable(TARGET, "redact", "REPORT-RUN-007")
    value = {
        "url": "https://user:pass@example.test/path?token=secret&id=7",
        "endpoint": "https://push.example.test/subscriptions/very-long-private-endpoint",
    }
    result = redact(value)
    serialized = json.dumps(result, ensure_ascii=False)
    assert "user:pass" not in serialized and "token=secret" not in serialized, trace_message(
        "REPORT-RUN-007", "URL credentials/query leaked"
    )
    assert "very-long-private-endpoint" not in serialized, trace_message(
        "REPORT-RUN-007", "full subscriber endpoint leaked"
    )
    assert "example.test" in serialized, trace_message(
        "REPORT-RUN-007", "redaction removed all useful host context"
    )


@pytest.mark.trace("REPORT-RUN-008")
@pytest.mark.red_expected
def test_finalize_derives_success_only_when_required_checks_pass_and_effects_confirm() -> None:
    add_check = planned_callable(TARGET, "add_check", "REPORT-RUN-008")
    finalize = planned_callable(TARGET, "finalize", "REPORT-RUN-008")
    report = run_report()
    add_check(report, name="schema", status="passed", required=True)
    result = finalize(report, status="success", finished_at="2026-08-26T12:01:00Z")
    assert result["status"] == "success" and result["finished_at"] == "2026-08-26T12:01:00Z", trace_message(
        "REPORT-RUN-008", "successful report did not finalize"
    )
    failed = run_report()
    add_check(failed, name="schema", status="failed", required=True)
    with pytest.raises(ValueError):
        finalize(failed, status="success", finished_at="2026-08-26T12:01:00Z")


@pytest.mark.trace("REPORT-RUN-009")
@pytest.mark.red_expected
def test_finalize_rejects_illegal_status_transition_missing_time_and_second_finalize() -> None:
    finalize = planned_callable(TARGET, "finalize", "REPORT-RUN-009")
    for status in ("running", "mystery", ""):
        with pytest.raises(ValueError):
            finalize(run_report(), status=status, finished_at="2026-08-26T12:01:00Z")
    with pytest.raises(ValueError):
        finalize(run_report(), status="failed", finished_at=None)
    done = finalize(run_report(), status="skipped", finished_at="2026-08-26T12:01:00Z")
    with pytest.raises(ValueError):
        finalize(done, status="success", finished_at="2026-08-26T12:02:00Z")


@pytest.mark.trace("REPORT-RUN-010")
@pytest.mark.red_expected
def test_write_report_is_atomic_refuses_overwrite_and_leaves_no_temp(tmp_path: Path) -> None:
    write_report = planned_callable(TARGET, "write_report", "REPORT-RUN-010")
    report = {**run_report(status="success"), "finished_at": "2026-08-26T12:01:00Z"}
    output = tmp_path / "reports" / "news-2026-08-26.json"
    returned = write_report(report, output)
    assert Path(returned) == output and json.loads(output.read_text(encoding="utf-8")) == report, trace_message(
        "REPORT-RUN-010", "written report differs"
    )
    with pytest.raises(FileExistsError):
        write_report(report, output)
    assert not list(output.parent.glob("*.tmp")), trace_message(
        "REPORT-RUN-010", "report writer left temp file"
    )


@pytest.mark.trace("REPORT-RUN-011")
@pytest.mark.red_expected
def test_report_never_contains_full_captions_subscriber_endpoints_or_secrets(tmp_path: Path) -> None:
    add_effect = planned_callable(TARGET, "add_effect", "REPORT-RUN-011")
    write_report = planned_callable(TARGET, "write_report", "REPORT-RUN-011")
    caption = "Este es el caption completo y no debe entrar al reporte"
    endpoint = "https://push.example.test/private/subscriber/endpoint"
    report = run_report()
    add_effect(
        report,
        kind="social",
        status="partial",
        detail={"caption": caption, "subscriber_endpoint": endpoint, "access_token": "synthetic"},
    )
    report.update(status="partial", finished_at="2026-08-26T12:01:00Z")
    output = tmp_path / "report.json"
    write_report(report, output)
    text = output.read_text(encoding="utf-8")
    assert caption not in text and endpoint not in text and "synthetic" not in text, trace_message(
        "REPORT-RUN-011", "report persisted prohibited content"
    )


@pytest.mark.trace("REPORT-RUN-012")
@pytest.mark.red_expected
def test_report_serialization_is_deterministic_utf8_newline_and_schema_closed(tmp_path: Path) -> None:
    write_report = planned_callable(TARGET, "write_report", "REPORT-RUN-012")
    first_report = {**run_report(status="skipped"), "finished_at": "2026-08-26T12:01:00Z", "summary": {"razón": "sin noticias"}}
    second_report = {key: first_report[key] for key in reversed(first_report)}
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    write_report(first_report, first)
    write_report(second_report, second)
    assert first.read_bytes() == second.read_bytes(), trace_message(
        "REPORT-RUN-012", "report bytes depend on mapping order"
    )
    assert first.read_bytes().endswith(b"\n"), trace_message(
        "REPORT-RUN-012", "report lacks final newline"
    )
