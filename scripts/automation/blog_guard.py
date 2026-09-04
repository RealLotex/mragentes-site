"""Pure editorial guards used before any Git or external side effect."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import shutil
import tempfile
import unicodedata
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml


_SEPARATOR_RE = re.compile(r"[^a-z0-9]+")
_AUTOMATION_ID_RE = re.compile(
    r"^blog:(?P<date>\d{4}-\d{2}-\d{2}):(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)$"
)
_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
_EDITORIAL_PILLARS = frozenset({
    "automatizacion-practica",
    "control-y-gobernanza",
    "casos-para-pymes",
})
_FRONT_MATTER_FIELDS = {
    "schema_version",
    "title",
    "date",
    "description",
    "image",
    "image_alt",
    "tags",
    "pillar",
    "sources",
    "automation_id",
    "slug",
    "draft",
    "aliases",
}


def _ascii_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", errors="ignore").decode("ascii").lower()
    return _SEPARATOR_RE.sub("-", ascii_text).strip("-")


def portable_slug(
    title: str,
    max_component_bytes: int = 143,
    prefix: str = "",
    suffix: str = "",
    *,
    already_slug: bool = False,
    legacy_path: str | None = None,
) -> str | dict[str, Any]:
    """Return an ASCII slug whose complete filename fits one component.

    Long slugs retain a readable prefix plus a hash derived from the complete
    normalized value. This makes truncation deterministic and prevents titles
    with a common prefix from colliding.
    """

    if not isinstance(title, str) or not isinstance(prefix, str) or not isinstance(suffix, str):
        raise TypeError("title, prefix and suffix must be strings")
    if isinstance(max_component_bytes, bool) or not isinstance(max_component_bytes, int):
        raise TypeError("max_component_bytes must be an integer")
    if max_component_bytes <= 0:
        raise ValueError("max_component_bytes must be positive")

    slug = _ascii_slug(title)
    if not slug:
        raise ValueError("title does not contain portable slug characters")
    reserved = len(prefix.encode("utf-8")) + len(suffix.encode("utf-8"))
    available = max_component_bytes - reserved
    if available <= 0:
        raise ValueError("prefix and suffix exhaust the component budget")

    truncated = len(slug.encode("ascii")) > available
    if truncated:
        digest = hashlib.sha256(slug.encode("ascii")).hexdigest()[:10]
        readable_budget = available - len(digest) - 1
        if readable_budget < 1:
            raise ValueError("component budget cannot hold a readable collision-safe slug")
        readable = slug[:readable_budget].rstrip("-")
        if not readable:
            raise ValueError("component budget cannot hold a readable slug")
        slug = f"{readable}-{digest}"

    if len(f"{prefix}{slug}{suffix}".encode("utf-8")) > max_component_bytes:
        raise ValueError("portable slug exceeds component budget")

    if already_slug or legacy_path is not None:
        if legacy_path is not None:
            if not legacy_path.startswith("/") or "://" in legacy_path or ".." in legacy_path:
                raise ValueError("legacy_path must be an absolute site-local path")
        return {
            "slug": slug,
            "legacy_alias": legacy_path,
            "truncated": truncated,
        }
    return slug


def _validated_local_date(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("local_date must be text")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("local_date must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError("local_date must use canonical YYYY-MM-DD")
    return value


def blog_run_id(local_date: str, slug: str) -> str:
    """Build the stable identity shared by retries of one editorial run."""

    local_date = _validated_local_date(local_date)
    if not isinstance(slug, str) or _ascii_slug(slug) != slug or not slug:
        raise ValueError("slug must already be canonical ASCII")
    return f"blog:{local_date}:{slug}"


def _front_matter_from_note(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    try:
        closing = lines.index("---", 1)
    except ValueError:
        return {}
    loaded = yaml.safe_load("\n".join(lines[1:closing])) or {}
    return loaded if isinstance(loaded, dict) else {}


def find_existing_note(
    content_dir: str | Path,
    run_id: str,
    local_date: str,
) -> Path | None:
    """Find an idempotent prior note without relying on its filename."""

    directory = Path(content_dir)
    _validated_local_date(local_date)
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id is required")
    if not directory.exists():
        return None
    matches: list[Path] = []
    for path in sorted(directory.glob("*.md"), key=lambda item: item.name):
        front_matter = _front_matter_from_note(path)
        observed_date = str(front_matter.get("date", ""))[:10]
        if front_matter.get("automation_id") == run_id and observed_date == local_date:
            matches.append(path)
    if len(matches) > 1:
        raise ValueError(f"multiple notes use automation_id {run_id}")
    return matches[0] if matches else None


def _selection_tokens(item: dict[str, Any]) -> tuple[str, str, frozenset[str]]:
    source = str(item.get("source", "")).casefold().strip()
    entity = str(item.get("entity", "")).casefold().strip()
    tags = item.get("tags", [])
    normalized_tags = frozenset(
        str(tag).casefold().strip() for tag in tags if isinstance(tag, str) and tag.strip()
    ) if isinstance(tags, list) else frozenset()
    return source, entity, normalized_tags


def select_news(
    items: list[dict[str, Any]],
    run_id: str,
    count: int,
    *,
    minimum: int = 1,
) -> list[dict[str, Any]]:
    """Choose verified available items deterministically, favouring diversity."""

    if not isinstance(items, list):
        raise TypeError("items must be a list")
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeError("count must be an integer")
    if isinstance(minimum, bool) or not isinstance(minimum, int):
        raise TypeError("minimum must be an integer")
    if count < 0 or minimum < 0 or minimum > count:
        raise ValueError("invalid selection bounds")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id is required")

    available = [
        deepcopy(item)
        for item in items
        if isinstance(item, dict)
        and (
            item.get("status") == "pending"
            or (item.get("status") == "reserved" and item.get("reserved_by") == run_id)
        )
    ]
    available.sort(key=lambda item: str(item.get("id", "")))

    selected: list[dict[str, Any]] = []
    used_sources: set[str] = set()
    used_entities: set[str] = set()
    used_tags: set[str] = set()
    while available and len(selected) < count:
        def score(item: dict[str, Any]) -> tuple[int, int, int, str]:
            source, entity, tags = _selection_tokens(item)
            return (
                1 if entity and entity not in used_entities else 0,
                1 if source and source not in used_sources else 0,
                len(tags - used_tags),
                str(item.get("id", "")),
            )

        best_score = max(score(item)[:3] for item in available)
        candidates = [item for item in available if score(item)[:3] == best_score]
        chosen = min(candidates, key=lambda item: str(item.get("id", "")))
        available.remove(chosen)
        selected.append(chosen)
        source, entity, tags = _selection_tokens(chosen)
        if source:
            used_sources.add(source)
        if entity:
            used_entities.add(entity)
        used_tags.update(tags)

    return selected if len(selected) >= minimum else []


def build_front_matter(
    title: str,
    local_date: str,
    description: str,
    image: str,
    image_alt: str,
    tags: list[str],
    pillar: str,
    sources: list[str],
    automation_id: str,
    aliases: list[str] | None = None,
) -> dict[str, Any]:
    """Build and validate the closed front-matter contract for an automated note."""

    document: dict[str, Any] = {
        "schema_version": 1,
        "title": title,
        "date": f"{_validated_local_date(local_date)}T12:00:00-03:00",
        "description": description,
        "image": image,
        "image_alt": image_alt,
        "tags": list(tags),
        "pillar": pillar,
        "sources": list(sources),
        "automation_id": automation_id,
        "slug": automation_id.rsplit(":", 1)[-1],
        "draft": False,
        "aliases": list(aliases or []),
    }
    return validate_front_matter(document)


def _canonical_public_url(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("source URLs must be text")
    split = urlsplit(value)
    if split.scheme != "https" or not split.hostname or split.username or split.password:
        raise ValueError("sources must be public HTTPS URLs")
    try:
        address = ipaddress.ip_address(split.hostname)
    except ValueError:
        address = None
    if address is not None and (address.is_private or address.is_loopback or address.is_reserved):
        raise ValueError("sources must not address private networks")
    hostname = split.hostname.casefold()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("sources must not address localhost")
    port = split.port
    netloc = hostname if port in (None, 443) else f"{hostname}:{port}"
    clean_query = [
        (key, query_value)
        for key, query_value in parse_qsl(split.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_") and key.casefold() not in _TRACKING_QUERY_KEYS
    ]
    clean_query.sort()
    path = split.path or "/"
    return urlunsplit(("https", netloc, path, urlencode(clean_query), ""))


def _normalize_tag(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("tags must be text")
    if "<" in value or ">" in value or any(ord(character) < 32 for character in value):
        raise ValueError("tags must not contain markup or control characters")
    return _ascii_slug(value)


def validate_front_matter(front_matter: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized copy or fail closed on unknown and unsafe fields."""

    if not isinstance(front_matter, dict):
        raise TypeError("front_matter must be a mapping")
    if set(front_matter) != _FRONT_MATTER_FIELDS:
        raise ValueError("front matter fields do not match the closed schema")
    result = deepcopy(front_matter)
    if result["schema_version"] != 1 or isinstance(result["schema_version"], bool):
        raise ValueError("unsupported front matter schema")
    if not isinstance(result["title"], str) or not result["title"].strip():
        raise ValueError("title is required")
    if not isinstance(result["date"], str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T12:00:00-03:00", result["date"]
    ):
        raise ValueError("date must be Córdoba noon with an explicit offset")
    _validated_local_date(result["date"][:10])

    description = result["description"]
    if (
        not isinstance(description, str)
        or not description.strip()
        or len(description) > 160
        or "<" in description
        or ">" in description
    ):
        raise ValueError("description must be nonempty plain text up to 160 characters")

    image = result["image"]
    image_alt = result["image_alt"]
    if (
        not isinstance(image, str)
        or not image.startswith("/images/stock/")
        or ".." in Path(image).parts
        or Path(image).suffix.casefold() not in {".webp", ".png", ".jpg", ".jpeg"}
    ):
        raise ValueError("image must be a site-local stock asset")
    if not isinstance(image_alt, str) or not image_alt.strip() or "<" in image_alt or ">" in image_alt:
        raise ValueError("image_alt must be descriptive plain text")

    tags = result["tags"]
    if not isinstance(tags, list) or not tags or len(tags) > 20:
        raise ValueError("tags must contain between 1 and 20 values")
    normalized_tags: list[str] = []
    for tag in tags:
        normalized = _normalize_tag(tag)
        if not normalized or len(normalized) > 50 or normalized != _ascii_slug(normalized):
            raise ValueError("tag is invalid")
        if normalized not in normalized_tags:
            normalized_tags.append(normalized)
    result["tags"] = normalized_tags

    pillar = result["pillar"]
    if not isinstance(pillar, str) or pillar not in _EDITORIAL_PILLARS:
        raise ValueError("pillar must be one of the editorial pillars")
    result["pillar"] = pillar

    sources = result["sources"]
    if not isinstance(sources, list) or not sources:
        raise ValueError("sources cannot be empty")
    canonical_sources: list[str] = []
    for source in sources:
        canonical = _canonical_public_url(source)
        if canonical in canonical_sources:
            raise ValueError("sources must be canonically unique")
        canonical_sources.append(canonical)
    result["sources"] = canonical_sources

    automation_id = result["automation_id"]
    if not isinstance(automation_id, str):
        raise TypeError("automation_id must be text")
    match = _AUTOMATION_ID_RE.fullmatch(automation_id)
    if not match:
        raise ValueError("automation_id has an invalid format")
    if match.group("date") != result["date"][:10]:
        raise ValueError("automation_id date differs from publication date")

    slug = result["slug"]
    if (
        not isinstance(slug, str)
        or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug)
        or slug != match.group("slug")
    ):
        raise ValueError("slug must be the canonical ASCII component in automation_id")

    if result["draft"] is not False:
        raise ValueError("automated notes must never be drafts")
    aliases = result["aliases"]
    if not isinstance(aliases, list):
        raise TypeError("aliases must be a list")
    canonical_path = f"/notas/{match.group('date')}-{match.group('slug')}/"
    seen_aliases: set[str] = set()
    for alias in aliases:
        if (
            not isinstance(alias, str)
            or not alias.startswith("/notas/")
            or not alias.endswith("/")
            or "://" in alias
            or ".." in Path(alias).parts
            or "?" in alias
            or "#" in alias
            or alias == canonical_path
            or alias in seen_aliases
        ):
            raise ValueError("alias must be unique, absolute and site-local")
        seen_aliases.add(alias)
    return result


