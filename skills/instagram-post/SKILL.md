# instagram-post — Skill de contenido para IG/FB de MR Agentes

Guía operativa para generar y publicar contenido (social manager). El pipeline vive en la **raíz del workspace** (repo público `mragentes-site`), rama `main`.

## Referencias
- **Reglas de marca:** `brand/INSTAGRAM-BRAND.md`
- **Templates render:** `skills/instagram-post/assets/*.html` (según layout)
- **Social manager:** `scripts/social/` (CLI con comandos `nota`, `publish-nota`, `publish-library`, `gallery`, `doctor`)
- **Estado anti-duplicado:** `scripts/social/state.json`
- **Biblioteca de posteos:** `scripts/social/library.py`

## Comandos (SIEMPRE usar el venv)
```bash
VENV=/home/openclaw/.openclaw/workspace/tmp/venv_social/bin/python
cd /home/openclaw/.openclaw/workspace
$VENV -m scripts.social doctor                      # diagnóstico
$VENV -m scripts.social gallery                     # muestrario plantillas
$VENV -m scripts.social publish-library --key <K> --dry-run   # previsualizar
$VENV -m scripts.social publish-library --key <K>             # publicar
$VENV -m scripts.social publish-nota --slug <S> --dry-run     # previsualizar nota
$VENV -m scripts.social publish-nota --slug <S>               # publicar nota
```
> ⚠️ `publish-library` NO acepta `--force`. `publish-nota` SÍ.

## Diferencias clave
- **`publish-nota`** publica una nota del blog (`content/notas/*.md`) como **álbum de fotos** en FB + carrusel en IG.
- **`publish-library`** publica una pieza de contenido propio (la biblioteca `library.py`). Es el que usa el cron diario.

## Token de Meta (lección 2026-08-10 — NO repetir el error)
- El token es **long-lived** (`expires_at:0`). Vive SOLO en `.env` (raíz) + secret de GitHub `META_ACCESS_TOKEN`. NUNCA commitear.
- **CATEGORIZAR el error ANTES de tocar tokens**:
  - `publish_actions ... deprecated` = **permiso de app/scope deprecado**, NO token vencido → regenerar long-lived y reinstalar. No hay fix de código.
  - `190 Session has expired` = token vencido.
- Verificar permisos: `GET /debug_token?input_token=<tok>&access_token=<app_id|app_secret>` → debe incluir `pages_manage_posts`, `pages_read_engagement` (+ `pages_manage_metadata` para stories).
- **Probar publicación real** (post de test + borrar) antes de dar por bueno un token. `debug_token` solo valida el token, no que el permiso publique.

## Verificación post-publicación
Tras publicar, confirmá en `state.json` que la entrada tenga **tanto** `facebook` como `instagram` (o `story`) con ids (no `fb: -`). Si FB quedó vacío y solo salió IG, republicá la pieza (puede haber sido por token sin `pages_manage_posts`).

## Errores comunes que NO son del token
- `(#12) deprecate_post_aggregated_fields_for_attachement` al LEER un post con `attachments{...}` → campo deprecado. Verificá con `fields=id,is_published,permalink_url` (sin subcampos).
- `Result` del publisher usa `.network` (NO `.platform`).

## Seguridad
Repo es **PÚBLICO**. No commitear `.env`, tokens ni secrets. Ver `TOOLS.md → Seguridad` para rotación/purga.
