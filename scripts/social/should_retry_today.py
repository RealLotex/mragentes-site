#!/usr/bin/env python3
"""Gate del cron de reintento a los 15 min.

Decide si el segundo disparo (13:15) del cron social debe correr o no.
Emite exclusivamente a stdout una línea con `fire` o `nofire`.

Regla:
- Si en `scripts/social/state.json` ya hay UNA pieza con `date == hoy`
  (en `published[]`), imprime `nofire` → el día ya está cubierto.
- Si NO hay pieza de hoy, imprime `fire` → conviene reintentar.

Este contrato lo consume el `trigger.script` del job de cron de OpenClaw,
que espera un JSON `{ "fire": true|false }`. Acá se prefiere imprimir el
JSON completo para que OpenClaw lo evalúe sin ambigüedad.

Uso:
    python3 scripts/social/should_retry_today.py          # fire | nofire (JSON)
    python3 scripts/social/should_retry_today.py --plain  # fire / nofire (texto)
"""
import json
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
STATE = WORKSPACE / "scripts" / "social" / "state.json"


def has_post_today(state_path: Path = STATE, today: str | None = None) -> bool:
    """Devuelve True si hay al menos una pieza publicada con date == hoy."""
    today = today or datetime.now().strftime("%Y-%m-%d")
    try:
        data = json.loads(state_path.read_text())
    except Exception:
        # Sin state legible → asumir que no hay post hoy (conviene reintentar).
        return False
    published = data.get("published", {})
    if not isinstance(published, dict):
        return False
    for v in published.values():
        if not isinstance(v, dict):
            continue
        date = str(v.get("date", ""))[:10]
        if date == today:
            return True
    return False


def main() -> int:
    plain = "--plain" in sys.argv
    fire = not has_post_today()
    if plain:
        print("fire" if fire else "nofire")
    else:
        print(json.dumps({"fire": fire}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
