# Contrato editorial: noticia concreta, lenguaje claro

## Selección

- Buscar hechos de IA publicados hoy o en los dos días anteriores; priorizar la actualidad
  mainstream y alternar proveedores y temas. La adopción en empresas argentinas es noticia
  cuando hay empresa, tecnología, fecha y evidencia identificables.
- Abrir la fuente primaria. Un portal como iProUP puede detectar un tema y aportar contexto,
  pero sus afirmaciones deben atribuirse. No inventar fechas, cifras, citas ni URLs.
- Una nota trata **un** hecho principal. Si la evidencia no alcanza, no publicar relleno.

## Redacción

- Primer párrafo: quién hizo qué, cuándo y dónde. No reformular el título como introducción.
- Español formal, preciso y fácil de leer. Definir un término técnico sólo cuando sea necesario.
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
`scripts/automation/editorial_release.py` controla fecha, idempotencia, portada, front matter,
cola, hashes, anuncio social, escaneo, commit y PR. GitHub CI y `deploy.yml` controlan lo demás.
