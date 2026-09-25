#!/usr/bin/env python3
"""finish_v2.py - the board finished from top-edge option B of the YACC1 memory card v2.0:
options-top-edge-J2/memory-v2.0.kicad_pcb (Ken's pick, 2026-09-24, of the re-layout with J2 at the top edge,
relayout_placements.py OPTIONS["b"]; superseded the same day by the standoff decision - gen_standoff.py - and kept, with
its fab files, as a record: build.sh FROM=trial / ROUTE=1 remakes it there).

Run with KiCad's bundled Python (pcbnew); build.sh does:

  finish_v2.py project                          -> memory-v2.0.kicad_pro / .kicad_dru get the re-layout rules (0.25 mm
                                                   tracks, 0.2 mm clearance, 0.8/0.4 vias, class Power = planes only),
                                                   so the schematic and the final board share one project
  finish_v2.py make <routed.kicad_pcb> <out>    -> the final board from a routed option-B board (the committed trial
                                                   route or a new Freerouting run, gen_relayout.py ses): every via a
                                                   THROUGH via (the session import marks them "buried"), via clean-up
                                                   (a run of track between a via and a pad flipped onto the other
                                                   signal layer when it fits there, the via removed), collinear
                                                   segments merged, the adapter strip + keep-low zone moved to F.Fab,
                                                   J3 pin labels, silkscreen tidy (tidy() below), title block, the
                                                   removed caps C20-C23 taken off (drop_removed(), after the tidy, so
                                                   no other text moves because of them), planes refilled
  finish_v2.py silk <pcb>                       -> the silkscreen check alone (reference texts and board texts clear of
                                                   pads, holes, vias, other silk and the edge; upright)
  finish_v2.py verify <pcb> <drc.json>          -> the final gates: 0 unrouted, 0 DRC copper violations, every via a
                                                   through via, every GND/VCC pad on its plane, each plane one solid
                                                   piece, no silk collision on a text; the routing numbers
  finish_v2.py fab <pcb>                        -> gerbers/ (4 copper layers) + drill + <name>-gerbers.zip, top and
                                                   bottom renders, placement PDF (tools/kicad/kicad_route.py placement),
                                                   <name>-jlcpcb-order.txt (the built card's order parameters)

Nothing here moves a part: the placement is option B's. The only positions that change are silkscreen texts.
The one part change: C20-C23 (mem_v2_netlist.REMOVED, Ken 2026-09-24) are on option B's board and its trial route (both
made before the removal) and are not on the final board.
"""
import os, sys, re, json, math, glob, shutil, zipfile, subprocess, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_mem_v2 as GM                                     # noqa: E402
import gen_relayout as GR                                   # noqa: E402
import relayout_placements as RP                            # noqa: E402
import mem_v2_netlist as NL                                 # noqa: E402

PROJ = GM.PROJ
CLI = GM.CLI
OPT = "b"                     # Ken's pick, 2026-09-24
TITLE = "YACC1 memory card v2.0"
DATE = "2026-09-24"

# silkscreen texts that belong to a part: the tidy keeps them nearer that part than any other
OWNER = {"ROM": "U$1", "RAM": "U$1", "0X8000": "U$1", "0XF000": "U$1", "-BUS-EN": "JP1", "Gnd": "JP1",
         "PWR": "PWR0", "ACT": "LED1", "PIN20 +5V": "JP2", "CF: P8/P9": "J2", "+5V": "J3", "G": "J3", "nc": "J3"}
J3_PINS = ["+5V", "G", "G", "nc"]          # J3 pin 1..4 (the CF card v1.0's adapter power header)
# placement nudges after routing, for the silkscreen only (listed in the README): ref -> (dx, dy) mm
NUDGE = {"C30": (-2.54, 0.0)}               # frees the row left of J3 pin 1 for its "+5V" label (C30's pads are plane-only)
# board texts placed explicitly: text -> (x, y, angle, justify)
TEXT_AT = {"Gnd": (29.21, 14.78, 0, "l")}   # the built card has "Gnd" above JP1 pin 3, running into "-BUS-EN": now
                                            # beside pin 3


# ---------------------------------------------------------------------------------------------------------------------
def project():
    """the v2.0 project (schematic + final board) with the re-layout rules; gen_mem_v2.py sch writes it with the built
    card's rules first (those stay with the keep-copper record, build.sh keeps a copy for it)"""
    GR.write_project(OPT, PROJ)             # the same rules as memory-v2.0-relayout-b.kicad_pro
    print("project: %s.kicad_pro / .kicad_dru = the re-layout rules" % PROJ)


# ---------------------------------------------------------------------------------------------------------------------
# geometry
def seg_dist(a, b, c, d):
    """distance between segments ab and cd (points as (x, y))"""
    def pd(p, q, r):
        qx, qy = r[0] - q[0], r[1] - q[1]
        L = qx * qx + qy * qy
        t = 0 if L == 0 else max(0, min(1, ((p[0] - q[0]) * qx + (p[1] - q[1]) * qy) / L))
        return math.hypot(p[0] - q[0] - t * qx, p[1] - q[1] - t * qy)

    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    d1, d2, d3, d4 = cross(c, d, a), cross(c, d, b), cross(a, b, c), cross(a, b, d)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 and d2 and d3 and d4:
        return 0.0
    return min(pd(a, c, d), pd(b, c, d), pd(c, a, b), pd(d, a, b))