def _safe_destination(root: Path, relative: str | Path, allow_root: Path, suffixes: set[str]) -> Path:
    candidate_relative = Path(relative)
    if candidate_relative.is_absolute() or ".." in candidate_relative.parts:
        raise ValueError("destination must be a safe relative path")
    destination = root / candidate_relative
    try:
        destination.resolve(strict=False).relative_to(allow_root.resolve(strict=False))
    except ValueError as exc:
        raise ValueError("destination is outside its allowlisted directory") from exc
    if destination.suffix.casefold() not in suffixes:
        raise ValueError("destination extension is not allowlisted")
    return destination


def _asset_bytes(source: Path, suffix: str) -> bytes:
    if source.is_symlink():
        raise ValueError("asset source must not be a symlink")
    if not source.is_file():
        raise FileNotFoundError(f"asset source is not a regular file: {source}")
    content = source.read_bytes()
    if not content or len(content) > 15 * 1024 * 1024:
        raise ValueError("asset size is invalid")
    signatures = {
        ".webp": lambda value: value.startswith(b"RIFF") and b"WEBP" in value[:32],
        ".png": lambda value: value.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": lambda value: value.startswith(b"\xff\xd8\xff"),
        ".jpeg": lambda value: value.startswith(b"\xff\xd8\xff"),
    }
    if not signatures[suffix](content):
        raise ValueError("asset content does not match its extension")
    return content


