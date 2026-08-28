from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import scan_secrets as scanner
from tests.support.contracts import trace_message


def run_git(repository: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def local_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    run_git(repository, "init", "--quiet")
    run_git(repository, "config", "user.name", "Secret Scan Tests")
    run_git(repository, "config", "user.email", "secret-scan@example.invalid")
    (repository / ".gitignore").write_text(
        ".env\n.env.*\n!.env.example\nconfig.local.json\n*.pem\n*.key\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(scanner, "BASE_DIR", repository)
    return repository


@pytest.mark.trace("SEC-SCAN-001")
@pytest.mark.red_expected
def test_high_confidence_synthetic_values_are_detected_and_classified() -> None:
    values = {
        "github": "ghp_" + "A" * 36,
        "openai": "sk-" + "B" * 32,
        "meta-token": "EAA" + "C" * 40,
        "private-key": "-----BEGIN " + "PRIVATE KEY-----",
    }

    hits = scanner.scan_text("\n".join(values.values()), "fixture.txt")
    kinds = {hit[2] for hit in hits}

    assert set(values).issubset(kinds), trace_message(
        "SEC-SCAN-001", f"missing high-confidence detectors: {set(values) - kinds}"
    )


@pytest.mark.trace("SEC-SCAN-002")
@pytest.mark.red_expected
def test_allowlist_is_precise_and_every_hit_is_fully_redacted() -> None:
    value = "ghp_" + "D" * 36
    allowed = "\n".join(
        (
            'api_key = "your_api_key"',
            'access_token = "${META_ACCESS_TOKEN}"',
            'password = "synthetic-password"',
        )
    )

    assert scanner.scan_text(allowed, "examples.env") == [], trace_message(
        "SEC-SCAN-002", "documented placeholders were treated as real credentials"
    )
    hits = scanner.scan_text(f"{value}  # example shown nearby", "fixture.txt")
    assert hits and value not in repr(hits), trace_message(
        "SEC-SCAN-002", "a real-shaped value was allowlisted or returned unredacted"
    )
    assert value not in scanner._safe_output(f"prefix {value} suffix"), trace_message(
        "SEC-SCAN-002", "diagnostic redaction exposed the matched value"
    )


@pytest.mark.trace("SEC-SCAN-003")
@pytest.mark.red_expected
def test_binary_files_are_skipped_and_symlinks_are_never_followed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = local_repository(tmp_path, monkeypatch)
    value = "ghp_" + "E" * 36
    (repository / "binary.dat").write_bytes(b"\x00\x01" + value.encode("ascii"))
    outside = tmp_path / "outside.txt"
    outside.write_text(value, encoding="utf-8")
    (repository / "external-link").symlink_to(outside)
    run_git(repository, "add", ".gitignore", "binary.dat", "external-link")

    hits = scanner.scan_working(False)

    assert hits == [], trace_message(
        "SEC-SCAN-003", "binary content or an external symlink target was scanned"
    )


@pytest.mark.trace("SEC-SCAN-004")
@pytest.mark.red_expected
def test_sensitive_tracked_names_are_rejected_but_templates_are_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = local_repository(tmp_path, monkeypatch)
    (repository / ".env.example").write_text("META_ACCESS_TOKEN=\n", encoding="utf-8")
    (repository / ".env.production").write_text("META_ACCESS_TOKEN=\n", encoding="utf-8")
    (repository / "config.local.json").write_text("{}\n", encoding="utf-8")
    (repository / "private.key").write_text("placeholder\n", encoding="utf-8")
    run_git(repository, "add", ".gitignore", ".env.example")
    run_git(repository, "add", "--force", ".env.production", "config.local.json", "private.key")

    problems = scanner.check_hygiene()
    flattened = "\n".join(problems)

    for name in (".env.production", "config.local.json", "private.key"):
        assert name in flattened, trace_message(
            "SEC-SCAN-004", f"tracked sensitive filename was accepted: {name}"
        )
    assert ".env.example" not in flattened, trace_message(
        "SEC-SCAN-004", "the empty public environment template was rejected"
    )


@pytest.mark.trace("SEC-SCAN-005")
@pytest.mark.red_expected
def test_tracked_blob_is_scanned_from_index_when_worktree_path_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = local_repository(tmp_path, monkeypatch)
    value = "sk-" + "F" * 32
    tracked = repository / "tracked.txt"
    tracked.write_text(value, encoding="utf-8")
    run_git(repository, "add", ".gitignore", "tracked.txt")
    tracked.unlink()

    hits = scanner.scan_working(False)

    assert hits and hits[0][0] == "tracked.txt", trace_message(
        "SEC-SCAN-005", "missing worktree path was not scanned from the Git index"
    )
    assert value not in repr(hits), trace_message(
        "SEC-SCAN-005", "index-backed result exposed the credential"
    )


@pytest.mark.trace("SEC-SCAN-006")
@pytest.mark.red_expected
def test_untracked_files_are_included_only_when_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = local_repository(tmp_path, monkeypatch)
    value = "EAA" + "G" * 40
    (repository / "untracked.txt").write_text(value, encoding="utf-8")
    run_git(repository, "add", ".gitignore")

    tracked_only = scanner.scan_working(False)
    with_untracked = scanner.scan_working(True)

    assert tracked_only == [], trace_message(
        "SEC-SCAN-006", "default tree scan unexpectedly included untracked files"
    )
    assert any(hit[0] == "untracked.txt" for hit in with_untracked), trace_message(
        "SEC-SCAN-006", "explicit untracked scan omitted an untracked credential"
    )
    assert value not in repr(with_untracked), trace_message(
        "SEC-SCAN-006", "untracked result exposed the credential"
    )


@pytest.mark.trace("SEC-SCAN-007")
@pytest.mark.red_expected
def test_history_scan_finds_superseded_blob_without_exposing_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = local_repository(tmp_path, monkeypatch)
    value = "github_pat_" + "H" * 55
    historical = repository / "historical.txt"
    historical.write_text(value, encoding="utf-8")
    run_git(repository, "add", ".gitignore", "historical.txt")
    run_git(repository, "commit", "--quiet", "-m", "synthetic historical fixture")
    historical.write_text("safe\n", encoding="utf-8")
    run_git(repository, "add", "historical.txt")
    run_git(repository, "commit", "--quiet", "-m", "replace fixture")

    assert scanner.scan_working(False) == [], trace_message(
        "SEC-SCAN-007", "current safe tree produced a false positive"
    )
    hits = scanner.scan_history()

    assert any(hit[0].startswith("historical.txt @ ") for hit in hits), trace_message(
        "SEC-SCAN-007", "superseded historical blob was not scanned"
    )
    assert value not in repr(hits), trace_message(
        "SEC-SCAN-007", "history result exposed the credential"
    )


@pytest.mark.trace("SEC-SCAN-008")
@pytest.mark.red_expected
def test_remote_credentials_are_reported_without_echoing_url_or_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = local_repository(tmp_path, monkeypatch)
    username = "automation-user"
    password = "synthetic-remote-password"
    credential_url = f"https://{username}:{password}@example.invalid/repository.git"
    run_git(repository, "remote", "add", "origin", credential_url)

    problems = scanner._remote_hygiene()
    flattened = "\n".join(problems)

    assert problems and "origin" in flattened, trace_message(
        "SEC-SCAN-008", "credential-bearing remote was not rejected"
    )
    assert credential_url not in flattened and password not in flattened, trace_message(
        "SEC-SCAN-008", "remote diagnostic exposed a credential or full URL"
    )


@pytest.mark.trace("SEC-SCAN-009")
@pytest.mark.red_expected
def test_git_http_extraheader_is_reported_without_echoing_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = local_repository(tmp_path, monkeypatch)
    header = "AUTHORIZATION: Basic " + "c3ludGhldGljOnZhbHVl"
    run_git(
        repository,
        "config",
        "--local",
        "http.https://example.invalid/.extraheader",
        header,
    )

    problems = scanner._remote_hygiene()
    flattened = "\n".join(problems)

    assert any("extraheader" in problem.lower() for problem in problems), trace_message(
        "SEC-SCAN-009", "Git HTTP authentication header was not rejected"
    )
    assert header not in flattened, trace_message(
        "SEC-SCAN-009", "extraheader diagnostic exposed the configured value"
    )


@pytest.mark.trace("SEC-SCAN-010")
@pytest.mark.red_expected
def test_main_has_stable_clean_finding_and_infrastructure_exit_codes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(scanner, "working_files", lambda include_untracked: [])
    monkeypatch.setattr(scanner, "scan_working", lambda include_untracked: [])
    monkeypatch.setattr(scanner, "check_hygiene", lambda: [])
    assert scanner.main([]) == 0, trace_message("SEC-SCAN-010", "clean scan did not exit 0")
    capsys.readouterr()

    value = "ghp_" + "J" * 36
    redacted_hit = scanner.scan_text(value, "fixture.txt")
    monkeypatch.setattr(scanner, "scan_working", lambda include_untracked: redacted_hit)
    assert scanner.main([]) == 1, trace_message("SEC-SCAN-010", "finding did not exit 1")
    finding_output = capsys.readouterr()
    assert value not in finding_output.out + finding_output.err, trace_message(
        "SEC-SCAN-010", "finding output exposed the credential"
    )

    def fail_inventory(include_untracked: bool) -> list[Path]:
        raise OSError("synthetic infrastructure failure")

    monkeypatch.setattr(scanner, "working_files", fail_inventory)
    assert scanner.main([]) == 2, trace_message(
        "SEC-SCAN-010", "infrastructure failure did not exit 2"
    )
    infrastructure_output = capsys.readouterr()
    assert "synthetic infrastructure failure" not in (
        infrastructure_output.out + infrastructure_output.err
    ), trace_message("SEC-SCAN-010", "infrastructure detail leaked to output")
