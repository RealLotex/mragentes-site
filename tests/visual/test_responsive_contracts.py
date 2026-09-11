from __future__ import annotations

import pytest

from tests.support.contracts import require_target, trace_message


def _css() -> str:
    return require_target("assets/css/main.css", "UX-RESP-001").read_text(encoding="utf-8")


def _site_js() -> str:
    return require_target("assets/js/site.js", "UX-RESP-001").read_text(encoding="utf-8")


def _home() -> str:
    return require_target("layouts/index.html", "UX-COPY-001").read_text(encoding="utf-8")


@pytest.mark.trace("UX-RESP-001")
@pytest.mark.red_expected
@pytest.mark.visual
def test_navigation_uses_the_same_tablet_breakpoint_as_the_collapsed_layout() -> None:
    css = _css()
    js = _site_js()
    assert "@media (max-width: 61.99rem)" in css, trace_message(
        "UX-RESP-001", "tablet layout must switch before the header starts colliding"
    )
    assert "(min-width: 62rem)" in js, trace_message(
        "UX-RESP-001", "menu state must use the same 62rem breakpoint as the CSS"
    )


@pytest.mark.trace("UX-RESP-002")
@pytest.mark.red_expected
@pytest.mark.visual
def test_mobile_menu_stretches_to_the_viewport_instead_of_its_content_width() -> None:
    css = _css()
    assert "justify-self: stretch" in css, trace_message(
        "UX-RESP-002", "open mobile navigation must be a full-width, scannable menu"
    )


@pytest.mark.trace("UX-RESP-003")
@pytest.mark.red_expected
@pytest.mark.visual
def test_diagnostic_selects_fit_the_mobile_content_column() -> None:
    css = _css()
    readiness_rule = css.split(".readiness-assessment select", 1)[1].split("}", 1)[0]
    assert "width: 100%" in readiness_rule, trace_message(
        "UX-RESP-003", "diagnostic controls must not overflow a 320px viewport"
    )


@pytest.mark.trace("UX-RESP-004")
@pytest.mark.red_expected
@pytest.mark.visual
def test_tool_surfaces_stack_at_the_same_tablet_breakpoint() -> None:
    css = _css()
    assert "@media (max-width: 61.99rem) {\n  .tool-grid," in css, trace_message(
        "UX-RESP-004", "tool surfaces need a tablet breakpoint"
    )
    assert "readiness-assessment { grid-template-columns: minmax(0, 1fr); }" in css, trace_message(
        "UX-RESP-004", "diagnostic columns must stack before tablet content gets cramped"
    )


@pytest.mark.trace("UX-RESP-005")
@pytest.mark.red_expected
@pytest.mark.visual
def test_footer_social_links_keep_a_comfortable_touch_target() -> None:
    css = _css()
    social_rule = css.split(".social a", 1)[1].split("}", 1)[0]
    assert "width: 44px" in social_rule and "height: 44px" in social_rule, trace_message(
        "UX-RESP-005", "footer social links are too small for comfortable touch use"
    )


@pytest.mark.trace("UX-COPY-001")
@pytest.mark.red_expected
@pytest.mark.visual
def test_home_intro_uses_one_consistent_voice() -> None:
    home = _home()
    assert "Marcos Rosich trabaja desde Gálvez" in home, trace_message(
        "UX-COPY-001", "home intro switches awkwardly between first and third person"
    )
    assert "Trabaja Marcos Rosich" not in home, trace_message(
        "UX-COPY-001", "home intro keeps the inverted third-person phrasing"
    )
