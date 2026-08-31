from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from scripts.social import copy as copywriter
from scripts.social import templates
from scripts.social.templates import Piece
from tests.unit.social._helpers import install_fast_render, make_nota


@pytest.mark.trace("SOCIAL-COPY-001")
@pytest.mark.baseline_green
def test_seed_and_pick_are_stable_and_input_sensitive() -> None:
    first = copywriter.seed_for("nota-uno")
    assert first == copywriter.seed_for("nota-uno")
    assert first != copywriter.seed_for("nota-dos")
    assert copywriter._pick(["a", "b", "c"], first) in {"a", "b", "c"}
    assert copywriter._pick(["a", "b", "c"], first, 1) != copywriter._pick(
        ["a", "b", "c"], first
    )


@pytest.mark.trace("SOCIAL-COPY-002")
@pytest.mark.baseline_green
def test_hashtag_maps_brand_terms_and_normalizes_free_text() -> None:
    assert copywriter.hashtag(" automatización ") == "Automatizacion"
    assert copywriter.hashtag("atencion-al-cliente") == "AtencionAlCliente"
    assert copywriter.hashtag("Ética + IA") == "ÉticaIa"
    assert copywriter.hashtag("---") == ""


@pytest.mark.trace("SOCIAL-COPY-003")
@pytest.mark.baseline_green
def test_hashtags_are_deterministic_unique_limited_and_brand_first(tmp_path: Path) -> None:
    nota = make_nota(
        tmp_path,
        tags=["automatización", "Automatización", "pymes", "datos", "pymes"],
    )

    tags = copywriter.hashtags(nota, seed=123, limit=7)

    assert tags[0] == "#MRAgentes"
    assert len(tags) == 7
    assert len(tags) == len(set(tags))
    assert all(tag.startswith("#") and " " not in tag for tag in tags)
    assert tags == copywriter.hashtags(nota, seed=123, limit=7)


@pytest.mark.trace("SOCIAL-COPY-004")
@pytest.mark.baseline_green
def test_trim_normalizes_whitespace_preserves_short_text_and_ellipsizes_on_word() -> None:
    assert copywriter._trim("  uno\n dos   tres ", 100) == "uno dos tres"
    shortened = copywriter._trim("uno dos tres cuatro cinco", 16)
    assert shortened == "uno dos tres…"
    assert len(shortened) <= 16
    assert copywriter._trim("", 10) == ""


@pytest.mark.trace("SOCIAL-COPY-005")
@pytest.mark.baseline_green
def test_caption_has_distinct_facebook_and_instagram_contracts(tmp_path: Path) -> None:
    nota = make_nota(tmp_path)

    facebook = copywriter.caption(nota, "facebook", "https://site.example/")
    instagram = copywriter.caption(nota, "instagram", "https://site.example/")

    assert facebook == copywriter.caption(nota, "facebook", "https://site.example/")
    assert instagram == copywriter.caption(nota, "instagram", "https://site.example/")
    assert nota.title in facebook and nota.title in instagram
    assert "https://site.example/notas/" in facebook
    assert "enlace" in instagram.lower() and "https://site.example/notas/" not in instagram
    assert "#MRAgentes" in facebook and "#MRAgentes" in instagram
    assert facebook != instagram


@pytest.mark.trace("SOCIAL-COPY-006")
@pytest.mark.baseline_green
def test_cover_story_and_closing_pieces_use_real_nota_metadata(tmp_path: Path) -> None:
    nota = make_nota(tmp_path)

    cover = copywriter.cover_piece(nota, "https://site.example")
    story = copywriter.story_piece(nota, "https://site.example")
    closing = copywriter.closing_piece(nota)

    assert isinstance(cover, Piece)
    assert cover.title == nota.title
    assert cover.meta == "26.08.2026"
    assert cover.url == nota.url("https://site.example")
    assert story.lead and len(story.lead) <= 150
    assert story.footer_right == copywriter.SOCIAL_SHARE_CTA
    assert closing.rows and any("mragentes.com.ar" in value for _, value in closing.rows)
    assert closing.footer_right == copywriter.SOCIAL_SHARE_CTA


@pytest.mark.trace("SOCIAL-COPY-013")
@pytest.mark.baseline_green
def test_every_social_output_includes_the_share_cta(tmp_path: Path) -> None:
    nota = make_nota(tmp_path)

    assert copywriter.SOCIAL_SHARE_CTA in copywriter.caption(nota, "facebook")
    assert copywriter.SOCIAL_SHARE_CTA in copywriter.caption(nota, "instagram")
    assert all(
        piece.footer_right == copywriter.SOCIAL_SHARE_CTA
        for _, piece in copywriter.carousel_for_nota(nota)
    )
    assert Piece().footer_right == copywriter.SOCIAL_SHARE_CTA


