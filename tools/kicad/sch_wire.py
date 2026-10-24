#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""sch_wire.py - wired schematic sheets for the generated YACC1 cards (2026-10-24): the parts of one functional block
placed by ELK (the Eclipse Layout Kernel: tools/kicad/elk_layout.js, elkjs) and the nets between them drawn as
orthogonal wires; power, the bus signals and one-pin nets keep a short stub to a label or a power symbol, as before.
Shared by hardware/cards/video/kicad/v2.0/gen_v20.py (the V2.0 card, a hierarchical schematic) and
hardware/cards/memory/kicad/v2.0/gen_mem_v2.py (sheet 7, the CF section). The model is the P8X project's
generators/sch (p8x_kicad_wire.py, elk_layout.js); the symbols, stubs, labels and power symbols are written by the CF
card's sheet writer (hardware/cards/cf/kicad/v1.0/gen_cf.py, class Sheet), used read-only through a subclass.

How a sheet is drawn (layout_sheet()):
  * every unit is an ELK node whose box holds its body, its fields and the stubs / labels / power symbols of the pins
    that are not wired; a wired pin is a port on the box edge (a short wire joins the pin to it);
  * a net is WIRED on a sheet when it is not power, not a bus signal and has two or more pins there. Each wire runs
    from the pin on a symbol's right-hand edge (a driver first) to the others, so the sheet reads left to right
    (FLOW_BY_SIDE in P8X). A wired net that also reaches other sheets gets a label node of its own: on the left when it
    is driven elsewhere, on the right when this sheet drives it;
  * everything is on the 1.27 mm grid (one ELK unit); after ELK the coordinates are integers again, the ends of every
    route are pinned to their ports and every wire is checked: no point shared by two nets except a plain crossing, no
    wire through a pin or a label of another net. Junctions go where three or more wire ends meet;
  * every wired net carries its name once (a label on the wire, or on a short stub for a hierarchical label); if the
    routing cannot be made clean with wider spacings the sheet falls back to the label style (every pin a stub and a
    label), as in P8X.
Connectivity is not trusted to this file: each card's build exports KiCad's netlist of the result and compares it,
net by net, with the card's netlist module.

