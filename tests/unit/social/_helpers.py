from __future__ import annotations

import datetime as dt
import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageFont

from scripts.social.config import Settings
from scripts.social.notas import Nota
from scripts.social.templates import Piece


FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
DEJAVU = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def make_nota(tmp_path: Path, **overrides: Any) -> Nota:
    values: dict[str, Any] = {
        "path": tmp_path / "2026-08-26-automatizacion-util.md",
        "title": "Automatización útil para pymes",
        "date": dt.date(2026, 8, 26),
        "description": "Una guía concreta para automatizar sin perder el control humano.",
        "image": "",
        "image_alt": "Una hoja con un proceso de automatización",
        "tags": ["automatización", "pymes"],
        "body": (
            "Este párrafo suficientemente largo explica una automatización útil y medible.\n\n"
            "## Decisiones importantes\n\n"
            "- Definir una persona responsable de revisar cada excepción operativa.\n"
            "- Medir resultados antes de ampliar la automatización a todo el equipo.\n\n"
            "El equipo redujo 42% del tiempo operativo, sin perder revisión humana.\n\n"
            "> Una automatización responsable tiene que poder explicarse y recuperarse.\n"
        ),
    }
    values.update(overrides)
    return Nota(**values)


def rich_piece() -> Piece:
    return Piece(
        title="Automatizar con criterio, evidencia y una salida segura",
        kicker="guía práctica",
        lead="Una idea concreta para mejorar un proceso sin perder el control humano.",
        items=[
            ("Definir el problema", "Acordar qué resultado se espera."),
            ("Probar en pequeño", "Medir antes de ampliar."),
            ("Revisar", "Conservar una salida manual."),
        ],
        rows=[
            ("objetivo", "reducir tareas repetitivas"),
            ("control", "revisión humana"),
            ("salida", "recuperación documentada"),
        ],
        stat="42%",
        unit="menos",
        caption="Tiempo operativo evitado en una prueba controlada",
        quote="Una automatización responsable tiene que poder explicarse y recuperarse.",
        author="Equipo MR Agentes",
        tags=["automatización", "pymes", "datos"],
        cta="Leé la guía completa en el sitio",
        meta="26.08.2026",
        section="prueba",
        footer_right="mragentes.com.ar",
    )


@functools.lru_cache(maxsize=512)
def fast_font(role: str = "display", size: int = 48, weight: int = 400, width: int = 100):
    del role, weight, width
    return ImageFont.truetype(str(DEJAVU), max(6, int(size)))


def install_fast_render(monkeypatch) -> None:
    from scripts.social import brand, canvas

    monkeypatch.setattr(brand, "font", fast_font)
    monkeypatch.setattr(brand, "sanitize", lambda value, role="display": value or "")
    monkeypatch.setattr(
        brand,
        "hand",
        lambda size, ink=brand.INK, paper=brand.BONE: Image.new(
            "RGBA", (max(1, int(size)), max(1, int(size))), (*ink, 255)
        ),
    )
    monkeypatch.setattr(canvas, "grain", lambda image, amount=7, seed=0: image.copy())


def configured_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "access_token": "test-token-never-sent",
        "fb_page_id": "123456",
        "ig_user_id": "654321",
        "graph_version": "v21.0",
        "enabled": True,
        "dry_run": False,
        "site_base_url": "https://mragentes.example",
        "image_base": "https://cdn.mragentes.example/social",
        "repository": "example/mragentes-site",
        "branch": "main",
    }
    values.update(overrides)
    return Settings(**values)


@dataclass
class StubResponse:
    status_code: int = 200
    body: Any = field(default_factory=dict)
    text: str = ""
    json_error: Exception | None = None

    def json(self) -> Any:
        if self.json_error is not None:
            raise self.json_error
        return self.body


@dataclass
class StubRequests:
    post_responses: list[Any] = field(default_factory=list)
    get_responses: list[Any] = field(default_factory=list)
    head_responses: list[Any] = field(default_factory=list)
    post_calls: list[dict[str, Any]] = field(default_factory=list)
    get_calls: list[dict[str, Any]] = field(default_factory=list)
    head_calls: list[dict[str, Any]] = field(default_factory=list)

    @staticmethod
    def _next(queue: list[Any]) -> Any:
        if not queue:
            raise AssertionError("stub request queue exhausted")
        value = queue.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value

    def post(self, url: str, **kwargs: Any) -> StubResponse:
        self.post_calls.append({"url": url, **kwargs})
        return self._next(self.post_responses)

    def get(self, url: str, **kwargs: Any) -> StubResponse:
        self.get_calls.append({"url": url, **kwargs})
        return self._next(self.get_responses)

    def head(self, url: str, **kwargs: Any) -> StubResponse:
        self.head_calls.append({"url": url, **kwargs})
        return self._next(self.head_responses)


class DrawRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def _record(self, name: str, *args: Any, **kwargs: Any) -> None:
        self.calls.append((name, args, kwargs))

    def rectangle(self, *args: Any, **kwargs: Any) -> None:
        self._record("rectangle", *args, **kwargs)

    def line(self, *args: Any, **kwargs: Any) -> None:
        self._record("line", *args, **kwargs)

    def ellipse(self, *args: Any, **kwargs: Any) -> None:
        self._record("ellipse", *args, **kwargs)

    def text(self, *args: Any, **kwargs: Any) -> None:
        self._record("text", *args, **kwargs)
