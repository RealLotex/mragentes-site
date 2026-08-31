"""
La marca, en código.

Los valores no se inventaron acá: son los mismos tokens de `assets/css/main.css`
y las mismas tres tipografías autoalojadas en `static/fonts/`. Si el sitio cambia
de tinta, esto se actualiza en un solo lugar y todas las piezas siguen.

La marca es la mano grabada (`static/faviconhand512.png`), igual que en el
masthead del sitio.
"""

from __future__ import annotations

import functools
import unicodedata
from pathlib import Path

from PIL import Image, ImageFont

from .config import BASE_DIR, CACHE_DIR

# ── 01 · Tinta y papel ──────────────────────────────────────────────────────
INK = (23, 19, 14)          # --ink       #17130e
INK_70 = (74, 65, 54)       # --ink-70    #4a4136
INK_55 = (107, 96, 82)      # --ink-55    #6b6052
BONE = (241, 235, 222)      # --bone      #f1ebde
BONE_2 = (232, 224, 207)    # --bone-2    #e8e0cf
BONE_3 = (221, 210, 187)    # --bone-3    #ddd2bb
MINIO = (168, 57, 27)       # --minio     #a8391b
MINIO_INK = (138, 45, 19)   # --minio-ink #8a2d13

# Filetes (el CSS los define con alfa sobre papel; acá van ya resueltos)
RULE = (198, 189, 174)
RULE_MID = (160, 150, 133)
RULE_INK = (52, 45, 36)

# ── 02 · Tipografías ────────────────────────────────────────────────────────
FONT_DIR = BASE_DIR / "static" / "fonts"
FONT_FILES = {
    "display": "archivo-normal-latin.woff2",     # Archivo, Omnibus-Type
    "text": "alegreya-normal-latin.woff2",       # Alegreya, Huerta Tipográfica
    "italic": "alegreya-italic-latin.woff2",
    "data": "chivomono-normal-latin.woff2",      # Chivo Mono, Omnibus-Type
}
# Ejes variables de cada familia, en el orden que espera FreeType.
FONT_AXES = {
    "display": ("wght", "wdth"),
    "text": ("wght",),
    "italic": ("wght",),
    "data": ("wght",),
}

# Firma
LOGO_HAND = BASE_DIR / "static" / "faviconhand512.png"
SITE_HOST = "mragentes.com.ar"
HANDLE = "@mragentes"
# Todas las piezas, incluso las de contenido diario, terminan con la misma
# invitación a compartir. La flecha usa «» porque las fuentes de la marca no
# contienen el glifo ↗; así evitamos que el CTA se convierta en un cuadrado.
SOCIAL_SHARE_CTA = "Enviaselo » a alguien que le pueda servir"


class FontUnavailable(RuntimeError):
    pass


@functools.lru_cache(maxsize=8)
def _ttf_path(role: str) -> Path:
    """Convierte el WOFF2 del sitio a TTF (Pillow no lee WOFF2) y lo cachea.

    Usar el mismo archivo que sirve la web no es capricho: garantiza que el
    posteo y la página estén compuestos con exactamente la misma letra, con
    los mismos subconjuntos y los mismos ejes variables.
    """
    src = FONT_DIR / FONT_FILES[role]
    if not src.exists():
        raise FontUnavailable(f"Falta la fuente {src}")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dst = CACHE_DIR / (src.stem + ".ttf")
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return dst

    try:
        from fontTools.ttLib import TTFont
    except ImportError as exc:  # pragma: no cover
        raise FontUnavailable(
            "Falta fonttools. Instalá: pip install -r scripts/requirements.txt"
        ) from exc

    font = TTFont(str(src))
    font.flavor = None
    font.save(str(dst))
    return dst


@functools.lru_cache(maxsize=512)
def font(role: str = "display", size: int = 48, weight: int = 400, width: int = 100) -> ImageFont.FreeTypeFont:
    """Instancia de fuente lista para dibujar, con el peso pedido.

    Las tres familias son variables: en vez de sintetizar negritas (que
    engordan feo), se mueve el eje wght como hace el navegador.
    """
    size = max(6, int(size))
    ft = ImageFont.truetype(str(_ttf_path(role)), size)
    axes = FONT_AXES.get(role, ())
    if not axes:
        return ft
    values = []
    for axis in axes:
        values.append(weight if axis == "wght" else width)
    try:
        ft.set_variation_by_axes(values)
    except Exception:  # pragma: no cover — build de Pillow sin variaciones
        pass
    return ft