Needs node and elkjs: cd tools/kicad && npm install (tools/setup_check.py checks it).
"""
import os, re, sys, json, math, subprocess, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "hardware", "cards", "cf", "kicad", "v1.0"))
import gen_cf                                          # noqa: E402  (the CF card's sheet writer, read-only)

G = 2.54
U1 = 1.27                                              # one ELK unit = the 1.27 mm connection grid
CH = 1.0 / U1                                          # a 1.27 mm character: ~1.0 mm wide, in units
DIRV = {"R": (1, 0), "L": (-1, 0), "U": (0, -1), "D": (0, 1)}
SIDE = {"R": "EAST", "L": "WEST", "U": "NORTH", "D": "SOUTH"}
DRIVER = ("output", "tri_state", "open_collector", "open_emitter", "power_out")
STUB = 4                                               # gen_cf.STUB (2 x 2.54 mm) in units


def elk_ready():
    """-> None when node and elkjs are there, else what to do"""
    try:
        r = subprocess.run(["node", "--version"], capture_output=True, text=True)
    except OSError:
        return "node is missing (brew install node)"
    if r.returncode:
        return "node does not run"
    if not os.path.isdir(os.path.join(HERE, "node_modules", "elkjs")):
        return "elkjs is missing: cd tools/kicad && npm install"
    return None


def run_elk(graph):
    r = subprocess.run(["node", os.path.join(HERE, "elk_layout.js")], input=json.dumps(graph), capture_output=True,
                       text=True, cwd=HERE)
    if r.returncode:
        raise SystemExit("ELK failed: " + r.stderr)
    return json.loads(r.stdout)


def tlen(s):
    """the width of a 1.27 mm text in units"""
    return len(s) * CH + 0.5


class Box:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)

    def __or__(self, o):
        return Box(min(self.x0, o.x0), min(self.y0, o.y0), max(self.x1, o.x1), max(self.y1, o.y1))

    def hits(self, o, g=0.0):
        return self.x0 < o.x1 + g and o.x0 < self.x1 + g and self.y0 < o.y1 + g and o.y0 < self.y1 + g

    def moved(self, dx, dy):
        return Box(self.x0 + dx, self.y0 + dy, self.x1 + dx, self.y1 + dy)


def text_box(x, y, text, just, size=1.27):
    """the box (units) of a horizontal text at (x, y) units with a KiCad justify string"""
    w = tlen(text) * size / 1.27
    h = size / U1
    j = just.split()
    if "left" in j:
        xa, xb = x, x + w
    elif "right" in j:
        xa, xb = x - w, x
    else:
        xa, xb = x - w / 2, x + w / 2
    if "bottom" in j:
        ya, yb = y - h, y
    elif "top" in j:
        ya, yb = y, y + h
    else:
        ya, yb = y - h / 2, y + h / 2
    return Box(xa, ya, xb, yb)


def label_box(x, y, d, text, kind):
    """the box of a label anchored at (x, y) (units) whose text runs in direction d"""
    extra = 0.4 if kind == "local" else 1.6           # hierarchical / global labels: the arrow / the frame
    L = tlen(text) + extra
    dx, dy = DIRV[d]
    if kind == "local":
        if d in "RL":
            return Box(x, y - 1.3, x + dx * L, y + 0.1)
        return Box(x - 1.3, y, x + 0.1, y + dy * L)
    if d in "RL":
        return Box(x, y - 0.9, x + dx * L, y + 0.9)
    return Box(x - 0.9, y, x + 0.9, y + dy * L)


# ---------------------------------------------------------------------------------------------------------------------
# the writer: gen_cf.Sheet with labels of the kind the card asks for, junctions, unique UUIDs per sheet
class WSheet(gen_cf.Sheet):
    def __init__(self, key, label_kind, shape=None):
        super().__init__()
        self.key = key                                 # makes every UUID of this sheet its own
        self.label_kind = label_kind                   # net -> "local" | "global" | "hier"
        self.shape = shape or (lambda net: "passive")
        self.nwires = self.nlabels = self.njunctions = self.nstubs = 0
        self.nwired = 0                                  # nets drawn as wires

    def U(self, *k):
        return gen_cf.U(self.key, *k)

    def wire(self, x1, y1, x2, y2):
        self.nwires += 1
        self.out.append('\t(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid "%s"))'
                        % (gen_cf.f(x1), gen_cf.f(y1), gen_cf.f(x2), gen_cf.f(y2), self.U("w", x1, y1, x2, y2)))

    def junction(self, x, y):
        self.njunctions += 1
        self.out.append('\t(junction (at %s %s) (diameter 0) (color 0 0 0 0) (uuid "%s"))'
                        % (gen_cf.f(x), gen_cf.f(y), self.U("j", x, y)))

    def part(self, ref, unit, x, y, rot=0, fields=None, **kw):
        """gen_cf's part(); a unit turned 180 degrees gets its Reference / Value upright: KiCad applies the symbol's
        turn to a field's justification, so the text is written at angle 0 with the justification flipped"""
        if rot == 180 and fields:
            flip = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}
            fields = {k: (v[0], v[1], " ".join(flip.get(w, w) for w in v[2].split())) for k, v in fields.items()}
        n0, w0 = len(self.out), self.nwires
        ends = super().part(ref, unit, x, y, rot=rot, fields=fields, **kw)
        self.nstubs += self.nwires - w0                  # the pin stubs to labels / power symbols
        if rot == 180:
            self.out[n0] = re.sub(r'(\(property "(?:Reference|Value|Footprint|Datasheet|Description)" "(?:[^"\\]|\\.)*" '
                                  r'\(at [-\d.]+ [-\d.]+) 180\)', r'\1 0)', self.out[n0])
        return ends

    def noconn(self, x, y):
        self.out.append('\t(no_connect (at %s %s) (uuid "%s"))' % (gen_cf.f(x), gen_cf.f(y), self.U("nc", x, y)))

    def text(self, x, y, s, size=1.524, bold=False, just="left top"):
        self.out.append('\t(text %s (exclude_from_sim no) (at %s %s 0) (effects (font (size %s %s)%s) (justify %s)) '
                        '(uuid "%s"))' % (gen_cf.q(s), gen_cf.f(x), gen_cf.f(y), gen_cf.f(size), gen_cf.f(size),
                                          " (bold yes)" if bold else "", just, self.U("t", x, y, s[:20])))

    def label(self, x, y, net, d):
        if (round(x, 3), round(y, 3), net) in self.labels:
            return
        self.labels.add((round(x, 3), round(y, 3), net))
        self.nlabels += 1
        kind = self.label_kind(net)
        if kind == "local":
            ang, just = {"R": (0, "left bottom"), "L": (180, "right bottom"), "U": (90, "left bottom"),
                         "D": (270, "right bottom")}[d]
            self.out.append('\t(label %s (at %s %s %d) (effects (font (size 1.27 1.27)) (justify %s)) (uuid "%s"))'
                            % (gen_cf.q(net), gen_cf.f(x), gen_cf.f(y), ang, just, self.U("l", x, y, net)))
            return
        ang, just = {"R": (0, "left"), "L": (180, "right"), "U": (90, "left"), "D": (270, "right")}[d]
        if kind == "global":
            self.out.append('\t(global_label %s (shape passive) (at %s %s %d) (fields_autoplaced yes) (effects (font '
                            '(size 1.27 1.27)) (justify %s)) (uuid "%s")\n\t\t(property "Intersheetrefs" '
                            '"${INTERSHEET_REFS}" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))\n\t)'
                            % (gen_cf.q(net), gen_cf.f(x), gen_cf.f(y), ang, just, self.U("gl", x, y, net),
                               gen_cf.f(x), gen_cf.f(y)))
        else:
            self.out.append('\t(hierarchical_label %s (shape %s) (at %s %s %d) (effects (font (size 1.27 1.27)) '
                            '(justify %s)) (uuid "%s"))' % (gen_cf.q(net), self.shape(net), gen_cf.f(x), gen_cf.f(y),
                                                            ang, just, self.U("hl", x, y, net)))


