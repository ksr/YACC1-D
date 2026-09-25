#!/usr/bin/env python3
"""gen_standoff.py - the STANDOFF placement options of the YACC1 memory card v2.0 (Ken, 2026-09-24): the CF-to-IDE
adapter (HX-2118P) on two M3 standoffs on the card, J2 parallel to the bus connector X1 about 1/3 of the way to the top
edge, a short straight IDE ribbon from J2 up to the adapter's header. standoff_placements.py holds the options, the
adapter's measured geometry and the clearance figures.

Run with KiCad's bundled Python (pcbnew); build.sh does, per option:

  gen_standoff.py board <opt> <schematic .net>     -> memory-v2.0-standoff-<opt>.kicad_pcb (+ .kicad_pro, .kicad_dru)
        the built board with every track and via removed (outline, X1 and its mounting holes, the In1 GND / In2 VCC
        planes kept), every pad on its v2.0 schematic net, the CF footprints added, C20-C23 left off (removed from
        the circuit, Ken 2026-09-24: these boards equal the schematic exactly), every part except X1 placed from
        standoff_placements.py (JP1 and the U$1 block group on the built card's pads, the LEDs where option B had
        them); H1 / H2 = the adapter's two M3 standoff holes (MountingHole_3.2mm_M3, NPTH 3.2 mm, board-only
        footprints: not in the schematic, not in the BOM) each inside a 7 mm copper keep-out (rule area on all four
        copper layers: no track, no via, no plane); the adapter drawn on F.Fab and User.Drawings (outline, holes,
        header shroud, pin-1 end, power pads, CF slot edge, ribbon zone, the ROM keep-clear zone); silkscreen:
        "CF ADAPTER ON STANDOFFS", the adapter's four corners as L marks, "CF SLOT", "ADAPTER PIN 1", a circle where
        each standoff stands, "PIN 1" at J2; the re-layout design rules (gen_relayout.write_project). Silkscreen
        texts are not tidied (placement options, not a finished board)
  gen_standoff.py refill <pcb>                     -> the planes refilled
  gen_standoff.py check <pcb> <opt>                -> placement check: no overlaps, pads 0.5 mm inside the edge, X1 /
        JP1 / U$1 group as built, J2 oriented for a straight ribbon (pin 1 at the adapter's pin-1 end, beside the
        adapter, not under it), nothing tall under the adapter or the ribbon, the standoff holes clear (no pad copper
        within 4.0 mm of a hole centre: washer / nut on the bottom; no part body within 3.5 mm: the hex standoff on
        top; the 7 mm keep-out on every copper layer), the ROM (IC13) not under the adapter / a standoff / the ribbon
        and its keep-clear zone (10 mm past both short ends, 2 mm along the long sides) empty
  gen_standoff.py geom <pcb> <opt> <out.json> [<stats.json> [final]]  -> the geometry the 1:1 print needs
        (print_1to1.py, system python); "final" = the routed v2.0 board: the print draws its tracks and vias too
  gen_standoff.py shuffle <dsn> <seed> <out.dsn>   -> the DSN with its components listed in another order (seed 0:
        unchanged); build.sh routes each option in several orders and keeps the best (see shuffle())
  gen_standoff.py dsn / ses / stats / airwire / review   -> gen_relayout.py's (the trial route, same settings)
"""
import os, sys, re, json, math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_mem_v2 as GM                                     # noqa: E402
import gen_relayout as GR                                   # noqa: E402
import mem_v2_netlist as NL                                 # noqa: E402
import standoff_placements as SP                            # noqa: E402

PROJ = GM.PROJ
HOLES = ("H1", "H2")                                        # H1 = the adapter's y-max hole (pin-1 end), H2 = y-min
# parts that must not stand under the adapter or the ribbon (taller than SP.UNDER_MAX, or needing hands / a plug)
TALL = dict(GM.TALL, J2="IDE header + ribbon plug, ~13 mm", J3="power header + cable plug, ~14 mm")


def fname(opt, kind="kicad_pcb"):
    return os.path.join(HERE, "%s-standoff-%s.%s" % (PROJ, opt, kind))


