"""
El circuito completo: de la nota publicada al posteo.

  nota en content/notas/  →  piezas en static/social/<slug>/  →  commit + push
  →  URL pública  →  Facebook (multipart) + Instagram (carrusel e historia)
  →  registro en state.json

Lo usan tanto el CLI como el enganche automático de `publish_daily.py` y
`publish_blog.py`, así que la lógica vive una sola vez.
"""

from __future__ import annotations

import re
import subprocess
import time
import unicodedata
from pathlib import Path

from . import copy as copywriter
from . import state as state_mod
from . import templates as tpl
from .config import BASE_DIR, OUT_DIR, Settings
from .notas import Nota
from .publisher import Meta, resolve_public_url


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


# ── git ─────────────────────────────────────────────────────────────────────


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=BASE_DIR, check=check, capture_output=True, text=True)


def commit_and_push(paths: list[Path], message: str, branch: str = "", log=print) -> bool:
    """Publica las piezas en el repo. Instagram las baja por URL, no por subida."""
    rels = []
    for p in paths:
        try:
            rels.append(str(p.relative_to(BASE_DIR)))
        except ValueError:
            continue
    if not rels:
        return False

    try:
        _git("add", "--", *rels)
        if not _git("diff", "--cached", "--quiet", "--", *rels, check=False).returncode:
            return True  # no había nada nuevo que commitear
        _git("commit", "-m", message)
    except subprocess.CalledProcessError as exc:
        log(f"  ⚠️  git commit falló: {(exc.stderr or '').strip()[:200]}")
        return False

    target = branch or _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    delay = 2
    for attempt in range(4):
        try:
            _git("push", "-u", "origin", f"HEAD:{target}")
            return True
        except subprocess.CalledProcessError as exc:
            err = (exc.stderr or "").strip()
            log(f"  ⚠️  push falló ({attempt + 1}/4): {err[:160]}")
            time.sleep(delay)
            delay *= 2
            try:
                _git("pull", "--rebase", "origin", target)
            except subprocess.CalledProcessError:
                pass
    return False


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
    if not OUT_DIR.exists():
        return []
    import shutil

    dirs = sorted(
        (d for d in OUT_DIR.iterdir() if d.is_dir() and d.name not in RESERVED_DIRS),
        key=lambda d: d.name,
    )
    stale = dirs[:-keep] if len(dirs) > keep else []
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
    """Devuelve {'status', 'results', 'pieces', 'captions'}. Nunca levanta excepción."""
    state = state_mod.load()
    if state_mod.is_published(nota.slug, state) and not force:
        log(f"○ «{nota.title}» ya se había publicado. Usá --force para repetir.")
        return {"status": "ya-publicada", "results": [], "pieces": {}, "captions": {}}

    pieces = render_nota_pieces(nota, settings, carousel=carousel, story=story)
    for p in pieces["all"]:
        log(f"  ✔ {p.relative_to(BASE_DIR)}")

    captions = {
        "facebook": copywriter.caption(nota, "facebook", settings.site_base_url),
        "instagram": copywriter.caption(nota, "instagram", settings.site_base_url),
    }

    if settings.dry_run or not settings.can_post:
        return {
            "status": "ensayo" if settings.dry_run else "sin-credenciales",
            "results": [],
            "pieces": pieces,
            "captions": captions,
        }

    if commit:
        prune_old_pieces(log=log)
        # Se commitea el directorio entero para que la limpieza viaje en el
        # mismo commit que las piezas nuevas.
        if not commit_and_push([*pieces["all"], OUT_DIR], f"🖼️  Piezas de redes: {nota.title}", branch, log):
            log("  ⚠️  No pude publicar las imágenes en el repo; Instagram puede fallar.")

    meta = Meta(settings)
    results = []
    record: dict = {"date": nota.date.isoformat(), "images": [public_name(p) for p in pieces["all"]]}

    # Facebook: publicar el álbum completo (todas las láminas del feed), no
    # la portada sola.
    fb = meta.facebook_album(pieces["feed"], captions["facebook"], link=nota.url(settings.site_base_url))
    results.append(fb)
    if fb.ok:
        record["facebook"] = fb.id

    urls = []
    missing = []
    for path in pieces["feed"]:
        url = resolve_public_url(public_name(path), settings, wait=wait)
        if url:
            urls.append(url)
        else:
            missing.append(public_name(path))
            log(f"  ⚠️  {public_name(path)} no respondió por URL; se intenta igual vía raw.")

    # Si alguna no resolvió, reintentamos con espera extra antes de rendirnos:
    # un carrusel incompleto no es aceptable.
    for _path in list(missing):
        url = resolve_public_url(_path, settings, wait=120)
        if url:
            urls.append(url)
            missing.remove(_path)

    if urls:
        ig = (
            meta.instagram_carousel(urls[:10], captions["instagram"])
            if len(urls) > 1
            else meta.instagram_image(urls[0], captions["instagram"])
        )
        results.append(ig)
        if ig.ok:
            record["instagram"] = ig.id
        elif missing:
            log(f"  ✖ Instagram: faltaron láminas -> {', '.join(missing)}")
    else:
        log("  ✖ Instagram: ninguna pieza quedó accesible por URL pública.")

    if pieces["story"]:
        story_url = resolve_public_url(public_name(pieces["story"]), settings, wait=wait)
        if story_url:
            st = meta.instagram_story(story_url)
            results.append(st)
            if st.ok:
                record["story"] = st.id
            # La historia de Facebook no se publica por Graph API: Meta no
            # expone el edge para apps de terceros (verificado: /stories da
            # "Unsupported post request" con o sin pages_manage_metadata).
            # La historia queda solo en Instagram, donde sí funciona.

    state_mod.record(nota.slug, record, state)
    return {
        "status": "publicada" if any(r.ok for r in results) else "falló",
        "results": results,
        "pieces": pieces,
        "captions": captions,
    }
