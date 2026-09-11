"""Composición local de piezas sociales para el sistema editorial.

La publicación remota, el push y el ledger pertenecen a los workflows de
GitHub. Este módulo sólo renderiza piezas para inspección o para que otro
proceso las empaquete como artefacto versionado.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from . import copy as copywriter
from . import state as state_mod
from . import templates as tpl
from .config import BASE_DIR, OUT_DIR, Settings
from .notas import Nota


def ascii_slug(text: str, limit: int = 72) -> str:
    """Nombre de carpeta sin acentos.

    Los slugs de las notas los tienen («…se-volvió-transparente») y quedan bien
    en la URL de la web, pero acá el nombre viaja hasta los servidores de Meta
    para que bajen la imagen. Un carácter mal codificado en el camino y la
    publicación falla sin decir por qué. Se le saca el acento y listo.
    """
    plain = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    plain = re.sub(r"[^A-Za-z0-9._-]+", "-", plain).strip("-.")
    return (plain[:limit].rstrip("-.") or "nota").lower()


# ── Composición ─────────────────────────────────────────────────────────────


def render_nota_pieces(
    nota: Nota,
    settings: Settings,
    out_dir: Path | None = None,
    carousel: bool = True,
    story: bool = True,
) -> dict:
    """Carrusel 4:5 + historia 9:16, armados con el contenido real de la nota."""
    out_dir = Path(out_dir) if out_dir else OUT_DIR / ascii_slug(nota.slug)
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = copywriter.seed_for(nota.slug)

    slides = (
        copywriter.carousel_for_nota(nota, settings.site_base_url)
        if carousel
        else [("nota", copywriter.cover_piece(nota, settings.site_base_url))]
    )
    feed_paths = [
        tpl.render(key, piece, "portrait", seed=seed + i).save(out_dir / f"{i:02d}-{key}.jpg")
        for i, (key, piece) in enumerate(slides, start=1)
    ]

    story_path = None
    if story:
        story_path = tpl.render(
            "nota", copywriter.story_piece(nota, settings.site_base_url), "story", seed=seed
        ).save(out_dir / "historia.jpg")

    return {
        "feed": feed_paths,
        "story": story_path,
        "all": feed_paths + ([story_path] if story_path else []),
    }


def public_name(path: Path) -> str:
    """Nombre relativo a static/social/, que es lo que ve la URL pública."""
    return str(path.relative_to(OUT_DIR)).replace("\\", "/")


# Carpetas de static/social/ que no son piezas de notas.
RESERVED_DIRS = {"muestrario", "preview", "biblioteca"}


def prune_old_pieces(keep: int = 10, log=print) -> list[str]:
    """Deja sólo las piezas de las últimas `keep` notas.

    Cada nota son unos 800 kB de imágenes que Meta sólo necesita durante los
    minutos que tarda en descargarlas. Guardarlas para siempre engorda el sitio
    y el repositorio sin que nadie las mire: pasada esa ventana, se borran.
    """
    if isinstance(keep, bool) or not isinstance(keep, int) or keep < 0:
        raise ValueError("keep debe ser un entero no negativo")
    if not OUT_DIR.exists():
        return []
    import shutil

    dirs = sorted(
        (d for d in OUT_DIR.iterdir() if d.is_dir() and d.name not in RESERVED_DIRS),
        key=lambda d: d.name,
    )
    stale = dirs if keep == 0 else (dirs[:-keep] if len(dirs) > keep else [])
    removed = []
    for d in stale:
        shutil.rmtree(d, ignore_errors=True)
        removed.append(d.name)
    if removed:
        log(f"  🧹 Piezas viejas borradas: {len(removed)}")
    return removed


# ── Publicación ─────────────────────────────────────────────────────────────


def publish_nota(
    nota: Nota,
    settings: Settings,
    *,
    carousel: bool = True,
    story: bool = True,
    commit: bool = True,
    branch: str = "",
    wait: int = 240,
    force: bool = False,
    log=print,
) -> dict:
    """Renderiza un ensayo; la entrega remota sólo existe en GitHub Actions."""
    del commit, branch, wait, force
    if not settings.dry_run:
        log("⛔ Publicación directa deshabilitada: use la cola editorial y los workflows de GitHub.")
        return {"status": "deshabilitada", "results": [], "pieces": {}, "captions": {}}

    state = state_mod.load()

    pieces = render_nota_pieces(nota, settings, carousel=carousel, story=story)
    for p in pieces["all"]:
        log(f"  ✔ {p.relative_to(BASE_DIR)}")

    captions = {
        "facebook": copywriter.caption(nota, "facebook", settings.site_base_url),
        "instagram": copywriter.caption(nota, "instagram", settings.site_base_url),
    }

    return {
        "status": "ensayo",
        "results": [],
        "pieces": pieces,
        "captions": captions,
    }
