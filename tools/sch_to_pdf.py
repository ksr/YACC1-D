#!/usr/bin/env python3
"""Make a PDF of every Eagle schematic under hardware/ (active AND deprecated revisions).

Route: tools/kicad/eagle_sch_to_kicad.py (Eagle 6+ XML .sch -> KiCad schematic, in a scratch dir)
       then `kicad-cli sch export pdf`. Fusion/Eagle have no scriptable export on this Mac (Eagle 9.6.2 blocks
       on its login dialog when driven from the command line).
Output: <folder of the .sch>/pdf/<sch basename>-schematic.pdf   (never touches the .sch; existing Eagle-made
        PDFs beside the .sch are left alone). Also writes hardware/SCHEMATICS.md, an index of every PDF.
usage: sch_to_pdf.py [--only <substring>]   (run from anywhere; needs KiCad 10 at /Applications/KiCad)
"""
import os, sys, subprocess, tempfile, shutil, time, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); HW = os.path.join(ROOT, "hardware")
CONV = os.path.join(ROOT, "tools", "kicad", "eagle_sch_to_kicad.py")
KICAD = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
schs = sorted(os.path.join(r, f) for r, ds, fs in os.walk(HW) for f in fs
              if f.lower().endswith(".sch") and "/kicad/" not in r + "/" and (only is None or only in os.path.join(r, f)))
def skipped(design):
    """pdf/SKIP.txt beside a design folder lists design file names that get no PDF (e.g. a board that only re-labels another)."""
    sk = os.path.join(os.path.dirname(design), "pdf", "SKIP.txt")
    return os.path.exists(sk) and os.path.basename(design) in [l.strip() for l in open(sk) if l.strip() and not l.startswith("#")]
results = []
# prune orphans: a PDF whose design file is gone (design folded/deleted) or that is now listed in SKIP.txt
for r, ds, fs in os.walk(HW):
    if os.path.basename(r) != "pdf": continue
    for f in fs:
        if f.endswith("-schematic.pdf"):
            design = os.path.join(os.path.dirname(r), f[:-len("-schematic.pdf")] + ".sch")
            if not os.path.exists(design) or skipped(design): os.remove(os.path.join(r, f)); print("orphan PDF removed:", os.path.relpath(os.path.join(r, f), HW))
for sch in schs:
    if skipped(sch): continue
    rel = os.path.relpath(sch, HW); outdir = os.path.join(os.path.dirname(sch), "pdf")
    pdf = os.path.join(outdir, os.path.splitext(os.path.basename(sch))[0] + "-schematic.pdf")
    if os.path.exists(pdf) and os.path.getmtime(pdf) > os.path.getmtime(sch) and os.path.getmtime(pdf) > os.path.getmtime(CONV):
        results.append((rel, "up to date", pdf)); continue
    tmp = tempfile.mkdtemp(prefix="sch2pdf-")
    try:
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.splitext(os.path.basename(sch))[0])
        c = subprocess.run([sys.executable, CONV, sch, tmp, name], capture_output=True, text=True, timeout=300)
        if c.returncode != 0:
            results.append((rel, "CONVERT FAILED: " + (c.stderr or c.stdout).strip().splitlines()[-1][:160], None)); continue
        os.makedirs(outdir, exist_ok=True)
        k = subprocess.run([KICAD, "sch", "export", "pdf", "-o", pdf, os.path.join(tmp, name + ".kicad_sch")], capture_output=True, text=True, timeout=300)
        if k.returncode != 0 or not os.path.exists(pdf):
            results.append((rel, "PDF FAILED: " + (k.stderr or k.stdout).strip().splitlines()[-1][:160], None)); continue
        results.append((rel, "made", pdf))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("%-10s %s" % (results[-1][1][:10], rel), flush=True)
with open(os.path.join(HW, "SCHEMATICS.md"), "w") as f:
    f.write("# Schematic PDFs\n\nGenerated %s by `tools/sch_to_pdf.py` from every Eagle `.sch` under `hardware/` "
            "(active and deprecated revisions), rendered by KiCad after conversion with `tools/kicad/eagle_sch_to_kicad.py`. "
            "Page 1 of each PDF is KiCad's sheet index; the circuit starts on page 2. These are derived files: "
            "re-run the script after any change to a `.sch`.\n\n| Schematic | PDF |\n|---|---|\n")
    for rel, st, pdf in results:
        f.write("| `%s` | %s |\n" % (rel, ("[`%s`](%s)" % (os.path.basename(pdf), os.path.relpath(pdf, HW))) if pdf else "**" + st + "**"))
made = sum(1 for r in results if r[1] == "made"); upd = sum(1 for r in results if r[1] == "up to date")
fail = [r for r in results if r[2] is None]
print("\n%d schematics: %d made, %d up to date, %d FAILED" % (len(results), made, upd, len(fail)))
for r in fail: print("   ", r[0], "->", r[1])
