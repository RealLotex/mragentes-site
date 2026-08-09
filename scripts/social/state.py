"""
Qué se publicó y qué no.

Sirve para dos cosas: que una nota no se postee dos veces (el workflow puede
correr de nuevo por un reintento o un push arreglando una coma) y que el
rotador de plantillas no repita la misma composición dos veces seguidas.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from .config import STATE_FILE

EMPTY = {"version": 2, "published": {}}


def load(path: Path = STATE_FILE) -> dict:
    if not path.exists():
        return dict(EMPTY, published={})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(EMPTY, published={})
    data.setdefault("published", {})
    data.setdefault("version", 2)
    return data


def save(state: dict, path: Path = STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_published(slug: str, state: dict | None = None) -> bool:
    state = state if state is not None else load()
    entry = state["published"].get(slug)
    if not entry:
        return False
    return bool(entry.get("facebook") or entry.get("instagram"))


def record(slug: str, results: dict, state: dict | None = None, save_now: bool = True) -> dict:
    state = state if state is not None else load()
    entry = state["published"].setdefault(slug, {})
    entry["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    for key, value in results.items():
        if value:
            entry[key] = value
    if save_now:
        save(state)
    return state
