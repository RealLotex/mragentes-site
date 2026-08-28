from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from scripts.social import brand, canvas, templates
from tests.unit.social._helpers import install_fast_render, rich_piece


MANIFEST = Path(__file__).resolve().parents[1] / "fixtures" / "social" / "snapshot_manifest.json"


def _install_snapshot_surfaces(monkeypatch: pytest.MonkeyPatch) -> dict[str, canvas.Surface]:
    surfaces = {
        "feed": canvas.Surface("feed", 360, 360, 24, label="test feed", type_scale=0.52),
        "portrait": canvas.Surface(
            "portrait", 360, 450, 26, label="test portrait", type_scale=0.52
        ),
        "story": canvas.Surface(
            "story",
            360,
            640,
            28,
            safe_top=40,
            safe_bottom=60,
            label="test story",
            type_scale=0.58,
        ),
    }
    monkeypatch.setattr(canvas, "SURFACES", surfaces)
    return surfaces


def _relative_luminance(color: tuple[int, int, int]) -> float:
    values = []
    for channel in color:
        normalized = channel / 255
        values.append(
            normalized / 12.92
            if normalized <= 0.04045
            else ((normalized + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]


def _contrast(first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
    high, low = sorted((_relative_luminance(first), _relative_luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.trace("VIS-SOCIAL-001")
@pytest.mark.baseline_green
@pytest.mark.visual
def test_each_template_matches_deterministic_characterization_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fast_render(monkeypatch)
    _install_snapshot_surfaces(monkeypatch)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = manifest["sha256_prefix"]
    actual = {}

    for key in templates.TEMPLATES:
        image = templates.render(key, rich_piece(), "feed", seed=manifest["seed"]).img
        actual[key] = hashlib.sha256(image.tobytes()).hexdigest()[:16]

    assert actual == expected


@pytest.mark.trace("VIS-SOCIAL-002")
@pytest.mark.baseline_green
@pytest.mark.visual
def test_all_templates_render_nonblank_native_story_compositions_inside_safe_canvas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fast_render(monkeypatch)
    surfaces = _install_snapshot_surfaces(monkeypatch)
    expected = surfaces["story"]

    for key in templates.TEMPLATES:
        sheet = templates.render(key, rich_piece(), "story", seed=11)
        assert sheet.img.size == (expected.w, expected.h)
        colors = sheet.img.resize((48, 48)).getcolors(maxcolors=48 * 48)
        assert colors is not None and len(colors) >= 8, key
        x0, y0, x1, y1 = sheet.content_box
        assert x0 >= expected.margin
        assert y0 > expected.safe_top
        assert x1 <= expected.w - expected.margin
        assert y1 < expected.h - expected.safe_bottom


@pytest.mark.trace("VIS-SOCIAL-003")
@pytest.mark.baseline_green
@pytest.mark.visual
def test_brand_text_and_accent_contrast_meet_wcag_aa_on_every_ground() -> None:
    for ground in ("paper", "ink", "minio"):
        palette = brand.Palette(ground)
        assert _contrast(palette.fg, palette.bg) >= 4.5, ground
        assert _contrast(palette.fg_soft, palette.bg) >= 4.5, ground
        assert _contrast(palette.accent, palette.bg) >= 4.5, ground


@pytest.mark.trace("VIS-SOCIAL-004")
@pytest.mark.baseline_green
@pytest.mark.visual
def test_same_seed_is_pixel_identical_and_different_ground_is_visibly_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fast_render(monkeypatch)
    _install_snapshot_surfaces(monkeypatch)
    piece = rich_piece()
    first = templates.render("titular", piece, "portrait", seed=9, ground="paper").img
    second = templates.render("titular", piece, "portrait", seed=9, ground="paper").img
    dark = templates.render("titular", piece, "portrait", seed=9, ground="ink").img

    assert first.tobytes() == second.tobytes()
    differing = sum(
        a != b
        for a, b in zip(
            first.resize((64, 64)).get_flattened_data(),
            dark.resize((64, 64)).get_flattened_data(),
        )
    )
    assert differing / (64 * 64) >= 0.80


@pytest.mark.trace("VIS-SOCIAL-005")
@pytest.mark.baseline_green
@pytest.mark.visual
def test_saved_social_jpeg_has_expected_dimensions_mode_and_bounded_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fast_render(monkeypatch)
    surfaces = _install_snapshot_surfaces(monkeypatch)
    sheet = templates.render("anuncio", rich_piece(), "portrait", seed=5)
    target = sheet.save(tmp_path / "social" / "daily.jpg", quality=86)

    assert 5_000 <= target.stat().st_size <= 1_000_000
    with Image.open(target) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert image.size == (surfaces["portrait"].w, surfaces["portrait"].h)
