"""
La lámina: superficie, papel, filetes y composición de texto.

Dos reglas que este módulo garantiza por construcción, porque son los dos
errores que arruinaban las piezas viejas:

  1. **Nada se estira.** Toda foto entra por `cover()`, que escala respetando
     la proporción y recorta lo que sobra. Una historia 9:16 nunca es un
     cuadrado deformado: se compone nativa a 1080×1920.

  2. **Nada se desborda.** El texto no se dibuja con un cuerpo fijo y a ver
     qué pasa: `fit_text()` busca el cuerpo más grande que entra en la caja
     y, si ni el mínimo entra, corta con puntos suspensivos. Los bloques
     miden contra el presupuesto de alto que les queda, así que la suma
     nunca puede pasarse del área de contenido.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from . import brand
from .brand import Palette

# ── Superficies ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Surface:
    key: str
    w: int
    h: int
    margin: int
    safe_top: int = 0
    safe_bottom: int = 0
    label: str = ""
    # Las historias se miran de lejos y por dos segundos: la misma composición
    # pide un cuerpo mayor. No es "estirar", es componer para el formato.
    type_scale: float = 1.0

    @property
    def ratio(self) -> float:
        return self.w / self.h


FEED = Surface("feed", 1080, 1080, 78, label="Instagram / Facebook · 1:1")
PORTRAIT = Surface("portrait", 1080, 1350, 84, label="Instagram feed · 4:5", type_scale=1.06)
STORY = Surface("story", 1080, 1920, 92, safe_top=176, safe_bottom=252,
                label="Historias · 9:16", type_scale=1.34)

SURFACES = {s.key: s for s in (FEED, PORTRAIT, STORY)}


def surface(key: str) -> Surface:
    if key not in SURFACES:
        raise KeyError(f"Superficie desconocida: {key}. Hay {sorted(SURFACES)}")
    return SURFACES[key]


# ── Texto ───────────────────────────────────────────────────────────────────

# Interlineado por familia. El serif necesita más aire que el palo seco.
LEADING = {"display": 1.10, "text": 1.34, "italic": 1.34, "data": 1.42}


def text_width(fnt, text: str, tracking: float = 0.0) -> float:
    if not text:
        return 0.0
    base = fnt.getlength(text)
    if tracking:
        base += tracking * (len(text) - 1)
    return base


def wrap_text(text: str, fnt, max_w: float, tracking: float = 0.0, role: str | None = None) -> list[str]:
    """Corta por palabras; una palabra más ancha que la caja se parte a la fuerza."""
    if role:
        text = brand.sanitize(text, role)
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = ""
        for word in words:
            probe = f"{current} {word}".strip()
            if text_width(fnt, probe, tracking) <= max_w or not current:
                if text_width(fnt, probe, tracking) <= max_w:
                    current = probe
                    continue
                # Palabra sola que no entra: partirla.
                chunk = ""
                for ch in word:
                    if text_width(fnt, chunk + ch, tracking) <= max_w or not chunk:
                        chunk += ch
                    else:
                        lines.append(chunk)
                        chunk = ch
                current = chunk
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


@dataclass
class FittedText:
    lines: list[str]
    font: object
    size: int
    line_h: int
    height: int
    truncated: bool = False

    @property
    def is_empty(self) -> bool:
        return not any(line.strip() for line in self.lines)


def fit_text(
    text: str,
    *,
    role: str = "display",
    weight: int = 400,
    width: int = 100,
    max_w: float,
    max_h: float,
    size_max: int = 120,
    size_min: int = 20,
    max_lines: int = 6,
    leading: float | None = None,
    tracking: float = 0.0,
) -> FittedText:
    """El cuerpo más grande que entra en la caja. Si no entra ni el mínimo, corta."""
    if not math.isfinite(max_w) or max_w <= 0 or not math.isfinite(max_h) or max_h < 0:
        raise ValueError("Las dimensiones max_w/max_h deben ser finitas y utilizables")
    if (
        isinstance(size_min, bool)
        or isinstance(size_max, bool)
        or size_min <= 0
        or size_max <= 0
        or size_min > size_max
    ):
        raise ValueError("El rango de tamaño exige 0 < size_min <= size_max")
    if isinstance(max_lines, bool) or max_lines < 1:
        raise ValueError("max_lines debe ser un entero positivo")
    text = brand.sanitize((text or "").strip(), role)
    lead = leading if leading is not None else LEADING.get(role, 1.2)
    if not text:
        return FittedText([], brand.font(role, size_min, weight, width), size_min, 0, 0)

    size_max = max(size_min, int(size_max))
    best: FittedText | None = None
    lo, hi = size_min, size_max
    while lo <= hi:
        mid = (lo + hi) // 2
        fnt = brand.font(role, mid, weight, width)
        lines = wrap_text(text, fnt, max_w, tracking)
        line_h = max(1, int(round(mid * lead)))
        height = line_h * len(lines)
        if len(lines) <= max_lines and height <= max_h:
            best = FittedText(lines, fnt, mid, line_h, height)
            lo = mid + 1
        else:
            hi = mid - 1

    if best is not None:
        return best

    # Ni el cuerpo mínimo entra: se recorta con elipsis antes que desbordar.
    fnt = brand.font(role, size_min, weight, width)
    line_h = max(1, int(round(size_min * lead)))
    allowed = min(max_lines, int(max_h // line_h))
    if allowed < 1:
        # No entra ni un renglón: mejor no dibujar nada que pisar lo de al lado.
        return FittedText([], fnt, size_min, line_h, 0, truncated=True)
    lines = wrap_text(text, fnt, max_w, tracking)
    if len(lines) > allowed:
        lines = lines[:allowed]
        last = lines[-1].rstrip()
        while last and text_width(fnt, last + "…", tracking) > max_w:
            last = last[:-1].rstrip()
        lines[-1] = (last + "…") if last else "…"
        return FittedText(lines, fnt, size_min, line_h, line_h * len(lines), truncated=True)
    return FittedText(lines, fnt, size_min, line_h, line_h * len(lines))


# ── Dibujo ──────────────────────────────────────────────────────────────────


def draw_tracked(draw: ImageDraw.ImageDraw, xy, text: str, fnt, fill, tracking: float = 0.0, align: str = "left", box_w: float | None = None, role: str | None = None):
    """Dibuja una línea con prosa normal o con letra espaciada.

    Sin tracking se delega en Pillow (respeta el kerning de la fuente). Con
    tracking hay que ir carácter por carácter — se usa sólo en claves y
    etiquetas en versalitas, donde el espaciado es parte del estilo.
    """
    x, y = xy
    if role:
        text = brand.sanitize(text, role)
    if not text:
        return
    if not tracking:
        w = fnt.getlength(text)
        if align == "center" and box_w:
            x += (box_w - w) / 2
        elif align == "right" and box_w:
            x += box_w - w
        draw.text((x, y), text, font=fnt, fill=fill, anchor="la")
        return

    total = text_width(fnt, text, tracking)
    if align == "center" and box_w:
        x += (box_w - total) / 2
    elif align == "right" and box_w:
        x += box_w - total
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill, anchor="la")
        x += fnt.getlength(ch) + tracking


def draw_fitted(draw, fitted: FittedText, x: float, y: float, box_w: float, fill, align: str = "left", tracking: float = 0.0) -> float:
    for i, line in enumerate(fitted.lines):
        draw_tracked(draw, (x, y + i * fitted.line_h), line, fitted.font, fill, tracking, align, box_w)
    return y + fitted.height


# ── Fotografía ──────────────────────────────────────────────────────────────


def cover(img: Image.Image, w: int, h: int, focus: tuple[float, float] = (0.5, 0.42)) -> Image.Image:
    """Escala manteniendo proporción y recorta. Jamás deforma."""
    if w <= 0 or h <= 0:
        raise ValueError("Las dimensiones de cover deben ser positivas")
    if (
        not isinstance(focus, tuple)
        or len(focus) != 2
        or any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in focus)
        or any(not math.isfinite(float(value)) or not 0 <= float(value) <= 1 for value in focus)
    ):
        raise ValueError("El foco debe contener dos coordenadas entre 0 y 1")
    img = img.convert("RGB")
    src_w, src_h = img.size
    scale = max(w / src_w, h / src_h)
    new = (max(1, int(math.ceil(src_w * scale))), max(1, int(math.ceil(src_h * scale))))
    img = img.resize(new, Image.LANCZOS)
    max_x = max(0, new[0] - w)
    max_y = max(0, new[1] - h)
    left = int(max_x * focus[0])
    top = int(max_y * focus[1])
    return img.crop((left, top, left + w, top + h))


def duotone(img: Image.Image, dark: tuple[int, int, int], light: tuple[int, int, int], contrast: float = 1.12) -> Image.Image:
    """Foto llevada a los dos tonos de la marca: parece lámina impresa, no stock."""
    gray = ImageOps.grayscale(img)
    gray = ImageEnhance.Contrast(gray).enhance(contrast)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    return ImageOps.colorize(gray, black=dark, white=light)


def grain(img: Image.Image, amount: int = 7, seed: int = 0) -> Image.Image:
    """Grano de papel. Poco: apenas rompe el plano digital."""
    if amount <= 0:
        return img
    rnd = random.Random(seed)
    w, h = img.size
    small = Image.new("L", (max(1, w // 2), max(1, h // 2)))
    small.putdata([128 + rnd.randint(-amount, amount) for _ in range(small.width * small.height)])
    noise = small.resize(img.size, Image.BILINEAR).filter(ImageFilter.GaussianBlur(0.4))
    return ImageChops.overlay(img, Image.merge("RGB", (noise, noise, noise)))


def scrim(img: Image.Image, color: tuple[int, int, int], alpha: float, box=None, direction: str | None = None) -> Image.Image:
    """Velo plano o degradado para que el texto tenga contraste sobre la foto."""
    box = box or (0, 0, img.width, img.height)
    x0, y0, x1, y1 = box
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    layer = Image.new("RGB", (w, h), color)
    if direction in {"up", "down"}:
        mask = Image.new("L", (1, h))
        for i in range(h):
            t = i / max(1, h - 1)
            v = t if direction == "down" else 1 - t
            mask.putpixel((0, i), int(255 * alpha * (v ** 1.35)))
        mask = mask.resize((w, h))
    else:
        mask = Image.new("L", (w, h), int(255 * alpha))
    base = img.copy()
    base.paste(layer, (x0, y0), mask)
    return base


# ── La lámina ───────────────────────────────────────────────────────────────


class Sheet:
    """Una pieza: papel, cabecera, pie y el área de contenido en el medio."""

    def __init__(
        self,
        surf: Surface,
        ground: str = "paper",
        photo: Path | str | None = None,
        photo_focus: tuple[float, float] = (0.5, 0.42),
        seed: int | str = 0,
        ruled: bool = False,
    ):
        self.surface = surf
        self.palette = Palette(ground)
        self.seed = seed if isinstance(seed, int) else int(hashlib.sha1(str(seed).encode()).hexdigest()[:8], 16)
        self.ground = ground
        self.photo_path = Path(photo) if photo else None
        self.photo_focus = photo_focus
        self.ruled = ruled

        self.img = Image.new("RGB", (surf.w, surf.h), self.palette.bg)
        self._paint_ground()
        self.draw = ImageDraw.Draw(self.img)

        self._header_bottom = surf.safe_top + surf.margin
        self._footer_top = surf.h - surf.safe_bottom - surf.margin

    # ── Fondo ───────────────────────────────────────────────────────────
    def _paint_ground(self):
        s = self.surface
        pal = self.palette
        if self.photo_path and self.photo_path.exists():
            base = Image.open(self.photo_path)
            base = cover(base, s.w, s.h, self.photo_focus)
            dark = pal.bg if pal.is_dark else brand.INK
            light = brand.BONE_3 if not pal.is_dark else (198, 186, 166)
            base = duotone(base, dark, light)
            self.img = grain(base, 6, self.seed)
        else:
            self.img = grain(self.img, 5, self.seed)
            if self.ruled:
                self._paint_rules()

    @property
    def frame_inset(self) -> int:
        return 34 if self.surface.key != "story" else 44

    def _paint_rules(self):
        """Papel reglado, como la hoja de especificación del sitio.

        Las líneas mueren en el filete de la lámina: si se escaparan al borde
        del lienzo, el marco dejaría de leerse como el borde de la hoja.
        """
        d = ImageDraw.Draw(self.img)
        step = 60
        inset = self.frame_inset
        col = tuple(
            int(a + (b - a) * 0.35)
            for a, b in zip(self.palette.bg, self.palette.rule)
        )
        for y in range(inset + step, self.surface.h - inset, step):
            d.line([(inset + 1, y), (self.surface.w - inset - 1, y)], fill=col, width=1)

    # ── Utilidades de pintura ───────────────────────────────────────────
    def veil(self, alpha: float = 0.55, color=None, box=None, direction=None):
        color = color or self.palette.bg
        self.img = scrim(self.img, color, alpha, box, direction)
        self.draw = ImageDraw.Draw(self.img)

    def panel(self, box, fill=None, border=None, radius: int = 0):
        fill = self.palette.bg if fill is None else fill
        self.draw.rectangle(box, fill=fill, outline=border, width=1 if border else 0)

    def rule(self, x0, y, x1, color=None, width=1):
        self.draw.line([(x0, y), (x1, y)], fill=color or self.palette.rule, width=width)

    def vrule(self, x, y0, y1, color=None, width=1):
        self.draw.line([(x, y0), (x, y1)], fill=color or self.palette.rule, width=width)

    # ── Cabecera y pie ──────────────────────────────────────────────────
    def signature(self, x: int, y: int, logo: int = 56):
        """La firma del masthead, al pie de la letra: mano + MR en negrita y
        «Agentes» en regular más claro (.signature-name span en el CSS)."""
        pal = self.palette
        hand = brand.hand(logo, pal.fg if pal.is_dark else brand.INK, pal.bg if pal.is_dark else brand.BONE)
        self.img.paste(hand, (x, y), hand)
        self.draw = ImageDraw.Draw(self.img)

        size = int(logo * 0.62)
        tx = x + logo + int(logo * 0.34)
        ty = y + (logo - size) / 2 - size * 0.12
        bold = brand.font("display", size, 700, 112)
        light = brand.font("display", size, 400, 100)
        self.draw.text((tx, ty), "MR ", font=bold, fill=pal.fg, anchor="la")
        self.draw.text((tx + bold.getlength("MR "), ty), "Agentes", font=light, fill=pal.fg_faint, anchor="la")

    def chrome(self, section: str = "", meta: str = "", footer_right: str | None = None, frame: bool = True):
        """Firma arriba, filete abajo. Igual que el masthead y el colofón del sitio."""
        s, pal = self.surface, self.palette
        m = s.margin
        top = s.safe_top + m

        if frame:
            inset = self.frame_inset
            self.draw.rectangle([inset, inset, s.w - inset, s.h - inset], outline=pal.rule, width=1)

        logo = 56 if s.key != "story" else 64
        self.signature(m, top, logo)

        if section:
            lab = brand.font("data", 23, 500)
            draw_tracked(
                self.draw,
                (m, top + logo * 0.24),
                section.upper(),
                lab,
                pal.accent,
                tracking=4.5,
                align="right",
                box_w=s.w - 2 * m,
                role="data",
            )
            if meta:
                draw_tracked(
                    self.draw,
                    (m, top + logo * 0.24 + 30),
                    meta.upper(),
                    brand.font("data", 20, 400),
                    pal.fg_faint,
                    tracking=3.2,
                    align="right",
                    box_w=s.w - 2 * m,
                    role="data",
                )

        rule_y = top + logo + 26
        self.rule(m, rule_y, s.w - m, pal.rule)
        self._header_bottom = rule_y

        foot_rule = s.h - s.safe_bottom - m - 46
        self.rule(m, foot_rule, s.w - m, pal.rule)
        foot_font = brand.font("data", 22, 500)
        draw_tracked(self.draw, (m, foot_rule + 14), brand.SITE_HOST, foot_font, pal.fg_soft, tracking=2.4, role="data")
        draw_tracked(
            self.draw,
            (m, foot_rule + 14),
            (footer_right if footer_right is not None else brand.HANDLE),
            foot_font,
            pal.fg_faint,
            tracking=2.4,
            align="right",
            box_w=s.w - 2 * m,
            role="data",
        )
        self._footer_top = foot_rule

    # ── Área de contenido ───────────────────────────────────────────────
    @property
    def content_box(self) -> tuple[int, int, int, int]:
        s = self.surface
        gap_top = 54 if s.key != "story" else 74
        gap_bottom = 44 if s.key != "story" else 64
        return (s.margin, self._header_bottom + gap_top, s.w - s.margin, self._footer_top - gap_bottom)

    @property
    def content_w(self) -> int:
        x0, _, x1, _ = self.content_box
        return x1 - x0

    @property
    def content_h(self) -> int:
        _, y0, _, y1 = self.content_box
        return y1 - y0

    def save(self, path: Path, quality: int = 86) -> Path:
        """Guarda la pieza.

        Instagram y Facebook recomprimen todo lo que subís, así que guardar a
        calidad 92 sólo engorda el repositorio: la red se queda con su propia
        versión igual. Con 86 no se ve la diferencia y pesa un tercio menos.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() in {".jpg", ".jpeg"}:
            self.img.convert("RGB").save(path, "JPEG", quality=quality, optimize=True,
                                         progressive=True, subsampling=2)
        else:
            self.img.save(path)
        return path
