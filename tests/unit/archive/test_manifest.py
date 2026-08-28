from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tests.support.contracts import trace_message
from tests.support.planned import planned_callable, planned_signature


TARGET = "scripts/archive/manifest.py"


def _manifest_entries(value: object, trace_id: str) -> list[dict[str, object]]:
    assert isinstance(value, dict), trace_message(trace_id, "manifest must be a mapping")
    entries = value.get("entries")
    assert isinstance(entries, list), trace_message(trace_id, "manifest.entries must be a list")
    assert all(isinstance(entry, dict) for entry in entries), trace_message(
        trace_id, "manifest entry is not a mapping"
    )
    return entries


@pytest.mark.trace("ARCH-MAN-001")
@pytest.mark.red_expected
def test_manifest_module_exposes_the_complete_planned_api() -> None:
    expected = {
        "walk_safe": ("root",),
        "classify_path": ("relative_path",),
        "build_manifest": ("root",),
        "write_checksums": ("root", "entries", "output_path"),
        "verify_checksums": ("root", "checksums_path"),
    }
    for symbol, parameters in expected.items():
        planned_signature(TARGET, symbol, parameters, "ARCH-MAN-001")


@pytest.mark.trace("ARCH-MAN-002")
@pytest.mark.red_expected
def test_walk_safe_is_sorted_relative_and_does_not_follow_symlinks(tmp_path: Path) -> None:
    walk_safe = planned_callable(TARGET, "walk_safe", "ARCH-MAN-002")
    root = tmp_path / "tree"
    (root / "b").mkdir(parents=True)
    (root / "a.txt").write_text("a", encoding="utf-8")
    (root / "b" / "z.txt").write_text("z", encoding="utf-8")
    (root / "outside").symlink_to(tmp_path.parent, target_is_directory=True)
    first = walk_safe(root)
    second = walk_safe(root)
    assert first == second, trace_message("ARCH-MAN-002", "walk order is not deterministic")
    paths = [entry["path"] for entry in first]
    assert paths == sorted(paths), trace_message("ARCH-MAN-002", "walk order is not sorted")
    assert all(not Path(path).is_absolute() for path in paths), trace_message(
        "ARCH-MAN-002", "walk leaked an absolute path"
    )
    outside = next(entry for entry in first if entry["path"] == "outside")
    assert outside["type"] == "symlink" and outside.get("followed") is False, trace_message(
        "ARCH-MAN-002", "external symlink was followed"
    )


@pytest.mark.trace("ARCH-MAN-003")
@pytest.mark.red_expected
def test_classify_path_covers_sensitive_and_operational_categories() -> None:
    classify = planned_callable(TARGET, "classify_path", "ARCH-MAN-003")
    cases = {
        "workspace/app.py": "code",
        "workspace/.git/config": "git",
        ".openclaw/state.db": "state",
        ".env": "secret",
        ".config/google-chrome/Default/Cookies": "browser_profile",
        "logs/run.log": "runtime",
        "cache/item.bin": "cache",
        "generated/card.png": "generated",
        "media/photo.jpg": "media",
        "roblox/workspace.json": "excluded",
    }
    observed = {path: classify(path) for path in cases}
    assert observed == cases, trace_message(
        "ARCH-MAN-003", f"unexpected path classifications: {observed}"
    )


