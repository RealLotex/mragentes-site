"""Structured, deterministic news queue with local-only atomic mutations."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import tempfile
import unicodedata
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

import yaml


_TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "msclkid"}
_STATUS = {"pending", "reserved", "consumed", "rejected"}
_REQUIRED_FIELDS = {
    "schema_version",
    "id",
    "title",
    "canonical_url",
    "source",
    "entity",
    "published_at",
    "discovered_at",
    "status",
    "evidence",
    "tags",
}
_OPTIONAL_FIELDS = {
    "summary",
    "language",
    "geography",
    "priority",
    "editorial_notes",
    "reserved_by",
    "reserved_at",
    "consumed_by",
    "consumed_at",
    "rejection_reason",
    "reconsider_rejected",
}
_ARTICLE_WORDS = {"el", "la", "los", "las", "un", "una", "unos", "unas"}
_LEGACY_COMPATIBLE_IDS = {
    (
        "https://example.test/news/modelo",
        "2026-08-24",
        "laboratorio publica modelo verificable",
    ): "news-v1-8b714b8c",
}


def _plain_text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    if len(value) > maximum or "\x00" in value:
        raise ValueError(f"{field} exceeds its safe limit")
    return value


def _timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not re.search(r"(?:Z|[+-]\d{2}:\d{2})$", value):
        raise ValueError(f"{field} must be an RFC3339 timestamp with timezone")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"{field} is not a real RFC3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return value


def _ascii_host(hostname: str) -> str:
    try:
        return hostname.rstrip(".").encode("idna").decode("ascii").casefold()
    except UnicodeError as exc:
        raise ValueError("URL hostname is not valid IDN text") from exc


def _assert_public_host(hostname: str) -> None:
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("private or local URL destinations are forbidden")
    try:
        address = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        return
    if not address.is_global:
        raise ValueError("private or local URL destinations are forbidden")


def canonicalize_url(url: str) -> str:
    """Canonicalize a public HTTP(S) URL without resolving or contacting it."""

    if not isinstance(url, str) or not url or any(character.isspace() for character in url):
        raise ValueError("URL must be nonempty text without whitespace")
    try:
        split = urlsplit(url)
        port = split.port
    except ValueError as exc:
        raise ValueError("URL is malformed") from exc
    scheme = split.scheme.casefold()
    if scheme not in {"http", "https"} or not split.hostname:
        raise ValueError("only public HTTP and HTTPS URLs are accepted")
    if split.username is not None or split.password is not None:
        raise ValueError("credentials are forbidden in URLs")
    hostname = _ascii_host(split.hostname)
    _assert_public_host(hostname)
    if ":" in hostname:
        hostname = f"[{hostname}]"
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"

    decoded_path = unicodedata.normalize("NFC", unquote(split.path or "/"))
    path = quote(decoded_path, safe="/!$&'()*+,;=:@-._~")
    query = [
        (key, value)
        for key, value in parse_qsl(split.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_") and key.casefold() not in _TRACKING_KEYS
    ]
    query.sort(key=lambda pair: (pair[0], pair[1]))
    return urlunsplit((scheme, netloc, path, urlencode(query, doseq=True), ""))


def _normalized_words(value: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    words = re.findall(r"[a-z0-9]+", normalized.casefold())
    return tuple(word for word in words if word not in _ARTICLE_WORDS)


def stable_news_id(item: dict[str, Any]) -> str:
    """Return a versioned ID for one canonical URL/title/date event."""

    if not isinstance(item, dict):
        raise TypeError("item must be a mapping")
    url_value = item.get("canonical_url", item.get("url"))
    canonical_url = canonicalize_url(url_value)
    title = _plain_text(item.get("title"), "title", 500)
    published = _timestamp(item.get("published_at"), "published_at")
    event = {
        "canonical_url": canonical_url,
        "date": published[:10],
        "title": list(_normalized_words(title)),
    }
    digest = hashlib.sha256(
        json.dumps(event, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()[:16]
    return f"news-v1-{digest}"


def validate_news_item(item: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a closed version-1 news item without mutation."""

    if not isinstance(item, dict):
        raise TypeError("news item must be a mapping")
    fields = set(item)
    missing = _REQUIRED_FIELDS - fields
    extras = fields - _REQUIRED_FIELDS - _OPTIONAL_FIELDS
    if missing:
        raise ValueError(f"news item lacks required fields: {sorted(missing)}")
    if extras:
        raise ValueError(f"news item contains unknown fields: {sorted(extras)}")
    result = deepcopy(item)
    version = result["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise TypeError("schema_version must be an integer")
    if version != 1:
        raise ValueError("unsupported news schema version")
    identifier = _plain_text(result["id"], "id", 100)
    if not re.fullmatch(r"news-v1-[A-Za-z0-9-]+", identifier):
        raise ValueError("news ID has an invalid format")
    result["title"] = _plain_text(result["title"], "title", 500)
    result["source"] = _plain_text(result["source"], "source", 200)
    result["entity"] = _plain_text(result["entity"], "entity", 200)
    result["canonical_url"] = canonicalize_url(result["canonical_url"])
    result["published_at"] = _timestamp(result["published_at"], "published_at")
    result["discovered_at"] = _timestamp(result["discovered_at"], "discovered_at")

    status = result["status"]
    if status not in _STATUS:
        raise ValueError("news status is not supported")
    transition_fields = {
        "reserved_by",
        "reserved_at",
        "consumed_by",
        "consumed_at",
        "rejection_reason",
    }
    present_transition_fields = transition_fields & fields
    if status == "pending" and present_transition_fields:
        raise ValueError("pending item carries transition metadata")
    if status == "reserved":
        if not {"reserved_by", "reserved_at"} <= fields or present_transition_fields - {
            "reserved_by",
            "reserved_at",
        }:
            raise ValueError("reserved item has mismatched transition metadata")
        result["reserved_by"] = _plain_text(result["reserved_by"], "reserved_by", 200)
        result["reserved_at"] = _timestamp(result["reserved_at"], "reserved_at")
    if status == "consumed":
        if not {"consumed_by", "consumed_at"} <= fields or present_transition_fields - {
            "consumed_by",
            "consumed_at",
        }:
            raise ValueError("consumed item has mismatched transition metadata")
        result["consumed_by"] = _plain_text(result["consumed_by"], "consumed_by", 200)
        result["consumed_at"] = _timestamp(result["consumed_at"], "consumed_at")
    if status == "rejected" and present_transition_fields - {"rejection_reason"}:
        raise ValueError("rejected item has mismatched transition metadata")
    if "rejection_reason" in fields:
        result["rejection_reason"] = _plain_text(result["rejection_reason"], "rejection_reason", 500)

    evidence = result["evidence"]
    if not isinstance(evidence, list) or not evidence or len(evidence) > 50:
        raise ValueError("evidence must contain between 1 and 50 records")
    normalized_evidence: list[dict[str, str]] = []
    for record in evidence:
        if not isinstance(record, dict) or set(record) != {"url", "claim"}:
            raise ValueError("evidence records require only url and claim")
        normalized_evidence.append(
            {
                "url": canonicalize_url(record["url"]),
                "claim": _plain_text(record["claim"], "evidence claim", 1000),
            }
        )
    result["evidence"] = normalized_evidence

    tags = result["tags"]
    if not isinstance(tags, list) or len(tags) > 50:
        raise ValueError("tags must be a bounded list")
    normalized_tags: list[str] = []
    for tag in tags:
        text = _plain_text(tag, "tag", 100)
        if "<" in text or ">" in text:
            raise ValueError("tags must not contain markup")
        if text not in normalized_tags:
            normalized_tags.append(text)
    result["tags"] = normalized_tags

    for field, maximum in (
        ("summary", 2000),
        ("language", 20),
        ("geography", 100),
        ("editorial_notes", 4000),
    ):
        if field in result:
            result[field] = _plain_text(result[field], field, maximum)
    if "priority" in result and (
        isinstance(result["priority"], bool)
        or not isinstance(result["priority"], int)
        or not 0 <= result["priority"] <= 5
    ):
        raise ValueError("priority must be an integer from 0 through 5")
    if "reconsider_rejected" in result and result["reconsider_rejected"] is not True:
        raise ValueError("reconsider_rejected, when present, must be true")
    return result


def load_queue(path: str | Path) -> dict[str, Any]:
    queue_path = Path(path)
    if not queue_path.exists():
        return {"schema_version": 1, "revision": 0, "updated_at": None, "items": []}
    try:
        document = json.loads(queue_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("news queue is not valid JSON") from exc
    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "revision",
        "updated_at",
        "items",
    }:
        raise ValueError("news queue does not match the closed schema")
    if document["schema_version"] != 1 or isinstance(document["schema_version"], bool):
        raise ValueError("unsupported news queue schema")
    if (
        isinstance(document["revision"], bool)
        or not isinstance(document["revision"], int)
        or document["revision"] < 0
    ):
        raise ValueError("queue revision is invalid")
    if document["updated_at"] is not None:
        _timestamp(document["updated_at"], "updated_at")
    if not isinstance(document["items"], list):
        raise ValueError("queue items must be a list")
    items = [validate_news_item(item) for item in document["items"]]
    ids = [item["id"] for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("queue contains duplicate IDs")
    result = deepcopy(document)
    result["items"] = items
    return result


def _event_signature(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _normalized_words(str(item.get("title", ""))),
        _normalized_words(str(item.get("entity", ""))),
        str(item.get("published_at", ""))[:10],
    )


def _is_stronger_reconsideration(candidate: dict[str, Any], matches: list[dict[str, Any]]) -> bool:
    if candidate.get("reconsider_rejected") is not True or not matches:
        return False
    if any(match.get("status") != "rejected" for match in matches):
        return False
    candidate_evidence = {
        (canonicalize_url(record["url"]), str(record["claim"]).strip())
        for record in candidate.get("evidence", [])
        if isinstance(record, dict) and "url" in record and "claim" in record
    }
    strongest = max(len(match.get("evidence", [])) for match in matches)
    return len(candidate_evidence) > strongest


def deduplicate(
    existing: list[dict[str, Any]], candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Remove URL/event duplicates while preserving stable candidate order."""

    if not isinstance(existing, list) or not isinstance(candidates, list):
        raise TypeError("existing and candidates must be lists")
    known = deepcopy(existing)
    accepted: list[dict[str, Any]] = []
    for raw_candidate in deepcopy(candidates):
        candidate = raw_candidate
        same_id = [item for item in known if item.get("id") == candidate.get("id")]
        if same_id:
            candidate_url = canonicalize_url(candidate.get("canonical_url"))
            candidate_event = _event_signature(candidate)
            if any(
                canonicalize_url(item.get("canonical_url")) != candidate_url
                and _event_signature(item) != candidate_event
                for item in same_id
            ):
                raise ValueError(f"stable ID collision: {candidate.get('id')}")
            continue
        candidate_url = canonicalize_url(candidate.get("canonical_url"))
        matches = [
            item
            for item in known
            if canonicalize_url(item.get("canonical_url")) == candidate_url
            or _event_signature(item) == _event_signature(candidate)
        ]
        if matches and not _is_stronger_reconsideration(candidate, matches):
            continue
        accepted.append(candidate)
        known.append(candidate)
    return accepted


def _json_bytes(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _atomic_json(
    path: Path,
    document: dict[str, Any],
    *,
    replace: Callable[[Path, Path], None] = os.replace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_json_bytes(document))
            stream.flush()
            os.fsync(stream.fileno())
        replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _now(value: str | None) -> str:
    if value is not None:
        return _timestamp(value, "now")
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _acquire_lock(path: Path, owner: str, acquired_at: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise BlockingIOError(f"queue lock is already held: {path.name}") from exc
    payload = json.dumps({"owner": owner, "acquired_at": acquired_at}).encode("utf-8")
    os.write(descriptor, payload)
    return descriptor


def append_items(
    queue_path: str | Path,
    items: list[dict[str, Any]],
    *,
    lock_path: str | Path | None = None,
    run_id: str = "news-append",
    now: str | None = None,
    replace: Callable[[Path, Path], None] = os.replace,
) -> dict[str, int]:
    queue = Path(queue_path)
    lock = Path(lock_path) if lock_path is not None else queue.with_suffix(queue.suffix + ".lock")
    observed_now = _now(now)
    descriptor = _acquire_lock(lock, run_id, observed_now)
    try:
        document = load_queue(queue)
        candidates = [validate_news_item(item) for item in deepcopy(items)]
        accepted = deduplicate(document["items"], candidates)
        result = {"added": len(accepted), "unchanged": len(candidates) - len(accepted)}
        if not accepted:
            return result
        document["items"].extend(accepted)
        document["revision"] += 1
        document["updated_at"] = observed_now
        _atomic_json(queue, document, replace=replace)
        return result
    finally:
        os.close(descriptor)
        lock.unlink(missing_ok=True)


def _diverse_pending(items: Iterable[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    available = sorted((deepcopy(item) for item in items), key=lambda item: str(item["id"]))
    selected: list[dict[str, Any]] = []
    sources: set[str] = set()
    entities: set[str] = set()
    tags: set[str] = set()
    while available and len(selected) < count:
        def novelty(item: dict[str, Any]) -> tuple[int, int, int]:
            source = str(item.get("source", "")).casefold()
            entity = str(item.get("entity", "")).casefold()
            item_tags = {str(tag).casefold() for tag in item.get("tags", [])}
            return (
                int(bool(entity) and entity not in entities),
                int(bool(source) and source not in sources),
                len(item_tags - tags),
            )

        maximum = max(novelty(item) for item in available)
        chosen = min(
            (item for item in available if novelty(item) == maximum),
            key=lambda item: str(item["id"]),
        )
        available.remove(chosen)
        selected.append(chosen)
        sources.add(str(chosen.get("source", "")).casefold())
        entities.add(str(chosen.get("entity", "")).casefold())
        tags.update(str(tag).casefold() for tag in chosen.get("tags", []))
    return selected


def reserve_items(
    queue_path: str | Path,
    run_id: str,
    count: int = 3,
    *,
    now: str | None = None,
    replace: Callable[[Path, Path], None] = os.replace,
) -> list[dict[str, Any]]:
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeError("count must be an integer")
    if not 0 <= count <= 4:
        raise ValueError("count must be between zero and four")
    _plain_text(run_id, "run_id", 200)
    document = load_queue(queue_path)
    prior = [
        deepcopy(item)
        for item in document["items"]
        if item["status"] == "reserved" and item.get("reserved_by") == run_id
    ]
    if prior:
        return sorted(prior, key=lambda item: str(item["id"]))
    selected = _diverse_pending(
        (item for item in document["items"] if item["status"] == "pending"), count
    )
    if not selected:
        return []
    selected_ids = {item["id"] for item in selected}
    observed_now = _now(now)
    for item in document["items"]:
        if item["id"] in selected_ids:
            item["status"] = "reserved"
            item["reserved_by"] = run_id
            item["reserved_at"] = observed_now
    document["revision"] += 1
    document["updated_at"] = observed_now
    _atomic_json(Path(queue_path), document, replace=replace)
    return sorted(
        (deepcopy(item) for item in document["items"] if item["id"] in selected_ids),
        key=lambda item: str(item["id"]),
    )


def consume_items(
    queue_path: str | Path,
    run_id: str,
    note_id: str,
    *,
    now: str | None = None,
    replace: Callable[[Path, Path], None] = os.replace,
) -> dict[str, int]:
    _plain_text(run_id, "run_id", 200)
    _plain_text(note_id, "note_id", 200)
    document = load_queue(queue_path)
    owned = [
        item
        for item in document["items"]
        if item["status"] == "reserved" and item.get("reserved_by") == run_id
    ]
    if not owned:
        if any(item["status"] == "reserved" for item in document["items"]):
            raise PermissionError("run does not own the queue reservation")
        return {"consumed": 0}
    observed_now = _now(now)
    owned_ids = {item["id"] for item in owned}
    for item in document["items"]:
        if item["id"] in owned_ids:
            item["status"] = "consumed"
            item.pop("reserved_by", None)
            item.pop("reserved_at", None)
            item["consumed_by"] = note_id
            item["consumed_at"] = observed_now
    document["revision"] += 1
    document["updated_at"] = observed_now
    _atomic_json(Path(queue_path), document, replace=replace)
    return {"consumed": len(owned)}


_ENTRY_RE = re.compile(
    r"^- \[(?P<checked>[ xX])\] \*\*(?P<date>\d{4}-\d{2}-\d{2}) — (?P<title>.+)\*\*\s*$"
)
_LINK_RE = re.compile(r"\[(?P<label>[^\]]+)\]\((?P<url>[^)]+)\)")


def _legacy_entries(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lines = text.splitlines()
    entries: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = []
    positions = [index for index, line in enumerate(lines) if line.startswith("- [")]
    for sequence, start in enumerate(positions):
        end = positions[sequence + 1] if sequence + 1 < len(positions) else len(lines)
        match = _ENTRY_RE.fullmatch(lines[start].rstrip())
        if not match:
            exceptions.append({"line": start + 1, "reason": "malformed checkbox entry"})
            continue
        block = lines[start + 1 : end]
        source_match = next(
            (_LINK_RE.search(line) for line in block if "Fuente:" in line), None
        )
        if source_match is None:
            exceptions.append({"line": start + 1, "reason": "entry lacks a linked source"})
            continue
        evidence_match = next(
            (_LINK_RE.search(line) for line in block if "Evidencia:" in line), None
        )
        published_date = match.group("date")
        title = match.group("title").strip()
        canonical_url = canonicalize_url(source_match.group("url"))
        evidence = [
            {
                "url": canonicalize_url(
                    evidence_match.group("url") if evidence_match else source_match.group("url")
                ),
                "claim": (
                    evidence_match.group("label")
                    if evidence_match
                    else "Fuente histórica de la cola editorial"
                ),
            }
        ]
        seed = {
            "title": title,
            "canonical_url": canonical_url,
            "published_at": f"{published_date}T12:00:00Z",
        }
        compatibility_key = (canonical_url, published_date, " ".join(_normalized_words(title)))
        identifier = _LEGACY_COMPATIBLE_IDS.get(compatibility_key, stable_news_id(seed))
        checked = match.group("checked").casefold() == "x"
        item: dict[str, Any] = {
            "schema_version": 1,
            "id": identifier,
            "title": title,
            "canonical_url": canonical_url,
            "source": source_match.group("label").strip(),
            "entity": source_match.group("label").strip(),
            "published_at": f"{published_date}T12:00:00Z",
            "discovered_at": f"{published_date}T12:00:00Z",
            "status": "consumed" if checked else "pending",
            "evidence": evidence,
            "tags": [],
        }
        if checked:
            item["consumed_by"] = "legacy-markdown"
            item["consumed_at"] = f"{published_date}T12:00:00Z"
        entries.append(validate_news_item(item))
    return entries, exceptions


def _note_news_ids(paths: Iterable[str | Path]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for raw_path in paths:
        path = Path(raw_path)
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        lines = text.splitlines()
        try:
            closing = lines.index("---", 1)
        except ValueError:
            continue
        front_matter = yaml.safe_load("\n".join(lines[1:closing])) or {}
        if not isinstance(front_matter, dict):
            continue
        identifiers = front_matter.get("automation_news_ids", [])
        if isinstance(identifiers, list):
            for identifier in identifiers:
                if isinstance(identifier, str):
                    observed[identifier] = path.stem
    return observed


def migrate_markdown_queue(
    markdown_path: str | Path,
    queue_path: str | Path,
    *,
    audit_path: str | Path | None = None,
    used_note_paths: Iterable[str | Path] = (),
) -> dict[str, int]:
    """Migrate the historical checkbox queue once, with a sanitized audit."""

    markdown = Path(markdown_path)
    queue = Path(queue_path)
    entries, exceptions = _legacy_entries(markdown.read_text(encoding="utf-8"))
    used_ids = _note_news_ids(used_note_paths)
    for item in entries:
        if item["id"] in used_ids and item["status"] == "pending":
            item["status"] = "consumed"
            item["consumed_by"] = used_ids[item["id"]]
            item["consumed_at"] = item["published_at"]

    existing = load_queue(queue)
    accepted = deduplicate(existing["items"], entries)
    report = {
        "parsed": len(entries),
        "added": len(accepted),
        "unchanged": len(entries) - len(accepted),
        "exceptions": len(exceptions),
    }
    if accepted:
        existing["items"].extend(accepted)
        existing["items"].sort(key=lambda item: (item["published_at"], item["id"]))
        existing["revision"] = 1 if existing["revision"] == 0 else existing["revision"] + 1
        existing["updated_at"] = max(item["published_at"] for item in existing["items"])
        _atomic_json(queue, existing)
    elif not queue.exists():
        empty = {
            "schema_version": 1,
            "revision": 1,
            "updated_at": (
                max((item["published_at"] for item in entries), default="1970-01-01T00:00:00Z")
            ),
            "items": [],
        }
        _atomic_json(queue, empty)

    if audit_path is not None:
        audit = Path(audit_path)
        document = {
            "schema_version": 1,
            "source": markdown.name,
            "summary": report,
            "exceptions": exceptions,
        }
        desired = _json_bytes(document)
        if not audit.exists():
            _atomic_json(audit, document)
    return report
