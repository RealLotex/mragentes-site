from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.social import config


ENV_KEYS = (
    "META_ACCESS_TOKEN",
    "FB_PAGE_TOKEN",
    "PAGE_ACCESS_TOKEN",
    "FB_PAGE_ID",
    "IG_USER_ID",
    "IG_BUSINESS_ID",
    "META_GRAPH_VERSION",
    "META_ENVIRONMENT",
    "SOCIAL_ENABLED",
    "SOCIAL_DRY_RUN",
    "SITE_BASE_URL",
    "SOCIAL_IMAGE_BASE",
    "GITHUB_REPOSITORY",
    "GITHUB_REF_NAME",
    "SOCIAL_GIT_BRANCH",
    "SOCIAL_HANDLE",
)


def _clear_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_KEYS:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.trace("META-CONFIG-001")
@pytest.mark.baseline_green
def test_load_dotenv_parses_exports_quotes_comments_and_ignores_malformed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comentario\n"
        "export ALPHA='uno dos'\n"
        'BETA="tres # cuatro"\n'
        "GAMMA=cinco # comentario final\n"
        "SIN_IGUAL\n"
        "=sin-clave\n",
        encoding="utf-8",
    )
    for key in ("ALPHA", "BETA", "GAMMA"):
        monkeypatch.delenv(key, raising=False)

    values = config.load_dotenv(env_file)

    assert values == {"ALPHA": "uno dos", "BETA": "tres # cuatro", "GAMMA": "cinco"}
    assert os.environ["ALPHA"] == "uno dos"
    assert os.environ["BETA"] == "tres # cuatro"
    assert os.environ["GAMMA"] == "cinco"


@pytest.mark.trace("META-CONFIG-002")
@pytest.mark.baseline_green
def test_load_dotenv_preserves_environment_unless_override_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("VALUE=archivo\n", encoding="utf-8")
    monkeypatch.setenv("VALUE", "entorno")

    assert config.load_dotenv(env_file, override=False)["VALUE"] == "archivo"
    assert os.environ["VALUE"] == "entorno"
    config.load_dotenv(env_file, override=True)
    assert os.environ["VALUE"] == "archivo"


@pytest.mark.trace("META-CONFIG-003")
@pytest.mark.baseline_green
def test_bool_accepts_documented_values_and_falls_back_for_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for raw in config.TRUTHY:
        monkeypatch.setenv("FLAG", f" {raw.upper()} ")
        assert config._bool("FLAG", False) is True
    for raw in config.FALSY:
        monkeypatch.setenv("FLAG", f" {raw.upper()} ")
        assert config._bool("FLAG", True) is False
    monkeypatch.setenv("FLAG", "quizás")
    assert config._bool("FLAG", True) is True
    monkeypatch.delenv("FLAG")
    assert config._bool("FLAG", False) is False


@pytest.mark.trace("META-CONFIG-004")
@pytest.mark.baseline_green
def test_settings_derive_graph_root_and_platform_capabilities() -> None:
    empty = config.Settings()
    facebook = config.Settings(access_token="token", fb_page_id="123")
    instagram = config.Settings(access_token="token", ig_user_id="456")

    assert empty.graph_root == "https://graph.facebook.com/v21.0"
    assert empty.can_post is False
    assert facebook.can_post_facebook is True
    assert facebook.can_post_instagram is False
    assert instagram.can_post_instagram is True
    assert instagram.can_post is True


@pytest.mark.trace("META-CONFIG-005")
@pytest.mark.baseline_green
def test_public_url_candidates_encode_unicode_deduplicate_and_keep_priority() -> None:
    settings = config.Settings(
        image_base="https://cdn.example/social/",
        repository="owner/repo",
        branch="automation/social/2026-08-26",
        site_base_url="https://site.example/",
    )

    candidates = settings.public_url_candidates("día uno/lámina 01.jpg")

    assert candidates == [
        "https://cdn.example/social/d%C3%ADa%20uno/l%C3%A1mina%2001.jpg",
        "https://raw.githubusercontent.com/owner/repo/automation/social/2026-08-26/"
        "static/social/d%C3%ADa%20uno/l%C3%A1mina%2001.jpg",
        "https://site.example/social/d%C3%ADa%20uno/l%C3%A1mina%2001.jpg",
    ]
    duplicate = config.Settings(
        image_base="https://site.example/social", repository="", site_base_url="https://site.example"
    )
    assert duplicate.public_url_candidates("uno.jpg") == [
        "https://site.example/social/uno.jpg"
    ]


@pytest.mark.trace("META-CONFIG-006")
@pytest.mark.baseline_green
def test_load_settings_reads_aliases_booleans_and_emits_actionable_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_settings_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "FB_PAGE_TOKEN=token-de-prueba\n"
        "FB_PAGE_ID=123\n"
        "IG_BUSINESS_ID=456\n"
        "SOCIAL_ENABLED=no\n"
        "SOCIAL_DRY_RUN=yes\n"
        "META_GRAPH_VERSION=v99.0\n"
        "GITHUB_REF_NAME=automation/social/test\n",
        encoding="utf-8",
    )

    settings = config.load_settings(env_file)

    assert settings.access_token == "token-de-prueba"
    assert settings.fb_page_id == "123"
    assert settings.ig_user_id == "456"
    assert settings.enabled is False
    assert settings.dry_run is True
    assert settings.graph_version == "v99.0"
    assert settings.branch == "automation/social/test"
    assert settings.warnings == []

    _clear_settings_env(monkeypatch)
    missing = config.load_settings(tmp_path / "missing.env")
    assert len(missing.warnings) == 3
    assert all("vacío" in warning or "queda fuera" in warning for warning in missing.warnings)


@pytest.mark.trace("META-CONFIG-007")
@pytest.mark.red_expected
def test_public_url_candidates_reject_traversal_absolute_urls_and_credentials() -> None:
    settings = config.Settings(repository="owner/repo")
    invalid = (
        "../secret.jpg",
        "%2e%2e/secret.jpg",
        "/absolute.jpg",
        "https://attacker.example/image.jpg",
        "user:password@host/image.jpg",
    )

    for filename in invalid:
        with pytest.raises(ValueError, match="imagen|ruta|filename|segura"):
            settings.public_url_candidates(filename)


@pytest.mark.trace("META-CONFIG-008")
@pytest.mark.red_expected
def test_settings_repr_and_diagnostics_never_reveal_access_token() -> None:
    secret = "meta-secret-sentinel-123456789"
    settings = config.Settings(access_token=secret, fb_page_id="123", ig_user_id="456")

    assert secret not in repr(settings)
    assert secret not in "\n".join(settings.warnings)


@pytest.mark.trace("META-CONFIG-009")
@pytest.mark.red_expected
def test_meta_testing_environment_is_explicit_and_defaults_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_settings_env(monkeypatch)
    monkeypatch.setenv("META_ENVIRONMENT", "testing")

    settings = config.load_settings(tmp_path / "missing.env")

    assert settings.meta_environment == "testing"
    assert settings.is_testing is True


@pytest.mark.trace("META-CONFIG-010")
@pytest.mark.red_expected
def test_load_settings_rejects_malformed_graph_version_and_non_numeric_asset_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_settings_env(monkeypatch)
    monkeypatch.setenv("META_GRAPH_VERSION", "latest;drop")
    monkeypatch.setenv("META_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("FB_PAGE_ID", "page/not-numeric")
    monkeypatch.setenv("IG_USER_ID", "instagram-not-numeric")

    with pytest.raises(ValueError, match="Graph|ID|configuración"):
        config.load_settings(tmp_path / "missing.env")
