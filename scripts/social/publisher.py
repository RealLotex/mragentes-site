"""
Publicación en Facebook e Instagram (Graph API).

Las dos redes no se publican igual y conviene tenerlo claro:

  · **Facebook** acepta el archivo por multipart (`source`). No hace falta que
    la imagen esté en ningún lado: se sube y listo.

  · **Instagram** no acepta binarios. Crea un contenedor a partir de una URL
    pública que Meta descarga desde sus servidores, y recién después se
    publica. Por eso las piezas se commitean en `static/social/`: quedan
    servidas por `raw.githubusercontent.com` apenas se pushea (sin esperar el
    deploy de Pages) y por el sitio una vez que el deploy termina.

Nada de esto revienta la publicación de la nota: cualquier error se devuelve
como resultado, no como excepción hacia afuera.
"""

from __future__ import annotations

import time
import json
from dataclasses import dataclass, field
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from .config import Settings

TIMEOUT = 60


class PublishError(RuntimeError):
    pass


@dataclass
class Result:
    network: str
    kind: str
    ok: bool
    id: str = ""
    url: str = ""
    error: str = ""
    skipped: str = ""

    def line(self) -> str:
        if self.skipped:
            return f"  ○ {self.network} {self.kind}: omitido ({self.skipped})"
        if self.ok:
            return f"  ✔ {self.network} {self.kind}: {self.id}"
        return f"  ✖ {self.network} {self.kind}: {self.error}"


