# SECURITY.md — Runbook de Seguridad (mragentes-site)

> **⚠️ Este repositorio es PÚBLICO** y sirve mragentes.com.ar. Todo lo que se commitea
> queda visible para siempre en el historial. Actuá en consecuencia.

Última actualización: 2026-08-10 (tras la purga total del historial).

---

## Contexto del incidente (2026-08-10)

- Un `FACEBOOK_ACCESS_TOKEN` real estaba leakeado en el historial (archivo
  `META API TOKENS.txt`, commit `ba7179b`, de junio).
- El repo es público → el token quedó expuesto al mundo.
- Mitigación en dos capas:
  1. **Rotación** del token (se regeneró un long-lived nuevo vía
     `fb_exchange_token`; el viejo quedó muerto).
  2. **Purga total** del historial con `git filter-repo` + force-push
     (366 → 253 commits).
- Estado final: rama única `main`, token nuevo en `.env` local + secrets GitHub,
  token viejo fuera del historial.

---

## Reglas no negociables

1. **NUNCA committear secretos.** `.env`, `META API TOKENS.txt`, tokens, keys,
   archivos `*hardcoded*` → siempre en `.gitignore`, solo en disco local y en
   los secrets de GitHub (o secrets del proveedor).
2. **Antes de `git add`/`git commit`**: revisá `git status` y confirmá que no
   entran archivos con credenciales.
3. **Un token que pasó por un chat, un log o un commit quedó quemado** →
   rotarlo. No alcanza con borrar el archivo.
4. **Nunca pegar tokens completos en conversaciones** — referenciá por
   fragmento inicial o por longitud.
5. **Repo público = asumí que el historial lo lee cualquiera.**

## Auditoría de secretos

```bash
# Buscar un fragmento de token en TODO el historial (rápido, pickaxe)
git log --all --oneline -S "<frag_15_chars>" --

# Buscar archivos con nombres sospechosos
for b in main; do git ls-tree -r $b --name-only | grep -iE "\.env$|token|secret|TOKENS|credential" | grep -v .example; done

# Script existente (árbol + historial)
python3 scripts/scan_secrets.py --all
```

> Método rápido y correcto: `git log -S` (pickaxe). El barrido `git grep` por
> commit es lento.

## Rotación de token de Meta (long-lived)

```bash
# Necesitás: FB_APP_ID + FB_APP_SECRET (en social-manager/.env) + short-lived token
curl -s "https://graph.facebook.com/v25.0/oauth/access_token?grant_type=fb_exchange_token&client_id=${APP_ID}&client_secret=${APP_SECRET}&fb_exchange_token=${SHORT}"
# Devuelve un access_token long-lived (expires_at=0 en debug_token)

# Validar
curl -s "https://graph.facebook.com/v25.0/debug_token?input_token=<NUEVO>&access_token=<APP_ID>|<APP_SECRET>"
```

Actualizar en: `.env` local (raíz) y el secret de GitHub Actions.

## Actualizar secret de GitHub Actions (no se puede leer)

Los secrets de GitHub NO se leen por API (solo nombre + fecha). Se actualizan
cifrando con la public key del repo (NaCl sealed box):

```python
# pip: pynacl
import base64, json, urllib.request, nacl.public
# 1) GET /repos/<repo>/actions/secrets/public-key -> {key_id, key}
# 2) box = nacl.public.SealedBox(PublicKey(b64decode(key)))
#    enc = box.encrypt(valor.encode())
# 3) PUT /repos/<repo>/actions/secrets/<NAME>
#    body = {"encrypted_value": b64encode(enc), "key_id": key_id}
```

## Purga total del historial (destructivo — último recurso)

```bash
# 1) BACKUP COMPLETO obligatorio
mkdir -p tmp/security_backup
git bundle create tmp/security_backup/backup_$(date +%Y%m%d).bundle --all

# 2) Trabajar en un MIRROR aparte (nunca en el repo real)
rm -rf tmp/purge_work && git clone --mirror . tmp/purge_work && cd tmp/purge_work

# 3) Instalar y ejecutar filter-repo
#    pipx install git-filter-repo
git filter-repo --force --invert-paths --path "META API TOKENS.txt" --path "<otro_archivo>"

# 4) VERIFICAR: token ausente + estructura web intacta
git log --all -S "<top_secret>" --          # -> vacío
git ls-tree --name-only main | grep "<estructura esperada>"

# 5) Force-push desde el mirror
cd tmp/purge_work && git push --force https://TOKEN@github.com/<owner>/<repo>.git main:main

# 6) Reconstruir el repo local
cd <workspace> && git fetch origin && git reset --hard origin/main

# 7) Limpiar
rm -rf tmp/purge_work
```

> ⚠️ filter-repo reescribe TODOS los SHAs. Cualquier clon/referencia vieja queda
> inválida → por eso el backup es obligatorio.
> ⚠️ GitHub mantiene caché de commits viejos (forks/búsqueda). Reportar el
> secreto en **Settings → Security → Secret scanning** para que GitHub lo invalide.

## Recordatorio operativo

- Rama única: `main`.
- Git token embebido en el remote local (URL con `ghp_...`): rotarlo por higiene.
- Backup del estado pre-purga: `tmp/security_backup/repo_backup_20260810_111319.bundle`.
