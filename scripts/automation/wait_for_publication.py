#!/usr/bin/env python3
"""Fail-closed health gate between a Pages deploy and external effects."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from html.parser import HTMLParser
import json
from pathlib import Path
import time
from typing import Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from scripts.generate_notas_index import canonical_note_url, parse_front_matter


SITE_ORIGIN = "https://mragentes.com.ar"
MAX_RESPONSE_BYTES = 2_000_000


class PublicationNotReady(RuntimeError):
    """The deployed page is not yet safe to use as an external-effect gate."""


@dataclass(frozen=True)
class FetchResult:
    status: int
    url: str
    body: str
    headers: Mapping[str, str]


class _CanonicalParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "link":
            return
        values = {key.lower(): value for key, value in attrs}
        relations = (values.get("rel") or "").lower().split()
        href = values.get("href")
        if "canonical" in relations and href:
            self.hrefs.append(href)


def _origin(url: str) -> str:
    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _validate_public_url(url: str, *, kind: str, origin: str = SITE_ORIGIN) -> str:
    if not isinstance(url, str) or not url.strip() or url != url.strip():
        raise ValueError(f"{kind} URL must be a non-empty trimmed string")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or _origin(url) != origin:
        raise ValueError(f"{kind} URL must use the canonical origin")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(f"{kind} URL contains forbidden URL components")
    decoded_path = unquote(parsed.path)
    if "\\" in decoded_path or any(part == ".." for part in decoded_path.split("/")):
        raise ValueError(f"{kind} URL contains path traversal")
    if kind == "note" and not decoded_path.startswith("/notas/"):
        raise ValueError("note URL must be below /notas/")
    if kind == "image" and not decoded_path.startswith("/images/"):
        raise ValueError("image URL must be below /images/")
    return url


def _url_for_transport(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit(
        (parsed.scheme, parsed.netloc, quote(unquote(parsed.path), safe="/%"), "", "")
    )


def fetch_url(url: str, timeout: float) -> FetchResult:
    """Fetch one bounded public resource without exposing response bodies."""

    request = Request(
        _url_for_transport(url),
        headers={"User-Agent": "MR-Agentes-publication-gate/1.0", "Accept": "*/*"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - validated HTTPS
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise PublicationNotReady("response exceeds the health-gate size limit")
            content_type = response.headers.get_content_type()
            charset = response.headers.get_content_charset() or "utf-8"
            body = raw.decode(charset, errors="replace") if content_type.startswith("text/") else ""
            return FetchResult(
                status=int(response.status),
                url=unquote(response.geturl()),
                body=body,
                headers={key.lower(): value for key, value in response.headers.items()},
            )
    except HTTPError as exc:
        return FetchResult(
            status=int(exc.code),
            url=unquote(exc.geturl()),
            body="",
            headers={key.lower(): value for key, value in exc.headers.items()},
        )
    except (TimeoutError, URLError, OSError) as exc:
        raise PublicationNotReady(f"network unavailable: {type(exc).__name__}") from exc


def _canonical_matches(html: str, note_url: str) -> bool:
    parser = _CanonicalParser()
    parser.feed(html)
    expected = unquote(note_url.rstrip("/"))
    return any(unquote(urljoin(note_url, href).rstrip("/")) == expected for href in parser.hrefs)


def verify_deployed_url(
    note_url: str,
    *,
    image_url: str | None,
    marker: str,
    fetch: Callable[[str, float], FetchResult] = fetch_url,
    attempts: int = 8,
    timeout: float = 10,
    initial_delay: float = 2,
    max_delay: float = 15,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    """Wait until note, canonical marker and optional image are all deployed."""

    if isinstance(attempts, bool) or attempts < 1:
        raise ValueError("attempts must be a positive integer")
    if timeout <= 0 or initial_delay < 0 or max_delay <= 0:
        raise ValueError("timeout/delay bounds are invalid")
    note_url = _validate_public_url(note_url, kind="note")
    if image_url is not None:
        image_url = _validate_public_url(image_url, kind="image")
    if not isinstance(marker, str) or not marker.strip():
        raise ValueError("marker must be a non-empty string")

    last_reason = "publication did not become ready"
    for index in range(attempts):
        try:
            page = fetch(note_url, timeout)
        except PublicationNotReady as exc:
            last_reason = str(exc)
        else:
            if _origin(page.url) != SITE_ORIGIN:
                raise ValueError("note redirect left the canonical origin")
            if unquote(page.url.rstrip("/")) != unquote(note_url.rstrip("/")):
                last_reason = "note redirect does not match the canonical URL"
            elif page.status != 200:
                last_reason = f"note returned HTTP {page.status}"
            elif marker not in page.body:
                last_reason = "note marker is missing"
            elif not _canonical_matches(page.body, note_url):
                last_reason = "canonical marker is missing or mismatched"
            elif image_url is None:
                return {"ready": True, "attempts": index + 1, "note_url": note_url}
            else:
                try:
                    image = fetch(image_url, timeout)
                except PublicationNotReady as exc:
                    last_reason = f"image unavailable: {exc}"
                else:
                    if _origin(image.url) != SITE_ORIGIN:
                        raise ValueError("image redirect left the canonical origin")
                    content_type = image.headers.get("content-type", "").lower()
                    if image.status == 200 and content_type.startswith("image/"):
                        return {
                            "ready": True,
                            "attempts": index + 1,
                            "note_url": note_url,
                            "image_url": image_url,
                        }
                    last_reason = f"image returned HTTP {image.status} or invalid content type"

        if index + 1 < attempts:
            sleep(min(initial_delay * (2**index), max_delay))

    raise PublicationNotReady(last_reason)


def _local_targets(root: Path, site: str, selected_slugs: Sequence[str]) -> list[dict[str, str | None]]:
    notes: list[dict[str, str | None]] = []
    for path in sorted((root / "content" / "notas").glob("*.md")):
        if path.name == "_index.md":
            continue
        meta = parse_front_matter(path.read_text(encoding="utf-8"))
        title = str(meta.get("title", "")).strip()
        if not title:
            continue
        note_path = canonical_note_url(meta, path.name, title)
        slug = note_path.removeprefix("/notas/").removesuffix("/")
        if selected_slugs and slug not in selected_slugs:
            continue
        image_value = meta.get("image")
        image_url = urljoin(site.rstrip("/") + "/", str(image_value).lstrip("/")) if image_value else None
        notes.append(
            {
                "slug": slug,
                "title": title,
                "date": str(meta.get("date", ""))[:10],
                "note_url": urljoin(site.rstrip("/") + "/", note_path.lstrip("/")),
                "image_url": image_url,
            }
        )
    if selected_slugs:
        found = {str(item["slug"]) for item in notes}
        missing = sorted(set(selected_slugs) - found)
        if missing:
            raise ValueError(f"unknown local note slugs: {missing}")
    elif notes:
        newest = max(str(item["date"]) for item in notes)
        notes = [item for item in notes if item["date"] == newest]
    return notes


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default=SITE_ORIGIN)
    parser.add_argument("--slug", action="append", default=[])
    parser.add_argument("--attempts", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[2]
    site = args.site.rstrip("/")
    if site != SITE_ORIGIN:
        raise ValueError("the production gate only accepts the canonical site")
    targets = _local_targets(root, site, args.slug)
    if not targets:
        raise PublicationNotReady("no local note target was found")

    reports = [
        verify_deployed_url(
            str(target["note_url"]),
            image_url=str(target["image_url"]) if target["image_url"] else None,
            marker=str(target["title"]),
            attempts=args.attempts,
            timeout=args.timeout,
        )
        for target in targets
    ]
    print(json.dumps({"ready": True, "notes": reports}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
