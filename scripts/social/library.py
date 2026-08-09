"""
Biblioteca de posteos listos.

El contenido vive en `library.json` — texto plano, sin código — para que se
pueda ampliar sin abrir un editor de Python. Cada entrada trae la plantilla que
usa, lo que va en la lámina y el texto para cada red.
"""

from __future__ import annotations

import json
from pathlib import Path

from .templates import Piece

LIBRARY_FILE = Path(__file__).with_name("library.json")


def _load() -> list[dict]:
    data = json.loads(LIBRARY_FILE.read_text(encoding="utf-8"))
    return data.get("posts", [])


LIBRARY: list[dict] = _load()


def entry(key: str) -> dict:
    for item in LIBRARY:
        if item["key"] == key:
            return item
    raise KeyError(f"No existe el posteo «{key}». Hay: {', '.join(e['key'] for e in LIBRARY)}")


def library_piece(key: str) -> tuple[str, Piece]:
    item = entry(key)
    return item["template"], Piece.from_dict(item["piece"])


def captions(key: str) -> dict:
    return entry(key).get("caption", {})