def pad_capsules(b):
    """every pad as a capsule (segment + radius, mm) on the copper layers it has: circles exact, ovals exact, anything
    else by its circumscribed circle (conservative)"""
    import pcbnew
    T = pcbnew.ToMM
    out = []
    for f in b.GetFootprints():
        for p in f.Pads():
            x, y = T(p.GetPosition().x), T(p.GetPosition().y)
            sx, sy = T(p.GetSize(pcbnew.F_Cu).x), T(p.GetSize(pcbnew.F_Cu).y)
            sh = p.GetShape(pcbnew.F_Cu)
            a = math.radians(-p.GetOrientation().AsDegrees())
            if sh in (pcbnew.PAD_SHAPE_CIRCLE, pcbnew.PAD_SHAPE_OVAL):
                r = min(sx, sy) / 2
                h = (max(sx, sy) - min(sx, sy)) / 2
                if sx >= sy:
                    dx, dy = h * math.cos(a), h * math.sin(a)
                else:
                    dx, dy = -h * math.sin(a), h * math.cos(a)
                out.append(((x - dx, y - dy), (x + dx, y + dy), r, p.GetNetname(), "%s.%s" % (f.GetReference(), p.GetNumber())))
            else:
                bb = p.GetBoundingBox()
                r = math.hypot(T(bb.GetWidth()) / 2, T(bb.GetHeight()) / 2)
                out.append(((x, y), (x, y), r, p.GetNetname(), "%s.%s" % (f.GetReference(), p.GetNumber())))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# copper clean-up (text level: pcbnew only reads the pads)
def _num(s):
    return float(s)


def parse_copper(t):
    forms = GR.gen_cf.top_forms(t)
    segs, vias, other = [], [], []
    for f in forms:
        if f.startswith("(segment"):
            m = re.search(r"\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)\s*\(width ([-\d.]+)\)\s*"
                          r"\(layer \"([^\"]+)\"\)\s*\(net \"((?:[^\"\\]|\\.)*)\"\)\s*\(uuid \"([^\"]+)\"\)", f)
            if not m:
                raise SystemExit("cleanup: cannot parse %s" % f[:120])
            segs.append(dict(a=(_num(m.group(1)), _num(m.group(2))), b=(_num(m.group(3)), _num(m.group(4))),
                             w=_num(m.group(5)), layer=m.group(6), net=m.group(7), uuid=m.group(8), locked="(locked" in f))
        elif f.startswith("(via"):
            m = re.search(r"\(at ([-\d.]+) ([-\d.]+)\)\s*\(size ([-\d.]+)\)\s*\(drill ([-\d.]+)\)\s*\(layers [^)]*\)\s*"
                          r"\(net \"((?:[^\"\\]|\\.)*)\"\)\s*\(uuid \"([^\"]+)\"\)", f)
            if not m:
                raise SystemExit("cleanup: cannot parse %s" % f[:120])
            vias.append(dict(at=(_num(m.group(1)), _num(m.group(2))), size=_num(m.group(3)), drill=_num(m.group(4)),
                             net=m.group(5), uuid=m.group(6)))
        else:
            other.append(f)
    return other, segs, vias


def seg_form(s):
    return ('(segment\n\t\t(start %s %s)\n\t\t(end %s %s)\n\t\t(width %s)\n\t\t(layer "%s")\n\t\t(net "%s")\n\t\t'
            '(uuid "%s")\n\t)' % (_f(s["a"][0]), _f(s["a"][1]), _f(s["b"][0]), _f(s["b"][1]), _f(s["w"]), s["layer"],
                                  s["net"], s["uuid"]))


def via_form(v):
    return ('(via\n\t\t(at %s %s)\n\t\t(size %s)\n\t\t(drill %s)\n\t\t(layers "F.Cu" "B.Cu")\n\t\t(net "%s")\n\t\t'
            '(uuid "%s")\n\t)' % (_f(v["at"][0]), _f(v["at"][1]), _f(v["size"]), _f(v["drill"]), v["net"], v["uuid"]))


