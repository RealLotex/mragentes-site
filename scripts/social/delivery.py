"""Idempotent, testing-only delivery of validated social drafts to Meta."""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path
from typing import Any, Callable, Mapping

from scripts.automation import social_guard

from . import copy as copywriter
from . import ledger
from .config import Settings
from .notas import Nota
from .publisher import Meta, Result, head_ok


RECONCILIATION_TOLERANCE_SECONDS = 4 * 60 * 60


def build_blog_note_draft(
    note: Nota,
    *,
    deploy_sha: str,
    root: Path,
    created_at: str,
    site_base_url: str = "https://mragentes.com.ar",
) -> dict[str, Any]:
    """Build the transient social contract for one already-deployed note."""

    if not isinstance(note, Nota):
        raise TypeError("note must be a parsed Nota")
    if not note.image or not note.image.startswith("/images/stock/"):
        raise ValueError("blog note must declare a deployed stock cover")
    relative_asset = "static/" + note.image.lstrip("/")
    repository_root = Path(root).resolve()
    asset_path = (repository_root / relative_asset).resolve()
    try:
        asset_path.relative_to(repository_root / "static" / "images" / "stock")
    except ValueError as exc:
        raise ValueError("blog cover escaped the stock image allowlist") from exc
    if not asset_path.is_file() or asset_path.suffix.casefold() not in {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
    }:
        raise ValueError("blog cover does not exist or has an unsupported format")

    created = _timestamp(created_at)
    if created.date() != note.date:
        raise ValueError("blog social draft date differs from the note publication date")
    topic_hash = "sha256:" + hashlib.sha256(note.title.encode("utf-8")).hexdigest()
    draft: dict[str, Any] = {
        "schema_version": 1,
        "run_id": social_guard.social_run_id(
            note.date.isoformat(), "blog_note", subject=note.slug
        ),
        "kind": "blog_note",
        "topic": note.title,
        "topic_hash": topic_hash,
        "content_hash": "pending",
        "dedupe_key": "pending",
        "asset": {
            "path": relative_asset,
            "sha256": hashlib.sha256(asset_path.read_bytes()).hexdigest(),
            "alt": note.image_alt or f"Imagen principal de {note.title}",
        },
        "captions": {
            "facebook": copywriter.caption(note, "facebook", site_base_url),
            "instagram": copywriter.caption(note, "instagram", site_base_url),
        },
        "created_at": created_at,
        "note_slug": note.slug,
        "note_url": note.url(site_base_url),
        "deploy_sha": deploy_sha,
    }
    draft["content_hash"] = social_guard.content_hash(draft)
    draft["dedupe_key"] = (
        f"blog_note:{note.date.isoformat()}:{draft['content_hash']}"
    )
    return social_guard.validate_social_draft(draft)


def _timestamp(value: str) -> dt.datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = dt.datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return parsed


def _asset_url(settings: Settings, relative_path: str) -> str:
    if not relative_path.startswith("static/"):
        raise ValueError("social asset must be served from static/")
    return f"{settings.site_base_url.rstrip('/')}/{relative_path.removeprefix('static/')}"


def _caption_hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _confirmed(entry: Mapping[str, Any]) -> list[str]:
    platforms = entry.get("platforms", {})
    return [
        platform
        for platform in ledger.PLATFORMS
        if isinstance(platforms.get(platform), Mapping)
        and platforms[platform].get("status") == "confirmed"
    ]


def _mark_failure(
    ledger_path: Path,
    *,
    dedupe_key: str,
    platform: str,
    result: Result,
    now: str,
) -> dict[str, Any]:
    category = result.category
    if category not in {"retryable", "permanent", "uncertain"}:
        category = "permanent"
    reason = result.error or result.error_code or result.skipped or "remote publication failed"
    return ledger.mark_partial(
        ledger_path,
        dedupe_key=dedupe_key,
        platform=platform,
        category=category,
        reason=reason,
        now=now,
    )


def _find_remote(
    meta: Meta,
    platform: str,
    draft: Mapping[str, Any],
) -> dict[str, Any]:
    created = _timestamp(str(draft["created_at"]))
    since = (created - dt.timedelta(seconds=RECONCILIATION_TOLERANCE_SECONDS)).isoformat()
    recent = meta.recent_publications(platform, since=since, limit=25)
    return ledger.find_recent_match(
        {
            "platform": platform,
            "caption_hash": _caption_hash(str(draft["captions"][platform])),
            "created_at": str(draft["created_at"]),
        },
        recent,
        tolerance_seconds=RECONCILIATION_TOLERANCE_SECONDS,
    )