def _artifact(path: Path, root: Path, content: bytes) -> dict[str, str]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def build_atomic_change(
    root: str | Path,
    run_id: str,
    note_relative_path: str | Path,
    note_content: str,
    asset_source: str | Path,
    asset_relative_path: str | Path,
    queue_path: str | Path,
    queue_document: dict[str, Any],
    *,
    apply: bool = False,
    replace: Any = os.replace,
) -> dict[str, Any]:
    """Apply the note, stock asset and queue update as one local transaction."""

    repository = Path(root).resolve(strict=True)
    if not isinstance(run_id, str) or not run_id or not isinstance(note_content, str):
        raise ValueError("run_id and note_content are required")
    note = _safe_destination(
        repository,
        note_relative_path,
        repository / "content" / "notas",
        {".md"},
    )
    asset = _safe_destination(
        repository,
        asset_relative_path,
        repository / "static" / "images" / "stock",
        {".webp", ".png", ".jpg", ".jpeg"},
    )
    queue = Path(queue_path)
    if not queue.is_absolute():
        queue = repository / queue
    queue_roots = (
        repository / "data",  # legacy fixture/consumer location
        repository / ".automation" / "news" / "queue",  # versioned automation contract
    )
    queue_resolved = queue.resolve(strict=False)
    if not any(
        queue_resolved.is_relative_to(root.resolve(strict=False)) for root in queue_roots
    ):
        raise ValueError("queue must stay in an allowlisted repository queue directory")
    if queue.suffix.casefold() != ".json":
        raise ValueError("queue must be JSON")

    note_bytes = note_content.encode("utf-8")
    asset_bytes = _asset_bytes(Path(asset_source), asset.suffix.casefold())
    queue_bytes = (
        json.dumps(queue_document, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    ).encode("utf-8")
    desired = {note: note_bytes, asset: asset_bytes, queue: queue_bytes}
    report = {
        "run_id": run_id,
        "status": "planned",
        "artifacts": {
            "note": _artifact(note, repository, note_bytes),
            "asset": _artifact(asset, repository, asset_bytes),
            "queue": _artifact(queue, repository, queue_bytes),
        },
    }

    for protected in (note, asset):
        if protected.exists() and protected.read_bytes() != desired[protected]:
            raise FileExistsError(f"refusing to overwrite existing artifact: {protected.name}")
    if all(path.is_file() and path.read_bytes() == content for path, content in desired.items()):
        report["status"] = "unchanged"
        return report
    if not apply:
        return report

    originals = {path: path.read_bytes() if path.exists() else None for path in desired}
    transaction = Path(tempfile.mkdtemp(prefix=".blog-txn-", dir=repository))
    staged: list[tuple[Path, Path]] = []
    try:
        for position, (destination, content) in enumerate(desired.items()):
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = transaction / f"{position}.tmp"
            temporary.write_bytes(content)
            staged.append((temporary, destination))
        for temporary, destination in staged:
            replace(temporary, destination)
        report["status"] = "applied"
        return report
    except BaseException:
        for destination, original in originals.items():
            if original is None:
                destination.unlink(missing_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(original)
        raise
    finally:
        shutil.rmtree(transaction, ignore_errors=True)