# ---------------------------------------------------------------------------------------------------------------------
# the circuit as one sheet sees it
class Design:
    """N: a netlist module (PARTS, NETS, NO_CONNECT); bus: nets always drawn as stub labels (the bus connector's);
    sheets: [(name, [(ref, unit), ...]), ...] - every unit of every part exactly once; hier: True = every net that
    reaches more than one sheet is wired to a label node of its own (a hierarchical schematic)"""
    def __init__(self, N, bus, sheets, lib, power=("VCC", "GND"), hier=False, rot=None):
        self.N, self.bus, self.power, self.hier, self.lib = N, set(bus), set(power), hier, lib
        self.netof = {(r, str(p)): n for n, conns in N.NETS.items() for r, p in conns}
        self.nc = {(r, str(p)) for r, ps in N.NO_CONNECT.items() for p in ps}
        self.sheets = sheets
        self.rot = rot or {}
        self.where = collections.defaultdict(set)        # net -> sheet names with a pin on it
        self.pin_etype = {}
        self.sheet_pins = collections.defaultdict(lambda: collections.defaultdict(list))   # sheet -> net -> pins
        for name, items in sheets:
            for ref, unit in items:
                for p in self.unit_pins(ref, unit):
                    key = (ref, p["num"])
                    self.pin_etype[key] = p["etype"]
                    n = self.netof.get(key)
                    if n:
                        self.where[n].add(name)
                        self.sheet_pins[name][n].append(key)
        self.drv_sheets = {}
        for n, sh in self.where.items():
            for kinds in (DRIVER, ("bidirectional", "passive")):
                d = {s for s in sh if any(self.pin_etype[k] in kinds for k in self.sheet_pins[s][n])}
                if d:
                    self.drv_sheets[n] = d
                    break
            else:
                self.drv_sheets[n] = set(sh)

    def symbol(self, ref):
        return self.lib(gen_cf.SYM_SUB.get(self.N.PARTS[ref][1], self.N.PARTS[ref][1]))

    def unit_pins(self, ref, unit):
        return self.symbol(ref).unit_pins(unit)

    def driven_here(self, net, sheet):
        return sheet in self.drv_sheets.get(net, ())

    def crosses(self, net):
        return len(self.where.get(net, ())) > 1

    def rotation(self, ref, unit):
        """rot for a unit: 0 for ICs; a two-pin part turned so VCC points up, GND down, signals sideways"""
        if (ref, unit) in self.rot:
            return self.rot[(ref, unit)]
        s = self.symbol(ref)
        pins = s.unit_pins(unit)
        if len(pins) != 2 or not self.N.PARTS[ref][1].startswith("Device:") or len(s.units) > 1:
            return 0
        best = None
        for rot in (0, 180, 90, 270):
            sc = 0
            for p in pins:
                d = outward(p, rot)
                n = self.netof.get((ref, p["num"]))
                if n == "VCC":
                    sc += 3 if d == "U" else -3 if d == "D" else 0
                elif n == "GND":
                    sc += 3 if d == "D" else -3 if d == "U" else 0
                elif n:
                    sc += 1 if d in "LR" else 0
            if best is None or sc > best[0]:
                best = (sc, rot)
        return best[1]


def outward(p, rot):
    a = (p["ang"] + 180) % 360
    dx, dy = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}[a]
    dx, dy = gen_cf.rot_pt(dx, dy, rot)
    return gen_cf.dir_name(dx, dy)


