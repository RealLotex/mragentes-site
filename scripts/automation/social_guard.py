"""Pure validation, freshness and recovery rules for MR Agentes social runs."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from scripts.automation.editorial_style import validate_formal_text


_KINDS = {"daily_owned", "blog_note"}
_PLATFORMS = {"facebook", "instagram"}
_BASE_FIELDS = {
    "schema_version",
    "run_id",
    "kind",
    "topic",
    "topic_hash",
    "content_hash",
    "dedupe_key",
    "asset",
    "captions",
    "created_at",
}
_BLOG_FIELDS = {"note_slug", "note_url", "deploy_sha"}


def _local_date(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("local date must be text")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("local date must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError("local date must be canonical YYYY-MM-DD")
    return value


def _timestamp(value: Any, field: str = "timestamp") -> datetime:
    if not isinstance(value, str) or not re.search(r"(?:Z|[+-]\d{2}:\d{2})$", value):
        raise ValueError(f"{field} must be an RFC3339 timestamp with timezone")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"{field} is not a real timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def _text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    if len(value) > maximum or "\x00" in value:
        raise ValueError(f"{field} exceeds its limit")
    return value


def _caption_text(value: Any, field: str, maximum: int) -> str:
    """Reject text that was serialized twice before it reaches Meta.

    JSON represents a real paragraph break as ``\\n`` in the file and the
    JSON decoder turns it back into a newline.  A second serialization leaves
    the two literal characters ``\\`` and ``n`` in the decoded caption, which
    Meta correctly publishes verbatim.  Social captions never need that
    notation, so reject it at the closed-draft boundary instead of silently
    publishing malformed copy.
    """

    text = _text(value, field, maximum)
    if "\\n" in text or "\\r" in text:
        raise ValueError(f"{field} contains serialized line-break characters")
    return text


def _note_slug(value: Any) -> str:
    slug = _text(value, "note_slug", 250)
    if (
        slug.startswith("-")
        or slug.endswith("-")
        or "--" in slug
        or any(not (character.isalnum() or character == "-") for character in slug)
    ):
        raise ValueError("note_slug must be one canonical Unicode slug component")
    return slug


def social_run_id(local_date: str, kind: str, *, subject: str | None = None) -> str:
    """Build distinct retry identities for original daily pieces and blog notes."""

    local_date = _local_date(local_date)
    if kind not in _KINDS:
        raise ValueError("unsupported social kind")
    if kind == "daily_owned":
        if subject is not None:
            raise ValueError("daily_owned does not accept a blog subject")
        return f"social:daily_owned:{local_date}"
    try:
        subject = _note_slug(subject)
    except ValueError as exc:
        raise ValueError("blog_note requires a canonical subject slug") from exc
    return f"social:blog_note:{local_date}:{subject}"


def content_hash(draft: dict[str, Any]) -> str:
    """Hash the material social payload independently of mapping insertion order."""

    if not isinstance(draft, dict):
        raise TypeError("draft must be a mapping")
    asset = draft.get("asset") if isinstance(draft.get("asset"), dict) else {}
    material = {
        "kind": draft.get("kind"),
        "topic": draft.get("topic"),
        "captions": draft.get("captions"),
        "asset": {
            "path": asset.get("path"),
            "sha256": asset.get("sha256"),
            "alt": asset.get("alt"),
        },
        "note_slug": draft.get("note_slug"),
        "note_url": draft.get("note_url"),
        "deploy_sha": draft.get("deploy_sha"),
    }
    encoded = json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _public_note_url(value: Any) -> str:
    text = _text(value, "note_url", 2048)
    parsed = urlsplit(text)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.hostname.casefold() != "mragentes.com.ar"
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("note_url must be the public canonical MR Agentes HTTPS URL")
    return text


def validate_social_draft(draft: dict[str, Any]) -> dict[str, Any]:
    """Validate a closed, remote-result-free social draft without mutating it."""

    if not isinstance(draft, dict):
        raise TypeError("social draft must be a mapping")
    kind = draft.get("kind")
    if kind not in _KINDS:
        raise ValueError("unsupported social kind")
    expected_fields = _BASE_FIELDS | (_BLOG_FIELDS if kind == "blog_note" else set())
    if set(draft) != expected_fields:
        raise ValueError("social draft does not match its closed schema")
    result = deepcopy(draft)
    version = result["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise TypeError("schema_version must be an integer")
    if version != 1:
        raise ValueError("unsupported social schema version")
    result["run_id"] = _text(result["run_id"], "run_id", 250)
    result["topic"] = _text(result["topic"], "topic", 500)
    result["topic_hash"] = _text(result["topic_hash"], "topic_hash", 200)
    result["content_hash"] = _text(result["content_hash"], "content_hash", 200)

    created_at = _timestamp(result["created_at"], "created_at")
    created_date = created_at.date().isoformat()
    if created_date not in result["run_id"]:
        raise ValueError("created_at local date differs from run identity")
    expected_dedupe = f"{kind}:{created_date}:{result['content_hash']}"
    if result["dedupe_key"] != expected_dedupe:
        raise ValueError("dedupe_key differs from kind, date or content hash")

    asset = result["asset"]
    if not isinstance(asset, dict) or set(asset) != {"path", "sha256", "alt"}:
        raise ValueError("asset must contain only path, sha256 and alt")
    asset_path = Path(str(asset["path"]))
    if (
        asset_path.is_absolute()
        or ".." in asset_path.parts
        or asset_path.as_posix() == "."
        or not (
            asset_path.as_posix().startswith("static/images/social/")
            or (
                kind == "blog_note"
                and asset_path.as_posix().startswith("static/images/stock/")
            )
        )
        or asset_path.suffix.casefold() not in {".png", ".jpg", ".jpeg", ".webp"}
    ):
        raise ValueError("asset path is outside the social image allowlist")
    if not isinstance(asset["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"]):
        raise ValueError("asset sha256 is malformed")
    asset["alt"] = _text(asset["alt"], "asset alt", 500)

    captions = result["captions"]
    if not isinstance(captions, dict) or set(captions) != _PLATFORMS:
        raise ValueError("both platform-specific captions are required")
    facebook = _caption_text(captions["facebook"], "facebook caption", 63_206)
    instagram = _caption_text(captions["instagram"], "instagram caption", 2_200)
    if facebook.strip() == instagram.strip():
        raise ValueError("platform captions must be tailored separately")
    validate_formal_text(result["topic"], field="social topic")
    validate_formal_text(facebook, field="facebook caption")
    validate_formal_text(instagram, field="instagram caption")

    if kind == "blog_note":
        result["note_slug"] = _note_slug(result["note_slug"])
        result["note_url"] = _public_note_url(result["note_url"])
        if not isinstance(result["deploy_sha"], str) or not re.fullmatch(
            r"[0-9a-f]{40}", result["deploy_sha"]
        ):
            raise ValueError("deploy_sha must be a full Git commit hash")
    return result


def _records_source(records: Iterable[dict[str, Any]] | str | Path) -> list[dict[str, Any]]:
    if isinstance(records, (str, Path)):
        path = Path(records)
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("recent record file is corrupt") from exc
    else:
        loaded = list(records)
    if not isinstance(loaded, list) or any(not isinstance(record, dict) for record in loaded):
        raise ValueError("recent records must be a list of mappings")
    return deepcopy(loaded)


def recent_topic_hashes(
    records: Iterable[dict[str, Any]] | str | Path,
    since: str,
    *,
    kind: str = "daily_owned",
) -> set[str]:
    """Read topic hashes for one kind at or after an inclusive timestamp."""

    if kind not in _KINDS:
        raise ValueError("unsupported social kind")
    boundary = _timestamp(since, "since")
    hashes: set[str] = set()
    for record in _records_source(records):
        if record.get("kind") != kind:
            continue
        created = _timestamp(record.get("created_at"), "record created_at")
        topic_hash = record.get("topic_hash")
        if created >= boundary:
            hashes.add(_text(topic_hash, "topic_hash", 200))
    return hashes


def _normalize_topic(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.findall(r"[a-z0-9]+", normalized.casefold()))


def ensure_fresh(
    draft: dict[str, Any],
    recent_records: Iterable[dict[str, Any]] | str | Path,
    *,
    now: str | None = None,
    window_days: int = 30,
    collision_policy: str = "error",
) -> dict[str, Any]:
    """Reject recent topic/copy/media reuse and stop on suspected hash collisions."""

    if isinstance(window_days, bool) or not isinstance(window_days, int) or window_days < 1:
        raise ValueError("window_days must be a positive integer")
    records = _records_source(recent_records)
    reference = _timestamp(now or draft.get("created_at"), "now")
    boundary = reference - timedelta(days=window_days)
    relevant: list[dict[str, Any]] = []
    for record in records:
        created = _timestamp(record.get("created_at"), "record created_at")
        if boundary <= created <= reference:
            relevant.append(record)
    relevant.sort(
        key=lambda record: (
            str(record.get("created_at", "")),
            str(record.get("kind", "")),
            str(record.get("topic_hash", "")),
            str(record.get("content_hash", "")),
        )
    )

    draft_topic = _normalize_topic(draft.get("topic"))
    draft_topic_hash = draft.get("topic_hash")
    for record in relevant:
        same_topic_hash = record.get("topic_hash") == draft_topic_hash
        record_topic = _normalize_topic(record.get("topic"))
        if same_topic_hash and record_topic and draft_topic and record_topic != draft_topic:
            if collision_policy == "needs_review":
                return {
                    "fresh": False,
                    "status": "needs_review",
                    "reason": "topic_hash_collision",
                }
            raise ValueError("topic hash collision requires review")
        if same_topic_hash or (record_topic and draft_topic and record_topic == draft_topic):
            raise ValueError("topic was used inside the freshness window")
        if record.get("kind") != draft.get("kind"):
            continue
        if record.get("content_hash") == draft.get("content_hash"):
            raise ValueError("content was used inside the freshness window")
        asset = draft.get("asset") if isinstance(draft.get("asset"), dict) else {}
        if record.get("asset_sha256") == asset.get("sha256"):
            raise ValueError("asset was used inside the freshness window")
    return {"fresh": True, "status": "fresh", "checked": len(relevant)}


def classify_completion(
    platforms: Iterable[str],
    records: Iterable[dict[str, Any]],
    *,
    dedupe_key: str | None = None,
) -> dict[str, Any]:
    """Classify durable checkpoints without turning uncertainty into a retry."""

    ordered_platforms = list(platforms)
    if (
        len(ordered_platforms) != len(set(ordered_platforms))
        or any(platform not in _PLATFORMS for platform in ordered_platforms)
    ):
        raise ValueError("platform set is invalid")
    completed_ids: dict[str, set[str]] = {platform: set() for platform in ordered_platforms}
    uncertain: set[str] = set()
    for record in deepcopy(list(records)):
        if not isinstance(record, dict) or "platform" not in record or "status" not in record:
            raise ValueError("completion record is malformed")
        platform = record["platform"]
        status = record["status"]
        if platform not in ordered_platforms or status not in {"complete", "failed"}:
            raise ValueError("completion record has unknown platform or status")
        if dedupe_key is not None and record.get("dedupe_key") != dedupe_key:
            continue
        if status == "complete":
            remote_id = _text(record.get("remote_id"), "remote_id", 300)
            completed_ids[platform].add(remote_id)
            continue
        phase = record.get("phase")
        if phase not in {"before_remote", "after_remote_create"}:
            raise ValueError("failed checkpoint phase is unknown")
        if phase == "after_remote_create":
            uncertain.add(platform)

    conflicts = {
        platform: sorted(remote_ids)
        for platform, remote_ids in completed_ids.items()
        if len(remote_ids) > 1
    }
    completed = [
        platform for platform in ordered_platforms if len(completed_ids[platform]) == 1
    ]
    uncertain.difference_update(completed)
    missing = [
        platform
        for platform in ordered_platforms
        if platform not in completed and platform not in uncertain and platform not in conflicts
    ]
    if conflicts:
        status = "needs_review"
    elif uncertain:
        status = "uncertain"
    elif len(completed) == len(ordered_platforms):
        status = "complete"
    elif completed:
        status = "partial"
    else:
        status = "none"
    result: dict[str, Any] = {
        "status": status,
        "completed": completed,
        "missing": missing,
        "uncertain": [platform for platform in ordered_platforms if platform in uncertain],
    }
    if conflicts:
        result["conflicts"] = conflicts
    return result


def recovery_plan(
    completion: dict[str, Any], remote_matches: dict[str, list[str]]
) -> dict[str, Any]:
    """Return a no-force recovery plan; uncertainty is reconciled before publishing."""

    if not isinstance(completion, dict) or not isinstance(remote_matches, dict):
        raise TypeError("completion and remote_matches must be mappings")
    force = False
    completed = list(completion.get("completed", []))
    missing = list(completion.get("missing", []))
    uncertain = list(completion.get("uncertain", []))
    if completion.get("status") == "needs_review":
        return {
            "status": "needs_review",
            "publish": [],
            "checkpoint": [],
            "skip": completed,
            "force": force,
        }
    if uncertain:
        checkpoints: list[dict[str, str]] = []
        for platform in uncertain:
            matches = remote_matches.get(platform, [])
            if not isinstance(matches, list) or len(matches) != 1 or not matches[0]:
                return {
                    "status": "needs_review",
                    "publish": [],
                    "checkpoint": [],
                    "skip": completed,
                    "force": force,
                }
            checkpoints.append({"platform": platform, "remote_id": matches[0]})
        return {
            "status": "reconcile",
            "publish": [],
            "checkpoint": checkpoints,
            "skip": completed,
            "force": force,
        }
    if completion.get("status") == "complete":
        return {
            "status": "complete",
            "publish": [],
            "checkpoint": [],
            "skip": completed,
            "force": force,
        }
    return {
        "status": "retry",
        "publish": missing,
        "checkpoint": [],
        "skip": completed,
        "force": force,
    }
