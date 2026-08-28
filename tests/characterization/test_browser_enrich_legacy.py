from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.support.contracts import load_python_target, require_target, trace_message


TARGET = "scripts/browser_enrich.py"


class FakeHTTPResponse:
    def __init__(self, body: bytes, content_type: str = "text/html; charset=utf-8") -> None:
        self.body = body
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


@pytest.mark.trace("LEGACY-EDITORIAL-012")
@pytest.mark.baseline_green
def test_connector_content_cleanup_characterizes_html_charset_and_max_chars() -> None:
    module = load_python_target(TARGET, "LEGACY-EDITORIAL-012")
    html = (
        "<html><header>Header</header><nav>Menu</nav><script>secret()</script>"
        "<style>.x{}</style><body>Investigación &amp; evidencia comprobable para empresas.</body>"
        "<footer>Footer</footer></html>"
    ).encode()
    observed = module.clean_extracted_html(html, charset="utf-8", max_chars=30)
    assert observed == "Investigación & evidencia comp", trace_message(
        "LEGACY-EDITORIAL-012", f"unexpected cleaned/truncated text: {observed!r}"
    )


@pytest.mark.trace("LEGACY-EDITORIAL-013")
@pytest.mark.baseline_green
def test_missing_connector_content_is_explicitly_unreachable_without_transport() -> None:
    module = load_python_target(TARGET, "LEGACY-EDITORIAL-013")
    url = "https://example.test/article"
    observed = module.enrich_trends_from_records(
        [{"title": "Nota", "source": "Example", "url": url}]
    )
    assert observed[0]["status"] == "unreachable" and observed[0]["content"] == "", trace_message(
        "LEGACY-EDITORIAL-013", "missing connector evidence was not classified"
    )


@pytest.mark.trace("LEGACY-EDITORIAL-014")
@pytest.mark.baseline_green
def test_meaningful_paragraph_extraction_filters_navigation_and_keeps_substantive_unicode() -> None:
    module = load_python_target(TARGET, "LEGACY-EDITORIAL-014")
    text = (
        "Suscribite al newsletter y compartir en Facebook. "
        "Según la investigación, la inteligencia artificial mejora procesos empresariales con datos verificables. "
        "La empresa está aplicando el sistema en Córdoba y tiene resultados concretos. "
        "Corto."
    )
    observed = module.extract_meaningful_paragraphs(text, min_len=20)
    assert len(observed) == 2, trace_message(
        "LEGACY-EDITORIAL-014", f"unexpected meaningful sentence count: {observed}"
    )
    assert all("Suscribite" not in item for item in observed), trace_message(
        "LEGACY-EDITORIAL-014", "navigation boilerplate was retained"
    )
    assert module.extract_meaningful_paragraphs(None) == [], trace_message(
        "LEGACY-EDITORIAL-014", "empty input behavior changed"
    )


