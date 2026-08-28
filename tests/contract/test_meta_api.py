from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.social import publisher
from scripts.social.publisher import Meta, PublishError, Result
from tests.unit.social._helpers import StubRequests, StubResponse, configured_settings


META_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "meta"


@pytest.mark.trace("META-FB-001")
@pytest.mark.baseline_green
def test_publish_error_is_a_runtime_domain_error_and_result_lines_cover_all_states() -> None:
    assert issubclass(PublishError, RuntimeError)
    assert Result("facebook", "feed", True, id="fb-1").line() == "  ✔ facebook feed: fb-1"
    assert Result("facebook", "feed", False, error="bad request").line() == (
        "  ✖ facebook feed: bad request"
    )
    assert Result("instagram", "feed", False, skipped="disabled").line() == (
        "  ○ instagram feed: omitido (disabled)"
    )


@pytest.mark.trace("META-FB-002")
@pytest.mark.baseline_green
def test_meta_requires_requests_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(publisher, "requests", None)

    with pytest.raises(PublishError, match="requests"):
        Meta(configured_settings())._require_requests()


@pytest.mark.trace("META-FB-003")
@pytest.mark.baseline_green
def test_meta_post_and_get_build_versioned_urls_copy_payload_and_apply_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = StubRequests(
        post_responses=[StubResponse(body={"id": "post-1"})],
        get_responses=[StubResponse(body={"id": "page-1"})],
    )
    monkeypatch.setattr(publisher, "requests", transport)
    settings = configured_settings(access_token="sentinel-token")
    meta = Meta(settings)
    original_data = {"message": "hola"}
    original_params = {"fields": "id"}

    assert meta._post("/123/feed", original_data) == {"id": "post-1"}
    assert meta._get("123", original_params) == {"id": "page-1"}

    assert original_data == {"message": "hola"}
    assert original_params == {"fields": "id"}
    assert transport.post_calls == [
        {
            "url": "https://graph.facebook.com/v21.0/123/feed",
            "data": {"message": "hola", "access_token": "sentinel-token"},
            "files": None,
            "timeout": publisher.TIMEOUT,
        }
    ]
    assert transport.get_calls == [
        {
            "url": "https://graph.facebook.com/v21.0/123",
            "params": {"fields": "id", "access_token": "sentinel-token"},
            "timeout": publisher.TIMEOUT,
        }
    ]


@pytest.mark.trace("META-FB-004")
@pytest.mark.baseline_green
def test_unwrap_accepts_success_and_rejects_invalid_json_http_and_graph_errors() -> None:
    assert Meta._unwrap(StubResponse(status_code=200, body={"id": "ok"})) == {"id": "ok"}

    with pytest.raises(PublishError, match="HTTP 502"):
        Meta._unwrap(
            StubResponse(status_code=502, text="upstream non-json", json_error=ValueError("bad json"))
        )
    with pytest.raises(PublishError, match="OAuthException 190: expired"):
        Meta._unwrap(
            StubResponse(
                status_code=400,
                body={"error": {"type": "OAuthException", "code": 190, "message": "expired"}},
            )
        )
    with pytest.raises(PublishError, match="HTTP 500"):
        Meta._unwrap(StubResponse(status_code=500, body={"message": "server"}))


@pytest.mark.trace("META-FB-005")
@pytest.mark.baseline_green
def test_whoami_requests_only_configured_assets_with_minimal_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = configured_settings()
    meta = Meta(settings)
    calls: list[tuple[str, dict]] = []

    def fake_get(path: str, params=None):
        calls.append((path, params))
        return {"id": path}

    monkeypatch.setattr(meta, "_get", fake_get)
    result = meta.whoami()

    assert result == {
        "facebook": {"id": settings.fb_page_id},
        "instagram": {"id": settings.ig_user_id},
    }
    assert calls == [
        (settings.fb_page_id, {"fields": "id,name,fan_count"}),
        (settings.ig_user_id, {"fields": "id,username,followers_count"}),
    ]


@pytest.mark.trace("META-FB-006")
@pytest.mark.baseline_green
def test_facebook_photo_skips_without_credentials_and_does_not_call_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meta = Meta(configured_settings(access_token="", fb_page_id=""))
    monkeypatch.setattr(
        meta,
        "_post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("transport must not run")),
    )

    result = meta.facebook_photo("https://cdn.example/image.jpg", "caption")

    assert result.ok is False
    assert result.skipped
    assert result.network == "facebook" and result.kind == "feed"


