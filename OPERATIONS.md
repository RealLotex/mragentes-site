# Operación

Este runbook cubre la operación diaria del sitio, las notas, las imágenes sociales y Web Push.
La zona horaria de negocio es siempre `America/Cordoba`; no conviertas los horarios a UTC en
los prompts ni dependas de la zona horaria del runner.

## Objetivo de servicio

- Publicar una nota cada miércoles y otra cada domingo: dos notas por semana.
- Enviar una notificación push por cada nota, sólo después de verla desplegada.
- Mantener el push de bienvenida al crear una suscripción.
- Publicar una pieza original todos los días en Facebook e Instagram.
- Anunciar también cada nota en ambas redes; miércoles y domingo pueden tener la pieza diaria y
  el anuncio de nota como eventos distintos.
- Mantener la aplicación de Meta en `testing`.
- Gestionar código y contenido con Codex, sus automatizaciones nativas y GitHub sin servidores
  propios.

## Calendario canónico

| Tarea | ID nativo | Horario local | Cron de referencia | Skill | Salida |
|---|---|---:|---|---|---|
| MR Agentes — Noticias | `mr-agentes-noticias` | todos los días 18:00 | `0 18 * * *` | `mragentes-news-scout` | cola verificada |
| MR Agentes — Blog | `mr-agentes-blog` | miércoles y domingo 12:00 | `0 12 * * 0,3` | `mragentes-blog-publisher` | nota + imagen |
| MR Agentes — Social diario | `mr-agentes-social-diario` | todos los días 15:00 | `0 15 * * *` | `mragentes-social-manager` | draft + imagen |
| MR Agentes — Recuperación social | `mr-agentes-recuperaci-n-social` | todos los días 15:15 | `15 15 * * *` | `mragentes-social-manager` | diagnóstico/recuperación |

Los descriptores completos viven en `.automation/schedules/`. El cron sólo sirve como contrato
legible; el registro se realiza como automatización nativa de Codex. Las cuatro definiciones
están registradas una sola vez, se muestran como `ACTIVE` en Codex y usan el entorno de ejecución
`local`. En los descriptores esto corresponde a `status: "active"`, `registered: true` y
`execution_environment: "local"`. `catch_up` permanece en `false`: encender la computadora más
tarde no debe crear publicaciones atrasadas sin revisión.

El orden diario es intencional. La nota de las 12:00 usa la cola acumulada, incluida información
de días anteriores. Social prepara su pieza a las 15:00 y la recuperación la revisa a las 15:15.
El relevamiento de las 18:00 alimenta próximas notas.

## Responsabilidades

| Capa | Hace | No hace |
|---|---|---|
| automatización Codex | investigar, redactar, renderizar, validar, crear rama | usar secretos o publicar remoto |
| pull request + CI | revisar schemas, hashes, tests, build y seguridad | aceptar artefactos inválidos |
| GitHub Pages | servir el sitio generado desde `main` | disparar antes de CI |
| workflow Meta | reconciliar y entregar a Facebook/Instagram | generar contenido nuevo |
| workflow push | pedir un evento por nota desplegada | administrar suscriptores |
| Cloudflare Worker | alta/baja, bienvenida, dedupe y fan-out | redactar notas |
| Codex + conectores | mantener tareas y proveedor, auditar, reparar | guardar secretos en el repo |

## Verificación de puesta en marcha

Las cuatro automatizaciones ya están registradas y `ACTIVE`. Usá los pasos siguientes para
auditar ese estado o recuperar la configuración sin crear definiciones duplicadas.

### 1. Estado local y pruebas

Desde la raíz:

```bash
.venv/bin/python -m pytest -q
npm test
hugo --quiet --minify --baseURL https://mragentes.com.ar/ --destination /tmp/mragentes-build
.venv/bin/python scripts/scan_secrets.py --all
git diff --check
```

