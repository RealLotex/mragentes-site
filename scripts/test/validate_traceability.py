from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import jsonschema
import yaml

RANGE_RE = re.compile(r"\.\.|\*|\[[^]]+\]")
TRACE_ID_RE = re.compile(r"^[A-Z][A-Z0-9-]+-[0-9]{3}$")
SECRET_RE = re.compile(
    r"(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9._-]{16,})"
)
JS_CATALOG_KEYS = {
    "id",
    "initial_state",
    "requirement",
    "source_symbols",
    "test_paths",
}
INITIAL_STATES = {"BASELINE_GREEN", "RED_EXPECTED", "EXTERNAL_BLOCKED"}


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("traceability root must be a mapping")
    return value


def trace_marker_id(decorator: ast.expr) -> str | None:
    if not isinstance(decorator, ast.Call) or len(decorator.args) != 1:
        return None
    function = decorator.func
    if not (
        isinstance(function, ast.Attribute)
        and function.attr == "trace"
        and isinstance(function.value, ast.Attribute)
        and function.value.attr == "mark"
    ):
        return None
    argument = decorator.args[0]
    return argument.value if isinstance(argument, ast.Constant) and isinstance(argument.value, str) else None


def marker_name(decorator: ast.expr) -> str | None:
    if isinstance(decorator, ast.Attribute) and isinstance(decorator.value, ast.Attribute):
        if decorator.value.attr == "mark":
            return decorator.attr
    return None


