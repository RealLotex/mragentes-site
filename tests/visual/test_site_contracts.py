from __future__ import annotations

import json

import pytest

from tests.support.contracts import require_target, trace_message


@pytest.mark.trace("VIS-SITE-001")
@pytest.mark.red_expected
@pytest.mark.visual
def test_site_visual_matrix_covers_pages_and_viewports() -> None:
    manifest = json.loads(
        require_target("tests/visual/visual-matrix.json", "VIS-SITE-001").read_text(encoding="utf-8")
    )
    pairs = {(case["page"], case["viewport"]) for case in manifest["site"]}
    expected = {(page, viewport) for page in ("home", "notas", "nota", "colophon") for viewport in ("mobile", "desktop")}
    assert expected <= pairs, trace_message("VIS-SITE-001", f"missing visual cases: {expected - pairs}")


@pytest.mark.trace("VIS-PUSH-001")
@pytest.mark.red_expected
@pytest.mark.visual
def test_push_visual_matrix_covers_all_feedback_states() -> None:
    manifest = json.loads(
        require_target("tests/visual/visual-matrix.json", "VIS-PUSH-001").read_text(encoding="utf-8")
    )
    states = set(manifest["push_states"])
    expected = {"unsupported", "ios-install", "off", "requesting", "on", "welcome-confirmed", "error"}
    assert expected <= states, trace_message("VIS-PUSH-001", f"missing push states: {expected - states}")


@pytest.mark.trace("A11Y-001")
@pytest.mark.red_expected
@pytest.mark.visual
def test_accessibility_runner_is_part_of_visual_contract() -> None:
    path = require_target("scripts/test/run_accessibility.mjs", "A11Y-001")
    source = path.read_text(encoding="utf-8")
    for term in ("axe", "aria-live", "keyboard", "reduced-motion"):
        assert term in source, trace_message("A11Y-001", f"accessibility runner lacks: {term}")
