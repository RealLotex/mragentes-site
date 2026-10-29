from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from PIL import Image

from scripts.automation import editorial_release as publisher
from tests.unit.automation.test_editorial_release import _submission

pytestmark = [pytest.mark.trace("EDITORIAL-EXTRA-001"), pytest.mark.red_expected]


def test_extra_prepares_six_artifacts_without_overwriting_daily_report(tmp_path, monkeypatch):
    daily = tmp_path / ".automation/reports/editorial-2026-10-29.json"
    daily.parent.mkdir(parents=True)
    daily.write_text('{"note_slug":"daily"}\n')
    image = tmp_path / "cover.png"
    Image.new("RGB", (800, 500)).save(image)

    def render(command, root, **kwargs):
        social = root / f"static/images/social/notes/{command[-1]}.jpg"
        social.parent.mkdir(parents=True)
        Image.new("RGB", (1080, 1350)).save(social)
        return ""

    monkeypatch.setattr(publisher, "_run", render)
    paths = publisher.prepare_release(
        tmp_path, publisher.validate_submission(_submission(), date(2026, 10, 29)),
        image, date(2026, 10, 29), edition="iol-mcp",
    )
    assert len(paths) == 6
    assert paths[-1] == ".automation/reports/editorial-2026-10-29-iol-mcp.json"
    report = json.loads((tmp_path / paths[-1]).read_text())
    assert report["branch"] == "automation/editorial/2026-10-29-iol-mcp"
    assert report["run_id"] == "editorial:2026-10-29:iol-mcp"
    assert daily.read_text() == '{"note_slug":"daily"}\n'


@pytest.mark.parametrize("edition", ["../main", "", "Upper", "x" * 49, "a/b"])
def test_invalid_edition_is_rejected_before_git(tmp_path, monkeypatch, edition):
    monkeypatch.setattr(publisher, "_run", lambda *a, **k: pytest.fail("Git called"))
    with pytest.raises(ValueError, match="edition"):
        publisher.release(tmp_path / "absent.json", tmp_path / "absent.png", edition=edition)


@pytest.mark.parametrize("existing", [False, True])
def test_extra_release_bypasses_only_daily_guard_and_is_idempotent(tmp_path, monkeypatch, existing):
    payload = tmp_path / "input.json"
    payload.write_text(json.dumps(_submission()))
    image = tmp_path / "cover.png"
    Image.new("RGB", (800, 500)).save(image)
    parent = tmp_path / "temporary"
    parent.mkdir()
    worktree = parent / "worktree"
    worktree.mkdir()
    day = publisher.datetime.now(publisher.TIMEZONE).date().isoformat()
    reports = worktree / ".automation/reports"
    reports.mkdir(parents=True)
    (reports / f"editorial-{day}.json").write_text('{"note_slug":"daily"}')
    notes = worktree / "content/notas"
    notes.mkdir(parents=True)
    (notes / "daily.md").write_text(f'date: "{day}T00:00:00-03:00"')
    slug = str(publisher.portable_slug(_submission()["title"], max_component_bytes=120))
    if existing:
        (reports / f"editorial-{day}-iol-mcp.json").write_text(json.dumps({"note_slug": slug}))
    paths = [f"artifact-{i}" for i in range(6)]
    calls = []

    def run(command, root, **kwargs):
        calls.append(command)
        if command[:5] == ["git", "diff", "--cached", "--name-only"]:
            return "\n".join(paths)
        return ""

    def prepare(*args, **kwargs):
        assert kwargs == {"edition": "iol-mcp"}
        assert not existing
        return paths

    monkeypatch.setattr(publisher.tempfile, "mkdtemp", lambda **k: str(parent))
    monkeypatch.setattr(publisher, "_run", run)
    monkeypatch.setattr(publisher, "prepare_release", prepare)
    monkeypatch.setattr(Path, "rmdir", lambda self: None)
    result = publisher.release(payload, image, dry_run=True, edition="iol-mcp")
    assert result.startswith("skipped_valid:" if existing else "dry_run_valid:")
    assert ["git", "ls-remote", "--heads", "origin", f"automation/editorial/{day}-iol-mcp"] in calls
    assert not any(command[:2] == ["git", "push"] for command in calls)
