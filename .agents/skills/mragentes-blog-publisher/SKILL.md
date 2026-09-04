---
name: mragentes-blog-publisher
description: Prepara una nota automatizada de MR Agentes desde la cola editorial con asset, validaciones y cambio Git atómico.
---

# Publicación editorial del blog

Usá esta skill únicamente para la nota prevista en miércoles o domingo según `America/Cordoba`, o para un fixture de prueba explícito. La ejecución local prepara una rama de automatización; GitHub Pages sigue siendo la autoridad que publica el sitio.

## Entradas y salidas

Leé pendientes en `.automation/news/`, notas existentes en `content/notas/`, [estilo editorial](references/editorial-style.md) y [quality gates](references/quality-gates.md). Usá [la plantilla](assets/note-template.md) como contrato de estructura, no como texto para copiar.

La salida es exactamente una nota nueva o reutilizada, su asset bajo `static/images/stock/`, el manifiesto de borrador y la transición de 2 a 3 noticias de `reserved` a `consumed`. Todo pertenece al mismo `automation_id` y al mismo cambio Git atómico.

## Flujo

1. Calculá `blog:<fecha>:<slug>` y reutilizá cualquier borrador con esa identidad; nunca generes una segunda nota para la fecha.
2. Seleccioná 2 o 3 noticias `pending`, aunque hayan sido descubiertas días antes, y reservá sólo para ese identificador.
3. Elegí además un nivel de lectura: `inicial` para una primera explicación sin conocimientos previos, `intermedio` para decisiones de diseño y `avanzado` para arquitectura, límites o evaluación. La nota debe sostener ese nivel con definiciones y ejemplos. Elegí exactamente un pilar editorial y declaralo en el front matter: `automatizacion-practica` (métodos, pasos y herramientas), `control-y-gobernanza` (trazabilidad, límites, seguridad) o `casos-para-pymes` (problema, decisión, resultado y aprendizaje). Confirmá fuentes, nombres, fechas y cifras. Redactá una síntesis original con conclusión accionable.
4. Creá o elegí un asset permitido, optimizado y con texto alternativo. No incluyas credenciales, material sin licencia ni referencias privadas.
5. Generá front matter conforme a `.automation/schemas/blog-draft.schema.json` y un nombre portable mediante `scripts/automation/blog_guard.py`.
6. Ejecutá validación de enlaces, schema, asset, pruebas y build de Hugo.
7. Sólo con todos los gates verdes, aplicá nota + asset + transición a `consumed` en un commit atómico para `automation/blog/<run_id>`.

## Entrega remota

Antes de mutar el repositorio, comprobá que el conector de GitHub esté autenticado y tenga permiso de escritura sobre `RealLotex/mragentes-site`. Si no está disponible, terminá en `needs_review` sin escribir. Para entregar la rama seguí `.automation/github/connector-egress.json`: transmití textos como UTF-8 y el asset binario como base64, creá un único árbol y commit remoto con todos los paths y actualizá la referencia sólo por fast-forward. Git local puede preparar el commit atómico revisado, pero no uses git push local, `gh`, tokens ni credenciales locales como alternativa.

## Límites

No invoques Meta, Cloudflare ni otro publicador externo. No despliegues, no escribas en `main`, no hagas force push y no leas secretos. Si falla Hugo, un enlace crítico, el schema o el asset, la transacción deja cero cambios parciales.

## Dry-run y recuperación

En `dry-run`, trabajá en temporal, ejecutá los mismos gates y devolvé el manifiesto del cambio; no escribas el repositorio, no hagas commit ni entrega remota. Un reintento conserva `automation_id`, slug y reservas. Un conflicto, una publicación previa ambigua o más de una nota con la misma identidad termina en `needs_review`.
