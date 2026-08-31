from __future__ import annotations

import pytest

from scripts.automation.editorial_style import (
    inspect_note,
    validate_academic_note,
    validate_formal_text,
)


def _note(*, body: str = "") -> str:
    analysis = body or (
        "## Evidencia verificable\n\n"
        "El análisis documenta datos, fechas y entidades mediante fuentes públicas. " * 120
        + "\n\n## Implicancias operativas\n\n"
        + "La evidencia permite comparar riesgos, arquitectura y gobernanza en la operación. " * 120
        + "\n\n## Conclusión\n\n"
        + "La conclusión sintetiza el impacto de los datos y las decisiones de diseño. " * 120
        + "\n\n## Fuentes\n\n"
        + "- https://example.test/a\n- https://example.test/b\n- https://example.test/c\n"
    )
    return "---\ntitle: Prueba\n---\n\n" + analysis


@pytest.mark.trace("EDITORIAL-STYLE-001")
@pytest.mark.red_expected
def test_academic_note_requires_sourced_analytical_structure() -> None:
    report = validate_academic_note(_note())
    assert report["words"] >= 1_000
    assert report["sections"] >= 4
    assert report["sources"] >= 3
    assert report["analytic_markers"] >= 2


@pytest.mark.trace("EDITORIAL-STYLE-002")
@pytest.mark.red_expected
@pytest.mark.parametrize(
    "text",
    (
        "Esta semana analizamos una herramienta.",
        "La semana deja una señal relevante.",
        "No vendemos humo.",
        "Vos podés automatizar este paso.",
        "Definí el alcance antes de publicar.",
    ),
)
def test_formal_text_rejects_weekly_formulas_and_colloquial_register(text: str) -> None:
    with pytest.raises(ValueError):
        validate_formal_text(text)


@pytest.mark.trace("EDITORIAL-STYLE-003")
@pytest.mark.red_expected
def test_academic_note_fails_closed_when_the_structure_is_too_short() -> None:
    with pytest.raises(ValueError, match="1000 words"):
        validate_academic_note(
            _note(
                body="## Evidencia\n\nTexto técnico.\n\n## Conclusión\n\nTexto.\n\n"
                "- https://example.test/a\n- https://example.test/b\n- https://example.test/c"
            )
        )


@pytest.mark.trace("EDITORIAL-STYLE-004")
@pytest.mark.red_expected
def test_inspection_ignores_front_matter_when_counting_article_words() -> None:
    report = inspect_note("---\ntitle: " + ("x " * 1_000) + "\n---\n\n## Análisis\n\nDato.")
    assert report["words"] < 10
