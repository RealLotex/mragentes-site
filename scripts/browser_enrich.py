#!/usr/bin/env python3
"""Local adapter for article text collected by the connected browser.

This module deliberately owns no HTTP transport. Codex/browser connectors
collect source material; this adapter cleans that supplied text and can merge
it into a local draft before the guarded blog transaction.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
CONTENT_DIR = os.path.join(BASE_DIR, "content", "notas")
ENRICH_FILE = os.path.join(SCRIPTS_DIR, "_browser_enrich.json")
TRENDS_FILE = os.path.join(SCRIPTS_DIR, "_last_trends.json")


def clean_extracted_html(
    value: str | bytes,
    *,
    charset: str = "utf-8",
    max_chars: int = 5000,
) -> str:
    """Normalize connector-supplied HTML/text without contacting its URL."""

    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 1:
        raise ValueError("max_chars must be a positive integer")
    if isinstance(value, bytes):
        try:
            source = value.decode(charset, errors="replace")
        except LookupError as exc:
            raise ValueError("unknown source charset") from exc
    elif isinstance(value, str):
        source = value
    else:
        raise TypeError("extracted content must be text or bytes")
    for element in ("script", "style", "header", "footer", "nav"):
        source = re.sub(
            rf"<{element}[^>]*>.*?</{element}>", "", source, flags=re.DOTALL | re.IGNORECASE
        )
    source = re.sub(r"<!--.*?-->", "", source, flags=re.DOTALL)
    source = re.sub(r"<[^>]+>", " ", source)
    source = html.unescape(source)
    source = re.sub(r"\s+", " ", source).strip()
    return source[:max_chars]


def extract_meaningful_paragraphs(text: str | None, min_len: int = 40) -> list[str]:
    if not text:
        return []
    navigation = {
        "cookie", "suscrib", "newsletter", "publicidad", "derechos reservados",
        "compartir", "facebook", "twitter", "instagram", "linkedin", "tiktok",
        "menú", "navegación", "política de privacidad", "últimas noticias",
    }
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚ\"'“])", text)
    meaningful = [
        sentence.strip()
        for sentence in sentences
        if len(sentence.strip()) >= min_len
        and not any(marker in sentence.casefold() for marker in navigation)
    ]
    return meaningful


def parse_enrich_file(enrich_path: str = ENRICH_FILE) -> dict[str, Any] | None:
    if not os.path.exists(enrich_path):
        print(f"❌ No se encuentra {enrich_path}")
        return None
    with open(enrich_path, encoding="utf-8") as stream:
        loaded = json.load(stream)
    if not isinstance(loaded, dict):
        raise ValueError("enrichment root must be a mapping")
    return loaded


def enrich_trends_from_records(trends: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Clean already-collected records and classify missing evidence explicitly."""

    enriched: list[dict[str, Any]] = []
    for raw in deepcopy(list(trends)):
        if not isinstance(raw, dict):
            raise ValueError("trend must be a mapping")
        title = str(raw.get("title", ""))
        source = str(raw.get("source", ""))
        url = str(raw.get("url", ""))
        supplied = raw.get("content", raw.get("extracted_content"))
        content = clean_extracted_html(supplied) if isinstance(supplied, (str, bytes)) else ""
        paragraphs = extract_meaningful_paragraphs(content)
        enriched.append(
            {
                "title": title,
                "source": source,
                "url": url,
                "resolved_url": str(raw.get("resolved_url", url)),
                "content": content,
                "paragraphs": paragraphs,
                "status": "ok" if content else "unreachable",
            }
        )
    return enriched


def update_nota_with_enriched(
    enriched_data: dict[str, Any] | str,
    nota_filepath: str | None = None,
) -> bool:
    if isinstance(enriched_data, str):
        with open(enriched_data, encoding="utf-8") as stream:
            enrich = json.load(stream)
    else:
        enrich = deepcopy(enriched_data)
    note = nota_filepath
    if not note and isinstance(enrich, dict) and enrich.get("nota_file"):
        note = os.path.join(CONTENT_DIR, str(enrich["nota_file"]))
    if not note or not os.path.exists(note):
        print(f"❌ No se encuentra la nota: {note}")
        return False
    path = Path(note)
    text = path.read_text(encoding="utf-8")
    for index, trend in enumerate(enrich.get("trends", []), start=1):
        paragraphs = trend.get("paragraphs", []) if isinstance(trend, dict) else []
        if not paragraphs:
            continue
        title = str(trend.get("title", ""))
        source = str(trend.get("source", ""))
        marker = f"### {index}. {title}"
        position = text.find(marker)
        if position < 0:
            continue
        end_candidates = [
            candidate for candidate in (text.find("\n### ", position + 1), text.find("\n---", position + 1))
            if candidate >= 0
        ]
        end = min(end_candidates) if end_candidates else len(text)
        quote = str(paragraphs[0]).strip()[:250]
        replacement = (
            f"{marker}\n*Fuente: {source}*\n> {quote}\n\n"
            f"Según el reportaje de {source}, {quote[0].lower() + quote[1:] if quote else ''}\n\n"
            f"*Contenido extraído directamente del artículo de {source}.*\n"
        )
        text = text[:position] + replacement + text[end:]
    path.write_text(text, encoding="utf-8")
    print(f"✅ Nota actualizada: {path}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Procesar evidencia ya recolectada por el conector")
    parser.add_argument("--enrich-file", default=ENRICH_FILE)
    parser.add_argument("--update", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    enrich = parse_enrich_file(args.enrich_file)
    if not enrich:
        return 1
    enriched = enrich_trends_from_records(enrich.get("trends", []))
    enrich["trends"] = enriched
    enrich["enriched_at"] = datetime.datetime.now(datetime.UTC).isoformat()
    if args.dry_run:
        return 0
    output = Path(args.enrich_file).with_name(Path(args.enrich_file).stem + "_enriched.json")
    output.write_text(json.dumps(enrich, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    note = args.update or str(enrich.get("nota_file", ""))
    if note:
        note_path = Path(note) if Path(note).is_absolute() else Path(CONTENT_DIR) / note
        if note_path.exists():
            update_nota_with_enriched(enrich, str(note_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