@pytest.mark.trace("LEGACY-EDITORIAL-015")
@pytest.mark.baseline_green
def test_parse_enrich_file_handles_missing_valid_and_malformed_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load_python_target(TARGET, "LEGACY-EDITORIAL-015")
    missing = tmp_path / "missing.json"
    assert module.parse_enrich_file(str(missing)) is None, trace_message(
        "LEGACY-EDITORIAL-015", "missing enrichment file behavior changed"
    )
    payload = {"title": "Nota", "trends": []}
    valid = tmp_path / "valid.json"
    valid.write_text(json.dumps(payload), encoding="utf-8")
    assert module.parse_enrich_file(str(valid)) == payload, trace_message(
        "LEGACY-EDITORIAL-015", "valid enrichment JSON changed"
    )
    malformed = tmp_path / "bad.json"
    malformed.write_text("{bad", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        module.parse_enrich_file(str(malformed))
    assert "No se encuentra" in capsys.readouterr().out, trace_message(
        "LEGACY-EDITORIAL-015", "missing file feedback changed"
    )


@pytest.mark.trace("LEGACY-EDITORIAL-016")
@pytest.mark.baseline_green
def test_enrich_trends_marks_success_and_unreachable_from_connector_records() -> None:
    module = load_python_target(TARGET, "LEGACY-EDITORIAL-016")
    trends = [
        {
            "title": "Éxito",
            "source": "A",
            "url": "https://example.test/ok",
            "content": "La empresa tiene datos verificables y puede mejorar procesos de negocio.",
        },
        {"title": "Falla", "source": "B", "url": "https://example.test/fail"},
    ]
    observed = module.enrich_trends_from_records(trends)
    assert [item["status"] for item in observed] == ["ok", "unreachable"], trace_message(
        "LEGACY-EDITORIAL-016", f"unexpected enrichment statuses: {observed}"
    )
    assert observed[0]["paragraphs"] and observed[1]["paragraphs"] == [], trace_message(
        "LEGACY-EDITORIAL-016", "enrichment payload shape changed"
    )


@pytest.mark.trace("LEGACY-EDITORIAL-017")
@pytest.mark.baseline_green
def test_update_note_uses_enriched_paragraphs_and_missing_note_returns_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_python_target(TARGET, "LEGACY-EDITORIAL-017")
    monkeypatch.setattr("random.shuffle", lambda _items: None)
    assert module.update_nota_with_enriched({"trends": []}, str(tmp_path / "missing.md")) is False, trace_message(
        "LEGACY-EDITORIAL-017", "missing note behavior changed"
    )
    note = tmp_path / "note.md"
    title = "Modelo con evidencia verificable"
    note.write_text(
        f"### 1. {title}\n*Fuente: Example*\n> Cita vieja\n\nAnálisis viejo\n\n---\n",
        encoding="utf-8",
    )
    enriched = {
        "trends": [
            {
                "title": title,
                "source": "Example",
                "url": "https://example.test/a",
                "paragraphs": ["La Empresa tiene evidencia verificable suficiente para este análisis."],
                "content": "contenido",
            }
        ]
    }
    assert module.update_nota_with_enriched(enriched, str(note)) is True, trace_message(
        "LEGACY-EDITORIAL-017", "valid note enrichment failed"
    )
    text = note.read_text(encoding="utf-8")
    assert "Contenido extraído directamente" in text, trace_message(
        "LEGACY-EDITORIAL-017", "enriched attribution was not written"
    )


@pytest.mark.trace("LEGACY-EDITORIAL-018")
@pytest.mark.baseline_green
def test_browser_enrich_main_dry_run_has_exit_zero_and_does_not_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_python_target(TARGET, "LEGACY-EDITORIAL-018")
    input_path = tmp_path / "input.json"
    input_path.write_text("{}", encoding="utf-8")
    payload = {
        "title": "Nota",
        "nota_file": "note.md",
        "trends": [{"title": "T", "source": "S", "url": "https://example.test"}],
    }
    monkeypatch.setattr(module, "parse_enrich_file", lambda _: payload)
    monkeypatch.setattr(
        module,
        "enrich_trends_from_records",
        lambda trends: [{**trends[0], "status": "ok", "paragraphs": ["Dato"], "content": "Dato"}],
    )
    monkeypatch.setattr(sys, "argv", ["browser_enrich.py", "--enrich-file", str(input_path), "--dry-run"])
    before = set(tmp_path.iterdir())
    assert module.main() == 0, trace_message("LEGACY-EDITORIAL-018", "dry-run exit is not zero")
    assert set(tmp_path.iterdir()) == before, trace_message(
        "LEGACY-EDITORIAL-018", "browser dry-run wrote output"
    )


@pytest.mark.trace("EDITORIAL-SEPARATION-003")
@pytest.mark.red_expected
def test_browser_enrich_runtime_no_longer_implements_direct_http_fetch() -> None:
    source = require_target(TARGET, "EDITORIAL-SEPARATION-003").read_text(encoding="utf-8")
    forbidden = ("urllib.request.urlopen", "urllib.request.build_opener", "fetch_with_browser_headers")
    found = [item for item in forbidden if item in source]
    assert not found, trace_message(
        "EDITORIAL-SEPARATION-003", f"legacy direct HTTP enrichment remains: {found}"
    )