# ---------------------------------------------------------------------------------------------------------------------
def build(opt, netfile, out=None):
    import pcbnew
    from pcbnew import VECTOR2I
    O = SP.OPTIONS[opt]
    FM = pcbnew.FromMM
    P = lambda x, y: VECTOR2I(FM(x), FM(y))
    nodes, paths = GM.read_netlist(netfile)
    out = out or fname(opt)
    src = open(os.path.join(GM.V13, GM.OLD + ".kicad_pcb")).read()
    assert src.count('"%s"' % GM.TITLE_OLD) == 1
    src = src.replace('"%s"' % GM.TITLE_OLD, '"%s"' % GM.TITLE_NEW)
    forms = GR.gen_cf.top_forms(src)
    kept = []
    for f in forms:
        if re.match(r"\((segment|via|arc)\b", f):
            continue
        m = re.match(r'\(footprint "[^"]*"[\s\S]*?\(property "Reference" "([^"]+)"', f)
        if m and m.group(1) in NL.REMOVED:
            continue                                        # C20-C23: not on these boards (= the schematic)
        kept.append(f)
    open(out, "w").write("(kicad_pcb\n\t" + "\n\t".join(kept) + "\n)\n")
    b = pcbnew.LoadBoard(out)
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    x1_at = (fps["X1"].GetPosition().x, fps["X1"].GetPosition().y, fps["X1"].GetOrientationDegrees())
    old_at = {r: (f.GetPosition().x, f.GetPosition().y) for r, f in fps.items()}
    nets = {}

    def net(name):
        if name not in nets:
            ni = b.FindNet(name)
            if ni is None:
                ni = pcbnew.NETINFO_ITEM(b, name)
                b.Add(ni)
            nets[name] = ni
        return nets[name]

    for ref, (value, symid, fpid, note) in NL.PARTS.items():
        lib, name = fpid.split(":")
        fp = pcbnew.FootprintLoad(os.path.join(GM.KFP, lib + ".pretty"), name)
        if fp is None:
            raise SystemExit("board: footprint %s not found" % fpid)
        fp.SetFPIDAsString(fpid)
        fp.SetReference(ref)
        fp.SetValue(value)
        fp.SetField("Description", note)
        b.Add(fp)
        fps[ref] = fp
    for ref, fp in fps.items():
        if ref not in paths:
            raise SystemExit("board: %s is not in the schematic" % ref)
        fp.SetPath(pcbnew.KIID_PATH("/" + "/".join(x for x in paths[ref].split("/") if x and x != GM.ROOT_UUID)))
        for p in fp.Pads():
            if p.GetNumber() == "":
                continue
            if (ref, p.GetNumber()) in nodes:
                p.SetNet(net(nodes[(ref, p.GetNumber())]))
            elif p.GetNetname():
                raise SystemExit("board: %s.%s is on %s but has no pin in the schematic" % (ref, p.GetNumber(),
                                                                                            p.GetNetname()))
    missing = sorted(r for r in fps if r != "X1" and r not in O["place"])
    extra = sorted(r for r in O["place"] if r not in fps)
    if missing or extra:
        raise SystemExit("option %s: parts not placed %s, unknown %s" % (opt, missing, extra))
    for ref, spec in O["place"].items():
        GR.place_fp(fps[ref], spec, pcbnew)
    for ref in NL.PARTS:
        fld = fps[ref].Reference()
        fld.SetTextSize(VECTOR2I(FM(1.0), FM(1.0)))
        fld.SetTextThickness(FM(0.15))
    delta = {r: (fps[r].GetPosition().x - old_at[r][0], fps[r].GetPosition().y - old_at[r][1]) for r in old_at}
    LABELS = {"ROM": "U$1", "RAM": "U$1", "0X8000": "U$1", "0XF000": "U$1", "-BUS-EN": "JP1", "Gnd": "JP1"}
    for d in b.GetDrawings():
        if d.GetClass() == "PCB_TEXT" and d.GetText() in LABELS:
            dx, dy = delta[LABELS[d.GetText()]]
            d.SetPosition(VECTOR2I(d.GetPosition().x + dx, d.GetPosition().y + dy))
    JUST = {"l": pcbnew.GR_TEXT_H_ALIGN_LEFT, "c": pcbnew.GR_TEXT_H_ALIGN_CENTER, "r": pcbnew.GR_TEXT_H_ALIGN_RIGHT}

    def text(s, x, y, size=1.0, angle=0, layer=pcbnew.F_SilkS, just="l"):
        t = pcbnew.PCB_TEXT(b)
        t.SetText(s)
        t.SetLayer(layer)
        t.SetTextSize(VECTOR2I(FM(size), FM(size)))
        t.SetTextThickness(FM(max(0.15, size * 0.15)))
        t.SetHorizJustify(JUST[just])
        t.SetTextAngleDegrees(angle)
        t.SetPosition(P(x, y))
        b.Add(t)

    def line(a, c, layer, w=0.2, dash=False):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a))
        s.SetEnd(P(*c))
        s.SetLayer(layer)
        s.SetWidth(FM(0.301 if dash else w))
        b.Add(s)

    def rect(R, layer, w=0.2, dash=False):
        x0, y0, x1, y1 = R
        for a, c in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            line(a, c, layer, w, dash)

    def circle(cx, cy, r, layer, w=0.2):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_CIRCLE)
        s.SetCenter(P(cx, cy))
        s.SetEnd(P(cx + r, cy))
        s.SetLayer(layer)
        s.SetWidth(FM(w))
        b.Add(s)

    for s, x, y, size, angle, just in O["silk"]:
        text(s, x, y, size, angle, just=just)
    # the standoff holes: board-only NPTH footprints + a copper keep-out on all four layers
    ad = O["adapter"]
    jg = O["jg"]
    for ref, (hx, hy) in zip(HOLES, ad["holes"]):
        fp = pcbnew.FootprintLoad(os.path.join(GM.KFP, "MountingHole.pretty"), "MountingHole_3.2mm_M3")
        fp.SetFPIDAsString("MountingHole:MountingHole_3.2mm_M3")
        fp.SetReference(ref)
        fp.SetValue("M3 standoff %g mm (CF adapter)" % SP.STANDOFF)
        fp.SetBoardOnly(True)
        fp.SetExcludedFromBOM(True)
        fp.SetExcludedFromPosFiles(True)
        fp.Reference().SetVisible(False)
        fp.SetPosition(P(hx, hy))
        b.Add(fp)
        z = pcbnew.ZONE(b)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowZoneFills(True)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
        ls = pcbnew.LSET()
        for L in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
            ls.AddLayer(L)
        z.SetLayerSet(ls)
        z.SetZoneName("standoff %s keep-out" % ref)
        ol = z.Outline()
        ol.NewOutline()
        r = SP.KEEPOUT_D / 2
        for k in range(32):
            a = 2 * math.pi * k / 32
            ol.Append(FM(hx + r * math.cos(a)), FM(hy + r * math.sin(a)))
        b.Add(z)
        circle(hx, hy, SP.HEX_R + 0.3, pcbnew.F_SilkS, 0.15)              # where the standoff stands
    # the adapter on F.Fab (placement PDF) and User.Drawings (review render: duplicated onto the silk of a copy).
    # J2 (on THIS board) solid and thick; the adapter's own header (on the adapter, 15 mm up) dashed; a ribbon arrow
    # from one to the other; J2's plug envelope dashed; the CF slot edge thick, labelled where the card goes in
    rz = rom_zone_from(fps[SP.ROM], pcbnew)
    x0, y0, x1, y1 = ad["outline"]
    jx = jg["px"] - SP.G / 2                                # J2's centre line
    hx = (ad["shroud"][0] + ad["shroud"][2]) / 2            # the adapter header's centre line
    ymid = (jg["shroud"][1] + jg["shroud"][3]) / 2
    for layer in (pcbnew.F_Fab, pcbnew.Dwgs_User):
        rect(ad["outline"], layer, 0.3)
        rect(ad["shroud"], layer, dash=True)
        line((ad["slot_x"], y0), (ad["slot_x"], y1), layer, 0.6)
        rect(ad["pwr"], layer, dash=True)
        rect(SP.ribbon_zone(jg, ad), layer, dash=True)
        rect(jg["shroud"], layer, 0.4)
        rect(jg["plug"], layer, dash=True)
        for hx_, hy_ in ad["holes"]:
            circle(hx_, hy_, SP.HX["hole_dia"] / 2, layer, 0.15)
            circle(hx_, hy_, SP.HEX_R, layer, 0.15)
        for (ox, oy), (ix, iy) in ad["pins"][:1]:
            circle(ox, oy, 0.6, layer, 0.15)
            circle(ix, iy, 0.6, layer, 0.15)
        for yy in (jg["shroud"][1] + 8.0, ymid, jg["shroud"][3] - 8.0):       # the ribbon: J2 -> adapter header
            line((jx, yy), (hx, yy), layer, 0.25)
            line((hx, yy), (hx - 1.2, yy - 0.7), layer, 0.25)
            line((hx, yy), (hx - 1.2, yy + 0.7), layer, 0.25)
        rect(rz, layer, dash=True)
        text("J2 - IDE HEADER ON THIS BOARD (pin 1 = square pad)", jg["shroud"][0] + 1.0, ymid, 0.9, 90, layer, "c")
        text("ADAPTER'S IDE HEADER (on the adapter, 15 mm above)", ad["shroud"][0] + 1.25, (y0 + y1) / 2, 0.9, 90,
             layer, "c")
        text("SHORT 40-WIRE RIBBON, pin 1 to pin 1 (%s)" % SP.RIBBON, (jg["shroud"][2] + x0) / 2 - 0.2,
             (jg["shroud"][1] + ymid) / 2 + 4.0, 0.8, 90, layer, "c")
        text("CF CARD INSERTS HERE (into the adapter)", x1 - 1.4, (y0 + y1) / 2, 1.0, 90, layer, "c")
    text("CF ADAPTER %s on 2 x M3 %g mm standoffs (H1, H2)" % (SP.HX["name"], SP.STANDOFF), x1 - 3.4, (y0 + y1) / 2,
         0.9, 90, pcbnew.F_Fab, "c")
    text("J2 plug envelope (%g mm tall)" % SP.PLUG_H, jx, jg["plug"][1] - 0.9, 0.7, 0, pcbnew.F_Fab, "c")
    text("adapter pin-1 end", ad["xa"] + 5.9, ad["pin1_end_y"] + 1.8, 0.8, 0, pcbnew.F_Fab, "c")
    text("power pads (approx.)", ad["pwr"][2] + 0.6, (ad["pwr"][1] + ad["pwr"][3]) / 2, 0.8, 90, pcbnew.F_Fab, "c")
    text("ROM: keep clear, removable", (rz[0] + rz[2]) / 2, rz[1] + 1.5, 1.0, 0, pcbnew.F_Fab, "c")
    text("Option %s: %s" % (opt.upper(), O["title"]), 20.0, 7.0, 1.5, 0, pcbnew.Dwgs_User)
    text("J2 (solid) = the IDE header ON THIS BOARD; the %s adapter (outline) and ITS OWN IDE header (dashed) sit 15 mm "
         "above on standoffs, joined to J2 by a short ribbon (arrows); dashed: J2's plug envelope, ribbon zone, power "
         "pads, ROM keep-clear zone" % SP.HX["name"], 20.0, 128.0, 1.0, 0, pcbnew.Dwgs_User)
    # silkscreen: the note, the adapter's four corners as L marks, PIN 1 at the adapter's pin-1 end
    text("CF ADAPTER ON STANDOFFS", (x0 + x1) / 2, y1 - 1.2, 1.0, 0, pcbnew.F_SilkS, "c")
    L = 3.0
    for cx, cy, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x1, y1, -1, -1), (x0, y1, 1, -1)):
        line((cx, cy), (cx + sx * L, cy), pcbnew.F_SilkS, 0.15)
        line((cx, cy), (cx, cy + sy * L), pcbnew.F_SilkS, 0.15)
    text("CF SLOT", x1 - 1.2, y0 + 7.0, 0.9, 90, pcbnew.F_SilkS, "c")
    text("ADAPTER PIN 1", x0 + 1.2, y1 - 8.0, 0.8, 90, pcbnew.F_SilkS, "c")
    # planes: thermal reliefs and antipads of the re-layout rules
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() not in ("GND", "VCC"):
            continue
        z.SetLocalClearance(FM(GR.RULES["plane_clearance"]))
        z.SetThermalReliefGap(FM(GR.RULES["thermal_gap"]))
        z.SetThermalReliefSpokeWidth(FM(GR.RULES["thermal_spoke"]))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    fx = fps["X1"]
    assert (fx.GetPosition().x, fx.GetPosition().y, fx.GetOrientationDegrees()) == x1_at
    pcbnew.SaveBoard(out, b)
    t = open(out).read()
    t = re.sub(r"\(width 0\.301\)(\s*)\(type (?:solid|default)\)", r"(width 0.3)\1(type dash)", t)
    open(out, "w").write(t)
    GR.write_project(opt, os.path.abspath(out)[:-len(".kicad_pcb")])
    print("board %s: %d footprints + H1/H2 (standoff holes, board only), X1 kept, C20-C23 left off"
          % (os.path.basename(out), len(fps)))


