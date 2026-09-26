from __future__ import annotations

import pytest

from scripts.automation.editorial_style import (
    inspect_note,
    validate_academic_note,
    validate_formal_text,
)


def _note(*, body: str = "") -> str:
    analysis = body or (
        "OpenAI informó el 25 de septiembre de 2026 un incidente concreto "
        "en un entorno de pruebas. "
        "[Informe](https://example.test/a). "
        * 24
        + "\n\n## El acceso por DNS\n\n"
        + "El agente consultó un servicio externo y el monitor generó una alerta en 15 minutos. "
        * 18
        + "\n\n## La respuesta\n\n"
        + "El equipo detuvo la ejecución dos horas y media después del acceso. " * 12
    )
    return "---\ntitle: Prueba\n---\n\n" + analysis


@pytest.mark.trace("EDITORIAL-STYLE-001")
@pytest.mark.red_expected
def test_academic_note_requires_sourced_analytical_structure() -> None:
    report = validate_academic_note(_note())
    assert report["words"] >= 350
    assert report["sections"] == 2
    assert report["sources"] >= 1
    assert report["faq_questions"] == 0


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
    with pytest.raises(ValueError, match="350 words"):
        validate_academic_note(
            _note(
                body="## Evidencia\n\nTexto técnico.\n\n## Respuesta\n\nTexto.\n\n"
                "- https://example.test/a\n- https://example.test/b\n- https://example.test/c"
            )
        )


@pytest.mark.trace("EDITORIAL-STYLE-004")
@pytest.mark.red_expected
def test_inspection_ignores_front_matter_when_counting_article_words() -> None:
    report = inspect_note("---\ntitle: " + ("x " * 1_000) + "\n---\n\n## Análisis\n\nDato.")
    assert report["words"] < 10


@pytest.mark.trace("EDITORIAL-NEWS-001")
@pytest.mark.red_expected
def test_concise_specific_news_passes_without_faq_or_four_sections() -> None:
    body = (
        "OpenAI informó el 25 de septiembre de 2026 que un agente usó DNS para consultar "
        "un servicio externo. [Informe](https://alignment.openai.com/report/). "
        "La alerta llegó en 15 minutos y la ejecución se detuvo dos horas y media después. "
    ) * 12
    report = validate_academic_note("## El incidente\n\n" + body + "\n\n## La respuesta\n\n" + body)
    assert report["words"] >= 350
    assert report["sections"] == 2
    assert report["faq_questions"] == 0


@pytest.mark.trace("EDITORIAL-NEWS-002")
@pytest.mark.red_expected
@pytest.mark.parametrize(
    "phrase",
    (
        "En este artículo exploraremos",
        "marca un momento crucial",
        "refleja el panorama cambiante",
        "los expertos sostienen",
        "en conclusión",
    ),
)
def test_news_style_rejects_boilerplate(phrase: str) -> None:
    with pytest.raises(ValueError):
        validate_formal_text(phrase)
