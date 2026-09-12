---
name: mragentes-editorial-publisher
description: Investiga noticias, prepara una única nota diaria de MR Agentes y su anuncio visual, valida todo y entrega un solo cambio Git atómico. Usar para la automatización editorial diaria o su recuperación manual; no publica directamente en Meta ni Cloudflare.
---

# Publicador editorial diario de MR Agentes

Esta skill es la única autoridad local del recorrido noticias → blog → recurso social. Leé
`references/editorial-contract.md` antes de escribir y usá `assets/note-template.md` como base.

## Contrato de ejecución

1. Determiná la fecha en `America/Cordoba` y la identidad `editorial:YYYY-MM-DD`.
2. Exigí un worktree limpio creado desde `origin/main`. Si no está limpio, si la nota del día ya
   existe o si el estado remoto es ambiguo, detenete con `needs_review`; nunca pises cambios.
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
    sobre `automation/editorial/<run_id>`, siguiendo
    `.automation/github/connector-egress.json`. Creá un PR no borrador a `main` con el conector.

El merge protegido y `.github/workflows/deploy.yml` publican la web y, sólo después del health
gate, hacen una publicación en Facebook, una en Instagram y un push por nota. Esta skill no llama a Meta
ni Cloudflare, no hace merge y no usa credenciales locales. No usa git push local
ni lo autoriza. No uses git push local.

## Recuperación

Reejecutá la misma identidad. Reutilizá una rama o PR sólo si apuntan al mismo SHA base y a los
mismos artefactos. Ante timeout del conector, commit remoto no comprobable o efecto externo
`uncertain`, devolvé `needs_review`; no repitas a ciegas.