def rom_zone_from(fp, pcbnew):
    """the ROM's keep-clear zone: its pads' box + ROM_END past both short ends + ROM_SIDE along the long sides"""
    T = pcbnew.ToMM
    bbs = [p.GetBoundingBox() for p in fp.Pads()]
    x0, y0 = min(T(q.GetX()) for q in bbs), min(T(q.GetY()) for q in bbs)
    x1, y1 = max(T(q.GetRight()) for q in bbs), max(T(q.GetBottom()) for q in bbs)
    if y1 - y0 > x1 - x0:                                   # standing along y: the short ends are at y0 / y1
        return (x0 - SP.ROM_SIDE, y0 - SP.ROM_END, x1 + SP.ROM_SIDE, y1 + SP.ROM_END)
    return (x0 - SP.ROM_END, y0 - SP.ROM_SIDE, x1 + SP.ROM_END, y1 + SP.ROM_SIDE)


# ---------------------------------------------------------------------------------------------------------------------
def outline(b):
    """the board outline's centre lines (x0, y0, x1, y1): 17.747 / 10.025 / 195.527 / 123.995, the print grid's origin
    (the bounding box would add half the line width)"""
    import pcbnew
    T = pcbnew.ToMM
    pts = [q for s in b.GetDrawings() if s.GetLayer() == pcbnew.Edge_Cuts and s.GetClass() == "PCB_SHAPE"
           for q in (s.GetStart(), s.GetEnd())]
    return (T(min(q.x for q in pts)), T(min(q.y for q in pts)), T(max(q.x for q in pts)), T(max(q.y for q in pts)))


