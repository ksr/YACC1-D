#!/usr/bin/env python3
"""route_v2.py - turn the chosen placement (option B) into the routed I/O card v2.0 board io-v2.0.kicad_pcb (2026-09-23).

Run with KiCad's bundled Python (pcbnew); `ROUTE=1 build.sh` runs the steps in this order:

    route_v2.py prep <options/io-v2.0-option-b.kicad_pcb> io-v2.0.kicad_pcb
        copy the placed board; LOCK the kept v1.1 copper; apply FINAL_MOVES (JP2); replace the placement-review
        adapter drawing with the TAODAN strip on F.Fab; J2 pin-1 mark; tidy the reference texts of new/moved parts
    route_v2.py first_nets io-v2.0.kicad_pcb reports/route-stage-a-nets.txt
        the signal nets with a broken v1.1 connection (they must thread between the kept copper)
    kicad_route.py export_dsn; route_v2.py dsn_split   (those nets -> Specctra class "First")
    Freerouting -inc kicad_default,Power               (stage A: only class First)
    route_v2.py import io-v2.0.kicad_pcb <ses> --lock  (the kept copper is proven untouched; all copper locked)
    route_v2.py finish io-v2.0.kicad_pcb reports/route-stage-a-nets.txt --lock
        the grid router finishes what Freerouting left of those nets
    kicad_route.py export_dsn; Freerouting             (stage B: everything else)
    route_v2.py import io-v2.0.kicad_pcb <ses>         (router copper unlocked again, kept copper stays locked)
    route_v2.py finish io-v2.0.kicad_pcb --rip
        the grid router with rip-up: routes every connection still open; a path may go through unlocked router
        copper of other nets, which is ripped out and routed again (negotiated: fought-over cells get dearer; a net
        ripped PROTECT times is protected). As a last resort (no progress for 8 rounds) kept v1.1 copper may be
        ripped too, at KEEP_RIP per cell, and every such item is listed in reports/route-kept-removed.txt (none was
        on the committed board). Duplicates and dangling router stubs are removed.

Design rules = v1.1's (the project's Default net class, from the Eagle design: 0.1524 mm track, 0.127 mm clearance,
0.508/0.254 mm vias, 0.381 mm copper to edge). The Power class (GND, VCC; gen_io_v2.py writes it into the project)
routes at POWER_W = 0.3048 mm, twice v1.1's 0.1524 mm power tracks; the grid router falls back to 0.1524 mm only if
0.3048 mm cannot get through (it never had to on the committed board).

Why a grid router of its own: Freerouting 1.9 leaves a dozen connections open on this board whatever the order (some
of them even when routing a net alone), mostly v1.1 nets whose kept copper ends in a tight spot. The grid router is
simple and slow (pure Python, 0.127 mm grid) but it is exact about the rules and finds those paths.
"""
import os, sys, re, json, subprocess, collections, math

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "kicad"))
sys.path.insert(0, HERE)
import pcbnew                                         # noqa: E402
from pcbnew import VECTOR2I                           # noqa: E402
import kicad_route as KR                              # noqa: E402

CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
FM, T = pcbnew.FromMM, pcbnew.ToMM
POWER_W = 0.3048                                     # new GND/VCC tracks (12 mil); v1.1's are all 0.1524
SIG_W = 0.1524
VIA_D, VIA_H = 0.508, 0.254                           # v1.1's vias (all 158 of them)

# the parts whose reference texts tidy_silk places: every CF part and every v1.1 part option B moved (+ JP2 below)
from route_check import CF_PARTS, SWITCHES, MOVED     # noqa: E402
# placement changes made after option B was chosen: ref -> (x, y, rotation) of the footprint origin (pin 1)
FINAL_MOVES = {
    # IDE pin-20 power jumper: header + shunt is ~8.5 mm tall, so it may not sit under the adapter, which overhangs
    # each end of J2 (Ken's rule: nothing taller than ~8 mm within 12 mm of either end of J2 along its axis). Option
    # B had it 6 mm left of J2's end; here it is 14 mm left of it, under RN3's left half, standing (pin 1 at the top).
    "JP2": (31.0, 17.8, 0),
}
ADAPTER_LEN = 70.0                                    # TAODAN CF-IDE40: 70 x 63 mm PCB, socket along a 70 mm edge
ADAPTER_STRIP = 8.0                                   # the strip drawn on F.Fab: socket body + the PCB either side


def _save(b, path):
    pcbnew.SaveBoard(path, b)


def _kept_key(t):
    if t.Type() == pcbnew.PCB_VIA_T:
        p = t.GetPosition()
        return ("via", p.x, p.y, t.GetWidth(pcbnew.F_Cu), t.GetDrill(), t.GetNetname())
    s, e = t.GetStart(), t.GetEnd()
    a, c = sorted([(s.x, s.y), (e.x, e.y)])
    return ("trk", a, c, t.GetWidth(), t.GetLayer(), t.GetNetname())


# ---------------------------------------------------------------------------------------------------------------------
# silkscreen: reference texts of the new and moved parts clear of pads, of other silk and of each other
def _silk_obstacles(b, skip_fp):
    """(shape, clearance mm) of everything a reference text must not touch"""
    obs = []
    for f in b.GetFootprints():
        for p in f.Pads():
            obs.append((p.GetEffectiveShape(pcbnew.F_Cu), 0.2))
        for g in f.GraphicalItems():
            if g.GetLayer() == pcbnew.F_SilkS and g.GetClass() not in ("PCB_TEXT", "PCB_FIELD"):
                obs.append((g.GetEffectiveShape(pcbnew.F_SilkS), 0.12))
            elif g.GetLayer() == pcbnew.F_SilkS and g.GetClass() == "PCB_TEXT" and g.IsVisible():
                obs.append((g.GetEffectiveShape(pcbnew.F_SilkS), 0.12))
        if f.GetReference() == skip_fp:
            continue
        for fld in (f.Reference(), f.Value()):
            if fld.IsVisible() and fld.GetLayer() == pcbnew.F_SilkS:
                obs.append((fld.GetEffectiveShape(pcbnew.F_SilkS), 0.15))
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.F_SilkS:
            obs.append((d.GetEffectiveShape(pcbnew.F_SilkS), 0.15))
    return obs


