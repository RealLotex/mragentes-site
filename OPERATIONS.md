# Operación editorial

## Servicio esperado

La tarea `mr-agentes-noticias` corre todos los días a las 05:00 de `America/Cordoba`.
Inicia una conversación nueva con GPT-6 Luna xhigh. Intenta una noticia concreta publicada hoy o en los dos días
anteriores. Si la evidencia no alcanza, informa `skipped_valid`; si hay un bloqueo o un estado
remoto incierto, informa `needs_review`. Una nota integrada genera una publicación en Facebook,
una publicación en Instagram y un push luego de que la web esté disponible.

La computadora debe permanecer encendida y la aplicación de escritorio, abierta. La tarea usa el
proyecto local registrado `MR Agentes`; su ruta configurada debe resolver a un repositorio Git
existente. La publicación cotidiana depende de una sesión `gh` válida en el llavero del sistema.
Comprobar el acceso con `gh auth status` y el permiso de escritura con
`gh api repos/RealLotex/mragentes-site --jq .permissions.push`, sin mostrar credenciales.

## Qué hace cada corrida

1. El modelo busca durante unos minutos una noticia mainstream de IA: modelo, descubrimiento,
   seguridad de agentes, debate público, robótica o adopción empresarial argentina. Abre la
   fuente original; medios como iProUP ayudan a encontrar hechos, no sustituyen la verificación.
2. Redacta una sola nota, con el hecho en el primer párrafo, citas junto a los datos y una imagen
   pertinente. Guarda JSON e imagen fuera del repositorio. El ejemplo de formato está en
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

Una nota debe dejar datos memorables: nombres, fecha, cifras, mecanismo y límites. Debe poder
leerse sin conocimientos técnicos avanzados, conservando precisión. Evitar introducciones que
repiten el título, “en este artículo exploraremos”, reflexiones grandilocuentes, consenso sin
fuente, tono de folleto, tres elementos de relleno, preguntas frecuentes automáticas y un cierre
que sólo resume. No forzar una aplicación para PyMEs en cada noticia. La referencia completa está
en `references/editorial-contract.md` de la skill.

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
