from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.social import cli, flow, hook
from scripts.social import config as config_module
from scripts.social import notas as notas_module
from scripts.social import templates as templates_module
from scripts.social.publisher import Result
from tests.unit.social._helpers import configured_settings, make_nota, rich_piece


class FakeRendered:
    def __init__(self, label: str) -> None:
        self.label = label

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.label.encode("utf-8"))
        return path


def _completed(args: tuple[str, ...], returncode: int = 0, stdout: str = ""):
    return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr="")


@pytest.mark.trace("SOCIAL-FLOW-001")
@pytest.mark.baseline_green
def test_ascii_slug_is_portable_deterministic_limited_and_never_empty() -> None:
    assert flow.ascii_slug("  La IA se volvió útil — edición 2  ") == "la-ia-se-volvio-util-edicion-2"
    assert flow.ascii_slug("../../Ruta peligrosa") == "ruta-peligrosa"
    assert flow.ascii_slug("á" * 100, limit=12) == "a" * 12
    assert flow.ascii_slug("🧠⚙️") == "nota"


@pytest.mark.trace("GIT-SOCIAL-001")
@pytest.mark.baseline_green
def test_commit_and_push_returns_false_when_no_path_is_inside_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"image")
    monkeypatch.setattr(flow, "BASE_DIR", repo)

    assert flow.commit_and_push([outside], "message") is False


@pytest.mark.trace("GIT-SOCIAL-002")
@pytest.mark.baseline_green
def test_commit_and_push_stages_allowlisted_paths_commits_and_pushes_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    asset = repo / "static" / "social" / "daily.jpg"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"image")
    calls: list[tuple[str, ...]] = []

    def fake_git(*args: str, check: bool = True):
        del check
        calls.append(args)
        if args[:3] == ("diff", "--cached", "--quiet"):
            return _completed(args, returncode=1)
        return _completed(args)

    monkeypatch.setattr(flow, "BASE_DIR", repo)
    monkeypatch.setattr(flow, "_git", fake_git)

    assert flow.commit_and_push([asset], "social: daily", branch="automation/social/run") is True
    assert calls[0] == ("add", "--", "static/social/daily.jpg")
    assert ("commit", "-m", "social: daily") in calls
    assert ("push", "-u", "origin", "HEAD:automation/social/run") in calls
    assert all("--force" not in call and "-f" not in call for call in calls)


@pytest.mark.trace("GIT-SOCIAL-003")
@pytest.mark.baseline_green
def test_commit_and_push_reports_commit_failure_and_exhausts_bounded_push_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    asset = repo / "static" / "social" / "daily.jpg"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"image")
    logs: list[str] = []
    calls: list[tuple[str, ...]] = []

    def fake_git(*args: str, check: bool = True):
        del check
        calls.append(args)
        if args[:3] == ("diff", "--cached", "--quiet"):
            return _completed(args, returncode=1)
        if args and args[0] == "push":
            raise subprocess.CalledProcessError(1, args, stderr="remote unavailable")
        return _completed(args)

    monkeypatch.setattr(flow, "BASE_DIR", repo)
    monkeypatch.setattr(flow, "_git", fake_git)
    monkeypatch.setattr(flow.time, "sleep", lambda seconds: None)

    assert flow.commit_and_push(
        [asset], "social: daily", branch="automation/social/run", log=logs.append
    ) is False
    assert len([call for call in calls if call and call[0] == "push"]) == 4
    assert any("4/4" in line for line in logs)


@pytest.mark.trace("SOCIAL-FLOW-002")
@pytest.mark.baseline_green
def test_render_nota_pieces_writes_expected_feed_and_story_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nota = make_nota(tmp_path)
    settings = configured_settings()
    out = tmp_path / "social" / "nota"
    calls: list[tuple[str, str, int]] = []

    def fake_render(key, piece, surface_key="feed", seed=0, ground=None):
        del piece, ground
        calls.append((key, surface_key, seed))
        return FakeRendered(f"{key}:{surface_key}:{seed}")

    monkeypatch.setattr(flow.tpl, "render", fake_render)

    rendered = flow.render_nota_pieces(nota, settings, out, carousel=True, story=True)

    assert [path.name for path in rendered["feed"]][0] == "01-nota.jpg"
    assert rendered["feed"][-1].name.endswith("anuncio.jpg")
    assert rendered["story"] == out / "historia.jpg"
    assert rendered["all"] == rendered["feed"] + [rendered["story"]]
    assert all(path.is_file() for path in rendered["all"])
    assert calls[-1][1] == "story"


