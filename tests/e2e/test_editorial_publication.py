from __future__ import annotations

import pytest

from tests.support.contracts import require_python_symbol, trace_message


@pytest.mark.trace("EDITORIAL-E2E-001")
@pytest.mark.red_expected
@pytest.mark.e2e
def test_daily_pipeline_is_exactly_once_across_every_external_destination() -> None:
    simulate = require_python_symbol(
        "scripts/automation/e2e_simulator.py",
        "simulate_editorial_pipeline",
        "EDITORIAL-E2E-001",
    )
    result = simulate(reruns=2, deploy_healthy=True)
    assert result == {
        "notes": 1,
        "facebook": 1,
        "instagram": 1,
        "pushes": 1,
        "duplicates": 0,
    }, trace_message("EDITORIAL-E2E-001", f"pipeline is not exactly once: {result}")


@pytest.mark.trace("EDITORIAL-E2E-002")
@pytest.mark.red_expected
@pytest.mark.e2e
def test_unhealthy_deploy_blocks_every_external_destination() -> None:
    simulate = require_python_symbol(
        "scripts/automation/e2e_simulator.py",
        "simulate_editorial_pipeline",
        "EDITORIAL-E2E-002",
    )
    result = simulate(reruns=2, deploy_healthy=False)
    assert result["notes"] == 1
    assert result["facebook"] == result["instagram"] == result["pushes"] == 0
