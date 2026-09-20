#!/usr/bin/env python3
"""Compile every Arduino sketch under embedded/ with arduino-cli (board: Arduino Uno / ATmega328) against ONLY the
vendored libraries in embedded/libraries (a private user-libraries dir keeps ~/Documents/Arduino/libraries out of it).
Sketch folders whose name does not match their main .ino are copied to a scratch dir under the right name first
(the old tree kept e.g. Sequencer2.ino inside a folder called 'download').
Expected outcomes are listed in EXPECT; anything else is a failure. Never writes into the tree."""
import os, sys, subprocess, tempfile, shutil, glob, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = next((p for p in ["/opt/homebrew/bin/arduino-cli", "/usr/local/bin/arduino-cli", os.path.expanduser("~/bin/arduino-cli"),
                        "/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli"] if os.path.exists(p)), "arduino-cli")
FQBN = "arduino:avr:uno"
EXPECT = {  # sketch folder (relative to embedded/) -> "ok" | "fail: <why>"
    "bus-tester/bus-driver-mcp23x17-wip": "fail: needs Adafruit MCP23X17 2.x + BusIO, not vendored (2026-09-18 work in progress)",
}
SKIP_DIRS = ("libraries",)   # third-party library examples
def sketches():
    out = []
    for root, dirs, files in os.walk(os.path.join(ROOT, "embedded")):
        rel = os.path.relpath(root, os.path.join(ROOT, "embedded"))
        if rel.split(os.sep)[0] in SKIP_DIRS: dirs[:] = []; continue
        inos = [f for f in files if f.endswith(".ino")]
        if inos: out.append((rel, root, inos))
    return sorted(out)
def primary(root, inos):
    for f in inos:
        if re.search(r"void\s+setup\s*\(", open(os.path.join(root, f), errors="ignore").read()): return f
    return inos[0]
tmp = tempfile.mkdtemp(prefix="yacc1-ino-"); userlibs = os.path.join(tmp, "user"); os.makedirs(os.path.join(userlibs, "libraries"))
cfg = os.path.join(tmp, "arduino-cli.yaml"); open(cfg, "w").write("directories:\n  user: %s\n" % userlibs)
results = []; bad = 0
for rel, root, inos in sketches():
    name = primary(root, inos)[:-4]
    sk = os.path.join(tmp, "sk", rel.replace("/", "_"), name); os.makedirs(sk)
    for f in os.listdir(root):
        p = os.path.join(root, f)
        if os.path.isfile(p) and (f.endswith((".ino", ".h", ".cpp", ".c"))): shutil.copy(p, sk)
    r = subprocess.run([CLI, "--config-file", cfg, "compile", "--fqbn", FQBN, "--libraries", os.path.join(ROOT, "embedded/libraries"), sk], capture_output=True, text=True)
    ok = r.returncode == 0
    size = re.search(r"Sketch uses (\d+) bytes", r.stdout); size = size.group(1) if size else "-"
    err = next((l for l in (r.stderr + r.stdout).splitlines() if "error" in l.lower()), "").strip()[:110]
    exp = EXPECT.get(rel, "ok")
    verdict = "OK" if ok else "FAIL"
    if (exp == "ok") != ok: bad += 1; verdict += "  <-- unexpected"
    elif not ok: verdict += "  (expected: %s)" % exp[6:]
    results.append((rel, name + ".ino", size, verdict, "" if ok else err))
shutil.rmtree(tmp, ignore_errors=True)
w = max(len(r[0]) for r in results)
for rel, ino, size, verdict, err in results: print("%-*s  %-26s %6s bytes  %s%s" % (w, rel, ino, size, verdict, ("\n" + " " * (w + 2) + err) if err else ""))
print("\n%d sketches, %d unexpected results -> %s" % (len(results), bad, "EMBEDDED VERIFIED" if bad == 0 else "EMBEDDED FAILED")); sys.exit(1 if bad else 0)
