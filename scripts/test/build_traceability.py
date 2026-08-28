from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.test.validate_traceability import collect_test_metadata


JS_TITLE_RE = re.compile(
    r"(?:^| > )\[(?P<id>[A-Z][A-Z0-9-]+-[0-9]{3})\]\s+(?P<requirement>.+)$"
)

# These contracts were already satisfied by the copied implementation or by
# the deterministic test fakes before the migration implementation began. The
# list is deliberately explicit so a newly passing RED cannot be silently
# reclassified on a later run.
JS_BASELINE_GREEN_IDS = {
    "PUSH-AUTH-001",
    "PUSH-AUTH-002",
    "PUSH-AUTH-003",
    "PUSH-CLIENT-002",
    "PUSH-CLIENT-004",
    "PUSH-CLIENT-007",
    "PUSH-CLIENT-011",
    "PUSH-CLIENT-015",
    "PUSH-CRYPTO-001",
    "PUSH-CRYPTO-002",
    "PUSH-CRYPTO-004",
    "PUSH-CRYPTO-011",
    "PUSH-KV-001",
    "PUSH-KV-002",
    "PUSH-KV-003",
    "PUSH-KV-006",
    "PUSH-KV-007",
    "PUSH-KV-009",
    "PUSH-PAYLOAD-002",
    "PUSH-PAYLOAD-004",
    "PUSH-PAYLOAD-009",
    "PUSH-PAYLOAD-010",
    "PUSH-SUB-015",
    "PUSH-SW-001",
    "PUSH-SW-002",
    "PUSH-SW-004",
    "PUSH-SW-006",
    "PUSH-SW-007",
    "PUSH-UNSUB-008",
    "PUSH-WELCOME-008",
}

JS_SOURCE_RULES: list[tuple[str, str]] = [
    ("PUSH-CLIENT-", "assets/js/push.js"),
    ("PUSH-SW-", "static/sw.js"),
    ("PUSH-AUTH-", "workers/push/src/auth.ts"),
    ("PUSH-PAYLOAD-", "workers/push/src/payload.ts"),
    ("PUSH-CRYPTO-", "workers/push/src/crypto.ts"),
    ("PUSH-COORD-", "workers/push/src/coordinator.ts"),
    ("PUSH-DELIVERY-", "workers/push/src/storage.ts"),
    ("PUSH-KV-", "workers/push/src/storage.ts"),
    ("PUSH-SUB-", "workers/push/src/subscriptions.ts"),
    ("PUSH-WELCOME-", "workers/push/src/subscriptions.ts"),
    ("PUSH-UNSUB-", "workers/push/src/subscriptions.ts"),
    ("PUSH-SEND-", "workers/push/src/index.ts"),
]


PREFIX_RULES: list[tuple[str, str, str, str]] = [
    ("HARNESS-", "19.3", "scripts/test", "local"),
    ("SRC-", "21.1", "scripts/automation/preflight.py", "local"),
    ("GIT-", "21.1", "repository/git", "local"),
    ("PORT-", "21.1", "scripts/automation/blog_guard.py::portable_slug", "local"),
    ("DISK-", "21.1", "scripts/automation/preflight.py::assert_disk_space", "local"),
    ("ARCH-", "21.2", "scripts/archive", "local"),
    ("SEC-SCAN-", "21.2", "scripts/scan_secrets.py", "local"),
    ("SEC-", "21.2", ".github/workflows", "GitHub"),
    ("NEWS-", "21.3", "scripts/automation/news_queue.py", "Codex Scheduled"),
    ("BLOG-", "21.4", "scripts/automation/blog_guard.py", "Codex Scheduled"),
    ("SOCIAL-", "21.5", "scripts/social", "GitHub"),
    ("META-", "21.6", "scripts/social/publisher.py", "Meta"),
    ("PUSH-", "21.7", "workers/push/src", "Cloudflare"),
    ("LEGACY-PUSH-", "22.2", "scripts/push_server.py", "local"),
    ("WF-", "21.8", ".github/workflows", "GitHub"),
    ("SKILL-", "21.9", ".agents/skills", "Codex Scheduled"),
    ("TASK-", "21.9", ".automation/schedules", "Codex Scheduled"),
    ("PROJECT-", "21.9", ".testplan/external-capabilities.json", "local"),
    ("CF-MCP-", "21.9", ".testplan/external-capabilities.json", "Cloudflare"),
    ("CUT-", "21.10", "scripts/automation/preflight.py", "local"),
    ("E2E-", "21.10", "scripts/automation/e2e_simulator.py", "local"),
    ("SOAK-", "21.10", "scripts/automation/soak_report.py", "local"),
    ("RETIRE-", "21.10", "OPERATIONS.md", "local"),
    ("VIS-", "21.11", "assets", "local"),
    ("A11Y-", "21.11", "layouts", "local"),
    ("SCHEMA-", "21.3", ".automation/schemas", "local"),
    ("CLI-", "22.5", "scripts/social/cli.py", "local"),
]


def classify(trace_id: str) -> tuple[str, str, str]:
    for prefix, section, symbol, owner in PREFIX_RULES:
        if trace_id.startswith(prefix):
            return section, symbol, owner
    return "23", "repository", "local"


def layer_for(nodeids: list[str]) -> str:
    joined = " ".join(nodeids)
    for segment, layer in (
        ("/e2e/", "e2e"),
        ("/visual/", "visual"),
        ("/integration/", "integration"),
        ("/contract/", "contract"),
        ("/static/", "static"),
        ("/workflows/", "contract"),
    ):
        if segment in joined:
            return layer
    return "unit"


