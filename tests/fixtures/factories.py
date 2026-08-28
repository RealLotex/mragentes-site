from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


FIXED_NOW = datetime(2026, 8, 26, 15, 0, tzinfo=UTC)


def news_item(
    *,
    item_id: str = "news-v1-8b714b8c",
    title: str = "Un laboratorio publica un modelo verificable",
    url: str = "https://example.test/news/modelo?utm_source=rss",
    published_at: str = "2026-08-24T13:30:00Z",
    status: str = "pending",
    source: str = "Example Research",
    entity: str = "Example Lab",
    evidence: list[dict[str, str]] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "schema_version": 1,
        "id": item_id,
        "title": title,
        "canonical_url": url,
        "source": source,
        "entity": entity,
        "published_at": published_at,
        "discovered_at": "2026-08-26T12:00:00Z",
        "status": status,
        "evidence": evidence
        if evidence is not None
        else [
            {
                "url": "https://example.test/research/model-card",
                "claim": "La ficha técnica identifica el modelo y la fecha de publicación.",
            }
        ],
        "tags": ["ia", "modelos"],
    }
    item.update(overrides)
    return item


def queue_document(*items: dict[str, Any], revision: int = 1) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "revision": revision,
        "updated_at": "2026-08-26T12:00:00Z",
        "items": list(items),
    }


def social_draft(*, kind: str = "daily_owned", **overrides: Any) -> dict[str, Any]:
    draft: dict[str, Any] = {
        "schema_version": 1,
        "run_id": "social-daily-owned-2026-08-26",
        "kind": kind,
        "topic": "Cómo validar una automatización antes de publicarla",
        "topic_hash": "sha256:topic-41b6",
        "content_hash": "sha256:content-92a1",
        "dedupe_key": "daily_owned:2026-08-26:sha256:content-92a1",
        "asset": {
            "path": "static/images/social/generated/daily-owned-2026-08-26.png",
            "sha256": "a" * 64,
            "alt": "Lista visual de controles para validar una automatización.",
        },
        "captions": {
            "facebook": "Validar antes de publicar evita retrabajo. Más información en el sitio.",
            "instagram": "Validar antes de publicar evita retrabajo. #Automatización #IA",
        },
        "created_at": "2026-08-26T12:00:00Z",
    }
    draft.update(overrides)
    return draft


def run_report(*, run_id: str = "news-2026-08-26", status: str = "running") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": run_id,
        "kind": "news",
        "status": status,
        "started_at": "2026-08-26T12:00:00Z",
        "finished_at": None,
        "checks": [],
        "effects": [],
        "summary": {},
    }


def write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def init_git_repo(path: Path) -> Path:
    """Create an empty directory; individual tests run the guarded git commands."""
    path.mkdir(parents=True, exist_ok=True)
    return path