def rect_circle_dist(R, cx, cy):
    dx = max(R[0] - cx, 0, cx - R[2])
    dy = max(R[1] - cy, 0, cy - R[3])
    return math.hypot(dx, dy)


def inter(A, C, m=0.0):
    return min(A[2], C[2]) - max(A[0], C[0]) > m and min(A[3], C[3]) - max(A[1], C[1]) > m


def check(pcb, opt):
    import pcbnew
    O = SP.OPTIONS[opt]
    ad, jg = O["adapter"], O["jg"]
    b = pcbnew.LoadBoard(pcb)
    T = pcbnew.ToMM
    boxes = GM.body_boxes(b)
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    probs, notes = [], []
    parts = sorted(r for r in boxes if r not in HOLES)
    for i, a in enumerate(parts):
        for c in parts[i + 1:]:
            o = GM.overlap(boxes[a], boxes[c])
            if o:
                probs.append("%s / %s overlap %.2f x %.2f mm" % (a, c, o[0], o[1]))
    E = b.GetBoardEdgesBoundingBox()
    ex0, ey0, ex1, ey1 = T(E.GetX()), T(E.GetY()), T(E.GetRight()), T(E.GetBottom())
    for ref, f in fps.items():
        if ref == "X1":
            continue
        for p in f.Pads():
            pb = p.GetBoundingBox()
            if min(T(pb.GetX()) - ex0, T(pb.GetY()) - ey0, ex1 - T(pb.GetRight()), ey1 - T(pb.GetBottom())) < 0.5:
                probs.append("%s pad %s within 0.5 mm of the board edge" % (ref, p.GetNumber()))
        bx = boxes[ref]
        if bx[0] < ex0 or bx[1] < ey0 or bx[2] > ex1 + 0.01 or bx[3] > ey1:
            probs.append("%s body outside the board outline" % ref)
    # X1, JP1 and the block jumpers U$1 / RN7 / RN8 on the built card's pads (IC18 and C24 beside them as in the
    # top-edge options: relayout_placements.UBLOCK_BUILT)
    built = pcbnew.LoadBoard(os.path.join(GM.V13, GM.OLD + ".kicad_pcb"))
    bpads = {(f.GetReference(), p.GetNumber()): (T(p.GetPosition().x), T(p.GetPosition().y))
             for f in built.GetFootprints() if f.GetReference() in ("X1", "JP1", "U$1", "RN7", "RN8") for p in f.Pads()}
    for (ref, num), at in sorted(bpads.items()):
        got = [(T(p.GetPosition().x), T(p.GetPosition().y)) for p in fps[ref].Pads() if p.GetNumber() == num]
        if not any(math.hypot(g[0] - at[0], g[1] - at[1]) < 0.02 for g in got):
            probs.append("%s pad %s not where the built card has it" % (ref, num))
            break
    # J2: pin 1 at the adapter's pin-1 end (y max), odd row toward the adapter (+x), beside the adapter, not under it
    j2 = {p.GetNumber(): (T(p.GetPosition().x), T(p.GetPosition().y)) for p in fps["J2"].Pads()}
    ys = [v[1] for v in j2.values()]
    if abs(j2["1"][1] - max(ys)) > 1e-3 or abs(j2["1"][1] - ad["pin1_end_y"]) > 0.3:
        probs.append("J2 pin 1 (y %.2f) is not at the adapter's pin-1 end (y %.2f)" % (j2["1"][1], ad["pin1_end_y"]))
    if not j2["1"][0] > j2["2"][0]:
        probs.append("J2's odd row is not on the adapter side")
    if boxes["J2"][2] > ad["outline"][0] - 0.3:
        probs.append("J2 reaches under the adapter (courtyard x %.2f, adapter edge %.2f)" % (boxes["J2"][2],
                                                                                            ad["outline"][0]))
    # J2's plug envelope (the shroud + PLUG_SIDE all round, PLUG_H tall): clear of the adapter outline, the adapter's
    # header edge J2_SHROUD_GAP from J2's shroud (the ribbon folds up out of J2's plug and down into the adapter's),
    # and no other part's body inside it. Options made before the rule (a, b: no "gap") get a note, not a failure
    pe, sgap = jg["plug"], ad["outline"][0] - jg["shroud"][2]
    pnotes = []
    if inter(pe, ad["outline"]):
        pnotes.append("J2's plug envelope reaches %.2f mm under the adapter" % (pe[2] - ad["outline"][0]))
    if sgap < SP.J2_SHROUD_GAP - 1e-6:
        pnotes.append("J2's shroud only %.2f mm from the adapter's header edge (rule %.1f)" % (sgap, SP.J2_SHROUD_GAP))
    for r in parts:
        if r != "J2" and inter(boxes[r], pe):
            pnotes.append("%s inside J2's plug envelope" % r)
    if O.get("gap") is None:
        notes += ["NOTE (option made before the J2 plug-envelope rule): " + x for x in pnotes]
    else:
        probs += pnotes
    # nothing tall under the adapter or the ribbon
    rz = SP.ribbon_zone(jg, ad)
    for r in TALL:
        if r in boxes and r != "J2":
            if inter(boxes[r], ad["outline"]):
                probs.append("%s (%s) under the adapter" % (r, TALL[r]))
            if inter(boxes[r], rz):
                probs.append("%s (%s) under the ribbon" % (r, TALL[r]))
    under = sorted(r for r in parts if inter(boxes[r], ad["outline"]))
    # the standoff holes
    pads = [(f.GetReference(), p) for f in b.GetFootprints() for p in f.Pads() if f.GetReference() not in HOLES]
    hole_near = []
    for h, (hx, hy) in zip(HOLES, ad["holes"]):
        f = fps.get(h)
        if f is None or abs(T(f.GetPosition().x) - hx) > 1e-3 or abs(T(f.GetPosition().y) - hy) > 1e-3:
            probs.append("%s missing or not at the adapter's hole (%.2f, %.2f)" % (h, hx, hy))
        dpad = min((rect_circle_dist((T(p.GetBoundingBox().GetX()), T(p.GetBoundingBox().GetY()),
                                      T(p.GetBoundingBox().GetRight()), T(p.GetBoundingBox().GetBottom())), hx, hy),
                    "%s.%s" % (r, p.GetNumber())) for r, p in pads)
        dbody = min((rect_circle_dist(boxes[r], hx, hy), r) for r in parts)
        if dpad[0] < SP.PAD_CLEAR:
            probs.append("%s: pad %s %.2f mm from the hole centre (min %.1f: washer / nut)" % (h, dpad[1], dpad[0],
                                                                                            SP.PAD_CLEAR))
        if dbody[0] < SP.BODY_CLEAR:
            probs.append("%s: %s body %.2f mm from the hole centre (min %.1f: the standoff)" % (h, dbody[1], dbody[0],
                                                                                             SP.BODY_CLEAR))
        if min(hx - ex0, hy - ey0, ex1 - hx, ey1 - hy) < SP.KEEPOUT_D / 2 + 0.5:
            probs.append("%s: keep-out circle too near the board edge" % h)
        ox, oy = outline(b)[:2]
        hole_near.append("%s (%.2f, %.2f) = print grid (%.1f, %.1f): nearest pad %s %.1f mm, nearest body %s %.1f mm"
                         % (h, hx, hy, hx - ox, hy - oy, dpad[1], dpad[0], dbody[1], dbody[0]))
    ko = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowTracks() and z.GetDoNotAllowVias()
          and z.GetDoNotAllowZoneFills() and z.GetLayerSet().Contains(pcbnew.In1_Cu)
          and z.GetLayerSet().Contains(pcbnew.In2_Cu) and z.GetLayerSet().Contains(pcbnew.F_Cu)
          and z.GetLayerSet().Contains(pcbnew.B_Cu)]
    if len(ko) != 2:
        probs.append("%d standoff keep-out rule areas on all four copper layers, expected 2" % len(ko))
    # the ROM
    rom = rom_zone_from(fps[SP.ROM], pcbnew)
    g = SP.ROM_ADAPTER_GAP
    grow = lambda R: (R[0] - g, R[1] - g, R[2] + g, R[3] + g)
    if inter(boxes[SP.ROM], grow(ad["outline"])) or inter(rom, grow(ad["outline"])):
        probs.append("the ROM or its keep-clear zone within %.0f mm of the adapter" % g)
    if inter(rom, grow(rz)):
        probs.append("the ROM's keep-clear zone within %.0f mm of the ribbon zone" % g)
    for hx, hy in ad["holes"]:
        if rect_circle_dist(rom, hx, hy) < SP.HEX_R + g:
            probs.append("the ROM's keep-clear zone near a standoff")
    inrom = sorted(r for r in parts if r != SP.ROM and inter(boxes[r], rom))
    for r in inrom:
        probs.append("%s in the ROM keep-clear zone" % r)
    dro = min(rect_circle_dist(ad["outline"], x, y) for x in (rom[0], rom[2]) for y in (rom[1], rom[3]))
    print("placement %s: %s" % (os.path.basename(pcb), "OK - no overlaps, pads 0.5 mm inside the edge, X1 / JP1 / U$1 "
          "group as built, J2 oriented for a straight ribbon, nothing tall under the adapter or the ribbon, standoff "
          "holes clear, ROM keep-clear zone empty and away from the adapter" if not probs else "%d problem(s)" % len(probs)))
    for x in probs:
        print("    ", x)
    x0, y0, x1, y1 = ad["outline"]
    ox, oy = outline(b)[:2]
    print("    adapter x %.2f-%.2f, y %.2f-%.2f (print grid x %.1f-%.1f, y %.1f-%.1f); header edge x %.2f, slot edge x %.2f"
          % (x0, x1, y0, y1, x0 - ox, x1 - ox, y0 - oy, y1 - oy, x0, x1))
    print("    J2 pin 1 (%.2f, %.2f), pins y %.2f-%.2f, odd row x %.2f, even row x %.2f, courtyard to x %.2f (%.2f mm "
          "before the adapter's header edge)" % (j2["1"][0], j2["1"][1], min(ys), max(ys), j2["1"][0], j2["2"][0],
                                                boxes["J2"][2], ad["outline"][0] - boxes["J2"][2]))
    print("    J2 shroud x %.2f-%.2f, plug envelope x %.2f-%.2f / y %.2f-%.2f (%.0f mm tall); %.2f mm from the shroud to "
          "the adapter's header edge; ribbon between the plugs %s (minimum ~%.0f mm)"
          % (jg["shroud"][0], jg["shroud"][2], pe[0], pe[2], pe[1], pe[3], SP.PLUG_H, sgap, SP.RIBBON,
             SP.ribbon_length(jg, ad, SP.STANDOFF)))
    for x in notes:
        print("    " + x)
    for s in hole_near:
        print("    " + s)
    print("    under the adapter (low parts only): %s" % ", ".join(under))
    print("    ROM %s keep-clear zone x %.1f-%.1f, y %.1f-%.1f, holds: %s; %.1f mm from the adapter"
          % (SP.ROM, rom[0], rom[2], rom[1], rom[3], ", ".join(inrom) or "nothing", dro))
    return not probs


