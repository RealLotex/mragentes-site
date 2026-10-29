from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.visual.test_home_latest_notes import _build


def _note(tmp_path: Path) -> str:
    return (tmp_path / "public/notas/latest/index.html").read_text(encoding="utf-8")


@pytest.mark.trace("NOTE-LAYOUT-001")
@pytest.mark.red_expected
@pytest.mark.visual
def test_note_opens_with_headline_metadata_assigned_image_and_share_controls(tmp_path: Path) -> None:
    _build(tmp_path, [("latest", "2020-01-02", 'image: "/images/stock/fixture.png"\nimage_alt: "Ilustración conceptual de prueba"')])
    note = _note(tmp_path)
    assert 'class="note-head' in note
    assert 'aria-label="Ruta de navegación"' in note
    assert note.count("<h1>") == 1
    assert "Resumen de latest" in note and "2 de enero de 2020" in note
    assert note.count("data-share-url=") == 1
    assert 'data-share-status aria-live="polite"' in note
    assert 'class="note-figure"' in note
    assert 'alt="Ilustración conceptual de prueba"' in note
    assert "srcset=" in note and "fetchpriority=" in note
    assert note.index("<figcaption>") < note.index("Texto de la nota.")
    for source in re.findall(r'(/note-images/[^\s\"]+\.webp)', note):
        assert (tmp_path / "public" / source.lstrip("/")).is_file()


@pytest.mark.trace("NOTE-LAYOUT-002")
@pytest.mark.red_expected
@pytest.mark.visual
def test_note_preserves_content_toc_and_paths_to_services(tmp_path: Path) -> None:
    body = "Apertura original.\n\n## Cómo funciona\nDetalle uno.\n\n## Qué cambia\nDetalle dos.\n\n## Fuentes\n[Fuente](https://example.com/)."
    _build(tmp_path, [("latest", "2020-01-02", "")], body=body)
    note = _note(tmp_path)
    assert 'class="note-sidebar"' in note
    assert 'href="/servicios/"' in note and 'href="/contacto/"' in note
    assert '<details class="note-contents">' in note
    assert 'href="#cómo-funciona"' in note
    assert "Apertura original." in note and "Detalle uno." in note and "Detalle dos." in note
    assert 'href="https://example.com/"' in note
    assert 'class="note-figure"' not in note
    assert 'src=""' not in note


@pytest.mark.trace("NOTE-LAYOUT-003")
@pytest.mark.red_expected
@pytest.mark.visual
def test_related_notes_have_graphic_cards_and_exclude_current_draft_and_future(tmp_path: Path) -> None:
    image = 'image: "/images/stock/fixture.png"\ntags: ["automatizacion"]'
    _build(tmp_path, [
        ("old", "2020-01-01", image), ("second", "2020-01-02", image),
        ("latest", "2020-01-03", image), ("draft", "2020-01-04", "draft: true"),
        ("future", "2099-01-01", ""),
    ])
    note = _note(tmp_path)
    related = note.split('aria-labelledby="note-related-title"', 1)[1]
    links = re.findall(r'href="(/notas/[^\"]+/)"', related.split("</section>", 1)[0])
    assert links == ["/notas/second/", "/notas/old/"]
    assert 'class="note-related-grid"' in related
    assert "<img " in related


@pytest.mark.trace("NOTE-LAYOUT-004")
@pytest.mark.red_expected
@pytest.mark.visual
def test_notes_credit_marcos_with_portrait_and_person_schema(tmp_path: Path) -> None:
    _build(tmp_path, [("latest", "2020-01-02", "")])
    note = _note(tmp_path)
    byline = note.split('class="note-author"', 1)[1].split("</a>", 1)[0]
    assert "Marcos Rosich" in byline
    assert "<small>MR AGENTES</small>" in byline
    portrait = re.search(r'src="([^"]+)"', byline).group(1)
    assert "/authors/marcos-rosich" in portrait and portrait.endswith(".webp")
    assert (tmp_path / "public" / portrait.lstrip("/")).is_file()
    graph = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', note).group(1))["@graph"]
    article = next(node for node in graph if node["@type"] == "BlogPosting")
    assert article["author"]["@type"] == "Person"
    assert article["author"]["name"] == "Marcos Rosich"
    assert article["author"]["url"].endswith("/nosotros/")
    assert article["publisher"]["@id"].endswith("#mragentes")


@pytest.mark.trace("NOTE-LAYOUT-005")
@pytest.mark.red_expected
@pytest.mark.visual
def test_note_promo_has_one_contact_button_without_duplicate_link(tmp_path: Path) -> None:
    _build(tmp_path, [("latest", "2020-01-02", "")])
    promo = _note(tmp_path).split('class="note-promo"', 1)[1].split("</div>", 1)[0]
    assert re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', promo) == [("/contacto/", "Contactanos")]
    assert 'class="btn"' in promo
