# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics.

## Instagram Posts

- Skill: `skills/instagram-post/SKILL.md`
- Reglas de marca: `brand/INSTAGRAM-BRAND.md` (consultar solo al generar posts)
- **⚠️ SIEMPRE usar `gen_slide.py` — NUNCA escribir HTML a mano**
- **Script de referencia:** `skills/instagram-post/scripts/gen_slide.py` (generó los PNGs del 9 de junio, estándar de calidad)
- ⚠️ NO usar `scripts/gen_slide.py` (versión legacy simple, sin brand ni layouts)
- Generar slides con: `python3 skills/instagram-post/scripts/gen_slide.py --json '<json_plan>' output/carpeta_destino/`
- El JSON debe incluir un array de objetos con `layout` y los campos del builder correspondiente
- Layouts disponibles: `hero`, `bullets`, `bullets_cards`, `bullets_num`, `compare_v`, `multi-body`, `case`, `cta`, `timeline`, `single`, `single_img`
- Layouts de story: `story_hook`, `story_content`, `story_cta`
- El script aplica TODAS las reglas de marca automáticamente (colores, fuentes 46px+, backgrounds, logos)
- NO editar el HTML generado manualmente; si hay que ajustar, modificar el JSON y re-renderear
- El social manager (`social-manager/scripts/social_manager.py`) usa este mismo script vía `GEN_SLIDE`

---

## Social Manager — SISTEMA NUEVO v2 (desde 2026-08-08)

> ⚠️ El sistema viejo (`social-manager/scripts/social_manager.py` + `day_NN.json` + catbox) quedó **OBSOLETO**. Rama `master` eliminada. El contenido que publica ahora sale de las notas del blog.

**Cómo funciona (pipeline nuevo):**
1. La nota se escribe en `content/notas/<slug>.md` (raíz del repo).
2. Push a `main` en `content/notas/*.md` dispara `.github/workflows/social.yml`.
3. Actions compone las piezas (carrusel 4:5 + historia 9:16) y publica en FB + IG automáticamente.
4. `state.json` evita repetir.

**No hay que publicar manualmente** — alcanza con pushear la nota.

### Credenciales
- **Actions**: secrets `META_ACCESS_TOKEN`, `FB_PAGE_ID`, `IG_USER_ID` (cifrados en GitHub).
- **Local**: `.env` en la **RAÍZ del workspace** con esas mismas claves.
- ⚠️ Tokens de Meta son de corta duración (~2h). Si falla con `Session has expired`, regenerar token **long-lived (60 días)** en Graph API Explorer → Exchange.

### Comandos
```bash
cd /home/openclaw/.openclaw/workspace
./tmp/venv_social/bin/python -m scripts.social doctor                    # Diagnóstico
./tmp/venv_social/bin/python -m scripts.social publish-nota --slug X --dry-run  # Renderizar sin publicar
./tmp/venv_social/bin/python -m scripts.social publish-nota --latest    # Publicar última
./tmp/venv_social/bin/python -m scripts.social gallery                  # Muestrario 15 plantillas
```
> ⚠️ Usar `./tmp/venv_social/bin/python` (tiene las deps). El python del sistema no tiene pip.

### Verificación de seguridad
```bash
python3 scripts/scan_secrets.py --all   # Escanea árbol + historial por secretos
```

### Known Issues (nuevo sistema)
- Tokens Meta de corta duración → expiran a las ~2h; requerir long-lived (60 días).
- El workflow `social.yml` corre en nube de GitHub (no local); usa los secrets, no el `.env` local.
- Borrar post IG requiere token con `instagram_content_publish` (no disponible)
- Cron MUST use `sessionTarget: "isolated"` + `payload.kind: "agentTurn"`
- Publicación IG single post: esperar 3-5s entre crear media y publicar (processing time)
---

## DeepSeek V4 Flash — Responses API + Thinking (2026-08-02)

