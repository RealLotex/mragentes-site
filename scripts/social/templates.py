"""
Plantillas de contenido.

Quince composiciones distintas, cada una pensada para un tipo de mensaje, y
cada una resuelta nativamente para las tres superficies (1:1, 4:5 y 9:16).
Ninguna es un reencuadre de otra: la historia no es el cuadrado estirado, se
compone aparte con la misma gramática.

La variedad sale de tres perillas que rotan solas:
  · la plantilla (quince)
  · el fondo — papel, papel reglado, tinta, minio, o la foto de la nota
  · el orden de los ganchos y los cierres en el texto (ver copy.py)

Para agregar una plantilla: escribir la función, sumarla a TEMPLATES y listo;
el CLI, la galería y el rotador la toman automáticamente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import brand
from .blocks import (
    Body,
    Chips,
    Columns,
    Flex,
    Gap,
    HandMark,
    Heading,
    KeyValues,
    Kicker,
    Ledger,
    Mono,
    Panel,
    PhotoBand,
    Quote,
    Rule,
    Stat,
    Steps,
    stack,
)
from .canvas import Sheet, Surface, surface


# ── Contenido ───────────────────────────────────────────────────────────────


@dataclass
class Piece:
    """Lo que una pieza necesita saber. Todo opcional salvo el título."""

    title: str = ""
    kicker: str = ""
    lead: str = ""
    items: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    stat: str = ""
    unit: str = ""
    caption: str = ""
    quote: str = ""
    author: str = ""
    photo: str | Path | None = None
    tags: list = field(default_factory=list)
    cta: str = ""
    meta: str = ""
    section: str = ""
    footer_right: str = ""
    url: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Piece":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


# ── Andamiaje común ─────────────────────────────────────────────────────────

GROUNDS = ("paper", "ruled", "ink", "minio")


def _new_sheet(
    surf: Surface,
    ground: str,
    seed: int,
    photo: str | Path | None = None,
    section: str = "",
    meta: str = "",
    footer_right: str | None = None,
    frame: bool = True,
) -> Sheet:
    ruled = ground == "ruled"
    base = "paper" if ground in {"paper", "ruled"} else ground
    sh = Sheet(surf, ground=base, photo=photo, seed=seed, ruled=ruled)
    if photo:
        # Foto de fondo: velo plano para bajar el ruido + degradado desde abajo
        # para que el titular apoye sobre algo sólido sin tapar la imagen.
        sh.veil(0.34, sh.palette.bg)
        sh.veil(0.86, sh.palette.bg, direction="up")
    sh.chrome(section=section, meta=meta, footer_right=footer_right, frame=frame and not photo)
    return sh


def _label(piece: Piece, default: str) -> str:
    return (piece.section or default).strip()


# ── Plantillas ──────────────────────────────────────────────────────────────


def t_nota(piece: Piece, surf: Surface, seed: int, ground: str) -> Sheet:
    """01 · Aviso de nota nueva. Usa la imagen de la nota como fondo."""
    photo = piece.photo if piece.photo and Path(piece.photo).exists() else None
    # Con foto de portada, priorizar el fondo completo (la identidad visual de la
    # nota es la imagen). Sin foto, cae a la variante con banda tipográfica.
    band = not photo or (surf.key == "story" and photo)

    if photo and not band:
        sh = _new_sheet(surf, "ink", seed, photo=photo, section=_label(piece, "nota nueva"),
                        meta=piece.meta, footer_right=piece.footer_right or "leé la nota »")
        blocks = [
            Flex(1),
            Kicker(piece.kicker or "análisis"),
            Gap(10),
            Heading(piece.title, frac=0.5, size_max=104, max_lines=5),
            Rule(accent=True, frac=0.22, pad_top=26, pad_bottom=24, thickness=3),
            Body(piece.lead, frac=0.22, max_lines=4, size_max=40),
            Gap(20),
            Chips(piece.tags[:4]),
        ]
    else:
        sh = _new_sheet(surf, ground if ground != "ink" else "paper", seed,
                        section=_label(piece, "nota nueva"), meta=piece.meta,
                        footer_right=piece.footer_right or "leé la nota »")
        blocks = [
            PhotoBand(photo, frac=0.36 if surf.key != "story" else 0.32) if photo else Gap(0),
            Gap(32),
            Kicker(piece.kicker or "análisis"),
            Gap(8),
            Heading(piece.title, frac=0.36, size_max=86, max_lines=5),
            Rule(accent=True, frac=0.18, pad_top=22, pad_bottom=20, thickness=3),
            Body(piece.lead, frac=0.24, max_lines=4, size_max=42),
            Flex(1),
            Gap(18),
            Chips(piece.tags[:4]),
        ]
    stack(sh, blocks)
    return sh


def t_titular(piece: Piece, surf: Surface, seed: int, ground: str) -> Sheet:
    """02 · Titular a toda página. Una idea, en grande, sin adornos."""
    sh = _new_sheet(surf, ground, seed, section=_label(piece, "apunte"), meta=piece.meta,
                    footer_right=piece.footer_right or brand.HANDLE)
    stack(sh, [
        Kicker(piece.kicker or "para pensar"),
        Gap(18),
        Rule(frac=0.14, thickness=3, accent=True, pad_top=0, pad_bottom=30),
        Heading(piece.title, frac=0.62, size_max=132, max_lines=6),
        Gap(26),
        Body(piece.lead, frac=0.26, max_lines=5),
        Flex(1),
        Mono(piece.cta or "Automatización y agentes de IA para pymes · Gálvez, Santa Fe", size=24),
    ])
    return sh


def t_dato(piece: Piece, surf: Surface, seed: int, ground: str) -> Sheet:
    """03 · Un número solo, con su fuente. Nada convence más que un dato."""
    sh = _new_sheet(surf, ground, seed, section=_label(piece, "el dato"), meta=piece.meta,
                    footer_right=piece.footer_right or brand.HANDLE)
    stack(sh, [
        Kicker(piece.kicker or "el número de la semana"),
        Flex(1),
        Stat(piece.stat or piece.title, unit=piece.unit, caption=piece.caption or piece.title, frac=0.55),
        Rule(pad_top=34, pad_bottom=26),
        Body(piece.lead, frac=0.26, max_lines=5),
        Flex(1),
        Mono(piece.author or piece.cta or "Fuente: elaboración propia", size=23),
    ])
    return sh


def t_cita(piece: Piece, surf: Surface, seed: int, ground: str) -> Sheet:
    """04 · Cita. Alegreya en bastardilla, comilla colgada en minio."""
    sh = _new_sheet(surf, ground, seed, section=_label(piece, "cita"), meta=piece.meta,
                    footer_right=piece.footer_right or brand.HANDLE)
    stack(sh, [
        Flex(1),
        Quote(piece.quote or piece.title, author=piece.author, frac=0.72),
        Flex(1),
        Body(piece.lead, frac=0.2, max_lines=4, size_max=34),
    ])
    return sh


def t_lista(piece: Piece, surf: Surface, seed: int, ground: str) -> Sheet:
    """05 · Lista reglada numerada. Sin viñetas, sin tarjetas."""
    sh = _new_sheet(surf, ground, seed, section=_label(piece, "lista"), meta=piece.meta,
                    footer_right=piece.footer_right or brand.HANDLE)
    stack(sh, [
        Kicker(piece.kicker or "para tener a mano"),
        Gap(12),
        Heading(piece.title, frac=0.24, size_max=76, max_lines=3),
        Rule(pad_top=26, pad_bottom=30),
        Ledger(items=piece.items),
        Flex(1),
        Mono(piece.cta or "Escribinos y lo vemos en tu empresa", size=24),
    ])
    return sh


def t_mito(piece: Piece, surf: Surface, seed: int, ground: str) -> Sheet:
    """06 · Mito y verdad, en dos paños separados por un filete."""
    sh = _new_sheet(surf, ground if ground != "ink" else "paper", seed,
                    section=_label(piece, "mito y verdad"), meta=piece.meta,
                    footer_right=piece.footer_right or brand.HANDLE)
    mito = piece.items[0] if piece.items else ""
    verdad = piece.items[1] if len(piece.items) > 1 else ""
    mito_txt = mito[1] if isinstance(mito, (tuple, list)) else mito
    verdad_txt = verdad[1] if isinstance(verdad, (tuple, list)) else verdad
    stack(sh, [
        Heading(piece.title, frac=0.2, size_max=68, max_lines=3),
        Rule(pad_top=22, pad_bottom=28),
        Columns(cols=[
            [Kicker("mito", color=sh.palette.fg_faint), Gap(14),
             Body(str(mito_txt), frac=0.3, max_lines=8, size_max=40, color=sh.palette.fg_soft)],
            [Kicker("verdad"), Gap(14),
             Body(str(verdad_txt), frac=0.34, max_lines=9, size_max=42, color=sh.palette.fg)],
        ], ratios=[1, 1], gap=44),
        Flex(1),
        Mono(piece.cta or "Lo charlamos sin vueltas: mragentes.com.ar/contacto", size=23),
    ])
    return sh


def t_comparativa(piece: Piece, surf: Surface, seed: int, ground: str) -> Sheet:
    """07 · Antes y después: dos columnas de la misma operación."""
    sh = _new_sheet(surf, ground, seed, section=_label(piece, "antes y después"), meta=piece.meta,
                    footer_right=piece.footer_right or brand.HANDLE)
    antes = [i for i in piece.items[: len(piece.items) // 2]] if piece.items else []
    despues = [i for i in piece.items[len(piece.items) // 2:]] if piece.items else []
    if piece.rows:
        antes = [r[0] for r in piece.rows]
        despues = [r[1] for r in piece.rows]
    stack(sh, [
        Kicker(piece.kicker or "el mismo proceso, dos veces"),
        Gap(12),
        Heading(piece.title, frac=0.2, size_max=72, max_lines=3),
        Rule(pad_top=24, pad_bottom=28),
        Columns(cols=[
            [Kicker("antes", color=sh.palette.fg_faint), Gap(16),
             Ledger(items=antes, numbered=False, marker="—")],
            [Kicker("después"), Gap(16),
             Ledger(items=despues, numbered=False, marker="»")],
        ], ratios=[1, 1], gap=40),
        Flex(1),
        Mono(piece.cta or "Diagnóstico sin cargo · mragentes.com.ar", size=23),
    ])
    return sh


def t_ficha(piece: Piece, surf: Surface, seed: int, ground: str) -> Sheet:
    """08 · Hoja de especificación, igual que el shortcode `ficha` del sitio."""
    sh = _new_sheet(surf, ground, seed, section=_label(piece, "ficha técnica"), meta=piece.meta,
                    footer_right=piece.footer_right or brand.HANDLE)
    stack(sh, [
        Kicker(piece.kicker or "servicio"),
        Gap(12),
        Heading(piece.title, frac=0.22, size_max=76, max_lines=3),
        Body(piece.lead, frac=0.14, max_lines=3, size_max=34),
        Rule(pad_top=24, pad_bottom=8),
        KeyValues(rows=piece.rows or [(str(i[0]), str(i[1])) for i in piece.items if isinstance(i, (tuple, list))]),
        Flex(1),
        Mono(piece.cta or "Pedí la ficha completa por WhatsApp", size=24),
    ])
    return sh


def t_pasos(piece: Piece, surf: Surface, seed: int, ground: str) -> Sheet:
    """09 · Proceso en pasos, encadenados por una vertical."""
    sh = _new_sheet(surf, ground, seed, section=_label(piece, "paso a paso"), meta=piece.meta,
                    footer_right=piece.footer_right or brand.HANDLE)
    stack(sh, [
        Kicker(piece.kicker or "cómo lo hacemos"),
        Gap(12),
        Heading(piece.title, frac=0.2, size_max=72, max_lines=3),
        Rule(pad_top=22, pad_bottom=30),
        Steps(items=piece.items),
        Flex(1),
        Mono(piece.cta or "De la primera charla a producción, en semanas", size=23),
    ])
    return sh


def t_pregunta(piece: Piece, surf: Surface, seed: int, ground: str) -> Sheet:
    """10 · Pregunta directa. La mano grande hace de sello."""
    sh = _new_sheet(surf, ground, seed, section=_label(piece, "pregunta"), meta=piece.meta,
                    footer_right=piece.footer_right or brand.HANDLE)
    stack(sh, [
        Flex(1),
        HandMark(size=200 if surf.key != "story" else 260),
        Gap(30),
        Heading(piece.title, frac=0.42, size_max=104, max_lines=5),
        Gap(22),
        Body(piece.lead, frac=0.22, max_lines=4),
        Flex(1),
        Rule(pad_top=0, pad_bottom=18),
        Mono(piece.cta or "Contanos en los comentarios", size=25, color=sh.palette.accent),
    ])
    return sh


def t_glosario(piece: Piece, surf: Surface, seed: int, ground: str) -> Sheet:
    """11 · Glosario: un término del rubro, explicado sin humo."""
    sh = _new_sheet(surf, ground, seed, section=_label(piece, "glosario"), meta=piece.meta,
                    footer_right=piece.footer_right or brand.HANDLE)
    stack(sh, [
        Kicker(piece.kicker or "diccionario mínimo de ia"),
        Gap(20),
        Heading(piece.title, frac=0.24, size_max=112, max_lines=2),
        Mono(piece.caption or "sustantivo · jerga del rubro", size=25),
        Rule(pad_top=24, pad_bottom=28),
        Body(piece.lead, frac=0.34, max_lines=9, size_max=44),
        Flex(1),
        Panel(blocks=[
            Kicker("en criollo"),
            Gap(10),
            Body(piece.quote or piece.caption or "", frac=0.18, max_lines=4, size_max=34),
        ], pad=28) if (piece.quote or piece.caption) else Gap(0),
    ])
    return sh


def t_caso(piece: Piece, surf: Surface, seed: int, ground: str) -> Sheet:
    """12 · Caso: problema, solución y resultado, con el número al final."""
    sh = _new_sheet(surf, ground, seed, section=_label(piece, "caso"), meta=piece.meta,
                    footer_right=piece.footer_right or brand.HANDLE)
    rows = piece.rows or [
        ("problema", piece.items[0] if piece.items else ""),
        ("solución", piece.items[1] if len(piece.items) > 1 else ""),
        ("resultado", piece.items[2] if len(piece.items) > 2 else ""),
    ]
    stack(sh, [
        Kicker(piece.kicker or "de la vida real"),
        Gap(12),
        Heading(piece.title, frac=0.18, size_max=68, max_lines=3),
        Rule(pad_top=22, pad_bottom=10),
        KeyValues(rows=[(k, v) for k, v in rows if v]),
        Flex(1),
        Stat(piece.stat, unit=piece.unit, caption=piece.caption, frac=0.26) if piece.stat else Gap(0),
        Gap(10),
        Mono(piece.cta or "¿Te suena parecido? Escribinos", size=24),
    ])
    return sh


def t_anuncio(piece: Piece, surf: Surface, seed: int, ground: str) -> Sheet:
    """13 · Anuncio con canales. El cierre de cualquier carrusel."""
    sh = _new_sheet(surf, "minio" if ground == "paper" and seed % 2 else ground, seed,
                    section=_label(piece, "aviso"), meta=piece.meta,
                    footer_right=piece.footer_right or brand.HANDLE)
    stack(sh, [
        Kicker(piece.kicker or "mr agentes"),
        Gap(16),
        Heading(piece.title, frac=0.36, size_max=98, max_lines=4),
        Gap(20),
        Body(piece.lead, frac=0.22, max_lines=5),
        Flex(1),
        Rule(pad_top=0, pad_bottom=22),
        KeyValues(rows=piece.rows or [
            ("web", "mragentes.com.ar"),
            ("whatsapp", "3404 50-2729"),
            ("dónde", "Gálvez, Santa Fe · remoto en todo el país"),
        ], key_frac=0.28),
    ])
    return sh


def t_agenda(piece: Piece, surf: Surface, seed: int, ground: str) -> Sheet:
    """14 · Resumen de la semana: tres o cuatro entradas con su fecha."""
    sh = _new_sheet(surf, ground, seed, section=_label(piece, "la semana"), meta=piece.meta,
                    footer_right=piece.footer_right or brand.HANDLE)
    stack(sh, [
        Kicker(piece.kicker or "lo que pasó"),
        Gap(12),
        Heading(piece.title, frac=0.2, size_max=74, max_lines=3),
        Rule(pad_top=22, pad_bottom=10),
        KeyValues(rows=piece.rows or [(str(i[0]), str(i[1])) for i in piece.items if isinstance(i, (tuple, list))],
                  key_frac=0.24),
        Flex(1),
        Mono(piece.cta or "El análisis completo, en el sitio", size=24),
    ])
    return sh


def t_punto(piece: Piece, surf: Surface, seed: int, ground: str) -> Sheet:
    """15 · Punto suelto de un carrusel: número grande, idea corta."""
    sh = _new_sheet(surf, ground, seed, section=_label(piece, "punto"), meta=piece.meta,
                    footer_right=piece.footer_right or brand.HANDLE)
    stack(sh, [
        Kicker(piece.kicker or ""),
        Flex(1),
        Stat(piece.stat or "01", caption="", frac=0.28) if (piece.stat or piece.kicker == "") else Gap(0),
        Gap(18),
        Heading(piece.title, frac=0.34, size_max=92, max_lines=4),
        Gap(20),
        Body(piece.lead, frac=0.3, max_lines=7),
        Flex(1),
        Mono(piece.cta or "", size=23),
    ])
    return sh


# ── Registro ────────────────────────────────────────────────────────────────


@dataclass
class Template:
    key: str
    name: str
    summary: str
    fn: Callable[[Piece, Surface, int, str], Sheet]
    grounds: tuple = ("paper", "ruled", "ink")
    needs: tuple = ()

    def render(self, piece: Piece, surface_key: str = "feed", seed: int = 0, ground: str | None = None) -> Sheet:
        surf = surface(surface_key)
        g = ground or self.grounds[seed % len(self.grounds)]
        return self.fn(piece, surf, seed, g)


TEMPLATES: dict[str, Template] = {t.key: t for t in [
    Template("nota", "Aviso de nota", "Nota nueva en el sitio, con su imagen de fondo.",
             t_nota, ("paper", "ruled", "ink"), ("title", "lead")),
    Template("titular", "Titular", "Una idea sola, a toda página.",
             t_titular, ("paper", "ink", "ruled", "minio"), ("title",)),
    Template("dato", "El dato", "Un número grande con su fuente.",
             t_dato, ("ink", "paper", "minio"), ("stat",)),
    Template("cita", "Cita", "Frase textual en bastardilla, con atribución.",
             t_cita, ("paper", "ruled", "ink"), ("quote",)),
    Template("lista", "Lista reglada", "Tres a cinco puntos numerados.",
             t_lista, ("paper", "ruled", "ink"), ("title", "items")),
    Template("mito", "Mito y verdad", "Dos paños: lo que se dice y lo que pasa.",
             t_mito, ("paper", "ruled"), ("title", "items")),
    Template("comparativa", "Antes y después", "El mismo proceso, en dos columnas.",
             t_comparativa, ("paper", "ruled", "ink"), ("title", "items")),
    Template("ficha", "Ficha técnica", "Hoja de especificación de un servicio.",
             t_ficha, ("paper", "ruled"), ("title", "rows")),
    Template("pasos", "Paso a paso", "Proceso encadenado, uno a cuatro pasos.",
             t_pasos, ("paper", "ruled", "ink"), ("title", "items")),
    Template("pregunta", "Pregunta", "Pregunta directa para que respondan.",
             t_pregunta, ("paper", "minio", "ink"), ("title",)),
    Template("glosario", "Glosario", "Un término del rubro, explicado sin humo.",
             t_glosario, ("paper", "ruled", "ink"), ("title", "lead")),
    Template("caso", "Caso", "Problema, solución y resultado.",
             t_caso, ("paper", "ruled", "ink"), ("title",)),
    Template("anuncio", "Anuncio", "Aviso de servicio con los canales de contacto.",
             t_anuncio, ("minio", "ink", "paper"), ("title",)),
    Template("agenda", "La semana", "Tres o cuatro entradas fechadas.",
             t_agenda, ("paper", "ruled", "ink"), ("title", "rows")),
    Template("punto", "Punto de carrusel", "Una idea por lámina, para carruseles.",
             t_punto, ("paper", "ruled", "ink", "minio"), ("title",)),
]}


def get(key: str) -> Template:
    if key not in TEMPLATES:
        raise KeyError(f"Plantilla desconocida: {key}. Hay: {', '.join(TEMPLATES)}")
    return TEMPLATES[key]


def render(key: str, piece: Piece | dict, surface_key: str = "feed", seed: int = 0, ground: str | None = None) -> Sheet:
    if isinstance(piece, dict):
        piece = Piece.from_dict(piece)
    return get(key).render(piece, surface_key, seed, ground)


def carousel(pieces: list[tuple[str, Piece]], surface_key: str = "portrait", seed: int = 0) -> list[Sheet]:
    """Carrusel: una lámina por entrada, con el fondo alternado."""
    sheets = []
    for i, (key, piece) in enumerate(pieces):
        sheets.append(render(key, piece, surface_key, seed=seed + i))
    return sheets
