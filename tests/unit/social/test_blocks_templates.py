from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from PIL import Image

from scripts.social import blocks, canvas, templates
from tests.unit.social._helpers import install_fast_render, rich_piece


@dataclass
class ProbeBlock(blocks.Block):
    requested: int
    flex_value: float = 0
    measurements: list[tuple[int, int]] = field(default_factory=list)
    draws: list[tuple[int, int, int, int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.flex = self.flex_value

    def measure(self, sheet, width: int, budget: int) -> int:
        self.measurements.append((width, budget))
        return self.requested

    def draw(self, sheet, x: int, y: int, width: int, height: int) -> None:
        self.draws.append((x, y, width, height))


def _small_surfaces(monkeypatch: pytest.MonkeyPatch) -> dict[str, canvas.Surface]:
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


@pytest.mark.trace("SOCIAL-RENDER-BLOCK-CORE-001")
@pytest.mark.baseline_green
def test_scale_gap_and_flex_obey_surface_and_budget() -> None:
    sheet = canvas.Sheet(canvas.Surface("test", 200, 300, 20, type_scale=1.5), seed=1)
    assert blocks.sc(sheet, 10) == 15
    assert blocks.sc(sheet, 0) == 1
    assert blocks.Gap(40).measure(sheet, 100, 25) == 25
    flex = blocks.Flex(2.5)
    assert flex.flex == 2.5
    assert flex.measure(sheet, 100, 100) == 0


@pytest.mark.trace("SOCIAL-RENDER-BLOCK-CORE-002")
@pytest.mark.baseline_green
def test_natural_height_clamps_negative_and_oversized_measurements_to_budget() -> None:
    sheet = canvas.Sheet(canvas.Surface("test", 200, 300, 20), seed=1)
    probes = [ProbeBlock(40), ProbeBlock(-10), ProbeBlock(200)]

    total = blocks.natural_height(sheet, probes, width := 120, budget := 100)

    assert total == 100
    assert probes[0].measurements == [(width, budget)]
    assert probes[1].measurements == [(width, 60)]
    assert probes[2].measurements == [(width, 60)]


@pytest.mark.trace("SOCIAL-RENDER-BLOCK-CORE-003")
@pytest.mark.baseline_green
def test_stack_never_draws_more_than_box_and_honors_center_bottom_and_flex() -> None:
    sheet = canvas.Sheet(canvas.Surface("test", 200, 300, 20), seed=1)
    top = ProbeBlock(30)
    flex = ProbeBlock(0, flex_value=1)
    blocks.stack(sheet, [top, flex], box=(10, 20, 190, 220))
    assert top.draws == [(10, 20, 180, 30)]
    assert flex.draws == [(10, 50, 180, 170)]

    centered = ProbeBlock(40)
    blocks.stack(sheet, [centered], box=(0, 0, 100, 100), align="center")
    assert centered.draws[0][1] == 30
    bottom = ProbeBlock(40)
    blocks.stack(sheet, [bottom], box=(0, 0, 100, 100), align="bottom")
    assert bottom.draws[0][1] == 60


@pytest.mark.trace("SOCIAL-RENDER-BLOCK-CORE-004")
@pytest.mark.baseline_green
def test_every_concrete_block_measures_within_budget_and_draws_without_overflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fast_render(monkeypatch)
    photo = tmp_path / "photo.png"
    Image.new("RGB", (300, 180), "navy").save(photo)
    sheet = canvas.Sheet(canvas.Surface("test", 500, 700, 30, type_scale=0.7), seed=5)
    sheet.chrome(section="test")
    representatives: list[blocks.Block] = [
        blocks.Gap(20),
        blocks.Flex(1),
        blocks.Rule(thickness=2, accent=True),
        blocks.Kicker("criterio"),
        blocks.Heading("Un título verificable que puede ocupar más de una línea"),
        blocks.Body("Un cuerpo suficientemente largo para comprobar ajuste y presupuesto."),
        blocks.Mono("dedupe_key=stable"),
        blocks.Stat("42%", unit="menos", caption="Tiempo operativo evitado"),
        blocks.Ledger(items=["uno", ("dos", "detalle"), {"title": "tres", "detail": "dato"}]),
        blocks.Steps(items=[("definir", "el objetivo"), ("medir", "el resultado")]),
        blocks.KeyValues(rows=[("kind", "daily_owned"), ("status", "partial")]),
        blocks.Quote("Una automatización responsable debe poder explicarse.", "MR Agentes"),
        blocks.Columns(cols=[[blocks.Body("izquierda")], [blocks.Body("derecha")]]),
        blocks.Panel(blocks=[blocks.Kicker("panel"), blocks.Body("contenido")]),
        blocks.PhotoBand(photo, caption="Foto de prueba"),
        blocks.HandMark(size=80),
        blocks.Chips(items=["automatización", "pymes", "datos"]),
    ]
    x, y, _, _ = sheet.content_box
    for block in representatives:
        budget = 420
        height = block.measure(sheet, 400, budget)
        assert 0 <= height <= budget, type(block).__name__
        block.draw(sheet, x, y, 400, height)


@pytest.mark.trace("SOCIAL-RENDER-BLOCK-CORE-005")
@pytest.mark.baseline_green
def test_ledger_normalizes_strings_sequences_and_mappings_without_mutating_input() -> None:
    source = ["simple", ("title", "detail"), ["only"], {"title": "mapped", "detail": "value"}]
    original = ["simple", ("title", "detail"), ["only"], {"title": "mapped", "detail": "value"}]
    ledger = blocks.Ledger(items=source)

    assert ledger._normalize() == [
        ("simple", ""),
        ("title", "detail"),
        ("only", ""),
        ("mapped", "value"),
    ]
    assert source == original


@pytest.mark.trace("SOCIAL-RENDER-BLOCK-CORE-006")
@pytest.mark.baseline_green
def test_columns_switch_between_row_and_story_column_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fast_render(monkeypatch)
    feed = canvas.Sheet(canvas.Surface("feed", 400, 400, 20), seed=1)
    story = canvas.Sheet(canvas.Surface("story", 400, 700, 20), seed=1)
    column = blocks.Columns(
        cols=[[blocks.Gap(30)], [blocks.Gap(40)]], ratios=[1, 2], gap=20, stack_on=("story",)
    )

    assert 0 <= column.measure(feed, 300, 200) <= 200
    assert column._mode == "row"
    assert 0 <= column.measure(story, 300, 200) <= 200
    assert column._mode == "column"
    assert len(column._heights) == 2


@pytest.mark.trace("SOCIAL-RENDER-BLOCK-CORE-007")
@pytest.mark.red_expected
def test_empty_quote_and_invalid_flex_weight_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fast_render(monkeypatch)
    sheet = canvas.Sheet(canvas.Surface("test", 300, 400, 20), seed=1)

    assert blocks.Quote("").measure(sheet, 250, 200) == 0
    for invalid in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="flex|weight|peso"):
            blocks.Flex(invalid)


@pytest.mark.trace("SOCIAL-RENDER-TEMPLATE-001")
@pytest.mark.baseline_green
def test_piece_from_dict_filters_unknown_fields_without_mutating_input() -> None:
    raw = {"title": "Prueba", "items": ["uno"], "unknown": "ignored"}
    piece = templates.Piece.from_dict(raw)

    assert piece.title == "Prueba"
    assert piece.items == ["uno"]
    assert not hasattr(piece, "unknown")
    assert raw == {"title": "Prueba", "items": ["uno"], "unknown": "ignored"}


@pytest.mark.trace("SOCIAL-RENDER-TEMPLATE-002")
@pytest.mark.baseline_green
def test_template_registry_has_fifteen_unique_complete_templates() -> None:
    assert len(templates.TEMPLATES) == 15
    assert len(templates.TEMPLATES) == len(set(templates.TEMPLATES))
    for key, template in templates.TEMPLATES.items():
        assert template.key == key
        assert template.name and template.summary
        assert template.grounds
        assert callable(template.fn)
    with pytest.raises(KeyError, match="Plantilla desconocida"):
        templates.get("does-not-exist")


@pytest.mark.trace("SOCIAL-RENDER-TEMPLATE-003")
@pytest.mark.baseline_green
def test_every_template_renders_every_surface_with_correct_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fast_render(monkeypatch)
    surfaces = _small_surfaces(monkeypatch)
    piece = rich_piece()

    for key in templates.TEMPLATES:
        for surface_key, expected in surfaces.items():
            sheet = templates.render(key, piece, surface_key, seed=7)
            assert sheet.surface.key == surface_key
            assert sheet.img.size == (expected.w, expected.h)
            x0, y0, x1, y1 = sheet.content_box
            assert 0 <= x0 < x1 <= expected.w
            assert 0 <= y0 < y1 <= expected.h


@pytest.mark.trace("SOCIAL-RENDER-TEMPLATE-004")
@pytest.mark.baseline_green
def test_template_ground_rotation_and_explicit_ground_are_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fast_render(monkeypatch)
    _small_surfaces(monkeypatch)
    piece = rich_piece()
    template = templates.get("titular")

    first = template.render(piece, "feed", seed=3)
    second = template.render(piece, "feed", seed=3)
    explicit = template.render(piece, "feed", seed=99, ground="ink")

    assert first.ground == second.ground == template.grounds[3 % len(template.grounds)]
    assert first.img.tobytes() == second.img.tobytes()
    assert explicit.ground == "ink"


@pytest.mark.trace("SOCIAL-RENDER-TEMPLATE-005")
@pytest.mark.baseline_green
def test_carousel_preserves_order_increments_seed_and_supports_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fast_render(monkeypatch)
    _small_surfaces(monkeypatch)
    piece = rich_piece()

    sheets = templates.carousel(
        [("titular", piece), ("dato", piece), ("anuncio", piece)],
        surface_key="portrait",
        seed=10,
    )

    assert len(sheets) == 3
    assert all(sheet.surface.key == "portrait" for sheet in sheets)
    assert [sheet.seed for sheet in sheets] == [10, 11, 12]
    assert templates.carousel([], seed=10) == []


@pytest.mark.trace("SOCIAL-RENDER-TEMPLATE-006")
@pytest.mark.red_expected
def test_template_render_validates_declared_required_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fast_render(monkeypatch)
    _small_surfaces(monkeypatch)

    for key, template in templates.TEMPLATES.items():
        if not template.needs:
            continue
        with pytest.raises(ValueError, match="campo|required|falta|necesita"):
            template.render(templates.Piece(), "feed", seed=1)


@pytest.mark.trace("SOCIAL-RENDER-TEMPLATE-007")
@pytest.mark.red_expected
def test_template_render_rejects_ground_not_declared_by_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fast_render(monkeypatch)
    _small_surfaces(monkeypatch)

    with pytest.raises(ValueError, match="ground|fondo|permitido"):
        templates.get("mito").render(rich_piece(), "feed", seed=1, ground="transparent")
