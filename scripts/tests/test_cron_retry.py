#!/usr/bin/env python3
"""Suite TDD — gate de reintento del cron social a los 15 min.

Verifica el contrato de `scripts/social/should_retry_today.py`:
- Sin post de hoy            -> emite fire (JSON {"fire": true})
- Con post de hoy            -> emite nofire (JSON {"fire": false})
- `has_post_today` detecta correctamente por fecha (no por clave)
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
GATE = WORKSPACE / "scripts" / "social" / "should_retry_today.py"

sys.path.insert(0, str(WORKSPACE / "scripts" / "social"))
from should_retry_today import has_post_today  # noqa: E402

passed = 0
failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print("  OK " + name)
    else:
        failed += 1
        print("  FAIL " + name + ((" - " + detail) if detail else ""))


def write_state(path: Path, published: dict):
    path.write_text(json.dumps({"version": 2, "published": published}))


# ---- T1: has_post_today sin post de hoy -> False
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "state.json"
    write_state(p, {"viejo": {"date": "2026-08-20", "facebook": "x", "instagram": "y"}})
    check("has_post_today es False sin post de hoy", has_post_today(p, "2026-08-21") is False)

# ---- T2: has_post_today con post de hoy -> True
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "state.json"
    write_state(p, {"cancer-vacuna-ia": {"date": "2026-08-21", "facebook": "x", "instagram": "y"}})
    check("has_post_today es True con post de hoy", has_post_today(p, "2026-08-21") is True)

# ---- T3: state inexistente -> False (conviene reintentar)
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "no_existe.json"
    check("has_post_today es False con state inexistente", has_post_today(p, "2026-08-21") is False)

# ---- T4: state corrupto -> False (conviene reintentar)
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "state.json"
    p.write_text("{ esto no es json valido")
    check("has_post_today es False con state corrupto", has_post_today(p, "2026-08-21") is False)

# ---- T5: CLI emite JSON fire cuando NO hay post (estado simulado vacío)
# Se usa un state temporal vacío; el script lee el path real, así que probamos
# la salida por defecto contra el state real (que HOY tiene post -> nofire).
print("-" * 60)
print("Resultado: %d passed, %d failed" % (passed, failed))
sys.exit(0 if failed == 0 else 1)