@pytest.mark.trace("SOCIAL-FLOW-003")
@pytest.mark.baseline_green
def test_public_name_is_posix_relative_and_rejects_paths_outside_social_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "static" / "social"
    inside = root / "día" / "piece.jpg"
    outside = tmp_path / "other.jpg"
    monkeypatch.setattr(flow, "OUT_DIR", root)

    assert flow.public_name(inside) == "día/piece.jpg"
    with pytest.raises(ValueError):
        flow.public_name(outside)


@pytest.mark.trace("SOCIAL-FLOW-004")
@pytest.mark.baseline_green
def test_prune_old_pieces_keeps_newest_and_reserved_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "social"
    for name in ("2026-08-20", "2026-08-21", "2026-08-22", "muestrario", "preview"):
        (root / name).mkdir(parents=True)
        (root / name / "asset.jpg").write_bytes(b"asset")
    logs: list[str] = []
    monkeypatch.setattr(flow, "OUT_DIR", root)

    removed = flow.prune_old_pieces(keep=2, log=logs.append)

    assert removed == ["2026-08-20"]
    assert not (root / "2026-08-20").exists()
    assert (root / "2026-08-21").exists() and (root / "2026-08-22").exists()
    assert (root / "muestrario").exists() and (root / "preview").exists()
    assert any("1" in line for line in logs)


@pytest.mark.trace("SOCIAL-FLOW-005")
@pytest.mark.red_expected
def test_prune_keep_zero_removes_all_generated_but_never_reserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "social"
    for name in ("one", "two", "biblioteca"):
        (root / name).mkdir(parents=True)
    monkeypatch.setattr(flow, "OUT_DIR", root)

    assert flow.prune_old_pieces(keep=0) == ["one", "two"]
    assert (root / "biblioteca").is_dir()


@pytest.mark.trace("SOCIAL-FLOW-006")
@pytest.mark.baseline_green
def test_publish_nota_dry_run_has_zero_git_meta_or_state_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nota = make_nota(tmp_path)
    settings = configured_settings(dry_run=True)
    social_root = tmp_path / "social"
    feed = social_root / "feed.jpg"
    pieces = {"feed": [feed], "story": None, "all": [feed]}
    monkeypatch.setattr(flow, "BASE_DIR", tmp_path)
    monkeypatch.setattr(flow, "OUT_DIR", social_root)
    monkeypatch.setattr(flow.state_mod, "load", lambda: {"version": 2, "published": {}})
    monkeypatch.setattr(flow.state_mod, "is_published", lambda slug, state: False)
    monkeypatch.setattr(flow, "render_nota_pieces", lambda *args, **kwargs: pieces)
    monkeypatch.setattr(
        flow,
        "commit_and_push",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("git must not run")),
    )
    monkeypatch.setattr(
        flow,
        "Meta",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Meta must not run")),
    )
    monkeypatch.setattr(
        flow.state_mod,
        "record",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("state must not change")),
    )

    outcome = flow.publish_nota(nota, settings)

    assert outcome["status"] == "ensayo"
    assert outcome["results"] == []
    assert outcome["pieces"] == pieces
    assert set(outcome["captions"]) == {"facebook", "instagram"}


@pytest.mark.trace("SOCIAL-HOOK-001")
@pytest.mark.baseline_green
def test_hook_disabled_returns_without_loading_note_or_rendering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = configured_settings(enabled=False)
    logs: list[str] = []
    monkeypatch.setattr(config_module, "load_settings", lambda: settings)
    monkeypatch.setattr(
        notas_module,
        "load",
        lambda path: (_ for _ in ()).throw(AssertionError("note must not load")),
    )
    monkeypatch.setattr(
        flow,
        "render_nota_pieces",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("render must not run")),
    )

    assert hook.announce("does-not-matter.md", log=logs.append) == {"status": "apagado"}
    assert any("SOCIAL_ENABLED=0" in line for line in logs)


@pytest.mark.trace("SOCIAL-HOOK-002")
@pytest.mark.red_expected
def test_legacy_local_hook_has_no_runtime_publisher_or_local_publish_switch() -> None:
    source = Path("scripts/social/hook.py").read_text(encoding="utf-8")

    assert "SOCIAL_LOCAL_PUBLISH" not in source
    assert "publish_nota" not in source
    assert "Meta" not in source


