#!/usr/bin/env python3
"""Generate the public note index consumed by the service worker.

Hugo's URL is determined by an explicit ``slug`` when present and otherwise by
the materialized Markdown filename. Keeping that rule here avoids breaking
canonical URLs when a long source filename must be shortened for portability.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

import yaml


BASE_DIR = Path(__file__).resolve().parent.parent
CONTENT_DIR = BASE_DIR / "content" / "notas"


def parse_front_matter(content: str) -> dict[str, Any]:
    """Parse a closed YAML front-matter mapping."""

    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        closing = next(
            index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"
        )
    except StopIteration:
        return {}
    try:
        loaded = yaml.safe_load("\n".join(lines[1:closing])) or {}
    except yaml.YAMLError:
        return {}
    return dict(loaded) if isinstance(loaded, Mapping) else {}


def _safe_url_component(value: str, *, field: str) -> str:
    """Validate one Hugo path component without changing its Unicode spelling."""

    if not value or value != value.strip():
        raise ValueError(f"{field} must be a non-empty trimmed path component")
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"{field} must not contain path traversal or separators")
    if "://" in value or any(character in value for character in "?#"):
        raise ValueError(f"{field} must not contain a protocol, query, or fragment")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{field} must not contain control characters")
    return value


def canonical_note_url(meta: Mapping[str, Any], filename: str, title: str = "") -> str:
    """Return the URL Hugo will publish for a note."""

    del title  # Titles are editorial data and never stable URL material.
    explicit_slug = meta.get("slug")
    if explicit_slug is not None:
        if not isinstance(explicit_slug, str):
            raise ValueError("slug must be a string")
        component = _safe_url_component(explicit_slug, field="slug")
    else:
        path = Path(filename)
        if path.name != filename or path.suffix.lower() != ".md":
            raise ValueError("filename must be one Markdown basename")
        component = _safe_url_component(path.stem, field="filename stem")
    return f"/notas/{component}/"


def _write_json_atomically(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def main() -> None:
    notas: list[dict[str, str]] = []
    if not CONTENT_DIR.exists():
        print("No content/notas dir")
        return

    for source_path in sorted(CONTENT_DIR.glob("*.md")):
        if source_path.name == "_index.md":
            continue
        content = source_path.read_text(encoding="utf-8")
        meta = parse_front_matter(content)
        title = str(meta.get("title", ""))
        date = str(meta.get("date", ""))[:10]
        description = str(meta.get("description", ""))[:200]
        if not title:
            continue
        notas.append(
            {
                "title": title,
                "date": date,
                "description": description,
                "url": canonical_note_url(meta, source_path.name, title),
            }
        )

    output_path = BASE_DIR / "static" / "notas" / "index.json"
    _write_json_atomically(output_path, notas)
    print(f"index.json generado con {len(notas)} notas en static/notas/")


if __name__ == "__main__":
    main()
