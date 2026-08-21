#!/usr/bin/env python3
"""Suite TDD - migracion vision DeepSeek"""
import json, os, subprocess, sys

WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.expanduser("~/.openclaw/openclaw.json")
TEST_IMAGE = os.path.join(WORKSPACE, "static", "faviconhand512.png")
VISION_MODEL = "deepseek-v4-flash-vision-exp"
VISION_REF = "deepseek/deepseek-v4-flash-vision-exp"

passed = 0
failed = 0
verbose = "--verbose" in sys.argv

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print("  OK " + name)
    else:
        failed += 1
        print("  FAIL " + name + (("\n     " + detail) if detail else ""))

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def models_list():
    r = subprocess.run(["openclaw", "models", "list"], capture_output=True, text=True, timeout=120)
    return r.stdout

print("T1 - modelo vision registrado en catalogo")
cfg = load_config()
ds = cfg.get("models", {}).get("providers", {}).get("deepseek", {}).get("models", [])
ve = next((m for m in ds if m.get("id") == VISION_MODEL), None)
check("existe en models.providers.deepseek.models[]", ve is not None)
check("input text+image", ve is not None and "image" in ve.get("input", []), json.dumps(ve) if ve else "ausente")
check("contextWindow >= 100000", ve is not None and ve.get("contextWindow", 0) >= 100000)

ml = models_list()
line = next((l for l in ml.splitlines() if VISION_MODEL in l), "")
check("models list muestra text+image", "text+image" in line, line or "ausente")

print("T2 - tools.media.image usa deepseek (google fallback)")
im = cfg.get("tools", {}).get("media", {}).get("image", {}).get("models", [])
check("primero es deepseek vision", bool(im) and im[0].get("provider") == "deepseek" and im[0].get("model") == VISION_MODEL, json.dumps(im))
check("google fallback segundo", len(im) >= 2 and im[1].get("provider") == "google", json.dumps(im))
check("capabilities image", all("image" in m.get("capabilities", []) for m in im), json.dumps(im))

print("T3 - batch attachments mode=all")
att = cfg.get("tools", {}).get("media", {}).get("image", {}).get("attachments", {})
check("mode == all", att.get("mode") == "all", json.dumps(att))
check("maxAttachments >= 2", att.get("maxAttachments", 0) >= 2, json.dumps(att))

print("T4 - describe imagen real")
check("imagen existe", os.path.exists(TEST_IMAGE), TEST_IMAGE)
if os.path.exists(TEST_IMAGE):
    r = subprocess.run(["openclaw", "infer", "image", "describe", "--file", TEST_IMAGE,
                        "--model", VISION_REF, "--timeout-ms", "90000"],
                       capture_output=True, text=True, timeout=120)
    ok = r.returncode == 0 and len(r.stdout.strip()) > 10
    check("describe responde no vacio", ok, "rc=%s stderr=%s" % (r.returncode, r.stderr[-300:]))
    if verbose and ok:
        print("     -> " + r.stdout.strip()[:300])

print("-" * 60)
print("Resultado: %d passed, %d failed" % (passed, failed))
sys.exit(0 if failed == 0 else 1)