def _body_box(f):
    """mm (x0, y0, x1, y1) of the pads + silk graphics of a footprint (no texts)"""
    bs = [p.GetBoundingBox() for p in f.Pads()]
    bs += [g.GetBoundingBox() for g in f.GraphicalItems()
           if g.GetClass() not in ("PCB_TEXT", "PCB_FIELD") and g.GetLayer() == pcbnew.F_SilkS]
    return (min(T(q.GetX()) for q in bs), min(T(q.GetY()) for q in bs),
            max(T(q.GetRight()) for q in bs), max(T(q.GetBottom()) for q in bs))


def tidy_silk(b, refs):
    E = b.GetBoardEdgesBoundingBox()
    ex0, ey0, ex1, ey1 = T(E.GetX()) + 0.6, T(E.GetY()) + 0.6, T(E.GetRight()) - 0.6, T(E.GetBottom()) - 0.6
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    moved, stuck = [], []
    for ref in refs:
        f = fps[ref]
        r = f.Reference()
        obs = _silk_obstacles(b, ref)

        def free():
            bb = r.GetBoundingBox()
            if T(bb.GetX()) < ex0 or T(bb.GetY()) < ey0 or T(bb.GetRight()) > ex1 or T(bb.GetBottom()) > ey1:
                return False
            s = r.GetEffectiveShape(pcbnew.F_SilkS)
            return not any(s.Collide(o, FM(c)) for o, c in obs)

        if ref not in SWITCHES and free():
            continue
        home = (r.GetPosition(), r.GetTextAngleDegrees())
        x0, y0, x1, y1 = _body_box(f)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        r.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        r.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        if ref in SWITCHES:
            # the switch row sits 0.9 mm from the CF chip column now, so v1.1's place for these (left of the switch)
            # is gone; every switch gets its reference in the 1.4 mm gap above its own body, at the pin-1 end, the
            # same way for all of them (0.9 mm text: v1.1's 1.6 mm does not fit the gap)
            r.SetTextSize(VECTOR2I(FM(0.9), FM(0.9)))
            r.SetTextThickness(FM(0.14))
            r.SetTextAngleDegrees(0)
            bb = r.GetBoundingBox()
            r.SetPosition(VECTOR2I(FM(x0 + T(bb.GetWidth()) / 2 + 0.3), FM(y0 - 0.14 - T(bb.GetHeight()) / 2)))
            if free():
                moved.append("%s(above its body)" % ref)
                continue
        cands = []
        for ang in (0, 90):
            r.SetTextAngleDegrees(ang)
            bb = r.GetBoundingBox()
            hw, hh = T(bb.GetWidth()) / 2, T(bb.GetHeight()) / 2
            for k in range(6):
                g = 0.25 + 0.6 * k
                for px, py in ((cx, y0 - g - hh), (cx, y1 + g + hh), (x0 - g - hw, cy), (x1 + g + hw, cy),
                               (x0 + hw, y0 - g - hh), (x1 - hw, y0 - g - hh), (x0 + hw, y1 + g + hh),
                               (x1 - hw, y1 + g + hh), (x0 - g - hw, y0 + hh), (x0 - g - hw, y1 - hh),
                               (x1 + g + hw, y0 + hh), (x1 + g + hw, y1 - hh)):
                    cands.append((k, math.hypot(px - T(home[0].x), py - T(home[0].y)), ang, px, py))
            cands.append((6, 0, ang, cx, cy))             # inside the body: last resort
        cands.sort(key=lambda c: (c[0], c[1]))
        for k, _, ang, px, py in cands:
            r.SetTextAngleDegrees(ang)
            r.SetPosition(VECTOR2I(FM(px), FM(py)))
            if free():
                moved.append("%s(%.1f,%.1f%s)" % (ref, px, py, "" if ang == 0 else " r90"))
                break
        else:
            r.SetPosition(home[0])
            r.SetTextAngleDegrees(home[1])
            stuck.append(ref)
    print("tidy_silk: %d reference text(s) moved %s; no free spot: %s" % (len(moved), " ".join(moved), stuck or "none"))
    return stuck


# ---------------------------------------------------------------------------------------------------------------------
def adapter_drawing(b):
    """drop the placement review's adapter outline (User.Drawings: the old standoff-mounted adapter, its notes and the
    option title) and draw the TAODAN CF-IDE40 on F.Fab instead: it plugs straight onto J2 and stands perpendicular to
    the card, so all it occupies on the board is a 70 mm strip centred on J2 (it overhangs each end of the header)"""
    old = [d for d in b.GetDrawings() if d.GetLayer() == pcbnew.Dwgs_User]      # removed at the text level by
                                                                                   # prep (no Remove() in KiCad 10 SWIG)
    j2 = b.FindFootprintByReference("J2")
    xs = [T(p.GetPosition().x) for p in j2.Pads()]
    ys = [T(p.GetPosition().y) for p in j2.Pads()]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    x0, x1 = cx - ADAPTER_LEN / 2, cx + ADAPTER_LEN / 2
    y0, y1 = cy - ADAPTER_STRIP / 2, cy + ADAPTER_STRIP / 2
    for a, c in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(VECTOR2I(FM(a[0]), FM(a[1])))
        s.SetEnd(VECTOR2I(FM(c[0]), FM(c[1])))
        s.SetLayer(pcbnew.F_Fab)
        s.SetWidth(FM(0.2))
        b.Add(s)
    for txt, y in (("TAODAN CF-IDE40 plugs onto J2, stands perpendicular (70 mm, centred on J2)", y1 + 1.4),
                   ("parts under its 70 mm span: < 8 mm tall", y1 + 3.0)):
        tx = pcbnew.PCB_TEXT(b)
        tx.SetText(txt)
        tx.SetLayer(pcbnew.F_Fab)
        tx.SetTextSize(VECTOR2I(FM(1.0), FM(1.0)))
        tx.SetTextThickness(FM(0.15))
        tx.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        tx.SetPosition(VECTOR2I(FM(x0 + 0.5), FM(y)))
        b.Add(tx)
    print("adapter: %d review drawing item(s) removed; F.Fab outline x %.2f..%.2f, y %.2f..%.2f (J2 pins x %.2f..%.2f)"
          % (len(old), x0, x1, y0, y1, min(xs), max(xs)))