@pytest.mark.trace("META-FB-007")
@pytest.mark.baseline_green
def test_facebook_photo_uploads_local_file_or_uses_remote_url_and_adds_link_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image = tmp_path / "image.jpg"
    image.write_bytes(b"jpeg")
    meta = Meta(configured_settings())
    calls: list[tuple[str, dict, dict | None]] = []

    def fake_post(path: str, data: dict, files=None):
        calls.append((path, dict(data), files))
        return {"post_id": f"post-{len(calls)}"}

    monkeypatch.setattr(meta, "_post", fake_post)
    local = meta.facebook_photo(image, "caption", "https://site.example/note")
    remote = meta.facebook_photo(
        "https://cdn.example/image.jpg",
        "caption https://site.example/note",
        "https://site.example/note",
    )

    assert local.ok and local.id == "post-1" and local.url.endswith("post-1")
    assert calls[0][0].endswith("/photos")
    assert calls[0][1]["caption"].count("https://site.example/note") == 1
    assert calls[0][2]["source"][0] == "image.jpg"
    assert remote.ok and remote.id == "post-2"
    assert calls[1][1]["url"] == "https://cdn.example/image.jpg"
    assert calls[1][1]["caption"].count("https://site.example/note") == 1


@pytest.mark.trace("META-FB-008")
@pytest.mark.baseline_green
def test_facebook_photo_converts_graph_error_to_failed_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meta = Meta(configured_settings())
    monkeypatch.setattr(meta, "_post", lambda *args, **kwargs: (_ for _ in ()).throw(PublishError("denied")))

    result = meta.facebook_photo("https://cdn.example/image.jpg", "caption")

    assert result.ok is False and result.error == "denied"


@pytest.mark.trace("META-FB-009")
@pytest.mark.baseline_green
def test_facebook_album_rejects_empty_and_skips_without_credentials() -> None:
    empty = Meta(configured_settings()).facebook_album([], "caption")
    skipped = Meta(configured_settings(access_token="")).facebook_album(["one.jpg"], "caption")

    assert empty.ok is False and empty.error == "sin imágenes"
    assert skipped.ok is False and skipped.skipped


@pytest.mark.trace("META-FB-010")
@pytest.mark.baseline_green
def test_facebook_album_uploads_children_unpublished_then_one_attached_feed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local = tmp_path / "local.jpg"
    local.write_bytes(b"jpeg")
    meta = Meta(configured_settings())
    calls: list[tuple[str, dict, dict | None]] = []

    def fake_post(path: str, data: dict, files=None):
        calls.append((path, dict(data), files))
        if path.endswith("/photos"):
            return {"id": f"photo-{len(calls)}"}
        return {"id": "feed-1"}

    monkeypatch.setattr(meta, "_post", fake_post)
    result = meta.facebook_album(
        [local, "https://cdn.example/remote.jpg"], "caption", "https://site.example/note"
    )

    assert result.ok and result.id == "feed-1"
    assert len(calls) == 3
    assert calls[0][1] == {"published": "false"}
    assert calls[0][2]["source"][0] == "local.jpg"
    assert calls[1][1] == {"url": "https://cdn.example/remote.jpg", "published": "false"}
    attached = json.loads(calls[2][1]["attached_media"])
    assert attached == [{"media_fbid": "photo-1"}, {"media_fbid": "photo-2"}]
    assert calls[2][1]["message"].count("https://site.example/note") == 1


@pytest.mark.trace("META-FB-011")
@pytest.mark.baseline_green
def test_facebook_album_caps_ten_images_and_fails_when_no_child_gets_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meta = Meta(configured_settings())
    calls: list[str] = []

    def no_ids(path: str, data: dict, files=None):
        del data, files
        calls.append(path)
        return {}

    monkeypatch.setattr(meta, "_post", no_ids)
    result = meta.facebook_album([f"https://cdn.example/{index}.jpg" for index in range(12)], "caption")

    assert result.ok is False and "no se pudieron" in result.error
    assert len(calls) == 10
    assert all(path.endswith("/photos") for path in calls)


