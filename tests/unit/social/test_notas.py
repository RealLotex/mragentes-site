from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from scripts.social import notas


FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "social" / "nota_complete.md"


@pytest.mark.trace("SOCIAL-NOTA-001")
@pytest.mark.baseline_green
def test_slugify_matches_hugo_style_unicode_and_collapses_separators() -> None:
    assert notas._slugify("  La IA bajó: ¿qué cambió?  ") == "la-ia-bajó-qué-cambió"
    assert notas._slugify("A/B + C___D") == "a-b-c-d"
    assert notas._slugify("NIÑEZ y pingüinos") == "niñez-y-pingüinos"


@pytest.mark.trace("SOCIAL-NOTA-002")
@pytest.mark.baseline_green
def test_unquote_only_removes_matching_outer_quotes() -> None:
    assert notas._unquote(' "valor con espacios" ') == "valor con espacios"
    assert notas._unquote("'otro valor'") == "otro valor"
    assert notas._unquote('"incompleto') == '"incompleto'
    assert notas._unquote("") == ""


@pytest.mark.trace("SOCIAL-NOTA-003")
@pytest.mark.baseline_green
def test_parse_front_matter_handles_flat_values_lists_colons_and_plain_markdown() -> None:
    text = (
        "---\n"
        'title: "Título: con dos puntos"\n'
        "tags:\n"
        "  - automatización\n"
        "  - pymes\n"
        "draft: false\n"
        "línea inválida\n"
        "---\n"
        "Cuerpo.\n"
    )
    front, body = notas.parse_front_matter(text)

    assert front == {
        "title": "Título: con dos puntos",
        "tags": ["automatización", "pymes"],
        "draft": "false",
    }
    assert body == "Cuerpo.\n"
    assert notas.parse_front_matter("# Sin front matter\n") == ({}, "# Sin front matter\n")


@pytest.mark.trace("SOCIAL-NOTA-004")
@pytest.mark.baseline_green
def test_loaded_nota_has_stable_identity_url_date_and_tags(tmp_path: Path) -> None:
    target = tmp_path / "2026-08-26-nota.md"
    target.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    nota = notas.load(target)

    assert nota.title == "Automatización útil: datos, criterio y resultados"
    assert nota.slug == "automatización-útil-datos-criterio-y-resultados"
    assert nota.url("https://example.test/") == (
        "https://example.test/notas/automatizaci%C3%B3n-%C3%BAtil-datos-criterio-y-resultados/"
    )
    assert nota.date == dt.date(2026, 8, 26)
    assert nota.date_label == "26.08.2026"
    assert nota.tags == ["automatización", "pymes"]


@pytest.mark.trace("SOCIAL-NOTA-005")
@pytest.mark.baseline_green
def test_main_body_and_markdown_extractors_exclude_sources_and_markup(tmp_path: Path) -> None:
    target = tmp_path / "2026-08-26-nota.md"
    target.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    nota = notas.load(target)

    assert "Documento de ejemplo" not in nota.main_body
    assert len(nota.paragraphs) >= 3
    assert all("http" not in paragraph for paragraph in nota.paragraphs)
    assert nota.lead == nota.description
    assert nota.headings == ["Tres decisiones antes de empezar", "Qué conviene medir"]
    assert len(nota.quotes) == 2
    assert len(nota.numbers) == 1
    assert nota.numbers[0][0] == "42%"
    assert len(nota.bullets) == 3
    assert all("[" not in bullet and "http" not in bullet for bullet in nota.bullets)


@pytest.mark.trace("SOCIAL-NOTA-006")
@pytest.mark.red_expected
def test_extractors_deduplicate_quotes_and_filter_short_or_source_bullets(tmp_path: Path) -> None:
    nota = notas.Nota(
        path=tmp_path / "note.md",
        title="Prueba",
        date=dt.date(2026, 8, 26),
        body=(
            "> Una cita suficientemente extensa para ser útil dentro de una pieza social completa.\n"
            "> Una cita suficientemente extensa para ser útil dentro de una pieza social completa.\n\n"
            "- corto\n"
            "- [Un punto suficientemente descriptivo](https://example.invalid/detail) para usar en carrusel.\n"
            "- Fuente https://example.invalid/source\n"
        ),
    )

    assert nota.quotes == [
        "Una cita suficientemente extensa para ser útil dentro de una pieza social completa."
    ]
    assert nota.bullets == ["Un punto suficientemente descriptivo para usar en carrusel."]


