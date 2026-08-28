from __future__ import annotations

import copy

import pytest

from tests.support.contracts import trace_message
from tests.support.planned import planned_callable


TARGET = "scripts/automation/social_guard.py"
PLATFORMS = ("facebook", "instagram")


def _classify(records: list[dict[str, object]], trace_id: str, **kwargs: object):
    classify = planned_callable(TARGET, "classify_completion", trace_id)
    result = classify(PLATFORMS, copy.deepcopy(records), **kwargs)
    assert isinstance(result, dict), trace_message(trace_id, "completion must be a mapping")
    return result


@pytest.mark.trace("SOCIAL-RECOVER-001")
@pytest.mark.red_expected
def test_no_platform_records_classifies_none_complete() -> None:
    result = _classify([], "SOCIAL-RECOVER-001")
    assert result == {
        "status": "none",
        "completed": [],
        "missing": ["facebook", "instagram"],
        "uncertain": [],
    }, trace_message("SOCIAL-RECOVER-001", f"unexpected empty completion: {result}")


@pytest.mark.trace("SOCIAL-RECOVER-002")
@pytest.mark.red_expected
def test_facebook_success_only_classifies_instagram_missing() -> None:
    records = [{"platform": "facebook", "status": "complete", "remote_id": "fb-1"}]
    result = _classify(records, "SOCIAL-RECOVER-002")
    assert result["status"] == "partial" and result["missing"] == ["instagram"], trace_message(
        "SOCIAL-RECOVER-002", f"Facebook partial state is wrong: {result}"
    )


@pytest.mark.trace("SOCIAL-RECOVER-003")
@pytest.mark.red_expected
def test_instagram_success_only_classifies_facebook_missing() -> None:
    records = [{"platform": "instagram", "status": "complete", "remote_id": "ig-1"}]
    result = _classify(records, "SOCIAL-RECOVER-003")
    assert result["status"] == "partial" and result["missing"] == ["facebook"], trace_message(
        "SOCIAL-RECOVER-003", f"Instagram partial state is wrong: {result}"
    )


@pytest.mark.trace("SOCIAL-RECOVER-004")
@pytest.mark.red_expected
def test_both_remote_ids_classify_complete_regardless_of_record_order() -> None:
    records = [
        {"platform": "facebook", "status": "complete", "remote_id": "fb-1"},
        {"platform": "instagram", "status": "complete", "remote_id": "ig-1"},
    ]
    first = _classify(records, "SOCIAL-RECOVER-004")
    second = _classify(list(reversed(records)), "SOCIAL-RECOVER-004")
    assert first == second and first["status"] == "complete", trace_message(
        "SOCIAL-RECOVER-004", "complete state is unstable"
    )


@pytest.mark.trace("SOCIAL-RECOVER-005")
@pytest.mark.red_expected
def test_explicit_pre_remote_failure_remains_safe_to_retry() -> None:
    records = [
        {"platform": "facebook", "status": "failed", "phase": "before_remote", "error_class": "auth"},
        {"platform": "instagram", "status": "failed", "phase": "before_remote", "error_class": "rate_limit"},
    ]
    result = _classify(records, "SOCIAL-RECOVER-005")
    assert result["status"] == "none" and result["missing"] == ["facebook", "instagram"], trace_message(
        "SOCIAL-RECOVER-005", "pre-remote failures were treated as completed"
    )


@pytest.mark.trace("SOCIAL-RECOVER-006")
@pytest.mark.red_expected
def test_timeout_after_remote_create_is_uncertain_not_missing() -> None:
    records = [
        {
            "platform": "instagram",
            "status": "failed",
            "phase": "after_remote_create",
            "error_class": "timeout",
            "creation_id": "container-1",
        }
    ]
    result = _classify(records, "SOCIAL-RECOVER-006")
    assert result["status"] == "uncertain" and result["uncertain"] == ["instagram"], trace_message(
        "SOCIAL-RECOVER-006", "post-create timeout would allow a duplicate"
    )


@pytest.mark.trace("SOCIAL-RECOVER-007")
@pytest.mark.red_expected
def test_conflicting_remote_ids_for_same_platform_require_review() -> None:
    records = [
        {"platform": "facebook", "status": "complete", "remote_id": "fb-1"},
        {"platform": "facebook", "status": "complete", "remote_id": "fb-2"},
    ]
    result = _classify(records, "SOCIAL-RECOVER-007")
    assert result["status"] == "needs_review" and result["conflicts"]["facebook"] == ["fb-1", "fb-2"], trace_message(
        "SOCIAL-RECOVER-007", "remote ID conflict was hidden"
    )