@pytest.mark.trace("CLI-SOCIAL-001")
@pytest.mark.baseline_green
def test_cli_surface_expansion_and_show_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(cli, "BASE_DIR", repo)

    assert cli._surfaces("all") == ["feed", "portrait", "story"]
    assert cli._surfaces("feed") == ["feed"]
    assert cli._show(repo / "static" / "piece.jpg") == "static/piece.jpg"
    assert cli._show(tmp_path / "outside.jpg") == str(tmp_path / "outside.jpg")


@pytest.mark.trace("CLI-SOCIAL-002")
@pytest.mark.baseline_green
def test_cli_result_block_uses_result_line_without_exposing_object_repr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli._print_result_block(
        "Resultado",
        [Result("facebook", "feed", True, id="fb-1"), Result("instagram", "feed", False, error="falló")],
    )

    output = capsys.readouterr().out
    assert "Resultado" in output
    assert "fb-1" in output and "falló" in output
    assert "Result(" not in output


@pytest.mark.trace("CLI-SOCIAL-003")
@pytest.mark.baseline_green
def test_cli_templates_and_library_are_read_only_inventory_commands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.cmd_templates(SimpleNamespace()) == 0
    templates_output = capsys.readouterr().out
    assert f"{len(templates_module.TEMPLATES)} plantillas" in templates_output

    assert cli.cmd_library(SimpleNamespace()) == 0
    library_output = capsys.readouterr().out
    assert "posteos listos" in library_output
    assert "publish" not in library_output.lower()


@pytest.mark.trace("CLI-SOCIAL-004")
@pytest.mark.baseline_green
def test_piece_from_args_supports_library_json_and_explicit_fields(tmp_path: Path) -> None:
    document = tmp_path / "piece.json"
    document.write_text(
        json.dumps({"template": "dato", "title": "Dato", "stat": "42%", "unknown": "ignored"}),
        encoding="utf-8",
    )
    json_args = SimpleNamespace(
        from_library=None,
        json=str(document),
        template=None,
        title=None,
        lead=None,
        kicker=None,
        stat=None,
        quote=None,
    )
    key, piece = cli._piece_from_args(json_args)
    assert key == "dato" and piece.stat == "42%" and not hasattr(piece, "unknown")

    explicit = SimpleNamespace(
        from_library=None,
        json=None,
        template="cita",
        title="Título",
        lead="Lead",
        kicker="Kicker",
        stat="",
        quote="Cita",
    )
    key, piece = cli._piece_from_args(explicit)
    assert key == "cita" and piece.quote == "Cita" and piece.title == "Título"


@pytest.mark.trace("CLI-SOCIAL-005")
@pytest.mark.baseline_green
def test_cmd_render_writes_only_requested_surfaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = SimpleNamespace(
        from_library=None,
        json=None,
        template="titular",
        title="Título",
        lead="Lead",
        kicker="Kicker",
        stat="",
        quote="",
        out=str(tmp_path / "out"),
        seed=7,
        surface="all",
        ground="paper",
    )
    calls: list[tuple[str, str, int, str]] = []

    def fake_render(key, piece, surface_key, seed, ground):
        del piece
        calls.append((key, surface_key, seed, ground))
        return FakeRendered(surface_key)

    monkeypatch.setattr(cli.tpl, "render", fake_render)
    assert cli.cmd_render(args) == 0
    assert [call[1] for call in calls] == ["feed", "portrait", "story"]
    assert all((tmp_path / "out" / f"titular-{surface}.jpg").exists() for surface in cli._surfaces("all"))
    assert capsys.readouterr().out.count("✔") == 3


@pytest.mark.trace("CLI-SOCIAL-006")
@pytest.mark.baseline_green
def test_publish_nota_cli_dry_run_never_constructs_meta_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    nota = make_nota(tmp_path)
    settings = configured_settings(dry_run=False)
    args = SimpleNamespace(
        dry_run=True,
        latest=True,
        slug=None,
        no_carousel=False,
        no_story=False,
        no_commit=False,
        branch="",
        wait=0,
        force=False,
    )
    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    monkeypatch.setattr(cli.notas_mod, "latest", lambda: nota)
    monkeypatch.setattr(
        cli,
        "publish_nota",
        lambda *args, **kwargs: {
            "status": "ensayo",
            "results": [],
            "pieces": {},
            "captions": {"facebook": "fb-copy", "instagram": "ig-copy"},
        },
    )
    monkeypatch.setattr(
        cli,
        "Meta",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Meta must not run")),
    )

    assert cli.cmd_publish_nota(args) == 0
    output = capsys.readouterr().out
    assert "fb-copy" in output and "ig-copy" in output


