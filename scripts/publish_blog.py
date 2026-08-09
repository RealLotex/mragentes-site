#!/usr/bin/env python3
"""
Publicador de blog MR Agentes — v2 simplificada.
Toma un JSON generado por el agente y crea la nota en Hugo + push.

El agente se encarga de:
  - Investigar tendencias
  - Buscar/descargar imagen
  - Escribir el contenido

Este script solo hace:
  - Copiar imagen al directorio de stock
  - Crear archivo Hugo .md
  - git commit + push
  - Enviar notificación push (si está configurado)
  - Trackear estado

Uso:
  python3 scripts/publish_blog.py post.json
  python3 scripts/publish_blog.py post.json --dry-run
  python3 scripts/publish_blog.py post.json --force  # sobrescribir nota del día
"""

import os
import sys
import json
import shutil
import subprocess
import datetime
import re
import argparse
import urllib.parse
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_DIR = os.path.join(BASE_DIR, "content", "notas")
STOCK_DIR = os.path.join(BASE_DIR, "static", "images", "stock")
STATE_FILE = os.path.join(BASE_DIR, "scripts", ".publish_state.json")
STOCK_IMAGES_DIR = "/images/stock/"

# ─── Utilidades ────────────────────────────────────────────────────────────

def slugify(text):
    """Convertir texto a slug URL-friendly."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\sáéíóúñ-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:80]


def load_state():
    """Cargar estado desde archivo JSON."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"used_images": [], "published": []}


def save_state(state):
    """Guardar estado a archivo JSON."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _generate_image_alt(image_filename):
    """Alt text genérico para imágenes (el agente puede sobrescribir)."""
    return f"Imagen ilustrativa de automatización e inteligencia artificial por MR Agentes"


# ─── Core ──────────────────────────────────────────────────────────────────

def create_nota(title, body, tags, image_filename, description=None, image_alt=None):
    """Crear archivo Hugo .md en content/notas/."""
    today = datetime.date.today()
    slug = slugify(title)
    filename = f"{today.isoformat()}-{slug}.md"
    filepath = os.path.join(CONTENT_DIR, filename)

    tags_yaml = "\n".join([f"  - {t}" for t in tags])
    if description is None:
        description = title

    alt = image_alt or _generate_image_alt(image_filename)
    content = f"""---
title: "{title}"
date: {today.isoformat()}
description: "{description}"
image: "{STOCK_IMAGES_DIR}{image_filename}"
image_alt: "{alt}"
tags:
{tags_yaml}
---

