# Contrato editorial: contar una historia para personas

La calidad editorial no bloquea la publicación diaria. Estas pautas orientan la escritura;
el propietario ajusta su estándar en el prompt de la automatización. Si faltan novedades,
ampliar la ventana de búsqueda y publicar la mejor historia verificable disponible.

## Selección

- Priorizar una noticia mainstream de IA de las últimas 48 horas que tenga una historia que
  contar: personas, un problema, decisiones, una solución, un conflicto o una consecuencia.
  La adopción empresarial argentina también puede aportar historias relevantes.
- Abrir la fuente original y buscar antecedentes, ejemplos y cobertura adicional cuando ayuden
  a comprender el tema. Verificar nombres, fechas, cifras y enlaces; atribuir las afirmaciones
  a quien las hace.
- Partir de un hecho principal y desarrollar los hechos relacionados que lo expliquen. La
  unidad de la historia permite incorporar contexto, voces y comparaciones pertinentes.

## Reconstruir la historia

Escribir para alguien que llega sin conocer el tema. Presentar a los protagonistas, el problema
previo, lo que hicieron y las consecuencias. Ubicar pronto al lector en la noticia y después
ordenar los antecedentes de manera que se entienda cómo se llegó hasta ahí. Una escena
documentada, un ejemplo revelador, un contraste o el hecho central pueden servir como apertura.

En un caso como el video de IA presentado ante un juez, el lector necesita comprender el
episodio que originó el proceso, quién produjo el video y con qué propósito, cómo intervino
en la decisión y qué resolvió la apelación. Esa secuencia humana y causal explica la noticia
mejor que repetir el fallo durante varios párrafos. En un lanzamiento tecnológico, reconstruir
el problema previo, explicar el mecanismo con un ejemplo y mostrar la diferencia concreta.

Las escenas, citas y experiencias se apoyan en fuentes reales. Distinguir hechos comprobados,
afirmaciones de una empresa y análisis propio. La incertidumbre se explica donde cambia la
interpretación de un hecho, sin convertir cada final en un inventario de datos que faltan.

## Retención: adaptación de los guiones de YouTube

YouTube recomienda cumplir pronto la expectativa creada por el título y sostener el interés
con valor y narración. El equipo de Theorist describe una progresión de apertura, hipótesis,
evidencia, giro y resolución. La adaptación al artículo consiste en tomar esos recursos con
flexibilidad; no imponer una plantilla audiovisual ni una cantidad fija de pasos.

- **Promesa y apertura:** un título atractivo y fiel, seguido de un comienzo que ya entregue
  información y deje claro por qué la historia merece atención.
- **Pregunta central:** una duda real, explícita o implícita, que el relato permita comprender:
  cómo se llegó a esa decisión, cómo funciona la propuesta o qué cambia para sus protagonistas.
- **Progresión:** cada tramo agrega un hecho, un antecedente, una explicación o una consecuencia.
  Las transiciones muestran relaciones de causa y efecto y conducen a la siguiente duda natural.
- **Ritmo:** alternar momentos concretos, ejemplos y explicación. Dar espacio a las partes que
  necesitan desarrollo y resolver con brevedad lo que ya está claro.
- **Contraste o giro:** aprovechar un cambio real o una evidencia que modifica lo que se creía,
  cuando exista en las fuentes. La curiosidad nace de los hechos y su interpretación.
- **Resolución:** responder la pregunta y dejar una comprensión nueva sobre lo que está en
  juego, las consecuencias o el próximo paso documentado.

La noticia y el resultado conocido se cuentan pronto. El lector sigue porque quiere entender
el cómo y el porqué. La aplicación de estas ideas a notas escritas es una decisión editorial;
las guías de video no demuestran por sí mismas una mejora de retención en el blog.

Fuentes: [guía de YouTube sobre interés y satisfacción](https://support.google.com/youtube/answer/16559650?hl=en)
y [patrones narrativos del equipo de Theorist](https://blog.youtube/creator-and-artist-stories/matpat-retirement/).

## Libertad de escritura, búsqueda y MR Agentes

Usar español natural, profesional y accesible. Elegir extensión, orden y subtítulos según la
historia. Explicar conceptos técnicos con ejemplos; incorporar antecedentes, mecanismos,
comparaciones y consecuencias respaldadas. El cuerpo debe aportar información y comprensión
que el título todavía no da. Integrar enlaces donde ayuden a comprobar o ampliar lo contado.

Un título descriptivo, un resumen útil, nombres completos y subtítulos claros facilitan que
personas y buscadores comprendan el tema. Responder las preguntas del lector dentro del relato
y usar los términos con naturalidad. Google recomienda contenido útil para personas; sus
funciones de búsqueda con IA mantienen esas prácticas. El objetivo es mejorar el descubrimiento
y la posibilidad de ser citado, sin prometer posiciones ni menciones en asistentes.

MR Agentes se posiciona con una mirada práctica sobre agentes de IA, automatización y trabajo,
cuando aporte a la historia. Consultar las páginas de servicios, nosotros y notas para enlazar
contenido propio relevante y describir la actividad real. Una mención o invitación breve puede
ser pertinente; el valor principal para la marca es que el lector quiera volver por lo aprendido.

Referencias de búsqueda: [contenido útil de Google](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)
y [funciones de IA de Google Search](https://developers.google.com/search/docs/appearance/ai-features).

## Entrega

El modelo sólo entrega un JSON y un JPG/PNG. El script fijo
`scripts/automation/editorial_release.py` controla formato, idempotencia, portada, front matter,
cola, hashes, anuncio social, escaneo, commit y PR. GitHub CI y `deploy.yml` controlan lo demás.
No exige antigüedad máxima, cita exacta de la URL primaria dentro del cuerpo, extensión editorial,
resolución mínima ni una fuente nueva. `skipped_valid` sólo corresponde a una nota ya registrada
en main para ese día. Los límites de seguridad y la confirmación de efectos externos se conservan.
