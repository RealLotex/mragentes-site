# PLAN — Migrar visión de Google (free, rate-limited) a DeepSeek Vision

Fecha: 2026-08-21 · Paradigma: TDD con confirmación visual (obligatorio según USER)

## 1. Objetivo
Reemplazar el proveedor de visión de imágenes de OpenClaw:
- **Actual:** `google/gemini-3.5-flash-lite` con `GOOGLE_API_KEY` gratuita → se rate-limitea rápido.
- **Nuevo:** `deepseek/deepseek-v4-flash-vision-exp` (misma API key DeepSeek que ya usamos como modelo principal).

Esto NO requiere actualizar OpenClaw (versión 2026.7.1-2 = última npm; el core ya auto-registra
proveedores custom con modelos image-capable en `models.providers.*.models[].input`).

## 2. Hallazgos de la investigación (fuente: api-docs.deepseek.com/guides/vision)
- Modelo: `deepseek-v4-flash-vision-exp`. Formatos: JPEG, PNG, GIF, WebP.
- Envío: base64 inline (`image_url` data URI) — compatible con el adapter `openai-completions` de OpenClaw.
- **Tokens:** toda imagen se auto-resize a ~800×800 → **máx 384 tokens/imagen** (cota dura de costo).
- **Batch:** hasta **600 imágenes por request** (cada una cotizada independiente) → batch = 1 request con N imágenes en vez de N requests.
- Límites: body 48 MiB, imagen 32 MiB inline, URL 8192 chars.
- `detail:"low"` (512×512) → **NO pasable** vía OpenClaw: el core serializa `image_url` como string plano.
  Mitigación: el auto-resize a 800×800 ya acota el costo por imagen.
- Files API (reuso de imagen subida) → no aplica al flujo de OpenClaw (manda base64 inline).

## 3. Arquitectura

### Archivos a MODIFICAR
| Archivo | Cambio |
|---|---|
| `~/.openclaw/openclaw.json` | 1) Agregar `deepseek-v4-flash-vision-exp` al catálogo `models.providers.deepseek.models[]` con `input: ["text","image"]`. 2) `tools.media.image.models` → deepseek vision primero, google como fallback. 3) `tools.media.image.attachments` → `{mode:"all"}` (batch de imágenes inbound en 1 request). |
| `TOOLS.md` | Documentar la migración + comandos de verificación. |

### Archivos a CREAR
| Archivo | Propósito |
|---|---|
| `scripts/tests/test_vision_deepseek.py` | Suite de tests TDD (RED→GREEN). |
| `PLAN_VISION_DEEPSEEK.md` | Este plan (entregable del paradigma TDD). |

### Archivos de respaldo
- `~/.openclaw/openclaw.json.bak-vision-<timestamp>` (antes de tocar config).

## 4. Paso a paso
1. Backup de `openclaw.json`.
2. **RED:** correr `scripts/tests/test_vision_deepseek.py` → falla (modelo no registrado, config sigue en google).
3. Implementar:
   - `openclaw config set models.providers.deepseek.models '<array 5 modelos>' --strict-json --replace`
   - `openclaw config set tools.media.image.models '[deepseek, google]' --strict-json --replace`
   - `openclaw config set tools.media.image.attachments '{mode:"all",maxAttachments:10}' --strict-json`
4. Hot reload (gateway vigila el archivo; validar con `openclaw config validate`).
5. **GREEN:** correr tests → pasan.
6. **Confirmación visual:** describir una imagen real (favicon + slide PNG) con el tool `image` y verificar que la descripción es correcta.
7. Commit (solo tests + plan + TOOLS.md; **NUNCA** openclaw.json — vive fuera del repo y tiene secrets).

## 5. Tests (TDD)
Ver `scripts/tests/test_vision_deepseek.py`:
- T1: el modelo `deepseek-v4-flash-vision-exp` está registrado con input text+image en `openclaw models list`.
- T2: `tools.media.image.models[0]` es deepseek vision (google queda como fallback en [1]).
- T3: `tools.media.image.attachments.mode == "all"` (batch).
- T4 (funcional): `openclaw infer image describe --model deepseek/deepseek-v4-flash-vision-exp` describe una imagen real y devuelve texto no vacío.
- T5 (funcional): el tool `image` de OpenClaw responde con descripción coherente (confirmación visual posterior).
