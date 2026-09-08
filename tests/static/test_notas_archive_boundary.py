from __future__ import annotations

import pytest

from tests.support.contracts import require_target, trace_message


@pytest.mark.trace("NOTAS-ARCHIVE-001")
@pytest.mark.red_expected
def test_notes_index_contains_only_discovery_and_note_archive_content() -> None:
    """Downloads, tools and reading programs belong outside the notes archive."""

    source = require_target("layouts/notas/list.html", "NOTAS-ARCHIVE-001").read_text(
        encoding="utf-8"
    )
    forbidden = ("learning_routes", "checklist-automatizacion.pdf", "calculadora-impacto")
    assert not any(item in source for item in forbidden), trace_message(
        "NOTAS-ARCHIVE-001", "the notes archive mixes editorial notes with resources"
    )


@pytest.mark.trace("TOOLS-SECTION-001")
@pytest.mark.red_expected
def test_tools_have_a_dedicated_entrypoint_and_navigation_link() -> None:
    """Practical resources need their own clear, non-editorial destination."""

    page = require_target("content/herramientas.md", "TOOLS-SECTION-001").read_text(
        encoding="utf-8"
    )
    layout = require_target("layouts/herramientas/single.html", "TOOLS-SECTION-001").read_text(
        encoding="utf-8"
    )
    config = require_target("hugo.toml", "TOOLS-SECTION-001").read_text(encoding="utf-8")
    assert "Herramientas" in page
    assert "checklist-automatizacion.pdf" in layout
    assert "calculadora-impacto" in layout
    assert 'url = "/herramientas/"' in config
