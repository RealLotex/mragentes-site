from __future__ import annotations

import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError

import pytest

from scripts.notifications import notify_deployed_note as notify_module
from scripts.notifications.notify_deployed_note import (
    NotificationConflict,
    build_note_notification,
    build_idempotency_key,
    changed_note_slugs,
    changed_social_drafts,
    request_notification,
)
from scripts.social.notas import Nota


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(
        repo,
        "-c",
        "user.name=Fixture User",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-m",
        message,
    )
    return _git(repo, "rev-parse", "HEAD")


def _note(title: str, slug: str, date: str = "2026-08-27") -> str:
    return f'---\ntitle: "{title}"\ndate: {date}\nslug: "{slug}"\n---\n\nTexto.\n'


@pytest.mark.trace("DEPLOY-DETECT-001")
@pytest.mark.red_expected
def test_changed_note_slugs_reports_only_added_notes_and_uses_frontmatter_slug(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    notes = repo / "content" / "notas"
    notes.mkdir(parents=True)
    existing = notes / "2026-08-26-existente.md"
    existing.write_text(_note("Existente", "existente", "2026-08-26"), encoding="utf-8")
    renamed = notes / "2026-08-25-renombrable.md"
    renamed.write_text(_note("Renombrable", "renombrable", "2026-08-25"), encoding="utf-8")
    _git(repo, "add", "content")
    before = _commit(repo, "base")

    existing.write_text(_note("Existente editada", "existente", "2026-08-26"), encoding="utf-8")
    renamed.rename(notes / "2026-08-25-renombrada.md")
    added = notes / "2026-08-27-portable-a1b2c3.md"
    added.write_text(_note("Título Unicode", "automatización-segura"), encoding="utf-8")
    _git(repo, "add", "-A")
    after = _commit(repo, "add note")

    assert changed_note_slugs(repo, before, after) == ["automatización-segura"]


@pytest.mark.trace("DEPLOY-DETECT-002")
@pytest.mark.red_expected
def test_changed_note_slugs_handles_zero_sha_and_rejects_duplicates(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    notes = repo / "content" / "notas"
    notes.mkdir(parents=True)
    (notes / "a.md").write_text(_note("A", "repetida"), encoding="utf-8")
    (notes / "b.md").write_text(_note("B", "repetida"), encoding="utf-8")
    _git(repo, "add", "content")
    after = _commit(repo, "initial")

    with pytest.raises(ValueError, match="duplicate"):
        changed_note_slugs(repo, "0" * 40, after)


@pytest.mark.trace("DEPLOY-DETECT-002B")
@pytest.mark.red_expected
def test_changed_note_slugs_accepts_only_a_closed_recovery_manifest_for_an_existing_note(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    note = repo / "content" / "notas" / "nota-segura.md"
    note.parent.mkdir(parents=True)
    note.write_text(_note("Nota segura", "nota-segura"), encoding="utf-8")
    _git(repo, "add", "content")
    before = _commit(repo, "base")

    retry = repo / ".automation" / "publication" / "retries" / "nota-segura.json"
    retry.parent.mkdir(parents=True)
    retry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "note_slug": "nota-segura",
                "reason": "post_deploy_gate_recovered",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".automation")
    after = _commit(repo, "recover note")

    assert changed_note_slugs(repo, before, after) == ["nota-segura"]

    retry.write_text(
        '{"schema_version":1,"note_slug":"other-note","reason":"post_deploy_gate_recovered"}\n',
        encoding="utf-8",
    )
    _git(repo, "add", ".automation")
    invalid = _commit(repo, "invalid retry")
    with pytest.raises(ValueError, match="invalid publication recovery target"):
        changed_note_slugs(repo, before, invalid)


@pytest.mark.trace("DEPLOY-DETECT-002C")
@pytest.mark.red_expected
def test_changed_note_slugs_accepts_distinct_versioned_recovery_attempts(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    note = repo / "content" / "notas" / "nota-versionada.md"
    note.parent.mkdir(parents=True)
    note.write_text(_note("Nota versionada", "nota-versionada"), encoding="utf-8")
    _git(repo, "add", "content")
    before = _commit(repo, "base")

    retry = repo / ".automation" / "publication" / "retries" / "nota-versionada" / "reintento01.json"
    retry.parent.mkdir(parents=True)
    retry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "note_slug": "nota-versionada",
                "retry_id": "reintento01",
                "reason": "post_deploy_gate_recovered",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".automation")
    after = _commit(repo, "versioned recovery")

    assert changed_note_slugs(repo, before, after) == ["nota-versionada"]


@pytest.mark.trace("DEPLOY-DETECT-003")
@pytest.mark.red_expected
def test_changed_social_drafts_reports_only_new_canonical_daily_contracts(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    drafts = repo / ".automation" / "social" / "drafts"
    drafts.mkdir(parents=True)
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    before = _commit(repo, "base")
    (drafts / "2026-08-27-daily-owned.json").write_text(
        '{"kind":"daily_owned"}\n', encoding="utf-8"
    )
    (drafts / "manual.json").write_text('{"kind":"daily_owned"}\n', encoding="utf-8")
    _git(repo, "add", ".automation")
    after = _commit(repo, "daily")

    assert changed_social_drafts(repo, before, after) == [
        ".automation/social/drafts/2026-08-27-daily-owned.json"
    ]


@pytest.mark.trace("PUSH-REQUEST-001")
@pytest.mark.red_expected
def test_idempotency_key_is_stable_bounded_and_rejects_invalid_parts() -> None:
    first = build_idempotency_key(
        "RealLotex/mragentes-site",
        "a" * 40,
        "automatización-segura",
        publication_date="2026-08-27",
    )
    second = build_idempotency_key(
        "RealLotex/mragentes-site",
        "a" * 40,
        "automatización-segura",
        publication_date="2026-08-27",
    )
    assert first == second == "blog-note:2026-08-27:automatización-segura"
    assert len(first.encode("utf-8")) <= 160
    for slug in ("", "../x", "a/b", "x?y"):
        with pytest.raises(ValueError):
            build_idempotency_key(
                "RealLotex/mragentes-site",
                "a" * 40,
                slug,
                publication_date="2026-08-27",
            )


class FakeResponse:
    def __init__(self, status: int, value: dict[str, object]) -> None:
        self.status = status
        self._body = json.dumps(value).encode()
        self.headers = {"content-type": "application/json"}

    def read(self, limit: int = -1) -> bytes:
        return self._body if limit < 0 else self._body[:limit]

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


@pytest.mark.trace("PUSH-REQUEST-002")
@pytest.mark.red_expected
def test_request_notification_sends_auth_hash_and_same_idempotency_key() -> None:
    seen = []

    def opener(request, timeout):
        seen.append((request, timeout))
        return FakeResponse(200, {"complete": True, "delivered": 3})

    event_id = "blog-note:2026-08-27:nota-segura"
    result = request_notification(
        "https://mragentes-push.example.workers.dev/api/send/",
        token="secret-not-logged",
        event_id=event_id,
        payload={
            "title": "Nota segura",
            "body": "Nueva nota",
            "url": "https://mragentes.com.ar/notas/nota-segura/",
        },
        opener=opener,
        attempts=1,
    )
    assert result == {"complete": True, "delivered": 3}
    request, timeout = seen[0]
    assert timeout > 0
    assert request.headers["Authorization"] == "Bearer secret-not-logged"
    assert request.headers["Idempotency-key"] == event_id
    sent = json.loads(request.data)
    assert sent["eventId"] == event_id
    assert sent["payloadHash"].startswith("sha256:")
    assert sent["payload"]["url"].endswith("/notas/nota-segura/")


@pytest.mark.trace("PUSH-REQUEST-003")
@pytest.mark.red_expected
def test_request_notification_treats_duplicate_as_success_and_conflict_as_failure() -> None:
    event_id = "blog-note:2026-08-27:nota-segura"

    def duplicate(request, timeout):
        del request, timeout
        raise HTTPError(
            "https://worker.example/api/send/",
            409,
            "Conflict",
            {"content-type": "application/json"},
            None,
        )

    # An empty 409 cannot prove idempotent equality and therefore fails closed.
    with pytest.raises(NotificationConflict):
        request_notification(
            "https://worker.example/api/send/",
            token="token",
            event_id=event_id,
            payload={
                "title": "T",
                "body": "B",
                "url": "https://mragentes.com.ar/notas/nota-segura/",
            },
            opener=duplicate,
            attempts=1,
        )


@pytest.mark.trace("PUSH-REQUEST-004")
@pytest.mark.red_expected
def test_request_notification_retries_429_once_with_same_body_and_key() -> None:
    calls = []

    def opener(request, timeout):
        del timeout
        calls.append((request.data, dict(request.headers)))
        if len(calls) == 1:
            raise HTTPError(request.full_url, 429, "rate", {}, None)
        return FakeResponse(200, {"complete": True})

    sleeps: list[float] = []
    request_notification(
        "https://worker.example/api/send/",
        token="token",
        event_id="blog-note:2026-08-27:nota-segura",
        payload={
            "title": "T",
            "body": "B",
            "url": "https://mragentes.com.ar/notas/nota-segura/",
        },
        opener=opener,
        attempts=2,
        sleep=sleeps.append,
    )
    assert len(calls) == 2
    assert calls[0] == calls[1]
    assert sleeps == [1]


@pytest.mark.trace("PUSH-REQUEST-005")
@pytest.mark.red_expected
def test_note_notification_uses_editorial_identity_and_same_site_cover(tmp_path: Path) -> None:
    import datetime as dt

    note = Nota(
        path=tmp_path / "note.md",
        title="Automatización segura",
        date=dt.date(2026, 8, 27),
        description="Una guía concreta para automatizar con control humano.",
        image="/images/stock/cover.webp",
        canonical_slug="automatización-segura",
    )
    event_id, payload = build_note_notification(
        note,
        repository="RealLotex/mragentes-site",
        deploy_sha="c" * 40,
    )
    assert event_id == "blog-note:2026-08-27:automatización-segura"
    assert payload == {
        "title": "Automatización segura",
        "body": "Una guía concreta para automatizar con control humano.",
        "url": "https://mragentes.com.ar/notas/automatizaci%C3%B3n-segura/",
        "image": "https://mragentes.com.ar/images/stock/cover.webp",
    }

    production_slug = (
        "openai-pausa-su-entrenamiento-por-cibercapacidad-crítica-claude-diseña-"
        "proteínas-que-funcionan-y-qwen-corona-a-china-la-semana-en-que-la-ia-se-"
        "puso-frenos-a-sí-misma"
    )
    production_note = Nota(
        path=tmp_path / "production-note.md",
        title="La semana en que la IA se puso frenos a sí misma",
        date=dt.date(2026, 8, 23),
        description="Resumen semanal.",
        canonical_slug=production_slug,
    )
    production_event, _ = build_note_notification(
        production_note,
        repository="RealLotex/mragentes-site",
        deploy_sha="c" * 40,
    )
    assert len(production_event.encode("utf-8")) > 160
    assert production_event.endswith(production_slug)


@pytest.mark.trace("PUSH-REQUEST-006")
@pytest.mark.red_expected
def test_send_note_cli_resolves_note_and_reads_token_only_from_named_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    import datetime as dt

    note = Nota(
        path=tmp_path / "note.md",
        title="Nota",
        date=dt.date(2026, 8, 27),
        description="Descripción",
        canonical_slug="nota",
    )
    monkeypatch.setenv("PUSH_API_TOKEN", "secret-from-environment")
    monkeypatch.setattr(notify_module.notas_mod, "find", lambda slug: note if slug == "nota" else None)
    seen = {}

    def fake_request(worker_url, **kwargs):
        seen.update({"worker_url": worker_url, **kwargs})
        return {"complete": True}

    monkeypatch.setattr(notify_module, "request_notification", fake_request)
    assert notify_module.main(
        [
            "send-note",
            "--worker-url",
            "https://worker.example/api/send/",
            "--note-slug",
            "nota",
            "--deploy-sha",
            "d" * 40,
            "--repository",
            "RealLotex/mragentes-site",
        ]
    ) == 0
    assert seen["token"] == "secret-from-environment"
    assert seen["event_id"] == "blog-note:2026-08-27:nota"
    assert "secret-from-environment" not in capsys.readouterr().out