- **Modelo:** `deepseek/deepseek-v4-flash` (checkpoint 0731) — id de API es `deepseek-v4-flash`, NO existe `deepseek-v4-flash-0731` como id separado
- **Adapter:** `api: "openai-responses"` (endpoint `https://api.deepseek.com/responses`) — el 0731 es el primer modelo DeepSeek con Responses API nativa
- **Reasoning:** `reasoning: true` + `compat.supportedReasoningEfforts: ["low", "high", "max"]` — DeepSeek acepta low/high/max (no medium/xhigh)
- **Thinking por defecto:** `max` en `agents.defaults.thinkingDefault` y todos los agentes
- **⚠️ Lección clave:** si `model.reasoning: false`, OpenClaw NO envía `reasoning_effort` (ni en completions ni en responses) → el thinking ≠ off falla con GatewayClientRequestError. Para habilitar thinking real, el modelo debe tener `reasoning: true` + `compat.supportsReasoningEffort: true`
- v4-pro/chat/reasoner siguen con `api: "openai-completions"` (pro soporta Responses recién en early August)

---

## ⚠️ Lección 2026-08-09: state.json se revierte con git restore

- `social-manager/content/state.json` está trackeado en git y sus actualizaciones diarias (web_posts) NO se commitean → cualquier `git checkout/restore` en el workspace lo revierte a la versión vieja y pierde el historial de posts
- **Síntoma:** el estado queda cortado (ej: publicado hasta 19/06) y el cron social puede republicar duplicados
- **Fix aplicado:** reconstruido desde outputs/memory y commiteado (`bfc5e8b`)
- **Regla:** si tocás state.json (o cualquier archivo de estado), commitearlo para que no se pierda en un restore

## Push Notifications

- **Worker:** `cf_worker.js` (raíz del workspace)
- **Deploy:** `bash mragentes-web/scripts/deploy_worker.sh`
- **Secrets (wrangler):** `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `API_TOKEN`
- **Debug:** `https://mragentes-push.rosichmarcos.workers.dev/api/debug/status`
- **Test:**
  ```bash
  curl -X POST https://mragentes-push.rosichmarcos.workers.dev/api/send/ \
    -H "Content-Type: application/json" \
    -d '{"token":"$TOKEN","title":"Test","body":"Hola","url":"https://mragentes.com.ar/"}'
  ```
- **Problema:** API_TOKEN en Cloudflare no coincide con config.local.json. Necesita `wrangler login` + deploy.
- **Suscripciones viejas:** Expiradas por cambio de VAPID keys. Usar `/api/debug/clear-all` para limpiar.

---

## Web — Nota Diaria (mragentes.com.ar)

> 📌 **El repo = raíz del workspace.** `content/`, `layouts/`, `static/`, `scripts/` están en `/home/openclaw/.openclaw/workspace/` (NO en `mragentes-web/`). `mragentes-web/` es un clon viejo desincronizado — NO usarlo para notas nuevas.

- **Script nota:** `scripts/publish_daily.py` (raíz) / `scripts/publish_blog.py`
- **Notas:** `content/notas/<slug>.md` (fuente de verdad → se despliega a GitHub Pages)
- **Social:** al pushear nota a `main`, Actions publica en FB+IG (`.github/workflows/social.yml`)
- **Énete nuevos": `scripts/social/` + `scripts/scan_secrets.py`
- **State nota:** `scripts/.publish_state.json`
- **Browser cache:** `scripts/_browser_enrich.json` + `scripts/_last_trends.json`

### Fuentes de investigación (2026-06-21)
**Argentinas:** La Nación, Ámbito, iProUP, Infobae, iProfesional
**Globales IT/IA:** TechCrunch, The Verge, ArsTechnica, Wired, MIT Technology Review, VentureBeat, ZDNet, CNET, The Next Web, Analytics Vidhya, Towards Data Science
**Finanzas:** Bloomberg, Forbes, Yahoo Finance
**Especializadas:** artificialintelligence-news.com

