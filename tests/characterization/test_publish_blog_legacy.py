from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.support.contracts import load_python_target, trace_message


TARGET = "scripts/publish_blog.py"


class FixedDate:
    @classmethod
    def today(cls):
        return cls()

    def isoformat(self) -> str:
        return "2026-08-26"

    def strftime(self, value: str) -> str:
        assert value == "%Y%m%d"
        return "20260826"


@pytest.mark.trace("LEGACY-EDITORIAL-001")
@pytest.mark.baseline_green
def test_publish_blog_slugify_characterizes_accents_symbols_and_legacy_limit() -> None:
    module = load_python_target(TARGET, "LEGACY-EDITORIAL-001")
    assert module.slugify("  ¡IA, Ñandú y corazón!  ") == "ia-ñandú-y-corazón", trace_message(
        "LEGACY-EDITORIAL-001", "legacy accent behavior changed before refactor"
    )
    assert len(module.slugify("palabra " * 100)) == 80, trace_message(
        "LEGACY-EDITORIAL-001", "legacy character limit changed"
    )
    assert module.slugify("🤖") == "", trace_message(
        "LEGACY-EDITORIAL-001", "legacy symbol-only behavior changed"
    )


@pytest.mark.trace("LEGACY-EDITORIAL-002")
@pytest.mark.baseline_green
def test_publish_blog_load_state_defaults_for_absent_and_corrupt_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_python_target(TARGET, "LEGACY-EDITORIAL-002")
    state = tmp_path / "state.json"
    monkeypatch.setattr(module, "STATE_FILE", str(state))
    expected = {"used_images": [], "published": []}
    assert module.load_state() == expected, trace_message(
        "LEGACY-EDITORIAL-002", "absent state default changed"
    )
    state.write_text("{broken", encoding="utf-8")
    assert module.load_state() == expected, trace_message(
        "LEGACY-EDITORIAL-002", "corrupt state default changed"
    )


@pytest.mark.trace("LEGACY-EDITORIAL-003")
@pytest.mark.baseline_green
def test_publish_blog_save_state_writes_readable_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_python_target(TARGET, "LEGACY-EDITORIAL-003")
    state_path = tmp_path / "nested" / "state.json"
    monkeypatch.setattr(module, "STATE_FILE", str(state_path))
    value = {"used_images": ["a.webp"], "published": [{"title": "Ñandú"}]}
    module.save_state(value)
    assert json.loads(state_path.read_text(encoding="utf-8")) == value, trace_message(
        "LEGACY-EDITORIAL-003", "saved state cannot round-trip"
    )


@pytest.mark.trace("LEGACY-EDITORIAL-004")
@pytest.mark.baseline_green
def test_publish_blog_generic_image_alt_is_nonempty_brand_copy() -> None:
    module = load_python_target(TARGET, "LEGACY-EDITORIAL-004")
    observed = module._generate_image_alt("unknown.webp")
    assert "automatización" in observed and "MR Agentes" in observed, trace_message(
        "LEGACY-EDITORIAL-004", f"unexpected legacy fallback alt: {observed}"
    )


@pytest.mark.trace("LEGACY-EDITORIAL-005")
@pytest.mark.baseline_green
def test_publish_blog_create_nota_characterizes_simple_hugo_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_python_target(TARGET, "LEGACY-EDITORIAL-005")
    content_dir = tmp_path / "content" / "notas"
    monkeypatch.setattr(module, "CONTENT_DIR", str(content_dir))
    monkeypatch.setattr(module, "datetime", SimpleNamespace(date=FixedDate))
    output = Path(
        module.create_nota(
            "Modelo verificable",
            "## Evidencia\n\nContenido comprobado.",
            ["ia", "modelos"],
            "modelo.webp",
            "Descripción breve",
            "Diagrama del modelo",
        )
    )
    text = output.read_text(encoding="utf-8")
    assert output.name == "2026-08-26-modelo-verificable.md", trace_message(
        "LEGACY-EDITORIAL-005", f"unexpected legacy filename: {output.name}"
    )
    for expected in (
        'title: "Modelo verificable"',
        "date: 2026-08-26",
        'image: "/images/stock/modelo.webp"',
        "  - ia",
        "Contenido comprobado.",
    ):
        assert expected in text, trace_message(
            "LEGACY-EDITORIAL-005", f"legacy Hugo document lost {expected!r}"
        )


