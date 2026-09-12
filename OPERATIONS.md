# Operación

## Servicio esperado

- Una nota diaria a las 18:00 de `America/Cordoba` cuando existan al menos dos hechos fiables.
- Una publicación en Facebook y una publicación en Instagram derivadas de esa nota.
- Un push por nota desplegada y una bienvenida al crear una suscripción.
- Cero publicaciones sociales diarias independientes.

## Calendario canónico

| Tarea | ID | Frecuencia | Skill | Sesión |
|---|---|---|---|---|
| MR Agentes — Editorial diario | `mr-agentes-noticias` | `0 18 * * *` | `mragentes-editorial-publisher` | conversación nueva + worktree |

Es una sola automatización nativa de Codex, activa todos los días y sin `catch_up`: si la
computadora estaba apagada no publica contenido atrasado automáticamente. Los antiguos registros
de blog, social y recuperación deben quedar pausados o eliminados después del cutover.

El worktree es un checkout temporal y aislado que Codex crea desde `origin/main`. Evita mezclar
la tarea programada con cambios humanos del checkout principal; no es otro servidor ni otro
clon que haya que mantener.

## Ejecución diaria

1. Codex abre una conversación nueva en el proyecto y un worktree limpio.
2. La skill investiga fuentes primarias, abre las páginas originales y actualiza la cola.
3. Deduplica y elige 2 o 3 ítems pendientes. Con menos de dos devuelve `skipped_valid`.
4. Reserva la identidad `editorial:YYYY-MM-DD` y comprueba que no exista la nota del día.
5. Redacta una nota original, enlaza la evidencia y crea una portada relevante.
6. Renderiza un único anuncio vertical con la plantilla `nota`.
7. Consume los ítems en la misma ejecución y crea manifiesto e informe.
8. Ejecuta guards, pruebas focalizadas, escaneo de secretos y Hugo.
9. El conector de GitHub crea un único commit en `automation/editorial/<run_id>` y un PR.
10. CI valida; el intake protegido integra el SHA exacto.
11. `deploy.yml` publica Pages y espera la disponibilidad real de nota e imagen.
12. Los jobs `publish_meta` y `notify_push` ejecutan los efectos idempotentes.

La automatización no hace merge, no usa git push local y no llama directamente a Meta o
Cloudflare. Toda la entrega editorial es una unidad: cola, nota, portada, anuncio, manifiesto e
informe.

## Verificación local antes del cutover

Desde un checkout limpio:

```bash
.venv/bin/python -m pytest -q
npm test
hugo --quiet --minify --baseURL https://mragentes.com.ar/ --destination /tmp/mragentes-build
.venv/bin/python scripts/scan_secrets.py --all
git diff --check
```

Verificar la portada, el archivo de notas y una nota individual en escritorio y móvil. Abrir
también el JPG de anuncio y confirmar marca, título legible, contraste y ausencia de recortes.

## GitHub

Confirmar sin leer valores:

- protección de `main` exige `Contract and site CI`;
- Pages usa GitHub Actions;
- existen `meta-testing`, `cloudflare-staging` y `cloudflare-production`;
- `meta-testing` contiene `META_ACCESS_TOKEN`, `FB_PAGE_ID` e `IG_USER_ID`;
- las Actions están fijadas por SHA;
- ningún job de pull request recibe secretos;
- sólo `automation/editorial/**` entra por `automation-intake.yml`.

El conector aplica `.automation/github/connector-egress.json`: sesión autenticada, árbol Git
atómico, fast-forward y un PR no borrador. Si el conector no confirma el resultado, detenerse en
`needs_review`; nunca recurrir a un push local.

## Qué significa `meta-testing`

`meta-testing` es un environment de GitHub que limita qué job puede recibir las credenciales de
Meta. Además, el código exige `META_ENVIRONMENT=testing`. Es una barrera fail-closed: permite
verificar la integración únicamente con los activos autorizados y no es producción abierta.

La aplicación de Meta permanece en modo testing hasta una decisión explícita del propietario.
Pasarla a producción requiere revisar permisos, destinatarios y una prueba RED→GREEN separada;
cambiar una variable por sí sola no lo autoriza.

`meta-preflight.yml` ejecuta `scripts.social.meta_preflight` con Graph `v26.0`. Es GET-only:
comprueba identidad, vínculo Facebook Page→Instagram y capacidad de reconciliación sin publicar.

## Verificación controlada de Meta

1. Ejecutar el preflight y confirmar sólo resultados booleanos.
2. Usar una nota real ya aprobada; no crear una pieza desechable.
3. Tras el health gate, revisar que `publish_meta` terminó `complete` con checkpoints de
   Facebook e Instagram.
4. Abrir ambos perfiles y comprobar visualmente imagen, texto y enlace.
5. Reejecutar el job con el mismo slug y SHA: debe reconciliar y crear cero duplicados.

Si una plataforma queda `uncertain`, no volver a publicar. Consultar publicaciones recientes por
hash/fecha y resolver manualmente. Un error `retryable` permite reejecutar sólo `publish_meta`;
la plataforma confirmada queda intacta.

## Cloudflare y Web Push

Auditar mediante el conector oficial:

- código activo equivalente a `cf_worker.js` del SHA probado; usar la versión activa informada por Cloudflare,
  no un número fijado en documentación;
- binding KV `PUSH_SUBS`, Durable Object/SQLite `NOTIFICATION_COORDINATOR` y secretos del Worker;
- CORS limitado a `https://mragentes.com.ar`;
- `/api/send/` devuelve 401 sin identidad y acepta el OIDC de GitHub esperado;
- logs y trazas redactan cabeceras, cuerpos y query strings sensibles.

Hay 8 suscripciones históricas. Algunas pueden conservar una URL `https://` legacy como clave;
el Worker lee esas entradas y `sub:v1:<sha256>`, deduplica y migra al recibir una alta válida.
No borrar las claves legacy hasta verificar la conversión.

## Recuperación

- Fallo antes del merge: corregir la misma rama/PR.
- Fallo de Pages o `wait_for_publication`: reejecutar el mismo `deploy.yml` y el mismo SHA cuando
  la web esté sana.
- Fallo Meta retryable: reejecutar sólo `publish_meta`.
- Fallo push retryable: reejecutar sólo `notify_push`; el `eventId` evita duplicados.
- Resultado externo incierto: detenerse, reconciliar y documentar; no ejecutar a ciegas.

No existe schedule de recuperación. GitHub conserva la ejecución, el SHA y los logs necesarios.

## Cutover de automatizaciones nativas

1. Actualizar el registro `mr-agentes-noticias`; no crear un duplicado.
2. Nombre: `MR Agentes — Editorial diario`.
3. Proyecto: `MR Agentes`; ejecución local, worktree dedicado, conversación nueva.
4. Frecuencia diaria 18:00 `America/Cordoba`; modelo y esfuerzo según `editorial.json`.
5. Prompt y skill idénticos al descriptor versionado.
6. Pausar los registros `mr-agentes-blog`, `mr-agentes-social-diario` y
   `mr-agentes-recuperaci-n-social` antes de activar el único registro.
7. Hacer una corrida manual controlada y registrar ID, SHA, PR, deploy y checkpoints.

La observación inicial dura 14 días: cada fecha debe terminar en nota o `skipped_valid`, nunca en
silencio. Registrar duración, fallos, duplicados y estado de las dos plataformas.