### CLI
```
python3 scripts/publish_daily.py                          # Publicar
python3 scripts/publish_daily.py --dry-run                # Solo crear
python3 scripts/publish_daily.py --force                  # Sobreescribir
python3 scripts/publish_daily.py --browser-enrich         # Generar nota + guardar URLs para enriquecer
python3 scripts/publish_daily.py --browser-enrich --force           # Forzar + enriquecer
```

### Flujo completo de nota (v4 — 2026-08-08)

```
# Paso 1: Generar nota (investiga + escribe content/notas/<slug>.md)
python3 scripts/publish_daily.py --browser-enrich --force

# Paso 2: ENRIQUECER — NO saltarse este paso
# 2a. web_search para encontrar URL real de cada artículo
# 2b. web_fetch en URL real para obtener contenido completo
# 2c. Extraer datos concretos, cifras, citas textuales

# Paso 3: REESCRIBIR — NO editar, reescribir desde cero
# - Título provocativo basado en contenido REAL
# - Citas textuales en >blockquote
# - 3-5 párrafos por artículo con datos verificables
# - Conclusión unificada propia
# - Links a URLs reales (no Google News)

# Paso 4: Commit y push DESDE LA RAÍZ DEL WORKSPACE (= repo)
cd /home/openclaw/.openclaw/workspace
git add content/notas/ static/images/ && git commit -m "📝 Nota diaria: [título]" && git push origin main
# 👉 El push dispara .github/workflows/social.yml que publica en FB+IG automáticamente

# Paso 5: Verificar online
curl -s -o /dev/null -w "%{http_code}" "https://mragentes.com.ar/notas/[slug]/"
```

> ⚠️ El push a `main` de una nota en `content/notas/*.md` **dispara la publicación automática en Instagram + Facebook** vía Actions. Ya no har falta correr social_manager manualmente.

### 📰 Estándar de calidad — No negociable
1. **NOTA PSEUDO-ACADÉMICA** — Reflexiva, analítica, puntos de vista impredecibles. SIN límite de extensión.
2. **🚫 PROHIBIDO** — Frases genéricas como "aborda un tema relevante", "desde nuestra perspectiva", etc.
3. **✅ OBLIGATORIO** — web_search + web_fetch para cada artículo. Citas textuales con datos verificables.
4. **🔗 Links reales** — a URL del sitio de origen, no a Google News.
5. **📷 Imágenes únicas** — No repetir hasta agotar catálogo (~17 imágenes).
6. **Fallback investigación** — Reintento 1 vez, luego calendario rotativo.
7. **Commit + push automático** → GitHub Pages deploy.

### Catálogo de imágenes (17 disponibles)
Originales: `automation.jpg`, `data-analytics.jpg`, `digital-world.jpg`, `ai-brain.jpg`
Pexels batch 2026-06-18: 14 imágenes con IDs 8386440, 8566472, 8438918, 8441272, 1181675, 1181354, 1181373, 1181390, 1181408, 1181304, 1181267, 1181401, 1181671, 1181672
    
⚠️ **Si se agregan imágenes manualmente:** agregar el filename a `STOCK_IMAGES` en `publish_daily.py` y su alt text a `_generate_image_alt()`.

### Cron
- **Nombre:** "Web — Nota Diaria"
- **Horario:** 12:00 todos los días (America/Cordoba)
- **Payload:** Investiga, escribe `content/notas/<slug>.md`, commitea y pushea a `main`. El push dispara la publicación automática en FB+IG vía Actions.
- **Timeout:** 480s | **Delivery:** announce telegram | **Light context:** false
- **Nombre:** "Social Manager — Daily Post"
- **Horario:** 13:00 todos los días (America/Cordoba)
- **Payload:** (en migración — ver cron. El posteo de redes lo hace ahora GitHub Actions al pushear nota.)

---

Add whatever helps you do your job. This is your cheat sheet.
