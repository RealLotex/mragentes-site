# Operación editorial

## Servicio esperado

La tarea `mr-agentes-noticias` corre todos los días a las 05:00 de `America/Cordoba`.
Inicia una conversación nueva con GPT-6 Luna xhigh. Publica una nota cada día; la actualidad de
los dos días anteriores es una preferencia editorial. La calidad editorial no bloquea la
publicación diaria. El propietario administra su estándar mediante el prompt de la tarea.
`skipped_valid` sólo corresponde a una nota del día ya registrada en main. Si hay un error
técnico o un estado remoto incierto, informa `needs_review`. Una nota integrada genera una publicación en Facebook,
una publicación en Instagram y un push luego de que la web esté disponible.

La computadora debe permanecer encendida y la aplicación de escritorio, abierta. La tarea usa el
proyecto local registrado `MR Agentes`; su ruta configurada debe resolver a un repositorio Git
existente. La publicación cotidiana depende de una sesión `gh` válida en el llavero del sistema.
Comprobar el acceso con `gh auth status` y el permiso de escritura con
`gh api repos/RealLotex/mragentes-site --jq .permissions.push`, sin mostrar credenciales.

## Qué hace cada corrida

1. El modelo investiga una noticia mainstream de IA y sus antecedentes: modelo, descubrimiento,
   seguridad de agentes, debate público, robótica o adopción empresarial argentina. Abre la
   fuente original; medios como iProUP ayudan a encontrar hechos, no sustituyen la verificación.
2. Redacta una sola nota que ubique pronto al lector y reconstruya la historia, sus antecedentes
   y su importancia, con fuentes y una imagen pertinente. Guarda JSON e imagen fuera del
   repositorio. El ejemplo de formato está en
   `.agents/skills/mragentes-editorial-publisher/assets/note-template.md`.
3. Ejecuta `python3 scripts/automation/editorial_release.py --input /var/tmp/nota.json --image /var/tmp/portada.jpg`.
   El comando controla idempotencia, validación, worktree, seis artefactos, commit, push y PR.
   Espera hasta que termine el despliegue y los envíos externos. Sólo `published:` confirma
   publicación; una URL de PR por sí sola no es el resultado final.
4. GitHub ejecuta CI, merge protegido y `deploy.yml`. Pages publica la nota. Después del health
   gate, los jobs `publish_meta` y `notify_push` hacen los efectos externos.

El modelo no abre ni modifica ramas a mano. No hay segundo intento programado ni otra tarea
social independiente. El script no llama directamente a Meta o Cloudflare.

## Estilo editorial

La prioridad editorial es Argentina. Buscá hechos sobre empresas, pymes, universidades, investigación, trabajo, agro, industria y políticas públicas del país. Antes de elegir, compará al menos cinco candidatos por impacto concreto, novedad, utilidad para usuarios o empresas, alcance y evidencia disponible. Priorizá productos que ya se pueden usar, integraciones MCP y agentes que actúan sobre servicios reales, adopción empresarial y cambios que afectan dinero, trabajo o productividad. El MCP de IOL InvertirOnline es un ejemplo del tipo de historia relevante: una capacidad disponible y sus consecuencias, con límites y permisos verificables. Las jornadas, cursos, efemérides y anuncios institucionales quedan detrás de novedades de mayor impacto; sólo elegirlos si hay un resultado o consecuencia excepcional comprobable.

Buscá en varias familias de fuentes: iProUP, El Cronista/Infotechnology, Ámbito, La Nación Tecnología y medios especializados argentinos como Infotecnología o ITSitio. Contrastá con fuentes originales: páginas de producto, documentación técnica, comunicados y responsables de empresas argentinas, fintechs, bancos, proveedores de software y organismos. Buscá también por nombres de productos y términos como MCP, agentes, integraciones y automatización, sin depender de un único medio ni de resultados genéricos sobre IA. Detectá contenido patrocinado y no lo cuentes como corroboración independiente. Registrá en el resumen de la corrida los cinco candidatos con URL, fecha del hecho, fecha de publicación, consecuencia y motivo de selección o descarte. Consultá las notas recientes para evitar repetir temas. La fecha del hecho importa más que la actualización de una página: no presentes un lanzamiento anterior como de hoy. Si faltan novedades recientes, ampliá la ventana de búsqueda local; una herramienta relevante de semanas anteriores puede superar una jornada de ayer. Elegí una noticia internacional sólo cuando tenga impacto concreto y verificable en Argentina y explicá esa relación desde la apertura. No inventes una conexión argentina. La calidad editorial no bloquea la publicación diaria: elegí la mejor historia verificable y publicá.

