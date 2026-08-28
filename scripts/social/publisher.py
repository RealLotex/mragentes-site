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

import datetime as dt
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from .config import Settings

TIMEOUT = 60


class PublishError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        category: str = "permanent",
        error_code: str = "publish_error",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.error_code = error_code
        self.retryable = retryable


_SENSITIVE_QUERY_KEYS = {
    "access_token",
    "token",
    "authorization",
    "password",
    "passwd",
    "secret",
    "client_secret",
}


def _redact_message(value: object, max_length: int = 220) -> str:
    """Convierte diagnósticos remotos en texto acotado sin credenciales."""
    text = str(value or "")
    text = re.sub(
        r"(?i)\b(access[_-]?token|authorization|password|passwd|client[_-]?secret|secret)"
        r"\s*[=:]\s*[^\s&,;]+",
        "[REDACTED]",
        text,
    )
    text = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+\-/]+=*", "Bearer [REDACTED]", text)
    text = re.sub(r"\bEAAB[A-Za-z0-9._~-]{8,}\b", "[REDACTED]", text)
    text = re.sub(r"(https?://)[^/@\s:]+:[^/@\s]+@", r"\1[REDACTED]@", text)
    text = " ".join(text.split())
    if max_length <= 0:
        return ""
    if len(text) > max_length:
        text = text[: max(0, max_length - 1)].rstrip() + "…"
    return text


def _safe_public_url(value: object) -> str:
    """Conserva un permalink público, quitando userinfo y parámetros sensibles."""
    raw = str(value or "")
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    try:
        port = f":{parsed.port}" if parsed.port is not None else ""
    except ValueError:
        return ""
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.casefold() not in _SENSITIVE_QUERY_KEYS
        ],
        doseq=True,
    )
    return _redact_message(
        urlunsplit((parsed.scheme, f"{host}{port}", parsed.path, query, "")), 2048
    )


def classify_publish_error(
    error: object,
    *,
    http_status: int | None = None,
    request_sent: bool = False,
) -> dict[str, object]:
    """Clasifica un fallo sin confundir timeout posenvío con reintento seguro."""
    if isinstance(error, PublishError):
        return {
            "category": error.category,
            "error_code": error.error_code,
            "retryable": error.retryable,
            "message": _redact_message(error),
        }

    if isinstance(error, (TimeoutError, ConnectionError)):
        category = "uncertain" if request_sent else "retryable"
        code = "transport_timeout" if isinstance(error, TimeoutError) else "transport_error"
        return {
            "category": category,
            "error_code": code,
            "retryable": category == "retryable",
            "message": _redact_message(error) or code,
        }

    graph = error.get("error", error) if isinstance(error, dict) else {}
    graph = graph if isinstance(graph, dict) else {}
    code = graph.get("code")
    transient = graph.get("is_transient") is True
    message = graph.get("message") or error
    if code in {190, 102}:
        category, error_code = "authentication", f"graph_{code}"
    elif transient or http_status == 429 or code in {1, 2, 4, 17, 32, 613}:
        category, error_code = "retryable", f"graph_{code or http_status or 'transient'}"
    elif http_status is not None and 500 <= http_status <= 599:
        category, error_code = "retryable", f"http_{http_status}"
    elif request_sent and not graph:
        category, error_code = "uncertain", "transport_uncertain"
    else:
        category, error_code = "permanent", f"graph_{code}" if code is not None else "publish_error"
    return {
        "category": category,
        "error_code": error_code,
        "retryable": category == "retryable",
        "message": _redact_message(message),
    }


@dataclass
class Result:
    network: str
    kind: str
    ok: bool
    id: str = ""
    url: str = ""
    error: str = ""
    skipped: str = ""
    retryable: bool = False
    error_code: str = ""
    category: str = ""

    def line(self) -> str:
        if self.skipped:
            return f"  ○ {self.network} {self.kind}: omitido ({_redact_message(self.skipped, 180)})"
        if self.ok:
            return f"  ✔ {self.network} {self.kind}: {_redact_message(self.id, 200)}"
        prefix = f"  ✖ {self.network} {self.kind}: "
        return prefix + _redact_message(self.error, max(1, 300 - len(prefix)))


