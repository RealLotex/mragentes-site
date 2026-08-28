from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


def run(command: list[str], *, cwd: Path) -> int:
    return subprocess.run(command, cwd=cwd, check=False, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}).returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    report = args.report_dir.resolve()
    report.mkdir(parents=True, exist_ok=True)
    python_rc = run(
        [str(root / ".venv/bin/python"), "-m", "pytest", "-m", "not operational", f"--junitxml={report / 'python.xml'}"],
        cwd=root,
    )
    if python_rc not in {0, 1}:
        return 2
    javascript_rc = run(["npm", "run", "test:js", "--", "--reporter=json", f"--outputFile={report / 'javascript.json'}"], cwd=root)
    if javascript_rc not in {0, 1}:
        return 3
    return 1 if python_rc or javascript_rc else 0


if __name__ == "__main__":
    raise SystemExit(main())
