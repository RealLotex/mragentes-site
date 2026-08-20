"""Shared payload rules for blog-to-Web-Push notifications."""

from __future__ import annotations

from urllib.parse import quote, urlparse


SITE_ORIGIN = "https://mragentes.com.ar"
BRAND_ICON = "/faviconhand512.png"
BRAND_BADGE = "/faviconhand512.png"


def public_post_image(value: str | None) -> str | None:
    """Return an absolute URL only for a same-site stock image.

    Push payloads are authorized by the publishing token, but the Worker still
    rejects arbitrary third-party image URLs to prevent tracking pixels and
    accidental mixed-brand assets.
    """
    if not isinstance(value, str) or not value.strip():
        return None

    parsed = urlparse(value.strip())
    if parsed.scheme or parsed.netloc:
        if f"{parsed.scheme}://{parsed.netloc}" != SITE_ORIGIN:
            return None
        path = parsed.path
    else:
        path = parsed.path

    path = "/" + path.lstrip("/")
    if not path.startswith("/images/stock/"):
        return None
    return f"{SITE_ORIGIN}{quote(path, safe='/')}"


def build_payload(title: str, body: str, url: str, image: str | None = None) -> dict[str, str]:
    """Build the common payload sent to the Cloudflare Worker."""
    payload = {
        "title": title,
        "body": body,
        "url": url,
        "icon": BRAND_ICON,
        "badge": BRAND_BADGE,
    }
    post_image = public_post_image(image)
    if post_image:
        payload["image"] = post_image
    return payload