@pytest.mark.trace("SOCIAL-COPY-014")
@pytest.mark.baseline_green
def test_method_carousel_and_card_grid_cover_pedagogical_formats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fast_render(monkeypatch)
    methods = copywriter.method_carousel(
        "Cómo empezar con automatización",
        [
            ("Elegir una tarea", "Identifique una tarea que se repite."),
            ("Probar en pequeño", "Revise el resultado con una persona."),
        ],
    )

    assert [key for key, _ in methods] == ["punto", "metodo", "metodo"]
    assert all(piece.footer_right == copywriter.SOCIAL_SHARE_CTA for _, piece in methods)
    assert {"metodo", "tarjetas"} <= set(templates.TEMPLATES)

    for count in (2, 4, 6):
        rendered = templates.render(
            "tarjetas",
            Piece(title="Comparación", items=[("Paso", "Explicación breve")] * count),
            "portrait",
        )
        assert rendered.img.size == (1080, 1350)

    with pytest.raises(ValueError, match="2, 4 o 6"):
        templates.render(
            "tarjetas",
            Piece(title="No permitido", items=[("Paso", "Detalle")] * 3),
            "portrait",
        )


@pytest.mark.trace("SOCIAL-COPY-007")
@pytest.mark.baseline_green
def test_support_pieces_are_grounded_in_numbers_quotes_and_headings(tmp_path: Path) -> None:
    nota = make_nota(
        tmp_path,
        body=(
            "## Primera decisión importante\n\n"
            "## Segunda decisión importante\n\n"
            "## Tercera decisión importante\n\n"
            "La prueba redujo 42% del tiempo operativo, manteniendo una revisión humana completa.\n\n"
            "> Una automatización responsable tiene que poder explicarse y recuperarse siempre.\n"
        ),
    )

    pieces = copywriter.support_pieces(nota, limit=3)
    by_key = {key: piece for key, piece in pieces}

    assert set(by_key) == {"dato", "cita", "lista"}
    assert by_key["dato"].stat == "42%"
    assert "automatización responsable" in by_key["cita"].quote
    assert by_key["lista"].items == nota.headings
    assert all("http" not in str(piece) for _, piece in pieces)


@pytest.mark.trace("SOCIAL-COPY-008")
@pytest.mark.baseline_green
def test_carousel_respects_max_slides_and_always_starts_with_cover(tmp_path: Path) -> None:
    nota = make_nota(tmp_path)
    slides = copywriter.carousel_for_nota(nota, max_slides=4)

    assert 2 <= len(slides) <= 4
    assert slides[0][0] == "nota"
    assert slides[-1][0] == "anuncio"
    assert copywriter.carousel_for_nota(nota, max_slides=2)[0][0] == "nota"
    assert len(copywriter.carousel_for_nota(nota, max_slides=2)) == 2


@pytest.mark.trace("SOCIAL-COPY-009")
@pytest.mark.red_expected
def test_caption_rejects_unknown_network_instead_of_silently_using_facebook(tmp_path: Path) -> None:
    nota = make_nota(tmp_path)

    with pytest.raises(ValueError, match="network|red|facebook|instagram"):
        copywriter.caption(nota, "tiktok")


@pytest.mark.trace("SOCIAL-COPY-010")
@pytest.mark.red_expected
def test_caption_enforces_platform_limits_without_splitting_unicode(tmp_path: Path) -> None:
    nota = make_nota(
        tmp_path,
        title=("Automatización responsable 🧠 " * 150).strip(),
        description=("Criterio humano, evidencia y recuperación. " * 80).strip(),
        body=("Un párrafo operativo suficientemente largo y verificable. " * 100).strip(),
    )

    facebook = copywriter.caption(nota, "facebook")
    instagram = copywriter.caption(nota, "instagram")

    assert len(facebook) <= 63_206
    assert len(instagram) <= 2_200
    assert not instagram.endswith("\ud83e")


@pytest.mark.trace("SOCIAL-COPY-011")
@pytest.mark.red_expected
def test_carousel_rejects_limits_that_cannot_hold_cover_and_closing(tmp_path: Path) -> None:
    nota = make_nota(tmp_path)

    for invalid in (-1, 0, 1):
        with pytest.raises(ValueError, match="max_slides|láminas|slides"):
            copywriter.carousel_for_nota(nota, max_slides=invalid)


@pytest.mark.trace("SOCIAL-COPY-012")
@pytest.mark.red_expected
def test_copy_contract_rejects_unsourced_hardcoded_performance_claims(tmp_path: Path) -> None:
    nota = make_nota(
        tmp_path,
        title="Mejorá 90% tus resultados en un día",
        description="Garantizamos duplicar ventas sin revisar datos ni citar una fuente.",
        body="Texto editorial sin evidencia cuantitativa ni enlaces a fuentes verificables.",
    )

    with pytest.raises(ValueError, match="fuente|evidencia|afirmación|claim"):
        copywriter.caption(nota, "instagram")