def collect_test_metadata(root: Path) -> dict[str, dict[str, str]]:
    nodes: dict[str, dict[str, str]] = {}
    for path in sorted((root / "tests").rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(root).as_posix()
        class_stack: list[str] = []

        class Visitor(ast.NodeVisitor):
            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                class_stack.append(node.name)
                self.generic_visit(node)
                class_stack.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                if node.name.startswith("test_"):
                    marker_ids = [trace_marker_id(item) for item in node.decorator_list]
                    marker_ids = [item for item in marker_ids if item]
                    states = [
                        name
                        for item in node.decorator_list
                        if (name := marker_name(item))
                        in {"baseline_green", "red_expected", "external_blocked"}
                    ]
                    nodeid = "::".join([relative, *class_stack, node.name])
                    if len(marker_ids) != 1:
                        raise ValueError(f"test must have exactly one literal trace marker: {nodeid}")
                    if len(states) != 1:
                        raise ValueError(f"test must have exactly one initial-state marker: {nodeid}")
                    nodes[nodeid] = {
                        "trace_id": marker_ids[0],
                        "initial_state": {
                            "baseline_green": "BASELINE_GREEN",
                            "red_expected": "RED_EXPECTED",
                            "external_blocked": "EXTERNAL_BLOCKED",
                        }[states[0]],
                        "name": node.name,
                    }
                self.generic_visit(node)

        Visitor().visit(tree)
    return nodes


def collect_test_nodes(root: Path) -> dict[str, str]:
    return {
        nodeid: metadata["trace_id"]
        for nodeid, metadata in collect_test_metadata(root).items()
    }


def collect_javascript_metadata(root: Path) -> dict[str, dict[str, str]]:
    catalogue = root / "tests-js" / "traceability.json"
    if not catalogue.is_file():
        return {}
    value = json.loads(catalogue.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("JavaScript traceability catalogue root must be a list")

    nodes: dict[str, dict[str, str]] = {}
    for index, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise ValueError(f"JavaScript catalogue entry {index} must be an object")
        keys = set(entry)
        if keys != JS_CATALOG_KEYS:
            raise ValueError(
                f"JavaScript catalogue entry {index} has invalid keys: "
                f"missing={sorted(JS_CATALOG_KEYS - keys)}, extra={sorted(keys - JS_CATALOG_KEYS)}"
            )
        trace_id = entry["id"]
        state = entry["initial_state"]
        requirement = entry["requirement"]
        source_symbols = entry["source_symbols"]
        test_paths = entry["test_paths"]
        if not isinstance(trace_id, str) or not TRACE_ID_RE.fullmatch(trace_id):
            raise ValueError(f"invalid JavaScript trace id at entry {index}: {trace_id!r}")
        if state not in INITIAL_STATES:
            raise ValueError(f"invalid JavaScript initial state for {trace_id}: {state!r}")
        if not isinstance(requirement, str) or not requirement.strip():
            raise ValueError(f"empty JavaScript requirement for {trace_id}")
        if not (
            isinstance(source_symbols, list)
            and source_symbols
            and all(isinstance(item, str) and item.strip() for item in source_symbols)
        ):
            raise ValueError(f"invalid JavaScript source_symbols for {trace_id}")
        if not (
            isinstance(test_paths, list)
            and test_paths
            and all(isinstance(item, str) and item.strip() for item in test_paths)
        ):
            raise ValueError(f"invalid JavaScript test_paths for {trace_id}")

        prefix = f"[{trace_id}] "
        for nodeid in test_paths:
            if not nodeid.startswith("tests-js/") or "::" not in nodeid:
                raise ValueError(f"invalid JavaScript test node for {trace_id}: {nodeid}")
            title = nodeid.rsplit("::", 1)[1]
            if not title.startswith(prefix):
                raise ValueError(
                    f"JavaScript test title does not match trace id {trace_id}: {nodeid}"
                )
            if nodeid in nodes:
                raise ValueError(f"duplicate JavaScript test node: {nodeid}")
            nodes[nodeid] = {
                "trace_id": trace_id,
                "initial_state": state,
                "name": title[len(prefix) :],
            }
    return nodes


def base_test_nodeid(nodeid: str) -> str:
    if nodeid.startswith("tests/"):
        return nodeid.split("[", 1)[0]
    return nodeid


def validate(root: Path, manifest_path: Path, schema_path: Path) -> list[str]:
    errors: list[str] = []
    manifest = load_yaml(manifest_path)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    for error in sorted(validator.iter_errors(manifest), key=lambda item: list(item.absolute_path)):
        errors.append(f"schema:{'/'.join(map(str, error.absolute_path))}: {error.message}")

    requirements = manifest.get("requirements", [])
    ids = [item.get("id", "") for item in requirements if isinstance(item, dict)]
    for requirement_id, count in Counter(ids).items():
        if count > 1:
            errors.append(f"duplicate id: {requirement_id}")
        if RANGE_RE.search(requirement_id):
            errors.append(f"range/wildcard id is forbidden: {requirement_id}")

    serialized = yaml.safe_dump(manifest, allow_unicode=True)
    if SECRET_RE.search(serialized):
        errors.append("manifest contains a secret-like value")
    if "/home/openclaw" in serialized:
        errors.append("manifest references the frozen source home")

    try:
        test_metadata = collect_test_metadata(root)
        javascript_metadata = collect_javascript_metadata(root)
        overlap = set(test_metadata) & set(javascript_metadata)
        if overlap:
            raise ValueError(f"duplicate cross-runtime test nodes: {sorted(overlap)}")
        all_metadata = {**test_metadata, **javascript_metadata}
        test_nodes = {nodeid: item["trace_id"] for nodeid, item in all_metadata.items()}
    except (json.JSONDecodeError, SyntaxError, ValueError) as exc:
        errors.append(f"test discovery: {exc}")
        all_metadata = {}
        test_nodes = {}

    manifest_nodes: dict[str, str] = {}
    for item in requirements:
        if not isinstance(item, dict):
            continue
        requirement_id = item.get("id", "")
        expected_red = item.get("expected_red")
        if isinstance(expected_red, dict) and expected_red.get("code") != requirement_id:
            errors.append(f"expected_red code differs from id: {requirement_id}")
        for nodeid in item.get("test_paths", []):
            if nodeid in manifest_nodes and manifest_nodes[nodeid] != requirement_id:
                errors.append(f"test node belongs to multiple requirements: {nodeid}")
            manifest_nodes[nodeid] = requirement_id

    manifest_base_nodes = {
        base_test_nodeid(nodeid): requirement_id
        for nodeid, requirement_id in manifest_nodes.items()
    }
    for nodeid, requirement_id in test_nodes.items():
        if manifest_base_nodes.get(nodeid) != requirement_id:
            errors.append(f"orphan/mismatched test: {nodeid} -> {requirement_id}")
    for nodeid, requirement_id in manifest_nodes.items():
        base_nodeid = base_test_nodeid(nodeid)
        if base_nodeid not in test_nodes:
            errors.append(f"manifest test node not collected: {nodeid} ({requirement_id})")
        elif test_nodes[base_nodeid] != requirement_id:
            errors.append(
                f"manifest/test trace mismatch: {nodeid} ({requirement_id} != {test_nodes[base_nodeid]})"
            )

    manifest_states = {
        item.get("id", ""): item.get("initial_state")
        for item in requirements
        if isinstance(item, dict)
    }
    for nodeid, metadata in all_metadata.items():
        trace_id = metadata["trace_id"]
        if manifest_states.get(trace_id) != metadata["initial_state"]:
            errors.append(
                f"manifest/test initial-state mismatch: {nodeid} "
                f"({manifest_states.get(trace_id)} != {metadata['initial_state']})"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, default=Path(".testplan/traceability.yml"))
    parser.add_argument(
        "--schema", type=Path, default=Path(".testplan/schemas/traceability.schema.json")
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    errors = validate(root, root / args.manifest, root / args.schema)
    if args.json:
        print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    else:
        for error in errors:
            print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
