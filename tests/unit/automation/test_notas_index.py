from __future__ import annotations

import pytest

from tests.support.contracts import trace_message
from tests.support.planned import planned_callable


TARGET = "scripts/generate_notas_index.py"


@pytest.mark.trace("NOTAS-INDEX-001")
@pytest.mark.red_expected
def test_explicit_hugo_slug_is_canonical_and_independent_from_portable_filename() -> None:
    canonical = planned_callable(TARGET, "canonical_note_url", "NOTAS-INDEX-001")
    slug = "modelo-crítico-diseña-soluciones"
    observed = canonical(
        {"slug": slug},
        "2026-08-23-modelo-corto-a1b2c3d4.md",
        "Un título que puede cambiar",
    )
    assert observed == f"/notas/{slug}/", trace_message(
        "NOTAS-INDEX-001", f"explicit Hugo slug was changed: {observed}"
    )


@pytest.mark.trace("NOTAS-INDEX-002")
@pytest.mark.red_expected
def test_default_hugo_url_uses_materialized_filename_stem_not_rebuilt_title() -> None:
    canonical = planned_callable(TARGET, "canonical_note_url", "NOTAS-INDEX-002")
    observed = canonical({}, "2026-08-26-modelo-portable.md", "Título editorial distinto")
    assert observed == "/notas/2026-08-26-modelo-portable/", trace_message(
        "NOTAS-INDEX-002", f"default URL diverges from Hugo filename behavior: {observed}"
    )


@pytest.mark.trace("NOTAS-INDEX-003")
@pytest.mark.red_expected
def test_explicit_slug_rejects_path_traversal_protocol_and_nested_path() -> None:
    canonical = planned_callable(TARGET, "canonical_note_url", "NOTAS-INDEX-003")
    for slug in ("../escape", "https://evil.test/x", "nested/path", ""):
        with pytest.raises(ValueError):
            canonical({"slug": slug}, "safe.md", "Safe")
