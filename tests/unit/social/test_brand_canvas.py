from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw

from scripts.social import brand, canvas
from tests.unit.social._helpers import DEJAVU, fast_font, install_fast_render


@pytest.mark.trace("SOCIAL-RENDER-BRAND-001")
@pytest.mark.baseline_green
def test_missing_brand_font_raises_actionable_domain_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    brand._ttf_path.cache_clear()
    monkeypatch.setattr(brand, "FONT_DIR", tmp_path)
    monkeypatch.setitem(brand.FONT_FILES, "display", "missing.woff2")

    with pytest.raises(brand.FontUnavailable, match="Falta la fuente"):
        brand._ttf_path("display")
    brand._ttf_path.cache_clear()


@pytest.mark.trace("SOCIAL-RENDER-BRAND-002")
@pytest.mark.baseline_green
def test_font_clamps_size_and_reuses_cached_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    brand.font.cache_clear()
    monkeypatch.setattr(brand, "_ttf_path", lambda role: DEJAVU)

    first = brand.font("display", 1, 400, 100)
    second = brand.font("display", 1, 400, 100)

    assert first is second
    assert first.size == 6
    brand.font.cache_clear()


@pytest.mark.trace("SOCIAL-RENDER-BRAND-003")
@pytest.mark.baseline_green
def test_sanitize_replaces_unsupported_symbols_and_preserves_supported_spanish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supported = frozenset(ord(char) for char in "áéíóúüñÁÉÍÓÚÜÑ abcdefghijklmnopqrstuvwxyz<>=!~»«·x(c)")
    monkeypatch.setattr(brand, "supported_codepoints", lambda role: supported)

    sanitized = brand.sanitize("niñez → 42% ✓ ™ ©", "display")

    assert sanitized == "niñez »  ·  (c)"
    assert brand.sanitize("", "display") == ""


@pytest.mark.trace("SOCIAL-RENDER-BRAND-004")
@pytest.mark.baseline_green
def test_hand_has_requested_size_alpha_and_deterministic_recolor() -> None:
    brand.hand.cache_clear()
    first = brand.hand(32, (1, 2, 3), (240, 241, 242))
    second = brand.hand(32, (1, 2, 3), (240, 241, 242))

    assert first.size == (32, 32)
    assert first.mode == "RGBA"
    assert first is second
    assert first.getbbox() is not None
    brand.hand.cache_clear()


@pytest.mark.trace("SOCIAL-RENDER-BRAND-005")
@pytest.mark.baseline_green
def test_palettes_have_complete_tokens_and_expected_darkness() -> None:
    for ground, dark in (("paper", False), ("ink", True), ("minio", True)):
        palette = brand.Palette(ground)
        assert palette.is_dark is dark
        for name in ("bg", "bg_alt", "fg", "fg_soft", "fg_faint", "accent", "rule", "panel"):
            color = getattr(palette, name)
            assert len(color) == 3
            assert all(0 <= channel <= 255 for channel in color)
        assert palette.fg != palette.bg


@pytest.mark.trace("SOCIAL-RENDER-BRAND-006")
@pytest.mark.red_expected
def test_palette_rejects_unknown_ground_instead_of_silently_using_paper() -> None:
    with pytest.raises(ValueError, match="ground|fondo|palette"):
        brand.Palette("transparent-neon")


@pytest.mark.trace("SOCIAL-RENDER-CANVAS-001")
@pytest.mark.baseline_green
def test_surface_registry_has_exact_platform_dimensions_and_ratios() -> None:
    assert canvas.surface("feed").w == canvas.surface("feed").h == 1080
    assert canvas.surface("portrait").ratio == pytest.approx(4 / 5)
    assert canvas.surface("story").ratio == pytest.approx(9 / 16)
    assert canvas.surface("story").safe_top > 0
    assert canvas.surface("story").safe_bottom > 0
    with pytest.raises(KeyError, match="Superficie desconocida"):
        canvas.surface("banner")


@pytest.mark.trace("SOCIAL-RENDER-CANVAS-002")
@pytest.mark.baseline_green
def test_text_width_and_wrap_handle_tracking_paragraphs_and_long_words() -> None:
    fnt = fast_font(size=24)
    assert canvas.text_width(fnt, "") == 0
    assert canvas.text_width(fnt, "abc", 2) == pytest.approx(fnt.getlength("abc") + 4)

    lines = canvas.wrap_text("uno dos\n\nsupercalifragilistico", fnt, max_w=100)
    assert lines[:2] == ["uno dos", ""]
    assert "".join(lines[2:]) == "supercalifragilistico"
    assert all(canvas.text_width(fnt, line) <= 100 or len(line) == 1 for line in lines if line)


@pytest.mark.trace("SOCIAL-RENDER-CANVAS-003")
@pytest.mark.baseline_green
def test_fit_text_chooses_largest_fit_and_truncates_when_minimum_overflows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(brand, "font", fast_font)
    monkeypatch.setattr(brand, "sanitize", lambda text, role="display": text)

    fitted = canvas.fit_text(
        "Una frase que tiene que entrar en dos líneas",
        max_w=340,
        max_h=130,
        size_max=60,
        size_min=18,
        max_lines=2,
    )
    assert 18 <= fitted.size <= 60
    assert fitted.height <= 130
    assert len(fitted.lines) <= 2
    assert fitted.is_empty is False

    truncated = canvas.fit_text(
        "texto " * 100,
        max_w=120,
        max_h=22,
        size_max=30,
        size_min=18,
        max_lines=1,
    )
    assert truncated.truncated is True
    assert truncated.lines[-1].endswith("…")
    assert truncated.height <= 22

    empty = canvas.fit_text("   ", max_w=100, max_h=100)
    assert empty.is_empty is True
    assert empty.height == 0


