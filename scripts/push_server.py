#!/usr/bin/env python3
"""
MR Agentes — Push Notification Server
Maneja suscripciones Web Push y envía notificaciones cuando se publica una nota.

Uso:
  python3 scripts/push_server.py              # Inicia servidor HTTP en :8081
  python3 scripts/push_server.py --port 8081  # Puerto personalizado

Endpoints:
  POST /api/subscribe/   - Registrar suscripción push
  POST /api/unsubscribe/ - Eliminar suscripción
  POST /api/send/        - Enviar notificación a todos los suscriptores (token auth)

Integración:
  publish_daily.py llama a /api/send/ automáticamente después de publicar.
"""

import os
import sys
import json
import time
import subprocess
import http.server
import urllib.parse
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBSCRIPTIONS_FILE = os.path.join(BASE_DIR, "scripts", "push_subscriptions.json")
CONFIG_FILE = os.path.join(BASE_DIR, "scripts", "config.local.json")

# VAPID keys y token desde archivo local (no versionado)
def _load_config():
    default = {
        "vapidPublicKey": "",
        "vapidPrivateKey": "",
        "pushApiToken": "",
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return {**default, **json.load(f)}
        except (json.JSONDecodeError, OSError):
            pass
    return default

_config = _load_config()
VAPID_PUBLIC_KEY = _config.get("vapidPublicKey", "")
VAPID_PRIVATE_KEY = _config.get("vapidPrivateKey", "")
API_TOKEN = _config.get("pushApiToken", "") or os.environ.get("PUSH_API_TOKEN", "")


def load_subscriptions():
    if os.path.exists(SUBSCRIPTIONS_FILE):
        try:
            with open(SUBSCRIPTIONS_FILE, "r") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_subscriptions(subscriptions):
    os.makedirs(os.path.dirname(SUBSCRIPTIONS_FILE), exist_ok=True)
    with open(SUBSCRIPTIONS_FILE, "w") as f:
        json.dump(subscriptions, f, indent=2)


def send_push_notification(subscription, payload):
    """Envía una notificación push a una suscripción usando web-push CLI."""
    try:
        sub_json = json.dumps(subscription)
        payload_json = json.dumps(payload)

        result = subprocess.run(
            [
                sys.executable, "-m", "web_push", "send_notification",
                "--endpoint", subscription.get("endpoint", ""),
                "--key", subscription.get("keys", {}).get("p256dh", ""),
                "--auth", subscription.get("keys", {}).get("auth", ""),
                "--payload", payload_json,
                "--vapid-public-key", VAPID_PUBLIC_KEY,
                "--vapid-private-key", VAPID_PRIVATE_KEY,
                "--vapid-subject", "mailto:marcos@mragentes.com.ar",
                "--ttl", "86400",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return True, None
        else:
            return False, result.stderr
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)


def send_push_to_all(title, body, url, image=None):
    """Envía notificación a todos los suscriptores activos."""
    subscriptions = load_subscriptions()
    if not subscriptions:
        print("  ℹ️  No hay suscriptores push.")
        return 0

    payload = {
        "title": title,
        "body": body,
        "url": url,
        "icon": "/faviconhand512.png",
        "badge": "/faviconhand512.png",
        "tag": f"nota-{int(time.time())}",
    }
    if image:
        payload["image"] = image

    sent = 0
    failed = []

    for sub in subscriptions:
        success, err = send_push_notification(sub, payload)
        if success:
            sent += 1
        else:
            failed.append(sub.get("endpoint", "unknown")[:40] + "...")

    if failed:
        print(f"  ⚠️  Push: {len(failed)} fallaron (de {len(subscriptions)} suscriptores)")

    return sent


# === HTTP Server ===

class PushHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        """Silenciar logs HTTP estándar."""
        pass

    def _send_json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return self.rfile.read(length).decode()
        return ""

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/vapid-key/":
            self._send_json(200, {"publicKey": VAPID_PUBLIC_KEY})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/api/subscribe/":
            body = self._read_body()
            try:
                subscription = json.loads(body)
                subscriptions = load_subscriptions()

                # No duplicar endpoints
                existing = [s for s in subscriptions if s.get("endpoint") == subscription.get("endpoint")]
                if not existing:
                    subscriptions.append(subscription)
                    save_subscriptions(subscriptions)
                    print(f"  📱 Nuevo suscriptor push ({len(subscriptions)} total)")

                self._send_json(200, {"status": "ok"})
            except Exception as e:
                self._send_json(400, {"error": str(e)})

        elif path == "/api/unsubscribe/":
            body = self._read_body()
            try:
                data = json.loads(body)
                endpoint = data.get("endpoint", "")
                subscriptions = load_subscriptions()
                subscriptions = [s for s in subscriptions if s.get("endpoint") != endpoint]
                save_subscriptions(subscriptions)
                print(f"  👋 Suscriptor removido ({len(subscriptions)} restantes)")
                self._send_json(200, {"status": "ok"})
            except Exception as e:
                self._send_json(400, {"error": str(e)})

        elif path == "/api/send/":
            body = self._read_body()
            try:
                data = json.loads(body)
                # Auth
                token = data.get("token", "")
                if token != API_TOKEN:
                    self._send_json(403, {"error": "Invalid token"})
                    return

                sent = send_push_to_all(
                    title=data.get("title", "Nueva nota de MR Agentes"),
                    body=data.get("body", ""),
                    url=data.get("url", "https://mragentes.com.ar/"),
                    image=data.get("image"),
                )
                self._send_json(200, {"status": "ok", "sent": sent})
            except Exception as e:
                self._send_json(400, {"error": str(e)})

        else:
            self._send_json(404, {"error": "Not found"})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="MR Agentes Push Server")
    parser.add_argument("--port", type=int, default=8081, help="Puerto del servidor")
    parser.add_argument("--send", nargs=4, metavar=("TITLE", "BODY", "URL", "IMAGE"),
                        help="Enviar notificación y salir (sin servidor)")
    args = parser.parse_args()

    if args.send:
        title, body, url, image = args.send
        if image == "none":
            image = None
        sent = send_push_to_all(title, body, url, image)
        print(f"  ✅ Notificación enviada a {sent} suscriptores")
        return

    port = args.port
    server = http.server.HTTPServer(("0.0.0.0", port), PushHandler)
    print(f"📡 Push server listening on :{port}")
    print(f"   Endpoints:")
    print(f"     POST /api/subscribe/   - Registrar suscripción")
    print(f"     POST /api/unsubscribe/ - Eliminar suscripción")
    print(f"     POST /api/send/        - Enviar notificación (auth required)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Servidor detenido.")
        server.server_close()


if __name__ == "__main__":
    main()
