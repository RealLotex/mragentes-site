from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

import pytest

from scripts.automation import social_guard
from scripts.social import ledger
from scripts.social.config import Settings
from scripts.social.delivery import build_blog_note_draft, deliver_draft
from scripts.social.notas import Nota
from scripts.social.publisher import Result


NOW = "2026-08-27T16:05:00+00:00"


def _draft(root: Path) -> dict:
    asset = root / "static" / "images" / "social" / "2026-08-27-prueba.webp"
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_bytes(b"safe-image-fixture")
    draft = {
        "schema_version": 1,
        "run_id": "social:daily_owned:2026-08-27",
        "kind": "daily_owned",
        "topic": "Automatización con salida manual",
        "topic_hash": "sha256:topic-safe",
        "content_hash": "pending",
        "dedupe_key": "pending",
        "asset": {
            "path": "static/images/social/2026-08-27-prueba.webp",
            "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
            "alt": "Diagrama de automatización con una salida manual",
        },
        "captions": {
            "facebook": "Automatizar también exige una salida manual.",
            "instagram": "Una automatización segura conserva salida. #automatización",
        },
        "created_at": "2026-08-27T13:00:00-03:00",
    }
    draft["content_hash"] = social_guard.content_hash(draft)
    draft["dedupe_key"] = f"daily_owned:2026-08-27:{draft['content_hash']}"
    return draft


def _settings() -> Settings:
    return Settings(
        access_token="test-token",
        fb_page_id="123",
        ig_user_id="456",
        enabled=True,
        dry_run=False,
        site_base_url="https://mragentes.com.ar",
        meta_environment="testing",
    )


class FakeMeta:
    def __init__(
        self,
        *,
        facebook: list[Result] | None = None,
        instagram: list[Result] | None = None,
        recent: dict[str, list[dict]] | None = None,
    ) -> None:
        self.facebook = list(facebook or [Result("facebook", "foto", True, id="fb-1")])
        self.instagram = list(instagram or [Result("instagram", "feed", True, id="ig-1")])
        self.recent = recent or {"facebook": [], "instagram": []}
        self.calls: list[tuple[str, object]] = []

    def recent_publications(self, platform: str, *, since: str, limit: int = 25):
        self.calls.append(("recent", platform))
        return self.recent.get(platform, [])

    def facebook_photo(self, asset: Path, caption: str) -> Result:
        self.calls.append(("facebook", (asset.name, caption)))
        return self.facebook.pop(0)

    def instagram_image(self, asset_url: str, caption: str) -> Result:
        self.calls.append(("instagram", (asset_url, caption)))
        return self.instagram.pop(0)


@pytest.mark.trace("SOCIAL-DELIVERY-001")
@pytest.mark.red_expected
def test_delivery_validates_reconciles_checkpoints_and_completes(tmp_path: Path) -> None:
    draft = _draft(tmp_path)
    meta = FakeMeta()
    ledger_path = tmp_path / "reports" / "ledger.json"
    probes: list[str] = []

    result = deliver_draft(
        draft,
        settings=_settings(),
        root=tmp_path,
        ledger_path=ledger_path,
        meta=meta,
        public_probe=lambda url: probes.append(url) or True,
        now=lambda: NOW,
    )

    assert result["status"] == "complete"
    assert result["confirmed"] == ["facebook", "instagram"]
    assert probes == ["https://mragentes.com.ar/images/social/2026-08-27-prueba.webp"]
    stored = next(iter(ledger.load_ledger(ledger_path)["entries"].values()))
    assert stored["status"] == "complete"
    assert stored["platforms"]["facebook"]["remote_id"] == "fb-1"
    assert stored["platforms"]["instagram"]["remote_id"] == "ig-1"


@pytest.mark.trace("SOCIAL-DELIVERY-002")
@pytest.mark.red_expected
def test_partial_retry_skips_confirmed_platform_and_only_retries_safe_failure(
    tmp_path: Path,
) -> None:
    draft = _draft(tmp_path)
    path = tmp_path / "ledger.json"
    first_meta = FakeMeta(
        instagram=[
            Result(
                "instagram",
                "feed",
                False,
                error="rate limited",
                category="retryable",
                retryable=True,
            )
        ]
    )
    first = deliver_draft(
        draft,
        settings=_settings(),
        root=tmp_path,
        ledger_path=path,
        meta=first_meta,
        public_probe=lambda url: True,
        now=lambda: NOW,
    )
    assert first["status"] == "partial"
    assert first["confirmed"] == ["facebook"]

    retry_meta = FakeMeta(instagram=[Result("instagram", "feed", True, id="ig-retry")])
    retry = deliver_draft(
        draft,
        settings=_settings(),
        root=tmp_path,
        ledger_path=path,
        meta=retry_meta,
        public_probe=lambda url: True,
        now=lambda: "2026-08-27T16:10:00+00:00",
    )
    assert retry["status"] == "complete"
    assert not any(call[0] == "facebook" for call in retry_meta.calls)
    assert sum(call[0] == "instagram" for call in retry_meta.calls) == 1


