#!/usr/bin/env python3
"""setup_check.py - is this Mac set up to work on YACC1-D? (2026-09-27)

Checks, without installing or changing anything, the tools each kind of work needs and prints what is present, what
is missing and how to get it. Ken develops on two Macs; run this on a fresh clone (CLAUDE.md "Two Macs").

    python3 tools/setup_check.py          # everything
    python3 tools/setup_check.py --quiet  # only what is missing

Exit status 0 when everything the core work needs (building, make check's software parts) is present, 1 otherwise;
board-design, Arduino and machine-connection items are reported but do not fail the check.
"""
import os, sys, shutil, subprocess, glob, importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUIET = "--quiet" in sys.argv
KICAD_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
KICAD_PY = "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"
INKSCAPE = os.environ.get("INK", "/Applications/Inkscape.app/Contents/MacOS/inkscape")
FRJAR = os.environ.get("FRJAR", os.path.expanduser("~/freerouting/freerouting.jar"))
ARDUINO_CLI = [ "/opt/homebrew/bin/arduino-cli", "/usr/local/bin/arduino-cli", os.path.expanduser("~/bin/arduino-cli"),
                "/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli"]
CONSOLE, SEQUENCER = "/dev/cu.usbserial-AB0MVHSQ", "/dev/cu.usbserial-AB6WZCQX"

def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)

results = []          # (group, ok, name, detail, fix, required)
def check(group, name, ok, detail="", fix="", required=False):
    results.append((group, bool(ok), name, detail, fix, required))

# ---- core: build the C tools, run make check's software parts -----------------------------------------------
G = "core (make, make check, compiler, OS, emulators)"
rc, out = run(["xcode-select", "-p"])
check(G, "Xcode command-line tools", rc == 0, out.splitlines()[0] if rc == 0 else "",
      "xcode-select --install", True)
for tool in ("cc", "make", "git"):
    p = shutil.which(tool)
    check(G, tool, p, p or "", "xcode-select --install", True)
v = sys.version_info
check(G, "Python 3.8+", v >= (3, 8), "%d.%d.%d" % (v.major, v.minor, v.micro), "install Python 3 (python.org or brew install python)", True)
rc, out = run(["git", "-C", ROOT, "remote", "get-url", "origin"])
check(G, "git remote origin", rc == 0 and "ksr/YACC1-D" in out, out, "git clone https://github.com/ksr/YACC1-D.git", True)
if rc == 0:
    run(["git", "-C", ROOT, "fetch", "-q", "origin"])
    rc2, behind = run(["git", "-C", ROOT, "rev-list", "--count", "HEAD..origin/main"])
    rc3, ahead = run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"])
    rc4, dirty = run(["git", "-C", ROOT, "status", "--porcelain"])
    ndirty = len([l for l in dirty.splitlines() if l])
    state = "behind %s, ahead %s, %d uncommitted" % (behind or "?", ahead or "?", ndirty)
    check(G, "in step with GitHub", rc2 == 0 and behind == "0" and ahead == "0" and ndirty == 0, state,
          "git pull (behind) / git push (ahead); commit or stash uncommitted work", False)
check(G, "reportlab (1:1 print PDFs)", importlib.util.find_spec("reportlab"), "",
      "python3 -m pip install --user reportlab", False)

# ---- board design ---------------------------------------------------------------------------------------------
G = "board design (hardware/cards/*/kicad/*/build.sh)"
rc, out = run([KICAD_CLI, "version"]) if os.path.exists(KICAD_CLI) else (1, "")
check(G, "KiCad 10 (kicad-cli)", rc == 0 and out.startswith("10"), out, "install KiCad 10 from kicad.org into /Applications")
check(G, "KiCad's Python (pcbnew)", os.path.exists(KICAD_PY), KICAD_PY if os.path.exists(KICAD_PY) else "", "comes with KiCad")
check(G, "Inkscape (SVG -> PNG plots)", os.path.exists(INKSCAPE), INKSCAPE if os.path.exists(INKSCAPE) else "",
      "install Inkscape from inkscape.org (or set INK=/path/to/inkscape)")
java = shutil.which("java")
rc, out = run([java, "-version"]) if java else (1, "")
check(G, "Java (for Freerouting)", rc == 0, out.splitlines()[0] if rc == 0 and out else "", "brew install openjdk")
check(G, "Freerouting jar", os.path.exists(FRJAR), FRJAR, "copy freerouting.jar to ~/freerouting/ (or set FRJAR=)")

# ---- Arduino firmware (tools/verify_embedded.py, part of make check) -------------------------------------------
G = "Arduino sketches (tools/verify_embedded.py)"
cli = next((p for p in ARDUINO_CLI if os.path.exists(p)), shutil.which("arduino-cli"))
check(G, "arduino-cli", cli, cli or "", "brew install arduino-cli  (then: arduino-cli core install arduino:avr)")
if cli:
    rc, out = run([cli, "core", "list"])
    if not (rc == 0 and "arduino:avr" in out):          # its first launch can be busy (index/lock): ask once more
        rc, out = run([cli, "core", "list"])
    check(G, "arduino:avr core", rc == 0 and "arduino:avr" in out, "", "arduino-cli core install arduino:avr")
rc, out = run(["arch", "-x86_64", "/usr/bin/true"])
check(G, "Rosetta 2 (the AVR toolchain is Intel-only)", rc == 0, "", "softwareupdate --install-rosetta --agree-to-license")
check(G, "vendored libraries", os.path.isdir(os.path.join(ROOT, "embedded/libraries/YACC")),
      "embedded/libraries (YACC, Adafruit_MCP23017 1.1.0)", "part of the repo - git pull")
ide_lib = os.path.expanduser("~/Documents/Arduino/libraries/YACC")
check(G, "YACC library for the Arduino IDE (optional)", os.path.isdir(ide_lib), ide_lib,
      "only for the IDE: cp -R embedded/libraries/YACC ~/Documents/Arduino/libraries/  (builds use the repo copy)")

# ---- the machine ----------------------------------------------------------------------------------------------
G = "the YACC1 machine (USB-serial; one Mac at a time)"
check(G, "console FTDI " + CONSOLE, os.path.exists(CONSOLE), "", "plug in the I/O card's FTDI cable (macOS has the driver)")
check(G, "sequencer FTDI " + SEQUENCER, os.path.exists(SEQUENCER), "", "plug in the sequencer card's FTDI cable")
kermit = shutil.which("kermit")
check(G, "C-Kermit (file transfer, docs/procedures/KERMIT.md)", kermit, kermit or "", "brew install c-kermit")
check(G, "screen (plain console)", shutil.which("screen"), "", "part of macOS")

# ---- report ---------------------------------------------------------------------------------------------------
missing_required = 0
last = None
for group, ok, name, detail, fix, required in results:
    if QUIET and ok:
        continue
    if group != last:
        print("\n" + group); last = group
    mark = "ok  " if ok else ("MISSING" if required else "--  ")
    line = "  %-7s %-46s %s" % (mark, name, detail)
    print(line.rstrip())
    if not ok and fix:
        print("          -> " + fix)
    if not ok and required:
        missing_required += 1
print("\n%s" % ("core tools present." if missing_required == 0 else "%d core item(s) missing." % missing_required))
print("Board design, Arduino and machine items are only needed for that kind of work.")
sys.exit(1 if missing_required else 0)
