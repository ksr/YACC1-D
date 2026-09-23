#!/usr/bin/env python3
"""kicad_route.py - shared routing/finishing steps for generated 2-layer YACC1 KiCad cards.

Run with KiCad's bundled Python (pcbnew):
    PYK=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
    $PYK tools/kicad/kicad_route.py export_dsn <board.kicad_pcb>          -> <board>.dsn for Freerouting
    $PYK tools/kicad/kicad_route.py import_ses <board.kicad_pcb> <ses>    -> routing in, stitch, edge heal, zone fill
    $PYK tools/kicad/kicad_route.py fill       <board.kicad_pcb>          -> refill the zones
    $PYK tools/kicad/kicad_route.py finish     <board.kicad_pcb>          -> gerbers/ + drill + zip, top render,
                                                                              placement PDF
Adapted 2026-09-23 from the P8X pipeline, ~/Developer/p8x/generators/kicad_tools.py (the projects are separate forks;
this copy is YACC1's): _inset_dsn_boundary, stitch_trivial_nets, heal_edge_clearance and placement are that file's
code with small changes. Differences for YACC1's 2-layer cards:
  * export_dsn drops the copper pours (not the keepout rule areas) from the DSN, so Freerouting routes GND as tracks
    like any other net; the pours are filled afterwards as extra copper. A pour on a signal layer would otherwise be
    exported as a "plane" and Freerouting would consider GND connected through it, which a real fill need not honour.
  * heal_starved_thermals (new): a track-routed GND pad whose thermal spokes reach only a local fill island gets a
    solid pad-level zone connection instead of failing DRC.
  * pcbnew is only ever asked to Add items: in KiCad 10's SWIG layer, board containers stop iterating after a Remove(),
    so a pour-free copy is made at the text level.
Known Freerouting 1.9 quirks (from P8X): run it from the card folder, use -mt 1 (the multi-threaded optimizer is
broken), kill it after ~20 min if the optimizer hangs, and never call --help (it opens a GUI).
"""
import os, sys, re, glob, shutil, zipfile, subprocess
import pcbnew

CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"


