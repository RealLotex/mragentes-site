from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def junit_results(path: Path) -> dict[str, tuple[str, str]]:
    root = ET.parse(path).getroot()
    results: dict[str, tuple[str, str]] = {}
    for case in root.iter("testcase"):
        classname = case.attrib.get("classname", "").replace(".", "/")
        name = case.attrib.get("name", "")
        nodeid = f"{classname}.py::{name}" if classname else name
        failure = case.find("failure")
        error = case.find("error")
        skipped = case.find("skipped")
        if error is not None:
            results[nodeid] = ("ERROR", error.attrib.get("message", ""))
        elif skipped is not None:
            results[nodeid] = ("SKIPPED", skipped.attrib.get("message", ""))
        elif failure is not None:
            results[nodeid] = ("FAILED", failure.attrib.get("message", ""))
        else:
            results[nodeid] = ("PASSED", "")
    return results


def vitest_results(path: Path, root: Path) -> dict[str, tuple[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    suites = payload.get("testResults") if isinstance(payload, dict) else None
    if not isinstance(suites, list):
        raise ValueError("Vitest JSON report lacks testResults")

    statuses = {
        "passed": "PASSED",
        "failed": "FAILED",
        "pending": "SKIPPED",
        "skipped": "SKIPPED",
        "todo": "SKIPPED",
        "disabled": "SKIPPED",
    }
    root = root.resolve()
    results: dict[str, tuple[str, str]] = {}
    for suite_index, suite in enumerate(suites):
        if not isinstance(suite, dict):
            raise ValueError(f"Vitest suite {suite_index} is not an object")
        filename = suite.get("name")
        assertions = suite.get("assertionResults")
        if not isinstance(filename, str) or not isinstance(assertions, list):
            raise ValueError(f"Vitest suite {suite_index} lacks name/assertionResults")
        source = Path(filename)
        source = source.resolve() if source.is_absolute() else (root / source).resolve()
        try:
            relative = source.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"Vitest suite path escapes repository: {filename}") from exc

        for assertion_index, assertion in enumerate(assertions):
            if not isinstance(assertion, dict):
                raise ValueError(
                    f"Vitest assertion {suite_index}:{assertion_index} is not an object"
                )
            title = assertion.get("title")
            raw_status = assertion.get("status")
            if not isinstance(title, str) or not title:
                raise ValueError(f"Vitest assertion {suite_index}:{assertion_index} lacks title")
            if raw_status not in statuses:
                status = "ERROR"
            else:
                status = statuses[raw_status]
            raw_messages = assertion.get("failureMessages", [])
            if not isinstance(raw_messages, list):
                raise ValueError(
                    f"Vitest assertion {suite_index}:{assertion_index} has invalid failureMessages"
                )
            message = "\n".join(str(item) for item in raw_messages)
            nodeid = f"{relative}::{title}"
            if nodeid in results:
                raise ValueError(f"duplicate Vitest node: {nodeid}")
            results[nodeid] = (status, message)
    return results


def git_output(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def summarize(
    root: Path,
    manifest_path: Path,
    junit_path: Path,
    javascript_path: Path | None = None,
) -> tuple[dict[str, Any], bool]:
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    results = junit_results(junit_path)
    if javascript_path is not None:
        javascript = vitest_results(javascript_path, root)
        duplicates = set(results) & set(javascript)
        if duplicates:
            raise ValueError(f"duplicate Python/JavaScript result nodes: {sorted(duplicates)}")
        results.update(javascript)
    requirements: list[dict[str, Any]] = []
    counts = {"red_expected": 0, "baseline_green": 0, "external_blocked": 0, "errors": 0}
    valid = True

    for item in manifest["requirements"]:
        node_results = [results.get(nodeid, ("MISSING", "")) for nodeid in item["test_paths"]]
        statuses = {status for status, _ in node_results}
        initial = item["initial_state"]
        if initial == "RED_EXPECTED":
            prefix = f"[{item['id']}]"
            classified = statuses == {"FAILED"} and all(prefix in message for _, message in node_results)
            status = "RED_EXPECTED" if classified else "ERROR"
        elif initial == "BASELINE_GREEN":
            status = "BASELINE_GREEN" if statuses == {"PASSED"} else "ERROR"
        else:
            local_ok = statuses <= {"PASSED", "FAILED"} and "MISSING" not in statuses
            status = "EXTERNAL_BLOCKED" if local_ok else "ERROR"
        if status == "ERROR":
            counts["errors"] += 1
            valid = False
        else:
            counts[status.lower()] += 1
        requirements.append(
            {
                "id": item["id"],
                "status": status,
                "nodeids": item["test_paths"],
                "fingerprints": [fingerprint(message) for _, message in node_results if message],
            }
        )

    index_path = root / ".git" / "index"
    payload = {
        "schema_version": 1,
        "run_id": datetime.now(UTC).strftime("red-%Y%m%dT%H%M%SZ"),
        "generated_at": datetime.now(UTC).isoformat(),
        "git": {
            "head": git_output(root, "rev-parse", "HEAD"),
            "index_digest": hashlib.sha256(index_path.read_bytes()).hexdigest(),
        },
        "environment": {
            "python": platform.python_version(),
            "node": os.environ.get("MRA_NODE_VERSION", "unknown"),
            "name_max": os.pathconf(root, "PC_NAME_MAX"),
        },
        "counts": counts,
        "requirements": requirements,
    }
    return payload, valid


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--traceability", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--javascript", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    payload, valid = summarize(root, args.traceability, args.junit, args.javascript)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