def pin1_mark(b):
    """a '1' inside J2's shroud beside pin 1: the footprint's own pin-1 triangle sits at the board edge, where the fab
    may clip it"""
    j2 = b.FindFootprintByReference("J2")
    p1 = [p for p in j2.Pads() if p.GetNumber() == "1"][0].GetPosition()
    x, y = T(p1.x) + 2.3, T(p1.y)
    for d in b.GetDrawings():
        if d.GetClass() == "PCB_TEXT" and d.GetText() == "1" and abs(T(d.GetPosition().x) - x) < 0.01:
            return
    tx = pcbnew.PCB_TEXT(b)
    tx.SetText("1")
    tx.SetLayer(pcbnew.F_SilkS)
    tx.SetTextSize(VECTOR2I(FM(1.0), FM(1.0)))
    tx.SetTextThickness(FM(0.15))
    tx.SetPosition(VECTOR2I(FM(x), FM(y)))
    b.Add(tx)
    print("pin1_mark: '1' at (%.2f, %.2f) beside J2 pin 1" % (x, y))


def prep(src, out):
    # pcbnew's SaveBoard rewrites the .kicad_pro beside the board from the project it loaded (the option's, which has
    # no Power class): keep the v2.0 project (gen_io_v2.py sch writes it with the net classes) and put it back after
    pro = out[:-len(".kicad_pcb")] + ".kicad_pro"
    protext = open(pro).read()
    b = pcbnew.LoadBoard(src)
    n = 0
    for t in b.GetTracks():
        t.SetLocked(True)
        n += 1
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    for ref, (x, y, rot) in FINAL_MOVES.items():
        fps[ref].SetOrientationDegrees(rot)
        fps[ref].SetPosition(VECTOR2I(FM(x), FM(y)))
    adapter_drawing(b)
    pin1_mark(b)
    tidy_silk(b, CF_PARTS + MOVED)
    _save(b, out)
    txt = open(out).read()
    forms = KR.top_forms(txt)
    keep = [f for f in forms if not (f.startswith("(gr_") and '(layer "Dwgs.User")' in f)]
    open(out, "w").write("(kicad_pcb\n\t" + "\n\t".join(keep) + "\n)\n")
    open(pro, "w").write(protext)
    b = pcbnew.LoadBoard(out)
    keys = sorted(map(repr, (_kept_key(t) for t in b.GetTracks())))
    open(out + ".kept", "w").write("\n".join(keys) + "\n")
    print("prep: %s <- %s; %d kept v1.1 copper items locked (list in %s.kept); moved after the choice: %s"
          % (os.path.basename(out), os.path.basename(src), n, os.path.basename(out), FINAL_MOVES))