@pytest.mark.trace("SOCIAL-RENDER-CANVAS-004")
@pytest.mark.baseline_green
def test_draw_helpers_respect_alignment_and_return_consumed_height() -> None:
    image = Image.new("RGB", (320, 160), "white")
    draw = ImageDraw.Draw(image)
    fnt = fast_font(size=24)
    fitted = canvas.FittedText(["uno", "dos"], fnt, 24, 32, 64)

    canvas.draw_tracked(draw, (0, 0), "CENTRO", fnt, "black", align="center", box_w=320)
    bottom = canvas.draw_fitted(draw, fitted, 0, 50, 320, "black", align="right", tracking=1)

    assert bottom == 114
    assert ImageChops.difference(image, Image.new("RGB", image.size, "white")).getbbox() is not None


@pytest.mark.trace("SOCIAL-RENDER-CANVAS-005")
@pytest.mark.baseline_green
def test_cover_preserves_aspect_ratio_and_focus_changes_crop() -> None:
    source = Image.new("RGB", (400, 200))
    draw = ImageDraw.Draw(source)
    draw.rectangle((0, 0, 199, 199), fill="red")
    draw.rectangle((200, 0, 399, 199), fill="blue")

    left = canvas.cover(source, 100, 100, focus=(0.0, 0.5))
    right = canvas.cover(source, 100, 100, focus=(1.0, 0.5))

    assert left.size == right.size == (100, 100)
    assert left.getpixel((50, 50)) == (255, 0, 0)
    assert right.getpixel((50, 50)) == (0, 0, 255)


@pytest.mark.trace("SOCIAL-RENDER-CANVAS-006")
@pytest.mark.baseline_green
def test_duotone_grain_and_scrim_are_deterministic_and_dimension_preserving() -> None:
    gradient = Image.new("RGB", (32, 24))
    gradient.putdata([(x * 8, x * 8, x * 8) for _y in range(24) for x in range(32)])

    duo = canvas.duotone(gradient, (0, 0, 0), (240, 230, 220))
    grain_one = canvas.grain(duo, amount=4, seed=9)
    grain_two = canvas.grain(duo, amount=4, seed=9)
    veiled = canvas.scrim(duo, (0, 0, 0), 0.5, direction="up")

    assert duo.size == grain_one.size == veiled.size == gradient.size
    assert grain_one.tobytes() == grain_two.tobytes()
    assert canvas.grain(duo, amount=0) is duo
    assert veiled.getpixel((16, 0)) != veiled.getpixel((16, 23))


@pytest.mark.trace("SOCIAL-RENDER-CANVAS-007")
@pytest.mark.baseline_green
def test_sheet_content_box_respects_safe_areas_and_save_formats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fast_render(monkeypatch)
    sheet = canvas.Sheet(canvas.STORY, seed="stable-seed", ruled=True)
    sheet.chrome(section="prueba", meta="26.08.2026")
    x0, y0, x1, y1 = sheet.content_box

    assert x0 >= canvas.STORY.margin
    assert y0 > canvas.STORY.safe_top
    assert x1 <= canvas.STORY.w - canvas.STORY.margin
    assert y1 < canvas.STORY.h - canvas.STORY.safe_bottom
    assert sheet.content_w == x1 - x0
    assert sheet.content_h == y1 - y0

    jpg = sheet.save(tmp_path / "nested" / "piece.jpg", quality=80)
    png = sheet.save(tmp_path / "piece.png")
    assert jpg.exists() and png.exists()
    with Image.open(jpg) as saved_jpg, Image.open(png) as saved_png:
        assert saved_jpg.size == saved_png.size == (1080, 1920)
        assert saved_jpg.format == "JPEG"
        assert saved_png.format == "PNG"


@pytest.mark.trace("SOCIAL-RENDER-CANVAS-008")
@pytest.mark.red_expected
def test_cover_rejects_out_of_range_focus_coordinates() -> None:
    source = Image.new("RGB", (200, 100), "white")

    for focus in ((-0.1, 0.5), (1.1, 0.5), (0.5, -1), (0.5, 2)):
        with pytest.raises(ValueError, match="focus|foco|0.*1"):
            canvas.cover(source, 100, 100, focus=focus)


@pytest.mark.trace("SOCIAL-RENDER-CANVAS-009")
@pytest.mark.red_expected
def test_fit_text_rejects_impossible_dimensions_and_invalid_size_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(brand, "font", fast_font)

    invalid = (
        {"max_w": 0, "max_h": 100, "size_min": 20, "size_max": 40},
        {"max_w": 100, "max_h": -1, "size_min": 20, "size_max": 40},
        {"max_w": 100, "max_h": 100, "size_min": 40, "size_max": 20},
        {"max_w": 100, "max_h": 100, "size_min": 0, "size_max": 20},
    )
    for kwargs in invalid:
        with pytest.raises(ValueError, match="dimension|size|max|min|tamaño"):
            canvas.fit_text("contenido", **kwargs)
