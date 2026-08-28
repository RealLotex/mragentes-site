#!/usr/bin/env python3
"""Decide si corresponde recuperar la publicación social diaria.

El formato histórico se conserva sólo para leer estados ya existentes. En el
ledger actual, una fecha está cubierta únicamente cuando su pieza
``daily_owned`` terminó en Facebook e Instagram. Las notas del blog son una
línea editorial independiente y nunca cancelan esta recuperación.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence


REPOSITORY = Path(__file__).resolve().parents[2]
STATE = REPOSITORY / "scripts" / "social" / "state.json"


def _entry_date(entry: dict) -> str:
    value = entry.get("local_date", entry.get("date", ""))
    return str(value)[:10]


def _platform_confirmed(entry: dict, platform: str) -> bool:
    platforms = entry.get("platforms")
    if isinstance(platforms, dict):
        checkpoint = platforms.get(platform)
        return bool(
            isinstance(checkpoint, dict)
            and checkpoint.get("status") == "confirmed"
            and checkpoint.get("remote_id")
        )
    return bool(entry.get(platform))


def _complete_daily_entry(entry: object, today: str) -> bool:
    if not isinstance(entry, dict):
        return False
    return bool(
        entry.get("kind") == "daily_owned"
        and _entry_date(entry) == today
        and entry.get("status") == "complete"
        and _platform_confirmed(entry, "facebook")
        and _platform_confirmed(entry, "instagram")
    )


def _legacy_post_today(document: dict, today: str) -> bool:
    """Interpreta el estado v2 sin confundir entradas modernas tipadas."""
    published = document.get("published", {})
    if not isinstance(published, dict):
        return False
    for entry in published.values():
        if not isinstance(entry, dict):
            continue
        if "kind" in entry:
            if _complete_daily_entry(entry, today):
                return True
            continue
        if _entry_date(entry) == today:
            return True
    return False


def has_post_today(state_path: Path = STATE, today: str | None = None) -> bool:
    """Indica si la pieza diaria de la fecha ya quedó completamente cubierta."""
    local_date = today or datetime.now().strftime("%Y-%m-%d")
    try:
        document = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(document, dict):
        return False

    entries = document.get("entries")
    if isinstance(entries, dict):
        return any(_complete_daily_entry(entry, local_date) for entry in entries.values())
    return _legacy_post_today(document, local_date)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evalúa la recuperación social diaria.")
    parser.add_argument("--plain", action="store_true", help="emite fire o nofire")
    parser.add_argument("--state", type=Path, default=STATE, help=argparse.SUPPRESS)
    parser.add_argument("--date", dest="local_date", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    fire = not has_post_today(args.state, args.local_date)
    if args.plain:
        print("fire" if fire else "nofire")
    else:
        print(json.dumps({"fire": fire}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