@pytest.mark.trace("SOCIAL-DELIVERY-003")
@pytest.mark.red_expected
def test_uncertain_effect_never_republishes_without_one_remote_match(tmp_path: Path) -> None:
    draft = _draft(tmp_path)
    path = tmp_path / "ledger.json"
    uncertain = FakeMeta(
        instagram=[
            Result(
                "instagram",
                "feed",
                False,
                error="timeout after request",
                category="uncertain",
            )
        ]
    )
    first = deliver_draft(
        draft,
        settings=_settings(),
        root=tmp_path,
        ledger_path=path,
        meta=uncertain,
        public_probe=lambda url: True,
        now=lambda: NOW,
    )
    assert first["status"] == "needs_review"

    retry_meta = FakeMeta()
    second = deliver_draft(
        draft,
        settings=_settings(),
        root=tmp_path,
        ledger_path=path,
        meta=retry_meta,
        public_probe=lambda url: True,
        now=lambda: "2026-08-27T16:10:00+00:00",
    )
    assert second["status"] == "needs_review"
    assert not any(call[0] in {"facebook", "instagram"} for call in retry_meta.calls)


@pytest.mark.trace("SOCIAL-DELIVERY-004")
@pytest.mark.red_expected
def test_remote_match_recovers_lost_local_ledger_without_duplicate(tmp_path: Path) -> None:
    draft = _draft(tmp_path)
    asset_hash = "sha256:" + draft["asset"]["sha256"]
    recent = {}
    for platform in ("facebook", "instagram"):
        caption = draft["captions"][platform]
        recent[platform] = [
            {
                "platform": platform,
                "remote_id": f"{platform}-remote",
                "permalink": f"https://example.test/{platform}-remote",
                "created_at": "2026-08-27T16:01:00+00:00",
                "caption_hash": "sha256:" + hashlib.sha256(caption.encode()).hexdigest(),
                "asset_hash": asset_hash,
            }
        ]
    meta = FakeMeta(recent=recent)
    result = deliver_draft(
        draft,
        settings=_settings(),
        root=tmp_path,
        ledger_path=tmp_path / "new-ledger.json",
        meta=meta,
        public_probe=lambda url: True,
        now=lambda: NOW,
    )
    assert result["status"] == "complete"
    assert not any(call[0] in {"facebook", "instagram"} for call in meta.calls)


@pytest.mark.trace("SOCIAL-DELIVERY-005")
@pytest.mark.red_expected
def test_invalid_asset_or_disabled_testing_configuration_causes_zero_remote_calls(
    tmp_path: Path,
) -> None:
    draft = _draft(tmp_path)
    draft["asset"]["sha256"] = "0" * 64
    meta = FakeMeta()
    with pytest.raises(ValueError, match="hash"):
        deliver_draft(
            draft,
            settings=_settings(),
            root=tmp_path,
            ledger_path=tmp_path / "ledger.json",
            meta=meta,
            public_probe=lambda url: True,
            now=lambda: NOW,
        )
    assert not meta.calls

    settings = _settings()
    settings.meta_environment = "disabled"
    with pytest.raises(PermissionError, match="testing"):
        deliver_draft(
            _draft(tmp_path),
            settings=settings,
            root=tmp_path,
            ledger_path=tmp_path / "ledger.json",
            meta=meta,
            public_probe=lambda url: True,
            now=lambda: NOW,
        )
    assert not meta.calls


@pytest.mark.trace("SOCIAL-DELIVERY-006")
@pytest.mark.red_expected
def test_blog_note_draft_uses_deployed_cover_explicit_slug_and_distinct_copy(
    tmp_path: Path,
) -> None:
    cover = tmp_path / "static" / "images" / "stock" / "cover.webp"
    cover.parent.mkdir(parents=True)
    cover.write_bytes(b"deployed-cover")
    note = Nota(
        path=tmp_path / "content" / "notas" / "portable.md",
        title="Automatización útil con control humano",
        date=dt.date(2026, 8, 27),
        description="Una guía concreta para automatizar y conservar una salida manual.",
        image="/images/stock/cover.webp",
        image_alt="Persona revisando un flujo automatizado",
        body=(
            "Un proceso automatizado mejora cuando el equipo define responsables y una salida manual.\n\n"
            "## Qué revisar antes de empezar\n\n"
            "Cada prueba necesita una métrica y una persona que pueda detenerla.\n"
        ),
        canonical_slug="automatización-útil-controlada",
    )
    draft = build_blog_note_draft(
        note,
        deploy_sha="b" * 40,
        root=tmp_path,
        created_at="2026-08-27T12:00:00-03:00",
    )
    assert draft["kind"] == "blog_note"
    assert draft["note_slug"] == "automatización-útil-controlada"
    assert draft["asset"]["path"] == "static/images/stock/cover.webp"
    assert draft["captions"]["facebook"] != draft["captions"]["instagram"]
    assert draft["content_hash"] == social_guard.content_hash(draft)