El resultado requerido es cero fallos, cero advertencias de Hugo y cero secretos. Revisá además
portada, servicios, notas, una nota individual y contacto en viewport móvil y escritorio.

### 2. GitHub

Verificá sin leer valores:

- branch protection de `main` exige CI y permite auto-merge;
- Pages usa GitHub Actions como source;
- los environments `meta-testing`, `cloudflare-staging` y `cloudflare-production` existen;
- `meta-testing` expone `META_ACCESS_TOKEN`, `FB_PAGE_ID`, `IG_USER_ID`;
- `cloudflare-production` expone el secret `PUSH_API_TOKEN` y la variable
  `PUSH_WORKER_URL`;
- las actions siguen fijadas por SHA;
- ningún workflow de pull request recibe estos secretos.

Las automatizaciones escriben únicamente mediante `.automation/github/connector-egress.json`:
un commit remoto atómico por ejecución (`create_blob`, `create_tree`, `create_commit`,
`update_ref`), ramas `automation/**` y fast-forward sin force. El push activa
`automation-intake.yml`, que abre o reutiliza el PR; el merge se hace sólo desde el
`workflow_run` confiable después de CI y con `--match-head-commit`. Si el conector no está
disponible, el resultado correcto es `needs_review`; no se habilita `git push local`.

No ejecutes una publicación para comprobar sólo “presencia”. Los workflows y preflight deben
fallar cerrados si falta configuración.

### 3. Cloudflare

Con el MCP oficial de Cloudflare (sesión OAuth Full Access administrada por el proveedor), auditá
el Worker que sirve `PUSH_WORKER_URL` y confirmá:

- código desplegado equivalente a `cf_worker.js` del SHA probado (versión activa 42);
- binding KV `PUSH_SUBS`;
- binding SQLite `NOTIFICATION_COORDINATOR` para el coordinador idempotente;
- secrets `API_TOKEN` y `VAPID_PRIVATE_KEY`;
- clave `VAPID_PUBLIC_KEY` coincidente con el meta del sitio;
- CORS limitado a `https://mragentes.com.ar`;
- rutas `/api/subscribe/`, `/api/unsubscribe/` y `/api/send/`;
- observabilidad disponible sin cuerpos ni cabeceras sensibles.

El namespace `PUSH_SUBS` conserva 8 suscripciones activas históricas (ocho en total). Sus claves actuales son
URLs legacy, con objetos Web Push directos; el código nuevo también reconoce `sub:v1:<sha256>` y
deduplica ambos formatos. No migres ni borres las legacy mientras no exista una verificación
posterior: una alta válida las convierte de forma perezosa y una baja elimina ambas copias.
La auditoría posterior al despliegue debe devolver 404 para los endpoints debug retirados, 401
para `/api/send/` sin bearer, 204 CORS sólo para el origen del sitio y 403 para otros orígenes.

El release pasa primero por los tests de `.github/workflows/push-worker.yml`, luego staging y
recién después por el handoff del conector. No instales un publicador alternativo.

### 4. Meta

Confirmá en el panel de Meta y en GitHub que:

- la aplicación continúa en modo testing;
- Facebook Page e Instagram profesional pertenecen al mismo conjunto autorizado;
- el token tiene sólo los permisos necesarios y no expiró;
- `META_ENVIRONMENT=testing` llega al job;
- una consulta de identidad controlada devuelve exactamente los activos esperados.

`meta-preflight.yml` ejecuta `scripts.social.meta_preflight` en `meta-testing` con Graph `v26.0`.
Es una comprobación GET-only de identidad, vínculo Page→Instagram y lecturas de reconciliación;
no crea contenedores, no hace POST y devuelve sólo booleanos. Se puede lanzar manualmente o al
cambiar ese contrato en `main`, sin publicar una pieza de prueba.

La primera prueba remota debe usar contenido identificable de test y activos autorizados. Si la
política no permite eliminar en ambas plataformas, no publiques una pieza desechable: usá el
modo de validación sin efecto y después el primer evento real aprobado.