@pytest.mark.trace("SOCIAL-RECOVER-008")
@pytest.mark.red_expected
def test_unrelated_run_kind_or_dedupe_records_do_not_complete_current_run() -> None:
    records = [
        {"platform": "facebook", "status": "complete", "remote_id": "fb-old", "dedupe_key": "blog_note:other"},
        {"platform": "instagram", "status": "complete", "remote_id": "ig-old", "dedupe_key": "blog_note:other"},
    ]
    result = _classify(records, "SOCIAL-RECOVER-008", dedupe_key="daily_owned:today")
    assert result["status"] == "none", trace_message(
        "SOCIAL-RECOVER-008", "unrelated records satisfied current run"
    )


@pytest.mark.trace("SOCIAL-RECOVER-009")
@pytest.mark.red_expected
def test_duplicate_identical_checkpoints_are_idempotently_collapsed() -> None:
    record = {"platform": "facebook", "status": "complete", "remote_id": "fb-1"}
    result = _classify([record, copy.deepcopy(record)], "SOCIAL-RECOVER-009")
    assert result["completed"] == ["facebook"] and result["status"] == "partial", trace_message(
        "SOCIAL-RECOVER-009", "identical checkpoints became a conflict"
    )


@pytest.mark.trace("SOCIAL-RECOVER-010")
@pytest.mark.red_expected
def test_unknown_platform_status_or_record_shape_fails_closed() -> None:
    classify = planned_callable(TARGET, "classify_completion", "SOCIAL-RECOVER-010")
    invalid_records = (
        [{"platform": "tiktok", "status": "complete", "remote_id": "x"}],
        [{"platform": "facebook", "status": "mystery"}],
        [{"status": "complete", "remote_id": "x"}],
    )
    for records in invalid_records:
        with pytest.raises(ValueError):
            classify(PLATFORMS, records)


@pytest.mark.trace("SOCIAL-RECOVER-011")
@pytest.mark.red_expected
def test_recovery_plan_for_none_publishes_each_missing_platform_once() -> None:
    recovery = planned_callable(TARGET, "recovery_plan", "SOCIAL-RECOVER-011")
    completion = _classify([], "SOCIAL-RECOVER-011")
    plan = recovery(completion, remote_matches={})
    assert plan == {
        "status": "retry",
        "publish": ["facebook", "instagram"],
        "checkpoint": [],
        "skip": [],
        "force": False,
    }, trace_message("SOCIAL-RECOVER-011", f"unexpected empty recovery plan: {plan}")


@pytest.mark.trace("SOCIAL-RECOVER-012")
@pytest.mark.red_expected
def test_recovery_plan_for_partial_publishes_only_missing_platform() -> None:
    recovery = planned_callable(TARGET, "recovery_plan", "SOCIAL-RECOVER-012")
    completion = _classify(
        [{"platform": "facebook", "status": "complete", "remote_id": "fb-1"}],
        "SOCIAL-RECOVER-012",
    )
    plan = recovery(completion, remote_matches={})
    assert plan["publish"] == ["instagram"] and plan["skip"] == ["facebook"], trace_message(
        "SOCIAL-RECOVER-012", "partial recovery would duplicate completed platform"
    )
    assert plan["force"] is False, trace_message("SOCIAL-RECOVER-012", "partial recovery uses force")


@pytest.mark.trace("SOCIAL-RECOVER-013")
@pytest.mark.red_expected
def test_unique_recent_remote_match_repairs_uncertain_checkpoint_without_publish() -> None:
    recovery = planned_callable(TARGET, "recovery_plan", "SOCIAL-RECOVER-013")
    completion = _classify(
        [{"platform": "instagram", "status": "failed", "phase": "after_remote_create", "error_class": "timeout"}],
        "SOCIAL-RECOVER-013",
    )
    plan = recovery(completion, remote_matches={"instagram": ["ig-recovered"]})
    assert plan["publish"] == [] and plan["checkpoint"] == [
        {"platform": "instagram", "remote_id": "ig-recovered"}
    ], trace_message("SOCIAL-RECOVER-013", "unique remote match was not reconciled")


@pytest.mark.trace("SOCIAL-RECOVER-014")
@pytest.mark.red_expected
def test_zero_or_ambiguous_remote_match_for_uncertain_state_needs_review_never_force() -> None:
    recovery = planned_callable(TARGET, "recovery_plan", "SOCIAL-RECOVER-014")
    completion = _classify(
        [{"platform": "instagram", "status": "failed", "phase": "after_remote_create", "error_class": "timeout"}],
        "SOCIAL-RECOVER-014",
    )
    for matches in ({"instagram": []}, {"instagram": ["ig-1", "ig-2"]}):
        plan = recovery(completion, remote_matches=matches)
        assert plan["status"] == "needs_review", trace_message(
            "SOCIAL-RECOVER-014", "uncertain remote ambiguity did not stop automation"
        )
        assert plan["publish"] == [] and plan["force"] is False, trace_message(
            "SOCIAL-RECOVER-014", "ambiguous recovery could duplicate a post"
        )