# ---------------------------------------------------------------------------------------------------------------------
# one unit as an ELK node
class Node:
    def __init__(self, D, sheet, ref, unit, wired, label_kind):
        self.ref, self.unit, self.id = ref, unit, "%s/%d" % (ref, unit)
        self.rot = rot = D.rotation(ref, unit)
        s = D.symbol(ref)
        value = D.N.PARTS[ref][0]
        self.pins = []                                  # (num, x, y, d, net, how)   units, y down, origin = symbol
        boxes = []
        b = s.unit_body(unit)
        if b:
            cs = [gen_cf.rot_pt(u, -v, rot) for u in (b[0], b[2]) for v in (b[1], b[3])]
            self.body = Box(min(c[0] for c in cs) / U1, min(c[1] for c in cs) / U1,
                            max(c[0] for c in cs) / U1, max(c[1] for c in cs) / U1)
        else:
            self.body = Box(-1, -1, 1, 1)
        boxes.append(self.body)
        for p in s.unit_pins(unit):
            px, py = gen_cf.rot_pt(p["x"], -p["y"], rot)
            x, y = round(px / U1), round(py / U1)
            d = outward(p, rot)
            key = (ref, p["num"])
            net = D.netof.get(key)
            dx, dy = DIRV[d]
            if net is None:
                how = "nc"
                boxes.append(Box(x - 0.8, y - 0.8, x + 0.8, y + 0.8))
            elif net in D.power:
                how = "power"
                ex, ey = x + dx * STUB, y + dy * STUB
                if d in "UD":
                    boxes.append(Box(ex - 2.0, ey, ex + 2.0, ey + dy * 4.2) | Box(x, y, ex, ey))
                else:
                    boxes.append(Box(ex, ey - 2.0, ex + dx * 6.5, ey + 2.0) | Box(x, y, ex, ey))
            elif net in wired:
                how = "wire"
            else:
                how = "label"
                ex, ey = x + dx * STUB, y + dy * STUB
                boxes.append(label_box(ex, ey, d, net, label_kind(net)) | Box(x, y, ex, ey))
            self.pins.append((p["num"], x, y, d, net, how))
            if how == "wire":
                boxes.append(Box(x, y, x, y))
        self.fields = self.place_fields(D, s, ref, value, unit, rot, boxes)
        for k, (fx, fy, just) in self.fields.items():
            boxes.append(text_box(fx / U1, fy / U1, ref if k == "Reference" else value, just))
        self.elements = list(boxes)                     # what a name label must not cover (finer than the box)
        bb = boxes[0]
        for q in boxes[1:]:
            bb = bb | q
        self.box = Box(math.floor(bb.x0 - 1), math.floor(bb.y0 - 1), math.ceil(bb.x1 + 1), math.ceil(bb.y1 + 1))
        self.ports = {}                                 # pin num -> (x, y) on the box edge, units rel. symbol
        for num, x, y, d, net, how in self.pins:
            if how == "wire":
                self.ports[num] = {"R": (self.box.x1, y), "L": (self.box.x0, y), "U": (x, self.box.y0),
                                   "D": (x, self.box.y1)}[d]

    def place_fields(self, D, s, ref, value, unit, rot, boxes):
        """Reference / Value (sheet mm offsets, justify) as gen_cf.Sheet.part() would put them, moved where a wire
        leaving a wired pin would cross them"""
        pins = s.unit_pins(unit)
        auto = gen_cf.Sheet.auto_fields(s, unit, rot, pins)
        out = {}
        for key in ("Reference", "Value"):
            if key in auto:
                out[key] = auto[key]
            else:
                lx, ly, _ = s.props.get(key, (0, 0, 0))
                px, py = gen_cf.rot_pt(lx, -ly, rot)
                out[key] = (px, py, s.just.get(key, "") if rot == 0 else "")
        rays = []
        for num, x, y, d, net, how in self.pins:
            if how == "wire":
                dx, dy = DIRV[d]
                rays.append(Box(x, y, x + dx * 60, y + dy * 60))
        if not rays:
            return out
        b = self.body
        x0, y0, x1, y1 = b.x0 * U1, b.y0 * U1, b.x1 * U1, b.y1 * U1
        cands = {"Reference": [(x0, y0 - 0.6, "left bottom"), (x1, y0 - 0.6, "right bottom"),
                               (x0 - 0.6, y0 + 0.6, "right top"), (x1 + 0.6, y0 + 0.6, "left top")],
                 "Value": [(x0, y1 + 0.6, "left top"), (x1, y1 + 0.6, "right top"),
                           (x0 - 0.6, y1 - 0.6, "right bottom"), (x1 + 0.6, y1 - 0.6, "left bottom")]}
        for key, txt in (("Reference", ref), ("Value", value)):
            fx, fy, just = out[key]
            tb = text_box(fx / U1, fy / U1, txt, just or "center")
            if not any(tb.hits(r, 0.3) for r in rays):
                continue
            for c in cands[key]:
                tb = text_box(c[0] / U1, c[1] / U1, txt, c[2])
                if not any(tb.hits(r, 0.3) for r in rays) and not any(tb.hits(q) for q in boxes[1:]):
                    out[key] = c
                    break
        return out


# ---------------------------------------------------------------------------------------------------------------------
# a sheet
class Layout:
    """the result of layout_sheet(): node origins, wires, junctions, name labels, label nodes (all in units)"""
    pass


def wired_nets(D, sheet):
    out = {}
    for n, pins in D.sheet_pins[sheet].items():
        if n in D.power or n in D.bus or len(set(pins)) < 2:
            continue
        out[n] = pins
    return out


def layout_sheet(D, sheet, items, label_kind, spacing=None, options=None):
    """-> Layout, or None if the routing could not be made clean (the caller draws the sheet in the label style)"""
    wired = wired_nets(D, sheet)
    tries = [spacing] if spacing else [(2, 2, 5, 8), (3, 3, 6, 10), (4, 4, 8, 12), (5, 5, 10, 16)]
    last = None
    for sp in tries:
        L, problems = _layout(D, sheet, items, wired, label_kind, sp, options or {})
        if not problems:
            return L
        last = problems
    sys.stderr.write("  sheet %s: wiring not clean (%s) - label style\n" % (sheet, "; ".join(map(str, last[:3]))))
    return None


# ELK's layerings tried by best_layout(): the default (network simplex) and three that bound the nodes in a column, so
# a block with many small parts (pull-ups, jacks) spreads across the sheet instead of down it
LAYERINGS = [("simplex", {}),
             ("coffman-graham 6", {"elk.layered.layering.strategy": "COFFMAN_GRAHAM",
                                   "elk.layered.layering.coffmanGraham.layerBound": "6"}),
             ("coffman-graham 4", {"elk.layered.layering.strategy": "COFFMAN_GRAHAM",
                                   "elk.layered.layering.coffmanGraham.layerBound": "4"}),
             ("stretch width", {"elk.layered.layering.strategy": "STRETCH_WIDTH"})]


