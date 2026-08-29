---
name: mragentes-social-manager
description: Prepara piezas sociales originales o diagnostica recuperaciones seguras usando drafts y ledger versionados de MR Agentes.
---

# Social Manager de MR Agentes

Esta skill tiene dos modos explícitos y mutuamente excluyentes: `daily_owned` y `recovery`. La fecha se calcula en `America/Cordoba`. La creación ocurre en el repositorio; la publicación remota pertenece a workflows confiables con ledger, no a esta ejecución creativa.

Leé [marca](references/brand.md) para crear contenido. Leé [runbook de publicación](references/meta-runbook.md) sólo para entender el contrato de entrega. En modo `recovery`, leé además [recuperación](references/recovery.md).

## Modo `daily_owned`

1. Reutilizá el draft existente de la fecha o creá exactamente uno si no existe.
2. Leé una ventana acotada de temas, copy y hashes recientes; las piezas agotadas son historial, no una rueda reutilizable.
3. Redactá captions distintos para Facebook e Instagram y generá un asset original permitido con alt text.
4. Construí `run_id`, `dedupe_key`, hashes y JSON conforme a `.automation/schemas/social-post.schema.json`.
5. Ejecutá frescura, schema, render, asset y pruebas. Prepará sólo `automation/social/<run_id>`.

## Modo `recovery`

No generes una nueva pieza. Leé el draft de la fecha, el workflow y el ledger sanitario. Si ambas plataformas están confirmadas, devolvé `skipped`. Si falta una plataforma antes de cualquier creación remota, prepará sólo ese reintento. Si el efecto pudo ocurrir pero no hay checkpoint único, buscá una coincidencia remota mediante el workflow autorizado: coincidencia única reconstruye el checkpoint; cero o varias coincidencias devuelven `needs_review`.

## Entrega remota

Antes de mutar el repositorio o reintentar un workflow, comprobá que el conector de GitHub esté autenticado y tenga permiso de escritura sobre `RealLotex/mragentes-site`. Si no está disponible, terminá en `needs_review` sin escribir ni reintentar. Para entregar una rama seguí `.automation/github/connector-egress.json`: transmití textos como UTF-8 y assets binarios como base64, creá un único árbol y commit remoto con todos los paths y actualizá la referencia sólo por fast-forward. Git local puede preparar el commit revisado, pero no uses git push local, `gh`, tokens ni credenciales locales como alternativa. En `recovery`, el mismo conector sólo puede reintentar los jobs fallidos autorizados por el descriptor.

## Límites

No llames directamente a Meta ni a Cloudflare. No despliegues, no escribas en `main`, no hagas force push, no repitas una publicación incierta y no leas secretos. Usá únicamente este repositorio y las capacidades nativas autorizadas de Codex y GitHub.

## Dry-run y fallos

En `dry-run`, validá fixtures o artefactos en temporal y devolvé paths, hashes, gates y plan de recuperación; no escribas, no hagas commit, entrega remota, dispatch ni llamadas externas. Schema, hash o asset inválido termina en `failed`. Estado remoto ambiguo, conflicto de IDs o cambios ajenos termina en `needs_review`, siempre sin segunda pieza.
