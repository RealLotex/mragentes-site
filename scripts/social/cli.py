#!/usr/bin/env python3
"""
Línea de comandos del social manager.

  python3 -m scripts.social doctor                 # ¿está todo configurado?
  python3 -m scripts.social templates              # las quince plantillas
  python3 -m scripts.social library                # los posteos listos para usar
  python3 -m scripts.social gallery                # muestrario de todo
  python3 -m scripts.social nota --latest          # piezas de la última nota
  python3 -m scripts.social publish-nota --latest  # publicar en FB + IG
  python3 -m scripts.social publish-library --key diagnostico

Sin credenciales no falla: renderiza, muestra el texto que iría y avisa qué
falta. Con `--dry-run` tampoco toca la red, aunque las credenciales estén.
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):  # permite `python3 scripts/social/cli.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = "scripts.social"

from . import copy as copywriter  # noqa: E402
from . import notas as notas_mod  # noqa: E402
from . import state as state_mod  # noqa: E402
from . import templates as tpl  # noqa: E402
from .config import BASE_DIR, ENV_FILE, OUT_DIR, load_settings  # noqa: E402
from .flow import ascii_slug, commit_and_push, public_name, publish_nota, render_nota_pieces  # noqa: E402
from .library import LIBRARY, captions as library_captions, library_piece  # noqa: E402
from .publisher import Meta, PublishError, resolve_public_url  # noqa: E402
from .templates import Piece  # noqa: E402

SURFACE_CHOICES = ("feed", "portrait", "story", "all")


# ── Utilidades ──────────────────────────────────────────────────────────────


def _surfaces(value: str) -> list[str]:
    return ["feed", "portrait", "story"] if value == "all" else [value]


def _show(path: Path) -> str:
    """Ruta corta cuando está dentro del repo; completa cuando no."""
    try:
        return str(path.relative_to(BASE_DIR))
    except ValueError:
        return str(path)


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=BASE_DIR, check=check, capture_output=True, text=True)


def _print_result_block(title: str, results: list) -> None:
    print(f"\n{title}")
    for r in results:
        print(r.line())


# ── Comandos de inspección ──────────────────────────────────────────────────


def cmd_templates(args) -> int:
    print(f"{len(tpl.TEMPLATES)} plantillas:\n")
    for key, t in tpl.TEMPLATES.items():
        print(f"  {key:<12} {t.name:<22} {t.summary}")
        print(f"  {'':<12} fondos: {', '.join(t.grounds)}   campos: {', '.join(t.needs) or '—'}")
    return 0


def cmd_library(args) -> int:
    print(f"{len(LIBRARY)} posteos listos en la biblioteca:\n")
    for entry in LIBRARY:
        print(f"  {entry['key']:<22} [{entry['template']}] {entry['piece'].get('title', '')[:64]}")
    print("\nRenderizar uno:  python3 -m scripts.social render --from <clave> --surface all")
    return 0


def cmd_doctor(args) -> int:
    settings = load_settings()
    print("── Configuración ────────────────────────────────────────────")
    print(f"  .env                {'encontrado' if ENV_FILE.exists() else 'NO existe (copiá .env.example)'}")
    print(f"  SOCIAL_ENABLED      {settings.enabled}")
    print(f"  SOCIAL_DRY_RUN      {settings.dry_run}")
    print(f"  Graph API           {settings.graph_version}")
    print(f"  Facebook            {'listo (page ' + settings.fb_page_id + ')' if settings.can_post_facebook else 'sin configurar'}")
    print(f"  Instagram           {'listo (user ' + settings.ig_user_id + ')' if settings.can_post_instagram else 'sin configurar'}")
    print(f"  Repositorio         {settings.repository} · rama {settings.branch}")

    print("\n── Dependencias ─────────────────────────────────────────────")
    for mod in ("PIL", "fontTools", "brotli", "requests"):
        try:
            __import__(mod)
            print(f"  {mod:<18} ok")
        except ImportError:
            print(f"  {mod:<18} FALTA  → pip install -r scripts/requirements.txt")

    print("\n── Tipografías del sitio ────────────────────────────────────")
    try:
        from . import brand
        for role in ("display", "text", "italic", "data"):
            brand.font(role, 32, 600)
            print(f"  {role:<18} {brand.FONT_FILES[role]}")
    except Exception as exc:
        print(f"  ⚠️  {exc}")

    print("\n── Higiene ──────────────────────────────────────────────────")
    tracked = _git("ls-files", "--", ".env", check=False).stdout.strip()
    print("  .env versionado     " + ("¡SÍ! sacalo con: git rm --cached .env" if tracked else "no (correcto)"))
    ignored = (BASE_DIR / ".gitignore").read_text(encoding="utf-8") if (BASE_DIR / ".gitignore").exists() else ""
    print("  .gitignore cubre    " + ("sí" if ".env" in ignored else "NO — agregá .env"))

    if settings.can_post and not settings.dry_run and args.online:
        print("\n── Cuentas ──────────────────────────────────────────────────")
        try:
            for network, data in Meta(settings).whoami().items():
                print(f"  {network:<18} {data}")
        except PublishError as exc:
            print(f"  ⚠️  {exc}")

    for w in settings.warnings:
        print(f"\n  ⚠️  {w}")
    return 0


# ── Render ──────────────────────────────────────────────────────────────────


def _piece_from_args(args) -> tuple[str, Piece]:
    if args.from_library:
        return library_piece(args.from_library)
    if args.json:
        data = json.loads(Path(args.json).read_text(encoding="utf-8"))
        return data.get("template", args.template or "titular"), Piece.from_dict(data)
    piece = Piece(
        title=args.title or "Título de prueba",
        lead=args.lead or "",
        kicker=args.kicker or "",
        stat=args.stat or "",
        quote=args.quote or "",
    )
    return args.template or "titular", piece


def cmd_render(args) -> int:
    key, piece = _piece_from_args(args)
    out_dir = Path(args.out) if args.out else OUT_DIR / "preview"
    seed = args.seed if args.seed is not None else copywriter.seed_for(key + (piece.title or ""))
    written = []
    for surf in _surfaces(args.surface):
        sheet = tpl.render(key, piece, surf, seed=seed, ground=args.ground)
        path = sheet.save(out_dir / f"{key}-{surf}.jpg")
        written.append(path)
        print(f"  ✔ {_show(path)}")
    return 0 if written else 1


def cmd_gallery(args) -> int:
    """Muestrario: cada plantilla en cada superficie, con contenido real."""
    out_dir = Path(args.out) if args.out else BASE_DIR / "static" / "social" / "muestrario"
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    surfaces = _surfaces(args.surface)
    for entry in LIBRARY:
        key, piece = library_piece(entry["key"])
        seed = copywriter.seed_for(entry["key"])
        for surf in surfaces:
            sheet = tpl.render(key, piece, surf, seed=seed)
            sheet.save(out_dir / f"{entry['key']}-{key}-{surf}.jpg")
            count += 1
    print(f"  ✔ {count} piezas en {out_dir}")
    return 0


def cmd_nota(args) -> int:
    nota = notas_mod.latest() if args.latest or not args.slug else notas_mod.find(args.slug)
    if not nota:
        print("✖ No encontré la nota.")
        return 1
    settings = load_settings()
    out_dir = Path(args.out) if args.out else None
    paths = render_nota_pieces(nota, settings, out_dir, carousel=not args.no_carousel, story=not args.no_story)
    print(f"\n📝 {nota.title}")
    print(f"   {nota.url(settings.site_base_url)}")
    for p in paths["all"]:
        print(f"  ✔ {_show(p)}")
    print("\n── Facebook ─────────────────────────────────────────────────")
    print(copywriter.caption(nota, "facebook", settings.site_base_url))
    print("\n── Instagram ────────────────────────────────────────────────")
    print(copywriter.caption(nota, "instagram", settings.site_base_url))
    return 0


# ── Publicación ─────────────────────────────────────────────────────────────


def cmd_publish_nota(args) -> int:
    settings = load_settings()
    if args.dry_run:
        settings.dry_run = True
    if not settings.enabled and not settings.dry_run:
        print("○ SOCIAL_ENABLED=0 — no se publica nada.")
        return 0

    nota = notas_mod.latest() if args.latest or not args.slug else notas_mod.find(args.slug)
    if not nota:
        print("✖ No encontré la nota.")
        return 1

    print(f"📝 {nota.title}")
    print(f"   {nota.url(settings.site_base_url)}")
    if nota.photo:
        print(f"   imagen de la nota: {_show(nota.photo)}")
    else:
        print("   ⚠️  la nota no declara imagen — las piezas van sobre papel")

    outcome = publish_nota(
        nota, settings,
        carousel=not args.no_carousel,
        story=not args.no_story,
        commit=not args.no_commit,
        branch=args.branch,
        wait=args.wait,
        force=args.force,
    )

    if outcome["status"] in {"ensayo", "sin-credenciales"}:
        print("\n── Facebook ─────────────────────────────────────────────────")
        print(outcome["captions"]["facebook"])
        print("\n── Instagram ────────────────────────────────────────────────")
        print(outcome["captions"]["instagram"])
        motivo = "SOCIAL_DRY_RUN" if outcome["status"] == "ensayo" else "faltan credenciales"
        carpeta = ascii_slug(nota.slug)
        print(f"\n○ No se publicó ({motivo}). Las piezas quedaron en static/social/{carpeta}/")
        return 0

    if outcome["status"] == "ya-publicada":
        return 0

    _print_result_block("── Resultado ───────────────────────────────────────────────", outcome["results"])
    return 0 if outcome["status"] == "publicada" else 1


def cmd_publish_library(args) -> int:
    settings = load_settings()
    if args.dry_run:
        settings.dry_run = True

    # ── Guardia anti-duplicado ──────────────────────────────────────────
    # `publish-nota` revisa state.json antes de publicar y por eso nunca
    # duplica. Acá no se revisaba → si el cron reintenta o se invoca el
    # comando dos veces en la misma ventana, Facebook/Instagram recibían
    # el post dos veces (el duplicado aparecía ~1 min después del original,
    # cuando el chequeo de URL/verificación ya había pasado).
    # Lección 2026-08-15: mismo guard que publish-nota, con --force para
    # republicar deliberadamente.
    state = state_mod.load()
    if state_mod.is_published(args.key, state) and not args.force:
        print(f"○ «{args.key}» ya se publicó ({state['published'][args.key].get('date', '?')}).")
        print("  Usá --force si querés republicarlo a propósito (CUIDADO: duplica en redes).")
        return 0

    key, piece = library_piece(args.key)
    seed = copywriter.seed_for(args.key)

    out_dir = OUT_DIR / "biblioteca"
    feed = tpl.render(key, piece, args.surface, seed=seed).save(out_dir / f"{args.key}.jpg")
    print(f"  ✔ {_show(feed)}")
    story_path = None
    if args.story:
        story_path = tpl.render(key, piece, "story", seed=seed).save(out_dir / f"{args.key}-historia.jpg")
        print(f"  ✔ {_show(story_path)}")

    texts = library_captions(args.key)
    fb_caption = texts.get("facebook", "")
    ig_caption = texts.get("instagram", "")

    if settings.dry_run or not settings.can_post:
        print("\n── Facebook ─────────────────────────────────────────────────")
        print(fb_caption)
        print("\n── Instagram ────────────────────────────────────────────────")
        print(ig_caption)
        return 0

    if not args.no_commit:
        commit_and_push([p for p in [feed, story_path] if p], f"🖼️  Pieza de redes: {args.key}", args.branch)

    meta = Meta(settings)
    results = [meta.facebook_photo(feed, fb_caption)]
    url = resolve_public_url(public_name(feed), settings, wait=args.wait)
    if url:
        results.append(meta.instagram_image(url, ig_caption))
    if story_path:
        surl = resolve_public_url(public_name(story_path), settings, wait=args.wait)
        if surl:
            results.append(meta.instagram_story(surl))
    _print_result_block("── Resultado ───────────────────────────────────────────────", results)

    # Registrar en state.json (igual que publish-nota) para evitar duplicados
    # en el cron. La clave es args.key; sin esto, si el cron vuelve a correr,
    # no hay forma de saber que la pieza ya se publicó.
    record: dict = {"date": datetime.datetime.now().date().isoformat()}
    fb = next((r for r in results if r.network == "facebook" and r.ok), None)
    ig = next((r for r in results if r.network == "instagram" and r.kind == "feed" and r.ok), None)
    st = next((r for r in results if r.network == "instagram" and r.kind == "historia" and r.ok), None)
    if fb:
        record["facebook"] = fb.id
    if ig:
        record["instagram"] = ig.id
    if st:
        record["story"] = st.id
    if record != {"date": record["date"]}:
        state_mod.record(args.key, record, state=state_mod.load())

    return 0 if any(r.ok for r in results) else 1


# ── Parser ──────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="scripts.social", description="Social manager de MR Agentes")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="revisar configuración, dependencias e higiene")
    d.add_argument("--online", action="store_true", help="además consultar la Graph API")
    d.set_defaults(func=cmd_doctor)

    t = sub.add_parser("templates", help="listar plantillas")
    t.set_defaults(func=cmd_templates)

    lb = sub.add_parser("library", help="listar posteos listos para usar")
    lb.set_defaults(func=cmd_library)

    r = sub.add_parser("render", help="renderizar una pieza")
    r.add_argument("--template", help="clave de plantilla")
    r.add_argument("--from", dest="from_library", help="clave de la biblioteca")
    r.add_argument("--json", help="archivo JSON con el contenido")
    r.add_argument("--surface", choices=SURFACE_CHOICES, default="feed")
    r.add_argument("--ground", choices=("paper", "ruled", "ink", "minio"))
    r.add_argument("--seed", type=int)
    r.add_argument("--out")
    r.add_argument("--title")
    r.add_argument("--lead")
    r.add_argument("--kicker")
    r.add_argument("--stat")
    r.add_argument("--quote")
    r.set_defaults(func=cmd_render)

    g = sub.add_parser("gallery", help="muestrario de toda la biblioteca")
    g.add_argument("--surface", choices=SURFACE_CHOICES, default="all")
    g.add_argument("--out")
    g.set_defaults(func=cmd_gallery)

    n = sub.add_parser("nota", help="renderizar las piezas de una nota (sin publicar)")
    n.add_argument("--slug")
    n.add_argument("--latest", action="store_true")
    n.add_argument("--out")
    n.add_argument("--no-story", action="store_true")
    n.add_argument("--no-carousel", action="store_true")
    n.set_defaults(func=cmd_nota)

    pn = sub.add_parser("publish-nota", help="publicar una nota en Facebook e Instagram")
    pn.add_argument("--slug")
    pn.add_argument("--latest", action="store_true")
    pn.add_argument("--dry-run", action="store_true")
    pn.add_argument("--force", action="store_true", help="republicar aunque ya esté registrada")
    pn.add_argument("--no-story", action="store_true")
    pn.add_argument("--no-carousel", action="store_true")
    pn.add_argument("--no-commit", action="store_true", help="no commitear las imágenes")
    pn.add_argument("--branch", default="", help="rama a la que pushear las imágenes")
    pn.add_argument("--wait", type=int, default=240, help="segundos de espera a que la URL esté viva")
    pn.set_defaults(func=cmd_publish_nota)

    pl = sub.add_parser("publish-library", help="publicar un posteo de la biblioteca")
    pl.add_argument("--key", required=True)
    pl.add_argument("--surface", choices=("feed", "portrait"), default="portrait")
    pl.add_argument("--story", action="store_true")
    pl.add_argument("--dry-run", action="store_true")
    pl.add_argument("--force", action="store_true", help="republicar aunque ya esté registrada (CUIDADO: duplica)")
    pl.add_argument("--no-commit", action="store_true")
    pl.add_argument("--branch", default="")
    pl.add_argument("--wait", type=int, default=240)
    pl.set_defaults(func=cmd_publish_library)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except (KeyError, FileNotFoundError, ValueError) as exc:
        print(f"✖ {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
