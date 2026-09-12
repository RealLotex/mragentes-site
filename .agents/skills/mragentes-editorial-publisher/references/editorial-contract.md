# Contrato editorial

## Selección y fuentes

- Tema: IA, agentes, automatización, productividad o tecnología aplicable a PyMEs.
- Preferir anuncios, documentación, repositorios, papers y páginas oficiales. Un medio puede
  aportar contexto, pero no sustituye la fuente primaria cuando existe.
- Cada ítem necesita URL HTTPS canónica, fecha del hecho, entidad y una afirmación comprobable.
- Deduplicar por URL, entidad, fecha del evento y similitud del título contra pendientes y
  consumidos. Si dos fuentes discrepan en algo material, descartar o marcar revisión.
- Conservar noticias pendientes útiles de días anteriores. No copiar pasajes extensos.

## Nota

- Español claro y profesional, sin grandilocuencia, voseo ni afirmaciones que excedan fuentes.
- Mínimo 1.000 palabras, cuatro secciones sustantivas, tres fuentes y conclusión accionable.
- Integrar los hechos en un argumento; no encadenar resúmenes.
- Definir el primer uso de términos técnicos y explicar el impacto para una PyME.
- Incluir `## Preguntas frecuentes` con tres preguntas `###` y respuestas concretas.
- Front matter cerrado: versión 1, `draft: false`, slug e identidad únicos, descripción breve,
  fuente, portada local y texto alternativo útil.

## Gates y unidad atómica

- 2 o 3 noticias pasan de `pending` a `consumed` por la misma identidad editorial.
- La portada y el anuncio social existen, son legibles y sus hashes coinciden con el manifiesto.
- Enlaces críticos válidos, `editorial_style` GREEN, tests GREEN, Hugo GREEN y cero secretos.
- El árbol remoto contiene exactamente la cola actualizada, una nota, una portada, un anuncio,
  un manifiesto y un reporte. Cualquier fallo impide crear o actualizar la rama remota.