def _f(v):
    s = ("%.6f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _key(p):
    return (round(p[0], 4), round(p[1], 4))


def cleanup(pcb, clearance=0.2, edge=0.5):
    """-> (vias removed, segments before, segments after). Via clean-up: for each via, a run of track on one side
    (segments joined end to end with nothing else at the joints) that ends on a through-hole pad of its own net is
    moved onto the via's other signal layer when every segment of it keeps the clearance there (to the other nets'
    tracks, vias and pads) and the edge distance; a via left with copper on one layer only is removed. Then segments
    of one net, layer and width meeting end to end in a straight line with nothing else at the joint are merged."""
    import pcbnew
    b = pcbnew.LoadBoard(pcb)
    pads = pad_capsules(b)
    E = b.GetBoardEdgesBoundingBox()
    T = pcbnew.ToMM
    ex0, ey0, ex1, ey1 = T(E.GetX()), T(E.GetY()), T(E.GetRight()), T(E.GetBottom())
    t = open(pcb).read()
    other, segs, vias = parse_copper(t)
    nseg0 = len(segs)
    padpts = collections.defaultdict(list)
    for (a, c, r, net, name) in pads:
        if a == c:
            padpts[_key(a)].append(name)

    def on_pad(q, net):
        return any(pn == net and seg_dist(q, q, a, c) <= r - 0.01 for (a, c, r, pn, name) in pads)

    def ends_at(layer=None):
        m = collections.defaultdict(list)
        for i, s in enumerate(segs):
            if s is None or (layer and s["layer"] != layer):
                continue
            m[_key(s["a"])].append(i)
            m[_key(s["b"])].append(i)
        return m

    def fits(run, layer, net):
        for i in run:
            s = segs[i]
            hw = s["w"] / 2
            # something of the same net joining the run in the middle of a segment (a T): leave the run alone
            for j, o in enumerate(segs):
                if o is None or j in run or o["net"] != net:
                    continue
                for p in (o["a"], o["b"]):
                    if _key(p) not in (_key(s["a"]), _key(s["b"])) and seg_dist(p, p, s["a"], s["b"]) < 0.01:
                        return "a T-junction on the run"
            for p in (s["a"], s["b"]):
                if min(p[0] - ex0, p[1] - ey0, ex1 - p[0], ey1 - p[1]) < edge + hw:
                    return "board edge"
            sx0, sx1 = min(s["a"][0], s["b"][0]) - 2, max(s["a"][0], s["b"][0]) + 2
            sy0, sy1 = min(s["a"][1], s["b"][1]) - 2, max(s["a"][1], s["b"][1]) + 2
            for j, o in enumerate(segs):
                if o is None or j in run or o["layer"] != layer or o["net"] == net:
                    continue
                if max(o["a"][0], o["b"][0]) < sx0 or min(o["a"][0], o["b"][0]) > sx1 or \
                   max(o["a"][1], o["b"][1]) < sy0 or min(o["a"][1], o["b"][1]) > sy1:
                    continue
                if seg_dist(s["a"], s["b"], o["a"], o["b"]) < clearance + hw + o["w"] / 2 + 0.005:
                    return "a track of another net there"
            for v in vias:
                if v is None or v["net"] == net:
                    continue
                if seg_dist(s["a"], s["b"], v["at"], v["at"]) < clearance + hw + v["size"] / 2 + 0.005:
                    return "a via of another net there"
            for (a, c, r, pn, name) in pads:
                if pn == net:
                    continue
                if seg_dist(s["a"], s["b"], a, c) < clearance + hw + r + 0.005:
                    return "a pad of another net there"
        return None

    removed = []
    why = collections.defaultdict(set)
    changed = True
    while changed:
        changed = False
        for vi, v in enumerate(vias):
            if v is None:
                continue
            at = _key(v["at"])
            for layer in ("B.Cu", "F.Cu"):
                em = ends_at()
                here = [i for i in em[at] if segs[i]["layer"] == layer]
                there = [i for i in em[at] if segs[i]["layer"] != layer]
                if len(here) != 1 or not there:
                    continue
                # follow the run from the via
                run, p, i = [], at, here[0]
                ok = False
                while True:
                    run.append(i)
                    s = segs[i]
                    q = _key(s["b"]) if _key(s["a"]) == p else _key(s["a"])
                    others = [j for j in em[q] if j != i]
                    viahere = any(w is not None and _key(w["at"]) == q for w in vias)
                    if on_pad(q, v["net"]) or viahere:
                        ok = True                     # ends on a through-hole pad of its net (the pad is on both
                        break                         # layers) or on another via
                    if len(others) == 1 and not padpts.get(q) and not viahere and segs[others[0]]["layer"] == layer:
                        p, i = q, others[0]
                        continue
                    break
                if not ok:
                    why[v["uuid"]].add("the run does not end on a pad or via")
                    continue
                other_layer = "F.Cu" if layer == "B.Cu" else "B.Cu"
                w = fits(run, other_layer, v["net"])
                if w:
                    why[v["uuid"]].add(w)
                    continue
                for i in run:
                    segs[i]["layer"] = other_layer
                em = ends_at()
                if len({segs[i]["layer"] for i in em[at]}) <= 1:
                    removed.append((v["net"], v["at"]))
                    vias[vi] = None
                changed = True
                break
    # merge collinear segments
    merged = True
    while merged:
        merged = False
        em = ends_at()
        viapts = {_key(v["at"]) for v in vias if v is not None}
        for q, ids in em.items():
            if len(ids) != 2 or q in viapts or padpts.get(q):
                continue
            s, o = segs[ids[0]], segs[ids[1]]
            if s is None or o is None or s["layer"] != o["layer"] or s["net"] != o["net"] or s["w"] != o["w"]:
                continue
            pa = s["a"] if _key(s["b"]) == q else s["b"]
            pb = o["a"] if _key(o["b"]) == q else o["b"]
            ux, uy = q[0] - pa[0], q[1] - pa[1]
            wx, wy = pb[0] - q[0], pb[1] - q[1]
            lu, lw = math.hypot(ux, uy), math.hypot(wx, wy)
            if lu == 0 or lw == 0 or abs(ux * wy - uy * wx) / (lu * lw) > 1e-4 or ux * wx + uy * wy <= 0:
                continue
            s["a"], s["b"] = pa, pb
            segs[ids[1]] = None
            merged = True
            break
    # drop zero-length segments
    segs = [s for s in segs if s is not None and _key(s["a"]) != _key(s["b"])]
    live_vias = [v for v in vias if v is not None]
    text = "(kicad_pcb\n\t" + "\n\t".join(other + [seg_form(s) for s in segs] + [via_form(v) for v in live_vias]) + "\n)\n"
    open(pcb, "w").write(text)
    kept = collections.Counter(w for v in live_vias for w in why.get(v["uuid"], {"branches at the via"}))
    print("cleanup: %d via(s) removed %s; %d kept (why, per side tried: %s); %d -> %d track segments (collinear "
          "merged); every via a through via" % (len(removed), ["%s @ %.2f,%.2f" % (n, p[0], p[1]) for n, p in removed],
                                                 len(live_vias), dict(kept), nseg0, len(segs)))
    return len(removed), nseg0, len(segs)


# ---------------------------------------------------------------------------------------------------------------------
# silkscreen
def _rect_seg(R, a, c, m):
    """does segment ac come within m of rectangle R = (x0, y0, x1, y1)?"""
    x0, y0, x1, y1 = R[0] - m, R[1] - m, R[2] + m, R[3] + m
    for p in (a, c):
        if x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
            return True
    edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    return any(seg_dist(a, c, e0, e1) == 0 for e0, e1 in edges)


def silk_obstacles(b):
    """F.SilkS geometry as (kind, data, owner-id): 'seg' (a, c, halfwidth) for lines/rects/circles/arcs/polygons,
    'box' for texts; plus pads/vias as 'cu' capsules"""
    import pcbnew
    T = pcbnew.ToMM
    P = lambda v: (T(v.x), T(v.y))
    out = []

    def shape(s, oid):
        w = T(s.GetWidth()) / 2
        st = s.GetShape()
        if st == pcbnew.SHAPE_T_SEGMENT:
            out.append(("seg", (P(s.GetStart()), P(s.GetEnd()), w), oid))
        elif st == pcbnew.SHAPE_T_RECTANGLE:
            x0, y0 = P(s.GetStart())
            x1, y1 = P(s.GetEnd())
            for a, c in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
                out.append(("seg", (a, c, w), oid))
        elif st in (pcbnew.SHAPE_T_CIRCLE, pcbnew.SHAPE_T_ARC):
            c = P(s.GetCenter())
            r = T(s.GetRadius())
            if st == pcbnew.SHAPE_T_CIRCLE:
                a0, sweep = 0.0, 2 * math.pi
            else:                               # start -> mid -> end, whichever way round that is
                sx, sy = P(s.GetStart())
                mx, my = P(s.GetArcMid())
                ex, ey = P(s.GetEnd())
                a0 = math.atan2(sy - c[1], sx - c[0])
                am = (math.atan2(my - c[1], mx - c[0]) - a0) % (2 * math.pi)
                ae = (math.atan2(ey - c[1], ex - c[0]) - a0) % (2 * math.pi)
                sweep = ae if am < ae else ae - 2 * math.pi
            n = 24
            pts = [(c[0] + r * math.cos(a0 + sweep * k / n), c[1] + r * math.sin(a0 + sweep * k / n)) for k in range(n + 1)]
            for a, d in zip(pts, pts[1:]):
                out.append(("seg", (a, d, w), oid))
        elif st == pcbnew.SHAPE_T_POLY:
            ps = s.GetPolyShape()
            for oi in range(ps.OutlineCount()):
                ol = ps.Outline(oi)
                pts = [P(ol.CPoint(k)) for k in range(ol.PointCount())]
                for a, d in zip(pts, pts[1:] + pts[:1]):
                    out.append(("seg", (a, d, w), oid))
        else:
            bb = s.GetBoundingBox()
            out.append(("box", (T(bb.GetX()), T(bb.GetY()), T(bb.GetRight()), T(bb.GetBottom())), oid))

    for f in b.GetFootprints():
        ref = f.GetReference()
        for g in f.GraphicalItems():
            if g.GetLayer() != pcbnew.F_SilkS:
                continue
            if g.GetClass() == "PCB_SHAPE":
                shape(g, ref)
            elif g.GetClass() in ("PCB_TEXT",) and g.IsVisible():
                out.append(("box", text_box(g), "text:%s:%s" % (ref, g.GetText())))
        fld = f.Reference()
        if fld.IsVisible() and fld.GetLayer() == pcbnew.F_SilkS:
            out.append(("box", text_box(fld), "ref:" + ref))
        for p in f.Pads():
            bb = p.GetBoundingBox()
            out.append(("cu", (T(bb.GetX()), T(bb.GetY()), T(bb.GetRight()), T(bb.GetBottom())), ref))
    for d in b.GetDrawings():
        if d.GetLayer() != pcbnew.F_SilkS:
            continue
        if d.GetClass() == "PCB_TEXT":
            out.append(("box", text_box(d), gr_id(d)))
        elif d.GetClass() == "PCB_SHAPE":
            shape(d, "gr-shape")
    for tr in b.GetTracks():
        if tr.Type() == pcbnew.PCB_VIA_T:
            x, y, r = T(tr.GetPosition().x), T(tr.GetPosition().y), T(tr.GetWidth(pcbnew.F_Cu)) / 2
            out.append(("cu", (x - r, y - r, x + r, y + r), "via"))
    return out


def gr_id(d):
    import pcbnew
    return "gr:%s@%.3f,%.3f" % (d.GetText(), pcbnew.ToMM(d.GetPosition().x), pcbnew.ToMM(d.GetPosition().y))


def text_box(t):
    import pcbnew
    T = pcbnew.ToMM
    bb = t.GetBoundingBox()
    return (T(bb.GetX()), T(bb.GetY()), T(bb.GetRight()), T(bb.GetBottom()))


SILK_CLEAR = 0.05         # text to other silk
CU_CLEAR = 0.1            # text to a pad / via (mask opening + margin)
EDGE_CLEAR = 0.5          # text to the board edge


def collisions(box, obstacles, me, edge):
    hits = []
    x0, y0, x1, y1 = edge
    if box[0] < x0 + EDGE_CLEAR or box[1] < y0 + EDGE_CLEAR or box[2] > x1 - EDGE_CLEAR or box[3] > y1 - EDGE_CLEAR:
        hits.append("edge")
    for kind, d, oid in obstacles:
        if oid == me:
            continue
        if kind == "seg":
            a, c, w = d
            if min(a[0], c[0]) - 2 > box[2] or max(a[0], c[0]) + 2 < box[0] or \
               min(a[1], c[1]) - 2 > box[3] or max(a[1], c[1]) + 2 < box[1]:
                continue
            if _rect_seg(box, a, c, SILK_CLEAR + w):
                hits.append(oid)
        else:
            m = CU_CLEAR if kind == "cu" else SILK_CLEAR
            if GM.overlap(box, (d[0] - m, d[1] - m, d[2] + m, d[3] + m), m=0.0):
                hits.append(("pad of " if kind == "cu" else "") + oid)
    return hits


def tidy(b, log=None):
    """move each silkscreen text that touches a pad, a via, other silk or the edge (and turn each upside-down one
    upright) to the nearest free spot beside its part: a spiral of candidate positions within 8 mm, the text's own
    angle first, then 0 / 90 degrees; the spot must be nearer its own part than any other part (OWNER for board
    texts). Returns the texts moved and the ones left colliding."""
    import pcbnew
    T, FM = pcbnew.ToMM, pcbnew.FromMM
    E = b.GetBoardEdgesBoundingBox()
    edge = (T(E.GetX()), T(E.GetY()), T(E.GetRight()), T(E.GetBottom()))
    bodies = GM.body_boxes(b)
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    items = []
    for f in b.GetFootprints():
        fld = f.Reference()
        if fld.IsVisible() and fld.GetLayer() == pcbnew.F_SilkS:
            items.append((fld, "ref:" + f.GetReference(), f.GetReference()))
    for d in b.GetDrawings():
        if d.GetClass() == "PCB_TEXT" and d.GetLayer() == pcbnew.F_SilkS:
            items.append((d, None, OWNER.get(d.GetText())))
    moved, stuck = [], []

    def bdist(box, bb):
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        dx = max(bb[0] - cx, 0, cx - bb[2])
        dy = max(bb[1] - cy, 0, cy - bb[3])
        return math.hypot(dx, dy)

    for it, me, owner in items:
        if me is None:
            me = gr_id(it)
        x0, y0 = T(it.GetPosition().x), T(it.GetPosition().y)
        R = 14.0
        obst = [o for o in silk_obstacles(b) if _near(o, x0, y0, R)]
        ang = it.GetTextAngle().AsDegrees() % 360
        draw = it.GetDrawRotation().AsDegrees() % 360
        upside = 90 < draw <= 270
        hits = collisions(text_box(it), obst, me, edge)
        if not hits and not upside:
            continue
        best = None
        angles = [draw if not upside else (draw + 180) % 360] + [a for a in (0, 90) if a != draw]
        cands = []
        step = 0.254
        for i in range(-32, 33):
            for j in range(-32, 33):
                cands.append((math.hypot(i, j) * step, x0 + i * step, y0 + j * step))
        cands.sort()
        for ai, a in enumerate(angles):
            for dist, x, y in cands:
                if best and dist + ai * 1.5 >= best[0]:
                    break
                it.SetTextAngleDegrees((a - (draw - ang)) % 360)
                it.SetPosition(pcbnew.VECTOR2I(FM(x), FM(y)))
                box = text_box(it)
                if collisions(box, obst, me, edge):
                    continue
                if owner and owner in bodies:
                    mine = bdist(box, bodies[owner])
                    if mine > 0.8 and any(bdist(box, bb) < mine - 0.01 for r, bb in bodies.items() if r != owner):
                        continue
                best = (dist + ai * 1.5, x, y, a)
                break
        if best:
            it.SetTextAngleDegrees((best[3] - (draw - ang)) % 360)
            it.SetPosition(pcbnew.VECTOR2I(FM(best[1]), FM(best[2])))
            moved.append("%s %.1f mm%s" % (me or it.GetText(), best[0] - angles.index(best[3]) * 1.5,
                                           " (turned upright)" if upside else ""))
        else:
            it.SetTextAngleDegrees(ang)
            it.SetPosition(pcbnew.VECTOR2I(FM(x0), FM(y0)))
            stuck.append("%s: %s" % (me or it.GetText(), sorted(set(hits))))
    return moved, stuck


def _near(o, x, y, R):
    kind, d, oid = o
    if kind == "seg":
        a, c, w = d
        return seg_dist(a, c, (x, y), (x, y)) < R
    return d[0] - R < x < d[2] + R and d[1] - R < y < d[3] + R


def silk_report(pcb):
    import pcbnew
    b = pcbnew.LoadBoard(pcb)
    T = pcbnew.ToMM
    E = b.GetBoardEdgesBoundingBox()
    edge = (T(E.GetX()), T(E.GetY()), T(E.GetRight()), T(E.GetBottom()))
    obst = silk_obstacles(b)
    bad = []
    for kind, d, oid in obst:
        if kind != "box" or not (oid.startswith("ref:") or oid.startswith("gr:")):
            continue
        hits = collisions(d, obst, oid, edge)
        if hits:
            bad.append("%s: %s" % (oid.split(":")[1], sorted(set(hits))))
    ups = []
    for f in b.GetFootprints():
        fld = f.Reference()
        if fld.IsVisible() and 90 < fld.GetDrawRotation().AsDegrees() % 360 <= 270:
            ups.append(f.GetReference())
    for d in b.GetDrawings():
        if d.GetClass() == "PCB_TEXT" and d.GetLayer() == pcbnew.F_SilkS and 90 < d.GetDrawRotation().AsDegrees() % 360 <= 270:
            ups.append(d.GetText())
    print("silkscreen texts: %d touching a pad/via/other silk/the edge %s; %d upside down %s"
          % (len(bad), bad[:12], len(ups), ups))
    return not bad and not ups


# ---------------------------------------------------------------------------------------------------------------------
def make(routed, out):
    import pcbnew
    shutil.copy(routed, out)
    t = open(out).read()
    nb = len(re.findall(r"^\t\(via (?:buried|blind|micro)", t, re.M))
    t = re.sub(r"^\t\(via (?:buried|blind|micro)\b", "\t(via", t, flags=re.M)
    # title block (the board has none)
    t = re.sub(r"\t\(title_block[\s\S]*?\n\t\)\n", "", t)
    tb = ('\t(title_block\n\t\t(title "%s")\n\t\t(date "%s")\n\t\t(rev "2.0")\n\t\t(company "YACC1")\n\t\t'
          '(comment 1 "the built memory card v1.3 + the CF interface on P8/P9; re-laid out, option B")\n\t\t'
          '(comment 2 "4 layers: F.Cu signals / In1.Cu GND plane / In2.Cu VCC plane / B.Cu signals; 1.6 mm")\n\t)\n'
          % (TITLE, DATE))
    t = re.sub(r'(\t\(paper "[^"]*"\)\n)', lambda m: m.group(1) + tb, t, count=1)
    # the adapter drawings: User.Drawings -> F.Fab (strip solid, keep-low zone dashed); the option texts and the one
    # J3 line ("+5V G G nc", replaced by one label per pin below) go. Text level: KiCad 10's SWIG board containers
    # stop iterating after a Remove()
    forms = GR.gen_cf.top_forms(t)
    head = t[:t.index(forms[0])]
    keep = []
    for f in forms:
        if f.startswith("(gr_text") and ('(layer "Dwgs.User")' in f or f.startswith('(gr_text "+5V G G nc"')):
            continue
        if f.startswith("(gr_") and '(layer "Dwgs.User")' in f:
            f = f.replace('(layer "Dwgs.User")', '(layer "F.Fab")')
        keep.append(f)
    t = head + "\n\t".join(keep) + "\n)\n"
    open(out, "w").write(t)
    print("make: %s from %s; %d via(s) were imported as buried/blind -> through" % (os.path.basename(out),
                                                                                   os.path.basename(routed), nb))
    cleanup(out)
    b = pcbnew.LoadBoard(out)
    FM, T = pcbnew.FromMM, pcbnew.ToMM
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    j2 = fps["J2"]
    xs = sorted(T(p.GetPosition().x) for p in j2.Pads())
    ys = sorted(T(p.GetPosition().y) for p in j2.Pads())

    def text(s, x, y, size, angle=0, layer=pcbnew.F_SilkS, just=pcbnew.GR_TEXT_H_ALIGN_LEFT):
        tx = pcbnew.PCB_TEXT(b)
        tx.SetText(s)
        tx.SetLayer(layer)
        tx.SetTextSize(pcbnew.VECTOR2I(FM(size), FM(size)))
        tx.SetTextThickness(FM(max(0.15, size * 0.15)))
        tx.SetHorizJustify(just)
        tx.SetTextAngleDegrees(angle)
        tx.SetPosition(pcbnew.VECTOR2I(FM(x), FM(y)))
        b.Add(tx)
    c = (xs[0] + xs[-1]) / 2
    text("TAODAN CF-IDE40 (70 mm, stands up on J2); dashed: keep low (< ~8 mm)", c - 5.5, (ys[0] + ys[-1]) / 2, 1.0,
         90, pcbnew.F_Fab, pcbnew.GR_TEXT_H_ALIGN_CENTER)
    for ref, (dx, dy) in NUDGE.items():
        f = fps[ref]
        f.SetPosition(pcbnew.VECTOR2I(f.GetPosition().x + FM(dx), f.GetPosition().y + FM(dy)))
    JUST = {"l": pcbnew.GR_TEXT_H_ALIGN_LEFT, "c": pcbnew.GR_TEXT_H_ALIGN_CENTER, "r": pcbnew.GR_TEXT_H_ALIGN_RIGHT}
    for d in b.GetDrawings():
        if d.GetClass() == "PCB_TEXT" and d.GetLayer() == pcbnew.F_SilkS and d.GetText() in TEXT_AT:
            x, y, a, j = TEXT_AT[d.GetText()]
            d.SetPosition(pcbnew.VECTOR2I(FM(x), FM(y)))
            d.SetTextAngleDegrees(a)
            d.SetHorizJustify(JUST[j])
            d.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    # every IC's reference in the middle of its body, horizontal, just above the centre line (the tidy moves it only
    # if something is there); its value (F.Fab, the placement PDF) just below
    for ref, f in fps.items():
        if not ref.startswith("IC"):
            continue
        xs = [T(p.GetPosition().x) for p in f.Pads()]
        ys = [T(p.GetPosition().y) for p in f.Pads()]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        for fld, dy in ((f.Reference(), -0.8), (f.Value(), 0.9)):
            fld.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
            fld.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
            fld.SetPosition(pcbnew.VECTOR2I(FM(cx), FM(cy + dy)))
            for a in (0, 90, 180, 270):
                fld.SetTextAngleDegrees(a)
                if abs(fld.GetDrawRotation().AsDegrees() % 360) < 0.1:
                    break
    # J3: one label per pin
    for p in sorted(fps["J3"].Pads(), key=lambda p: int(p.GetNumber())):
        x, y = T(p.GetPosition().x), T(p.GetPosition().y)
        text(J3_PINS[int(p.GetNumber()) - 1], x - 1.15, y, 0.8, 0, just=pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    # the built card's U$1 reference is thinner than the DRC's minimum text thickness: 0.15 mm like the rest
    for f in b.GetFootprints():
        fld = f.Reference()
        if fld.IsVisible() and fld.GetLayer() == pcbnew.F_SilkS and T(fld.GetTextThickness()) < 0.15:
            fld.SetTextThickness(FM(0.15))
    moved, stuck = tidy(b)
    pcbnew.SaveBoard(out, b)
    print("silk tidy: %d text(s) moved %s" % (len(moved), moved))
    if stuck:
        print("silk tidy: %d text(s) with no free spot: %s" % (len(stuck), stuck))
    drop_removed(out)
    GM.refill(out)


def drop_removed(pcb):
    """take the removed parts (mem_v2_netlist.REMOVED: C20-C23) off a board, at the text level (KiCad 10's SWIG
    containers misbehave after Remove()). Their pads are plane-only (GND / VCC through thermal reliefs); a track or via
    touching one of their pads would be copper that served only them: none may exist (power is never routed), else
    stop. Their silk / fab graphics and reference texts are part of the footprint and go with it; nothing else changes
    (the plane refill after this redraws the reliefs)."""
    import pcbnew
    b = pcbnew.LoadBoard(pcb)
    pads = [(f.GetReference(), p) for f in b.GetFootprints() if f.GetReference() in NL.REMOVED for p in f.Pads()]
    hit = []
    for tr in b.GetTracks():
        pts = [tr.GetPosition()] if tr.Type() == pcbnew.PCB_VIA_T else [tr.GetStart(), tr.GetEnd()]
        for ref, p in pads:
            if any(p.HitTest(q) for q in pts):
                hit.append("%s.%s: %s on %s" % (ref, p.GetNumber(), tr.GetClass(), tr.GetNetname()))
    if hit:
        raise SystemExit("drop_removed: copper on the removed parts' pads: %s" % hit)
    nets = sorted({"%s.%s %s" % (r, p.GetNumber(), p.GetNetname()) for r, p in pads})
    t = open(pcb).read()
    forms = GR.gen_cf.top_forms(t)
    head = t[:t.index(forms[0])]
    keep, gone = [], []
    for f in forms:
        m = re.match(r'\(footprint "[^"]*"[\s\S]*?\(property "Reference" "([^"]+)"', f)
        if m and m.group(1) in NL.REMOVED:
            gone.append(m.group(1))
            continue
        keep.append(f)
    open(pcb, "w").write(head + "\n\t".join(keep) + "\n)\n")
    print("removed parts: %s taken off (pads %s; no track or via on them)" % (sorted(gone), nets))
    return gone


# ---------------------------------------------------------------------------------------------------------------------
def planes(pcb):
    """-> [(net, layer, filled pieces, filled area mm2, board area mm2)], and the GND/VCC pads without a plane
    connection"""
    import pcbnew
    b = pcbnew.LoadBoard(pcb)
    T = pcbnew.ToMM
    E = b.GetBoardEdgesBoundingBox()
    area = T(E.GetWidth()) * T(E.GetHeight())
    out = []
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() not in ("GND", "VCC"):
            continue
        for L in z.GetLayerSet().Seq():
            fp = z.GetFilledPolysList(L)
            a = fp.Area() / 1e12
            out.append((z.GetNetname(), b.GetLayerName(L), fp.OutlineCount(), a, area))
    return out


def verify(pcb, drcfile):
    import pcbnew
    b = pcbnew.LoadBoard(pcb)
    T = pcbnew.ToMM
    d = json.load(open(drcfile))
    x1 = lambda v: v["type"] == "items_not_allowed" and all(" of X1" in i["description"] for i in v["items"])
    c = collections.Counter(v["type"] for v in d["violations"] if not x1(v))
    copper = {k: n for k, n in c.items() if k not in GR.COSMETIC}
    unr = d.get("unconnected_items", [])
    L = collections.Counter()
    nseg = nvia = 0
    widths = collections.Counter()
    for tr in b.GetTracks():
        if tr.Type() == pcbnew.PCB_VIA_T:
            nvia += 1
        else:
            nseg += 1
            L[b.GetLayerName(tr.GetLayer())] += T(tr.GetLength())
            widths[round(T(tr.GetWidth()), 3)] += 1
    txt = open(pcb).read()
    nonthrough = len(re.findall(r"^\t\(via (?:buried|blind|micro)", txt, re.M))
    pl = planes(pcb)
    # every GND/VCC pad: the DRC's unconnected list covers them (a power pad off its plane is an unconnected item);
    # count them for the report
    npwr = sum(1 for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() in ("GND", "VCC"))
    aw, conns, nn = GR.airwire(pcb)
    ok = not unr and not copper and not nonthrough and all(n == 1 for _, _, n, _, _ in pl) and len(pl) == 2
    print("final board %s:\n  unrouted: %d\n  vias: %d (all through vias: %s)\n  track: %d segments, %.0f mm "
          "(F.Cu %.0f, B.Cu %.0f; placement airwire %.0f mm), widths %s\n  DRC copper violations: %s\n"
          "  DRC inherited: %d (X1's two mounting holes in X1's own keepout, as on the built card)\n"
          "  DRC cosmetic: %s\n  power pads: %d GND/VCC pads, all on their plane (in the 0 above)\n  planes: %s"
          % (os.path.basename(pcb), len(unr), nvia, "yes" if not nonthrough else "NO, %d not" % nonthrough, nseg,
             sum(L.values()), L.get("F.Cu", 0), L.get("B.Cu", 0), aw, dict(widths), copper or "none",
             sum(1 for v in d["violations"] if x1(v)),
             dict(sorted((k, n) for k, n in c.items() if k in GR.COSMETIC)), npwr,
             "; ".join("%s on %s: %d piece(s), %.0f mm2 = %.0f %% of the board" % (n, l, k, a, 100 * a / ar)
                       for n, l, k, a, ar in pl)))
    for u in unr[:10]:
        print("    unrouted: %s" % " - ".join(i["description"] for i in u["items"]))
    silk_ok = silk_report(pcb)
    print("  -> %s" % ("PASS" if ok and silk_ok else "FAIL"))
    return ok and silk_ok


# ---------------------------------------------------------------------------------------------------------------------
def fab(pcb):
    sys.path.insert(0, os.path.join(GM.ROOT, "tools", "kicad"))
    import kicad_route as KR
    d = os.path.dirname(os.path.abspath(pcb))
    name = os.path.basename(pcb)[:-len(".kicad_pcb")]
    ger = os.path.join(d, "gerbers")
    zipf = os.path.join(d, name + "-gerbers.zip")
    if os.path.isdir(ger):
        shutil.rmtree(ger)
    os.makedirs(ger)
    run = lambda *a: subprocess.run(list(a), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run(CLI, "pcb", "export", "gerbers", "--no-protel-ext", "--layers",
        "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts", "-o", ger + "/", pcb)
    run(CLI, "pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm", "--generate-map",
        "--map-format", "gerberx2", "-o", ger + "/", pcb)
    if os.path.exists(zipf):
        os.remove(zipf)
    with zipfile.ZipFile(zipf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(glob.glob(ger + "/*")):
            z.write(f, os.path.basename(f))
    for side in ("top", "bottom"):
        run(CLI, "pcb", "render", "--side", side, "--quality", "high", "--floor", "-w", "2000", "-h", "1400",
            "-o", os.path.join(d, "%s-render-%s.png" % (name, side)), pcb)
    KR.placement(pcb)
    jlc(pcb)
    print("fab: %d gerber/drill files -> gerbers/ + %s; %s-render-top.png, -render-bottom.png, -placement.pdf"
          % (len(os.listdir(ger)), os.path.basename(zipf), name, ))
    for f in sorted(os.listdir(ger)):
        print("    gerbers/%s" % f)


JLC = """YACC1 memory card v2.0 - PCB order parameters (JLCPCB)            *** NOT ORDERED ***
Generated by finish_v2.py fab from %(board)s.

The same stack-up and options as the built card's order: JLCPCB 2000765A-Y42 (2025-06-27, "Memory V1_2025-06-27_Y42",
hardware/cards/memory/eagle/v1.3/fab/jlcpcb-order-2000765A-Y42.zip, file YG/4te.json):

  Gerber file          %(zip)s
  Base material        FR-4                              (4te.json board_type)
  Layers               4                                 (layers 4)
  Dimensions           %(w).1f x %(h).1f mm                 (built card: 177.8 x 114.0 mm, size_x/size_y in cm)
  PCB thickness        1.6 mm                            (thickness 1.6)
  Outer copper weight  1 oz                              (cu_outer 1.0)
  Inner copper weight  0.5 oz                            (cu_inner 0.5)
  Solder mask          green                             (color_sm)
  Silkscreen           white                             (color_ss)
  Surface finish       HASL with lead                    (finished)
  Via covering         plugged (solder-mask plugged)     (via)
  Impedance control    none; castellated / gold fingers: none

Layer stack (top to bottom), the gerbers in the zip:
  L1  %(name)s-F_Cu.gbr     signals (top, component side)
  L2  %(name)s-In1_Cu.gbr   GND plane (solid, thermal reliefs on the GND pads)
  L3  %(name)s-In2_Cu.gbr   VCC plane (solid, thermal reliefs on the VCC pads)
  L4  %(name)s-B_Cu.gbr     signals (bottom)
  plus F_Mask, B_Mask, F_Silkscreen, B_Silkscreen, Edge_Cuts, the Excellon drill file(s) and the drill map.

Design minimums on this board: track 0.25 mm, clearance 0.2 mm, via 0.8 mm pad / 0.4 mm drill, copper to edge 0.5 mm;
%(vias)d vias, all through vias; every part through-hole (no SMD, no assembly, no stencil).
"""


def jlc(pcb):
    import pcbnew
    b = pcbnew.LoadBoard(pcb)
    T = pcbnew.ToMM
    E = b.GetBoardEdgesBoundingBox()
    name = os.path.basename(pcb)[:-len(".kicad_pcb")]
    nvia = sum(1 for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T)
    out = os.path.join(os.path.dirname(os.path.abspath(pcb)), name + "-jlcpcb-order.txt")
    open(out, "w").write(JLC % dict(board=os.path.basename(pcb), zip=name + "-gerbers.zip", w=T(E.GetWidth()),
                                    h=T(E.GetHeight()), name=name, vias=nvia))
    print("jlc -> %s" % os.path.basename(out))


if __name__ == "__main__":
    cmd = sys.argv[1]
    ok = True
    if cmd == "project":
        project()
    elif cmd == "make":
        make(sys.argv[2], sys.argv[3])
    elif cmd == "cleanup":
        cleanup(sys.argv[2])
    elif cmd == "drop-removed":
        drop_removed(sys.argv[2])
        GM.refill(sys.argv[2])
    elif cmd == "silk":
        ok = silk_report(sys.argv[2])
    elif cmd == "verify":
        ok = verify(sys.argv[2], sys.argv[3])
    elif cmd == "fab":
        fab(sys.argv[2])
    else:
        raise SystemExit("unknown command " + cmd)
    sys.stdout.flush()
    os._exit(0 if ok else 1)
