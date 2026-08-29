#!/usr/bin/env python3
"""Validate Meta testing credentials with GET-only Graph API operations.

This module deliberately exposes no publication operation. It verifies the
exact configured Facebook and Instagram identities plus the same collection
reads used by delivery reconciliation, then emits boolean evidence only.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from .config import Settings, load_settings
from .publisher import Meta

GRAPH_VERSION = "v26.0"
READ_WINDOW = dt.timedelta(days=1)


class ReadOnlyMeta(Protocol):
    def whoami(self) -> dict[str, Any]: ...

    def recent_publications(
        self, platform: str, *, since: str, limit: int = 25
    ) -> list[dict[str, str]]: ...


def _require_safe_configuration(settings: Settings) -> None:
    if settings.graph_version != GRAPH_VERSION:
        raise PermissionError("Meta preflight requires the pinned v26.0 contract")
    if not settings.is_testing:
        raise PermissionError("Meta preflight requires the explicit testing environment")
    if settings.enabled or not settings.dry_run:
        raise PermissionError("Meta preflight requires read-only disabled and dry-run flags")
    if not settings.access_token or not settings.fb_page_id or not settings.ig_user_id:
        raise PermissionError("Meta preflight credential set is incomplete")


def _identity_id(identities: Mapping[str, Any], platform: str) -> str:
    identity = identities.get(platform)
    if not isinstance(identity, Mapping):
        raise PermissionError(f"{platform.title()} identity response is absent")
    remote_id = identity.get("id")
    if not isinstance(remote_id, str | int) or isinstance(remote_id, bool):
        raise PermissionError(f"{platform.title()} identity response has no valid id")
    return str(remote_id)


def _since(now: Callable[[], dt.datetime]) -> str:
    observed = now()
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("preflight clock must include a timezone")
    boundary = (observed.astimezone(dt.UTC) - READ_WINDOW).replace(microsecond=0)
    return boundary.isoformat().replace("+00:00", "Z")


def run_preflight(
    settings: Settings,
    client: ReadOnlyMeta,
    *,
    now: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.UTC),
) -> dict[str, str | bool]:
    """Run only identity and recent-publication reads; return no remote data."""

    _require_safe_configuration(settings)
    try:
        identities = client.whoami()
    except Exception as exc:
        raise RuntimeError(f"Meta identity read failed: {type(exc).__name__}") from None
    if not isinstance(identities, Mapping):
        raise PermissionError("Meta identity read returned an invalid document")
    if _identity_id(identities, "facebook") != settings.fb_page_id:
        raise PermissionError("Facebook identity does not match the configured asset")
    if _identity_id(identities, "instagram") != settings.ig_user_id:
        raise PermissionError("Instagram identity does not match the configured asset")

    since = _since(now)
    for platform in ("facebook", "instagram"):
        try:
            recent = client.recent_publications(platform, since=since, limit=1)
        except Exception as exc:
            raise RuntimeError(
                f"{platform.title()} reconciliation read failed: {type(exc).__name__}"
            ) from None
        if not isinstance(recent, list):
            raise RuntimeError(f"{platform.title()} reconciliation read returned invalid data")

    return {
        "facebook_identity": True,
        "facebook_recent_read": True,
        "graph_version": GRAPH_VERSION,
        "instagram_identity": True,
        "instagram_recent_read": True,
        "mode": "read_only",
    }


def main() -> int:
    settings = load_settings()
    result = run_preflight(settings, Meta(settings))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