@pytest.mark.trace("META-FB-012")
@pytest.mark.baseline_green
def test_facebook_story_requires_existing_file_and_returns_logic_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image = tmp_path / "story.jpg"
    image.write_bytes(b"jpeg")
    meta = Meta(configured_settings())
    calls: list[tuple[str, dict, dict]] = []
    monkeypatch.setattr(
        meta,
        "_post",
        lambda path, data, files=None: calls.append((path, data, files)) or {"logic_id": "story-1"},
    )

    missing = meta.facebook_story(tmp_path / "missing.jpg")
    published = meta.facebook_story(image)

    assert missing.ok is False and "no existe" in missing.error
    assert published.ok is True and published.id == "story-1"
    assert calls[0][0].endswith("/stories")
    assert calls[0][2]["source"][0] == "story.jpg"


@pytest.mark.trace("META-FB-013")
@pytest.mark.red_expected
def test_transport_timeout_is_classified_as_failed_result_not_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = StubRequests(post_responses=[TimeoutError("simulated timeout")])
    monkeypatch.setattr(publisher, "requests", transport)

    result = Meta(configured_settings()).facebook_photo("https://cdn.example/image.jpg", "caption")

    assert result.ok is False
    assert result.retryable is False
    assert result.category == "uncertain"
    assert result.error_code == "transport_timeout"


@pytest.mark.trace("META-FB-014")
@pytest.mark.red_expected
def test_result_line_redacts_access_tokens_credentials_and_long_remote_payloads() -> None:
    secret = "EAAB-meta-secret-sentinel-123456789"
    result = Result(
        "facebook",
        "feed",
        False,
        error=f"OAuth failed access_token={secret} response={'x' * 1000}",
    )

    line = result.line()

    assert secret not in line
    assert "access_token=" not in line
    assert len(line) <= 300


@pytest.mark.trace("META-IG-001")
@pytest.mark.baseline_green
def test_ig_container_requires_returned_id_and_publish_returns_media_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meta = Meta(configured_settings())
    monkeypatch.setattr(meta, "_post", lambda path, params: {})
    with pytest.raises(PublishError, match="id de contenedor"):
        meta._ig_container({"image_url": "https://cdn.example/image.jpg"})

    responses = iter(({"id": "container-1"}, {"id": "media-1"}))
    monkeypatch.setattr(meta, "_post", lambda path, params: next(responses))
    assert meta._ig_container({"image_url": "https://cdn.example/image.jpg"}) == "container-1"
    assert meta._ig_publish("container-1") == "media-1"


@pytest.mark.trace("META-IG-002")
@pytest.mark.baseline_green
def test_ig_wait_handles_finished_pending_error_and_timeout_without_real_sleep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meta = Meta(configured_settings())
    sleeps: list[float] = []
    monkeypatch.setattr(publisher.time, "sleep", sleeps.append)

    finished = iter(({"status_code": "IN_PROGRESS"}, {"status_code": "FINISHED"}))
    monkeypatch.setattr(meta, "_get", lambda path, params=None: next(finished))
    meta._ig_wait("container", tries=3, delay=7)
    assert sleeps == [1.0]

    monkeypatch.setattr(meta, "_get", lambda path, params=None: {"status_code": "ERROR", "status": "bad"})
    with pytest.raises(PublishError, match="bad"):
        meta._ig_wait("container", tries=1, delay=0)

    monkeypatch.setattr(meta, "_get", lambda path, params=None: {"status_code": "IN_PROGRESS"})
    with pytest.raises(PublishError, match="no terminó"):
        meta._ig_wait("container", tries=2, delay=0)


@pytest.mark.trace("META-IG-003")
@pytest.mark.baseline_green
def test_instagram_image_runs_container_wait_publish_sequence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meta = Meta(configured_settings())
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        meta,
        "_ig_container",
        lambda params: calls.append(("container", params)) or "container-1",
    )
    monkeypatch.setattr(meta, "_ig_wait", lambda cid: calls.append(("wait", cid)))
    monkeypatch.setattr(meta, "_ig_publish", lambda cid: calls.append(("publish", cid)) or "media-1")

    result = meta.instagram_image("https://cdn.example/image.jpg", "caption")

    assert result == Result("instagram", "feed", True, id="media-1")
    assert calls == [
        ("container", {"image_url": "https://cdn.example/image.jpg", "caption": "caption"}),
        ("wait", "container-1"),
        ("publish", "container-1"),
    ]


@pytest.mark.trace("META-IG-004")
@pytest.mark.baseline_green
def test_instagram_methods_skip_without_credentials_and_convert_publish_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = Meta(configured_settings(access_token="", ig_user_id=""))
    assert missing.instagram_image("url", "caption").skipped
    assert missing.instagram_carousel(["one", "two"], "caption").skipped
    assert missing.instagram_story("url").skipped

    meta = Meta(configured_settings())
    monkeypatch.setattr(meta, "_ig_container", lambda params: (_ for _ in ()).throw(PublishError("bad")))
    assert meta.instagram_image("url", "caption").error == "bad"
    assert meta.instagram_carousel(["one", "two"], "caption").error == "bad"
    assert meta.instagram_story("url").error == "bad"


