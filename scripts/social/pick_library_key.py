#!/usr/bin/env python3
"""Elegir la clave de posteo del día para el social manager (reemplaza heredocs del cron).

Rotación: día del año % 15 sobre la lista de keys de library.json.
Solo imprime la clave elegida + estado (publicada o no) — no publica nada.
"""
import json, sys
from datetime import datetime
from pathlib import Path

WORKSPACE = Path("/home/openclaw/.openclaw/workspace")
LIBRARY = WORKSPACE / "scripts" / "social" / "library.json"
STATE = WORKSPACE / "scripts" / "social" / "state.json"

KEYS = [
    "diagnostico", "por-donde-empezar", "mito-chatbots", "dato-tareas",
    "cita-criterio", "antes-despues-pedidos", "como-trabajamos",
    "glosario-agente", "pregunta-horas", "caso-turnos", "titular-integracion",
    "semana-ia", "ficha-asistente", "anuncio-contacto", "punto-ejemplo",
]

def main():
    # Si library.json existe, usar sus keys reales (orden estable)
    keys = KEYS
    try:
        lib = json.loads(LIBRARY.read_text())
        if isinstance(lib, dict) and isinstance(lib.get("posts"), list):
            keys = [it.get("key") for it in lib["posts"] if isinstance(it, dict) and it.get("key")]
        elif isinstance(lib, dict) and lib.get("items"):
            keys = [it.get("key") for it in lib["items"] if it.get("key")]
        elif isinstance(lib, list):
            keys = [it.get("key") for it in lib if isinstance(it, dict) and it.get("key")]
    except Exception:
        pass

    if not keys:
        print("ERROR: no hay keys en library.json", file=sys.stderr)
        sys.exit(2)

    # Estado publicado
    published = {}
    try:
        published = json.loads(STATE.read_text()).get("published", {})
    except Exception:
        pass

    doy = datetime.now().timetuple().tm_yday
    key = keys[doy % len(keys)]
    is_pub = key in published

    print(f"KEY={key}")
    print(f"PUBLISHED={str(is_pub).lower()}")
    print(f"DATE={datetime.now().strftime('%Y-%m-%d')}")
    if is_pub:
        print(f"NOTE={key} ya está en state.json — elegí otra clave o terminá sin publicar")
    sys.exit(0 if not is_pub else 1)

if __name__ == "__main__":
    main()
