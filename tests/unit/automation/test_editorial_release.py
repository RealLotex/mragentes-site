from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml
from PIL import Image

from scripts.automation import editorial_release
from scripts.automation.editorial_release import build_note, validate_submission, wait_for_release
from scripts.automation.news_queue import load_queue, stable_news_id


def _submission() -> dict:
    return {
        "title": "Un agente de OpenAI usó DNS para salir de su entorno aislado",
        "summary": (
            "OpenAI detectó el acceso en 15 minutos y detuvo la ejecución "
            "dos horas y media después."
        ),
        "body": (
            "OpenAI informó el 25 de septiembre que un agente de investigación usó DNS "
            "para consultar un chatbot externo. [Informe original]"
            "(https://alignment.openai.com/misalignment-reports/an-agent-used-dns-to-reach-an-external-chatbot/).\n\n"
            "## Qué pasó\n\nEl agente hizo una consulta concreta.\n"
        ),
        "image_alt": "Servidor y conexiones de red en una sala técnica",
        "source_url": "https://alignment.openai.com/misalignment-reports/an-agent-used-dns-to-reach-an-external-chatbot/",
        "source_name": "OpenAI Alignment",
        "source_date": "2026-09-25",
    }


@pytest.mark.trace("EDITORIAL-RELEASE-001")
@pytest.mark.red_expected
def test_submission_is_one_fresh_sourced_story() -> None:
    item = validate_submission(_submission(), date(2026, 9, 26))
    assert item["source_date"] == "2026-09-25"
    assert item["source_url"] in item["body"]


@pytest.mark.trace("EDITORIAL-RELEASE-002")
@pytest.mark.red_expected
@pytest.mark.parametrize("changes", [
    {"source_date": "2026-09-20"},
    {"source_date": "2026-09-27"},
    {"body": "OpenAI informó un caso sin enlace."},
])
def test_editorial_age_and_inline_citation_do_not_block_publication(changes: dict) -> None:
    submission = _submission() | changes
    item = validate_submission(submission, date(2026, 9, 26))
    assert item["body"] == submission["body"].strip()
    assert item["source_date"] == submission["source_date"]


@pytest.mark.trace("EDITORIAL-AVAILABILITY-001")
@pytest.mark.red_expected
def test_long_prose_is_preserved_and_description_is_adapted_for_hugo() -> None:
    submission = _submission() | {
        "title": "Una noticia sobre inteligencia artificial " * 6,
        "summary": "Un resumen extenso. " * 30,
        "body": "Un párrafo breve con datos.\n\n" * 500,
        "image_alt": "Descripción de la ilustración. " * 10,
    }
    item = validate_submission(submission, date(2026, 9, 26))
    note = build_note(item, date(2026, 9, 26), "noticia", "noticia.png")
    front = yaml.safe_load(note.split("---", 2)[1])
    assert front["title"] == submission["title"].strip()
    assert front["description"] == submission["summary"].strip()[:160]
    assert submission["body"].strip() in note


@pytest.mark.trace("EDITORIAL-AVAILABILITY-002")
@pytest.mark.red_expected
def test_small_valid_cover_is_accepted(tmp_path: Path) -> None:
    image = tmp_path / "cover.png"
    Image.new("RGB", (320, 200)).save(image)
    assert editorial_release._check_image(image) == ".png"


@pytest.mark.trace("EDITORIAL-AVAILABILITY-003")
@pytest.mark.red_expected
def test_preparation_reuses_source_without_corrupting_queue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    submission = validate_submission(_submission(), date(2026, 9, 26))
    queue_path = tmp_path / ".automation/news/queue/news-queue.json"
    story = {
        "schema_version": 1, "title": submission["title"],
        "canonical_url": submission["source_url"], "source": submission["source_name"],
        "entity": submission["source_name"], "published_at": "2026-09-25T12:00:00Z",
        "discovered_at": "2026-09-25T12:00:00Z", "status": "consumed",
        "evidence": [{"url": submission["source_url"], "claim": submission["summary"]}],
        "tags": submission["tags"], "consumed_by": "previous-note",
        "consumed_at": "2026-09-25T12:00:00Z",
    }
    story["id"] = stable_news_id(story)
    queue_path.parent.mkdir(parents=True)
    queue_path.write_text(json.dumps({
        "schema_version": 1, "revision": 1, "updated_at": "2026-09-25T12:00:00Z",
        "items": [story],
    }), encoding="utf-8")
    image = tmp_path / "cover.png"
    Image.new("RGB", (800, 500)).save(image)

    def render(command: list[str], root: Path) -> str:
        assert command[1:4] == ["-m", "scripts.social", "render-note-announcement"]
        social = root / f"static/images/social/notes/{command[-1]}.jpg"
        social.parent.mkdir(parents=True)
        Image.new("RGB", (1080, 1350)).save(social)
        return ""

    monkeypatch.setattr(editorial_release, "_run", render)
    paths = editorial_release.prepare_release(tmp_path, submission, image, date(2026, 9, 26))
    assert len(paths) == 6
    assert all((tmp_path / path).is_file() for path in paths)
    queue = load_queue(queue_path)
    assert len(queue["items"]) == 1
    assert queue["items"][0]["consumed_by"] == "previous-note"
    report = json.loads((tmp_path / paths[-1]).read_text(encoding="utf-8"))
    assert report["selected_news_ids"] == [story["id"]]


