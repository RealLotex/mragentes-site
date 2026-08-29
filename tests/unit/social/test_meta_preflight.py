from __future__ import annotations

import datetime as dt
import importlib

import pytest

from scripts.social.config import Settings

NOW = dt.datetime(2026, 8, 28, 18, 0, tzinfo=dt.UTC)


class ReadOnlyMetaFake:
    def __init__(
        self,
        *,
        facebook_id: str = "123",
        instagram_id: str = "456",
        recent_error: Exception | None = None,
    ) -> None:
        self.facebook_id = facebook_id
        self.instagram_id = instagram_id
        self.recent_error = recent_error
        self.calls: list[tuple[str, object]] = []

    def whoami(self) -> dict[str, dict[str, str]]:
        self.calls.append(("whoami", None))
        return {
            "facebook": {"id": self.facebook_id, "name": "private-page-name"},
            "instagram": {"id": self.instagram_id, "username": "private-handle"},
        }

    def recent_publications(
        self, platform: str, *, since: str, limit: int = 25
    ) -> list[dict[str, str]]:
        self.calls.append(("recent_publications", (platform, since, limit)))
        if self.recent_error is not None:
            raise self.recent_error
        return [
            {
                "platform": platform,
                "remote_id": f"private-{platform}-id",
                "created_at": "2026-08-28T17:00:00+00:00",
                "permalink": f"https://{platform}.example/private",
                "caption_hash": "sha256:private-copy-hash",
            }
        ]

    def publish(self, *args, **kwargs):
        raise AssertionError("read-only preflight must not expose a publish method")


def safe_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "access_token": "secret-token-sentinel",
        "fb_page_id": "123",
        "ig_user_id": "456",
        "graph_version": "v26.0",
        "enabled": False,
        "dry_run": True,
        "meta_environment": "testing",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.trace("META-PREFLIGHT-001")
@pytest.mark.red_expected
def test_read_only_preflight_validates_exact_identities_and_reconciliation_reads() -> None:
    module = importlib.import_module("scripts.social.meta_preflight")
    client = ReadOnlyMetaFake()

    result = module.run_preflight(safe_settings(), client, now=lambda: NOW)

    assert result == {
        "facebook_identity": True,
        "facebook_recent_read": True,
        "graph_version": "v26.0",
        "instagram_identity": True,
        "instagram_recent_read": True,
        "mode": "read_only",
    }
    assert client.calls[0] == ("whoami", None)
    assert [call[1][0] for call in client.calls[1:]] == ["facebook", "instagram"]
    assert all(call[1][2] == 1 for call in client.calls[1:])


@pytest.mark.trace("META-PREFLIGHT-002")
@pytest.mark.red_expected
@pytest.mark.parametrize(
    "settings",
    (
        safe_settings(access_token=""),
        safe_settings(fb_page_id=""),
        safe_settings(ig_user_id=""),
        safe_settings(graph_version="v21.0"),
        safe_settings(meta_environment="disabled"),
        safe_settings(enabled=True),
        safe_settings(dry_run=False),
    ),
)
def test_read_only_preflight_fails_closed_before_network_for_unsafe_config(
    settings: Settings,
) -> None:
    module = importlib.import_module("scripts.social.meta_preflight")
    client = ReadOnlyMetaFake()

    with pytest.raises(PermissionError, match="preflight|read-only|v26|credential|testing"):
        module.run_preflight(settings, client, now=lambda: NOW)

    assert client.calls == []


@pytest.mark.trace("META-PREFLIGHT-003")
@pytest.mark.red_expected
@pytest.mark.parametrize(
    ("client", "message"),
    (
        (ReadOnlyMetaFake(facebook_id="999"), "Facebook"),
        (ReadOnlyMetaFake(instagram_id="999"), "Instagram"),
        (ReadOnlyMetaFake(recent_error=RuntimeError("read denied")), "read"),
    ),
)
def test_read_only_preflight_rejects_wrong_assets_or_missing_read_capability(
    client: ReadOnlyMetaFake,
    message: str,
) -> None:
    module = importlib.import_module("scripts.social.meta_preflight")

    with pytest.raises((PermissionError, RuntimeError), match=message):
        module.run_preflight(safe_settings(), client, now=lambda: NOW)


@pytest.mark.trace("META-PREFLIGHT-004")
@pytest.mark.red_expected
def test_read_only_preflight_result_never_contains_remote_data_or_credentials() -> None:
    module = importlib.import_module("scripts.social.meta_preflight")
    settings = safe_settings()
    result = module.run_preflight(settings, ReadOnlyMetaFake(), now=lambda: NOW)
    serialized = repr(result)

    for private_value in (
        settings.access_token,
        settings.fb_page_id,
        settings.ig_user_id,
        "private-page-name",
        "private-handle",
        "private-facebook-id",
        "private-instagram-id",
        "private-copy-hash",
    ):
        assert private_value not in serialized
