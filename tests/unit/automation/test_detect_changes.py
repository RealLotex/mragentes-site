from __future__ import annotations

import json

import pytest

from scripts.automation import detect_changes


@pytest.mark.trace("DEPLOY-DETECT-004")
@pytest.mark.red_expected
def test_detector_combines_sorted_note_and_daily_outputs(monkeypatch) -> None:
    monkeypatch.setattr(
        detect_changes,
        "changed_note_slugs",
        lambda repo, before, after: ["b", "a"],
    )
    monkeypatch.setattr(
        detect_changes,
        "changed_social_drafts",
        lambda repo, before, after: [
            ".automation/social/drafts/2026-08-27-daily-owned.json"
        ],
    )
    result = detect_changes.detect(".", "0" * 40, "a" * 40)
    assert result == {
        "note_slugs": ["a", "b"],
        "daily_drafts": [".automation/social/drafts/2026-08-27-daily-owned.json"],
    }


@pytest.mark.trace("DEPLOY-DETECT-005")
@pytest.mark.red_expected
def test_detector_cli_emits_one_compact_json_document(monkeypatch, capsys) -> None:
    expected = {"note_slugs": ["nota"], "daily_drafts": []}
    monkeypatch.setattr(detect_changes, "detect", lambda repo, before, after: expected)
    assert detect_changes.main(
        ["--repo", ".", "--before", "0" * 40, "--after", "a" * 40]
    ) == 0
    output = capsys.readouterr().out.strip()
    assert json.loads(output) == expected
    assert "\n" not in output