def _run(*a):
    subprocess.run(list(a), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def top_forms(text):
    forms, d, ins, start, j = [], 0, False, None, text.index("(") + 1
    while j < len(text):
        c = text[j]
        if ins:
            if c == "\\": j += 1
            elif c == '"': ins = False
        elif c == '"': ins = True
        elif c == "(":
            if d == 0: start = j
            d += 1
        elif c == ")":
            if d == 0: break
            d -= 1
            if d == 0: forms.append(text[start:j + 1])
        j += 1
    return forms


def _inset_dsn_boundary(t, keep_mm=0.35):
    """Shrink the routing boundary rectangle inward by keep_mm so Freerouting keeps copper back from the board edge
    (it otherwise routes to its own 0.2 mm boundary clearance and trips KiCad's 0.5 mm copper-to-edge rule)."""
    m = re.search(r'\(boundary\s*\(path pcb 0\s+([\-0-9\s.]+?)\)\s*\)', t)
    if not m:
        return t
    nums = [float(v) for v in m.group(1).split()]
    xs, ys = nums[0::2], nums[1::2]
    if len(xs) < 4:
        return t
    upm = 1.0 if re.search(r'\(unit mm\)', t) else 1000.0          # pcbnew writes the DSN in um
    d = keep_mm * upm
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    out = []
    for x, y in zip(xs, ys):
        out += [x + d if x == x0 else (x - d if x == x1 else x), y + d if y == y0 else (y - d if y == y1 else y)]
    newpath = "(boundary\n      (path pcb 0  " + "  ".join(
        "%g %g" % (out[i], out[i + 1]) for i in range(0, len(out), 2)) + ")\n    )"
    return t[:m.start()] + newpath + t[m.end():]


def export_dsn(brd):
    d = os.path.dirname(os.path.abspath(brd)); name = os.path.basename(brd)[:-len(".kicad_pcb")]
    dsn = os.path.join(d, name + ".dsn")
    text = open(brd).read()
    keep = [f for f in top_forms(text) if not (f.startswith("(zone") and "(keepout" not in f)]
    tmp = os.path.join(d, "_dsn_tmp.kicad_pcb")
    open(tmp, "w").write("(kicad_pcb\n\t" + "\n\t".join(keep) + "\n)\n")
    pro = os.path.join(d, name + ".kicad_pro")
    if os.path.exists(pro):
        shutil.copy(pro, os.path.join(d, "_dsn_tmp.kicad_pro"))      # the net classes (track widths) come from here
    try:
        b = pcbnew.LoadBoard(tmp)
        pcbnew.ExportSpecctraDSN(b, dsn)
    finally:
        for f in ("_dsn_tmp.kicad_pcb", "_dsn_tmp.kicad_pro", "_dsn_tmp.kicad_prl"):
            if os.path.exists(os.path.join(d, f)):
                os.remove(os.path.join(d, f))
    t = _inset_dsn_boundary(open(dsn).read())
    open(dsn, "w").write(t)
    classes = re.findall(r'\(class (\S+).*?\(width ([\d.]+)\)', t, re.S)
    print("export_dsn -> %s (classes: %s)" % (os.path.basename(dsn), ", ".join("%s %s" % c for c in classes)))


def stitch_trivial_nets(b):
    """Freerouting occasionally leaves a trivial 2-pad net unrouted; stitch it with a straight B.Cu track when its two
    pads are collinear (through-hole pads let it duck under the F.Cu tracks). DRC is the backstop."""
    b.BuildConnectivity()
    pads = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            pads.setdefault(p.GetNetname(), []).append(p)
    routed = {t.GetNetname() for t in b.GetTracks()}
    n = 0
    for name, ps in pads.items():
        if name in ("", "GND", "VCC") or len(ps) != 2 or name in routed:
            continue
        a, c = ps
        if a.GetPosition().x != c.GetPosition().x and a.GetPosition().y != c.GetPosition().y:
            continue
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(a.GetPosition()); t.SetEnd(c.GetPosition())
        t.SetLayer(pcbnew.B_Cu); t.SetWidth(pcbnew.FromMM(0.3)); t.SetNetCode(a.GetNetCode())
        b.Add(t); n += 1
        print("  stitched %s" % name)
    return n


def heal_edge_clearance(brd, clear=0.5, margin=0.06):
    """Pull any track vertex that sits inside clear + half-width of the (rectangular) board edge straight back in,
    moving coincident endpoints together so nets stay whole."""
    b = pcbnew.LoadBoard(brd); mm = pcbnew.ToMM; FM = pcbnew.FromMM
    xs, ys = [], []
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            for p in (d.GetStart(), d.GetEnd()):
                xs.append(mm(p.x)); ys.append(mm(p.y))
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    tracks = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]
    moves = {}
    for t in tracks:
        need = clear + mm(t.GetWidth()) / 2.0
        for get in (t.GetStart, t.GetEnd):
            px, py = mm(get().x), mm(get().y); nx, ny = px, py
            if px - x0 < need: nx = x0 + need + margin
            if x1 - px < need: nx = x1 - need - margin
            if py - y0 < need: ny = y0 + need + margin
            if y1 - py < need: ny = y1 - need - margin
            if (nx, ny) != (px, py):
                moves[(round(px, 4), round(py, 4))] = (nx, ny)
    moved = 0
    for t in tracks:
        for setp, getp in ((t.SetStart, t.GetStart), (t.SetEnd, t.GetEnd)):
            k = (round(mm(getp().x), 4), round(mm(getp().y), 4))
            if k in moves:
                setp(pcbnew.VECTOR2I(FM(moves[k][0]), FM(moves[k][1]))); moved += 1
    if moved:
        pcbnew.SaveBoard(brd, b)
    print("heal_edge: %d track endpoint(s) pulled back from the board edge" % moved)
    return moved


def fill(brd):
    b = pcbnew.LoadBoard(brd)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(brd, b)
    print("fill: zones refilled")


