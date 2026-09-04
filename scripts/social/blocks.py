"""
Bloques de composición.

El apilador reparte el alto de arriba hacia abajo dándole a cada bloque el
presupuesto que sobra: un bloque nunca puede medir más de lo que le queda, así
que la suma no se pasa del área de contenido. Ese es el motivo por el que no
hay desbordes — no es que estén "controlados", es que no pueden ocurrir.

Los bloques leen los colores de `sheet.palette`, así que la misma plantilla
compone bien sobre papel, sobre tinta o sobre minio. Ahí está buena parte de la
variedad: no hacen falta treinta plantillas para que no se vean todas iguales.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw

from . import brand
from .canvas import Sheet, cover, draw_fitted, draw_tracked, duotone, fit_text, text_width


def sc(sheet: "Sheet", value: float) -> int:
    """Cuerpo tipográfico ajustado a la superficie (ver Surface.type_scale)."""
    return max(1, int(round(value * sheet.surface.type_scale)))


# ── Apilador ────────────────────────────────────────────────────────────────


class Block:
    """Mide contra el presupuesto que le dan y dibuja dentro de lo que midió."""

    flex: float = 0.0

    def measure(self, sheet: Sheet, w: int, budget: int) -> int:
        return 0

    def draw(self, sheet: Sheet, x: int, y: int, w: int, h: int) -> None:  # pragma: no cover
        pass


def natural_height(sheet: Sheet, blocks: list[Block], w: int, budget: int) -> int:
    total = 0
    remaining = budget
    for b in blocks:
        h = max(0, min(b.measure(sheet, w, remaining), remaining))
        total += h
        remaining -= h
    return total


def stack(sheet: Sheet, blocks: list[Block], box=None, align: str = "top") -> None:
    x0, y0, x1, y1 = box or sheet.content_box
    w = int(x1 - x0)
    height = int(y1 - y0)

    heights: list[int] = []
    remaining = height
    for b in blocks:
        h = max(0, min(int(b.measure(sheet, w, remaining)), remaining))
        heights.append(h)
        remaining -= h

    total_flex = sum(b.flex for b in blocks)
    if total_flex > 0 and remaining > 0:
        leftover = remaining
        # En 9:16 el aire sobrante es mucho. Si se lo queda todo el elástico
        # del final, la composición se apelmaza contra la cabecera; un tercio
        # va arriba para que el bloque caiga donde el ojo mira.
        if sheet.surface.key == "story" and leftover > height * 0.10 and blocks and not blocks[0].flex:
            top_share = int(leftover * 0.32)
            y0 += top_share
            leftover -= top_share
        for i, b in enumerate(blocks):
            if b.flex:
                heights[i] += int(leftover * b.flex / total_flex)
        remaining = height - sum(heights)

    y = y0
    if not total_flex and remaining > 0:
        if align == "center":
            y += remaining // 2
        elif align == "bottom":
            y += remaining

    for b, h in zip(blocks, heights):
        if h > 0:
            b.draw(sheet, int(x0), int(y), w, int(h))
        y += h


# ── Espaciadores ────────────────────────────────────────────────────────────


@dataclass
class Gap(Block):
    px: int = 24

    def measure(self, sheet, w, budget):
        return min(self.px, budget)


@dataclass
class Flex(Block):
    weight: float = 1.0

    def __post_init__(self):
        try:
            weight = float(self.weight)
        except (TypeError, ValueError) as exc:
            raise ValueError("El peso flex debe ser un número finito no negativo") from exc
        if not math.isfinite(weight) or weight < 0:
            raise ValueError("El peso flex debe ser finito y no negativo")
        self.flex = weight

    def measure(self, sheet, w, budget):
        return 0


# ── Filetes ─────────────────────────────────────────────────────────────────


@dataclass
class Rule(Block):
    thickness: int = 1
    frac: float = 1.0
    color: tuple | None = None
    pad_top: int = 18
    pad_bottom: int = 18
    accent: bool = False

    def measure(self, sheet, w, budget):
        return min(self.pad_top + self.thickness + self.pad_bottom, budget)

    def draw(self, sheet, x, y, w, h):
        color = self.color or (sheet.palette.accent if self.accent else sheet.palette.rule)
        sheet.draw.rectangle(
            [x, y + self.pad_top, x + int(w * self.frac), y + self.pad_top + self.thickness - 1],
            fill=color,
        )


# ── Texto ───────────────────────────────────────────────────────────────────


@dataclass
class Kicker(Block):
    """Clave al margen: versalitas de Chivo Mono, espaciadas, en minio."""

    text: str
    size: int = 25
    tracking: float = 5.0
    color: tuple | None = None
    align: str = "left"
    weight: int = 500

    def measure(self, sheet, w, budget):
        if not self.text:
            return 0
        return min(int(sc(sheet, self.size) * 1.5), budget)

    def draw(self, sheet, x, y, w, h):
        if not self.text:
            return
        fnt = brand.font("data", sc(sheet, self.size), self.weight)
        draw_tracked(
            sheet.draw,
            (x, y),
            self.text.upper(),
            fnt,
            self.color or sheet.palette.accent,
            self.tracking,
            self.align,
            w,
            role="data",
        )


@dataclass
class Heading(Block):
    text: str
    size_max: int = 108
    size_min: int = 34
    max_lines: int = 5
    weight: int = 700
    width: int = 92
    frac: float = 0.62
    color: tuple | None = None
    align: str = "left"
    role: str = "display"
    leading: float | None = None
    _fit: object = field(default=None, init=False, repr=False)

    def measure(self, sheet, w, budget):
        if not self.text:
            return 0
        cap = min(budget, int(sheet.content_h * self.frac))
        minimum = max(1, int(self.size_min))
        self._fit = fit_text(
            self.text,
            role=self.role,
            weight=self.weight,
            width=self.width,
            max_w=w,
            max_h=cap,
            size_max=max(minimum, sc(sheet, self.size_max)),
            size_min=minimum,
            max_lines=self.max_lines,
            leading=self.leading,
        )
        return min(self._fit.height, budget)

    def draw(self, sheet, x, y, w, h):
        if not self._fit:
            return
        draw_fitted(sheet.draw, self._fit, x, y, w, self.color or sheet.palette.fg, self.align)


@dataclass
class Body(Block):
    """Texto largo en Alegreya, como el cuerpo de las notas."""

    text: str
    size_max: int = 44
    size_min: int = 24
    max_lines: int = 8
    frac: float = 0.4
    color: tuple | None = None
    align: str = "left"
    role: str = "text"
    weight: int = 400
    _fit: object = field(default=None, init=False, repr=False)

    def measure(self, sheet, w, budget):
        if not self.text:
            return 0
        cap = min(budget, int(sheet.content_h * self.frac))
        minimum = max(1, int(self.size_min))
        self._fit = fit_text(
            self.text,
            role=self.role,
            weight=self.weight,
            max_w=w,
            max_h=cap,
            size_max=max(minimum, sc(sheet, self.size_max)),
            size_min=minimum,
            max_lines=self.max_lines,
        )
        return min(self._fit.height, budget)

    def draw(self, sheet, x, y, w, h):
        if not self._fit:
            return
        draw_fitted(sheet.draw, self._fit, x, y, w, self.color or sheet.palette.fg_soft, self.align)


@dataclass
class Mono(Block):
    text: str
    size: int = 26
    tracking: float = 1.6
    color: tuple | None = None
    align: str = "left"
    max_lines: int = 3
    weight: int = 400
    _fit: object = field(default=None, init=False, repr=False)

    def measure(self, sheet, w, budget):
        if not self.text:
            return 0
        minimum = max(1, max(15, self.size - 10))
        self._fit = fit_text(
            self.text,
            role="data",
            weight=self.weight,
            max_w=w,
            max_h=budget,
            size_max=max(minimum, sc(sheet, self.size)),
            size_min=minimum,
            max_lines=self.max_lines,
            tracking=self.tracking,
        )
        return min(self._fit.height, budget)

    def draw(self, sheet, x, y, w, h):
        if not self._fit:
            return
        draw_fitted(sheet.draw, self._fit, x, y, w, self.color or sheet.palette.fg_faint, self.align, self.tracking)


# ── Dato grande ─────────────────────────────────────────────────────────────


@dataclass
class Stat(Block):
    value: str
    unit: str = ""
    caption: str = ""
    frac: float = 0.5
    align: str = "left"
    _fit: object = field(default=None, init=False, repr=False)
    _cap: object = field(default=None, init=False, repr=False)
    _unit_font: object = field(default=None, init=False, repr=False)

    _show_unit: bool = field(default=False, init=False, repr=False)

    def measure(self, sheet, w, budget):
        """La cifra manda; el epígrafe entra sólo si sobra lugar de verdad."""
        self._cap = None
        self._show_unit = False
        if budget <= 0 or not self.value:
            self._fit = None
            return 0

        cap_h = min(budget, int(sheet.content_h * self.frac))
        value_budget = int(cap_h * (0.64 if self.caption else 1.0))
        self._fit = fit_text(
            self.value,
            role="data",
            weight=600,
            max_w=w,
            max_h=value_budget,
            size_max=min(int(sheet.surface.w * 0.34), max(60, value_budget)),
            size_min=44,
            max_lines=1,
            leading=1.06,
        )
        if not self._fit.lines:
            self._fit = None
            return 0

        total = self._fit.height
        if self.unit:
            unit_font = brand.font("data", max(22, int(self._fit.size * 0.26)), 500)
            value_w = text_width(self._fit.font, self._fit.lines[0])
            self._show_unit = value_w + text_width(unit_font, self.unit, 2.0) + 16 <= w

        rest = min(budget, cap_h) - total - 22
        if self.caption and rest > 28:
            self._cap = fit_text(
                self.caption,
                role="display",
                weight=500,
                max_w=w,
                max_h=rest,
                size_max=sc(sheet, 44),
                size_min=22,
                max_lines=3,
            )
            if self._cap.lines:
                total += 22 + self._cap.height
            else:
                self._cap = None
        return min(total, budget)

    def draw(self, sheet, x, y, w, h):
        if not self._fit:
            return
        pal = sheet.palette
        draw_fitted(sheet.draw, self._fit, x, y, w, pal.accent, self.align)
        if self._show_unit:
            unit_font = brand.font("data", max(22, int(self._fit.size * 0.26)), 500)
            vw = text_width(self._fit.font, self._fit.lines[0])
            draw_tracked(sheet.draw, (x + vw + 16, y + self._fit.size * 0.18), self.unit,
                         unit_font, pal.fg_faint, 2.0, role="data")
        if self._cap:
            draw_fitted(sheet.draw, self._cap, x, y + self._fit.height + 22, w, pal.fg, self.align)


# ── Listas ──────────────────────────────────────────────────────────────────


@dataclass
class Ledger(Block):
    """Lista reglada, sin viñetas ni tarjetas: número, título y filete."""

    items: list = field(default_factory=list)
    numbered: bool = True
    marker: str = ""
    _rows: list = field(default_factory=list, init=False, repr=False)
    _pad: int = field(default=22, init=False, repr=False)

    def _normalize(self):
        rows = []
        for it in self.items:
            if isinstance(it, (tuple, list)):
                rows.append((str(it[0]), str(it[1]) if len(it) > 1 else ""))
            elif isinstance(it, dict):
                rows.append((str(it.get("title", "")), str(it.get("detail", ""))))
            else:
                rows.append((str(it), ""))
        return rows

    def measure(self, sheet, w, budget):
        rows = self._normalize()
        if not rows:
            return 0
        n = len(rows)
        num_w = 84 if sheet.surface.key == "story" else 76
        text_w = w - num_w
        scale = 1.0
        for _ in range(14):
            self._rows = []
            total = 0
            for i, (title, detail) in enumerate(rows):
                t_fit = fit_text(
                    title,
                    role="display",
                    weight=600,
                    max_w=text_w,
                    max_h=budget,
                    size_max=sc(sheet, 46 * scale),
                    size_min=int(22 * scale),
                    max_lines=2,
                )
                d_fit = None
                if detail:
                    detail_minimum = max(1, int(19 * scale))
                    d_fit = fit_text(
                        detail,
                        role="text",
                        max_w=text_w,
                        max_h=budget,
                        size_max=max(detail_minimum, sc(sheet, 34 * scale)),
                        size_min=detail_minimum,
                        max_lines=3,
                    )
                row_h = t_fit.height + (d_fit.height + 8 if d_fit else 0) + self._pad * 2
                self._rows.append((t_fit, d_fit, row_h, num_w))
                total += row_h
            total += n - 1  # filetes
            if total <= budget or scale < 0.5:
                return min(total, budget)
            scale *= 0.9
        return min(budget, sum(r[2] for r in self._rows))

    def draw(self, sheet, x, y, w, h):
        if h <= 0 or w <= 0:
            return
        pal = sheet.palette
        cy = y
        for i, (t_fit, d_fit, row_h, num_w) in enumerate(self._rows):
            if cy + row_h > y + h + 2:
                break
            if i:
                sheet.rule(x, cy, x + w, pal.rule)
            label = self.marker or (f"{i + 1:02d}" if self.numbered else "—")
            nfont = brand.font("data", 27, 500)
            draw_tracked(sheet.draw, (x, cy + self._pad + 6), label, nfont, pal.accent, 1.5, role="data")
            ty = cy + self._pad
            draw_fitted(sheet.draw, t_fit, x + num_w, ty, w - num_w, pal.fg)
            if d_fit:
                draw_fitted(sheet.draw, d_fit, x + num_w, ty + t_fit.height + 8, w - num_w, pal.fg_soft)
            cy += row_h


@dataclass
class Steps(Block):
    """Pasos encadenados por una vertical, como un diagrama de proceso."""

    items: list = field(default_factory=list)
    _rows: list = field(default_factory=list, init=False, repr=False)

    def measure(self, sheet, w, budget):
        if not self.items:
            return 0
        rail = 96
        scale = 1.0
        for _ in range(14):
            self._rows = []
            total = 0
            for it in self.items:
                title, detail = (it, "") if isinstance(it, str) else (it[0], it[1] if len(it) > 1 else "")
                t = fit_text(title, role="display", weight=600, max_w=w - rail, max_h=budget,
                             size_max=sc(sheet, 44 * scale), size_min=int(22 * scale), max_lines=2)
                detail_minimum = max(1, int(18 * scale))
                d = fit_text(detail, role="text", max_w=w - rail, max_h=budget,
                             size_max=max(detail_minimum, sc(sheet, 32 * scale)),
                             size_min=detail_minimum, max_lines=3) if detail else None
                row_h = t.height + (d.height + 6 if d else 0) + 46
                self._rows.append((t, d, row_h, rail))
                total += row_h
            if total <= budget or scale < 0.5:
                return min(total, budget)
            scale *= 0.9
        return min(budget, sum(r[2] for r in self._rows))

    def draw(self, sheet, x, y, w, h):
        pal = sheet.palette
        cy = y
        disc = 42
        for i, (t, d, row_h, rail) in enumerate(self._rows):
            if cy + row_h > y + h + 2:
                break
            cx = x + disc // 2
            if i < len(self._rows) - 1:
                sheet.vrule(cx, cy + disc + 6, cy + row_h + 6, pal.rule)
            sheet.draw.ellipse([x, cy, x + disc, cy + disc], outline=pal.accent, width=2)
            nf = brand.font("data", 21, 600)
            draw_tracked(sheet.draw, (x, cy + disc * 0.22), f"{i + 1}", nf, pal.accent, 0, "center", disc, role="data")
            draw_fitted(sheet.draw, t, x + rail, cy - 2, w - rail, pal.fg)
            if d:
                draw_fitted(sheet.draw, d, x + rail, cy - 2 + t.height + 6, w - rail, pal.fg_soft)
            cy += row_h


@dataclass
class CardGrid(Block):
    """Dos, cuatro o seis tarjetas en una misma lámina.

    Cada tarjeta tiene un título y una explicación breve. La grilla siempre es
    de dos columnas: 2 tarjetas comparan dos alternativas, 4 muestran un
    cuadro compacto y 6 permiten ordenar hasta seis pasos sin reducir la
    tipografía a un tamaño ilegible.
    """

    items: list = field(default_factory=list)
    gap: int = 18
    _cards: list = field(default_factory=list, init=False, repr=False)
    _card_h: int = field(default=0, init=False, repr=False)
    _card_w: int = field(default=0, init=False, repr=False)

    def _normalize(self) -> list[tuple[str, str]]:
        if len(self.items) not in {2, 4, 6}:
            raise ValueError("La grilla necesita exactamente 2, 4 o 6 tarjetas")
        rows: list[tuple[str, str]] = []
        for item in self.items:
            if isinstance(item, dict):
                title = str(item.get("title", ""))
                detail = str(item.get("detail", ""))
            elif isinstance(item, (tuple, list)):
                title = str(item[0]) if item else ""
                detail = str(item[1]) if len(item) > 1 else ""
            else:
                title, detail = str(item), ""
            if not title.strip():
                raise ValueError("Cada tarjeta necesita un título")
            rows.append((title, detail))
        return rows

    def measure(self, sheet, w, budget):
        rows = self._normalize()
        row_count = len(rows) // 2
        cap = min(budget, int(sheet.content_h * 0.62))
        self._card_w = max(1, (w - self.gap) // 2)
        self._card_h = max(1, (cap - self.gap * (row_count - 1)) // row_count)
        pad = max(18, int(self._card_w * 0.075))
        self._cards = []
        for title, detail in rows:
            title_fit = fit_text(
                title,
                role="display",
                weight=650,
                max_w=self._card_w - pad * 2,
                max_h=max(30, int(self._card_h * 0.38)),
                size_max=max(18, sc(sheet, 42 if len(rows) <= 4 else 34)),
                size_min=18,
                max_lines=3,
            )
            detail_fit = fit_text(
                detail,
                role="text",
                max_w=self._card_w - pad * 2,
                max_h=max(24, self._card_h - pad * 2 - title_fit.height - 16),
                size_max=max(16, sc(sheet, 30 if len(rows) <= 4 else 25)),
                size_min=16,
                max_lines=5 if len(rows) <= 4 else 4,
            ) if detail else None
            self._cards.append((title_fit, detail_fit, pad))
        return min(cap, budget)

    def draw(self, sheet, x, y, w, h):
        pal = sheet.palette
        for index, (title_fit, detail_fit, pad) in enumerate(self._cards):
            row, col = divmod(index, 2)
            cx = x + col * (self._card_w + self.gap)
            cy = y + row * (self._card_h + self.gap)
            sheet.draw.rectangle(
                [cx, cy, cx + self._card_w, cy + self._card_h],
                fill=pal.panel,
                outline=pal.rule_strong,
                width=1,
            )
            label = brand.font("data", sc(sheet, 18), 600)
            draw_tracked(sheet.draw, (cx + pad, cy + pad), f"{index + 1:02d}", label,
                         pal.accent, 1.5, role="data")
            title_y = cy + pad + int(sc(sheet, 18) * 1.7)
            draw_fitted(sheet.draw, title_fit, cx + pad, title_y, self._card_w - pad * 2, pal.fg)
            if detail_fit:
                draw_fitted(
                    sheet.draw,
                    detail_fit,
                    cx + pad,
                    title_y + title_fit.height + 14,
                    self._card_w - pad * 2,
                    pal.fg_soft,
                )


@dataclass
class KeyValues(Block):
    """Hoja de especificación: clave al margen, valor a la derecha."""

    rows: list = field(default_factory=list)
    key_frac: float = 0.34
    _fits: list = field(default_factory=list, init=False, repr=False)

    def measure(self, sheet, w, budget):
        if not self.rows:
            return 0
        kw = int(w * self.key_frac)
        vw = w - kw - 24
        scale = 1.0
        pad = 20
        for _ in range(14):
            self._fits = []
            total = 0
            for key, value in self.rows:
                key_minimum = 15
                k = fit_text(str(key), role="data", weight=500, max_w=kw - 16, max_h=budget,
                             size_max=max(key_minimum, sc(sheet, 24 * scale)),
                             size_min=key_minimum, max_lines=2, tracking=2.0)
                v = fit_text(str(value), role="display", weight=500, max_w=vw, max_h=budget,
                             size_max=sc(sheet, 40 * scale), size_min=int(20 * scale), max_lines=3)
                row_h = max(k.height, v.height) + pad * 2
                self._fits.append((k, v, row_h, kw, vw))
                total += row_h + 1
            if total <= budget or scale < 0.5:
                return min(total, budget)
            scale *= 0.9
        return min(budget, sum(r[2] for r in self._fits))

    def draw(self, sheet, x, y, w, h):
        pal = sheet.palette
        cy = y
        pad = 20
        for i, (k, v, row_h, kw, vw) in enumerate(self._fits):
            if cy + row_h > y + h + 2:
                break
            if i:
                sheet.rule(x, cy, x + w, pal.rule)
            draw_fitted(sheet.draw, k, x, cy + pad + 4, kw, pal.fg_faint, "left", 2.0)
            draw_fitted(sheet.draw, v, x + kw + 24, cy + pad, vw, pal.fg)
            cy += row_h


# ── Cita ────────────────────────────────────────────────────────────────────


@dataclass
class Quote(Block):
    text: str
    author: str = ""
    frac: float = 0.66
    _fit: object = field(default=None, init=False, repr=False)
    _auth: object = field(default=None, init=False, repr=False)
    _mark: int = field(default=0, init=False, repr=False)

    def measure(self, sheet, w, budget):
        self._fit = None
        self._auth = None
        self._mark = 0
        if not self.text or not self.text.strip() or budget <= 0:
            return 0
        self._mark = int(sheet.surface.w * 0.14)
        cap = min(budget, int(sheet.content_h * self.frac))
        self._fit = fit_text(
            f"«{self.text.strip()}»",
            role="italic",
            weight=500,
            max_w=w - 12,
            max_h=max(60, cap - self._mark),
            size_max=sc(sheet, 76),
            size_min=28,
            max_lines=8,
        )
        total = self._mark + self._fit.height
        author_budget = budget - total - 34
        if self.author and author_budget > 0:
            author_minimum = 17
            self._auth = fit_text(self.author, role="data", weight=500, max_w=w,
                                  max_h=author_budget,
                                  size_max=max(author_minimum, sc(sheet, 25)),
                                  size_min=author_minimum,
                                  max_lines=2, tracking=2.4)
            total += 34 + self._auth.height
        return min(total, budget)

    def draw(self, sheet, x, y, w, h):
        pal = sheet.palette
        mark_font = brand.font("display", int(self._mark * 1.5), 700, 90)
        sheet.draw.text((x - 6, y - self._mark * 0.62), "“", font=mark_font, fill=pal.accent, anchor="la")
        ty = y + self._mark
        draw_fitted(sheet.draw, self._fit, x, ty, w, pal.fg)
        if self._auth:
            ay = ty + self._fit.height + 18
            sheet.rule(x, ay, x + 90, pal.accent)
            draw_fitted(sheet.draw, self._auth, x, ay + 16, w, pal.fg_faint, "left", 2.4)


# ── Columnas adaptativas ────────────────────────────────────────────────────


@dataclass
class Columns(Block):
    """Dos paños. En cuadrado van lado a lado; en historia, uno arriba del otro.

    Es la clave para que las historias no sean un cuadrado estirado: la misma
    plantilla se recompone según la proporción de la superficie.
    """

    cols: list = field(default_factory=list)
    ratios: list | None = None
    gap: int = 40
    divider: bool = True
    stack_on: tuple = ("story",)
    _mode: str = field(default="row", init=False, repr=False)
    _heights: list = field(default_factory=list, init=False, repr=False)

    def measure(self, sheet, w, budget):
        n = len(self.cols)
        if not n:
            return 0
        self._mode = "column" if sheet.surface.key in self.stack_on else "row"
        ratios = self.ratios or [1] * n
        s = sum(ratios)
        if self._mode == "row":
            widths = [int((w - self.gap * (n - 1)) * r / s) for r in ratios]
            self._heights = [natural_height(sheet, col, cw, budget) for col, cw in zip(self.cols, widths)]
            return min(max(self._heights), budget)
        per = (budget - self.gap * (n - 1)) // n
        self._heights = [min(natural_height(sheet, col, w, per), per) for col in self.cols]
        return min(sum(self._heights) + self.gap * (n - 1), budget)

    def draw(self, sheet, x, y, w, h):
        n = len(self.cols)
        ratios = self.ratios or [1] * n
        s = sum(ratios)
        if self._mode == "row":
            cx = x
            for i, col in enumerate(self.cols):
                cw = int((w - self.gap * (n - 1)) * ratios[i] / s)
                stack(sheet, col, (cx, y, cx + cw, y + h))
                if self.divider and i < n - 1:
                    sheet.vrule(cx + cw + self.gap // 2, y, y + h, sheet.palette.rule)
                cx += cw + self.gap
        else:
            cy = y
            for i, col in enumerate(self.cols):
                ch = self._heights[i] if i < len(self._heights) else h // n
                stack(sheet, col, (x, cy, x + w, cy + ch))
                cy += ch
                if self.divider and i < n - 1:
                    sheet.rule(x, cy + self.gap // 2, x + w, sheet.palette.rule)
                cy += self.gap


@dataclass
class Panel(Block):
    """Paño con fondo propio y filete: sirve para el bloque mito / verdad."""

    blocks: list = field(default_factory=list)
    pad: int = 34
    fill: tuple | None = None
    border: bool = True
    accent_edge: bool = False
    _inner: int = field(default=0, init=False, repr=False)

    def measure(self, sheet, w, budget):
        inner_budget = max(0, budget - self.pad * 2)
        self._inner = natural_height(sheet, self.blocks, w - self.pad * 2, inner_budget)
        return min(self._inner + self.pad * 2, budget)

    def draw(self, sheet, x, y, w, h):
        pal = sheet.palette
        fill = self.fill if self.fill is not None else pal.panel
        sheet.draw.rectangle([x, y, x + w, y + h], fill=fill)
        if self.border:
            sheet.draw.rectangle([x, y, x + w, y + h], outline=pal.rule, width=1)
        if self.accent_edge:
            sheet.draw.rectangle([x, y, x + 5, y + h], fill=pal.accent)
        if h > self.pad * 2 and w > self.pad * 2:
            stack(sheet, self.blocks, (x + self.pad, y + self.pad, x + w - self.pad, y + h - self.pad))


# ── Fotografía dentro del flujo ─────────────────────────────────────────────


@dataclass
class PhotoBand(Block):
    path: Path | str | None = None
    frac: float = 0.46
    focus: tuple = (0.5, 0.42)
    caption: str = ""
    duo: bool = True
    _h: int = field(default=0, init=False, repr=False)
    _cap: object = field(default=None, init=False, repr=False)

    def measure(self, sheet, w, budget):
        if not self.path or not Path(self.path).exists():
            return 0
        self._h = int(min(budget, sheet.content_h * self.frac))
        if self.caption:
            self._cap = fit_text(self.caption, role="data", max_w=w, max_h=60, size_max=21,
                                 size_min=15, max_lines=2, tracking=1.6)
            self._h = max(0, self._h - self._cap.height - 14)
            return min(self._h + self._cap.height + 14, budget)
        return self._h

    def draw(self, sheet, x, y, w, h):
        if not self._h:
            return
        pal = sheet.palette
        img = Image.open(self.path)
        img = cover(img, int(w), int(self._h), self.focus)
        if self.duo:
            img = duotone(img, brand.INK if not pal.is_dark else pal.bg, brand.BONE_3 if not pal.is_dark else (196, 184, 164))
        sheet.img.paste(img, (int(x), int(y)))
        sheet.draw = ImageDraw.Draw(sheet.img)
        sheet.draw.rectangle([x, y, x + w - 1, y + self._h - 1], outline=pal.rule, width=1)
        if self._cap:
            draw_fitted(sheet.draw, self._cap, x, y + self._h + 12, w, pal.fg_faint, "left", 1.6)


@dataclass
class HandMark(Block):
    """La mano, grande, como sello. Se usa donde la pieza es puro texto."""

    size: int = 260
    align: str = "left"
    soft: bool = True

    def measure(self, sheet, w, budget):
        return min(self.size, budget)

    def draw(self, sheet, x, y, w, h):
        pal = sheet.palette
        size = min(self.size, h) if h else self.size
        if size <= 8:
            return
        img = brand.hand(int(size), pal.fg if pal.is_dark else brand.INK, pal.bg)
        if self.soft:
            img = img.copy()
            alpha = img.getchannel("A").point(lambda v: int(v * 0.9))
            img.putalpha(alpha)
        px = int(x) if self.align == "left" else int(x + (w - size) / 2) if self.align == "center" else int(x + w - size)
        sheet.img.paste(img, (px, int(y)), img)
        sheet.draw = ImageDraw.Draw(sheet.img)


@dataclass
class Chips(Block):
    """Temas, como los del pie de cada nota: cajas de un filete, nada de píldoras."""

    items: list = field(default_factory=list)
    size: int = 23
    _rows: list = field(default_factory=list, init=False, repr=False)
    _row_h: int = field(default=0, init=False, repr=False)

    def measure(self, sheet, w, budget):
        if not self.items:
            return 0
        fnt = brand.font("data", sc(sheet, self.size), 500)
        self._row_h = int(sc(sheet, self.size) * 2.3)
        rows, cur, cur_w = [], [], 0
        for raw in self.items:
            label = f"#{str(raw).strip().lstrip('#')}"
            cw = int(text_width(fnt, label.upper(), 2.0) + 34)
            if cur and cur_w + cw > w:
                rows.append(cur)
                cur, cur_w = [], 0
            cur.append((label, cw))
            cur_w += cw + 12
        if cur:
            rows.append(cur)
        max_rows = max(1, budget // (self._row_h + 12))
        self._rows = rows[:max_rows]
        return min(len(self._rows) * (self._row_h + 12) - 12, budget)

    def draw(self, sheet, x, y, w, h):
        pal = sheet.palette
        fnt = brand.font("data", sc(sheet, self.size), 500)
        cy = y
        for row in self._rows:
            cx = x
            for label, cw in row:
                sheet.draw.rectangle([cx, cy, cx + cw, cy + self._row_h], outline=pal.rule, width=1)
                draw_tracked(sheet.draw, (cx, cy + self._row_h * 0.28), label.upper(), fnt, pal.fg_faint, 2.0, "center", cw, role="data")
                cx += cw + 12
            cy += self._row_h + 12
