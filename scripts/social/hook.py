"""Enganche local entre una nota recién creada y sus piezas gráficas.

La función sólo compone archivos. La automatización programada consume luego
esos artefactos con su propio contrato idempotente; este módulo no tiene
transporte remoto ni un interruptor oculto para activarlo.
"""

from __future__ import annotations

import sys
from pathlib import Path


def announce(nota_path: str | Path, force: bool = False, log=print) -> dict:
    """Compone localmente el aviso de una nota; nunca realiza efectos remotos."""
    del force  # compatibilidad de firma; repetir una composición local es seguro
    try:
        if str(Path(__file__).resolve().parents[2]) not in sys.path:
            sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

        from scripts.social import notas as notas_mod
        from scripts.social.config import load_settings
        from scripts.social.flow import ascii_slug, render_nota_pieces

        settings = load_settings()
        if not settings.enabled:
            log("  ○ Redes: SOCIAL_ENABLED=0, no se compone nada.")
            return {"status": "apagado"}

        nota = notas_mod.load(nota_path)
        pieces = render_nota_pieces(nota, settings)
        log(f"  🖼️  Redes: {len(pieces['all'])} piezas en static/social/{ascii_slug(nota.slug)}/")
        return {"status": "compuesto", "pieces": pieces}

    except Exception as exc:  # noqa: BLE001 — jamás debe voltear la publicación
        log(f"  ⚠️  Redes: {type(exc).__name__}: {exc}")
        return {"status": "error", "error": str(exc)}
