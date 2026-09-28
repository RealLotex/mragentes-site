from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml

from scripts.automation.editorial_release import build_note, validate_submission, wait_for_release


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
def test_submission_rejects_stale_or_uncited_story() -> None:
    stale = _submission() | {"source_date": "2026-09-20"}
    with pytest.raises(ValueError, match="recent"):
        validate_submission(stale, date(2026, 9, 26))
    uncited = _submission() | {"body": "OpenAI informó un caso sin enlace."}
    with pytest.raises(ValueError, match="source"):
        validate_submission(uncited, date(2026, 9, 26))


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
                "deploy", "wait_for_publication", "publish_meta", "notify_push"
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