def first_nets(brd, out):
    """the signal nets with a broken v1.1 connection (a DRC unconnected item between two v1.1 items: a v1.1 pad or
    kept v1.1 copper). They are the constrained ones - they must thread between the kept copper - so stage A routes
    them alone, before the CF section and the power nets take the room."""
    j = brd + ".drc.json"
    subprocess.run([CLI, "pcb", "drc", "--format", "json", "-o", j, brd], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    d = json.load(open(j))
    os.remove(j)
    nets = set()
    for u in d.get("unconnected_items", []):
        ok = True
        for it in u["items"]:
            m = re.match(r"(?:PTH pad \S+|Track|Via) \[([^\]]*)\](?: on \S+)?(?: of (\S+))?", it["description"])
            if not m or (m.group(2) or "") in CF_PARTS:
                ok = False
            name = m.group(1) if m else None
        if ok and name not in ("GND", "VCC"):
            nets.add(name)
    open(out, "w").write("\n".join(sorted(nets)) + "\n")
    print("first_nets: %d signal nets with a broken v1.1 connection -> %s" % (len(nets), os.path.basename(out)))


def dsn_split(dsn, netfile):
    """move the nets listed in netfile out of the DSN's default class into a class of their own, 'First', with the
    same rules; Freerouting's -inc kicad_default,Power then routes only them"""
    want = set(open(netfile).read().split("\n")) - {""}
    t = open(dsn).read()
    m = re.search(r'\(class kicad_default (.*?)(\(circuit.*?\)\s*\(rule.*?\)\s*\))\s*\)', t, re.S)
    names = re.findall(r'"[^"]*"|[^\s()]+', m.group(1))
    unq = lambda s: s[1:-1] if s.startswith('"') else s
    keep = [n for n in names if unq(n) not in want]
    first = [n for n in names if unq(n) in want]
    if len(first) != len(want):
        raise SystemExit("dsn_split: nets not in the default class: %s" % (want - {unq(n) for n in first}))
    body = m.group(2)
    new = ("(class kicad_default %s\n      %s\n    )\n    (class First %s\n      %s\n    )"
           % (" ".join(keep), body, " ".join(first), body))
    t = t[:m.start()] + new + t[m.end():]
    open(dsn, "w").write(t)
    print("dsn_split: class First = %d nets" % len(first))


def import_ses(brd, ses, lock_all=False):
    kept = set(open(brd + ".kept").read().split("\n")) - {""}
    before = pcbnew.LoadBoard(brd)
    prev = {repr(_kept_key(t)) for t in before.GetTracks()}
    b = pcbnew.LoadBoard(brd)
    if not pcbnew.ImportSpecctraSES(b, ses):
        raise SystemExit("import: ImportSpecctraSES failed")
    got = {repr(_kept_key(t)): t for t in b.GetTracks()}
    lost = kept - set(got)
    if lost:
        raise SystemExit("import: %d kept v1.1 copper item(s) changed by the router, e.g. %s" % (len(lost), sorted(lost)[:3]))
    for k, tr in got.items():
        tr.SetLocked(k in kept or lock_all)
    new = [tr for k, tr in got.items() if k not in prev]
    _save(b, brd)
    print("import: %d kept v1.1 items intact; this pass added %d track segments + %d vias%s"
          % (len(kept), sum(1 for tr in new if tr.Type() == pcbnew.PCB_TRACE_T),
             sum(1 for tr in new if tr.Type() == pcbnew.PCB_VIA_T), " (all locked for the next pass)" if lock_all else ""))


# ---------------------------------------------------------------------------------------------------------------------
# finish: a small grid maze router for the connections Freerouting leaves open
GRID = 0.127                                          # mm (half of v1.1's 0.254 mm track pitch)
CLEAR = 0.127                                         # v1.1's clearance
EDGE = 0.381                                          # v1.1's copper-to-edge rule
MARGIN = 0.03                                         # extra over the rules, for the grid's discretisation
VIA_COST = 60                                         # in grid steps (7.6 mm of track)
BEND = 3.0                                            # per 45-degree turn, in grid steps
RIP = 40                                              # per grid step through rippable router copper
PROTECT = 4                                           # rip-ups of one net before its copper is protected
KEEP_RIP = 120                                        # per grid step through kept v1.1 copper (last resort only)
HOLE_HOLE = 0.254                                     # v1.1's min hole-to-hole


class Grid:
    """per layer, per cell: 0 = free, net code = only that net's copper within reach, -1 = two or more nets. One grid
    per 'reach' (half track width + clearance, or via radius + clearance)."""

    def __init__(self, b, reach, holes=False, soft=frozenset(), kept=frozenset()):
        """soft: uuids of router copper that may be ripped up, marked in sg; kept: uuids of kept v1.1 copper that may be
        ripped up as a last resort, marked in kg; everything else is marked in hd (hard)"""
        E = b.GetBoardEdgesBoundingBox()
        self.x0, self.y0 = T(E.GetX()), T(E.GetY())
        self.nx = int(T(E.GetWidth()) / GRID) + 1
        self.ny = int(T(E.GetHeight()) / GRID) + 1
        self.reach = reach
        import array
        self.hd = [array.array("i", [0]) * (self.nx * self.ny) for _ in range(2)]
        self.sg = [array.array("i", [0]) * (self.nx * self.ny) for _ in range(2)]
        self.kg = [array.array("i", [0]) * (self.nx * self.ny) for _ in range(2)]
        self.g = self.hd                                 # the grid mark() writes to
        ex1, ey1 = self.x0 + T(E.GetWidth()), self.y0 + T(E.GetHeight())
        lim = EDGE + reach - CLEAR + MARGIN + 0.1        # copper edge rule, not clearance
        for L in (0, 1):
            self.box(L, self.x0 - 1, self.y0 - 1, self.x0 + lim, ey1 + 1, -1)
            self.box(L, ex1 - lim, self.y0 - 1, ex1 + 1, ey1 + 1, -1)
            self.box(L, self.x0 - 1, self.y0 - 1, ex1 + 1, self.y0 + lim, -1)
            self.box(L, self.x0 - 1, ey1 - lim, ex1 + 1, ey1 + 1, -1)
        for z in b.Zones():                              # rule areas: the LCD keepout (F.Cu, no tracks, no vias)
            if not z.GetIsRuleArea():
                continue
            bb = z.GetBoundingBox()
            zx0, zy0, zx1, zy1 = T(bb.GetX()), T(bb.GetY()), T(bb.GetRight()), T(bb.GetBottom())
            layers = [L for L, lid in ((0, pcbnew.F_Cu), (1, pcbnew.B_Cu)) if z.IsOnLayer(lid)]
            for L in layers:
                self.box(L, zx0 - reach, zy0 - reach, zx1 + reach, zy1 + reach, -1)
        for f in b.GetFootprints():
            for p in f.Pads():                           # a pad on no net (a mounting hole, Y1 pin 1) blocks all
                self.shape(p, p.GetNetCode() or -1, [0, 1], reach)
        if holes:                                        # a via's drill: hole-to-hole 0.254 mm to every hole,
            for f in b.GetFootprints():                  # the via's own net included
                for p in f.Pads():
                    if p.GetDrillSize().x:
                        for L in (0, 1):
                            self.disk(L, T(p.GetPosition().x), T(p.GetPosition().y),
                                      T(max(p.GetDrillSize().x, p.GetDrillSize().y)) / 2 + VIA_H / 2 + HOLE_HOLE, -1)
            for tr in b.GetTracks():
                if tr.Type() == pcbnew.PCB_VIA_T and tr.m_Uuid.AsString() not in soft | kept:
                    for L in (0, 1):
                        self.disk(L, T(tr.GetPosition().x), T(tr.GetPosition().y), VIA_H + HOLE_HOLE, -1)
        for tr in b.GetTracks():
            u = tr.m_Uuid.AsString()
            self.g = self.sg if u in soft else self.kg if u in kept else self.hd
            if tr.Type() == pcbnew.PCB_VIA_T:
                if holes and self.g is not self.hd:
                    for L in (0, 1):
                        self.disk(L, T(tr.GetPosition().x), T(tr.GetPosition().y), VIA_H + HOLE_HOLE, -1)
                self.disk(0, T(tr.GetPosition().x), T(tr.GetPosition().y), T(tr.GetWidth(pcbnew.F_Cu)) / 2 + reach,
                          tr.GetNetCode())
                self.disk(1, T(tr.GetPosition().x), T(tr.GetPosition().y), T(tr.GetWidth(pcbnew.F_Cu)) / 2 + reach,
                          tr.GetNetCode())
            else:
                L = 0 if tr.GetLayer() == pcbnew.F_Cu else 1
                self.seg(L, T(tr.GetStart().x), T(tr.GetStart().y), T(tr.GetEnd().x), T(tr.GetEnd().y),
                         T(tr.GetWidth()) / 2 + reach, tr.GetNetCode())
        self.g = self.hd                                 # new copper from here on is hard

    def mark(self, L, i, net):
        g = self.g[L]
        v = g[i]
        if v == 0:
            g[i] = net
        elif v != net:
            g[i] = -1

    def cells(self, x0, y0, x1, y1):
        ix0 = max(0, int((x0 - self.x0) / GRID)); ix1 = min(self.nx - 1, int((x1 - self.x0) / GRID) + 1)
        iy0 = max(0, int((y0 - self.y0) / GRID)); iy1 = min(self.ny - 1, int((y1 - self.y0) / GRID) + 1)
        return ix0, iy0, ix1, iy1

    def box(self, L, x0, y0, x1, y1, net):
        ix0, iy0, ix1, iy1 = self.cells(x0, y0, x1, y1)
        for iy in range(iy0, iy1 + 1):
            for ix in range(ix0, ix1 + 1):
                self.mark(L, iy * self.nx + ix, net)

    def disk(self, L, cx, cy, r, net):
        r += MARGIN
        ix0, iy0, ix1, iy1 = self.cells(cx - r, cy - r, cx + r, cy + r)
        for iy in range(iy0, iy1 + 1):
            dy = self.y0 + iy * GRID - cy
            for ix in range(ix0, ix1 + 1):
                dx = self.x0 + ix * GRID - cx
                if dx * dx + dy * dy < r * r:
                    self.mark(L, iy * self.nx + ix, net)

    def seg(self, L, ax, ay, bx, by, r, net):
        r += MARGIN
        ix0, iy0, ix1, iy1 = self.cells(min(ax, bx) - r, min(ay, by) - r, max(ax, bx) + r, max(ay, by) + r)
        vx, vy = bx - ax, by - ay
        ll = vx * vx + vy * vy
        for iy in range(iy0, iy1 + 1):
            py = self.y0 + iy * GRID
            for ix in range(ix0, ix1 + 1):
                px = self.x0 + ix * GRID
                s = 0.0 if ll == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / ll))
                dx, dy = px - (ax + s * vx), py - (ay + s * vy)
                if dx * dx + dy * dy < r * r:
                    self.mark(L, iy * self.nx + ix, net)

    def shape(self, p, net, layers, r):
        bb = p.GetBoundingBox()
        s = p.GetEffectiveShape(pcbnew.F_Cu)
        rr = FM(r + MARGIN)
        ix0, iy0, ix1, iy1 = self.cells(T(bb.GetX()) - r - MARGIN, T(bb.GetY()) - r - MARGIN,
                                        T(bb.GetRight()) + r + MARGIN, T(bb.GetBottom()) + r + MARGIN)
        for iy in range(iy0, iy1 + 1):
            for ix in range(ix0, ix1 + 1):
                if s.Collide(VECTOR2I(FM(self.x0 + ix * GRID), FM(self.y0 + iy * GRID)), rr):
                    for L in layers:
                        self.mark(L, iy * self.nx + ix, net)
        if p.GetDrillSize().x:                           # hole-to-hole for vias is covered by the via grid's reach
            pass

    def free(self, L, i, net):
        """no copper of another net within reach (hard or soft)"""
        v = self.hd[L][i]
        if not (v == 0 or v == net):
            return False
        v = self.sg[L][i]
        if not (v == 0 or v == net):
            return False
        v = self.kg[L][i]
        return v == 0 or v == net

    def keptblocked(self, L, i, net):
        v = self.kg[L][i]
        return not (v == 0 or v == net)

    def hardfree(self, L, i, net):
        """free, or blocked only by soft (rippable) copper"""
        v = self.hd[L][i]
        return v == 0 or v == net