### 5. Verificar automatizaciones nativas de Codex

En el administrador nativo de Codex, listá el proyecto `MR Agentes` y compará cada registro con
su descriptor de `.automation/schedules/`. Los IDs de la tabla son estables: no recrees una
automatización para corregir sólo un campo.

1. confirmá que existen exactamente los cuatro `automation_id` de la tabla, sin duplicados;
2. confirmá proyecto `MR Agentes`, `execution_environment: "local"`, timezone, RRULE, modelo,
   effort, skill y prompt;
3. confirmá que cada automatización usa este repositorio, su `branch_template` y sólo los
   prefijos de `permissions.repository_writes`;
4. confirmá `external_publish: false` y `catch_up: false`;
5. confirmá que las cuatro continúan `ACTIVE`;
6. registrá ID, próxima ejecución y estado en el reporte operativo.

El registro se gestiona en esta computadora; GitHub y los proveedores conservan los efectos ya
integrados aunque la aplicación esté cerrada después de generar una rama.

## Ejecución normal

### Relevamiento diario

La automatización de las 18:00:

1. consulta fuentes permitidas y abre la página original;
2. comprueba fecha, URL, título y evidencia;
3. normaliza y deduplica contra la cola estructurada;
4. agrega sólo noticias pertinentes, incluso si servirán días después;
5. valida el schema y escribe un reporte sin contenido sensible;
6. publica una rama `automation/news/{run_id}`.

No redacta una nota, no toca social y no produce efectos externos. Si no hay hallazgos válidos,
el resultado correcto es `skipped_valid`, no contenido de relleno.

### Nota de miércoles o domingo

La automatización de las 12:00:

1. determina fecha local y reserva `blog:{fecha}`;
2. lee noticias pendientes de hoy o días previos;
3. investiga las seleccionadas en fuentes primarias;
4. redacta una nota original con enlaces verificables;
5. asigna slug explícito, una fotografía relevante de stock (Pexels o Unsplash) y alt útil; esa
   portada alimenta como fondo la plantilla social `nota`;
6. valida front matter, URL, asset, enlaces, calidad editorial e índice;
7. genera un único cambio atómico en `content/notas/`, `static/images/stock/` y estado
   permitido;
8. publica `automation/blog/{run_id}`.

No llama a Meta o Cloudflare. El anuncio y el push nacen del cambio recién agregado a `main`, no
del reloj. Por eso una reejecución del job editorial no puede duplicar efectos.

### Social diario

La automatización de las 15:00:

1. reserva `daily_owned:{fecha}`;
2. elige un tema y una composición distinta de los anuncios de notas;
3. renderiza el recurso bajo `static/images/social/`;
4. produce `.automation/social/drafts/YYYY-MM-DD-daily-owned.json`;
5. calcula `topic_hash`, `content_hash`, hash del asset y `dedupe_key`;
6. valida captions distintos para Facebook e Instagram;
7. publica `automation/social/{run_id}` sin llamar a Meta.

Al integrarse, deploy detecta el draft agregado y despacha `social-daily.yml` con esa ruta exacta.
La URL de la imagen debe ser pública antes de que Meta intente descargarla.

### Recuperación de las 15:15

La automatización de recuperación no genera otra pieza. Inspecciona la identidad de hoy, workflow y
ledger:

- si ambas plataformas están confirmadas, informa `skipped`;
- si una está confirmada y otra tiene fallo retryable, prepara sólo la faltante;
- si existe timeout o evidencia contradictoria, informa `needs_review` y no repite;
- si falta el draft, informa el bloqueo; no inventa uno durante recuperación.

La recuperación es idempotente: usa la misma fecha, hash y `dedupe_key` del intento original.

## Integración, despliegue y fan-out

### Intake