def best_layout(D, sheet, items, label_kind, measure):
    """layout_sheet() with each of LAYERINGS; measure(L) -> (w, h) mm of the whole drawing. Kept: the one on the
    smallest paper, then the one with the fewest wires. -> (Layout or None, the layering's name)"""
    best = None
    for name, opts in LAYERINGS:
        L = layout_sheet(D, sheet, items, label_kind, options=opts)
        if L is None:
            continue
        w, h, nwires = measure(L)
        pn = [p[0] for p in PAPER].index(paper_for(w, h)[0])
        key = (pn, nwires)
        if best is None or key < best[0]:
            best = (key, L, name)
    return (best[1], best[2]) if best else (None, None)


def _layout(D, sheet, items, wired, label_kind, sp, options):
    edge_edge, edge_node, node_node, between = sp
    nodes = [Node(D, sheet, ref, unit, wired, label_kind) for ref, unit in items]
    pinnode = {}
    for n in nodes:
        for num in n.ports:
            pinnode[(n.ref, num)] = n
    # label nodes: a wired net that reaches other sheets (hier designs) - source (left) or sink (right)
    lnodes = {}
    if D.hier:
        for net in wired:
            if D.crosses(net):
                src = not D.driven_here(net, sheet)
                w = math.ceil(tlen(net) + 2.5)
                lnodes[net] = dict(id="L:" + net, src=src, w=w, h=2)
    children = []
    for n in nodes:
        b = n.box
        ports = [{"id": "%s.%s" % (n.id, num), "x": px - b.x0, "y": py - b.y0, "width": 0, "height": 0,
                  "layoutOptions": {"elk.port.side": SIDE[d]}}
                 for num, x, y, d, net, how in n.pins if how == "wire" for px, py in [n.ports[num]]]
        children.append({"id": n.id, "width": b.x1 - b.x0, "height": b.y1 - b.y0, "ports": ports,
                         "layoutOptions": {"elk.portConstraints": "FIXED_POS"}})
    for net, ln in lnodes.items():
        children.append({"id": ln["id"], "width": ln["w"], "height": ln["h"],
                         "ports": [{"id": ln["id"] + ".p", "x": ln["w"] if ln["src"] else 0, "y": 1, "width": 0,
                                    "height": 0, "layoutOptions": {"elk.port.side": "EAST" if ln["src"] else "WEST"}}],
                         "layoutOptions": {"elk.portConstraints": "FIXED_POS"}})
    edges = []

    def pdir(key):
        n = pinnode[key]
        return next(d for num, x, y, d, nn, how in n.pins if num == key[1])

    for net, pins in wired.items():
        ids = ["%s.%s" % (pinnode[k].id, k[1]) for k in pins]
        rank = []
        for k, i in zip(pins, ids):
            et = D.pin_etype[k]
            rank.append(((0 if pdir(k) == "R" else 1), (0 if et in DRIVER else 1 if et == "bidirectional" else 2), i))
        rank.sort()
        order = [r[2] for r in rank]
        ln = lnodes.get(net)
        if ln and ln["src"]:
            src, rest = ln["id"] + ".p", order
        else:
            src, rest = order[0], order[1:] + ([ln["id"] + ".p"] if ln else [])
        for k, t in enumerate(rest):
            edges.append({"id": "%s#%d" % (net, k), "sources": [src], "targets": [t]})
    graph = {"id": "sheet", "children": children, "edges": edges,
             "layoutOptions": {"elk.spacing.edgeEdge": str(edge_edge), "elk.spacing.edgeNode": str(edge_node),
                               "elk.layered.spacing.edgeEdgeBetweenLayers": str(edge_edge),
                               "elk.layered.spacing.edgeNodeBetweenLayers": str(edge_node),
                               "elk.spacing.nodeNode": str(node_node),
                               "elk.layered.spacing.nodeNodeBetweenLayers": str(between),
                               "elk.spacing.componentComponent": str(2 * node_node)}}
    graph["layoutOptions"].update(options)
    out = run_elk(graph)
    pos = {}
    for ch in out["children"]:
        pos[ch["id"]] = (round(ch["x"]), round(ch["y"]))
    L = Layout()
    L.nodes, L.origin, L.lnodes = nodes, {}, {}
    portabs = {}
    for n in nodes:
        X, Y = pos[n.id]
        ox, oy = X - n.box.x0, Y - n.box.y0
        L.origin[n.id] = (ox, oy)
        for num, (px, py) in n.ports.items():
            portabs["%s.%s" % (n.id, num)] = (ox + px, oy + py)
    for net, ln in lnodes.items():
        X, Y = pos[ln["id"]]
        p = (X + (ln["w"] if ln["src"] else 0), Y + 1)
        portabs[ln["id"] + ".p"] = p
        L.lnodes[net] = dict(ln, at=p, box=Box(X, Y, X + ln["w"], Y + ln["h"]))
    # every net as a set of unit grid edges: the pin-to-port stubs and ELK's routes, their ends pinned to the ports
    gedges = collections.defaultdict(set)

    def add_seg(net, a, b):
        (x0, y0), (x1, y1) = a, b
        if x0 != x1 and y0 != y1:
            raise ValueError("diagonal")
        if x0 == x1:
            for y in range(min(y0, y1), max(y0, y1)):
                gedges[net].add(((x0, y), (x0, y + 1)))
        else:
            for x in range(min(x0, x1), max(x0, x1)):
                gedges[net].add(((x, y0), (x + 1, y0)))

    pinpts = {}                                         # grid point -> net of a pin end (all pins, every kind)
    for n in nodes:
        ox, oy = L.origin[n.id]
        for num, x, y, d, net, how in n.pins:
            pinpts[(ox + x, oy + y)] = net or "nc:%s.%s" % (n.ref, num)
            if how == "wire":
                px, py = n.ports[num]
                add_seg(net, (ox + x, oy + y), (ox + px, oy + py))
    for e in out.get("edges", []):
        net = e["id"].rsplit("#", 1)[0]
        for sec in e.get("sections", []):
            pts = [sec["startPoint"]] + sec.get("bendPoints", []) + [sec["endPoint"]]
            pts = [[round(p["x"]), round(p["y"])] for p in pts]
            fix_ends(pts, portabs[e["sources"][0]], portabs[e["targets"][0]])
            try:
                for a, b in zip(pts, pts[1:]):
                    add_seg(net, tuple(a), tuple(b))
            except ValueError:
                return None, [("diagonal route", net)]
    L.gedges = gedges
    problems = check(L, gedges, pinpts)
    if problems:
        return None, problems
    L.pinpts = pinpts
    return L, []


