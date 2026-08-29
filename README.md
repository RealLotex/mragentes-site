# MR Agentes

Sitio público de [mragentes.com.ar](https://mragentes.com.ar/) y automatización editorial
de MR Agentes. Hugo produce la web estática, GitHub Pages la publica y los flujos posteriores
distribuyen cada cambio validado a Meta y al servicio de Web Push.

El sistema está diseñado para operar con Codex, sus automatizaciones nativas, GitHub,
Cloudflare y Meta. Las cuatro automatizaciones editoriales están registradas, en estado
`ACTIVE` y configuradas con entorno de ejecución `local`; no necesita otro proceso local
permanente para publicar.

## Resultado operativo

- Una nota nueva cada miércoles y otra cada domingo: dos notas por semana.
- Relevamiento diario de noticias; una nota puede seleccionar noticias de días anteriores.
- Una pieza social original todos los días en Facebook e Instagram.
- Un anuncio social adicional de cada nota, después de comprobar que ya está desplegada.
- Una notificación push por nota y una notificación de bienvenida para cada alta nueva.
- Aplicación de Meta en modo `testing` hasta que el propietario decida promoverla.

Los horarios, recuperación y activación están en [OPERATIONS.md](OPERATIONS.md). Los límites
de cada componente están en [ARCHITECTURE.md](ARCHITECTURE.md) y el manejo de credenciales
en [SECURITY.md](SECURITY.md).

## Flujo de una publicación

1. Una automatización nativa de Codex ejecuta la skill correspondiente en el entorno local del
   proyecto.
2. La automatización genera únicamente artefactos permitidos y una rama `automation/**`.
3. `.github/workflows/automation-intake.yml` abre o reutiliza un pull request y solicita
   merge automático sólo después de CI.
4. Un merge a `main` ejecuta tests, compila Hugo y publica el artefacto en GitHub Pages.
5. El health gate confirma URL canónica, marcador de la nota e imagen pública.
6. Recién entonces GitHub Actions entrega el anuncio a Facebook e Instagram y solicita una
   única notificación al Cloudflare Worker.

Cada efecto remoto tiene identidad estable. Una reejecución reconcilia lo ya confirmado y
continúa sólo lo que falta; un resultado incierto se detiene para revisión.

## Estructura

```text
.agents/skills/              skills nativas para noticias, blog y social
.automation/
  schedules/                 contratos de las cuatro automatizaciones nativas de Codex
  schemas/                   schemas de noticias, notas y publicaciones sociales
  news/                      cola estructurada y reservas editoriales
  blog/                      estado transaccional de cada nota
  social/drafts/             borradores diarios cerrados por fecha
  reports/                   evidencia operativa sin secretos
.github/workflows/           CI, intake, Pages, Meta y notificaciones
assets/                      CSS y JavaScript procesados por Hugo
  js/push.js                 alta, renovación y baja de Web Push
content/notas/               fuente canónica de las notas publicadas
layouts/                     plantillas Hugo
scripts/automation/          validadores, detección, preflight y simuladores
scripts/notifications/       contrato cliente para una notificación por nota
scripts/social/              render, validación, entrega y ledger idempotente
static/
  images/stock/              imágenes editoriales públicas
  images/social/             recursos sociales diarios públicos
  sw.js                      recepción segura de Web Push
cf_worker.js                 Worker canónico de suscripciones y fan-out push
```

`public/` es un artefacto de build y no se versiona. Los assets de presentación que pasan por
Hugo Pipes viven en `assets/`; las imágenes que debe descargar Meta o un navegador viven en
`static/`.

## Desarrollo local

Requisitos:

- Python 3.12.
- Node.js 18.19 o superior.
- Hugo Extended 0.128.0, igual que el workflow de Pages.

Preparación reproducible:

```bash
python -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-test.lock.txt
npm ci
```

Verificación completa:

```bash
.venv/bin/python -m pytest -q
npm test
hugo --quiet --minify --baseURL https://mragentes.com.ar/ --destination /tmp/mragentes-build
```

Vista previa:

```bash
hugo server -D
```

Abrí `http://localhost:1313` y revisá como mínimo portada, servicios, índice de notas, una
nota y contacto a 390 px y 1440 px. No aceptes desborde horizontal, enlaces rotos ni una
imagen social ausente.

## Desarrollo por contratos

Todo cambio sigue PLAN → test RED → implementación → test GREEN → verificación proporcional.
Las suites Python cubren schemas, publicación, seguridad e independencia. Las suites de
JavaScript cubren Worker, cliente push y service worker. Una prueba local nunca habilita por
sí sola un efecto externo.

Comandos focalizados útiles:

```bash
.venv/bin/python -m pytest -q tests/static/test_runtime_independence.py
.venv/bin/python -m pytest -q tests/unit/social tests/contract/test_meta_api.py
npm test -- --run tests-js/push-client.test.mjs tests-js/service-worker.test.mjs
```

## Fuentes de verdad

- `main` es el estado publicable del sitio.
- `content/notas/*.md` define las notas; su `slug` explícito define la URL canónica.
- `.automation/schedules/*.json` define horario, skill, permisos y estado de cada tarea.
- `.automation/schemas/*.json` define la forma de los artefactos automáticos.
- Los entornos protegidos de GitHub contienen la configuración sensible.
- Cloudflare conserva suscripciones y estado de notificaciones; Meta conserva publicaciones.

No edites a mano una salida remota para “arreglar” el estado local. Usá el runbook de
reconciliación de [OPERATIONS.md](OPERATIONS.md).
