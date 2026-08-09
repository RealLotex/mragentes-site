"""
Configuración del social manager.

Todo lo sensible sale del entorno o de un archivo `.env` en la raíz del repo
(que está en .gitignore y nunca se commitea). Nada de tokens en el código:
si mañana este repo se hace público, no hay nada que rotar.

Variables (ver .env.example):
  META_ACCESS_TOKEN   token de página de larga duración (sirve para FB e IG)
  FB_PAGE_ID          id numérico de la página de Facebook
  IG_USER_ID          id de la cuenta profesional de Instagram vinculada
  META_GRAPH_VERSION  versión de la Graph API (default v21.0)
  SOCIAL_ENABLED      1/0 — apagar la publicación sin desinstalar nada
  SOCIAL_DRY_RUN      1/0 — renderizar y mostrar, sin llamar a la API
  SOCIAL_IMAGE_BASE   base pública desde donde Meta descarga las imágenes
  SITE_BASE_URL       https://mragentes.com.ar
  GITHUB_REPOSITORY   owner/repo (lo setea Actions solo)
  SOCIAL_GIT_BRANCH   rama desde la que se sirven las imágenes crudas
"""

from __future__ import annotations

import os
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = BASE_DIR / "scripts"
SOCIAL_DIR = SCRIPTS_DIR / "social"
CACHE_DIR = SOCIAL_DIR / ".cache"
OUT_DIR = BASE_DIR / "static" / "social"
STOCK_DIR = BASE_DIR / "static" / "images" / "stock"
CONTENT_NOTAS = BASE_DIR / "content" / "notas"
STATE_FILE = SOCIAL_DIR / "state.json"
ENV_FILE = BASE_DIR / ".env"

TRUTHY = {"1", "true", "yes", "on", "sí", "si"}
FALSY = {"0", "false", "no", "off"}


def load_dotenv(path: Path = ENV_FILE, override: bool = False) -> dict[str, str]:
    """Lee un .env sin dependencias externas.

    Soporta `CLAVE=valor`, comillas simples o dobles, comentarios con # y
    líneas `export CLAVE=valor`. Lo que ya está en el entorno gana, salvo
    que se pida override — así el workflow de Actions manda sobre el archivo.
    """
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        else:
            val = val.split(" #")[0].strip()
        if not key:
            continue
        values[key] = val
        if override or key not in os.environ:
            os.environ[key] = val
    return values


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    raw = raw.strip().lower()
    if raw in TRUTHY:
        return True
    if raw in FALSY:
        return False
    return default


@dataclass
class Settings:
    access_token: str = ""
    fb_page_id: str = ""
    ig_user_id: str = ""
    graph_version: str = "v21.0"
    enabled: bool = True
    dry_run: bool = False
    site_base_url: str = "https://mragentes.com.ar"
    image_base: str = ""
    repository: str = "RealLotex/mragentes-site"
    branch: str = "main"
    handle: str = "@mragentes"
    warnings: list[str] = field(default_factory=list)

    # ── Derivados ─────────────────────────────────────────────────────────
    @property
    def graph_root(self) -> str:
        return f"https://graph.facebook.com/{self.graph_version}"

    @property
    def can_post_facebook(self) -> bool:
        return bool(self.access_token and self.fb_page_id)

    @property
    def can_post_instagram(self) -> bool:
        return bool(self.access_token and self.ig_user_id)

    @property
    def can_post(self) -> bool:
        return self.can_post_facebook or self.can_post_instagram

    def public_url_candidates(self, filename: str) -> list[str]:
        """URLs públicas posibles para una imagen ya commiteada.

        Instagram no acepta subida binaria: baja la imagen de una URL. La
        cruda de GitHub está disponible apenas se pushea; la del sitio recién
        cuando termina el deploy de Pages. Se prueban en ese orden.
        """
        # Meta descarga la imagen tal cual: si el nombre trae acentos y no van
        # codificados, la descarga falla y el posteo se cae sin explicación.
        safe = urllib.parse.quote(filename, safe="/")
        urls = []
        if self.image_base:
            urls.append(f"{self.image_base.rstrip('/')}/{safe}")
        if self.repository:
            urls.append(
                "https://raw.githubusercontent.com/"
                f"{self.repository}/{self.branch}/static/social/{safe}"
            )
        urls.append(f"{self.site_base_url.rstrip('/')}/social/{safe}")
        seen, out = set(), []
        for u in urls:
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out


def load_settings(env_file: Path = ENV_FILE) -> Settings:
    load_dotenv(env_file)

    token = (
        os.environ.get("META_ACCESS_TOKEN")
        or os.environ.get("FB_PAGE_TOKEN")
        or os.environ.get("PAGE_ACCESS_TOKEN")
        or ""
    ).strip()

    settings = Settings(
        access_token=token,
        fb_page_id=(os.environ.get("FB_PAGE_ID") or "").strip(),
        ig_user_id=(os.environ.get("IG_USER_ID") or os.environ.get("IG_BUSINESS_ID") or "").strip(),
        graph_version=(os.environ.get("META_GRAPH_VERSION") or "v21.0").strip(),
        enabled=_bool("SOCIAL_ENABLED", True),
        dry_run=_bool("SOCIAL_DRY_RUN", False),
        site_base_url=(os.environ.get("SITE_BASE_URL") or "https://mragentes.com.ar").strip(),
        image_base=(os.environ.get("SOCIAL_IMAGE_BASE") or "").strip(),
        repository=(os.environ.get("GITHUB_REPOSITORY") or "RealLotex/mragentes-site").strip(),
        branch=(os.environ.get("SOCIAL_GIT_BRANCH") or os.environ.get("GITHUB_REF_NAME") or "main").strip(),
        handle=(os.environ.get("SOCIAL_HANDLE") or "@mragentes").strip(),
    )

    if not settings.access_token:
        settings.warnings.append("META_ACCESS_TOKEN vacío — no se puede publicar.")
    if not settings.fb_page_id:
        settings.warnings.append("FB_PAGE_ID vacío — Facebook queda fuera.")
    if not settings.ig_user_id:
        settings.warnings.append("IG_USER_ID vacío — Instagram queda fuera.")

    return settings