def _failed_result(network: str, kind: str, exc: PublishError) -> Result:
    return Result(
        network,
        kind,
        False,
        error=_redact_message(exc),
        retryable=exc.retryable,
        error_code=exc.error_code,
        category=exc.category,
    )


@dataclass
class Meta:
    settings: Settings
    log: list = field(default_factory=list)

    # ── Plomería ────────────────────────────────────────────────────────
    def _require_requests(self):
        if requests is None:
            raise PublishError("Falta `requests`: pip install -r scripts/requirements.txt")

    def _require_testing(self) -> None:
        if not self.settings.is_testing:
            raise PublishError(
                "META_ENVIRONMENT no está en testing; salida remota bloqueada",
                error_code="environment_not_testing",
            )

    def _post(self, path: str, data: dict, files: dict | None = None) -> dict:
        self._require_requests()
        self._require_testing()
        url = f"{self.settings.graph_root}/{path.lstrip('/')}"
        payload = dict(data)
        payload["access_token"] = self.settings.access_token
        try:
            resp = requests.post(url, data=payload, files=files, timeout=TIMEOUT)
        except Exception as exc:  # un POST pudo surtir efecto antes del corte
            details = classify_publish_error(exc, request_sent=True)
            raise PublishError(
                str(details["message"]),
                category=str(details["category"]),
                error_code=str(details["error_code"]),
                retryable=bool(details["retryable"]),
            ) from exc
        return self._unwrap(resp)

    def _get(self, path: str, params: dict | None = None) -> dict:
        self._require_requests()
        self._require_testing()
        url = f"{self.settings.graph_root}/{path.lstrip('/')}"
        query = dict(params or {})
        query["access_token"] = self.settings.access_token
        try:
            resp = requests.get(url, params=query, timeout=TIMEOUT)
        except Exception as exc:
            details = classify_publish_error(exc, request_sent=False)
            raise PublishError(
                str(details["message"]),
                category=str(details["category"]),
                error_code=str(details["error_code"]),
                retryable=bool(details["retryable"]),
            ) from exc
        return self._unwrap(resp)

    @staticmethod
    def _unwrap(resp) -> dict:
        try:
            body = resp.json()
        except ValueError:
            details = classify_publish_error({}, http_status=resp.status_code)
            raise PublishError(
                f"HTTP {resp.status_code}: {_redact_message(resp.text)}",
                category=str(details["category"]),
                error_code=str(details["error_code"]),
                retryable=bool(details["retryable"]),
            )
        if isinstance(body, dict) and body.get("error"):
            err = body["error"]
            details = classify_publish_error(body, http_status=resp.status_code)
            raise PublishError(
                f"{err.get('type', 'GraphError')} {err.get('code', '')}: "
                f"{_redact_message(err.get('message', ''))}".strip(),
                category=str(details["category"]),
                error_code=str(details["error_code"]),
                retryable=bool(details["retryable"]),
            )
        if resp.status_code >= 400:
            details = classify_publish_error(body, http_status=resp.status_code)
            raise PublishError(
                f"HTTP {resp.status_code}: {_redact_message(body)}",
                category=str(details["category"]),
                error_code=str(details["error_code"]),
                retryable=bool(details["retryable"]),
            )
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
            return _failed_result("facebook", "feed", exc)

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
            return _failed_result("facebook", "album", exc)

    def facebook_story(self, image: Path | str) -> Result:
        """Publica una historia real de Facebook (endpoint /stories).

        El edge `/{page_id}/stories` existe; para poder POSTear requiere el
        permiso `pages_manage_metadata` en el token de página (además de
        `pages_manage_posts`). Sin él, Meta responde "Unsupported post request".
        """
        if not self.settings.can_post_facebook:
            return Result("facebook", "historia", False, skipped="falta FB_PAGE_ID o token")
        try:
            path = Path(image)
            if not path.exists():
                return Result("facebook", "historia", False,
                              error=f"no existe la historia: {path.name}")
            with path.open("rb") as fh:
                body = self._post(
                    f"{self.settings.fb_page_id}/stories",
                    {"image_type": "jpg"},
                    files={"source": (path.name, fh, "image/jpeg")},
                )
            logic_id = str(body.get("logic_id") or body.get("id") or "")
            return Result("facebook", "historia", True, id=logic_id)
        except PublishError as exc:
            return _failed_result("facebook", "historia", exc)

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
            return _failed_result("instagram", "feed", exc)

    def instagram_carousel(self, image_urls: list[str], caption: str) -> Result:
        if not self.settings.can_post_instagram:
            return Result("instagram", "carrusel", False, skipped="falta IG_USER_ID o token")
        if not image_urls:
            return Result(
                "instagram",
                "carrusel",
                False,
                error="se necesita al menos una imagen",
                error_code="empty_media",
                category="permanent",
            )
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
            return _failed_result("instagram", "carrusel", exc)

    def instagram_story(self, image_url: str) -> Result:
        if not self.settings.can_post_instagram:
            return Result("instagram", "historia", False, skipped="falta IG_USER_ID o token")
        try:
            cid = self._ig_container({"image_url": image_url, "media_type": "STORIES"})
            self._ig_wait(cid)
            mid = self._ig_publish(cid)
            return Result("instagram", "historia", True, id=mid)
        except PublishError as exc:
            return _failed_result("instagram", "historia", exc)

    def recent_publications(
        self,
        platform: str,
        *,
        since: str,
        limit: int = 25,
    ) -> list[dict[str, str]]:
        """Lee evidencia remota mínima para reconciliar un resultado incierto."""
        if platform not in {"facebook", "instagram"}:
            raise ValueError("platform debe ser facebook o instagram")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit debe estar entre 1 y 100")
        if not isinstance(since, str):
            raise ValueError("since debe ser una fecha RFC3339")
        normalized = since[:-1] + "+00:00" if since.endswith("Z") else since
        try:
            boundary = dt.datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError("since debe ser una fecha RFC3339 válida") from exc
        if boundary.tzinfo is None or boundary.utcoffset() is None:
            raise ValueError("since debe incluir zona horaria")

        if platform == "facebook":
            path = f"{self.settings.fb_page_id}/posts"
            fields = "id,created_time,permalink_url,message"
        else:
            path = f"{self.settings.ig_user_id}/media"
            fields = "id,timestamp,permalink,caption"
        body = self._get(path, {"fields": fields, "since": since, "limit": limit})
        source = body.get("data", []) if isinstance(body, dict) else []
        if not isinstance(source, list):
            raise PublishError("Graph devolvió una colección reciente inválida")

        records: list[dict[str, str]] = []
        for item in source:
            if not isinstance(item, dict):
                continue
            created_at = item.get("created_time") if platform == "facebook" else item.get("timestamp")
            permalink = item.get("permalink_url") if platform == "facebook" else item.get("permalink")
            record = {
                "platform": platform,
                "remote_id": _redact_message(item.get("id", ""), 300),
                "created_at": _redact_message(created_at, 80),
                "permalink": _safe_public_url(permalink),
            }
            raw_copy = item.get("message") if platform == "facebook" else item.get("caption")
            if isinstance(raw_copy, str) and raw_copy:
                record["caption_hash"] = (
                    "sha256:" + hashlib.sha256(raw_copy.encode("utf-8")).hexdigest()
                )
            else:
                synthetic_hash = item.get("caption_hash") or item.get("message_hash")
                if isinstance(synthetic_hash, str) and synthetic_hash:
                    record["caption_hash"] = _redact_message(synthetic_hash, 300)
            asset_hash = item.get("asset_hash")
            if isinstance(asset_hash, str) and asset_hash:
                record["asset_hash"] = _redact_message(asset_hash, 300)
            records.append(record)
        return records


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