# ---------------------------------------------------------------------------------------------------------------------
def geom(pcb, opt, out, stats=None, final=False):
    """everything print_1to1.py draws, in board mm; final: the routed v2.0 board (memory-v2.0.kicad_pcb), whose
    tracks and vias the print draws too"""
    import pcbnew
    O = SP.OPTIONS[opt]
    b = pcbnew.LoadBoard(pcb)
    T = pcbnew.ToMM
    boxes = GM.body_boxes(b)
    E = b.GetBoardEdgesBoundingBox()
    fps = []
    for f in b.GetFootprints():
        r = f.GetReference()
        pads = []
        for p in f.Pads():
            bb = p.GetBoundingBox()
            pads.append(dict(n=p.GetNumber(), x=T(p.GetPosition().x), y=T(p.GetPosition().y),
                             w=T(bb.GetWidth()), h=T(bb.GetHeight()), npth=p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH))
        fps.append(dict(ref=r, value=f.GetValue(), box=boxes[r], pads=pads, hole=r in HOLES))
    ad = O["adapter"]
    jg = O["jg"]
    fprom = [f for f in b.GetFootprints() if f.GetReference() == SP.ROM][0]
    d = dict(opt=opt, title=O["title"], edge=outline(b),
             fps=fps, adapter=ad, j2=jg, ribbon=SP.ribbon_zone(jg, ad), rom=rom_zone_from(fprom, pcbnew),
             rom_ref=SP.ROM, hx=SP.HX, standoff=SP.STANDOFF, standoff_alt=SP.STANDOFF_ALT, hex_r=SP.HEX_R,
             keepout_d=SP.KEEPOUT_D, plug_h=SP.PLUG_H, plug_side=SP.PLUG_SIDE, ribbon_text=SP.RIBBON,
             ribbon_min=SP.ribbon_length(jg, ad, SP.STANDOFF), stats=json.load(open(stats)) if stats and os.path.exists(stats) else None,
             final=bool(final), tracks=[], vias=[])
    for tr in b.GetTracks():
        if tr.Type() == pcbnew.PCB_VIA_T:
            d["vias"].append((T(tr.GetPosition().x), T(tr.GetPosition().y), T(tr.GetWidth(pcbnew.F_Cu))))
        else:
            d["tracks"].append((T(tr.GetStart().x), T(tr.GetStart().y), T(tr.GetEnd().x), T(tr.GetEnd().y),
                                b.GetLayerName(tr.GetLayer()), T(tr.GetWidth())))
    json.dump(d, open(out, "w"), indent=1)
    print("geom -> %s" % os.path.basename(out))


