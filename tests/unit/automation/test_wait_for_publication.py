from __future__ import annotations

from collections import defaultdict

import pytest

from scripts.automation.wait_for_publication import (
    FetchResult,
    PublicationNotReady,
    verify_deployed_url,
)


class FakeFetch:
    def __init__(self, responses: dict[str, list[FetchResult]]) -> None:
        self.responses = {key: list(values) for key, values in responses.items()}
        self.calls: defaultdict[str, int] = defaultdict(int)

    def __call__(self, url: str, timeout: float) -> FetchResult:
        del timeout
        self.calls[url] += 1
        queue = self.responses[url]
        return queue.pop(0) if len(queue) > 1 else queue[0]


NOTE = "https://mragentes.com.ar/notas/nota-segura/"
IMAGE = "https://mragentes.com.ar/images/stock/nota.webp"
HTML = (
    '<html><head><link rel="canonical" '
    'href="https://mragentes.com.ar/notas/nota-segura/"></head>'
    '<body data-deploy-sha="abc123">Nota segura</body></html>'
)


@pytest.mark.trace("DEPLOY-HEALTH-001")
@pytest.mark.red_expected
def test_publication_gate_accepts_note_marker_canonical_and_image_200() -> None:
    fetch = FakeFetch(
        {
            NOTE: [FetchResult(200, NOTE, HTML, {"content-type": "text/html"})],
            IMAGE: [FetchResult(200, IMAGE, "", {"content-type": "image/webp"})],
        }
    )
    report = verify_deployed_url(
        NOTE,
        image_url=IMAGE,
        marker="Nota segura",
        fetch=fetch,
        attempts=1,
    )
    assert report["ready"] is True
    assert report["attempts"] == 1
    assert fetch.calls == {NOTE: 1, IMAGE: 1}


@pytest.mark.trace("DEPLOY-HEALTH-002")
@pytest.mark.red_expected
def test_publication_gate_retries_404_with_bounded_backoff_then_succeeds() -> None:
    fetch = FakeFetch(
        {
            NOTE: [
                FetchResult(404, NOTE, "", {}),
                FetchResult(200, NOTE, HTML, {"content-type": "text/html"}),
            ],
            IMAGE: [FetchResult(200, IMAGE, "", {"content-type": "image/webp"})],
        }
    )
    sleeps: list[float] = []
    report = verify_deployed_url(
        NOTE,
        image_url=IMAGE,
        marker="Nota segura",
        fetch=fetch,
        attempts=3,
        initial_delay=2,
        max_delay=3,
        sleep=sleeps.append,
    )
    assert report["attempts"] == 2
    assert sleeps == [2]


@pytest.mark.trace("DEPLOY-HEALTH-003")
@pytest.mark.red_expected
def test_publication_gate_rejects_wrong_marker_and_missing_image() -> None:
    wrong = FakeFetch(
        {
            NOTE: [FetchResult(200, NOTE, HTML, {"content-type": "text/html"})],
            IMAGE: [FetchResult(404, IMAGE, "", {})],
        }
    )
    with pytest.raises(PublicationNotReady, match="marker"):
        verify_deployed_url(
            NOTE,
            image_url=IMAGE,
            marker="Otra nota",
            fetch=wrong,
            attempts=1,
        )

    with pytest.raises(PublicationNotReady, match="image"):
        verify_deployed_url(
            NOTE,
            image_url=IMAGE,
            marker="Nota segura",
            fetch=wrong,
            attempts=1,
        )


@pytest.mark.trace("DEPLOY-HEALTH-004")
@pytest.mark.red_expected
def test_publication_gate_fails_closed_on_external_redirect_or_origin() -> None:
    redirected = FakeFetch(
        {
            NOTE: [
                FetchResult(
                    200,
                    "https://evil.test/notas/nota-segura/",
                    HTML,
                    {"content-type": "text/html"},
                )
            ]
        }
    )
    with pytest.raises(ValueError, match="redirect|origin"):
        verify_deployed_url(
            NOTE,
            image_url=None,
            marker="Nota segura",
            fetch=redirected,
            attempts=4,
        )

    with pytest.raises(ValueError, match="origin"):
        verify_deployed_url(
            "https://evil.test/notas/x/",
            image_url=None,
            marker="x",
            fetch=redirected,
        )


@pytest.mark.trace("DEPLOY-HEALTH-005")
@pytest.mark.red_expected
def test_publication_gate_validates_retry_bounds_before_network() -> None:
    fetch = FakeFetch({})
    for kwargs in (
        {"attempts": 0},
        {"initial_delay": -1},
        {"max_delay": 0},
        {"timeout": 0},
    ):
        with pytest.raises(ValueError):
            verify_deployed_url(
                NOTE,
                image_url=None,
                marker="Nota segura",
                fetch=fetch,
                **kwargs,
            )
    assert not fetch.calls
