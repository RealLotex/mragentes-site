"""
Lectura de las notas de Hugo.

El front matter no se toca (lo escriben `publish_daily.py` y `publish_blog.py`
desde hace meses): acá sólo se lee. De cada nota salen el título, la bajada, la
imagen de portada — la misma que ya se usa para las tarjetas de Facebook y
WhatsApp — y algunos materiales para armar el posteo: el primer párrafo, las
citas del cuerpo, los subtítulos y los números que aparecen en el texto.
"""

from __future__ import annotations

import datetime
import re
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

from .config import BASE_DIR, CONTENT_NOTAS

FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value.strip()


def parse_front_matter(text: str) -> tuple[dict, str]:
    """YAML mínimo: claves planas y listas con guion. Es todo lo que usan las notas."""
    m = FRONT_RE.match(text)
    if not m:
        return {}, text
    raw, body = m.group(1), m.group(2)

    data: dict = {}
    current_list: str | None = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.lstrip().startswith("- ") and current_list:
            data[current_list].append(_unquote(line.lstrip()[2:]))
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value == "":
            data[key] = []
            current_list = key
        else:
            data[key] = _unquote(value)
            current_list = None
    return data, body


@dataclass
class Nota:
    path: Path
    title: str
    date: datetime.date
    description: str = ""
    image: str = ""
    image_alt: str = ""
    tags: list = field(default_factory=list)
    body: str = ""

    # ── Identidad ───────────────────────────────────────────────────────
    @property
    def slug(self) -> str:
        """El slug es el nombre del archivo: así arma Hugo el permalink."""
        return self.path.stem

    def url(self, base: str = "https://mragentes.com.ar") -> str:
        return f"{base.rstrip('/')}/notas/{urllib.parse.quote(self.slug)}/"

    @property
    def date_label(self) -> str:
        return self.date.strftime("%d.%m.%Y")

    # ── Imagen ──────────────────────────────────────────────────────────
    @property
    def photo(self) -> Path | None:
        """Ruta local de la imagen de portada declarada en el front matter."""
        if not self.image:
            return None
        rel = self.image.lstrip("/")
        candidate = BASE_DIR / "static" / rel
        return candidate if candidate.exists() else None

    # ── Materia prima para el copy ──────────────────────────────────────
    @property
    def main_body(self) -> str:
        """El cuerpo sin la sección de fuentes.

        Las notas cierran con `## Fuentes` y una lista de enlaces. Es material
        valioso en la web y pésimo en un posteo: si no se corta acá, los
        «tres puntos» del carrusel terminan siendo tres URLs.
        """
        return re.split(r"^##+\s*(?:Fuentes?|Referencias|Enlaces)\s*$", self.body, maxsplit=1, flags=re.M | re.I)[0]

    @property
    def paragraphs(self) -> list[str]:
        out = []
        for chunk in re.split(r"\n\s*\n", self.main_body):
            chunk = chunk.strip()
            if not chunk or chunk.startswith(("#", ">", "-", "*", "|", "!")):
                continue
            chunk = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", chunk)     # links
            chunk = re.sub(r"[*_`]{1,3}", "", chunk)                    # énfasis
            chunk = re.sub(r"\s+", " ", chunk).strip()
            if len(chunk) > 60:
                out.append(chunk)
        return out

    @property
    def lead(self) -> str:
        return self.description or (self.paragraphs[0] if self.paragraphs else "")

    @property
    def headings(self) -> list[str]:
        return [re.sub(r"[*_`]", "", h).strip() for h in re.findall(r"^##\s+(.+)$", self.main_body, re.M)]

    @property
    def quotes(self) -> list[str]:
        """Citas del cuerpo: las líneas con `>` y las frases entre comillas."""
        found = [re.sub(r"[*_`]", "", q).strip() for q in re.findall(r"^>\s+(.+)$", self.main_body, re.M)]
        for q in re.findall(r"[“\"]([^”\"]{60,240})[”\"]", self.main_body):
            found.append(re.sub(r"\s+", " ", q).strip())
        seen, out = set(), []
        for q in found:
            if q and q not in seen:
                seen.add(q)
                out.append(q)
        return out

    @property
    def numbers(self) -> list[tuple[str, str]]:
        """Cifras del texto con su frase, para la plantilla `dato`."""
        out = []
        for sentence in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", self.main_body)):
            m = re.search(r"(\d[\d.,]*\s?(?:%|millones|mil millones|millón|puntos|veces|x))", sentence, re.I)
            if not m:
                continue
            clean = re.sub(r"[*_`>#]", "", sentence).strip()
            clean = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", clean)
            if 40 < len(clean) < 260:
                out.append((m.group(1).strip(), clean))
        return out

    @property
    def bullets(self) -> list[str]:
        out = []
        for line in re.findall(r"^[-*]\s+(.+)$", self.main_body, re.M):
            if "http" in line:
                continue
            line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
            line = re.sub(r"[*_`]", "", line).strip()
            if 12 < len(line) < 200:
                out.append(line)
        return out


def _parse_date(raw, fallback: Path) -> datetime.date:
    if isinstance(raw, str) and raw[:10]:
        try:
            return datetime.date.fromisoformat(raw[:10])
        except ValueError:
            pass
    stem = fallback.stem
    if len(stem) >= 10:
        try:
            return datetime.date.fromisoformat(stem[:10])
        except ValueError:
            pass
    return datetime.date.today()


def load(path: str | Path) -> Nota:
    path = Path(path)
    if not path.is_absolute():
        path = (BASE_DIR / path) if (BASE_DIR / path).exists() else (CONTENT_NOTAS / path)
    data, body = parse_front_matter(path.read_text(encoding="utf-8"))
    tags = data.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.strip("[]").split(",") if t.strip()]
    return Nota(
        path=path,
        title=str(data.get("title", path.stem)),
        date=_parse_date(data.get("date"), path),
        description=str(data.get("description", "")),
        image=str(data.get("image", "")),
        image_alt=str(data.get("image_alt", "")),
        tags=list(tags),
        body=body,
    )


def all_notas() -> list[Nota]:
    out = []
    for p in sorted(CONTENT_NOTAS.glob("*.md")):
        if p.name.startswith("_"):
            continue
        try:
            out.append(load(p))
        except Exception:
            continue
    return sorted(out, key=lambda n: (n.date, n.path.stem))


def latest() -> Nota | None:
    notas = all_notas()
    return notas[-1] if notas else None


def find(needle: str) -> Nota | None:
    """Busca por ruta, por slug exacto o por coincidencia parcial del nombre."""
    p = Path(needle)
    if p.exists() and p.suffix == ".md":
        return load(p)
    for nota in all_notas():
        if nota.slug == needle:
            return nota
    lowered = needle.lower()
    for nota in reversed(all_notas()):
        if lowered in nota.slug.lower() or lowered in nota.title.lower():
            return nota
    return None
