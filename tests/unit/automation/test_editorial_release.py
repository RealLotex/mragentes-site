from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

from scripts.automation.editorial_release import build_note, validate_submission


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