@dataclass
class Meta:
    settings: Settings
    log: list = field(default_factory=list)

    # ── Plomería ────────────────────────────────────────────────────────
    def _require_requests(self):
        if requests is None:
            raise PublishError("Falta `requests`: pip install -r scripts/requirements.txt")

    def _post(self, path: str, data: dict, files: dict | None = None) -> dict:
        self._require_requests()
        url = f"{self.settings.graph_root}/{path.lstrip('/')}"
        payload = dict(data)
        payload["access_token"] = self.settings.access_token
        resp = requests.post(url, data=payload, files=files, timeout=TIMEOUT)
        return self._unwrap(resp)

    def _get(self, path: str, params: dict | None = None) -> dict:
        self._require_requests()
        url = f"{self.settings.graph_root}/{path.lstrip('/')}"
        query = dict(params or {})
        query["access_token"] = self.settings.access_token
        resp = requests.get(url, params=query, timeout=TIMEOUT)
        return self._unwrap(resp)

    @staticmethod
    def _unwrap(resp) -> dict:
        try:
            body = resp.json()
        except ValueError:
            raise PublishError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        if isinstance(body, dict) and body.get("error"):
            err = body["error"]
            raise PublishError(
                f"{err.get('type', 'GraphError')} {err.get('code', '')}: {err.get('message', '')}".strip()
            )
        if resp.status_code >= 400:
            raise PublishError(f"HTTP {resp.status_code}: {str(body)[:200]}")
        return body

    # ── Diagnóstico ─────────────────────────────────────────────────────
    def whoami(self) -> dict:
        out = {}
        if self.settings.fb_page_id:
            out["facebook"] = self._get(self.settings.fb_page_id, {"fields": "id,name,fan_count"})
        if self.settings.ig_user_id:
            out["instagram"] = self._get(
                self.settings.ig_user_id, {"fields": "id,username,followers_count"}
            )
        return out

    # ── Facebook ────────────────────────────────────────────────────────
    def facebook_photo(self, image: Path | str, caption: str, link: str = "") -> Result:
        if not self.settings.can_post_facebook:
            return Result("facebook", "feed", False, skipped="falta FB_PAGE_ID o token")
        text = caption if not link or link in caption else f"{caption}\n\n{link}"
        try:
            path = Path(image)
            if path.exists():
                with path.open("rb") as fh:
                    body = self._post(
                        f"{self.settings.fb_page_id}/photos",
                        {"caption": text, "published": "true"},
                        files={"source": (path.name, fh, "image/jpeg")},
                    )
            else:
                body = self._post(
                    f"{self.settings.fb_page_id}/photos",
                    {"caption": text, "url": str(image), "published": "true"},
                )
            post_id = str(body.get("post_id") or body.get("id", ""))
            return Result("facebook", "feed", True, id=post_id,
                          url=f"https://facebook.com/{post_id}" if post_id else "")
        except PublishError as exc:
            return Result("facebook", "feed", False, error=str(exc))

    def facebook_album(self, images: list[Path | str], caption: str, link: str = "") -> Result:
        """Publica el carrusel completo en Facebook como álbum.

        El gran problema del pipeline original: publicaba `pieces['feed'][0]` — la
        portada nada más — con `/{page}/photos` (single photo). Acá se sube cada
        imagen y después se arma UN post con `attached_media`, que es lo que
        Facebook muestra como álbum/carrusel con todas las láminas.
        """
        if not self.settings.can_post_facebook:
            return Result("facebook", "album", False, skipped="falta FB_PAGE_ID o token")
        if not images:
            return Result("facebook", "album", False, error="sin imágenes")
        text = caption if not link or link in caption else f"{caption}\n\n{link}"
        try:
            attached: list[str] = []
            for image in images[:10]:
                path = Path(image)
                if path.exists():
                    with path.open("rb") as fh:
                        body = self._post(
                            f"{self.settings.fb_page_id}/photos",
                            {"published": "false"},
                            files={"source": (path.name, fh, "image/jpeg")},
                        )
                else:
                    body = self._post(
                        f"{self.settings.fb_page_id}/photos",
                        {"url": str(image), "published": "false"},
                    )
                fid = body.get("id", "")
                if fid:
                    attached.append(json.dumps({"media_fbid": fid}))
            if not attached:
                return Result("facebook", "album", False, error="no se pudieron subir las fotos")
            body = self._post(
                f"{self.settings.fb_page_id}/feed",
                {
                    "message": text,
                    "attached_media": "[" + ",".join(attached) + "]",
                    "published": "true",
                },
            )
            post_id = str(body.get("post_id") or body.get("id", ""))
            return Result("facebook", "album", True, id=post_id,
                          url=f"https://facebook.com/{post_id}" if post_id else "")
        except PublishError as exc:
            return Result("facebook", "album", False, error=str(exc))

    def facebook_story(self, image: Path | str) -> Result:
        """Publica una historia real de Facebook (sube al carrusel de Stories).

        Es distinto de `facebook_photo`, que sube al feed. Acá se usa el
        endpoint `/{page_id}/stories` y el archivo 9:16.
        """
        if not self.settings.can_post_facebook:
            return Result("facebook", "historia", False, skipped="falta FB_PAGE_ID o token")
        try:
            path = Path(image)
            if path.exists():
                with path.open("rb") as fh:
                    body = self._post(
                        f"{self.settings.fb_page_id}/stories",
                        {"image_type": "image/jpeg"},
                        files={"source": (path.name, fh, "image/jpeg")},
                    )
                    body = dict(body)
            else:
                body = self._post(
                    f"{self.settings.fb_page_id}/stories",
                    {"url": str(image), "image_type": "image/jpeg"},
                )
            mid = str(body.get("id", ""))
            return Result("facebook", "historia", True, id=mid)
        except PublishError as exc:
            return Result("facebook", "historia", False, error=str(exc))

    # ── Instagram ───────────────────────────────────────────────────────
    def _ig_container(self, params: dict) -> str:
        body = self._post(f"{self.settings.ig_user_id}/media", params)
        cid = str(body.get("id", ""))
        if not cid:
            raise PublishError("Instagram no devolvió id de contenedor")
        return cid

    def _ig_wait(self, container_id: str, tries: int = 20, delay: float = 3.0) -> None:
        for attempt in range(tries):
            body = self._get(container_id, {"fields": "status_code,status"})
            status = body.get("status_code")
            if status == "FINISHED":
                return
            if status == "ERROR":
                raise PublishError(f"Contenedor con error: {body.get('status', '')}")
            time.sleep(delay if attempt else 1.0)
        raise PublishError("El contenedor de Instagram no terminó de procesarse")

    def _ig_publish(self, container_id: str) -> str:
        body = self._post(f"{self.settings.ig_user_id}/media_publish", {"creation_id": container_id})
        return str(body.get("id", ""))

    def instagram_image(self, image_url: str, caption: str) -> Result:
        if not self.settings.can_post_instagram:
            return Result("instagram", "feed", False, skipped="falta IG_USER_ID o token")
        try:
            cid = self._ig_container({"image_url": image_url, "caption": caption})
            self._ig_wait(cid)
            mid = self._ig_publish(cid)
            return Result("instagram", "feed", True, id=mid)
        except PublishError as exc:
            return Result("instagram", "feed", False, error=str(exc))

    def instagram_carousel(self, image_urls: list[str], caption: str) -> Result:
        if not self.settings.can_post_instagram:
            return Result("instagram", "carrusel", False, skipped="falta IG_USER_ID o token")
        if len(image_urls) < 2:
            return self.instagram_image(image_urls[0], caption)
        try:
            children = []
            for url in image_urls[:10]:
                cid = self._ig_container({"image_url": url, "is_carousel_item": "true"})
                children.append(cid)
            for cid in children:
                self._ig_wait(cid)
            parent = self._ig_container({
                "media_type": "CAROUSEL",
                "children": ",".join(children),
                "caption": caption,
            })
            self._ig_wait(parent)
            mid = self._ig_publish(parent)
            return Result("instagram", "carrusel", True, id=mid)
        except PublishError as exc:
            return Result("instagram", "carrusel", False, error=str(exc))

    def instagram_story(self, image_url: str) -> Result:
        if not self.settings.can_post_instagram:
            return Result("instagram", "historia", False, skipped="falta IG_USER_ID o token")
        try:
            cid = self._ig_container({"image_url": image_url, "media_type": "STORIES"})
            self._ig_wait(cid)
            mid = self._ig_publish(cid)
            return Result("instagram", "historia", True, id=mid)
        except PublishError as exc:
            return Result("instagram", "historia", False, error=str(exc))


# ── Resolución de la URL pública ────────────────────────────────────────────


def head_ok(url: str, timeout: int = 15) -> bool:
    if requests is None:
        return False
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        if resp.status_code == 405:  # algunos CDN no responden HEAD
            resp = requests.get(url, timeout=timeout, stream=True)
        return resp.status_code == 200
    except Exception:
        return False


def resolve_public_url(filename: str, settings: Settings, wait: int = 240, quiet: bool = False) -> str:
    """Primera URL que efectivamente responda 200. Espera al deploy si hace falta."""
    candidates = settings.public_url_candidates(filename)
    deadline = time.time() + max(0, wait)
    delay = 5
    attempt = 0
    while True:
        for url in candidates:
            if head_ok(url):
                return url
        if time.time() >= deadline:
            return ""
        attempt += 1
        if not quiet and attempt == 1:
            print(f"  … esperando a que {filename} esté publicada", flush=True)
        time.sleep(delay)
        delay = min(20, delay + 5)