# ── 03 · Cobertura de glifos ────────────────────────────────────────────────
# Las fuentes del sitio son subconjuntos latinos: tienen todo el castellano, pero
# no tienen flechas ni palomitas. Un carácter que la fuente no dibuja sale como
# un rectángulo vacío — el "cuadradito" que arruinaba los posteos viejos. Se
# reemplaza por su equivalente tipográfico antes de dibujar, nunca después.

FALLBACKS = {
    "→": "»", "←": "«", "↗": "»", "↘": "»", "⟶": "»", "➜": "»", "▶": "»",
    "•": "·", "●": "·", "◦": "·", "‣": "·",
    "✓": "·", "✔": "·", "✅": "·", "☑": "·",
    "✗": "x", "✘": "x", "❌": "x", "×": "x",
    "≥": ">=", "≤": "<=", "≈": "~", "≠": "!=",
    "™": "", "®": "", "©": "(c)", "→": "»",
    " ": " ", " ": " ", " ": " ", "️": "",
}


@functools.lru_cache(maxsize=8)
def supported_codepoints(role: str) -> frozenset[int]:
    try:
        from fontTools.ttLib import TTFont
    except ImportError:  # pragma: no cover
        return frozenset()
    try:
        return frozenset(TTFont(str(_ttf_path(role))).getBestCmap().keys())
    except Exception:  # pragma: no cover
        return frozenset()


def sanitize(text: str, role: str = "display") -> str:
    """Deja sólo lo que la fuente sabe dibujar."""
    if not text:
        return ""
    ok = supported_codepoints(role)
    if not ok:
        return text
    out = []
    for ch in text:
        if ord(ch) in ok:
            out.append(ch)
            continue
        repl = FALLBACKS.get(ch)
        if repl is None:
            # Último intento: descomponer (é → e) antes de descartar.
            repl = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))
        for c in repl:
            if ord(c) in ok:
                out.append(c)
    return "".join(out)


# ── 04 · Firma ──────────────────────────────────────────────────────────────
@functools.lru_cache(maxsize=32)
def hand(size: int, ink: tuple[int, int, int] = INK, paper: tuple[int, int, int] = BONE) -> Image.Image:
    """La mano grabada, retintada para el fondo sobre el que va.

    El PNG original es negro puro + crema. Sobre papel hueso se lee tal cual;
    sobre tinta hay que invertir los dos tonos o desaparece.
    """
    src = Image.open(LOGO_HAND).convert("RGBA")
    src = src.resize((size, size), Image.LANCZOS)
    r, g, b, a = src.split()
    # Luminancia del original: 0 = trazo, 255 = relleno.
    lum = Image.merge("RGB", (r, g, b)).convert("L")
    out = Image.new("RGBA", src.size)
    px_l = lum.load()
    px_a = a.load()
    px_o = out.load()
    for y in range(size):
        for x in range(size):
            t = px_l[x, y] / 255.0
            px_o[x, y] = (
                int(ink[0] + (paper[0] - ink[0]) * t),
                int(ink[1] + (paper[1] - ink[1]) * t),
                int(ink[2] + (paper[2] - ink[2]) * t),
                px_a[x, y],
            )
    return out


# ── 05 · Paletas por fondo ──────────────────────────────────────────────────
class Palette:
    """Los mismos tokens, resueltos según sobre qué se imprime."""

    def __init__(self, ground: str = "paper"):
        if ground not in {"paper", "ink", "minio"}:
            raise ValueError(f"Fondo/palette desconocido: {ground!r}")
        self.ground = ground
        if ground == "ink":
            self.bg = INK
            self.bg_alt = (34, 29, 22)
            self.fg = BONE
            self.fg_soft = (196, 186, 168)
            self.fg_faint = (146, 136, 120)
            self.accent = (214, 106, 68)   # minio aclarado para leer sobre tinta
            self.rule = (86, 76, 62)
            self.rule_strong = (140, 128, 110)
            self.panel = (32, 27, 20)
        elif ground == "minio":
            self.bg = MINIO_INK
            self.bg_alt = (120, 39, 16)
            self.fg = BONE
            self.fg_soft = (238, 214, 200)
            self.fg_faint = (216, 178, 160)
            self.accent = BONE
            self.rule = (176, 105, 82)
            self.rule_strong = (222, 190, 176)
            self.panel = (118, 38, 16)
        else:  # paper
            self.bg = BONE
            self.bg_alt = BONE_2
            self.fg = INK
            self.fg_soft = INK_70
            self.fg_faint = INK_55
            self.accent = MINIO
            self.rule = RULE
            self.rule_strong = RULE_MID
            self.panel = BONE_2

    @property
    def is_dark(self) -> bool:
        return self.ground in {"ink", "minio"}
