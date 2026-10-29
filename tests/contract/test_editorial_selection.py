import json

import pytest

from tests.support.contracts import ROOT

pytestmark = [pytest.mark.trace("EDITORIAL-SELECTION-001"), pytest.mark.red_expected]


@pytest.mark.parametrize("path", [
    ".agents/skills/mragentes-editorial-publisher/SKILL.md",
    ".agents/skills/mragentes-editorial-publisher/references/editorial-contract.md",
    ".automation/schedules/editorial.json", "OPERATIONS.md",
])
def test_selection_compares_impact_and_searches_beyond_institutional_agendas(path):
    text = (ROOT / path).read_text()
    if path.endswith(".json"):
        text = json.loads(text)["prompt"]
    text = " ".join(text.casefold().split())
    for term in ("cinco candidatos", "impacto", "mcp", "iol", "el cronista", "iproup",
                 "infotechnology", "fuentes originales", "jornadas", "fecha del hecho"):
        assert term in text, f"{path}: falta {term}"


def test_extra_edition_is_explicit_and_never_scheduled():
    for path in ("OPERATIONS.md", ".agents/skills/mragentes-editorial-publisher/SKILL.md"):
        text = (ROOT / path).read_text()
        assert "--edition" in text
        assert "pedido explícito" in text
    prompt = json.loads((ROOT / ".automation/schedules/editorial.json").read_text())["prompt"]
    assert "No uses --edition en la corrida diaria" in prompt
