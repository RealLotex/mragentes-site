# Contrato editorial: noticia concreta, lenguaje claro

La calidad editorial no bloquea la publicación diaria. Estas pautas son recomendaciones;
el propietario ajusta su estándar en el prompt de la automatización. Si faltan novedades,
ampliar la ventana de búsqueda y publicar el mejor hecho verificable disponible.

## Selección

- Buscar hechos de IA publicados hoy o en los dos días anteriores; priorizar la actualidad
  mainstream y alternar proveedores y temas. La adopción en empresas argentinas es noticia
  cuando hay empresa, tecnología, fecha y evidencia identificables.
- Abrir la fuente primaria. Un portal como iProUP puede detectar un tema y aportar contexto,
  pero sus afirmaciones deben atribuirse. No inventar fechas, cifras, citas ni URLs.
- Una nota trata **un** hecho principal. Usar el mejor hecho verificable disponible ese día.

## Redacción

- Primer párrafo: quién hizo qué, cuándo y dónde. No reformular el título como introducción.
- Español formal, preciso y fácil de leer, sin voseo ni coloquialismos. Definir un término técnico
  sólo cuando sea necesario.
- Citar las cifras y afirmaciones cerca de su fuente. Identificar opiniones por nombre y cargo.
- Separar lo comprobado de lo que dice una empresa y de lo que todavía no se conoce.
- Extensión orientativa: 350–900 palabras, pocos subtítulos y párrafos de longitud variada.
- No añadir por rutina preguntas frecuentes, conclusión, “por qué importa” ni consejos para
  PyMEs. El análisis debe aportar un dato, una comparación verificable o una limitación concreta.

Prohibidas las aperturas “En este artículo exploraremos…”, los supuestos consensos sin fuente,
la grandilocuencia (“momento crucial”, “panorama cambiante”, “huella duradera”), las tendencias
amplias forzadas, los tríos vacíos, el tono de folleto y las frases de cierre que repiten la
nota. No usar sinónimos artificiales para evitar repetir un término técnico. No inventar citas.

## Entrega

El modelo sólo entrega un JSON y un JPG/PNG. El script fijo
`scripts/automation/editorial_release.py` controla formato, idempotencia, portada, front matter,
cola, hashes, anuncio social, escaneo, commit y PR. GitHub CI y `deploy.yml` controlan lo demás.
No exige antigüedad máxima, cita exacta de la URL primaria dentro del cuerpo, extensión editorial,
resolución mínima ni una fuente nueva. `skipped_valid` sólo corresponde a una nota ya registrada
en main para ese día. Los límites de seguridad y la confirmación de efectos externos se conservan.