def fix_ends(pts, s0, s1):
    """pin a route's two ends on its ports (ELK's are within rounding of them), keeping it orthogonal"""
    for idx, port, nxt in ((0, s0, 1), (len(pts) - 1, s1, len(pts) - 2)):
        a, b = pts[idx], pts[nxt]
        horiz = abs(a[1] - b[1]) <= abs(a[0] - b[0])
        pts[idx] = [port[0], port[1]]
        if len(pts) > 2 and 0 < nxt < len(pts) - 1:
            if horiz:
                pts[nxt][1] = port[1]
            else:
                pts[nxt][0] = port[0]
    if len(pts) == 2 and pts[0][0] != pts[1][0] and pts[0][1] != pts[1][1]:
        mx = (pts[0][0] + pts[1][0]) // 2
        pts[1:1] = [[mx, pts[0][1]], [mx, pts[1][1]]]
    # a fix may have left a diagonal next to a moved bend: square it
    k = 0
    while k < len(pts) - 1:
        a, b = pts[k], pts[k + 1]
        if a[0] != b[0] and a[1] != b[1]:
            pts.insert(k + 1, [b[0], a[1]])
        k += 1


def degree(gset):
    deg = collections.Counter()
    for a, b in gset:
        deg[a] += 1
        deg[b] += 1
    return deg


def check(L, gedges, pinpts):
    """wires of two nets meet only where they cross; no wire on another net's pin end or label; no wire through a
    symbol's box but its own stubs"""
    probs = []
    occ = {}
    for net, es in gedges.items():
        deg = degree(es)
        orient = collections.defaultdict(set)
        for a, b in es:
            o = "H" if a[1] == b[1] else "V"
            orient[a].add(o)
            orient[b].add(o)
        for p, k in deg.items():
            kind = "through" + orient[p].pop() if k == 2 and len(orient[p]) == 1 else "node"
            if p in occ and occ[p][0] != net:
                other, okind = occ[p]
                if not (kind.startswith("through") and okind.startswith("through") and kind != okind):
                    probs.append((net, other, p))
            else:
                occ[p] = (net, kind)
    for p, (net, kind) in occ.items():
        if p in pinpts and pinpts[p] != net:
            probs.append((net, "pin of " + str(pinpts[p]), p))
    # through another unit's box (the stubs to its own ports enter it)
    for n in L.nodes:
        ox, oy = L.origin[n.id]
        b = n.box.moved(ox, oy)
        own = {(ox + x, oy + y) for num, x, y, d, net, how in n.pins if how == "wire"}
        for net, es in gedges.items():
            for a, c in es:
                for p in (a, c):
                    if b.x0 < p[0] < b.x1 and b.y0 < p[1] < b.y1:
                        # allowed: on a straight line from one of this unit's wired pins to the box edge
                        if not any((p[0] == q[0] or p[1] == q[1]) and _on_stub(n, ox, oy, q, p) for q in own):
                            probs.append((net, "inside " + n.id, p))
                            break
    for net, ln in L.lnodes.items():
        b = ln["box"]
        for other, es in gedges.items():
            for a, c in es:
                for p in (a, c):
                    if b.x0 < p[0] < b.x1 and b.y0 < p[1] < b.y1:
                        probs.append((other, "inside label " + net, p))
    return probs[:20]


def _on_stub(n, ox, oy, q, p):
    for num, x, y, d, net, how in n.pins:
        if how != "wire" or (ox + x, oy + y) != q:
            continue
        px, py = n.ports[num]
        a, b = q, (ox + px, oy + py)
        return min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
    return False


def runs(es, breaks):
    """unit edges -> maximal straight wires, broken at every point of degree != 2, every bend and at breaks"""
    deg = degree(es)
    adj = collections.defaultdict(set)
    for a, b in es:
        adj[a].add(b)
        adj[b].add(a)
    seen, out = set(), []
    for a, b in sorted(es):
        if (a, b) in seen:
            continue
        horiz = a[1] == b[1]
        step = (1, 0) if horiz else (0, 1)
        lo, hi = a, b

        def stop(p, q_out):
            return deg[p] != 2 or p in breaks or q_out not in adj[p]
        while True:                                     # extend backwards
            prev = (lo[0] - step[0], lo[1] - step[1])
            if stop(lo, prev) or (min(prev, lo), max(prev, lo)) in seen:
                break
            seen.add((min(prev, lo), max(prev, lo)))
            lo = prev
        while True:
            nxt = (hi[0] + step[0], hi[1] + step[1])
            if stop(hi, nxt) or (min(hi, nxt), max(hi, nxt)) in seen:
                break
            seen.add((min(hi, nxt), max(hi, nxt)))
            hi = nxt
        seen.add((a, b))
        out.append((lo, hi))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# drawing a laid-out sheet
