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
import hashlib
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
from .delivery import (  # noqa: E402
    announcement_asset_relative_path,
    build_blog_note_draft,
    deliver_draft,
)
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
        photo=getattr(args, "photo", None) or None,
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


def cmd_render_note_announcement(args) -> int:
    """Render the only image a blog-note delivery is allowed to publish."""

    nota = notas_mod.find(args.slug)
    if nota is None:
        raise ValueError(f"No encontré la nota {args.slug!r}")
    if nota.photo is None:
        raise ValueError("La nota necesita una portada local antes del render de redes")
    target = Path(args.out) if args.out else BASE_DIR / announcement_asset_relative_path(nota)
    target = target if target.is_absolute() else BASE_DIR / target
    rendered = tpl.render(
        "nota",
        copywriter.cover_piece(nota, load_settings().site_base_url),
        "portrait",
        seed=copywriter.seed_for(nota.slug),
    ).save(target)
    print(f"  ✔ anuncio de plantilla nota: {_show(rendered)}")
    return 0


def cmd_draft_daily(args) -> int:
    """Crea y valida un borrador diario local; no consulta servicios remotos."""
    from scripts.automation import social_guard

    local_date = datetime.date.fromisoformat(args.date) if args.date else datetime.date.today()
    asset = Path(args.asset)
    asset = asset if asset.is_absolute() else BASE_DIR / asset
    asset = asset.resolve()
    try:
        relative_asset = asset.relative_to(BASE_DIR.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("El asset debe estar dentro del repositorio") from exc
    if not asset.is_file():
        raise FileNotFoundError(asset)
    if not relative_asset.startswith("static/images/social/"):
        raise ValueError("El asset diario debe estar bajo static/images/social/")

    zone = datetime.datetime.now().astimezone().tzinfo
    created_at = datetime.datetime.combine(
        local_date, datetime.time(hour=12), tzinfo=zone
    ).isoformat()
    topic_hash = "sha256:" + hashlib.sha256(args.topic.encode("utf-8")).hexdigest()
    draft = {
        "schema_version": 1,
        "run_id": social_guard.social_run_id(local_date.isoformat(), "daily_owned"),
        "kind": "daily_owned",
        "topic": args.topic,
        "topic_hash": topic_hash,
        "content_hash": "pending",
        "dedupe_key": "pending",
        "asset": {
            "path": relative_asset,
            "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
            "alt": args.alt,
        },
        "captions": {
            "facebook": args.facebook_caption,
            "instagram": args.instagram_caption,
        },
        "created_at": created_at,
    }
    draft["content_hash"] = social_guard.content_hash(draft)
    draft["dedupe_key"] = (
        f"daily_owned:{local_date.isoformat()}:{draft['content_hash']}"
    )
    validated = social_guard.validate_social_draft(draft)
    target = (
        Path(args.out)
        if args.out
        else BASE_DIR
        / ".automation"
        / "social"
        / "drafts"
        / f"{local_date}-daily-owned.json"
    )
    target = target if target.is_absolute() else BASE_DIR / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(validated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"  ✔ borrador local validado: {_show(target)}")
    return 0


def cmd_recover(args) -> int:
    """Muestra un plan de recuperación desde el ledger, sin ejecutar efectos."""
    from . import ledger as ledger_mod

    local_date = datetime.date.fromisoformat(args.date).isoformat()
    ledger_path = Path(args.ledger)
    ledger_path = ledger_path if ledger_path.is_absolute() else BASE_DIR / ledger_path
    document = ledger_mod.load_ledger(ledger_path)
    matches = [
        entry
        for entry in document["entries"].values()
        if entry.get("kind") == args.kind and entry.get("local_date") == local_date
    ]
    if args.subject:
        matches = [entry for entry in matches if args.subject in entry.get("run_id", "")]
    if not matches:
        print("○ No hay una ejecución local para recuperar.")
        return 1
    if len(matches) > 1:
        raise ValueError("Hay varias ejecuciones; indicá --subject para desambiguar")
    plan = ledger_mod.recovery_plan(matches[0])
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0 if plan.get("decision") != "needs_review" else 2


def _delivery_exit(result: dict) -> int:
    status = result.get("status")
    if status == "complete":
        return 0
    if status == "partial":
        return 2
    if status == "needs_review":
        return 3
    raise ValueError(f"Estado de entrega desconocido: {status!r}")


def cmd_deliver_draft(args) -> int:
    """Deliver one committed daily draft through the guarded Meta adapter."""

    draft_path = Path(args.draft)
    draft_path = draft_path if draft_path.is_absolute() else BASE_DIR / draft_path
    ledger_path = Path(args.ledger)
    ledger_path = ledger_path if ledger_path.is_absolute() else BASE_DIR / ledger_path
    document = json.loads(draft_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("El draft social debe ser un objeto JSON")
    result = deliver_draft(
        document,
        settings=load_settings(),
        root=BASE_DIR,
        ledger_path=ledger_path,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return _delivery_exit(result)


def cmd_deliver_note(args) -> int:
    """Build and deliver the transient contract for one deployed blog note."""

    note = notas_mod.find(args.slug)
    if note is None:
        raise ValueError(f"No encontré la nota {args.slug!r}")
    ledger_path = Path(args.ledger)
    ledger_path = ledger_path if ledger_path.is_absolute() else BASE_DIR / ledger_path
    created_at = args.created_at or f"{note.date.isoformat()}T12:00:00-03:00"
    settings = load_settings()
    draft = build_blog_note_draft(
        note,
        deploy_sha=args.deploy_sha,
        root=BASE_DIR,
        created_at=created_at,
        site_base_url=settings.site_base_url,
    )
    result = deliver_draft(
        draft,
        settings=settings,
        root=BASE_DIR,
        ledger_path=ledger_path,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return _delivery_exit(result)


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
    fb_result = meta.facebook_photo(feed, fb_caption)
    results = [fb_result]
    if fb_result.ok:
        # Registrar YA (lección 2026-08-21: si el proceso muere a mitad, un
        # reintento no debe volver a publicar FB).
        state_mod.record(
            args.key,
            {"date": datetime.datetime.now().date().isoformat(), "facebook": fb_result.id},
            state=state,
        )
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
    r.add_argument("--photo", help="foto de fondo local; se compone mediante la plantilla, nunca se publica sin marca")
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

    rna = sub.add_parser(
        "render-note-announcement",
        help="renderizar la pieza social obligatoria de una nota con la plantilla MR Agentes",
    )
    rna.add_argument("--slug", required=True)
    rna.add_argument("--out", help="ruta de salida; por defecto static/images/social/notes/")
    rna.set_defaults(func=cmd_render_note_announcement)

    dd = sub.add_parser("draft-daily", help="crear un borrador diario local validado")
    dd.add_argument("--date", help="fecha local YYYY-MM-DD (default: hoy)")
    dd.add_argument("--topic", required=True)
    dd.add_argument("--asset", required=True, help="archivo bajo static/images/social/")
    dd.add_argument("--alt", required=True, help="texto alternativo de la imagen")
    dd.add_argument("--facebook-caption", required=True)
    dd.add_argument("--instagram-caption", required=True)
    dd.add_argument("--out", help="JSON de salida local")
    dd.set_defaults(func=cmd_draft_daily)

    rc = sub.add_parser("recover", help="inspeccionar un plan local de recuperación")
    rc.add_argument("--kind", required=True, choices=("daily_owned", "blog_note"))
    rc.add_argument("--date", required=True, help="fecha local YYYY-MM-DD")
    rc.add_argument("--subject", help="slug de nota cuando haya más de una ejecución")
    rc.add_argument("--ledger", default="scripts/social/ledger.json")
    rc.set_defaults(func=cmd_recover)

    deliver_daily = sub.add_parser(
        "deliver-draft", help="entregar un draft validado a Meta testing"
    )
    deliver_daily.add_argument("--draft", required=True)
    deliver_daily.add_argument("--ledger", default=".automation/reports/social-delivery.json")
    deliver_daily.set_defaults(func=cmd_deliver_draft)

    deliver_note = sub.add_parser(
        "deliver-note", help="entregar el anuncio de una nota ya desplegada"
    )
    deliver_note.add_argument("--slug", required=True)
    deliver_note.add_argument("--deploy-sha", required=True)
    deliver_note.add_argument("--created-at")
    deliver_note.add_argument("--ledger", default=".automation/reports/social-delivery.json")
    deliver_note.set_defaults(func=cmd_deliver_note)

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
