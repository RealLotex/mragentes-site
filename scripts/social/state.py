"""
Qué se publicó y qué no.

Sirve para dos cosas: que una nota no se postee dos veces (el workflow puede
correr de nuevo por un reintento o un push arreglando una coma) y que el
rotador de plantillas no repita la misma composición dos veces seguidas.
"""

from __future__ import annotations

import datetime
import json
import os
import tempfile
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
    """Persist *state* without leaving a partially-written document behind.

    JSON serialization happens before the destination is touched.  If the
    filesystem write then fails after modifying the destination, the previous
    bytes are restored through a same-directory atomic replace.  The same
    rollback also removes a partial file when this was the first save.
    """

    payload = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = path.read_bytes() if path.exists() else None

    try:
        path.write_text(payload, encoding="utf-8")
    except BaseException:
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{path.name}.",
                suffix=".rollback",
                dir=path.parent,
            )
            temporary = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(previous)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
        raise


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
