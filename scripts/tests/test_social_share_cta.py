#!/usr/bin/env python3
"""Contrato de alcance orgánico para las piezas sociales de una nota."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.social import copy as copywriter  # noqa: E402
from scripts.social.notas import Nota  # noqa: E402
from scripts.social.templates import Piece  # noqa: E402


def sample_nota() -> Nota:
    return Nota(
        path=ROOT / "content/notas/ejemplo.md",
        title="Cómo empezar a automatizar una tarea repetida",
        date=dt.date(2026, 8, 31),
        description="Una explicación simple para detectar una tarea repetida y probar un primer cambio seguro.",
        tags=["automatización", "principiantes"],
        body=(
            "## Primer paso\n\n"
            "Elegí una tarea que se repita y anotá qué información necesita.\n\n"
            "## Segundo paso\n\n"
            "Probá el cambio con una persona revisando el resultado.\n\n"
            "## Tercer paso\n\n"
            "Medí si la tarea tarda menos y corregí lo que no funcione."
        ),
    )


def check(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(name)
    print(f"  OK {name}")


def main() -> None:
    nota = sample_nota()

    for network in ("facebook", "instagram"):
        check(
            f"el copy de {network} invita a compartir",
            copywriter.SOCIAL_SHARE_CTA in copywriter.caption(nota, network),
        )

    slides = copywriter.carousel_for_nota(nota)
    check("cada lámina del carrusel incluye el CTA de compartir", all(
        piece.footer_right == copywriter.SOCIAL_SHARE_CTA for _, piece in slides
    ))
    check("la historia incluye el CTA de compartir", (
        copywriter.story_piece(nota).footer_right == copywriter.SOCIAL_SHARE_CTA
    ))
    check("una pieza diaria creada desde una plantilla incluye el CTA", (
        Piece().footer_right == copywriter.SOCIAL_SHARE_CTA
    ))


if __name__ == "__main__":
    main()
