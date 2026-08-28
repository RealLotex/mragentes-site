from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

PYTHON_EXCLUDES = {"tests", "test", "__pycache__", ".venv", ".git", "node_modules", "public"}
TS_EXPORT = re.compile(
    r"(?:^|\n)\s*export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var)\s+([A-Za-z_$][\w$]*)",
    re.MULTILINE,
)


class PythonSymbolVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.symbols: list[str] = []

    def _visit_named(self, node: ast.AST, name: str) -> None:
        qualified = ".".join([*self.stack, name])
        self.symbols.append(qualified)
        self.stack.append(name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_named(node, node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_named(node, node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_named(node, node.name)


def python_symbols(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    visitor = PythonSymbolVisitor()
    visitor.visit(tree)
    return sorted(set(visitor.symbols))


def typescript_symbols(path: Path) -> list[str]:
    return sorted(set(TS_EXPORT.findall(path.read_text(encoding="utf-8"))))


def collect(root: Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in PYTHON_EXCLUDES for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        if path.suffix == ".py":
            result[relative] = python_symbols(path)
        elif path.suffix in {".ts", ".tsx"}:
            result[relative] = typescript_symbols(path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.dumps(collect(args.root.resolve()), ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