Una edición adicional sólo se prepara por pedido explícito del propietario con
`--edition <identificador>` (por ejemplo, `--edition iol-mcp`). Conserva la fecha real,
la nota diaria y el límite de seis rutas; usa una rama y un informe propios con el sufijo
del identificador. Repetir el mismo identificador no crea otra entrega; si pertenece a otra
nota, devuelve `needs_review`. No uses --edition en la corrida diaria ni para eludir un
resultado remoto incierto. No se agrega otra tarea programada.

La nota se escribe para una persona que no conoce el tema. Debe permitir reconstruir qué pasó,
quiénes participaron, cómo se llegó a la noticia y qué cambia. El interés se sostiene con
información nueva, ejemplos y explicaciones, con libertad de tono, extensión y estructura.
Se adaptan recursos de los guiones de YouTube: cumplir la promesa del título desde la apertura,
desarrollar una pregunta central, avanzar mediante causas y consecuencias y resolver al cierre.
Los hechos conocidos se cuentan pronto; las escenas y los giros se apoyan en las fuentes.

El reconocimiento de MR Agentes se construye con análisis práctico útil y enlaces internos
pertinentes. Los títulos descriptivos, las entidades claras y las respuestas integradas en el
relato ayudan a lectores y buscadores a comprender el contenido. Son objetivos editoriales,
sin cuotas ni validadores de calidad. La referencia completa está en
`references/editorial-contract.md` de la skill. El prompt de la tarea nativa y su copia en
`.automation/schedules/editorial.json` contienen las mismas instrucciones.

Estas pautas orientan la redacción y no autorizan omitir el día. El publicador admite una
fuente anterior o reutilizada, un cuerpo sin la URL primaria y una portada pequeña válida.
El resumen se adapta automáticamente al límite de 160 caracteres de los metadatos; el cuerpo
y el título publicado conservan su extensión. Los controles de JSON, URLs públicas, archivos
válidos, secretos, idempotencia y confirmación de entrega siguen siendo técnicos.

## Verificación y recuperación

- `python3 scripts/automation/editorial_release.py --input ... --image ... --dry-run` prepara y
  valida los seis archivos en un worktree temporal; muestra su ruta y no crea PR.
- `python3 -m pytest -q` y `npm test` ejecutan las suites locales. CI vuelve a ejecutarlas antes
  del merge. El build de Hugo ocurre en el pipeline de Pages.
- Si el script informa que la rama de la fecha existe con un PR abierto, usar ese PR. Si existe
  sin PR, revisar la rama; no crear otra publicación para el mismo día.
- Un error de CI deja el PR abierto para corregirlo. El intake sólo integra el SHA que aprobó CI.
- Si Pages o el health gate fallan, reejecutar el mismo `deploy.yml` después de corregir la causa.
- Si Meta o push informan un resultado incierto, reconciliar los IDs y logs antes de reintentar.

El environment de GitHub `meta-testing` limita las credenciales de Facebook e Instagram. La aplicación de
Meta sigue en modo testing; no es producción abierta. `meta-preflight.yml` ejecuta
`scripts.social.meta_preflight` con Graph `v26.0` y sólo operaciones GET-only. Tras un despliegue,
verificar los checkpoints de Facebook e Instagram y el resultado de `notify_push`.

Para Cloudflare, confirmar la versión activa informada por Cloudflare y los bindings
`PUSH_SUBS` y `NOTIFICATION_COORDINATOR`. Las 8 suscripciones históricas pueden incluir claves
`https://` legacy; conservarlas mientras se migran a `sub:v1:<sha256>`.

Los registros `mr-agentes-blog`, `mr-agentes-social-diario` y
`mr-agentes-recuperaci-n-social` permanecen pausados. No agregar otro cron para compensar una
falla de esta tarea: corregir el comando o el PR identificado por fecha.

Las notas nuevas llevan la fecha local a las 00:00 para que Hugo no las oculte como futuras
durante la publicación de las 05:00. Las notas anteriores fechadas al mediodía siguen siendo
válidas. Si un despliegue se interrumpe después del merge, identificar el rango exacto y
repetir `deploy.yml` sólo después de verificar que los efectos externos aún no se enviaron.
