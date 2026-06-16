# Problemas y Pendientes — Push Notifications

## 🚨 Problema Principal (NO RESUELTO)
**Las notificaciones push no llegan a los suscriptores.** El worker (`cf_worker.js`) está deployado en Cloudflare Workers, responde correctamente, procesa `/api/send/` con token, pero los envíos fallan:

- `sent:0, failed:4` (4 suscripciones en KV, 4 fallos)
- Las requests HTTP desde fuera del worker (curl) dan "Invalid token" aunque el token esté correcto en el secret del dashboard
- **Desde la consola del navegador** el worker sí acepta el mismo token y procesa el envío, pero da `failed` en todas las entregas

## 🔍 Hipótesis
1. **VAPID key mismatch:** Las suscripciones en el KV fueron creadas con la VAPID key **nueva** (del meta tag actualizado), pero el mapeo navegador/push-service puede estar usando la key con la que se registró originalmente. El worker envía con la key nueva via `env.VAPID_PRIVATE_KEY`.
2. **FCM vs Mozilla:** Las suscripciones son de FCM (Chrome Android). Quizás hay un paso extra de autenticación para FCM.
3. **El problema del token desde curl** podría ser encoding del body o headers. Investigar.

## 📋 Pendientes
- [ ] Hacer que el envío push funcione (debuggear por qué `fetch(endpoint)` devuelve error para suscripciones válidas)
- [ ] Probar con una suscripción de Firefox (Mozilla push) para comparar
- [ ] Agregar logging de error del push service (`await res.text()`) en `handleSend` para ver el código de error real
- [ ] Probar el envío directo desde Node con `web-push` contra una suscripción real del KV
- [ ] Si FCM requiere configuración adicional, documentarlo
- [ ] Agregar endpoint `/api/debug/token` en el worker para debuggear si el secret `API_TOKEN` se lee correctamente
- [ ] Cuando funcione, integrar el envío automático en `publish_daily.py` (enviar notificación cuando se publique una nota nueva)

## 📁 Archivos relevantes
- `cf_worker.js` (raíz del workspace) — Worker nuevo, RFC 8291 compliant
- `mragentes-web/static/js/push-notifications.js` — Frontend de suscripción
- `mragentes-web/layouts/_default/baseof.html` — Meta tag con VAPID public key
- VAPID keys generadas 2026-06-16 (nuevas, las viejas comprometidas)
