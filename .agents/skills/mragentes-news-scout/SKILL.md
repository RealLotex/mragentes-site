---
name: mragentes-news-scout
description: Releva y valida noticias para la cola editorial estructurada de MR Agentes sin redactar ni publicar contenido final.
---

# Relevamiento editorial de MR Agentes

Usá esta skill para una corrida acotada de investigación que deje noticias verificables en la cola del repositorio. La fecha operativa es siempre la fecha local de `America/Cordoba`.

## Alcance

Podés leer `.automation/news/`, este directorio de la skill y una ventana acotada de notas publicadas para deduplicar. Podés consultar la web para verificar fuentes actuales. La única salida versionable es un conjunto de ítems bajo `.automation/news/queue/` y su reporte sanitario; no recorras otros proyectos ni dependas de procesos locales ajenos al repositorio.

Antes de investigar, leé [fuentes](references/sources.md) y [reglas de selección](references/selection-rules.md). Validá cada ítem con `.automation/schemas/news-item.schema.json` y con `scripts/automation/news_queue.py`.

## Flujo

1. Calculá un `run_id` estable para la fecha local y comprobá si esa corrida ya dejó resultados.
2. Leé sólo pendientes y consumidos recientes necesarios para detectar duplicados.
3. Verificá la fecha real del hecho y preferí la fuente primaria; una noticia de días anteriores sigue siendo elegible.
4. Normalizá URL, entidad y evento. Seleccioná de 2 a 4 ítems útiles; cero es válido si no hay evidencia suficiente.
5. Escribí únicamente objetos de schema version 1 con afirmaciones breves y sus URLs de evidencia.
6. Ejecutá schema, deduplicación, pruebas y preflight. Prepará un commit sólo para la rama `automation/news/<run_id>` si todos los gates pasan.

## Entrega remota

Antes de mutar el repositorio, comprobá que el conector de GitHub esté autenticado y tenga permiso de escritura sobre `RealLotex/mragentes-site`. Si no está disponible, terminá en `needs_review` sin escribir. Para entregar la rama seguí `.automation/github/connector-egress.json`: revisá paths explícitos, creá todos los blobs y un único árbol y commit remoto, y actualizá la referencia sólo por fast-forward. Git local puede preparar el commit revisado, pero no uses git push local, `gh`, tokens ni credenciales locales como alternativa.

## Límites de seguridad

- **No Meta:** no publiques, consultes ni prepares llamadas a redes sociales.
- **No Cloudflare:** no invoques despliegues, Workers ni notificaciones.
- **No nota:** no redactes, modifiques ni publiques una nota del blog.
- No leas, muestres ni copies secretos. El conector autorizado es la única integración de escritura remota.
- Nunca hagas force push ni escribas en `main`.

## Dry-run y fallos

En `dry-run`, no escribas archivos, no hagas commit ni entrega remota: devolvé los ítems candidatos, duplicados, gates y paths que se modificarían. Ante una fuente ambigua, un schema inválido, un conflicto de lock o un estado remoto ambiguo, terminá con `needs_review` o `failed` y un reporte corto; nunca relajes la validación.