@pytest.mark.trace("META-IG-005")
@pytest.mark.baseline_green
def test_instagram_carousel_builds_children_parent_waits_and_caps_ten(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meta = Meta(configured_settings())
    container_params: list[dict] = []
    waits: list[str] = []

    def container(params: dict) -> str:
        container_params.append(params)
        return f"container-{len(container_params)}"

    monkeypatch.setattr(meta, "_ig_container", container)
    monkeypatch.setattr(meta, "_ig_wait", waits.append)
    monkeypatch.setattr(meta, "_ig_publish", lambda cid: "media-final")
    urls = [f"https://cdn.example/{index}.jpg" for index in range(12)]

    result = meta.instagram_carousel(urls, "caption")

    assert result.ok and result.id == "media-final" and result.kind == "carrusel"
    assert len(container_params) == 11
    assert all(item["is_carousel_item"] == "true" for item in container_params[:10])
    assert container_params[-1] == {
        "media_type": "CAROUSEL",
        "children": ",".join(f"container-{index}" for index in range(1, 11)),
        "caption": "caption",
    }
    assert waits == [*(f"container-{index}" for index in range(1, 11)), "container-11"]


@pytest.mark.trace("META-IG-006")
@pytest.mark.baseline_green
def test_single_item_carousel_delegates_to_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meta = Meta(configured_settings())
    monkeypatch.setattr(
        meta,
        "instagram_image",
        lambda url, caption: Result("instagram", "feed", True, id=f"{url}:{caption}"),
    )

    assert meta.instagram_carousel(["one"], "caption").id == "one:caption"


@pytest.mark.trace("META-IG-007")
@pytest.mark.red_expected
def test_empty_instagram_carousel_returns_domain_failure_without_index_error() -> None:
    result = Meta(configured_settings()).instagram_carousel([], "caption")

    assert result.ok is False
    assert result.error_code == "empty_media"
    assert "imagen" in result.error.lower()


@pytest.mark.trace("META-IG-008")
@pytest.mark.baseline_green
def test_instagram_story_sets_stories_media_type_and_publishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meta = Meta(configured_settings())
    params: list[dict] = []
    waits: list[str] = []
    monkeypatch.setattr(meta, "_ig_container", lambda value: params.append(value) or "story-container")
    monkeypatch.setattr(meta, "_ig_wait", waits.append)
    monkeypatch.setattr(meta, "_ig_publish", lambda cid: "story-media")

    result = meta.instagram_story("https://cdn.example/story.jpg")

    assert result.ok and result.id == "story-media" and result.kind == "historia"
    assert params == [
        {"image_url": "https://cdn.example/story.jpg", "media_type": "STORIES"}
    ]
    assert waits == ["story-container"]


@pytest.mark.trace("META-IG-009")
@pytest.mark.baseline_green
def test_head_ok_uses_get_fallback_for_405_and_returns_false_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = StubRequests(
        head_responses=[StubResponse(status_code=200), StubResponse(status_code=405), OSError("offline")],
        get_responses=[StubResponse(status_code=200)],
    )
    monkeypatch.setattr(publisher, "requests", transport)

    assert publisher.head_ok("https://cdn.example/one.jpg", timeout=4) is True
    assert publisher.head_ok("https://cdn.example/two.jpg", timeout=4) is True
    assert publisher.head_ok("https://cdn.example/three.jpg", timeout=4) is False
    assert transport.get_calls == [
        {"url": "https://cdn.example/two.jpg", "timeout": 4, "stream": True}
    ]


@pytest.mark.trace("META-IG-010")
@pytest.mark.baseline_green
def test_resolve_public_url_uses_first_live_candidate_and_bounded_injected_clock(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = configured_settings()
    candidates = settings.public_url_candidates("daily.jpg")
    calls: list[str] = []

    def first_live(url: str) -> bool:
        calls.append(url)
        return url == candidates[1]

    monkeypatch.setattr(publisher, "head_ok", first_live)
    assert publisher.resolve_public_url("daily.jpg", settings, wait=0) == candidates[1]
    assert calls == candidates[:2]

    now = [0.0]
    monkeypatch.setattr(publisher, "head_ok", lambda url: False)
    monkeypatch.setattr(publisher.time, "time", lambda: now[0])
    monkeypatch.setattr(publisher.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    assert publisher.resolve_public_url("missing.jpg", settings, wait=6, quiet=False) == ""
    assert "esperando" in capsys.readouterr().out
    assert now[0] >= 6


@pytest.mark.trace("META-RECENT-001")
@pytest.mark.red_expected
def test_graph_error_classification_distinguishes_retry_auth_permanent_and_uncertain() -> None:
    classifier = getattr(publisher, "classify_publish_error", None)
    assert callable(classifier), "[META-RECENT-001] missing classify_publish_error"
    rate = json.loads((META_FIXTURES / "graph_error_rate_limit.json").read_text(encoding="utf-8"))

    assert classifier(rate, http_status=429)["category"] == "retryable"
    assert classifier({"error": {"code": 190, "message": "expired"}}, http_status=400)[
        "category"
    ] == "authentication"
    assert classifier({"error": {"code": 100, "message": "invalid field"}}, http_status=400)[
        "category"
    ] == "permanent"
    assert classifier(TimeoutError("after send"), request_sent=True)["category"] == "uncertain"


@pytest.mark.trace("META-RECENT-002")
@pytest.mark.red_expected
def test_meta_recent_publications_returns_normalized_redacted_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meta = Meta(configured_settings(access_token="sentinel-secret"))
    recent = json.loads((META_FIXTURES / "recent_publications.json").read_text(encoding="utf-8"))
    responses = iter(({"data": recent["facebook"]}, {"data": recent["instagram"]}))
    monkeypatch.setattr(meta, "_get", lambda path, params=None: next(responses))

    facebook = meta.recent_publications("facebook", since="2026-08-26T15:50:00Z", limit=25)
    instagram = meta.recent_publications("instagram", since="2026-08-26T15:50:00Z", limit=25)

    for records in (facebook, instagram):
        assert len(records) == 1
        assert set(records[0]) >= {"platform", "remote_id", "created_at", "permalink"}
        assert "sentinel-secret" not in repr(records)


@pytest.mark.trace("META-RECENT-003")
@pytest.mark.red_expected
def test_meta_recent_publications_validates_platform_limit_and_time_window() -> None:
    meta = Meta(configured_settings())

    for platform, since, limit in (
        ("tiktok", "2026-08-26T15:50:00Z", 25),
        ("facebook", "not-a-date", 25),
        ("instagram", "2026-08-26T15:50:00Z", 0),
        ("instagram", "2026-08-26T15:50:00Z", 101),
    ):
        with pytest.raises(ValueError, match="platform|fecha|since|limit"):
            meta.recent_publications(platform, since=since, limit=limit)


@pytest.mark.trace("META-RECENT-004")
@pytest.mark.red_expected
def test_meta_recent_publications_hashes_real_copy_without_returning_raw_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meta = Meta(configured_settings(access_token="sentinel-secret"))
    responses = iter(
        (
            {
                "data": [
                    {
                        "id": "fb-1",
                        "created_time": "2026-08-26T16:02:10+00:00",
                        "message": "Copy real de Facebook",
                        "permalink_url": "https://facebook.example/posts/fb-1",
                    }
                ]
            },
            {
                "data": [
                    {
                        "id": "ig-1",
                        "timestamp": "2026-08-26T16:03:20+00:00",
                        "caption": "Copy real de Instagram",
                        "permalink": "https://instagram.example/p/ig-1",
                    }
                ]
            },
        )
    )
    requested: list[str] = []

    def fake_get(path, params=None):
        requested.append(params["fields"])
        return next(responses)

    monkeypatch.setattr(meta, "_get", fake_get)
    facebook = meta.recent_publications("facebook", since="2026-08-26T15:50:00Z")
    instagram = meta.recent_publications("instagram", since="2026-08-26T15:50:00Z")

    expected_fb = "sha256:" + hashlib.sha256("Copy real de Facebook".encode()).hexdigest()
    expected_ig = "sha256:" + hashlib.sha256("Copy real de Instagram".encode()).hexdigest()
    assert facebook[0]["caption_hash"] == expected_fb
    assert instagram[0]["caption_hash"] == expected_ig
    assert "message" in requested[0] and "caption" in requested[1]
    serialized = json.dumps([facebook, instagram])
    assert "Copy real" not in serialized and "sentinel-secret" not in serialized
