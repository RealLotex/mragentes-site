from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree

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
    preferred_source = 'href="https://www.google.com/preferences/source?q=mragentes.com.ar&amp;hl=es-419&amp;gl=AR"'
    assert note.count(preferred_source) == 1
    assert note.index('class="note-actions"') < note.index(preferred_source) < note.index("data-share-url=")
    assert note.index(preferred_source) < note.index('<figure class="note-figure">')
    assert 21 <= int(re.search(r'data-reaction-base="(\d+)"', note)[1]) <= 29
    assert 'data-note-audio' in note and re.search(r'data-audio-duration>\d{2}:\d{2}<', note)
    assert 'aria-controls="note-player"' in note
    assert 'data-note-player hidden' in note
    assert 'type="range" data-audio-progress' in note
    assert 'data-audio-toggle' in note and 'data-audio-skip="-15"' in note and 'data-audio-skip="15"' in note
    assert set(re.findall(r'data-share-provider="([^"]+)"', note)) == {
        "whatsapp", "x", "instagram", "facebook", "linkedin", "url",
    }
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
    published = (datetime.now(timezone(timedelta(hours=-3))) - timedelta(hours=1)).replace(microsecond=0)
    stamp = published.isoformat()
    _build(tmp_path, [
        ("latest", stamp, "news: true\nautomation_id: blog:2026-11-19:latest"),
        ("essay", stamp, ""),
        ("old", "2020-01-01", "news: true"),
        ("draft", stamp, "news: true\ndraft: true"),
    ])
    note = _note(tmp_path)
    byline = note.split('class="note-author"', 1)[1].split("</a>", 1)[0]
    assert "<span>MR Agentes</span>" in byline
    assert "Marcos Rosich · responsable editorial" in byline
    assert re.search(r'src="/authors/marcos-rosich[^"]*\.webp"', byline)
    assert 'href="https://mragentes.com.ar/nosotros/#criterio-editorial"' in byline
    graph = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', note).group(1))["@graph"]
    article = next(node for node in graph if node["@type"] == "NewsArticle")
    assert article["author"]["@type"] == "Organization"
    assert article["author"]["name"] == "MR Agentes"
    assert article["author"]["url"].endswith("/nosotros/#criterio-editorial")
    assert article["publisher"]["@id"].endswith("#mragentes")
    publisher = next(node for node in graph if node.get("@id") == article["publisher"]["@id"])
    assert publisher["publishingPrinciples"].endswith("/nosotros/#criterio-editorial")
    assert article["datePublished"] == article["dateModified"] == stamp

    public = tmp_path / "public"
    essay = (public / "notas/essay/index.html").read_text(encoding="utf-8")
    essay_byline = essay.split('class="note-author"', 1)[1].split("</a>", 1)[0]
    assert "Marcos Rosich" in essay_byline and "<small>MR AGENTES</small>" in essay_byline
    portrait = re.search(r'src="([^"]+)"', essay_byline).group(1)
    assert "/authors/marcos-rosich" in portrait and portrait.endswith(".webp")
    assert (public / portrait.lstrip("/")).is_file()
    essay_graph = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', essay).group(1))["@graph"]
    essay_schema = next(node for node in essay_graph if node["@type"] == "BlogPosting")
    assert essay_schema["author"]["@type"] == "Person" and essay_schema["author"]["name"] == "Marcos Rosich"
    about = (public / "nosotros/index.html").read_text(encoding="utf-8")
    assert 'id="criterio-editorial"' in about and 'href="/contacto/"' in about
    sitemap = ElementTree.parse(public / "sitemap-news.xml")
    namespaces = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9", "n": "http://www.google.com/schemas/sitemap-news/0.9"}
    entries = sitemap.findall("s:url", namespaces)
    assert len(entries) == 1
    assert entries[0].findtext("s:loc", namespaces=namespaces) == "https://mragentes.com.ar/notas/latest/"
    assert entries[0].findtext("n:news/n:publication_date", namespaces=namespaces) == stamp
    assert entries[0].findtext("n:news/n:title", namespaces=namespaces) == "latest"



@pytest.mark.trace("NOTE-LAYOUT-005")
@pytest.mark.red_expected
@pytest.mark.visual
def test_note_promo_has_one_contact_button_without_duplicate_link(tmp_path: Path) -> None:
    _build(tmp_path, [("latest", "2020-01-02", "")])
    promo = _note(tmp_path).split('class="note-promo"', 1)[1].split("</div>", 1)[0]
    links = re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', promo, flags=re.S)
    assert [(url, re.sub(r"<[^>]+>", "", label).strip()) for url, label in links] == [
        ("/contacto/", "Contactanos")
    ]
    assert 'class="btn"' in promo