def collect_concrete_python_nodes(root: Path) -> list[str]:
    completed = subprocess.run(
        [str(root / ".venv/bin/python"), "-m", "pytest", "--collect-only", "-q"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in completed.stdout.splitlines() if line.startswith("tests/")]


def javascript_source_symbol(trace_id: str) -> str:
    for prefix, symbol in JS_SOURCE_RULES:
        if trace_id.startswith(prefix):
            return symbol
    raise ValueError(f"no JavaScript source-symbol rule for {trace_id}")


def build_javascript_catalogue_from_rows(
    rows: list[dict[str, Any]], root: Path
) -> list[dict[str, Any]]:
    root = root.resolve()
    entries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_nodes: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"Vitest list row {index} is not an object")
        name = row.get("name")
        filename = row.get("file")
        if not isinstance(name, str) or not isinstance(filename, str):
            raise ValueError(f"Vitest list row {index} lacks name/file")
        match = JS_TITLE_RE.search(name)
        if match is None:
            raise ValueError(f"Vitest title lacks a stable trace id: {name}")
        trace_id = match.group("id")
        requirement = match.group("requirement").strip()
        if trace_id in seen_ids:
            raise ValueError(f"duplicate JavaScript trace id: {trace_id}")
        seen_ids.add(trace_id)

        source = Path(filename)
        source = source.resolve() if source.is_absolute() else (root / source).resolve()
        try:
            relative = source.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"Vitest test file escapes repository: {filename}") from exc
        if not relative.startswith("tests-js/"):
            raise ValueError(f"Vitest test file is outside tests-js: {relative}")
        title = f"[{trace_id}] {requirement}"
        nodeid = f"{relative}::{title}"
        if nodeid in seen_nodes:
            raise ValueError(f"duplicate JavaScript test node: {nodeid}")
        seen_nodes.add(nodeid)
        entries.append(
            {
                "id": trace_id,
                "initial_state": (
                    "BASELINE_GREEN" if trace_id in JS_BASELINE_GREEN_IDS else "RED_EXPECTED"
                ),
                "requirement": requirement,
                "source_symbols": [javascript_source_symbol(trace_id)],
                "test_paths": [nodeid],
            }
        )
    return sorted(entries, key=lambda item: item["id"])


def collect_concrete_javascript_rows(root: Path) -> list[dict[str, Any]]:
    completed = subprocess.run(
        [
            str(root / "node_modules/.bin/vitest"),
            "list",
            "--config",
            "tests-js/vitest.config.mjs",
            "--json",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, list):
        raise ValueError("Vitest list JSON root must be an array")
    return value


def build(root: Path) -> dict[str, Any]:
    metadata = collect_test_metadata(root)
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"nodes": [], "names": [], "states": set()}
    )
    for nodeid in collect_concrete_python_nodes(root):
        base = nodeid.split("[", 1)[0]
        item = metadata[base]
        group = grouped[item["trace_id"]]
        group["nodes"].append(nodeid)
        group["names"].append(item["name"])
        group["states"].add(item["initial_state"])

    js_catalog = root / "tests-js" / "traceability.json"
    if js_catalog.is_file():
        for item in json.loads(js_catalog.read_text(encoding="utf-8")):
            group = grouped[item["id"]]
            group["nodes"].extend(item["test_paths"])
            group["names"].append(item.get("requirement", item["id"]))
            group["states"].add(item["initial_state"])
            group["source_symbols"] = item["source_symbols"]

    requirements: list[dict[str, Any]] = []
    for trace_id, group in sorted(grouped.items()):
        if len(group["states"]) != 1:
            raise ValueError(f"mixed initial states for {trace_id}: {group['states']}")
        state = next(iter(group["states"]))
        section, symbol, owner = classify(trace_id)
        entry: dict[str, Any] = {
            "id": trace_id,
            "requirement": "; ".join(sorted({name.replace("test_", "").replace("_", " ") for name in group["names"]})),
            "plan_section": section,
            "source_symbols": group.get("source_symbols", [symbol]),
            "test_paths": sorted(set(group["nodes"])),
            "layer": layer_for(group["nodes"]),
            "side_effect_scope": "git-temp" if any("git_" in node for node in group["nodes"]) else "filesystem-temp" if any("/integration/" in node for node in group["nodes"]) else "none",
            "initial_state": state,
            "owner": owner,
        }
        if state == "RED_EXPECTED":
            entry["expected_red"] = {
                "kind": "assertion",
                "code": trace_id,
                "message_regex": rf"\\[{trace_id}\\]",
            }
        elif state == "EXTERNAL_BLOCKED":
            entry["external_probe"] = {
                "provider": owner if owner in {"Codex", "GitHub", "Meta", "Cloudflare"} else "Codex",
                "probe": f"operational probe for {trace_id}",
                "blocked_reason": "provider capability is not exposed in the current test session",
            }
        requirements.append(entry)
    return {"version": 1, "requirements": requirements}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path(".testplan/traceability.yml"))
    args = parser.parse_args()
    root = args.root.resolve()
    javascript_catalogue = build_javascript_catalogue_from_rows(
        collect_concrete_javascript_rows(root), root
    )
    missing_green_ids = JS_BASELINE_GREEN_IDS - {
        item["id"] for item in javascript_catalogue
    }
    if missing_green_ids:
        raise ValueError(
            f"declared JavaScript baseline-green tests were not collected: {sorted(missing_green_ids)}"
        )
    (root / "tests-js/traceability.json").write_text(
        json.dumps(javascript_catalogue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    output = root / args.output
    output.write_text(
        yaml.safe_dump(build(root), allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
