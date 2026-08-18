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
./tmp/venv_social/bin/python -m scripts.social publish-library --key X  # Publicar pieza de biblioteca
./tmp/venv_social/bin/python -m scripts.social gallery                  # Muestrario 15 plantillas
```
> ⚠️ Usar `./tmp/venv_social/bin/python` (tiene las deps). El python del sistema no tiene pip.
> ⚠️ `publish-library` y `publish-nota` **abortan si la clave/slug ya está en `state.json`** (protege contra duplicados, como el caso del 2026-08-15). Para republicar a propósito usar `--force` — con cuidado, eso duplica en redes.

### Verificación de seguridad
```bash
python3 scripts/scan_secrets.py --all   # Escanea árbol + historial por secretos
```

### Known Issues (nuevo sistema)
- ⚠️ **2026-08-18 FIX: `publish-nota` "✖ No encontré la nota" en GitHub Actions**. El workflow `social.yml` detecta el slug desde el **filename** (`2026-08-16-openai-ya-...-enterprise`), pero `find()` matcheaba solo contra `nota.slug`, derivado del **título** (con tilde "volvió", "la-semana-en-que", "un-negocio-de-empresas"). El fix `1b3dee2` (slug desde el title, correcto para links) rompió la búsqueda por filename → el run del 16/08 falló y la nota quedó sin publicar en redes. FIX: `find()` en `scripts/social/notas.py` ahora acepta ambas identidades (slug del título O filename con/sin prefijo de fecha). **Lección: workflow y CLI usan identificadores distintos de la misma nota; `find()` debe ser tolerante a ambos.**
- ⚠️ **2026-08-15 FIX: `publish-library` guardia anti-duplicado de ENTRADA**. El 10/08 se arregló que registrara en state.json, pero todavía publicaba SIN revisar si la clave ya estaba → si el cron reintentaba o el comando se invocaba dos veces en la misma ventana, Facebook/IG recibían el post 2 veces (el duplicado aparecía ~1 min después del original). Ahora `publish-library` revisa `state.json` ANTES de publicar y aborta salvo `--force` (igual que `publish-nota`). Commit: ver `git log` tras el fix de hoy.
- ⚠️ **2026-08-10 FIX: `publish-library` registra en state.json** (era `cmd_publish_library`, no llamaba a `state.record` → duplicados en cron). Ahora lo hace igual que `publish-nota`, solo si al menos una plataforma publicó. Commit `a7c102d`.
- ⚠️ **Categorizar el error de Meta ANTES de tocar tokens** (método que ahorra tokens quemados):
  - `(#200) publish_actions ... deprecated` = **permiso de app/scope deprecado**, NO token vencido. Hay que regenerar token con `pages_manage_posts` + `pages_read_engagement` (+ `pages_manage_metadata` para stories). No hay fix de código.
  - `190 Session has expired` = token vencido (corto ~2h), regenerar long-lived (60 días).
  - Verificar permisos: `GET /debug_token?input_token=<tok>&access_token=<app_id|app_secret>` → mirar `scopes` y `expires_at` (0 = long-lived).
- ⚠️ **El token GitHub para actualizar secrets vive en `/tmp/git-creds`** (credential store: `https://<user>:<token>@github.com`). No hay `gh` CLI ni `GITHUB_TOKEN` en env. Para update de secrets: extraer de ese archivo (campo 3 con `awk -F'[:@]'`).
- ⚠️ Confiar en **prueba real** antes de dar por bueno un token: publicar un post de test y borrarlo (ver "prueba de publicación" abajo). `debug_token` solo dice que el token es válido, no que el permiso funcione.
- ⚠️ El dataclass `Result` de `publisher.py` usa `.network` (y `kind`/`ok`/`id`). NO existe `.platform` (error común al replicar el patrón de registro).
- ⚠️ `publish-nota` publica la nota como **álbum de fotos** (`facebook_album`, usa `/photos` con `published:false` + `/feed` con `attached_media`). Si la nota no aparece: verificar `is_published` y el permalink del post con `GET /<post_id>?fields=id,is_published,permalink_url` (NO pedir campos agregados tipo `attachments{...}` → dan `(#12) deprecate_post_aggregated_fields`).
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

### Flujo de relevamiento + notas (v5 — 2026-08-10)

> 📥 **Cola diaria:** `content/cola_diaria.md` — buffer de noticias relevantes detectadas CADA día. Las notas de Mié/Dom se redactan tomando lo mejor de esta cola, así no se pierde la noticia del día.
> La cola se commitea junto con la próxima nota (NUNCA con git restore que la borre: agregada al commit de la nota).

**Por qué:** con 2 notas/semana (Mié+Dom) hay margen para más calidad. El relevamiento es DIARIO (ticker de noticias, sin redactar); la investigación profunda + redacción solo los días de publicación. Sin subagentes: un solo contexto redacta de punta a punta para no perder coherencia.

### Cron
- **Nombre:** "Relevamiento diario de noticias IA (cola)"
- **Horario:** 18:00 TODOS los días (America/Cordoba)
- **Payload:** Escanea fuentes (La Nación, Infobae, iProUP, iProfesional, Ámbito, TechCrunch, The Verge, ArsTechnica, MIT Tech Review, VentureBeat, artificialintelligence-news.com, The Guardian), detecta 2-4 noticias relevantes del día y las agrega a `content/cola_diaria.md`. NO redacta, NO commitea, NO publica.
- **Timeout:** 420s | **Delivery:** none
- **Nombre:** "Web — Nota Diaria (Dom+Mié)"
- **Horario:** 12:00 mié + dom (America/Cordoba)
- **Payload:** Lee `content/cola_diaria.md` (FUENTE PRIMARIA), elige 2-3 noticias más relevantes → investigación profunda en 2 pasadas (bruta + selectiva con fetch) → redacta nota pseudo-académica con citas/links reales → valida → commit+push (incluye cola_diaria.md en el commit). El push dispara la publicación automática en FB+IG vía Actions.
- **Timeout:** 480s | **Delivery:** announce telegram | **Light context:** false
- **Nombre:** "Social Manager — Daily Post"
- **Horario:** 13:00 todos los días (America/Cordoba)
- **Payload:** (en migración — ver cron. El posteo de redes lo hace ahora GitHub Actions al pushear nota.)

---

---

## 🛡️ Seguridad — Lecciones 2026-08-10 (purga total del historial)

> ⚠️ **El repo `mragentes-site` es PÚBLICO** (sirve la web). Cualquier archivo con un secreto que se commitee queda expuesto al mundo en el historial, para siempre.

### Lo que pasó (para entender por qué)
- Un `FACEBOOK_ACCESS_TOKEN` real se coló en el repo hace meses (`META API TOKENS.txt`).
- El token quedó en el historial git. Como el repo es público, cualquiera lo ve.
- Se rotó el token (mitigación funcional) y luego se hizo **purga total del historial** con `git filter-repo` + force-push.

### Reglas NO negociables
1. **NUNCA committear secretos.** `.env`, `META API TOKENS.txt`, `config.local.json`, tokens, keys → todo en `.gitignore` y SOLO en disco local.
2. **Antes de `git add .`**, revisar que no haya archivos sospechosos: `git status` y buscar `.env`, `token`, `secret`, `TOKENS`.
3. **Un token que se pega en un chat/quedó en un commit está quemado** → rotarlo, no alcanza con "borrar el archivo".
4. **Repo público = asumí que el historial lo lee cualquiera.** Pensar antes de pushear.

### Cómo auditar secretos (rápido, pickaxe)
```bash
# Buscar un fragmento de token en TODO el historial (rápido, ~4s)
git log --all --oneline -S "<frag_15_chars>" --

# Buscar archivos con nombres sospechosos en todas las branches
for b in main; do git ls-tree -r $b --name-only | grep -iE "\.env$|token|secret|TOKENS|credential" | grep -v .example; done

# Script existente (árbol + historial)
python3 scripts/scan_secrets.py --all
```
> **Lección 2026-08-10:** el barrido lento es `git grep <frag>` por commit. El método CORRECTO y rápido es `git log --all -S <frag>` (pickaxe).

### Cómo rotar el token de Meta (long-lived) — flujo completo verificado 2026-08-10
```bash
# 1) Necesitás: FB_APP_ID + FB_APP_SECRET (en social-manager/.env) y un page token corto vivo
# 2) Generar long-lived (expires_at=0)
curl -s "https://graph.facebook.com/v25.0/oauth/access_token?grant_type=fb_exchange_token&client_id=${APP_ID}&client_secret=${APP_SECRET}&fb_exchange_token=${SHORT}"
# 3) Validar permisos (TIENE que incluir pages_manage_posts!)
curl -s "https://graph.facebook.com/v25.0/debug_token?input_token=${LONG}&access_token=${APP_ID}|${APP_SECRET}"
#    → scopes esperados: pages_manage_posts, pages_read_engagement, pages_manage_metadata, pages_show_list...
#    → expires_at: 0 = long-lived que no expira
```
**Antes de instalar el token, hacer PRUEBA REAL de publicación** (un post de test y borrarlo):
```bash
# POST /v25.0/<page_id>/feed con message → devuelve post_id (permite publicar = pages_manage_posts OK)
# DELETE /v25.0/<post_id> → devuelve success
```
Luego actualizar:
- `.env` local (raíz) → `META_ACCESS_TOKEN`
- **Secret de GitHub Actions** → vía API (ver abajo)

### Cómo actualizar un secret de GitHub Actions por API (no se puede leer)
> Los secrets de GitHub **NO se leen** por API (solo nombre + fecha). Se actualizan cifrando con la public key del repo (NaCl sealed box).
```python
# pip: pynacl
import base64, json, urllib.request, nacl.public
# 1) GET /repos/<repo>/actions/secrets/public-key  -> {key_id, key}
# 2) box = nacl.public.SealedBox(PublicKey(b64decode(key))); enc = box.encrypt(valor.encode())
# 3) PUT /repos/<repo>/actions/secrets/<NAME>  body={encrypted_value: b64(enc), key_id}
```

### Cómo hacer purga total del historial (último recurso, destructivo)
```bash
# 1) BACKUP completo del repo ANTES de tocar nada
mkdir -p tmp/security_backup && git bundle create tmp/security_backup/backup_$(date +%Y%m%d).bundle --all

# 2) Trabajar en un MIRROR aparte, NUNCA en el repo real
rm -rf tmp/purge_work && git clone --mirror . tmp/purge_work && cd tmp/purge_work

# 3) Purgar (filter-repo se instala con: pipx install git-filter-repo)
git filter-repo --force --invert-paths --path "META API TOKENS.txt" --path "archivo_secreto"
# (filter-repo borra el remote 'origin' a propósito; hay que re-agregarlo para pushear)

# 4) VERIFICAR el mirror: token ausente, estructura web intacta
#    git log --all -S <top-secret>  → vacío

# 5) Force-push desde el mirror al repo real
cd tmp/purge_work && git push --force https://TOKEN@github.com/<owner>/<repo>.git main:main

# 6) Reconstruir el repo local desde el historial purgado
cd <workspace> && git fetch origin && git reset --hard origin/main

# 7) Limpiar: rm -rf tmp/purge_work
```
> ⚠️ `git filter-repo` reescribe TODOS los SHAs del historial → cualquier clon/referencia vieja queda inválida. Por eso el backup con `git bundle` es obligatorio.
> ⚠️ GitHub guarda caché de los commits viejos (forks, búsqueda) un tiempo. Reportar el secret en **Settings → Security → Secret scanning** para que GitHub lo invalide.

### Lección: nunca rebasear historial con duplicados
- Este repo tuvo 2 ramas (main + master) con commits intercalados/duplicados por un bundle de backup.
- Intentar `git rebase origin/main` sobre una rama local con 126 commits duplicados generó conflictos de add/add (AGENTS.md, TOOLS.md…).
- **Fix:** abortar el rebase y regenerar `main` desde origin: `git switch -C main origin/main`. NO reaplicar commits duplicados a mano.

### Estado actual post-purga (2026-08-10)
- Rama única: `main` (master eliminada local + origin). Sin tags.
- `git filter-repo` purgó `META API TOKENS.txt` y `cf_worker_hardcoded_token.js` → 366→253 commits.
- Secrets de GitHub: `META_ACCESS_TOKEN` (rotado), `FB_PAGE_ID`, `IG_USER_ID` sincronizados con `.env`.
- Backup disponible: `tmp/security_backup/repo_backup_20260810_111319.bundle` (323 MB).

---

Add whatever helps you do your job. This is your cheat sheet.
