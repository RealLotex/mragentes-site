from __future__ import annotations

import pytest

from tests.support.contracts import require_python_symbol, trace_message


@pytest.mark.trace("E2E-BLOG-001")
@pytest.mark.red_expected
@pytest.mark.e2e
def test_local_e2e_simulator_exposes_news_to_blog_pipeline() -> None:
    simulator = require_python_symbol(
        "scripts/automation/e2e_simulator.py", "simulate_blog_pipeline", "E2E-BLOG-001"
    )
    result = simulator(mode="local-fakes", reruns=2)
    assert result["notes"] == 1 and result["pushes"] == 1, trace_message(
        "E2E-BLOG-001", f"blog pipeline is not exactly-once: {result}"
    )


@pytest.mark.trace("E2E-SOCIAL-001")
@pytest.mark.red_expected
@pytest.mark.e2e
def test_local_e2e_simulator_separates_daily_and_blog_social() -> None:
    simulator = require_python_symbol(
        "scripts/automation/e2e_simulator.py", "simulate_social_pipeline", "E2E-SOCIAL-001"
    )
    result = simulator(day="wednesday", reruns=2)
    assert result == {"daily_owned": 2, "blog_note": 2, "duplicates": 0}, trace_message(
        "E2E-SOCIAL-001", f"social pipeline result differs: {result}"
    )


@pytest.mark.trace("E2E-FAILURE-001")
@pytest.mark.red_expected
@pytest.mark.e2e
def test_failed_deploy_produces_zero_external_calls() -> None:
    simulator = require_python_symbol(
        "scripts/automation/e2e_simulator.py", "simulate_failed_deploy", "E2E-FAILURE-001"
    )
    result = simulator()
    assert result["meta_calls"] == result["push_calls"] == 0, trace_message(
        "E2E-FAILURE-001", f"failed deploy leaked effects: {result}"
    )


@pytest.mark.trace("SOAK-CONTRACT-001")
@pytest.mark.red_expected
def test_soak_report_contract_requires_fourteen_days() -> None:
    validator = require_python_symbol(
        "scripts/automation/soak_report.py", "validate_soak", "SOAK-CONTRACT-001"
    )
    result = validator([])
    assert result["required_days"] == 14 and result["complete"] is False, trace_message(
        "SOAK-CONTRACT-001", f"soak contract differs: {result}"
    )
