# Seguridad

Este repositorio es público y sirve `mragentes.com.ar`. Todo contenido versionado debe
considerarse público y permanente. La arquitectura separa generación sin credenciales,
validación en GitHub y efectos externos dentro de entornos protegidos.

## Reglas no negociables

1. Nunca versiones `.env`, tokens, claves privadas, secretos de aplicación, cookies ni
   respuestas completas de APIs autenticadas.
2. Nunca pegues un secreto en una conversación, argumento de proceso, URL, commit, artefacto,
   captura, excepción o log.
3. Un secreto expuesto se considera comprometido: detené el flujo, revocalo, rotalo y recién
   después investigá el alcance.
4. No intentes leer el valor de un secret administrado. Validá presencia y comportamiento sin
   imprimirlo.
5. Ningún job de pull request no confiable recibe secretos ni permisos de escritura.
6. No relajes `meta-testing`, protecciones de ambiente, CORS, validación de origen, health gates
   ni controles idempotentes para resolver una urgencia.
7. Un resultado remoto incierto no se reintenta a ciegas: se reconcilia o pasa a revisión.

## Inventario de configuración sensible

| Autoridad | Nombre | Uso | Exposición permitida |
|---|---|---|---|
| GitHub, entorno `meta-testing` | `META_ACCESS_TOKEN` | autenticar Graph API | sólo variable de entorno del job |
| GitHub, entorno `meta-testing` | `FB_PAGE_ID` | destino Facebook | sólo variable de entorno del job |
| GitHub, entorno `meta-testing` | `IG_USER_ID` | destino Instagram | sólo variable de entorno del job |
| GitHub, entorno `cloudflare-production` | `PUSH_API_TOKEN` | autenticar `/api/send/` | sólo variable de entorno del job |
| GitHub, entorno `cloudflare-production` | `PUSH_WORKER_URL` | URL base del Worker | variable de entorno protegida |
| Cloudflare | `API_TOKEN` | verificar llamadas del workflow | secret del Worker |
| Cloudflare | `VAPID_PRIVATE_KEY` | firmar Web Push | secret del Worker |
| Cloudflare | `VAPID_PUBLIC_KEY` | alta del navegador | binding/configuración pública |
| Cloudflare | `PUSH_SUBS` | suscripciones y estado | binding KV; nunca artefacto CI |

`PUSH_API_TOKEN` y `API_TOKEN` representan el mismo secreto en lados opuestos del límite. La
clave privada VAPID nunca entra en GitHub ni en el cliente. El token de Meta nunca entra en una
tarea de ChatGPT: aparece únicamente en los workflows de entrega.

Los archivos `.env.example` y configuraciones versionadas deben contener nombres y valores
vacíos o no sensibles. No uses un valor real como “ejemplo”.

## Límites de confianza

### Codex y tareas de ChatGPT

Generan contenido, recursos y reportes en un worktree. No reciben credenciales de Meta o
Cloudflare y no publican directamente. Sus ramas sólo pueden escribir los prefijos declarados
en `.automation/schedules/*.json`.

### GitHub

- CI usa `contents: read` siempre que alcanza.
- El intake usa `contents: write` y `pull-requests: write` sólo para crear/reutilizar el PR y
  solicitar merge automático protegido.
- Pages usa `pages: write` e `id-token: write` únicamente en el job de despliegue.
- Los jobs externos declaran `contents: read`, un environment concreto y sólo sus secrets.
- Las actions de terceros permanecen fijadas por SHA.

### Meta

`META_ENVIRONMENT=testing` es un control fail-closed del código además del environment de
GitHub. La aplicación sigue en testing y publica únicamente sobre activos autorizados para el
propietario. Promoverla requiere una decisión explícita, revisión de permisos y una nueva ronda
RED→GREEN; cambiar sólo una variable no constituye aprobación.

### Cloudflare y Web Push

El Worker canónico es `cf_worker.js`. Sus rutas públicas de suscripción validan método, origen,
forma y tamaño; `/api/send/` exige bearer token y evento con identidad estable. Las
suscripciones se almacenan en `PUSH_SUBS`, no en el repositorio. El navegador sólo recibe la
clave pública VAPID.

El despliegue del Worker se realiza con el conector de Cloudflare después de tests y validación
de staging. No agregues tokens de cuenta ni comandos de publicación al repositorio.

## Controles antes de integrar

Ejecutá como mínimo:

```bash
.venv/bin/python scripts/scan_secrets.py --all
.venv/bin/python -m pytest -q tests/static/test_repository_contract.py
.venv/bin/python -m pytest -q tests/static/test_runtime_independence.py
git diff --cached --name-only
git diff --cached --check
```

Revisá cada ruta preparada explícitamente. Deben quedar fuera archivos con nombres o contenido
que sugieran credenciales, dumps, backups, sesiones o configuración local. Si un detector da
un falso positivo, documentá por qué; no desactives globalmente el control.

## Manejo seguro de errores

- Redactá tokens, cabeceras de autorización, cuerpos autenticados e identificadores privados.
- Limitá el cuerpo leído de una respuesta remota antes de clasificarla.
- Separá errores retryable, permanentes e inciertos.
- Conservá sólo hashes, IDs remotos necesarios, timestamps, estado y permalinks públicos.
- No guardes captions completos ni payloads privados en el ledger operativo.
- Un `409` sólo cuenta como duplicado confirmado si coincide la identidad y el hash esperados;
  cualquier conflicto distinto requiere revisión.

## Respuesta a un incidente

1. Pausá las tareas o environments que puedan repetir el efecto.
2. Revocá o rotá el secreto en la autoridad que lo emitió.
3. Actualizá el secret protegido sin mostrar su valor.
4. Determiná exposición en árbol, índice, historial, logs y artefactos mediante fragmentos
   mínimos no sensibles.
5. Si alcanzó Git, coordiná una remediación del historial con backup y autorización explícita;
   borrar el archivo en un commit nuevo no elimina la exposición previa.
6. Ejecutá contratos, una prueba controlada y reconciliación remota.
7. Reactivá de a una etapa y registrá causa, alcance y medidas preventivas sin incluir secretos.

## Reporte

Para informar una vulnerabilidad, no abras un issue público con datos explotables. Contactá al
propietario por un canal privado, describí impacto y reproducción con valores redactados, e
indicá si hubo un efecto externo. No pruebes publicación, borrado o acceso sobre activos que no
estén expresamente autorizados.