def draw(S, D, L, items, ox, oy, hier):
    """write the laid-out sheet into S (a WSheet), offset (ox, oy) mm. -> (extents box in mm, labels not clear)"""
    gx = lambda u: ox + u * U1
    gy = lambda u: oy + u * U1
    blocked = []                                         # boxes (units) a name label must not cover
    for n in L.nodes:
        X, Y = L.origin[n.id]
        rot = n.rot
        skip = {(n.ref, num) for num, x, y, d, net, how in n.pins if how == "wire"}
        S.part(n.ref, n.unit, gx(X), gy(Y), rot=rot, skip=skip,
               fields={k: (v[0], v[1], v[2]) for k, v in n.fields.items()})
        blocked += [e.moved(X, Y) for e in n.elements]
    for net, ln in L.lnodes.items():
        x, y = ln["at"]
        S.label(gx(x), gy(y), net, "L" if ln["src"] else "R")
        blocked.append(ln["box"])
    occupied = {}
    for net, es in L.gedges.items():
        for a, b in es:
            occupied[a] = net
            occupied[b] = net
    unclear = []
    S.nwired += len(L.gedges)
    for net, es in sorted(L.gedges.items()):
        deg = degree(es)
        breaks = {p for p in deg if p in L.pinpts}
        for a, b in runs(es, breaks):
            S.wire(gx(a[0]), gy(a[1]), gx(b[0]), gy(b[1]))
        for p, k in deg.items():
            if k >= 3:
                S.junction(gx(p[0]), gy(p[1]))
        if net in L.lnodes:
            continue
        spot = name_spot(net, es, deg, occupied, blocked, L.pinpts, hier, S.label_kind(net))
        if spot is None:
            unclear.append(net)
            p = sorted(deg)[0]
            spot = (p, p, "U")
        (px, py), (qx, qy), d = spot
        if (px, py) != (qx, qy):
            S.wire(gx(px), gy(py), gx(qx), gy(qy))
            if deg.get((px, py), 0) >= 2:
                S.junction(gx(px), gy(py))
            occupied[(qx, qy)] = net
        S.label(gx(qx), gy(qy), net, d)
        blocked.append(label_box(qx, qy, d, net, S.label_kind(net)))
    ext = None
    for b in blocked:
        ext = b if ext is None else ext | b
    for p in occupied:
        ext = ext | Box(p[0], p[1], p[0], p[1])
    return Box(gx(ext.x0), gy(ext.y0), gx(ext.x1), gy(ext.y1)), unclear


def name_spot(net, es, deg, occupied, blocked, pinpts, hier, kind):
    """where a wired net's name label goes: (point on the wire, label anchor, direction). A local label sits on a
    horizontal wire with its text above it. A hierarchical label stands at the end of a short stub, its text
    horizontal where it can (a stub off a vertical wire), else in line on a horizontal wire, else upright"""
    pts = sorted(deg, key=lambda p: (p[1], p[0]))
    hor = {p for a, b in es if a[1] == b[1] for p in (a, b)}
    ver = {p for a, b in es if a[0] == b[0] for p in (a, b)}
    first, second, third = [], [], []
    for p in pts:
        if p in pinpts or deg[p] >= 4:
            continue
        if kind == "local":
            if p in hor:
                first += [(p, p, "R"), (p, p, "L")]
            continue
        for d in ("R", "L", "U", "D"):
            dx, dy = DIRV[d]
            nb = (p[0] + dx, p[1] + dy)
            if (min(p, nb), max(p, nb)) in es:
                continue                                 # a wire already leaves p that way
            for ln in (2, 3, 4):
                q = (p[0] + ln * dx, p[1] + ln * dy)
                (first if d in "RL" else third).append((p, q, d))
        if p in hor and deg[p] == 2 and p not in ver:
            second += [(p, p, "R"), (p, p, "L")]
    for p, q, d in first + second + third:
        lb = label_box(q[0], q[1], d, net, kind)
        stub = Box(p[0], p[1], q[0], q[1])
        inline = p == q and kind != "local"
        bad = False
        for o, other in occupied.items():
            if other == net:
                if kind == "local" or inline:
                    if o[1] == p[1] or not (lb.x0 - 0.6 <= o[0] <= lb.x1 + 0.6 and lb.y0 - 0.6 <= o[1] <= lb.y1 + 0.6):
                        continue
                    bad = True
                    break
                if o != p and stub.x0 - 0.1 <= o[0] <= stub.x1 + 0.1 and stub.y0 - 0.1 <= o[1] <= stub.y1 + 0.1:
                    bad = True
                    break
                continue
            if lb.x0 - 0.6 <= o[0] <= lb.x1 + 0.6 and lb.y0 - 0.6 <= o[1] <= lb.y1 + 0.6:
                bad = True
                break
            if stub.x0 - 0.6 <= o[0] <= stub.x1 + 0.6 and stub.y0 - 0.6 <= o[1] <= stub.y1 + 0.6:
                bad = True
                break
        if bad:
            continue
        if any(lb.hits(b, 0.3) or stub.hits(b, 0.1) for b in blocked):
            continue
        if q in pinpts or (q in occupied and occupied[q] != net):
            continue
        return p, q, d
    return None


