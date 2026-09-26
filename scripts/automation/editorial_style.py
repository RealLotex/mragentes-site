"""Small, objective gates for a sourced MR Agentes news story."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from pathlib import Path

_WEEKLY_FORMULAS = (
    r"\bla semana\b",
    r"\besta semana\b",
    r"\ben esta semana\b",
    r"\bsemana en que\b",
)
_COLLOQUIAL_FORMS = (
    r"\bhumo\b",
    r"\bsin vueltas\b",
    r"\bvos\b",
    r"\bquer[eé]s\b",
    r"\bpod[eé]s\b",
    r"\bten[eé]s\b",
    r"\bdefin[ií]\b",
    r"\beleg[ií]\b",
    r"\bpon[eé]\b",
    r"\bguard[aá]\b",
    r"\bdejá\b",
    r"\bhac[eé]\b",
    r"\brevis[aá]\b",
    r"\bescribinos\b",
    r"\bcharlamos\b",
)
_FORBIDDEN = tuple(("fórmula semanal", pattern) for pattern in _WEEKLY_FORMULAS) + tuple(
    ("expresión coloquial", pattern) for pattern in _COLLOQUIAL_FORMS
)
_NEWS_BOILERPLATE = (
    r"en este art[ií]culo (?:exploraremos|analizaremos|veremos)",
    r"marca un momento (?:crucial|pivotal)",
    r"refleja el panorama cambiante",
    r"\b(?:los )?expertos sostienen\b",
    r"\bobservadores se[nñ]alan\b",
    r"\bdiversos estudios indican\b",
    r"\b(?:en )?conclusi[oó]n\b",
    r"\btendencias m[aá]s amplias\b",
    r"\bno s[oó]lo .{1,90} sino (?:tambi[eé]n )?\b",
)
_ANALYTIC_MARKERS = (
    "análisis",
    "evidencia",
    "datos",
    "implica",
    "riesgo",
    "impacto",
    "gobernanza",
    "arquitectura",
    "compar",
)


def validate_formal_text(value: str, *, field: str = "texto") -> str:
    """Reject the small set of repeatable editorial regressions we can prove."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    folded = value.casefold()
    for category, pattern in _FORBIDDEN:
        if re.search(pattern, folded, re.IGNORECASE):
            raise ValueError(f"{field} contains a forbidden {category}")
    for pattern in _NEWS_BOILERPLATE:
        if re.search(pattern, folded, re.IGNORECASE):
            raise ValueError(f"{field} contains editorial boilerplate")
    return value


def _body(markdown: str) -> str:
    if markdown.startswith("---"):
        closing = markdown.find("\n---", 3)
        if closing >= 0:
            return markdown[closing + 4 :]
    return markdown


def inspect_note(markdown: str) -> dict[str, int]:
    """Return the measurable characteristics of a technical article."""

    if not isinstance(markdown, str):
        raise TypeError("markdown must be text")
    body = _body(markdown)
    words = re.findall(r"\b[\wáéíóúüñ]+\b", body.casefold())
    return {
        "words": len(words),
        "sections": len(re.findall(r"(?m)^##\s+\S", body)),
        "sources": len(re.findall(r"https://[^\s)]+", body)),
        "analytic_markers": sum(marker in body.casefold() for marker in _ANALYTIC_MARKERS),
        "faq_questions": len(
            re.findall(r"(?mi)^###\s+.+\?\s*$", body.split("## Preguntas frecuentes", 1)[-1])
            if re.search(r"(?mi)^##\s+Preguntas frecuentes\s*$", body)
            else []
        ),
    }


def validate_academic_note(markdown: str) -> dict[str, int]:
    """Require a readable, sourced news report without a mandatory essay template."""

    validate_formal_text(markdown, field="nota")
    report = inspect_note(markdown)
    if report["words"] < 350:
        raise ValueError("nota must contain at least 350 words of reported facts")
    if report["sources"] < 1:
        raise ValueError("nota must cite at least one public source")
    if report["sections"] > 4:
        raise ValueError("nota has too many sections for a focused news report")
    if re.search(r"(?mi)^##\s+(?:Preguntas frecuentes|Conclusi[oó]n)\s*$", _body(markdown)):
        raise ValueError("nota contains a generic closing section")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--note", type=Path, required=True)
    args = parser.parse_args(argv)
    report = validate_academic_note(args.note.read_text(encoding="utf-8"))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
