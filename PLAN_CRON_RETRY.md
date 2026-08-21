# PLAN — Reintento del cron social a los 15 min (opción 1)

Fecha: 2026-08-21 · Paradigma: TDD (plan → RED → GREEN → confirmación visual)

## Objetivo
Cuando el cron "Social Manager — Daily Post" (13:00) falle porque el modelo no
responde (o cualquier otra razón transitoria), garantizar que **reintente 15 min
después** (13:15) y que no se pierda el post del día, **sin duplicar** en redes.

## Solución elegida (opción 1: refuerzo de schedule)
Agregar un **segundo disparo** del mismo job a las 13:15 que corra el mismo
workflow. La protección anti-duplicado ya existe y es robusta:
- `pick_library_key.py` devuelve `ALREADY_POSTED_TODAY=<clave>` (exit 1) si ya
  hay un post publicado hoy → el agente termina sin publicar nada.
- `publish-library` aborta si la clave ya está en `state.json`.

De este modo, si el run de las 13:00 publica OK, el de las 13:15 se convierte en
no-op (guard lo corta). Si el de 13:00 falla, el de 13:15 intenta de nuevo.

## Mecánica OpenClaw
El cron usa `schedule.kind: "cron"` con `expr: "0 13 * * *"`. Para un segundo
disparo a las 13:15, dos caminos:
- (a) Cambiar el `expr` a cubrir dos horas no es posible con una sola expresión
  cron simple (no hay "13:00 Y 13:15" sin expresiones complejas tipo
  `0 13 * * *` + otro job).
- (b) **Dos jobs** con un `trigger.script` que condicione el segundo: el job de
  13:15 lleva un `trigger.script` que solo dispara (`{fire:true}`) si hoy NO hay
  post publicado. Esto es exactamente la opción 1 + el gate del tipo `trigger`.

## Arquitectura

### Archivos NUEVOS
| Archivo | Propósito |
|---|---|
| `scripts/social/should_retry_today.py` | Script gate del cron: imprime `fire`/`nofire` según si conviene reintentar. Lo usa `trigger.script`. |
| `scripts/tests/test_cron_retry.py` | Suite TDD (RED→GREEN) para el nuevo gate. |

### Archivos a MODIFICAR
| Archivo | Cambio |
|---|---|
| (config cron, vía tool `cron`) | 1) Mantener job 13:00. 2) Crear job 13:15 con `trigger.script` que llama a `should_retry_today.py`. |
| `TOOLS.md` | Documentar el refuerzo de 15 min + el gate. |

## Regla del gate (`should_retry_today.py`)
- Lee `scripts/social/state.json`.
- Si ya hay una pieza con `date == hoy` (en `published[]`), imprime `nofire`
  (nada que publicar → no dispares).
- Si NO hay pieza de hoy, imprime `fire` (reintentá).
- El `trigger` de OpenClaw evalúa la salida: `fire` → correr payload; `nofire` → skip.

## Paso a paso
1. Escribir `should_retry_today.py`.
2. Tests RED: `test_cron_retry.py` verifica que el gate emite `fire` cuando no
   hay post hoy y `nofire` cuando sí lo hay. (RED porque el script aún no existe
   o no cumple el contrato.)
3. Implementar para GREEN.
4. Confirmación visual: correr el script real con el state actual (hoy YA hay
   post `cancer-vacuna-ia`) → debe imprimir `nofire`. Correr con un state
   simulado sin post de hoy → debe imprimir `fire`.
5. Cablear en cron: crear job 13:15 con `trigger.script`.
6. Commit (script + test + TOOLS.md).

## Contrato del trigger (OpenClaw)
`trigger.script` debe devolver JSON `{ "fire": true }` o `{ "fire": false }`
(o emitir la keyword). Se usa un `.py` que imprima exactamente eso a stdout.