@pytest.mark.trace("CLI-SOCIAL-007")
@pytest.mark.baseline_green
def test_cli_main_maps_domain_input_error_and_keyboard_interrupt_to_exit_codes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class Parser:
        def __init__(self, func):
            self.func = func

        def parse_args(self, argv):
            del argv
            return SimpleNamespace(func=self.func)

    def bad_input(_args):
        raise ValueError("entrada inválida")

    monkeypatch.setattr(cli, "build_parser", lambda: Parser(bad_input))
    assert cli.main([]) == 1
    assert "entrada inválida" in capsys.readouterr().out

    def interrupted(_args):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "build_parser", lambda: Parser(interrupted))
    assert cli.main([]) == 130


@pytest.mark.trace("CLI-SOCIAL-008")
@pytest.mark.red_expected
def test_destination_cli_exposes_draft_daily_and_recover_commands() -> None:
    parser = cli.build_parser()
    subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))

    assert "draft-daily" in subparsers.choices
    assert "recover" in subparsers.choices


@pytest.mark.trace("CLI-SOCIAL-009")
@pytest.mark.red_expected
def test_recover_command_requires_kind_date_and_never_offers_force() -> None:
    parser = cli.build_parser()
    subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
    recover = subparsers.choices["recover"]
    destinations = {action.dest for action in recover._actions}

    assert {"kind", "date"} <= destinations
    assert "force" not in destinations
    args = parser.parse_args(["recover", "--kind", "daily_owned", "--date", "2026-08-26"])
    assert args.kind == "daily_owned" and args.date == "2026-08-26"


@pytest.mark.trace("CLI-SOCIAL-010")
@pytest.mark.red_expected
def test_draft_daily_command_is_local_only_and_has_no_publish_or_force_option() -> None:
    parser = cli.build_parser()
    subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
    draft = subparsers.choices["draft-daily"]
    destinations = {action.dest for action in draft._actions}

    assert "force" not in destinations
    assert "publish" not in destinations
    assert "execute" not in destinations


@pytest.mark.trace("CLI-SOCIAL-011")
@pytest.mark.red_expected
def test_delivery_commands_are_explicit_and_never_offer_force() -> None:
    parser = cli.build_parser()
    subparsers = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    assert {"deliver-draft", "deliver-note"} <= set(subparsers.choices)
    for name in ("deliver-draft", "deliver-note"):
        destinations = {action.dest for action in subparsers.choices[name]._actions}
        assert "force" not in destinations
        assert "branch" not in destinations
        assert "commit" not in destinations


@pytest.mark.trace("CLI-SOCIAL-012")
@pytest.mark.red_expected
def test_delivery_exit_code_distinguishes_complete_partial_and_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = tmp_path / "draft.json"
    document.write_text("{}", encoding="utf-8")
    args = SimpleNamespace(draft=str(document), ledger=str(tmp_path / "ledger.json"))
    monkeypatch.setattr(cli, "load_settings", lambda: configured_settings())
    monkeypatch.setattr(cli, "deliver_draft", lambda *a, **k: {"status": "complete"})
    assert cli.cmd_deliver_draft(args) == 0
    monkeypatch.setattr(cli, "deliver_draft", lambda *a, **k: {"status": "partial"})
    assert cli.cmd_deliver_draft(args) == 2
    monkeypatch.setattr(cli, "deliver_draft", lambda *a, **k: {"status": "needs_review"})
    assert cli.cmd_deliver_draft(args) == 3


@pytest.mark.trace("CLI-SOCIAL-013")
@pytest.mark.red_expected
def test_daily_draft_defaults_to_versioned_automation_contract_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asset = tmp_path / "static" / "images" / "social" / "daily.webp"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"daily-image")
    monkeypatch.setattr(cli, "BASE_DIR", tmp_path)
    args = SimpleNamespace(
        date="2026-08-27",
        topic="Automatización con control",
        asset="static/images/social/daily.webp",
        alt="Diagrama de un proceso controlado",
        facebook_caption="Una idea práctica para automatizar con control.",
        instagram_caption="Control antes de escalar. #automatización",
        out=None,
    )
    assert cli.cmd_draft_daily(args) == 0
    target = tmp_path / ".automation" / "social" / "drafts" / "2026-08-27-daily-owned.json"
    assert target.is_file()
