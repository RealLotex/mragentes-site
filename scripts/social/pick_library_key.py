#!/usr/bin/env python3
"""Valida manualmente una pieza histórica de la biblioteca social.

La biblioteca es sólo material de compatibilidad: este comando nunca elige una
pieza por fecha ni actúa como fuente del contenido diario. La persona u
orquestación que lo invoque debe indicar una clave de manera explícita.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


REPOSITORY = Path(__file__).resolve().parents[2]
LIBRARY = REPOSITORY / "scripts" / "social" / "library.json"
STATE = REPOSITORY / "scripts" / "social" / "state.json"


def _library_items(document: object) -> list[dict]:
    """Devuelve entradas con forma válida preservando el orden del archivo."""
    if isinstance(document, list):
        candidates = document
    elif isinstance(document, dict):
        candidates = document.get("posts", document.get("items", []))
    else:
        candidates = []
    if not isinstance(candidates, list):
        return []
    return [item for item in candidates if isinstance(item, dict)]


def load_keys(path: Path = LIBRARY) -> list[str]:
    """Carga claves únicas y no vacías desde la biblioteca local."""
    document = json.loads(path.read_text(encoding="utf-8"))
    keys: list[str] = []
    seen: set[str] = set()
    for item in _library_items(document):
        key = item.get("key")
        if not isinstance(key, str):
            continue
        key = key.strip()
        if key and key not in seen:
            keys.append(key)
            seen.add(key)
    return keys


def published_keys(path: Path = STATE) -> set[str]:
    """Lee las claves ya registradas; un estado ausente o corrupto es vacío."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(document, dict):
        return set()
    published = document.get("published", {})
    if not isinstance(published, dict):
        return set()
    return {key for key in published if isinstance(key, str)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Valida una clave histórica elegida de forma manual."
    )
    parser.add_argument("key", nargs="?", help="clave explícita de library.json")
    parser.add_argument("--key", dest="named_key", help="equivalente nominal de key")
    parser.add_argument("--library", type=Path, default=LIBRARY, help=argparse.SUPPRESS)
    parser.add_argument("--state", type=Path, default=STATE, help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.key and args.named_key and args.key != args.named_key:
        print("ERROR: se indicaron dos claves diferentes", file=sys.stderr)
        return 2
    requested = args.named_key or args.key
    if not requested:
        print("ERROR: indicá una clave explícita con --key <CLAVE>", file=sys.stderr)
        return 2

    try:
        keys = load_keys(args.library)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: no se pudo leer la biblioteca: {exc}", file=sys.stderr)
        return 2
    if not keys:
        print("ERROR: la biblioteca no contiene claves válidas", file=sys.stderr)
        return 2
    if requested not in keys:
        print(f"ERROR: clave desconocida: {requested}", file=sys.stderr)
        return 2

    is_published = requested in published_keys(args.state)
    print(f"KEY={requested}")
    print(f"PUBLISHED={str(is_published).lower()}")
    if is_published:
        print("NOTE=La pieza ya figura en el estado; no debe volver a publicarse")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