def label_style_rows(D, items, label_kind, width=360.0):
    """the fallback / label-only layout: units in rows, every pin a stub and a label -> [(Node, X, Y units)]"""
    nodes = [Node(D, None, ref, unit, set(), label_kind) for ref, unit in items]
    out, x, y, rowh = [], 0, 0, 0
    W = width / U1
    for n in nodes:
        w, h = n.box.x1 - n.box.x0, n.box.y1 - n.box.y0
        if x + w > W and x > 0:
            x, y, rowh = 0, y + rowh + 2, 0
        out.append((n, x - n.box.x0, y - n.box.y0))
        x += w + 2
        rowh = max(rowh, h)
    return out


def draw_rows(S, placed, ox, oy):
    ext = None
    for n, X, Y in placed:
        S.part(n.ref, n.unit, ox + X * U1, oy + Y * U1, rot=n.rot,
               fields={k: (v[0], v[1], v[2]) for k, v in n.fields.items()})
        b = n.box.moved(X, Y)
        ext = b if ext is None else ext | b
    return Box(ox + ext.x0 * U1, oy + ext.y0 * U1, ox + ext.x1 * U1, oy + ext.y1 * U1)


PAPER = (("A4", 297, 210), ("A3", 420, 297), ("A2", 594, 420), ("A1", 841, 594), ("A0", 1189, 841))


def paper_for(w, h):
    """the smallest landscape sheet holding a drawing w x h mm from (12.7, 22.86), clear of the title block"""
    for name, pw, ph in PAPER:
        if 12.7 + w <= pw - 12 and 22.86 + h <= ph - 45:
            return name, pw, ph
    return PAPER[-1]


# ---------------------------------------------------------------------------------------------------------------------
# the board's links to the schematic
def symbol_paths(netfile):
    """ref -> the footprint path KiCad's "Update PCB from Schematic" gives it: the sheet path of the component and its
    first symbol UUID (kicad-cli netlist: (sheetpath (tstamps "/<sheet>/")) and (tstamps "<uuid>" ...))"""
    s = open(netfile).read()
    s = s[s.index("(components"):s.index("(libparts") if "(libparts" in s else len(s)]
    out = {}
    for blk in re.split(r'\(comp\s*\n', s)[1:]:
        ref = re.search(r'\(ref "([^"]+)"\)', blk).group(1)
        sp = re.search(r'\(sheetpath\s*\(names "[^"]*"\)\s*\(tstamps "([^"]*)"\)\s*\)', blk)
        ts = re.search(r'\(tstamps "([^"]*)"', blk[sp.end():])
        out[ref] = sp.group(1) + ts.group(1)
    return out


def link(netfile, pcb):
    """link(<netlist>, <pcb>): the headless equivalent of F8 for the links only (as the P8X project's
    link_board.py): every footprint's (path ...) set to its symbol's, by text, so nothing else in the board file can
    change - no position, track, zone, value or text. A footprint that has no path line gets one where KiCad writes it
    (after the properties); a board-only footprint (no symbol, e.g. a mounting hole) is left as it is."""
    paths = symbol_paths(netfile)
    t = open(pcb).read()
    out, i, changed, added, same, alone = [], 0, 0, 0, 0, 0
    for form in gen_cf.top_forms(t):
        if not form.startswith("(footprint"):
            continue
        j = t.index(form, i)
        ref = re.search(r'\(property "Reference" "([^"]+)"', form).group(1)
        if ref not in paths:
            alone += 1
            continue
        want = '\t\t(path "%s")' % paths[ref]
        m = re.search(r'\n\t\t\(path "[^"]*"\)', form)
        if m:
            new = form[:m.start() + 1] + want + form[m.end():]
            if new == form:
                same += 1
            else:
                changed += 1
        else:
            k = min(form.index(x) for x in ("\n\t\t(attr ", "\n\t\t(fp_", "\n\t\t(pad ") if x in form)
            new = form[:k + 1] + want + form[k:]
            added += 1
        out.append(t[i:j])
        out.append(new)
        i = j + len(form)
    out.append(t[i:])
    open(pcb, "w").write("".join(out))
    print("link: %d footprint paths changed, %d added, %d already right, %d board-only footprints left alone (%d "
          "symbols in the netlist)" % (changed, added, same, alone, len(paths)))


def count(path_or_text):
    """(wires, labels of every kind, junctions) in a .kicad_sch"""
    t = open(path_or_text).read() if os.path.exists(path_or_text) else path_or_text
    return (len(re.findall(r'^\t\(wire ', t, re.M)),
            len(re.findall(r'^\t\((?:label|global_label|hierarchical_label) ', t, re.M)),
            len(re.findall(r'^\t\(junction ', t, re.M)))