@pytest.mark.trace("LEGACY-EDITORIAL-006")
@pytest.mark.baseline_green
def test_publish_blog_copy_image_handles_missing_and_copies_with_date_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load_python_target(TARGET, "LEGACY-EDITORIAL-006")
    stock = tmp_path / "stock"
    monkeypatch.setattr(module, "STOCK_DIR", str(stock))
    monkeypatch.setattr(module, "datetime", SimpleNamespace(date=FixedDate))
    assert module.copy_image_to_stock("") is None, trace_message(
        "LEGACY-EDITORIAL-006", "missing image no longer returns None"
    )
    source = tmp_path / "source.webp"
    source.write_bytes(b"synthetic-image")
    name = module.copy_image_to_stock(str(source))
    assert name == "daily-20260826.webp", trace_message(
        "LEGACY-EDITORIAL-006", f"unexpected copied image name: {name}"
    )
    assert (stock / name).read_bytes() == b"synthetic-image", trace_message(
        "LEGACY-EDITORIAL-006", "image bytes changed during copy"
    )
    assert "Imagen no encontrada" in capsys.readouterr().out, trace_message(
        "LEGACY-EDITORIAL-006", "missing image feedback changed"
    )


@pytest.mark.trace("LEGACY-EDITORIAL-007")
@pytest.mark.baseline_green
def test_publish_blog_dotenv_delegates_to_social_config(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_python_target(TARGET, "LEGACY-EDITORIAL-007")
    from scripts.social import config

    calls: list[str] = []
    monkeypatch.setattr(config, "load_dotenv", lambda: calls.append("loaded"))
    module._load_dotenv()
    assert calls == ["loaded"], trace_message(
        "LEGACY-EDITORIAL-007", "legacy dotenv delegation changed"
    )


@pytest.mark.trace("LEGACY-EDITORIAL-008")
@pytest.mark.baseline_green
def test_publish_blog_embedded_push_transport_is_retired() -> None:
    module = load_python_target(TARGET, "LEGACY-EDITORIAL-008")
    assert not hasattr(module, "send_push_notification"), trace_message(
        "LEGACY-EDITORIAL-008", "embedded push transport was not retired"
    )


@pytest.mark.trace("LEGACY-EDITORIAL-009")
@pytest.mark.baseline_green
def test_publish_blog_dry_run_creates_note_without_git_or_external_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_python_target(TARGET, "LEGACY-EDITORIAL-009")
    content = tmp_path / "content" / "notas"
    stock = tmp_path / "stock"
    content.mkdir(parents=True)
    stock.mkdir()
    image = tmp_path / "input.webp"
    image.write_bytes(b"image")
    request = tmp_path / "post.json"
    request.write_text(
        json.dumps(
            {
                "title": "Modelo verificable",
                "description": "Descripción",
                "tags": ["ia"],
                "image": str(image),
                "image_alt": "Diagrama",
                "body": "## Evidencia\n\nContenido.",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "CONTENT_DIR", str(content))
    monkeypatch.setattr(module, "STOCK_DIR", str(stock))
    monkeypatch.setattr(module, "datetime", SimpleNamespace(date=FixedDate))
    assert module.publish_blog_post(str(request), dry_run=True) is True, trace_message(
        "LEGACY-EDITORIAL-009", "valid dry-run failed"
    )
    assert len(list(content.glob("*.md"))) == 1, trace_message(
        "LEGACY-EDITORIAL-009", "dry-run did not create exactly one note"
    )


@pytest.mark.trace("LEGACY-EDITORIAL-010")
@pytest.mark.baseline_green
def test_publish_blog_rejects_missing_title_body_and_duplicate_day(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_python_target(TARGET, "LEGACY-EDITORIAL-010")
    content = tmp_path / "content"
    content.mkdir()
    stock = tmp_path / "stock"
    stock.mkdir()
    monkeypatch.setattr(module, "CONTENT_DIR", str(content))
    monkeypatch.setattr(module, "STOCK_DIR", str(stock))
    monkeypatch.setattr(module, "datetime", SimpleNamespace(date=FixedDate))
    request = tmp_path / "post.json"
    request.write_text(json.dumps({"title": "", "body": "Texto"}), encoding="utf-8")
    assert module.publish_blog_post(str(request), dry_run=True) is False, trace_message(
        "LEGACY-EDITORIAL-010", "blank title was accepted"
    )
    request.write_text(json.dumps({"title": "Título", "body": ""}), encoding="utf-8")
    assert module.publish_blog_post(str(request), dry_run=True) is False, trace_message(
        "LEGACY-EDITORIAL-010", "blank body was accepted"
    )
    (content / "2026-08-26-existing.md").write_text("existing", encoding="utf-8")
    request.write_text(json.dumps({"title": "Título", "body": "Texto"}), encoding="utf-8")
    assert module.publish_blog_post(str(request), dry_run=True) is False, trace_message(
        "LEGACY-EDITORIAL-010", "duplicate day was accepted without force"
    )


@pytest.mark.trace("LEGACY-EDITORIAL-011")
@pytest.mark.baseline_green
def test_publish_blog_main_maps_publish_boolean_to_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_python_target(TARGET, "LEGACY-EDITORIAL-011")
    request = tmp_path / "post.json"
    request.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "publish_blog_post", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(sys, "argv", ["publish_blog.py", str(request), "--dry-run"])
    with pytest.raises(SystemExit) as success:
        module.main()
    assert success.value.code == 0, trace_message("LEGACY-EDITORIAL-011", "success exit is not 0")
    monkeypatch.setattr(module, "publish_blog_post", lambda *_args, **_kwargs: False)
    with pytest.raises(SystemExit) as failure:
        module.main()
    assert failure.value.code == 1, trace_message("LEGACY-EDITORIAL-011", "failure exit is not 1")


@pytest.mark.trace("EDITORIAL-SEPARATION-001")
@pytest.mark.red_expected
def test_publish_blog_success_path_does_not_call_local_push_or_social(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_python_target(TARGET, "EDITORIAL-SEPARATION-001")
    content = tmp_path / "content"
    stock = tmp_path / "stock"
    content.mkdir()
    stock.mkdir()
    (stock / "fallback.webp").write_bytes(b"image")
    request = tmp_path / "post.json"
    request.write_text(json.dumps({"title": "Título", "body": "Texto", "tags": []}), encoding="utf-8")
    monkeypatch.setattr(module, "CONTENT_DIR", str(content))
    monkeypatch.setattr(module, "STOCK_DIR", str(stock))
    monkeypatch.setattr(module, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(module, "datetime", SimpleNamespace(date=FixedDate))
    assert module.publish_blog_post(str(request)) is True, trace_message(
        "EDITORIAL-SEPARATION-001", "fixture publication did not reach success path"
    )
    for retired in ("git_commit_push", "send_push_notification", "announce_on_social"):
        assert not hasattr(module, retired), trace_message(
            "EDITORIAL-SEPARATION-001", f"legacy publisher retained external owner: {retired}"
        )


@pytest.mark.trace("EDITORIAL-SEPARATION-002")
@pytest.mark.red_expected
def test_publish_blog_no_longer_owns_direct_git_push_function() -> None:
    module = load_python_target(TARGET, "EDITORIAL-SEPARATION-002")
    assert not hasattr(module, "git_commit_push"), trace_message(
        "EDITORIAL-SEPARATION-002", "legacy direct git_commit_push still exists"
    )