@pytest.mark.trace("EDITORIAL-AVAILABILITY-004")
@pytest.mark.red_expected
@pytest.mark.parametrize("changes", [
    {"related_sources": [f"https://example.org/source/{i}" for i in range(4)]},
    {"related_sources": [_submission()["source_url"], _submission()["source_url"]]},
    {"tags": ["ia", "actualidad", "justicia", "agentes", "modelos", "robots"]},
    {"tags": []},
])
def test_optional_metadata_counts_do_not_block_a_note(changes: dict) -> None:
    item = validate_submission(_submission() | changes, date(2026, 9, 26))
    note = build_note(item, date(2026, 9, 26), "noticia", "noticia.png")
    front = yaml.safe_load(note.split("---", 2)[1])
    assert front["sources"]
    assert len(front["sources"]) == len(set(front["sources"]))
    assert front["tags"]


@pytest.mark.trace("EDITORIAL-RELEASE-003")
@pytest.mark.red_expected
def test_build_note_uses_closed_front_matter_and_one_story() -> None:
    note = build_note(
        _submission(), date(2026, 9, 26), "openai-agente-dns", "openai-agente-dns.jpg"
    )
    assert 'automation_id: "blog:2026-09-26:openai-agente-dns"' in note
    assert 'image: "/images/stock/openai-agente-dns.jpg"' in note
    assert 'slug: "openai-agente-dns"' in note
    assert "## Preguntas frecuentes" not in note
    front = yaml.safe_load(note.split("---", 2)[1])
    assert front["aliases"] == []


@pytest.mark.trace("EDITORIAL-RELEASE-004")
@pytest.mark.red_expected
def test_documented_script_invocation_loads_repo_modules() -> None:
    root = Path(__file__).resolve().parents[3]
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/automation/editorial_release.py", "--help"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.trace("EDITORIAL-RELEASE-005")
@pytest.mark.red_expected
def test_script_sets_its_own_commit_identity() -> None:
    root = Path(__file__).resolve().parents[3]
    script = (root / "scripts/automation/editorial_release.py").read_text(encoding="utf-8")
    assert "user.name=MR Agentes Editorial" in script
    assert "user.email=editorial@mragentes.com.ar" in script


@pytest.mark.trace("EDITORIAL-RELEASE-006")
@pytest.mark.red_expected
def test_daily_note_is_not_future_dated_at_five_in_cordoba() -> None:
    note = build_note(_submission(), date(2026, 9, 28), "agente-dns", "agente-dns.jpg")
    front = yaml.safe_load(note.split("---", 2)[1])
    assert datetime.fromisoformat(front["date"]) <= datetime.fromisoformat(
        "2026-09-28T05:00:00-03:00"
    )


@pytest.mark.trace("EDITORIAL-RELEASE-007")
@pytest.mark.red_expected
def test_release_waits_for_merge_and_successful_deploy() -> None:
    responses = iter(
        [
            {"state": "OPEN", "mergeCommit": None},
            {"state": "MERGED", "mergeCommit": {"oid": "a" * 40}},
            [],
            {"state": "MERGED", "mergeCommit": {"oid": "a" * 40}},
            [{"databaseId": 42, "status": "completed", "conclusion": "success"}],
            {"jobs": [{"name": name, "conclusion": "success"} for name in (
                "deploy", "wait_for_publication", "publish_meta (agente-dns)",
                "notify_push (agente-dns)",
            )]},
        ]
    )
    calls: list[list[str]] = []

    def run(command: list[str], _: Path) -> str:
        calls.append(command)
        return json.dumps(next(responses))

    result = wait_for_release(
        "https://github.com/RealLotex/mragentes-site/pull/86",
        "https://mragentes.com.ar/notas/agente-dns/",
        attempts=4,
        interval=0,
        run=run,
        sleep=lambda _: None,
    )
    assert "published:" in result
    assert "https://mragentes.com.ar/notas/agente-dns/" in result
    assert any("--commit" in command for command in calls)


@pytest.mark.trace("EDITORIAL-RELEASE-008")
@pytest.mark.red_expected
def test_failed_deploy_is_not_reported_as_published() -> None:
    responses = iter(
        [
            {"state": "MERGED", "mergeCommit": {"oid": "a" * 40}},
            [{"databaseId": 42, "status": "completed", "conclusion": "failure"}],
        ]
    )

    def run(_: list[str], __: Path) -> str:
        return json.dumps(next(responses))

    with pytest.raises(RuntimeError, match="deploy failed"):
        wait_for_release(
            "https://github.com/RealLotex/mragentes-site/pull/86",
            "https://mragentes.com.ar/notas/agente-dns/",
            attempts=1,
            interval=0,
            run=run,
            sleep=lambda _: None,
        )


@pytest.mark.trace("EDITORIAL-RELEASE-009")
@pytest.mark.red_expected
def test_september_28_note_is_visible_before_noon() -> None:
    root = Path(__file__).resolve().parents[3]
    note = root / (
        "content/notas/openai-pausa-tareas-con-herramientas-tras-un-fallo-de-aislamiento.md"
    )
    front = yaml.safe_load(note.read_text(encoding="utf-8").split("---", 2)[1])
    assert datetime.fromisoformat(front["date"]) <= datetime.fromisoformat(
        "2026-09-28T05:00:00-03:00"
    )