def heal_starved_thermals(brd, rounds=3):
    """A GND pad whose thermal spokes land on a fill island only it connects to (or on too few spokes) fails DRC's
    starved_thermal check. Every such pad is already track-routed by Freerouting, so the fix is local: connect that
    one pad solidly to the pour (a pad-level zone-connection override), refill, repeat. Returns the pads changed."""
    import json, tempfile
    changed = []
    for _ in range(rounds):
        j = os.path.join(tempfile.gettempdir(), "_starved_%d.json" % os.getpid())
        subprocess.run([CLI, "pcb", "drc", "--format", "json", "-o", j, brd],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        hits = []
        for v in json.load(open(j)).get("violations", []):
            if v["type"] != "starved_thermal":
                continue
            for it in v["items"]:
                m = re.match(r"PTH pad (\S+) \[[^\]]*\] of (\S+)", it.get("description", ""))
                if m:
                    hits.append((m.group(2), m.group(1)))
        os.remove(j)
        if not hits:
            break
        b = pcbnew.LoadBoard(brd)
        for fp in b.GetFootprints():
            for p in fp.Pads():
                if (fp.GetReference(), p.GetNumber()) in hits:
                    p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
                    changed.append("%s.%s" % (fp.GetReference(), p.GetNumber()))
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        pcbnew.SaveBoard(brd, b)
    print("heal_thermal: %d pad(s) set to a solid zone connection %s" % (len(changed), " ".join(changed)))
    return changed


def import_ses(brd, ses):
    b = pcbnew.LoadBoard(brd)
    if not pcbnew.ImportSpecctraSES(b, ses):
        raise SystemExit("import_ses: ImportSpecctraSES failed")
    stitch_trivial_nets(b)
    pcbnew.SaveBoard(brd, b)
    ntrk = sum(1 for t in b.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T)
    nvia = sum(1 for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T)
    print("import_ses: %d track segments, %d vias" % (ntrk, nvia))
    heal_edge_clearance(brd)
    fill(brd)
    heal_starved_thermals(brd)


def placement(brd, company="YACC1"):
    """a black-and-white parts-placement PDF (silk + fab + outline), board centred on the page"""
    b = pcbnew.LoadBoard(brd)
    bb = b.GetBoardEdgesBoundingBox()
    paper, pw, ph = ("A4", 297.0, 210.0) if pcbnew.ToMM(bb.GetWidth()) <= 270 else ("A3", 420.0, 297.0)
    c = bb.GetCenter()
    shift = pcbnew.VECTOR2I(pcbnew.FromMM(pw) // 2 - c.x, pcbnew.FromMM(ph) // 2 - c.y)
    for it in list(b.GetFootprints()) + list(b.GetTracks()) + list(b.GetDrawings()) + list(b.Zones()):
        it.Move(shift)
    d = os.path.dirname(os.path.abspath(brd)); name = os.path.basename(brd)[:-len(".kicad_pcb")]
    tmp = os.path.join(d, "_placement_tmp.kicad_pcb")
    pcbnew.SaveBoard(tmp, b)
    t = open(tmp).read()
    tb = '\t(title_block\n\t\t(title "%s - parts placement")\n\t\t(company "%s")\n\t)\n' % (name, company)
    t = re.sub(r'\(paper "[^"]*"\)\n', '(paper "%s")\n' % paper + tb, t, count=1)
    open(tmp, "w").write(t)
    out = os.path.join(d, name + "-placement.pdf")
    try:
        _run(CLI, "pcb", "export", "pdf", "--layers", "F.Silkscreen,F.Fab,Edge.Cuts", "--black-and-white",
             "--include-border-title", "--mode-single", "-o", out, tmp)
    finally:
        for f in glob.glob(os.path.join(d, "_placement_tmp.*")):
            os.remove(f)
    print("placement ->", os.path.basename(out))


def finish(brd):
    d = os.path.dirname(os.path.abspath(brd)); name = os.path.basename(brd)[:-len(".kicad_pcb")]
    ger = os.path.join(d, "gerbers"); zipf = os.path.join(d, name + "-gerbers.zip")
    if os.path.isdir(ger):
        shutil.rmtree(ger)
    os.makedirs(ger)
    _run(CLI, "pcb", "export", "gerbers", "--no-protel-ext", "--layers",
         "F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts", "-o", ger + "/", brd)
    _run(CLI, "pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm", "--generate-map",
         "--map-format", "gerberx2", "-o", ger + "/", brd)
    if os.path.exists(zipf):
        os.remove(zipf)
    with zipfile.ZipFile(zipf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(glob.glob(ger + "/*")):
            z.write(f, os.path.basename(f))
    _run(CLI, "pcb", "render", "--side", "top", "--quality", "high", "--floor", "-w", "1800", "-h", "1200",
         "-o", os.path.join(d, name + "-render-top.png"), brd)
    placement(brd)
    print("finish: %d gerber/drill files -> gerbers/ + %s, render, placement" % (len(os.listdir(ger)),
                                                                                 os.path.basename(zipf)))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "export_dsn": export_dsn(sys.argv[2])
    elif cmd == "import_ses": import_ses(sys.argv[2], sys.argv[3])
    elif cmd == "fill": fill(sys.argv[2])
    elif cmd == "heal_edge": heal_edge_clearance(sys.argv[2])
    elif cmd == "placement": placement(sys.argv[2])
    elif cmd == "finish": finish(sys.argv[2])
    else: sys.exit("unknown command " + cmd)
    sys.stdout.flush(); os._exit(0)                     # skip the wx exit hang (work is saved)