def deliver_draft(
    draft: dict[str, Any],
    *,
    settings: Settings,
    root: Path,
    ledger_path: Path,
    meta: Meta | None = None,
    public_probe: Callable[[str], bool] = head_ok,
    now: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Reconcile and publish each platform exactly once whenever provable."""

    validated = social_guard.validate_social_draft(draft)
    expected_content_hash = social_guard.content_hash(validated)
    if validated["content_hash"] != expected_content_hash:
        raise ValueError("draft content hash does not match its material payload")

    repository_root = Path(root).resolve()
    asset_path = (repository_root / validated["asset"]["path"]).resolve()
    try:
        asset_path.relative_to(repository_root)
    except ValueError as exc:
        raise ValueError("asset escaped the repository root") from exc
    if not asset_path.is_file():
        raise ValueError("social asset does not exist")
    actual_asset_hash = hashlib.sha256(asset_path.read_bytes()).hexdigest()
    if actual_asset_hash != validated["asset"]["sha256"]:
        raise ValueError("social asset hash does not match the draft")

    if (
        not settings.enabled
        or settings.dry_run
        or not settings.is_testing
        or not settings.can_post_facebook
        or not settings.can_post_instagram
    ):
        raise PermissionError("remote delivery requires both Meta accounts in testing mode")

    public_url = _asset_url(settings, validated["asset"]["path"])
    if not public_probe(public_url):
        raise ValueError("social asset is not publicly available yet")

    clock = now or (lambda: dt.datetime.now(dt.UTC).isoformat())
    observed_at = clock()
    _timestamp(observed_at)
    dedupe_key = "social:" + validated["dedupe_key"]
    acquisition = ledger.acquire(
        ledger_path,
        dedupe_key=dedupe_key,
        content_hash=validated["content_hash"],
        kind=validated["kind"],
        local_date=_timestamp(validated["created_at"]).date().isoformat(),
        run_id=validated["run_id"],
        now=observed_at,
    )
    entry = acquisition["entry"]
    if acquisition["decision"] == "skip_complete":
        return {"status": "complete", "confirmed": _confirmed(entry), "dedupe_key": dedupe_key}

    client = meta or Meta(settings)
    initial_run = acquisition["decision"] == "acquired"
    needs_review: list[str] = []

    for platform in ledger.PLATFORMS:
        state = entry["platforms"][platform]
        if state["status"] == "confirmed":
            continue

        must_reconcile = initial_run or state["status"] == "uncertain"
        if must_reconcile:
            try:
                match = _find_remote(client, platform, validated)
            except Exception as exc:  # remote read ambiguity is never permission to publish
                if state["status"] == "pending":
                    entry = ledger.mark_partial(
                        ledger_path,
                        dedupe_key=dedupe_key,
                        platform=platform,
                        category="uncertain",
                        reason=f"reconciliation failed: {type(exc).__name__}",
                        now=clock(),
                    )
                needs_review.append(platform)
                continue
            if match["decision"] == "matched":
                remote = match["match"]
                entry = ledger.checkpoint(
                    ledger_path,
                    dedupe_key=dedupe_key,
                    platform=platform,
                    remote_id=str(remote["remote_id"]),
                    permalink=str(remote.get("permalink", "")),
                    now=clock(),
                )
                continue
            if match["decision"] == "needs_review" or state["status"] == "uncertain":
                if state["status"] == "pending":
                    entry = ledger.mark_partial(
                        ledger_path,
                        dedupe_key=dedupe_key,
                        platform=platform,
                        category="uncertain",
                        reason="ambiguous remote reconciliation",
                        now=clock(),
                    )
                needs_review.append(platform)
                continue

        plan = ledger.recovery_plan(entry)
        if plan["decision"] == "needs_review" or platform not in plan.get("platforms", []):
            needs_review.append(platform)
            continue

        caption = validated["captions"][platform]
        result = (
            client.facebook_photo(asset_path, caption)
            if platform == "facebook"
            else client.instagram_image(public_url, caption)
        )
        if result.ok and result.id:
            entry = ledger.checkpoint(
                ledger_path,
                dedupe_key=dedupe_key,
                platform=platform,
                remote_id=result.id,
                permalink=result.url,
                now=clock(),
            )
        else:
            entry = _mark_failure(
                ledger_path,
                dedupe_key=dedupe_key,
                platform=platform,
                result=result,
                now=clock(),
            )
            if result.category != "retryable":
                needs_review.append(platform)

    confirmed = _confirmed(entry)
    if len(confirmed) == len(ledger.PLATFORMS):
        entry = ledger.complete(ledger_path, dedupe_key=dedupe_key, now=clock())
        return {"status": "complete", "confirmed": confirmed, "dedupe_key": dedupe_key}
    if needs_review or any(
        entry["platforms"][platform]["status"] == "uncertain"
        for platform in ledger.PLATFORMS
    ):
        return {
            "status": "needs_review",
            "confirmed": confirmed,
            "needs_review": sorted(set(needs_review)),
            "dedupe_key": dedupe_key,
        }
    return {
        "status": "partial",
        "confirmed": confirmed,
        "retryable": [
            platform
            for platform in ledger.PLATFORMS
            if entry["platforms"][platform].get("category") == "retryable"
        ],
        "dedupe_key": dedupe_key,
    }


__all__ = ["build_blog_note_draft", "deliver_draft"]
