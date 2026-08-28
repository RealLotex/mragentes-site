#!/usr/bin/env python3
"""Auditor local de secretos para el repositorio publico de MR Agentes.

El auditor trabaja exclusivamente sobre el repositorio que contiene este
archivo. No consulta servicios remotos ni directorios externos. Puede revisar
el arbol actual, archivos no versionados y blobs alcanzables del historial.

Codigos de salida:

* 0: no se encontraron secretos ni problemas de higiene;
* 1: se encontraron hallazgos o configuraciones inseguras;
* 2: la auditoria no pudo completarse por un error de infraestructura.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

BASE_DIR = Path(__file__).resolve().parents[1]
MAX_TEXT_BYTES = 2_000_000

Hit = tuple[str, str, str, str]
Pattern = tuple[str, str, re.Pattern[str]]

# Los patrones mas especificos preceden a los genericos para que una misma
# credencial produzca un solo hallazgo util.
PATTERNS: list[Pattern] = [
    (
        "anthropic",
        "Clave de Anthropic",
        re.compile(r"\bsk-ant-[A-Za-z0-9_-]{32,}"),
    ),
    (
        "openai",
        "Clave de OpenAI",
        re.compile(r"\bsk-(?!ant-)[A-Za-z0-9_-]{32,}"),
    ),
    (
        "github-fine-grained",
        "Token fine-grained de GitHub",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}"),
    ),
    (
        "github",
        "Token de GitHub",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}"),
    ),
    (
        "meta-token",
        "Token de Facebook o Instagram",
        re.compile(r"\bEAA[A-Za-z0-9]{40,}"),
    ),
    (
        "ig-token",
        "Token de Instagram",
        re.compile(r"\bIGQ[A-Za-z0-9_-]{40,}"),
    ),
    (
        "google",
        "Clave de Google o Firebase",
        re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b"),
    ),
    (
        "aws",
        "Clave de acceso de AWS",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
    (
        "slack",
        "Token de Slack",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    ),
    (
        "private-key",
        "Clave privada en PEM",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    ),
    (
        "vapid-private",
        "Clave privada VAPID en JSON",
        re.compile(r'"vapidPrivateKey"\s*:\s*"[A-Za-z0-9_-]{20,}"'),
    ),
    (
        "credential-url",
        "Credencial embebida en URL",
        re.compile(
            r"https?://[A-Za-z0-9._~%!$&'()*+,;=-]+"
            r":[A-Za-z0-9._~%!$&'()*+,;=-]{8,}@"
            r"[A-Za-z0-9.-]+(?::[0-9]+)?(?:/|$)",
            re.IGNORECASE,
        ),
    ),
    (
        "assignment",
        "Credencial asignada en texto",
        re.compile(
            r"(?i)\b(?:api[_-]?key|api[_-]?token|access[_-]?token|page[_-]?token|"
            r"client[_-]?secret|password|passwd|secret)\b\s*[:=]\s*[\"'][^\"'\s]{12,}[\"']"
        ),
    ),
]

PLACEHOLDER = re.compile(
    r"(?i)(?:your|tu|sample|dummy|fake|test|example|ejemplo|placeholder|sentinel|synthetic|"
    r"cambiar|reemplazar?)[_-]?(?:api[_-]?)?(?:key|token|secret|password)"
    r"|x{4,}|<[^>]+>|\$\{[^}]+\}"
)
LITERAL_PLACEHOLDER = re.compile(r"\b(?:TOKEN|SECRET|PASSWORD|USERNAME)\b")
SYNTHETIC_MARKER = re.compile(r"(?i)\b(?:sentinel|synthetic)(?:[-_][A-Za-z0-9]+)*\b")
EXAMPLE_CREDENTIAL_URL = re.compile(
    r"^https?://(?:user|username):(?:pass|password)@(?:[A-Za-z0-9-]+\.)*example\.test/",
    re.IGNORECASE,
)
RUNTIME_REFERENCE = re.compile(
    r"(?i)(?:os\.(?:environ|getenv)|process\.env|secrets\.|vars\.|"
    r"config\.(?:get|require)|data\.get|payload\.get)"
)

SKIP_SUFFIXES = {
    ".woff2",
    ".ttf",
    ".otf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".ico",
    ".glb",
    ".pdf",
    ".zip",
    ".gz",
    ".pyc",
}


def _run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    """Ejecuta un comando Git local sin shell y conserva filenames como bytes."""

    return subprocess.run(
        ["git", *args],
        cwd=BASE_DIR,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def _is_allowed(line: str, candidate: str | None = None) -> bool:
    """Acepta solo placeholders inequivocos o referencias al runtime.

    Una palabra como ``example`` en otro lugar de la linea no alcanza para
    ocultar un token con forma real: la excepcion debe estar dentro de la
    coincidencia concreta.
    """

    value = candidate if candidate is not None else line
    return bool(
        PLACEHOLDER.search(value)
        or LITERAL_PLACEHOLDER.search(value)
        or SYNTHETIC_MARKER.search(value)
        or EXAMPLE_CREDENTIAL_URL.search(value)
        or RUNTIME_REFERENCE.search(value)
    )


def _overlaps(span: tuple[int, int], used: list[tuple[int, int]]) -> bool:
    return any(span[0] < other[1] and other[0] < span[1] for other in used)


def scan_text(text: str, origin: str) -> list[Hit]:
    """Busca secretos de alta confianza y nunca devuelve el valor encontrado."""

    hits: list[Hit] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        used_spans: list[tuple[int, int]] = []
        for key, why, rx in PATTERNS:
            for match in rx.finditer(line):
                if key == "private-key" and "END PRIVATE KEY" in line:
                    continue
                if _overlaps(match.span(), used_spans) or _is_allowed(line, match.group(0)):
                    continue
                used_spans.append(match.span())
                hits.append(
                    (
                        origin,
                        str(lineno),
                        key,
                        f"{why}: [REDACTED; {len(match.group(0))} chars]",
                    )
                )
    return hits


def _decode_paths(raw: bytes) -> list[str]:
    return [os.fsdecode(item) for item in raw.split(b"\0") if item]


def tracked_files() -> list[Path]:
    """Lista archivos del indice con protocolo NUL, sin materializarlos."""

    return [BASE_DIR / name for name in _decode_paths(_run_git("ls-files", "-z").stdout)]


def working_files(include_untracked: bool) -> list[Path]:
    """Lista determinista del indice y, opcionalmente, archivos no ignorados."""

    paths = tracked_files()
    if include_untracked:
        paths.extend(
            BASE_DIR / name
            for name in _decode_paths(
                _run_git("ls-files", "-z", "--others", "--exclude-standard").stdout
            )
        )
    return list(dict.fromkeys(paths))


def _relative_name(path: Path) -> str | None:
    try:
        return path.relative_to(BASE_DIR).as_posix()
    except ValueError:
        return None


def _index_blob(relative_name: str) -> bytes | None:
    result = _run_git("show", f":{relative_name}", check=False)
    return result.stdout if result.returncode == 0 else None


def _file_bytes(path: Path, *, tracked: bool) -> bytes | None:
    """Lee sin seguir symlinks; usa el indice ante ENAMETOOLONG o path ausente."""

    relative_name = _relative_name(path)
    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            return _index_blob(relative_name) if tracked and relative_name else None
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_TEXT_BYTES:
            return None
        return path.read_bytes()
    except OSError:
        if tracked and relative_name:
            return _index_blob(relative_name)
        return None


def scan_working(include_untracked: bool) -> list[Hit]:
    """Escanea el arbol local; binarios y archivos demasiado grandes se omiten."""

    indexed = tracked_files()
    indexed_names = {_relative_name(path) for path in indexed}
    files = indexed if not include_untracked else working_files(True)
    hits: list[Hit] = []
    for path in files:
        relative_name = _relative_name(path)
        if relative_name is None or path.suffix.lower() in SKIP_SUFFIXES:
            continue
        raw = _file_bytes(path, tracked=relative_name in indexed_names)
        if raw is None or len(raw) > MAX_TEXT_BYTES or b"\0" in raw:
            continue
        text = raw.decode("utf-8", errors="ignore")
        hits.extend(scan_text(text, relative_name))
    return hits


def scan_history() -> list[Hit]:
    """Escanea una vez cada blob alcanzable del historial Git local."""

    listing = _run_git("rev-list", "--objects", "--all").stdout.decode(
        "utf-8", errors="surrogateescape"
    )
    hits: list[Hit] = []
    seen: set[str] = set()
    for line in listing.splitlines():
        sha, separator, name = line.partition(" ")
        if not separator or not name or sha in seen:
            continue
        seen.add(sha)
        if Path(name).suffix.lower() in SKIP_SUFFIXES:
            continue
        object_type = _run_git("cat-file", "-t", sha, check=False)
        if object_type.returncode != 0 or object_type.stdout.strip() != b"blob":
            continue
        blob = _run_git("cat-file", "-p", sha, check=False)
        if (
            blob.returncode != 0
            or len(blob.stdout) > MAX_TEXT_BYTES
            or b"\0" in blob.stdout
        ):
            continue
        text = blob.stdout.decode("utf-8", errors="ignore")
        hits.extend(scan_text(text, f"{name} @ {sha[:8]}"))
    return hits


def _sensitive_tracked_path(name: str) -> bool:
    path = Path(name)
    basename = path.name.lower()
    if basename in {".env.example", ".env.sample"}:
        return False
    return (
        basename == ".env"
        or basename.startswith(".env.")
        or basename == "config.local.json"
        or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}
    )


def _ignore_covers(name: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", "--", name],
        cwd=BASE_DIR,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _url_has_credentials(url: str) -> bool:
    if any(rx.search(url) for _, _, rx in PATTERNS):
        return True
    try:
        parsed = urlsplit(url)
    except ValueError:
        return True
    return parsed.scheme.lower() in {"http", "https"} and parsed.username is not None


def _remote_hygiene() -> list[str]:
    problems: list[str] = []
    remotes = _run_git("remote", check=False)
    if remotes.returncode != 0:
        return ["No se pudo auditar la configuracion local de remotes"]
    for remote in remotes.stdout.decode("utf-8", errors="replace").splitlines():
        if not remote:
            continue
        urls: list[str] = []
        for extra in ((), ("--push",)):
            result = _run_git("remote", "get-url", "--all", *extra, remote, check=False)
            if result.returncode == 0:
                urls.extend(result.stdout.decode("utf-8", errors="replace").splitlines())
        if any(_url_has_credentials(url) for url in urls):
            problems.append(f"El remote {remote!r} contiene credenciales embebidas")

    headers = _run_git(
        "config", "--local", "--get-regexp", r"^http\..*\.extraheader$", check=False
    )
    if headers.returncode == 0 and headers.stdout.strip():
        problems.append("La configuracion Git local contiene un HTTP extraheader sensible")
    return problems


def check_hygiene() -> list[str]:
    """Comprueba archivos sensibles, ignores y credenciales locales de Git."""

    problems: list[str] = []
    for path in tracked_files():
        relative_name = _relative_name(path)
        if relative_name and _sensitive_tracked_path(relative_name):
            problems.append(f"Archivo sensible versionado: {relative_name}")

    for required in (".env", "config.local.json", "private.pem", "private.key"):
        if not _ignore_covers(required):
            problems.append(f".gitignore no cubre {required!r}")

    problems.extend(_remote_hygiene())
    return problems


def _safe_output(value: str) -> str:
    """Elimina controles, credenciales y tokens antes de escribir un diagnostico."""

    safe = "".join(char if char.isprintable() else "?" for char in value)
    for _, _, regex in PATTERNS:
        safe = regex.sub("[REDACTED]", safe)
    return safe[:500]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Buscar credenciales filtradas")
    parser.add_argument(
        "--history", action="store_true", help="revisar todos los blobs alcanzables"
    )
    parser.add_argument(
        "--all", action="store_true", help="incluir historial y archivos no versionados"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        include_untracked = args.all
        files = working_files(include_untracked)
        print("-- Arbol de trabajo --")
        hits = scan_working(include_untracked)
        print(f"  {len(files)} archivos candidatos")

        if args.history or args.all:
            print("-- Historial local --")
            history_hits = scan_history()
            print(f"  {len(history_hits)} hallazgos en blobs historicos")
            hits.extend(history_hits)

        print("-- Higiene local --")
        problems = check_hygiene()
        if problems:
            for problem in problems:
                print(f"  ! {_safe_output(problem)}")
        else:
            print("  OK: ignores y configuracion Git local auditados")

        print("-- Resultado --")
        if not hits:
            print("  OK: sin credenciales de alta confianza")
            return 1 if problems else 0

        for origin, lineno, key, detail in hits:
            print(
                f"  X {_safe_output(origin)}:{lineno} [{key}] "
                f"{_safe_output(detail)}"
            )
        print(f"  {len(hits)} hallazgos; rotar cualquier credencial real antes de limpiar")
        return 1
    except (OSError, subprocess.SubprocessError, UnicodeError):
        print("ERROR: la auditoria local no pudo completarse", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
