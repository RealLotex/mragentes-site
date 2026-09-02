#!/usr/bin/env python3
"""Detect new notes and request one idempotent post-deploy push event."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import unicodedata
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.generate_notas_index import canonical_note_url, parse_front_matter
from scripts.push_payload import public_post_image
from scripts.social import notas as notas_mod
from scripts.social.notas import Nota


SITE_ORIGIN = "https://mragentes.com.ar"
ZERO_SHA = "0" * 40
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
EVENT_RE = re.compile(
    r"^blog-note:\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]):"
    r"[^\W_]+(?:-[^\W_]+)*$",
    re.UNICODE,
)
SAFE_SLUG_RE = re.compile(r"^[^\W_]+(?:-[^\W_]+)*$", re.UNICODE)
MAX_EVENT_ID_BYTES = 512
MAX_RESPONSE_BYTES = 128_000
RECOVERY_NOTE_PATH_RE = re.compile(
    r"^\.automation/publication/retries/(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)\.json$"
)


class NotificationError(RuntimeError):
    pass


class NotificationConflict(NotificationError):
    pass


class NotificationUnavailable(NotificationError):
    pass


def _git(repo: Path, *args: str, text: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=text,
    )
    return result.stdout


def _validate_commit(repo: Path, value: str, *, allow_zero: bool = False) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise ValueError("commit SHA must contain exactly 40 lowercase hex characters")
    if allow_zero and value == ZERO_SHA:
        return value
    resolved = str(_git(repo, "rev-parse", "--verify", f"{value}^{{commit}}", text=True)).strip()
    if resolved != value:
        raise ValueError("commit SHA must be canonical and fully resolved")
    return value


def _added_note_paths(repo: Path, before_sha: str, after_sha: str) -> list[str]:
    if before_sha == ZERO_SHA:
        output = _git(
            repo,
            "ls-tree",
            "-r",
            "--name-only",
            "-z",
            after_sha,
            "--",
            "content/notas",
        )
    else:
        output = _git(
            repo,
            "diff",
            "--find-renames=90%",
            "--diff-filter=A",
            "--name-only",
            "-z",
            before_sha,
            after_sha,
            "--",
            "content/notas",
        )
    assert isinstance(output, bytes)
    return sorted(
        os.fsdecode(item)
        for item in output.split(b"\0")
        if item and item.endswith(b".md") and not item.endswith(b"/_index.md")
    )


def _known_note_slugs(repo: Path, commit_sha: str) -> set[str]:
    """Read the canonical note identities available in one trusted revision."""

    output = _git(repo, "ls-tree", "-r", "--name-only", "-z", commit_sha, "--", "content/notas")
    assert isinstance(output, bytes)
    slugs: set[str] = set()
    for raw_path in output.split(b"\0"):
        if not raw_path or not raw_path.endswith(b".md") or raw_path.endswith(b"/_index.md"):
            continue
        relative_path = os.fsdecode(raw_path)
        source = str(_git(repo, "show", f"{commit_sha}:{relative_path}", text=True))
        meta = parse_front_matter(source)
        title = str(meta.get("title", "")).strip()
        if not title:
            raise ValueError(f"note has no title: {relative_path}")
        note_url = canonical_note_url(meta, Path(relative_path).name, title)
        slugs.add(note_url.removeprefix("/notas/").removesuffix("/"))
    return slugs


def _added_recovery_note_slugs(repo: Path, before_sha: str, after_sha: str) -> list[str]:
    """Accept a one-shot, versioned retry only for an existing canonical note."""

    output = _git(
        repo,
        "diff",
        "--diff-filter=A",
        "--name-only",
        "-z",
        before_sha,
        after_sha,
        "--",
        ".automation/publication/retries",
    )
    assert isinstance(output, bytes)
    known_slugs = _known_note_slugs(repo, after_sha)
    recovered: list[str] = []
    for raw_path in output.split(b"\0"):
        if not raw_path:
            continue
        relative_path = os.fsdecode(raw_path)
        match = RECOVERY_NOTE_PATH_RE.fullmatch(relative_path)
        if match is None:
            raise ValueError(f"invalid publication recovery path: {relative_path}")
        try:
            document = json.loads(str(_git(repo, "show", f"{after_sha}:{relative_path}", text=True)))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid publication recovery JSON: {relative_path}") from exc
        if not isinstance(document, dict) or set(document) != {"schema_version", "note_slug", "reason"}:
            raise ValueError(f"invalid publication recovery schema: {relative_path}")
        slug = document.get("note_slug")
        if (
            document.get("schema_version") != 1
            or document.get("reason") != "post_deploy_gate_recovered"
            or not isinstance(slug, str)
            or slug != match.group("slug")
            or slug not in known_slugs
        ):
            raise ValueError(f"invalid publication recovery target: {relative_path}")
        recovered.append(slug)
    return sorted(recovered)


def changed_note_slugs(repo: Path | str, before_sha: str, after_sha: str) -> list[str]:
    """Return new notes plus one-shot, audited recovery requests.

    Ordinary modifications, deletions and renames remain excluded. A recovery
    requires an added, closed-schema manifest that names an existing note,
    allowing a failed pre-egress deployment gate to resume on the current SHA.
    """

    root = Path(repo).resolve()
    if not (root / ".git").exists():
        raise ValueError("repo must be a Git worktree root")
    before_sha = _validate_commit(root, before_sha, allow_zero=True)
    after_sha = _validate_commit(root, after_sha)

    slugs: list[str] = []
    for relative_path in _added_note_paths(root, before_sha, after_sha):
        source = str(
            _git(root, "show", f"{after_sha}:{relative_path}", text=True)
        )
        meta = parse_front_matter(source)
        title = str(meta.get("title", "")).strip()
        if not title:
            raise ValueError(f"added note has no title: {relative_path}")
        note_url = canonical_note_url(meta, Path(relative_path).name, title)
        slugs.append(note_url.removeprefix("/notas/").removesuffix("/"))

    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicates:
        raise ValueError(f"duplicate canonical note slugs: {duplicates}")
    return sorted(set(slugs) | set(_added_recovery_note_slugs(root, before_sha, after_sha)))


def changed_social_drafts(repo: Path | str, before_sha: str, after_sha: str) -> list[str]:
    """Return newly added, date-scoped daily-owned draft paths."""

    root = Path(repo).resolve()
    if not (root / ".git").exists():
        raise ValueError("repo must be a Git worktree root")
    before_sha = _validate_commit(root, before_sha, allow_zero=True)
    after_sha = _validate_commit(root, after_sha)
    if before_sha == ZERO_SHA:
        output = _git(
            root,
            "ls-tree",
            "-r",
            "--name-only",
            "-z",
            after_sha,
            "--",
            ".automation/social/drafts",
        )
    else:
        output = _git(
            root,
            "diff",
            "--find-renames=90%",
            "--diff-filter=A",
            "--name-only",
            "-z",
            before_sha,
            after_sha,
            "--",
            ".automation/social/drafts",
        )
    assert isinstance(output, bytes)
    pattern = re.compile(
        r"^\.automation/social/drafts/\d{4}-\d{2}-\d{2}-daily-owned\.json$"
    )
    candidates = sorted(
        os.fsdecode(item) for item in output.split(b"\0") if item and pattern.fullmatch(os.fsdecode(item))
    )
    dates = [Path(path).name[:10] for path in candidates]
    if len(dates) != len(set(dates)):
        raise ValueError("duplicate daily social drafts for one local date")
    for relative_path in candidates:
        source = str(_git(root, "show", f"{after_sha}:{relative_path}", text=True))
        try:
            document = json.loads(source)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid daily social draft JSON: {relative_path}") from exc
        if not isinstance(document, dict) or document.get("kind") != "daily_owned":
            raise ValueError(f"added social draft is not daily_owned: {relative_path}")
    return candidates


def _safe_slug(slug: str) -> str:
    if (
        not isinstance(slug, str)
        or not slug
        or slug != slug.strip()
        or slug in {".", ".."}
        or any(character in slug for character in "/\\?#")
        or "://" in slug
        or any(ord(character) < 32 or ord(character) == 127 for character in slug)
        or slug != unicodedata.normalize("NFC", slug)
        or not SAFE_SLUG_RE.fullmatch(slug)
    ):
        raise ValueError("slug must be one safe, trimmed URL component")
    return slug


def build_idempotency_key(
    repository: str,
    deploy_sha: str,
    slug: str,
    *,
    publication_date: str,
) -> str:
    """Build the editorial event id accepted by the Worker coordinator."""

    if not isinstance(repository, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("repository must use owner/name form")
    if not isinstance(deploy_sha, str) or not SHA_RE.fullmatch(deploy_sha):
        raise ValueError("deploy_sha must be a full lowercase commit SHA")
    if not isinstance(publication_date, str) or not re.fullmatch(
        r"\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])", publication_date
    ):
        raise ValueError("publication_date must use YYYY-MM-DD")
    event_id = f"blog-note:{publication_date}:{_safe_slug(slug)}"
    if len(event_id.encode("utf-8")) > MAX_EVENT_ID_BYTES:
        raise ValueError(
            f"idempotency key exceeds {MAX_EVENT_ID_BYTES} UTF-8 bytes"
        )
    return event_id


def build_note_notification(
    note: Nota,
    *,
    repository: str,
    deploy_sha: str,
    site_origin: str = SITE_ORIGIN,
) -> tuple[str, dict[str, str]]:
    """Build the Worker event and payload from one deployed Hugo note."""

    if not isinstance(note, Nota):
        raise TypeError("note must be a parsed Nota")
    if site_origin.rstrip("/") != SITE_ORIGIN:
        raise ValueError("notification site origin must be canonical")
    event_id = build_idempotency_key(
        repository,
        deploy_sha,
        note.slug,
        publication_date=note.date.isoformat(),
    )
    title = note.title.strip()
    body = (note.description or "Publicamos una nota nueva en MR Agentes.").strip()
    if not title or len(title) > 300 or not body or len(body) > 1_000:
        raise ValueError("note notification title or body is outside its limit")
    payload = {
        "title": title,
        "body": body,
        "url": note.url(SITE_ORIGIN),
    }
    if note.image:
        image = public_post_image(note.image)
        if image is None:
            raise ValueError("note cover is not a safe same-site stock image")
        payload["image"] = image
    return event_id, payload


def _validate_request(worker_url: str, token: str, event_id: str, payload: Mapping[str, Any]) -> None:
    parsed = urlsplit(worker_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("worker_url must be an HTTPS endpoint")
    if parsed.query or parsed.fragment or not parsed.path.endswith("/api/send/"):
        raise ValueError("worker_url must target /api/send/ without query or fragment")
    if not isinstance(token, str) or not token.strip() or token != token.strip():
        raise ValueError("notification token is missing or malformed")
    if (
        not isinstance(event_id, str)
        or event_id != unicodedata.normalize("NFC", event_id)
        or len(event_id.encode("utf-8")) > MAX_EVENT_ID_BYTES
        or not EVENT_RE.fullmatch(event_id)
    ):
        raise ValueError("event_id is not a blog-note publication event")
    allowed = {"title", "body", "url", "image"}
    if not isinstance(payload, Mapping) or set(payload) - allowed:
        raise ValueError("payload contains unsupported fields")
    for field in ("title", "body", "url"):
        if not isinstance(payload.get(field), str) or not str(payload[field]).strip():
            raise ValueError(f"payload {field} is required")
    target = urlsplit(str(payload["url"]))
    if f"{target.scheme}://{target.netloc}" != SITE_ORIGIN or not target.path.startswith("/notas/"):
        raise ValueError("payload URL must identify a canonical site note")


def _read_json_response(response: Any) -> dict[str, Any]:
    raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise NotificationError("notification response exceeds the size limit")
    try:
        value = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NotificationError("notification response is not valid JSON") from exc
    if not isinstance(value, dict):
        raise NotificationError("notification response must be a JSON object")
    return value


def _safe_result(value: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "complete",
        "duplicate",
        "state",
        "delivered",
        "gone",
        "retryable",
        "uncertain",
        "invalid",
        "total",
    }
    return {key: value[key] for key in allowed if key in value}


def request_notification(
    worker_url: str,
    *,
    token: str,
    event_id: str,
    payload: Mapping[str, Any],
    opener: Callable[..., Any] = urlopen,
    attempts: int = 2,
    timeout: float = 15,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Send one bounded request; every retry reuses the exact event and hash."""

    _validate_request(worker_url, token, event_id, payload)
    if isinstance(attempts, bool) or attempts < 1 or attempts > 3:
        raise ValueError("attempts must be between one and three")
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    payload_bytes = json.dumps(
        dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    payload_hash = "sha256:" + hashlib.sha256(payload_bytes).hexdigest()
    request_body = json.dumps(
        {"eventId": event_id, "payloadHash": payload_hash, "payload": dict(payload)},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Idempotency-Key": event_id,
        "Origin": SITE_ORIGIN,
        "User-Agent": "MR-Agentes-post-deploy/1.0",
    }

    for index in range(attempts):
        request = Request(worker_url, data=request_body, headers=headers, method="POST")
        try:
            with opener(request, timeout=timeout) as response:
                status = int(response.status)
                value = _read_json_response(response)
        except HTTPError as exc:
            status = int(exc.code)
            try:
                value = _read_json_response(exc) if exc.fp is not None else {}
            except NotificationError:
                value = {}
        except (TimeoutError, URLError, OSError) as exc:
            if index + 1 < attempts:
                sleep(min(2**index, 5))
                continue
            raise NotificationUnavailable(f"notification transport failed: {type(exc).__name__}") from exc

        if 200 <= status < 300:
            return _safe_result(value)
        if status == 409:
            if value.get("duplicate") is True:
                result = _safe_result(value)
                result["duplicate"] = True
                return result
            raise NotificationConflict("event id exists with an unverified payload hash")
        if status == 429 or status >= 500:
            if index + 1 < attempts:
                sleep(min(2**index, 5))
                continue
            raise NotificationUnavailable(f"notification endpoint returned HTTP {status}")
        raise NotificationError(f"notification endpoint returned HTTP {status}")

    raise AssertionError("unreachable notification retry state")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    note_command = commands.add_parser(
        "send-note", help="send the notification for one deployed repository note"
    )
    note_command.add_argument("--worker-url", required=True)
    note_command.add_argument("--token-env", default="PUSH_API_TOKEN")
    note_command.add_argument("--note-slug", required=True)
    note_command.add_argument("--deploy-sha", required=True)
    note_command.add_argument("--repository", required=True)

    payload_command = commands.add_parser(
        "send-payload", help="send an already constructed notification payload"
    )
    payload_command.add_argument("--worker-url", required=True)
    payload_command.add_argument("--token-env", default="PUSH_API_TOKEN")
    payload_command.add_argument("--event-id", required=True)
    payload_command.add_argument("--title", required=True)
    payload_command.add_argument("--body", required=True)
    payload_command.add_argument("--url", required=True)
    payload_command.add_argument("--image")
    args = parser.parse_args(argv)

    token = os.environ.get(args.token_env, "")
    if args.command == "send-note":
        note = notas_mod.find(args.note_slug)
        if note is None:
            raise ValueError(f"deployed note not found: {args.note_slug}")
        event_id, payload = build_note_notification(
            note,
            repository=args.repository,
            deploy_sha=args.deploy_sha,
        )
    else:
        event_id = args.event_id
        payload = {"title": args.title, "body": args.body, "url": args.url}
        if args.image:
            payload["image"] = args.image
    result = request_notification(
        args.worker_url,
        token=token,
        event_id=event_id,
        payload=payload,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
