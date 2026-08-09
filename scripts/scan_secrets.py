#!/usr/bin/env python3
"""
Buscador de secretos filtrados.

Revisa el árbol de trabajo y, si se le pide, todo el historial de git — porque
un token borrado en el último commit sigue estando en el anterior, y con el
repositorio público eso es lo mismo que no haberlo borrado nunca.

  python3 scripts/scan_secrets.py             # archivos versionados de ahora
  python3 scripts/scan_secrets.py --history   # además, todos los commits
  python3 scripts/scan_secrets.py --all       # además, lo no versionado

Sale con código 1 si encuentra algo, para poder colgarlo de un hook o de CI.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

# Cada patrón lleva por qué está: sin eso, en seis meses nadie sabe si el
# hallazgo es un token de verdad o el ejemplo de la documentación.
PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("meta-token", "Token de Facebook / Instagram (empieza con EAA)",
     re.compile(r"\bEAA[A-Za-z0-9]{40,}")),
    ("ig-token", "Token de Instagram (IGQ…)",
     re.compile(r"\bIGQ[A-Za-z0-9_\-]{40,}")),
    ("openai", "Clave de OpenAI",
     re.compile(r"\bsk-[A-Za-z0-9_\-]{32,}")),
    ("anthropic", "Clave de Anthropic",
     re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{32,}")),
    ("google", "Clave de Google / Firebase",
     re.compile(r"\bAIza[A-Za-z0-9_\-]{35}")),
    ("github", "Token de GitHub",
     re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}")),
    ("aws", "Clave de acceso de AWS",
     re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("slack", "Token de Slack",
     re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("private-key", "Clave privada en PEM",
     re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("vapid-private", "Clave privada VAPID en JSON",
     re.compile(r"\"vapidPrivateKey\"\s*:\s*\"[A-Za-z0-9_\-]{20,}\"")),
    ("asignacion", "Credencial asignada en el código",
     re.compile(
         r"(?i)\b(?:api[_-]?key|api[_-]?token|access[_-]?token|page[_-]?token|"
         r"client[_-]?secret|password|passwd|secret)\b\s*[:=]\s*[\"'][^\"'\s]{12,}[\"']"
     )),
]

# Lo que parece secreto y no lo es. Sin esta lista el informe es ruido puro.
ALLOWLIST = [
    re.compile(r"(?i)os\.environ|getenv|process\.env|secrets\.|vars\.|\$\{\{"),
    re.compile(r"(?i)(config|data|payload|body|entry|item|opts?)\.get\("),
    re.compile(r"(?i)(tu[_-]?token|your[_-]?token|xxx+|<[^>]+>|placeholder|ejemplo|example|cambiar|reemplaz)"),
    re.compile(r"(?i)\"(api_?key|api_?token|access_?token|password|secret)\"\s*:\s*\"\""),
]

SKIP_SUFFIXES = {".woff2", ".ttf", ".otf", ".png", ".jpg", ".jpeg", ".webp",
                 ".ico", ".glb", ".pdf", ".zip", ".gz", ".pyc"}


def _is_allowed(line: str) -> bool:
    return any(rx.search(line) for rx in ALLOWLIST)


def scan_text(text: str, origin: str) -> list[tuple[str, str, str, str]]:
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if len(line) > 4000 or _is_allowed(line):
            continue
        for key, why, rx in PATTERNS:
            m = rx.search(line)
            if not m:
                continue
            shown = m.group(0)
            if len(shown) > 24:
                shown = shown[:12] + "…" + shown[-6:]
            hits.append((origin, f"{lineno}", key, f"{why}: {shown}"))
    return hits


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=BASE_DIR,
                         capture_output=True, text=True, check=True).stdout
    return [BASE_DIR / p for p in out.split("\0") if p]


def working_files(include_untracked: bool) -> list[Path]:
    files = tracked_files()
    if include_untracked:
        out = subprocess.run(["git", "ls-files", "-z", "--others", "--exclude-standard"],
                             cwd=BASE_DIR, capture_output=True, text=True, check=True).stdout
        files += [BASE_DIR / p for p in out.split("\0") if p]
    return files


def scan_working(include_untracked: bool) -> list[tuple[str, str, str, str]]:
    hits = []
    for path in working_files(include_untracked):
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        hits += scan_text(text, str(path.relative_to(BASE_DIR)))
    return hits


def scan_history() -> list[tuple[str, str, str, str]]:
    """Todos los blobs alcanzables, no sólo los del último commit."""
    listing = subprocess.run(["git", "rev-list", "--objects", "--all"], cwd=BASE_DIR,
                             capture_output=True, text=True, check=True).stdout
    hits = []
    seen = set()
    for line in listing.splitlines():
        sha, _, name = line.partition(" ")
        if not name or sha in seen:
            continue
        seen.add(sha)
        if Path(name).suffix.lower() in SKIP_SUFFIXES:
            continue
        blob = subprocess.run(["git", "cat-file", "-p", sha], cwd=BASE_DIR,
                              capture_output=True, check=False)
        if blob.returncode:
            continue
        text = blob.stdout.decode("utf-8", errors="ignore")
        if len(text) > 2_000_000:
            continue
        hits += scan_text(text, f"{name} @ {sha[:8]}")
    return hits


def check_hygiene() -> list[str]:
    problems = []
    tracked = subprocess.run(["git", "ls-files", "--", ".env", "*.env", "**/.env"],
                             cwd=BASE_DIR, capture_output=True, text=True, check=False).stdout.strip()
    for name in tracked.splitlines():
        if name and name != ".env.example":
            problems.append(f"{name} está versionado — sacalo con: git rm --cached {name}")

    gitignore = (BASE_DIR / ".gitignore")
    text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    for needed in (".env", "config.local.json"):
        if needed not in text:
            problems.append(f".gitignore no cubre «{needed}»")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="Buscar credenciales filtradas")
    ap.add_argument("--history", action="store_true", help="revisar todo el historial de git")
    ap.add_argument("--all", action="store_true", help="historial + archivos sin versionar")
    args = ap.parse_args()

    include_untracked = args.all
    print("── Árbol de trabajo ─────────────────────────────────────────")
    hits = scan_working(include_untracked)
    print(f"  {len(working_files(include_untracked))} archivos revisados")

    if args.history or args.all:
        print("\n── Historial completo ───────────────────────────────────────")
        history_hits = scan_history()
        print(f"  {len(history_hits)} coincidencias en objetos históricos")
        hits += history_hits

    print("\n── Higiene ──────────────────────────────────────────────────")
    problems = check_hygiene()
    if problems:
        for p in problems:
            print(f"  ⚠️  {p}")
    else:
        print("  ✔ .env fuera del control de versiones y cubierto por .gitignore")

    print("\n── Resultado ────────────────────────────────────────────────")
    if not hits:
        print("  ✔ Sin credenciales a la vista.")
        return 1 if problems else 0

    for origin, lineno, key, detail in hits:
        print(f"  ✖ {origin}:{lineno} [{key}] {detail}")
    print(f"\n  {len(hits)} hallazgos. Si alguno es real: rotá la credencial primero,")
    print("  después limpiá el historial. Rotar es lo urgente; borrar, lo prolijo.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