def _item_cells(G, it, net):
    """(layer, cell index, anchor point mm) of the grid cells inside a copper item of the net being routed"""
    out = []
    if isinstance(it, pcbnew.PAD):
        s = it.GetEffectiveShape(pcbnew.F_Cu)
        bb = it.GetBoundingBox()
        ix0, iy0, ix1, iy1 = G.cells(T(bb.GetX()), T(bb.GetY()), T(bb.GetRight()), T(bb.GetBottom()))
        c = (T(it.GetPosition().x), T(it.GetPosition().y))
        for iy in range(iy0, iy1 + 1):
            for ix in range(ix0, ix1 + 1):
                x, y = G.x0 + ix * GRID, G.y0 + iy * GRID
                if s.Collide(VECTOR2I(FM(x), FM(y)), -FM(0.05)) or math.hypot(x - c[0], y - c[1]) < 0.2:
                    for L in (0, 1):
                        out.append((L, iy * G.nx + ix, c))
        return out
    if it.Type() == pcbnew.PCB_VIA_T:
        c = (T(it.GetPosition().x), T(it.GetPosition().y))
        ix, iy = int(round((c[0] - G.x0) / GRID)), int(round((c[1] - G.y0) / GRID))
        return [(L, iy * G.nx + ix, c) for L in (0, 1)]
    L = 0 if it.GetLayer() == pcbnew.F_Cu else 1
    ax, ay, bx, by = T(it.GetStart().x), T(it.GetStart().y), T(it.GetEnd().x), T(it.GetEnd().y)
    hw = T(it.GetWidth()) / 2
    ix0, iy0, ix1, iy1 = G.cells(min(ax, bx) - hw, min(ay, by) - hw, max(ax, bx) + hw, max(ay, by) + hw)
    vx, vy = bx - ax, by - ay
    ll = vx * vx + vy * vy
    for iy in range(iy0, iy1 + 1):
        for ix in range(ix0, ix1 + 1):
            px, py = G.x0 + ix * GRID, G.y0 + iy * GRID
            s = 0.0 if ll == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / ll))
            qx, qy = ax + s * vx, ay + s * vy
            if math.hypot(px - qx, py - qy) <= hw:
                out.append((L, iy * G.nx + ix, (qx, qy)))
    return out