def shuffle(dsn, seed, out):
    """the same DSN with the components of its (placement ...) section in another order (seed 0 = unchanged).
    Freerouting 1.9 gives the same result for the same file (its pass limit changes nothing: it stops by itself), but
    the order in which the DSN lists the components changes its route (the order of the nets does not). The trial
    route of an option is the best of a few orders: same placement, same rules, only the listing order differs"""
    import random
    t = open(dsn).read()
    j = t.index("(placement") + len("(placement")
    comps, k = [], j
    while re.compile(r"\s*\(component\b").match(t, k):
        a = t.index("(component", k)
        depth, q = 0, a
        while True:
            if t[q] == "(":
                depth += 1
            elif t[q] == ")":
                depth -= 1
                if depth == 0:
                    break
            q += 1
        comps.append(t[a:q + 1])
        k = q + 1
    if int(seed):
        random.Random(int(seed)).shuffle(comps)
    open(out, "w").write(t[:j] + "".join("\n    " + c for c in comps) + t[k:])
    print("shuffle %s: %d component groups, seed %s" % (os.path.basename(out), len(comps), seed))


if __name__ == "__main__":
    cmd = sys.argv[1]
    ok = True
    if cmd == "board":
        build(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    elif cmd == "refill":
        GM.refill(sys.argv[2])
    elif cmd == "check":
        ok = check(sys.argv[2], sys.argv[3])
    elif cmd == "geom":
        geom(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else None,
             len(sys.argv) > 6 and sys.argv[6] == "final")
    elif cmd == "airwire":
        tot, conns, nn = GR.airwire(sys.argv[2])
        print("airwire %s: %.0f mm, %d connections on %d signal nets" % (os.path.basename(sys.argv[2]), tot, conns, nn))
    elif cmd == "review":
        GM.review_copy(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "shuffle":
        shuffle(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "dsn":
        GR.dsn(sys.argv[2], sys.argv[3])
    elif cmd == "ses":
        GR.ses(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "stats":
        r = GR.stats(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
        if len(sys.argv) > 5:
            json.dump(r, open(sys.argv[5], "w"))
    else:
        raise SystemExit("unknown command " + cmd)
    sys.stdout.flush()
    os._exit(0 if ok else 1)
