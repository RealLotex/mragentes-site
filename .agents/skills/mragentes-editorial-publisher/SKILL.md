---
name: mragentes-editorial-publisher
description: Investiga noticias, prepara una única nota diaria de MR Agentes y su anuncio visual, valida todo y entrega un solo cambio Git atómico. Usar para la automatización editorial diaria o su recuperación manual; no publica directamente en Meta ni Cloudflare.
---

# Publicador editorial diario de MR Agentes

Esta skill es la única autoridad local del recorrido noticias → blog → recurso social. Leé
`references/editorial-contract.md` antes de escribir y usá `assets/note-template.md` como base.

## Aislamiento obligatorio

La automatización nativa comienza en el checkout compartido del proyecto, no en un worktree
creado por la aplicación. Antes de comprobar limpieza o leer contenido operativo:

1. Ejecutá `git fetch --no-tags origin main` desde el repositorio compartido.
2. Creá un padre temporal con `mktemp -d` y ejecutá
   `git worktree add --detach <ruta-temporal>/worktree origin/main`.
3. Cambiá el directorio de trabajo al worktree aislado, releé esta skill desde allí y comprobá
   `git status --porcelain` dentro de ese worktree.

Un checkout compartido sucio no es un bloqueo: preservalo y no lo inspecciones, limpies ni
modifiques. Sólo un `git status --porcelain` no vacío dentro del worktree aislado recién creado
produce `needs_review`. Eliminá el worktree temporal sólo después de un `skipped_valid` sin
cambios o de que el conector confirme el PR; conservá la evidencia local ante un resultado
remoto incierto.

## Contrato de ejecución

1. Determiná la fecha en `America/Cordoba` y la identidad `editorial:YYYY-MM-DD`.
2. Comprobá los artefactos de esa identidad en el worktree creado desde `origin/main`. Si los
   artefactos completos de la fecha ya existen y son consistentes, devolvé `skipped_valid` sin
   escribir. Si hay estado parcial, duplicado o ambiguo, devolvé `needs_review`; nunca pises ni
   dupliques cambios.
3. En `dry-run`, investigá y validá sin crear rama, commit, PR ni efectos externos.
4. Abrí fuentes primarias y agregá a `.automation/news/queue/news-queue.json` sólo hechos
   verificables, actuales, pertinentes y no duplicados.
5. Elegí 2 o 3 ítems pendientes compatibles. Si no existen al menos dos, devolvé
   `skipped_valid`: no escribas contenido de relleno y no crees un cambio vacío.
6. Prepará una nota original y exactamente una imagen de portada. Preferí Pexels o Unsplash; si
   no hay una fotografía relevante, una imagen generada sin texto ni logotipos puede ser el
   fondo. La nota debe ser comprensible para una PyME y enlazar la evidencia junto a cada dato.
7. Renderizá exactamente un anuncio vertical con la plantilla `nota`:
   `python -m scripts.social render-note-announcement --slug <slug>`. El fondo nunca es la pieza
   social final.
8. Reservá y consumí los ítems seleccionados dentro de la misma transacción. Creá el manifiesto
   `.automation/blog/<fecha>-<slug>.json` y un reporte `.automation/reports/editorial-<fecha>.json`.
9. Ejecutá `blog_guard`, `editorial_style`, los tests focalizados, el escaneo de secretos y Hugo.
   Cualquier fallo cancela la entrega completa.
10. Entregá cola, nota, portada, anuncio, manifiesto e informe en un único commit remoto atómico
    sobre `automation/editorial/YYYY-MM-DD`, siguiendo
    `.automation/github/connector-egress.json`. Creá un PR no borrador a `main` con el conector.

Para el preflight de GitHub usá exactamente
`github_get_repo(repository_full_name="RealLotex/mragentes-site")` y exigí
`permissions.push=true`, como declara `.automation/github/connector-egress.json`; no inventes
otra llamada de permisos ni una escritura de prueba. Un error de autenticación, esquema o
permiso produce `needs_review`.

El merge protegido y `.github/workflows/deploy.yml` publican la web y, sólo después del health
gate, hacen una publicación en Facebook, una en Instagram y un push por nota. Esta skill no llama a Meta
ni Cloudflare, no hace merge y no usa credenciales locales. No usa git push local
ni lo autoriza. No uses git push local.

## Recuperación

Reejecutá la misma identidad. Reutilizá una rama o PR sólo si apuntan al mismo SHA base y a los
mismos artefactos. Ante timeout del conector, commit remoto no comprobable o efecto externo
`uncertain`, devolvé `needs_review`; no repitas a ciegas.
