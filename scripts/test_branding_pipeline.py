#!/usr/bin/env python3
"""Regression tests for the single-brand push notification pipeline."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.push_payload import build_payload, public_post_image


def test_post_image_is_absolute_and_site_scoped():
    assert public_post_image("/images/stock/post-cover.jpg") == (
        "https://mragentes.com.ar/images/stock/post-cover.jpg"
    )
    assert public_post_image("https://evil.example/steal.jpg") is None
    assert public_post_image("/images/mragentes.png") is None


def test_blog_payload_carries_post_cover_and_new_brand_assets():
    payload = build_payload(
        title="Nueva nota",
        body="Entrá a leerla.",
        url="https://mragentes.com.ar/notas/nueva-nota/",
        image="/images/stock/post-cover.jpg",
    )
    assert payload["image"] == "https://mragentes.com.ar/images/stock/post-cover.jpg"
    assert payload["icon"] == "/faviconhand512.png"
    assert payload["badge"] == "/faviconhand512.png"


def test_repository_has_no_old_brand_references_in_runtime_or_metadata():
    files = [
        ROOT / "cf_worker.js",
        ROOT / "static" / "sw.js",
        ROOT / "static" / "manifest.json",
        ROOT / "static" / "opensearch.xml",
        ROOT / "hugo.toml",
        ROOT / "layouts" / "_default" / "baseof.html",
        ROOT / "scripts" / "publish_blog.py",
        ROOT / "scripts" / "publish_daily.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)
    for old in ("mragentes.png", "favicon_v2", "favicon_v3", "notif-icon", "badge-icon", "notif-image"):
        assert old not in text, old
    assert "/images/faviconhand512.png" not in text
    assert "faviconhand512.png" in text


def test_notification_has_only_the_site_action():
    service_worker = (ROOT / "static" / "sw.js").read_text(encoding="utf-8")
    assert "title: 'Cerrar'" not in service_worker
    assert "action: 'close'" not in service_worker
    assert service_worker.count("title: 'Leer nota'") == 2


if __name__ == "__main__":
    for test in (test_post_image_is_absolute_and_site_scoped,
                 test_blog_payload_carries_post_cover_and_new_brand_assets,
                 test_repository_has_no_old_brand_references_in_runtime_or_metadata,
                 test_notification_has_only_the_site_action):
        test()
    print("branding pipeline tests: ok")