{body}
"""
    os.makedirs(CONTENT_DIR, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ Nota creada: {filename}")
    return filepath


def copy_image_to_stock(image_path):
    """Copiar imagen al directorio de stock con nombre único basado en fecha."""
    if not image_path or not os.path.exists(image_path):
        print("⚠️  Imagen no encontrada o ruta vacía. La nota se crea sin imagen.")
        return None

    today = datetime.date.today().strftime("%Y%m%d")
    ext = os.path.splitext(image_path)[1] or ".jpg"
    dest_name = f"daily-{today}{ext}"
    dest_path = os.path.join(STOCK_DIR, dest_name)

    os.makedirs(STOCK_DIR, exist_ok=True)
    shutil.copy2(image_path, dest_path)
    print(f"📷 Imagen copiada: {dest_name}")
    return dest_name


def git_commit_push(filepath, title):
    """Commit y push de la nueva nota al repo."""
    original_cwd = os.getcwd()
    try:
        os.chdir(BASE_DIR)

        subprocess.run(["git", "add", filepath], check=True, capture_output=True)

        # También agregar la imagen si se copió
        subprocess.run(
            ["git", "add", os.path.join("static", "images", "stock")],
            check=True, capture_output=True
        )

        commit_msg = f"📝 Nueva nota: {title}"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            check=True, capture_output=True
        )

        result = subprocess.run(
            ["git", "push", "origin", "main"],
            check=True, capture_output=True, text=True
        )

        print(f"✅ Push exitoso: {commit_msg}")
        return True

    except subprocess.CalledProcessError as e:
        err = e.stderr
        if isinstance(err, bytes):
            err = err.decode()
        print(f"❌ Error en git: {err}")
        return False
    finally:
        os.chdir(original_cwd)


def _load_dotenv():
    """Carga el .env de la raíz (si existe) para que las claves salgan de ahí."""
    try:
        from scripts.social.config import load_dotenv
    except ImportError:
        sys.path.insert(0, BASE_DIR)
        try:
            from scripts.social.config import load_dotenv
        except ImportError:
            return
    load_dotenv()


def send_push_notification(title, filepath):
    """Enviar notificación push a suscriptores vía Cloudflare Worker."""
    _load_dotenv()
    config_file = os.path.join(BASE_DIR, "scripts", "config.local.json")
    config = {}
    if os.path.exists(config_file):
        try:
            with open(config_file) as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    worker_url = config.get("pushWorkerUrl", "") or os.environ.get("PUSH_WORKER_URL", "")
    api_token = config.get("pushApiToken", "") or os.environ.get("PUSH_API_TOKEN", "")

    if not worker_url or not api_token:
        print("  ℹ️  Push notification no configurada")
        return

    # La URL sale del nombre del archivo, que es de donde Hugo saca el permalink
    # (/notas/:slug/ con :slug = nombre del .md, fecha incluida). Derivarla del
    # título dejaba afuera la fecha y el aviso llevaba a una página que no existe.
    slug = os.path.splitext(os.path.basename(filepath))[0]
    url = f"https://mragentes.com.ar/notas/{urllib.parse.quote(slug)}/"
    
    # Short title: max 7 words
    words = title.split()
    short_title = ' '.join(words[:7])
    if len(words) > 7:
        short_title += '…'

    try:
        import urllib.request
        payload = json.dumps({
            "token": api_token,
            "title": short_title,
            "body": "Accedé para leer esta nota en nuestra web.",
            "url": url,
        }).encode()
        req = urllib.request.Request(
            f"{worker_url}/api/send/",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            sent = result.get('sent', 0)
            failed = result.get('failed', 0)
            print(f"  🔔 Push: {sent} enviadas, {failed} fallidas")
    except Exception as e:
        print(f"  ⚠️  Push notification error: {e}")


def announce_on_social(filepath):
    """Aviso de nota nueva en Facebook e Instagram (ver scripts/social/).

    Compone las piezas con la imagen de portada de la nota. Publica desde acá
    sólo si SOCIAL_LOCAL_PUBLISH=1; si no, lo hace el workflow de GitHub.
    Nunca corta el flujo: la nota ya está en la web.
    """
    try:
        from scripts.social.hook import announce
    except ImportError:
        sys.path.insert(0, BASE_DIR)  # la raíz del repo, para que `scripts` sea paquete
        try:
            from scripts.social.hook import announce
        except ImportError as exc:
            print(f"  ⚠️  Redes: no pude cargar el social manager ({exc})")
            return
    announce(filepath)


# ─── MAIN ─────────────────────────────────────────────────────────────────

def publish_blog_post(json_path, dry_run=False, force=False):
    """Publicar nota de blog desde un JSON generado por el agente.

    Formato JSON:
    {
      "title": "Título de la nota",
      "description": "Meta description (opcional, se usa title si no está)",
      "tags": ["ia", "automatizacion", "tendencias"],
      "image": "/path/a/imagen_descargada.jpg",
      "image_alt": "Alt text para la imagen (opcional)",
      "body": "## Contenido en markdown\\n\\nTexto..."
    }
    """
    with open(json_path) as f:
        data = json.load(f)

    title = data.get("title", "").strip()
    body = data.get("body", "").strip()
    tags = data.get("tags", [])
    image_path = data.get("image", "")
    description = data.get("description", "")
    image_alt = data.get("image_alt", "")

    if not title:
        print("❌ El JSON no tiene título.")
        return False
    if not body:
        print("❌ El JSON no tiene body.")
        return False

    print(f"\n📝 Nota: {title}")
    print(f"   Tags: {', '.join(tags) if tags else '(ninguno)'}")

    # Verificar si ya existe nota hoy
    if not force:
        today_str = datetime.date.today().isoformat()
        existing = [f for f in os.listdir(CONTENT_DIR)
                    if f.startswith(today_str) and f.endswith(".md")]
        if existing:
            print(f"⚠️  Ya existe nota para hoy ({existing[0]}). Usá --force para sobrescribir.")
            return False

    # 1. Copiar imagen
    image_filename = None
    if image_path:
        image_filename = copy_image_to_stock(image_path)

    if not image_filename:
        # Fallback: buscar una imagen existente que no se haya usado recientemente
        state = load_state()
        used = state.get("used_images", [])
        existing_images = [f for f in os.listdir(STOCK_DIR)
                          if f.endswith(('.jpg', '.png', '.webp')) and f not in used]
        if existing_images:
            image_filename = existing_images[0]
            print(f"📷 Sin imagen nueva, usando existente: {image_filename}")
        else:
            # Resetear y reusar
            image_filename = os.listdir(STOCK_DIR)[0] if os.listdir(STOCK_DIR) else None
            state["used_images"] = []
            save_state(state)
            print(f"📷 Ciclo de imágenes reiniciado: {image_filename}")

    if not image_filename:
        print("❌ No hay imágenes disponibles en stock/")
        return False

    # 2. Crear nota
    filepath = create_nota(title, body, tags, image_filename, description, image_alt)
    print(f"   🖼️  Imagen: {image_filename}")

    if dry_run:
        print(f"\n🔍 DRY RUN — Nota creada sin push: {filepath}")
        return True

    # 3. Git commit + push
    success = git_commit_push(filepath, title)

    if success:
        # 4. Notificación push
        send_push_notification(title, filepath)

        # 4b. Aviso en Facebook e Instagram, con la imagen de la nota
        announce_on_social(filepath)

        # 5. Actualizar estado
        state = load_state()
        if "used_images" not in state:
            state["used_images"] = []
        if image_filename not in state["used_images"]:
            state["used_images"].append(image_filename)
            # Mantener solo últimas 30 imágenes usadas
            if len(state["used_images"]) > 30:
                state["used_images"] = state["used_images"][-30:]

        state["published"] = state.get("published", [])
        state["published"].append({
            "title": title,
            "date": datetime.date.today().isoformat(),
            "slug": slugify(title),
            "image": image_filename,
        })
        save_state(state)
        print(f"\n🎉 Nota publicada: {title}")
    else:
        print(f"\n⚠️  Nota creada localmente pero falló el push: {filepath}")

    return success


def main():
    parser = argparse.ArgumentParser(description="Publicar nota de blog desde JSON")
    parser.add_argument("json_file", help="Archivo JSON con el contenido de la nota")
    parser.add_argument("--dry-run", action="store_true", help="Crear nota sin git push")
    parser.add_argument("--force", action="store_true", help="Sobrescribir nota del día si ya existe")
    args = parser.parse_args()

    if not os.path.exists(args.json_file):
        print(f"❌ No se encontró: {args.json_file}")
        sys.exit(1)

    success = publish_blog_post(args.json_file, dry_run=args.dry_run, force=args.force)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
