# HEARTBEAT

## Modo Nocturno (00:00 - 07:00 UTC-3)
Si estamos en horario nocturno, el cron "Modo Nocturno — Mejorar Slides cada 30min" está activo.
Tu trabajo es mejorar continuamente los templates de slides:
- Comparar output con los HTMLs del 9 de junio (estándar de calidad)
- Mejorar builders, CSS, colores (azul #2596be + índigo #8b5cf6)
- Probar cada cambio y guardar PNGs de comparación
- Commit al terminar cada mejora

## Modo Diurno (07:00 - 00:00 UTC-3)
- Revisar `social-manager/content/calendar-30days.md` para tareas de contenido
- El daily post cron se ejecuta a las 12:00 (publica carousel o single + stories)
- Single posts: usar layout "single" con datos, infografías, ofertas
- Carousels: variedad de layouts (hero, bullets_num, compare_v, bullets_cards, case, cta, timeline)
- Siempre publicar stories junto con cada post

## Estado
- **Rama única: `main`** (master eliminada local + origin tras unificación + purga 2026-08-10)
- **Token Meta: rotado** (long-lived nuevo, `expires_at:0`). Vive SOLO en `.env` local (ignorado) + secrets de GitHub. NUNCA committear. Permisos: `pages_manage_posts`, `pages_read_engagement`, `pages_manage_metadata`, `pages_show_list`.
- **Nota del blog → FB/IG viaja por GitHub Actions** al pushear `content/notas/*.md`. Si no aparece en FB: es caché o falló el álbum; verificar `is_published` + permalink con `GET /<post_id>?fields=id,is_published,permalink_url` (crear NO pedir `attachments{}` → deprecado).
- **Bug `publish-library` FIX 2026-08-10** (`a7c102d`): ahora registra en `state.json` → no duplica en cron.
- **Repo público** → 🛡️ no committear secretos (ver TOOLS.md → Seguridad)
- Cron nocturno: activo cada 30min (00-07h)
- Cron Web Nota Diaria (12:00): solo publica nota web (SIN web_note_to_social.py)
- Cron Social Manager Daily (13:00): publica siguiente día del calendario con --next. Única fuente de verdad para redes.
- RPG: v1.6 completo (29 módulos JS, 10 mapas, ~16 enemigos, PWA, arena, crafting, shop, 32+ logros)
- RPG: sin issues pendientes, todo compilando correctamente

## Pipeline de Publicaciones (v2 — 2026-06-19)
**Dos fuentes independientes:**
- 12:00 → Nota web + post social de la nota vía `web_note_to_social.py --full`
- 13:00 → Social Manager publica el próximo día del calendario en IG + FB
- NO hay cruce: web_posts van a `state.json.web_posts[]`, calendario usa `state.json.published[]`
- Todos los días del calendario tienen slide_details completas (hero + contenido + cta).
- Singles (Día 4, 7, 11, 14, 17, 21, 24, 30): usan content_db en social_manager.py, no necesitan slide_details.

## Fixes Record
- **2026-08-18:** 🐛 FIX "✖ No encontré la nota" en `social.yml` — el run de Actions del 16/08 (`31954463278`) falló porque el workflow pasa el slug del **filename** y `find()` solo matcheaba el slug del **título**. `find()` ahora matchea también por filename (con/sin prefijo de fecha). Nota del 16/08 publicada manualmente (FB `1202855116233616_122124240723359279`, IG `17978720585901868`, story `18115740364937185`) y registrada en state.json.
- **2026-08-15:** 🐛 FIX ANTI-DUPLICADO `publish-library` — se publicó `mito-chatbots` duplicado (~1 min tras el original, `92c8cc9`/cron #6495). Comando publicado 2 veces en la misma ventana. `publish-library` NO revisaba `state.json` antes de publicar (a diferencia de `publish-nota`). Agregada guardia de entrada: corta si la clave ya está registrada, con flag `--force` para republicar deliberadamente. **Regla: publish-library y publish-nota siempre abortan si la clave/slug ya está en state.json.**
- **2026-08-10:** 🛡️ SEGURIDAD — Purga total del historial (repo públício).
  1. Descubierto `FACEBOOK_ACCESS_TOKEN` real leakeado en historial (`META API TOKENS.txt`, commit ba7179b).
  2. Rotado token Meta (long-lived) vía fb_exchange_token; actualizados secrets GitHub (libsodium).
  3. Eliminada rama master (solo queda main) + tag de backup.
  4. Purga total del historial con `git filter-repo` + force-push (366→253 commits).
  5. Backup: `tmp/security_backup/repo_backup_20260810_111319.bundle`.
  6. Documentado en TOOLS.md (sección Seguridad) + AGENTS.md (red line secretos).
- **2026-06-14:** Badge (.cta-button) en layout single no tenía fondo azul — faltaba CSS class en CSS_SINGLE. FIX: agregado .cta-button a CSS_SINGLE con bg #2596be, padding 28px 60px, font-size 56px, border-radius 18px.
- **2026-06-14:** Cron daily post cambiado de sessionTarget:main (systemEvent) a isolated (agentTurn).
- **2026-06-14:** Catbox.moe timeout aumentado de 60s a 120s.
- **2026-06-14:** Social manager skill creada y aplicada.
- **2026-06-15:** Bridge web_note_to_social.py creado. Toma notas.md de mragentes-web, genera slides IG/FB automáticamente + publica. Integrado en social_manager.py via --web-post. Cron Web Nota actualizado para publicar web + social post.
- **2026-06-16:** Fix URL en web_note_to_social.py — slug con prefijo de fecha (YYYY-MM-DD-title) → slug limpio (title). Fix deduplicación — check en state.json antes de publicar, aborta si ya existe. Fix guard — --full solo guarda state si al menos una plataforma publicó OK. Limpiados duplicados en state.json. Timeout cron aumentado 300→420s.
- **2026-06-16:** ✨ Enriched diario — publish_daily.py ahora SIEMPRE investiga tendencias online reales + análisis propio (antes era cada 5 días). 3 formatos impredecibles. DEEP_ANALYSES sin card duplicado.
- **2026-06-18:** 🔥 FIX RADICAL — Calendar y social_manager overhaul:
  1. **Día 8**: agregadas slides detalladas a "3 tipos de Agentes IA" (antes: 0 slides → genéricos)
  2. **Día 9**: REEMPLAZADO tema duplicado → "Cómo un negocio recuperó 40 ventas perdidas en WhatsApp con IA" con slides completas
  3. **Cobertura total**: agregadas 11 entries nuevas al content_db del carrusel cubriendo días 10-30
  4. **Reglas en TOOLS.md**: item 5-8 documentan que CADA día debe tener slides detalladas y NUNCA repetir temas
  5. **Cron actualizado**: mensaje con instrucciones explícitas de verificación de contenido
  6. **Republicados Día 8 y 9** con contenido nuevo en FB (IG token 403)
  7. **30/30 días sin contenido genérico** — test automático pasa
