#!/usr/bin/env python3
"""Make a multi-page PDF of every Eagle board under hardware/ (active AND deprecated revisions).

Route: KiCad's bundled python loads the Eagle .brd through pcbnew.PCB_IO_MGR (the same Eagle importer
kicad-cli pcb import uses), saves a temporary
.kicad_pcb, then `kicad-cli pcb export pdf --mode-multipage` plots one page per layer:
  F.Cu, In1.Cu, In2.Cu (4-layer boards only), B.Cu, F.SilkS, B.SilkS - every page also carries Edge.Cuts,
  and the copper pages carry the silkscreen of their side so parts are identifiable.
Output: <folder of the .brd>/pdf/<brd basename>-board.pdf ; index hardware/BOARDS.md.
usage: brd_to_pdf.py [--only <substring>]   (run with any python3; it re-executes itself under KiCad's python)
"""
import os, sys, subprocess, tempfile, shutil, time, re
KPY = "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"
KICAD = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); HW = os.path.join(ROOT, "hardware")
if os.path.realpath(sys.executable) != os.path.realpath(KPY) and "--inner" not in sys.argv:
    os.execv(KPY, [KPY, os.path.abspath(__file__), "--inner"] + sys.argv[1:])
import pcbnew
only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
brds = sorted(os.path.join(r, f) for r, ds, fs in os.walk(HW) for f in fs
              if f.lower().endswith(".brd") and "/kicad/" not in r + "/" and (only is None or only in os.path.join(r, f)))
def skipped(design):
    """pdf/SKIP.txt beside a design folder lists design file names that get no PDF (e.g. a board that only re-labels another)."""
    sk = os.path.join(os.path.dirname(design), "pdf", "SKIP.txt")
    return os.path.exists(sk) and os.path.basename(design) in [l.strip() for l in open(sk) if l.strip() and not l.startswith("#")]
results = []
# prune orphans: a PDF whose design file is gone (design folded/deleted) or that is now listed in SKIP.txt
for r, ds, fs in os.walk(HW):
    if os.path.basename(r) != "pdf": continue
    for f in fs:
        if f.endswith("-board.pdf"):
            design = os.path.join(os.path.dirname(r), f[:-len("-board.pdf")] + ".brd")
            if not os.path.exists(design) or skipped(design): os.remove(os.path.join(r, f)); print("orphan PDF removed:", os.path.relpath(os.path.join(r, f), HW))
for brd in brds:
    if skipped(brd): continue
    rel = os.path.relpath(brd, HW); outdir = os.path.join(os.path.dirname(brd), "pdf")
    pdf = os.path.join(outdir, os.path.splitext(os.path.basename(brd))[0] + "-board.pdf")
    if os.path.exists(pdf) and os.path.getmtime(pdf) > os.path.getmtime(brd) and os.path.getmtime(pdf) > os.path.getmtime(os.path.abspath(__file__)):
        results.append((rel, "up to date", pdf, "")); continue
    tmp = tempfile.mkdtemp(prefix="brd2pdf-")
    try:
        try:
            src = os.path.join(tmp, os.path.basename(brd)); shutil.copy2(brd, src)   # importer writes .kicad_dru/.kicad_prl beside its input: keep that in tmp
            board = pcbnew.PCB_IO_MGR.Load(pcbnew.PCB_IO_MGR.EAGLE, src)   # LoadBoard() only reads KiCad boards
            if board is None: raise RuntimeError("Eagle importer returned nothing")
        except Exception as e:
            results.append((rel, "IMPORT FAILED: " + str(e).splitlines()[0][:140], None, "")); continue
        # 2016-era boards put graphics on Eagle user layers that map to no KiCad layer; kicad-cli refuses such a file
        dropped = 0
        U = pcbnew.UNDEFINED_LAYER
        for item in list(board.GetDrawings()) + list(board.GetTracks()):
            if item.GetLayer() == U: board.Remove(item); dropped += 1
        for z in list(board.Zones()):
            if z.GetLayer() == U: z.SetLayer(pcbnew.Cmts_User); dropped += 1   # removing zones through SWIG corrupts the board; park them on an unplotted layer
        for fp in board.GetFootprints():
            for item in list(fp.GraphicalItems()):
                if item.GetLayer() == U: fp.Remove(item); dropped += 1
        # Eagle's origin is bottom-left and the importer leaves the board at negative Y (and unplaced parts at 0,0);
        # the PDF plotter clips negative space, so shift everything to start at +5 mm.
        bb = board.GetBoundingBox(); dx = pcbnew.FromMM(5) - bb.GetX(); dy = pcbnew.FromMM(5) - bb.GetY()
        mv = pcbnew.VECTOR2I(dx, dy)
        for coll in (board.GetFootprints(), board.GetTracks(), board.GetDrawings(), board.Zones()):
            for item in list(coll): item.Move(mv)
        kp = os.path.join(tmp, "b.kicad_pcb"); pcbnew.PCB_IO_KICAD_SEXPR().SaveBoard(kp, board)
        inner = ["In%d.Cu" % i for i in range(1, board.GetCopperLayerCount() - 1)]
        layers = ["F.Cu"] + inner + ["B.Cu", "F.SilkS", "B.SilkS"]
        nfp = len(list(board.GetFootprints())); ntr = len([t for t in board.GetTracks()])
        os.makedirs(outdir, exist_ok=True)
        cmd = [KICAD, "pcb", "export", "pdf", "--mode-multipage", "--layers", ",".join(layers),   # no drawing sheet: page = board extent
               "--common-layers", "Edge.Cuts", "--drill-shape-opt", "1", "-o", pdf, kp]
        k = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if k.returncode != 0 or not os.path.exists(pdf):
            results.append((rel, "PDF FAILED: " + (k.stderr or k.stdout).strip().splitlines()[-1][:140], None, "")); continue
        results.append((rel, "made", pdf, "%d layers, %d parts, %d track segments%s" % (2 + len(inner), nfp, ntr, ("; %d items on undefined Eagle layers dropped" % dropped) if dropped else "")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("%-10s %s  (%s)" % (results[-1][1][:10], rel, results[-1][3]), flush=True)
with open(os.path.join(HW, "BOARDS.md"), "w") as f:
    f.write("# Board PDFs\n\nGenerated %s by `tools/brd_to_pdf.py` from every Eagle `.brd` under `hardware/` (active and deprecated), "
            "imported with KiCad's Eagle board reader and plotted one page per layer: F.Cu, inner layers (4-layer boards), B.Cu, F.SilkS, "
            "B.SilkS, each with the board outline. Bottom pages are NOT mirrored (viewed from the top, as in Eagle). Derived files: re-run after any `.brd` change.\n\n"
            "| Board | PDF | Notes |\n|---|---|---|\n" % time.strftime("%Y-%m-%d"))
    for rel, st, pdf, info in results:
        f.write("| `%s` | %s | %s |\n" % (rel, ("[`%s`](%s)" % (os.path.basename(pdf), os.path.relpath(pdf, HW))) if pdf else "**" + st + "**", info))
fail = [r for r in results if r[2] is None]
print("\n%d boards: %d made, %d up to date, %d FAILED" % (len(results), sum(1 for r in results if r[1] == "made"), sum(1 for r in results if r[1] == "up to date"), len(fail)))
for r in fail: print("   ", r[0], "->", r[1])
