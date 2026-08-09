"""
Enganche para los publicadores de notas.

`publish_daily.py` y `publish_blog.py` llaman a `announce()` justo después de
pushear la nota. Es a prueba de balas por diseño: si falta una dependencia, si
no hay credenciales o si Meta devuelve un error, la nota ya está publicada en
la web y esto sólo escribe una línea de aviso. Nunca corta el flujo.

Por defecto compone las piezas y no publica: quien publica es el workflow
`.github/workflows/social.yml`, que se dispara con el mismo push. Si preferís
publicar desde tu máquina, poné `SOCIAL_LOCAL_PUBLISH=1` en el `.env` y
desactivá el workflow (variable de repositorio `SOCIAL_ENABLED=0`), para que la
nota no salga dos veces.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def announce(nota_path: str | Path, force: bool = False, log=print) -> dict:
    """Compone (y opcionalmente publica) el aviso de una nota recién publicada."""
    try:
        if str(Path(__file__).resolve().parents[2]) not in sys.path:
            sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

        from scripts.social import notas as notas_mod
        from scripts.social.config import TRUTHY, load_settings
        from scripts.social.flow import ascii_slug, publish_nota, render_nota_pieces

        settings = load_settings()
        if not settings.enabled:
            log("  ○ Redes: SOCIAL_ENABLED=0, no se compone nada.")
            return {"status": "apagado"}

        nota = notas_mod.load(nota_path)
        local = (os.environ.get("SOCIAL_LOCAL_PUBLISH", "0") or "0").strip().lower() in TRUTHY

        if not local or settings.dry_run or not settings.can_post:
            pieces = render_nota_pieces(nota, settings)
            log(f"  🖼️  Redes: {len(pieces['all'])} piezas en static/social/{ascii_slug(nota.slug)}/")
            if not local:
                log("  ○ Publica GitHub Actions (SOCIAL_LOCAL_PUBLISH=0).")
            elif not settings.can_post:
                log("  ○ Sin credenciales de Meta: sólo se compusieron las piezas.")
            return {"status": "compuesto", "pieces": pieces}

        log("  📣 Redes: publicando en Facebook e Instagram…")
        outcome = publish_nota(nota, settings, force=force, log=log)
        for r in outcome.get("results", []):
            log(r.line())
        return outcome

    except Exception as exc:  # noqa: BLE001 — jamás debe voltear la publicación
        log(f"  ⚠️  Redes: {type(exc).__name__}: {exc}")
        return {"status": "error", "error": str(exc)}