Un push a `automation/news/**`, `automation/blog/**` o `automation/social/**` activa
`automation-intake.yml`. El workflow reutiliza el PR si existe y solicita auto-merge con squash.
No empuja directamente a `main` ni evita CI.

### Pages

Todo cambio integrado ejecuta `deploy.yml`. Las suites pasan antes de Hugo; Pages recibe sólo el
artefacto `public/`. `scripts/automation/detect_changes.py` clasifica exclusivamente notas y
drafts recién agregados. Modificar una nota existente no se interpreta como una nota nueva.

### Efectos de una nota

Después del deploy, `wait_for_publication.py` debe confirmar:

- respuesta 2xx del mismo origen;
- URL canónica `/notas/{slug}/`;
- marcador/título de la nota esperada;
- imagen stock 2xx, con tipo y tamaño válidos;
- ausencia de redirects a otro host.

Por cada slug aprobado se despachan:

- `social-note.yml`, con `note_slug` y `deploy_sha`;
- `notify-note.yml`, con los mismos datos.

El evento push usa una clave como `blog-note:{fecha}:{slug}`. El Worker acepta repetir exactamente
esa identidad y hash como duplicado; rechaza la misma identidad con otro payload.

### Push de bienvenida

El cliente registra o revalida la suscripción con `/api/subscribe/`. El Worker agenda bienvenida
únicamente cuando crea una suscripción nueva. Una renovación de la misma suscripción no vuelve a
saludar. Si falla el registro remoto, el cliente revierte la suscripción local para no mostrar un
estado engañoso.

## Verificación diaria

Usá este orden, sin publicar manualmente para “probar”:

1. automatización de Codex: estado, run ID, rama y reporte;
2. pull request: CI y auto-merge;
3. Pages: workflow y URL pública;
4. health gate: slug e imagen confirmados;
5. Meta: workflow, ID/permalink por plataforma y ausencia de duplicados;
6. push: workflow, evento completo/duplicado y métricas del Worker;
7. recuperación: `skipped`, `complete`, `partial` o `needs_review` con causa clasificada.

No copies captions, tokens o cuerpos de suscripción a reportes. Los hashes y IDs remotos bastan.

## Runbooks de incidentes

### No se creó una rama automática

1. Confirmá que la automatización estaba `ACTIVE` y que la PC estaba activa a la hora prevista.
2. Compará task ID, timezone, próxima ejecución, skill y prompt con el descriptor.
3. Leé el reporte local y clasificá `skipped_valid`, validación, red o permiso.
4. Si la fecha aún corresponde y el evento sigue siendo deseado, ejecutá una vez la misma tarea
   con la misma fecha/run ID; no crees otra definición programada.
5. Si la ventana pasó, no hagas catch-up automático: decidí explícitamente si corresponde una
   publicación tardía.

### PR abierto pero sin merge

1. Abrí el check fallido y reproducilo localmente.
2. Corregí mediante RED→GREEN en la misma rama.
3. No cierres y recrees el PR para evitar un check.
4. Si sólo espera branch protection o aprobación, no empujes a `main` manualmente.

### Pages falló o la nota no aparece

1. Confirmá CI, build, deploy y SHA en ese orden.
2. Ejecutá el health gate contra el slug exacto.
3. Diferenciá propagación, canonical incorrecto, marcador ausente, imagen inválida y redirect.
4. Reejecutá el deploy del mismo SHA sólo después de corregir una causa o esperar propagación.
5. Confirmá que no se dispararon Meta ni push; si se dispararon pese al gate fallido, tratá el
   caso como incidente de arquitectura.

### Falta Facebook o Instagram

1. Identificá `kind`, fecha, `dedupe_key`, plataforma y estado del workflow.
2. Si una plataforma está confirmada, preservá ese checkpoint.
3. Consultá publicaciones recientes por ventana temporal y hash de caption.
4. Si hay una coincidencia única, reconciliá el ID/permalink y completá sin publicar.
5. Si no hay coincidencia y el error es retryable, reejecutá el workflow con los mismos inputs.
6. Si hay cero o múltiples coincidencias después de un timeout incierto, marcá `needs_review`.

