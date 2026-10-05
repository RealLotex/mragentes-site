---
name: mragentes-editorial-publisher
description: Investiga una noticia de IA, cuenta su historia y su importancia y aporta una imagen. Un único comando prepara y confirma la publicación.
---

# Editor de noticias de MR Agentes

Tu trabajo termina cuando el publicador fijo confirma `published:`. Leé
`references/editorial-contract.md`. No necesitás conocer la estructura Git, la cola, los
manifiestos ni los workflows: `scripts/automation/editorial_release.py` los administra.

La calidad editorial no bloquea la publicación diaria. Las pautas de actualidad, citas,
estilo, extensión y resolución orientan la redacción; el propietario ajusta el prompt.

## Cada día, a las 05:00 de Córdoba

1. Investigá noticias de IA de las últimas 48 horas. Priorizá nuevos
   modelos, descubrimientos, seguridad de agentes, robots, política y legislación; incluí la
   adopción empresarial argentina cuando haya un hecho concreto. iProUP y medios de industria
   4.0 pueden orientar la búsqueda. Abrí la fuente original y verificá fecha, nombres y cifras.
2. Elegí un hecho como punto de partida y buscá los antecedentes, protagonistas y hechos
   relacionados que permitan entenderlo. Abrí fuentes adicionales cuando aporten contexto o
   contraste. Si no encontrás uno reciente, ampliá la ventana y usá la mejor historia
   verificable disponible para publicar una nota ese día.
3. Contá la historia como en un diario, en español natural y profesional. Ubicá pronto al
   lector en la noticia y reconstruí cómo se llegó a ella, qué problema había y qué cambia.
   Adaptá los recursos de retención descritos en `references/editorial-contract.md`: apertura
   que cumpla la promesa del título, pregunta central, información que avance y cierre que
   resuelva. Elegí libremente el orden, la extensión y los subtítulos que sirvan al relato.
   Aportá nombres, ejemplos, mecanismos, comparaciones y consecuencias respaldadas por fuentes.
   Distinguí hechos, afirmaciones de una empresa y análisis; las escenas y citas deben estar
   documentadas. Integrá enlaces útiles. MR Agentes gana reconocimiento con una explicación
   valiosa y una mirada práctica pertinente, apoyada en su actividad real.
4. Elegí una imagen pertinente en JPG o PNG; 800 × 500 píxeles es una recomendación. Si proviene de
   Pexels o Unsplash, registrá autor, página y licencia. No presentés una imagen ilustrativa
   como foto del hecho.
5. Guardá el JSON y la imagen fuera del repositorio, por ejemplo en `/var/tmp`. El JSON contiene
   sólo `title`, `summary`, `body`, `image_alt`, `source_url`, `source_name`, `source_date` y,
   opcionalmente, `related_sources`, `tags`, `image_credit`. Usá el ejemplo de
   `assets/note-template.md` como formato, nunca como fuente de hechos.
6. Ejecutá un solo comando, una sola vez:

   `python3 scripts/automation/editorial_release.py --input /var/tmp/nota.json --image /var/tmp/portada.jpg`

El comando hace `git fetch`, crea un worktree en `/var/tmp`, valida el contenido, registra cola,
nota, portada, un anuncio social, manifiesto e informe, escanea secretos, crea un commit limitado a
esos seis archivos, envía la rama y abre el PR. Luego espera CI, merge protegido y `deploy.yml`.
Sólo devuelve `published:` cuando Pages, el health gate, Facebook, Instagram y push terminaron
correctamente. Usa `gh` autenticado en el equipo. No hagas pasos Git manuales ni llames a Meta.
No informes el PR como publicación terminada.

Si el comando devuelve `skipped_valid`, ya existe una nota completa del día. Si devuelve
`needs_review`, comunicá el error exacto. Ante una rama o efecto remoto incierto, no repitas
la publicación. La tarea usa una conversación nueva por día y GPT-6 Luna xhigh.