def _astar(G, V, net, src, dst, bends=True, hist=None):
    """A* over (layer, cell, heading): 8 directions, a bend costs BEND per 45 degrees, a via VIA_COST; bends=False
    drops the heading (a smaller search). hist (a dict) turns rip-up on: a cell blocked only by rippable router
    copper costs RIP * (1 + times that cell was fought over before) instead of being a wall."""
    import heapq
    nx = G.nx
    rip = hist is not None
    ok = G.hardfree if rip else G.free
    vok = V.hardfree if rip else V.free
    dstset = {(L, i) for L, i, _ in dst}
    tx = [i % nx for _, i, _ in dst]
    ty = [i // nx for _, i, _ in dst]
    cx, cy = sum(tx) / len(tx), sum(ty) / len(ty)
    spread = max(max(abs(x - cx) for x in tx), max(abs(y - cy) for y in ty))

    wt = 1.3 if rip else 1.0                             # weighted A* when ripping: faster, slightly longer paths

    def h(i):
        dx, dy = abs(i % nx - cx), abs(i // nx - cy)
        d = max(dx, dy) + 0.4142 * min(dx, dy) - spread * 1.5
        return wt * d if d > 0 else 0
    steps = [(1, 0, 1.0), (1, 1, 1.4142), (0, 1, 1.0), (-1, 1, 1.4142), (-1, 0, 1.0), (-1, -1, 1.4142), (0, -1, 1.0),
             (1, -1, 1.4142)]
    best, prev, heap = {}, {}, []
    for L, i, _ in src:
        if ok(L, i, net):
            best[(L, i, 8)] = 0.0
            heapq.heappush(heap, (h(i), 0.0, L, i, 8))
    n = 0
    limit = (3000000 if bends else 6000000)
    while heap:
        f, g, L, i, hd = heapq.heappop(heap)
        if g > best.get((L, i, hd), 1e18):
            continue
        if (L, i) in dstset:
            s = (L, i, hd)
            path = [s]
            while path[-1] in prev:
                path.append(prev[path[-1]])
            return [(q[0], q[1]) for q in path[::-1]]
        n += 1
        if n > limit:
            return None
        ix, iy = i % nx, i // nx
        for k, (dx, dy, c) in enumerate(steps):
            if not bends:
                k = 8
            elif hd != 8:
                turn = min((k - hd) % 8, (hd - k) % 8)
                if turn > 2:
                    continue                             # no sharper than 90 degrees
                c += BEND * turn
            jx, jy = ix + dx, iy + dy
            if not (0 <= jx < nx and 0 <= jy < G.ny):
                continue
            j = jy * nx + jx
            if not ok(L, j, net):
                continue
            if dx and dy and not (ok(L, iy * nx + jx, net) or ok(L, jy * nx + ix, net)):
                continue
            if rip and not G.free(L, j, net):
                c += KEEP_RIP if G.keptblocked(L, j, net) else RIP * (1 + hist.get((L, j), 0))
            ng = g + c
            if ng < best.get((L, j, k), 1e18):
                best[(L, j, k)] = ng
                prev[(L, j, k)] = (L, i, hd)
                heapq.heappush(heap, (ng + h(j), ng, L, j, k))
        M = 1 - L
        if vok(0, i, net) and vok(1, i, net):
            c = VIA_COST
            if rip and not (V.free(0, i, net) and V.free(1, i, net)):
                c += (KEEP_RIP if V.keptblocked(0, i, net) or V.keptblocked(1, i, net) else
                      RIP * (2 + hist.get((0, i), 0) + hist.get((1, i), 0)))
            ng = g + c
            if ng < best.get((M, i, 8), 1e18):
                best[(M, i, 8)] = ng
                prev[(M, i, 8)] = (L, i, hd)
                heapq.heappush(heap, (ng + h(i), ng, M, i, 8))
    return None


def _segdist(a, b, c, d):
    """distance between segments ab and cd (mm)"""
    def pd(p, q, r):
        vx, vy = r[0] - q[0], r[1] - q[1]
        ll = vx * vx + vy * vy
        s = 0.0 if ll == 0 else max(0.0, min(1.0, ((p[0] - q[0]) * vx + (p[1] - q[1]) * vy) / ll))
        return math.hypot(p[0] - q[0] - s * vx, p[1] - q[1] - s * vy)

    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    if (cross(a, b, c) * cross(a, b, d) < 0) and (cross(c, d, a) * cross(c, d, b) < 0):
        return 0.0
    return min(pd(a, c, d), pd(b, c, d), pd(c, a, b), pd(d, a, b))


def _find_item(b, desc, uuid):
    m = re.match(r"PTH pad (\S+) \[[^\]]*\] of (\S+)", desc)
    if m:
        for p in b.FindFootprintByReference(m.group(2)).Pads():
            if p.GetNumber() == m.group(1):
                return p
    for tr in b.GetTracks():
        if tr.m_Uuid.AsString() == uuid:
            return tr
    raise SystemExit("finish: item not found: %s" % desc)


def _drc(brd):
    j = brd + ".drc.json"
    subprocess.run([CLI, "pcb", "drc", "--format", "json", "-o", j, brd], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    d = json.load(open(j))
    os.remove(j)
    return d


def _strip(brd, uuids, keep_locked=True, record=None):
    """remove tracks/vias by uuid at the text level (a locked one only with keep_locked=False: then its identity is
    appended to the record file); -> number removed"""
    txt = open(brd).read()
    forms = KR.top_forms(txt)
    keep, gone = [], []
    for f in forms:
        m = re.match(r"\((segment|via)\b", f)
        if m and not (keep_locked and "(locked yes)" in f) and \
                re.search(r'\(uuid "([^"]+)"\)', f).group(1) in uuids:
            gone.append(f)
        else:
            keep.append(f)
    if gone:
        open(brd, "w").write("(kicad_pcb\n\t" + "\n\t".join(keep) + "\n)\n")
        if record:
            import route_check
            with open(record, "a") as rf:
                for f in gone:
                    if "(locked yes)" in f:
                        kind = re.match(r"\((segment|via)\b", f).group(1)
                        rf.write(repr(route_check.form_key(kind, f)) + "\n")
                        print("  finish: kept v1.1 %s removed: %s" % (kind, route_check.form_key(kind, f)))
    return len(gone)


def dedupe(brd):
    """drop zero-length segments and exact duplicates (same ends, width, layer, net) the grid router's repeated
    anchor stubs can leave; a locked (kept v1.1) item is never dropped"""
    import route_check
    txt = open(brd).read()
    forms = KR.top_forms(txt)
    seen, keep, n = set(), [], 0
    for f in forms:
        m = re.match(r"\((segment|via)\b", f)
        if m and "(locked yes)" not in f:
            k = route_check.form_key(m.group(1), f)
            if k in seen or (k[0] == "segment" and k[1] == k[2]):
                n += 1
                continue
            seen.add(k)
        elif m:
            seen.add(route_check.form_key(m.group(1), f))
        keep.append(f)
    if n:
        open(brd, "w").write("(kicad_pcb\n\t" + "\n\t".join(keep) + "\n)\n")
        print("  dedupe: %d duplicate or zero-length router item(s) removed" % n)
    return n


def finish(brd, netfile=None, lock=False, rip=False, rounds=150, record=None):
    """route what Freerouting left open: every DRC unconnected pair gets a maze-routed path (0/45/90-degree tracks on
    both layers, v1.1's vias), the power nets at POWER_W where it fits, else at v1.1's width. With rip=True a path may
    go through unlocked router copper of other nets; that copper is ripped out and its net goes back on the list
    (negotiated: cells fought over get dearer each time). The kept v1.1 copper is locked and never ripped."""
    pro = brd[:-len(".kicad_pcb")] + ".kicad_pro"
    protext = open(pro).read()
    only = set(open(netfile).read().split("\n")) - {""} if netfile else None
    hist = {} if rip else None
    added_total, ripped_total, failed = [], 0, set()
    best_left, stale = 1 << 30, 0
    keep_rip = False                                     # phase 2: kept v1.1 copper rippable too (last resort)
    ripcount = {}                                        # net name -> times its copper was ripped up
    for rnd in range(rounds):
        dedupe(brd)
        while True:                                      # dangling router stubs (after a rip-up) go first
            d = _drc(brd)
            kill = {i["uuid"] for v in d["violations"] if v["type"] in ("track_dangling", "via_dangling")
                    for i in v["items"]}
            if not kill or not _strip(brd, kill, keep_locked=not keep_rip, record=record):
                break
        todo = d.get("unconnected_items", [])
        if only is not None:
            todo = [u for u in todo if re.search(r"\[([^\]]*)\]", u["items"][0]["description"]).group(1) in only]
        todo = [u for u in todo if tuple(i["description"] for i in u["items"]) not in failed]
        if not todo:
            break
        if rip:                                          # negotiated rip-up: stop when it stops converging
            if len(todo) < best_left:
                best_left, stale = len(todo), 0
            else:
                stale += 1
                if stale > 8 and not keep_rip:
                    keep_rip, stale, best_left = True, 0, len(todo)
                    print("  finish: no progress in 8 rounds (%d open) - kept v1.1 copper may now be ripped up too, "
                          "at a high cost" % len(todo))
                elif stale > 30:
                    print("  finish: no progress in 30 rounds (%d connections open) - stopped" % len(todo))
                    break
        b = pcbnew.LoadBoard(brd)
        # a net ripped up PROTECT times is protected from then on (its copper is hard): two nets that keep taking the
        # same corridor from each other would otherwise swap it for ever
        soft = {tr.m_Uuid.AsString() for tr in b.GetTracks()
                if not tr.IsLocked() and ripcount.get(tr.GetNetname(), 0) < PROTECT} if rip else set()
        keptsoft = {tr.m_Uuid.AsString() for tr in b.GetTracks() if tr.IsLocked()} if keep_rip else set()
        grids = {}
        added, ripped = [], set()
        for u in todo:
            a, c = [_find_item(b, it["description"], it["uuid"]) for it in u["items"]]
            net = a.GetNetCode()
            name = a.GetNetname()
            widths = [POWER_W, SIG_W] if name in ("GND", "VCC") else [SIG_W]
            path = None
            for w in widths:
                reach = w / 2 + CLEAR
                if reach not in grids:
                    grids[reach] = Grid(b, reach, soft=soft, kept=keptsoft)
                if "via" not in grids:
                    grids["via"] = Grid(b, VIA_D / 2 + CLEAR, holes=True, soft=soft, kept=keptsoft)
                G, V = grids[reach], grids["via"]
                src, dst = _item_cells(G, a, net), _item_cells(G, c, net)
                path = (_astar(G, V, net, src, dst, hist=hist) or
                        _astar(G, V, net, src, dst, bends=False, hist=hist))
                if path:
                    break
            if not path:
                print("  finish: no path for %s (%s -> %s)" % (name, u["items"][0]["description"],
                                                              u["items"][1]["description"]))
                failed.add(tuple(i["description"] for i in u["items"]))
                continue
            anchor_a = {(L, i): pt for L, i, pt in src}[path[0]]
            anchor_c = {(L, i): pt for L, i, pt in dst}[path[-1]]
            pts = [(path[0][0], anchor_a)]
            for L, i in path:
                pts.append((L, (G.x0 + (i % G.nx) * GRID, G.y0 + (i // G.nx) * GRID)))
            pts.append((path[-1][0], anchor_c))
            items = []                                   # ("trk", layer, p, q) / ("via", p)
            run = [pts[0]]
            for q in pts[1:] + [None]:
                if q is not None and q[0] == run[-1][0]:
                    run.append(q)
                    continue
                xy = [r[1] for r in run]                 # one layer: drop the collinear interior points
                keep = [xy[0]]
                for k in range(1, len(xy) - 1):
                    d1 = (xy[k][0] - keep[-1][0], xy[k][1] - keep[-1][1])
                    d2 = (xy[k + 1][0] - xy[k][0], xy[k + 1][1] - xy[k][1])
                    if abs(d1[0] * d2[1] - d1[1] * d2[0]) > 1e-9 or d1[0] * d2[0] + d1[1] * d2[1] < 0:
                        keep.append(xy[k])
                keep.append(xy[-1])
                for p0, p1 in zip(keep, keep[1:]):
                    if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) > 1e-6:
                        items.append(("trk", run[0][0], p0, p1))
                if q is not None:                        # layer change at the last cell of the run
                    items.append(("via", run[-1][1]))
                    run = [q]
            # rip-up: the soft copper of other nets the new path is too close to
            hit = set()
            if rip:
                for tr in b.GetTracks():
                    u_ = tr.m_Uuid.AsString()
                    if (u_ not in soft and u_ not in keptsoft) or u_ in ripped or tr.GetNetCode() == net:
                        continue
                    if tr.Type() == pcbnew.PCB_VIA_T:
                        o = ((T(tr.GetPosition().x), T(tr.GetPosition().y)),) * 2
                        ow, olayers = T(tr.GetWidth(pcbnew.F_Cu)), (0, 1)
                    else:
                        o = ((T(tr.GetStart().x), T(tr.GetStart().y)), (T(tr.GetEnd().x), T(tr.GetEnd().y)))
                        ow, olayers = T(tr.GetWidth()), (0 if tr.GetLayer() == pcbnew.F_Cu else 1,)
                    for it in items:
                        if it[0] == "via":
                            s, e, iw, il = it[1], it[1], VIA_D, (0, 1)
                        else:
                            s, e, iw, il = it[2], it[3], w, (it[1],)
                        if not set(il) & set(olayers):
                            continue
                        if _segdist(s, e, o[0], o[1]) < (iw + ow) / 2 + CLEAR + 0.01 or \
                                (it[0] == "via" and tr.Type() == pcbnew.PCB_VIA_T and
                                 math.hypot(s[0] - o[0][0], s[1] - o[0][1]) < VIA_H + HOLE_HOLE + 0.01):
                            hit.add(u_)
                            ripcount[tr.GetNetname()] = ripcount.get(tr.GetNetname(), 0) + 1
                            break
                for L, i in path:                        # history: the cells this rip-up fought over
                    if not G.free(L, i, net):
                        hist[(L, i)] = hist.get((L, i), 0) + 1
            for it in items:
                if it[0] == "via":
                    v = pcbnew.PCB_VIA(b)
                    v.SetPosition(VECTOR2I(FM(it[1][0]), FM(it[1][1])))
                    v.SetWidth(FM(VIA_D))
                    v.SetDrill(FM(VIA_H))
                    v.SetNetCode(net)
                    v.SetLocked(lock)
                    b.Add(v)
                    for gr in grids.values():
                        rr = VIA_D / 2 + gr.reach
                        gr.disk(0, it[1][0], it[1][1], rr, net)
                        gr.disk(1, it[1][0], it[1][1], rr, net)
                    for L in (0, 1):
                        grids["via"].disk(L, it[1][0], it[1][1], VIA_H + HOLE_HOLE, -1)
                else:
                    tr = pcbnew.PCB_TRACK(b)
                    tr.SetStart(VECTOR2I(FM(it[2][0]), FM(it[2][1])))
                    tr.SetEnd(VECTOR2I(FM(it[3][0]), FM(it[3][1])))
                    tr.SetLayer(pcbnew.F_Cu if it[1] == 0 else pcbnew.B_Cu)
                    tr.SetWidth(FM(w))
                    tr.SetNetCode(net)
                    tr.SetLocked(lock)
                    b.Add(tr)
                    for gr in grids.values():
                        gr.seg(it[1], it[2][0], it[2][1], it[3][0], it[3][1], w / 2 + gr.reach, net)
            added.append("%s (%d segments, %d vias, %.2f mm%s)" % (
                name, sum(1 for x in items if x[0] == "trk"), sum(1 for x in items if x[0] == "via"), w,
                ", ripped %d" % len(hit) if hit else ""))
            ripped |= hit                                # stays an obstacle in the grids until the round ends
        _save(b, brd)
        open(pro, "w").write(protext)
        if ripped:
            ripped_total += _strip(brd, ripped, keep_locked=False, record=record)
        if not added:
            break
        added_total += added
        print("  finish round %d: routed %s" % (rnd + 1, ", ".join(added)))
    dedupe(brd)
    d = _drc(brd)
    left = [u for u in d.get("unconnected_items", []) if only is None or
            re.search(r"\[([^\]]*)\]", u["items"][0]["description"]).group(1) in only]
    left = len(left)
    print("finish: %d connection(s) routed by the grid router, %d router item(s) ripped up and re-routed; "
          "%d unconnected left%s" % (len(added_total), ripped_total, left, " (of these nets)" if only else ""))
    return left


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "prep":
        prep(sys.argv[2], sys.argv[3])
    elif cmd == "pin1":                                  # apply the J2 pin-1 mark to a finished board
        pro = sys.argv[2][:-len(".kicad_pcb")] + ".kicad_pro"
        protext = open(pro).read()
        b = pcbnew.LoadBoard(sys.argv[2])
        pin1_mark(b)
        _save(b, sys.argv[2])
        open(pro, "w").write(protext)
    elif cmd == "first_nets":
        first_nets(sys.argv[2], sys.argv[3])
    elif cmd == "dsn_split":
        dsn_split(sys.argv[2], sys.argv[3])
    elif cmd == "finish":
        args = [a for a in sys.argv[3:] if not a.startswith("--")]
        left = finish(sys.argv[2], args[0] if args else None, lock="--lock" in sys.argv, rip="--rip" in sys.argv,
                      record=os.path.join(os.path.dirname(os.path.abspath(sys.argv[2])), "reports",
                                          "route-kept-removed.txt"))
        sys.stdout.flush()
        os._exit(0 if left == 0 or args else 1)
    elif cmd == "import":
        import_ses(sys.argv[2], sys.argv[3], lock_all="--lock" in sys.argv)
    else:
        sys.exit("unknown command " + cmd)
    sys.stdout.flush()
    os._exit(0)