Nunca uses opciones de fuerza ni cambies el caption/asset conservando la misma identidad.

### No llegó el push de una nota

1. Confirmá que la URL pasó el health gate.
2. Revisá `notify-note.yml` y su clasificación, sin mostrar el bearer.
3. Buscá en Cloudflare el `eventId` exacto y su `payloadHash`.
4. Si no existe y el fallo fue retryable, reejecutá con el mismo slug y SHA.
5. Si está completo o duplicado, no repitas: revisá estado de la suscripción/navegador.
6. Si el ID existe con otro hash, detené el flujo y corregí el conflicto.

Respuestas `404` o `410` del proveedor push eliminan la suscripción vencida; no son motivo para
recrear envíos globales.

### Falló la bienvenida

La bienvenida es best-effort y no debe bloquear el alta. Confirmá que fue una suscripción nueva,
que el Worker agendó `welcomeScheduled` y que el endpoint no expiró. Revalidar no debe crear otra
bienvenida. Probá cambios del flujo en staging con una suscripción descartable autorizada.

### Se sospecha un secreto expuesto

Pausá environments/tareas afectados, rotá en el proveedor, actualizá GitHub o Cloudflare sin
mostrar el valor y seguí `SECURITY.md`. No intentes ocultarlo sólo con un commit posterior.

## Mantenimiento

### Cambios del sitio

Todo cambio de contenido, layout, estilo o script entra por PR y se verifica con Hugo y navegador.
No subas `public/`. Conservá `image`, `image_alt` y `slug` de las notas porque alimentan SEO,
social y push.

### Cambios de skills o schedules

Actualizá descriptor, skill, tests de contrato y este runbook juntos. Después editá la
automatización real desde Codex conservando su `automation_id`, volvé a listar y compará. No
dejes dos definiciones activas durante una migración.

### Cambios del Worker

Escribí tests JavaScript RED, implementá GREEN, ejecutá suite completa, validá staging y usá el
conector de Cloudflare para producción. Confirmá bindings y secretos por nombre, nunca por valor.

### Rotación de credenciales

Rotá de a una frontera. Instalá el nuevo valor protegido, verificá una operación mínima autorizada
y recién entonces revocá el anterior si el proveedor requiere solapamiento. Registrá fecha,
autoridad y resultado, no el secreto.

## Pausa y rollback

Las cuatro automatizaciones permanecen `ACTIVE` durante la operación normal. Para detener nueva
generación durante un incidente, cambialas temporalmente a `PAUSED`; esto no afecta el sitio ya
publicado. Para detener efectos remotos, deshabilitá temporalmente los environments protegidos o
sus workflows con una revisión explícita. No borres suscripciones, posts ni historial como parte
de una pausa.

Un rollback web redeploya un SHA previamente probado mediante GitHub. Antes, verificá si el SHA
contiene eventos nuevos: volver atrás la web no despublica Meta ni revierte un push ya entregado.
Esos sistemas requieren reconciliación separada.

## Criterio de operación al 100%

El cutover termina cuando:

- suites Python, JavaScript y Hugo están GREEN;
- los cuatro schedules conservan sus IDs, están registrados una sola vez, `ACTIVE` y en entorno
  `local`;
- branch protection, auto-merge y Pages funcionan;
- Meta testing confirma Facebook e Instagram sin duplicados;
- Cloudflare confirma alta, baja, bienvenida y una notificación de nota idempotente;
- una simulación de reruns prueba cero duplicados y recuperación parcial;
- se completan 14 días de shadow/soak con reportes válidos;
- no existe dependencia de cuentas, procesos ni archivos retirados.

Hasta completar el soak temporal, el software puede estar implementado y activo, pero el gate de
confiabilidad de 14 días sigue pendiente y debe informarse como tal.