@pytest.mark.trace("SOCIAL-NOTA-007")
@pytest.mark.baseline_green
def test_parse_date_prefers_front_matter_then_filename() -> None:
    path = Path("2026-08-25-file.md")
    assert notas._parse_date("2026-08-26T12:00:00-03:00", path) == dt.date(2026, 8, 26)
    assert notas._parse_date("invalid", path) == dt.date(2026, 8, 25)


@pytest.mark.trace("SOCIAL-NOTA-008")
@pytest.mark.baseline_green
def test_all_latest_and_find_use_deterministic_order_and_supported_identities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = tmp_path / "notas"
    content.mkdir()
    (content / "_index.md").write_text("---\ntitle: Index\n---\n", encoding="utf-8")
    (content / "2026-08-25-primera.md").write_text(
        '---\ntitle: "Primera nota"\ndate: "2026-08-25"\n---\nCuerpo largo de la primera nota.\n',
        encoding="utf-8",
    )
    second = content / "2026-08-26-segunda-nota.md"
    second.write_text(
        '---\ntitle: "Segunda nota útil"\ndate: "2026-08-26"\n---\nCuerpo largo de la segunda nota.\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(notas, "CONTENT_NOTAS", content)

    loaded = notas.all_notas()
    assert [item.title for item in loaded] == ["Primera nota", "Segunda nota útil"]
    assert notas.latest().path == second
    assert notas.find("segunda-nota-útil").path == second
    assert notas.find("2026-08-26-segunda-nota.md").path == second
    assert notas.find("segunda nota").path == second
    assert notas.find("no existe") is None


@pytest.mark.trace("SOCIAL-NOTA-009")
@pytest.mark.baseline_green
def test_photo_resolves_only_an_existing_static_asset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    static = tmp_path / "static" / "images" / "stock"
    static.mkdir(parents=True)
    image = static / "cover.jpg"
    image.write_bytes(b"fake-image")
    monkeypatch.setattr(notas, "BASE_DIR", tmp_path)

    valid = notas.Nota(
        path=tmp_path / "note.md",
        title="Prueba",
        date=dt.date(2026, 8, 26),
        image="/images/stock/cover.jpg",
    )
    missing = notas.Nota(
        path=tmp_path / "note.md",
        title="Prueba",
        date=dt.date(2026, 8, 26),
        image="/images/stock/missing.jpg",
    )
    assert valid.photo == image
    assert missing.photo is None


@pytest.mark.trace("SOCIAL-NOTA-010")
@pytest.mark.red_expected
def test_photo_rejects_traversal_outside_static(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    (repo / "static").mkdir(parents=True)
    escaped = tmp_path / "outside.jpg"
    escaped.write_bytes(b"not-a-site-asset")
    monkeypatch.setattr(notas, "BASE_DIR", repo)
    nota = notas.Nota(
        path=tmp_path / "note.md",
        title="Prueba",
        date=dt.date(2026, 8, 26),
        image="../../outside.jpg",
    )

    assert nota.photo is None


@pytest.mark.trace("SOCIAL-NOTA-011")
@pytest.mark.red_expected
def test_explicit_hugo_slug_wins_over_title_and_portable_filename(tmp_path: Path) -> None:
    target = tmp_path / "2026-08-27-portable-a1b2c3d4.md"
    target.write_text(
        "---\n"
        'title: "Un título editorial que puede cambiar"\n'
        "date: 2026-08-27\n"
        'slug: "automatización-canónica"\n'
        "---\n\nTexto.\n",
        encoding="utf-8",
    )
    nota = notas.load(target)
    assert nota.slug == "automatización-canónica"
    assert nota.url() == "https://mragentes.com.ar/notas/automatizaci%C3%B3n-can%C3%B3nica/"

    target.write_text(
        "---\n"
        'title: "Seguro"\n'
        "date: 2026-08-27\n"
        'slug: "../escape"\n'
        "---\n\nTexto.\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="slug"):
        notas.load(target)