@pytest.mark.trace("ARCH-MAN-004")
@pytest.mark.red_expected
def test_build_manifest_contains_only_relative_metadata_and_no_file_content(tmp_path: Path) -> None:
    build_manifest = planned_callable(TARGET, "build_manifest", "ARCH-MAN-004")
    root = tmp_path / "archive-source"
    root.mkdir()
    secret_value = "synthetic-private-value-never-copy"
    (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (root / ".env").write_text(f"TOKEN={secret_value}\n", encoding="utf-8")
    manifest = build_manifest(root)
    entries = _manifest_entries(manifest, "ARCH-MAN-004")
    serialized = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
    assert secret_value not in serialized, trace_message(
        "ARCH-MAN-004", "manifest leaked file content"
    )
    assert all(not Path(str(entry["path"])).is_absolute() for entry in entries), trace_message(
        "ARCH-MAN-004", "manifest contains an absolute path"
    )
    required = {"path", "type", "size", "mtime_ns", "mode", "classification"}
    assert all(required <= set(entry) for entry in entries), trace_message(
        "ARCH-MAN-004", "manifest entry lacks required metadata"
    )


@pytest.mark.trace("ARCH-MAN-005")
@pytest.mark.red_expected
def test_checksum_file_is_atomic_sorted_and_reproducible(tmp_path: Path) -> None:
    write_checksums = planned_callable(TARGET, "write_checksums", "ARCH-MAN-005")
    root = tmp_path / "tree"
    root.mkdir()
    (root / "z.txt").write_bytes(b"z")
    (root / "a.txt").write_bytes(b"a")
    entries = [{"path": "z.txt"}, {"path": "a.txt"}]
    output = tmp_path / "CHECKSUMS.sha256"
    returned = write_checksums(root, entries, output)
    first = output.read_text(encoding="utf-8")
    returned_again = write_checksums(root, list(reversed(entries)), output)
    second = output.read_text(encoding="utf-8")
    assert Path(returned) == output and Path(returned_again) == output, trace_message(
        "ARCH-MAN-005", "checksum writer returned a different destination"
    )
    assert first == second, trace_message("ARCH-MAN-005", "checksum output is not reproducible")
    assert first.splitlines() == sorted(first.splitlines(), key=lambda line: line.split("  ", 1)[1]), trace_message(
        "ARCH-MAN-005", "checksum entries are not sorted"
    )
    assert hashlib.sha256(b"a").hexdigest() in first, trace_message(
        "ARCH-MAN-005", "checksum content is incorrect"
    )


@pytest.mark.trace("ARCH-MAN-006")
@pytest.mark.red_expected
def test_checksum_verifier_reports_missing_extra_and_mutated_files(tmp_path: Path) -> None:
    write_checksums = planned_callable(TARGET, "write_checksums", "ARCH-MAN-006")
    verify_checksums = planned_callable(TARGET, "verify_checksums", "ARCH-MAN-006")
    root = tmp_path / "tree"
    root.mkdir()
    (root / "keep.txt").write_text("before", encoding="utf-8")
    (root / "gone.txt").write_text("gone", encoding="utf-8")
    checksums = tmp_path / "CHECKSUMS.sha256"
    write_checksums(root, [{"path": "keep.txt"}, {"path": "gone.txt"}], checksums)
    (root / "keep.txt").write_text("after", encoding="utf-8")
    (root / "gone.txt").unlink()
    (root / "extra.txt").write_text("extra", encoding="utf-8")
    report = verify_checksums(root, checksums)
    assert report["ok"] is False, trace_message("ARCH-MAN-006", "mutation was accepted")
    assert report["mismatched"] == ["keep.txt"], trace_message(
        "ARCH-MAN-006", "changed file was not classified"
    )
    assert report["missing"] == ["gone.txt"], trace_message(
        "ARCH-MAN-006", "missing file was not classified"
    )
    assert report["extra"] == ["extra.txt"], trace_message(
        "ARCH-MAN-006", "extra file was not classified"
    )


@pytest.mark.trace("ARCH-COPY-001")
@pytest.mark.red_expected
def test_walk_excludes_roblox_by_rule_without_hiding_neighbor_projects(tmp_path: Path) -> None:
    walk_safe = planned_callable(TARGET, "walk_safe", "ARCH-COPY-001")
    root = tmp_path / "tree"
    (root / "roblox-agent").mkdir(parents=True)
    (root / "roblox-agent" / "world.rbxl").write_text("excluded", encoding="utf-8")
    (root / "mragentes-site").mkdir()
    (root / "mragentes-site" / "README.md").write_text("keep", encoding="utf-8")
    entries = walk_safe(root, exclude_names={"roblox-agent"})
    paths = {entry["path"] for entry in entries}
    assert "mragentes-site/README.md" in paths, trace_message(
        "ARCH-COPY-001", "neighbor project was excluded"
    )
    assert not any(path.startswith("roblox-agent/") for path in paths), trace_message(
        "ARCH-COPY-001", "Roblox content remains active in the copy inventory"
    )


@pytest.mark.trace("ARCH-COPY-002")
@pytest.mark.red_expected
def test_manifest_counts_files_directories_bytes_and_exceptions(tmp_path: Path) -> None:
    build_manifest = planned_callable(TARGET, "build_manifest", "ARCH-COPY-002")
    root = tmp_path / "tree"
    (root / "dir").mkdir(parents=True)
    (root / "a").write_bytes(b"abc")
    (root / "dir" / "b").write_bytes(b"12345")
    manifest = build_manifest(root)
    assert manifest["summary"] == {
        "files": 2,
        "directories": 1,
        "bytes": 8,
        "exceptions": 0,
    }, trace_message("ARCH-COPY-002", f"wrong manifest summary: {manifest.get('summary')}")


@pytest.mark.trace("ARCH-COPY-003")
@pytest.mark.red_expected
def test_long_name_rescue_map_is_explicit_reversible_and_collision_safe(tmp_path: Path) -> None:
    build_manifest = planned_callable(TARGET, "build_manifest", "ARCH-COPY-003")
    root = tmp_path / "tree"
    root.mkdir()
    first = "a" * 150 + ".md"
    second = "a" * 149 + "b.md"
    manifest = build_manifest(
        root,
        rescue_map={first: "rescued-a.md", second: "rescued-b.md"},
        unavailable_paths={first, second},
    )
    mapping = manifest["rescue_name_map"]
    assert mapping == {first: "rescued-a.md", second: "rescued-b.md"}, trace_message(
        "ARCH-COPY-003", "rescue mapping is not reversible"
    )
    assert len(set(mapping.values())) == len(mapping), trace_message(
        "ARCH-COPY-003", "rescue names collide"
    )


@pytest.mark.trace("ARCH-COPY-004")
@pytest.mark.red_expected
def test_disappearing_or_unreadable_files_become_sanitized_exceptions(tmp_path: Path) -> None:
    build_manifest = planned_callable(TARGET, "build_manifest", "ARCH-COPY-004")
    root = tmp_path / "tree"
    root.mkdir()
    (root / "vanished.txt").write_text("temporary", encoding="utf-8")

    def read_metadata(path: Path) -> object:
        if path.name == "vanished.txt":
            raise FileNotFoundError("synthetic vanished path")
        return path.lstat()

    manifest = build_manifest(root, metadata_reader=read_metadata)
    exceptions = manifest["exceptions"]
    assert exceptions == [
        {"path": "vanished.txt", "reason": "unavailable", "recoverable": False}
    ], trace_message("ARCH-COPY-004", f"unexpected copy exceptions: {exceptions}")
    assert str(root) not in json.dumps(exceptions), trace_message(
        "ARCH-COPY-004", "exception leaked an absolute path"
    )


@pytest.mark.trace("ARCH-COPY-005")
@pytest.mark.red_expected
def test_copy_inventory_never_follows_external_symlink_or_special_file(tmp_path: Path) -> None:
    walk_safe = planned_callable(TARGET, "walk_safe", "ARCH-COPY-005")
    root = tmp_path / "tree"
    root.mkdir()
    (root / "external").symlink_to(tmp_path.parent, target_is_directory=True)
    entries = walk_safe(root)
    external = next(entry for entry in entries if entry["path"] == "external")
    assert external["type"] == "symlink", trace_message(
        "ARCH-COPY-005", "external link was not classified as a symlink"
    )
    assert external.get("copied") is False, trace_message(
        "ARCH-COPY-005", "external link was selected for copy"
    )


@pytest.mark.trace("ARCH-COPY-006")
@pytest.mark.red_expected
def test_repeated_inventory_is_byte_stable_and_contains_no_secret_values(tmp_path: Path) -> None:
    build_manifest = planned_callable(TARGET, "build_manifest", "ARCH-COPY-006")
    root = tmp_path / "tree"
    root.mkdir()
    synthetic_secret = "ghp_" + "s" * 36
    (root / "credential.txt").write_text(synthetic_secret, encoding="utf-8")
    first = json.dumps(build_manifest(root), sort_keys=True, separators=(",", ":"))
    second = json.dumps(build_manifest(root), sort_keys=True, separators=(",", ":"))
    assert first == second, trace_message("ARCH-COPY-006", "inventory is not byte-stable")
    assert synthetic_secret not in first, trace_message(
        "ARCH-COPY-006", "inventory leaked a synthetic secret value"
    )
