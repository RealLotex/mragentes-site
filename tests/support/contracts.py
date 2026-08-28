from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TRACE_ID_RE = re.compile(r"^[A-Z][A-Z0-9-]+-[0-9]{3}$")


def trace_message(trace_id: str, message: str) -> str:
    if not TRACE_ID_RE.fullmatch(trace_id):
        raise ValueError(f"invalid trace id: {trace_id!r}")
    return f"[{trace_id}] {message}"


def repository_path(relative_path: str) -> Path:
    candidate = (ROOT / relative_path).resolve(strict=False)
    try:
        candidate.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"repository path escapes root: {relative_path!r}") from exc
    return candidate


def require_target(relative_path: str, trace_id: str) -> Path:
    target = repository_path(relative_path)
    assert target.is_file(), trace_message(
        trace_id, f"planned production target is absent: {relative_path}"
    )
    return target


def require_directory(relative_path: str, trace_id: str) -> Path:
    target = repository_path(relative_path)
    assert target.is_dir(), trace_message(
        trace_id, f"planned production directory is absent: {relative_path}"
    )
    return target


def load_python_target(relative_path: str, trace_id: str) -> ModuleType:
    target = require_target(relative_path, trace_id)
    module_name = "_mra_contract_" + re.sub(r"[^a-zA-Z0-9_]", "_", relative_path)
    spec = importlib.util.spec_from_file_location(module_name, target)
    assert spec and spec.loader, trace_message(trace_id, f"cannot create import spec: {relative_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # converted to a classified contract failure
        raise AssertionError(
            trace_message(trace_id, f"target import failed: {relative_path}: {type(exc).__name__}")
        ) from None
    return module


def require_symbol(module: ModuleType, dotted_name: str, trace_id: str) -> Any:
    value: Any = module
    for part in dotted_name.split("."):
        assert hasattr(value, part), trace_message(trace_id, f"missing symbol: {dotted_name}")
        value = getattr(value, part)
    return value


def require_python_symbol(relative_path: str, dotted_name: str, trace_id: str) -> Any:
    return require_symbol(load_python_target(relative_path, trace_id), dotted_name, trace_id)


def assert_source_absent(relative_path: str, patterns: list[str], trace_id: str) -> None:
    source = require_target(relative_path, trace_id).read_text(encoding="utf-8")
    found = [pattern for pattern in patterns if re.search(pattern, source, flags=re.MULTILINE)]
    assert not found, trace_message(trace_id, f"forbidden legacy patterns remain: {found}")
