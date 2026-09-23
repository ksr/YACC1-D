#!/usr/bin/env python3
"""Convert an Eagle 9.x XML schematic (.sch) into a KiCad 9/10 hierarchical schematic.

Written for the YACC1 Memory card v1.3 conversion (YACCS/kicad). Behaviour:
  * one KiCad sub-sheet per Eagle sheet, plus a root sheet that references them
  * every Eagle deviceset/device used -> a lib_symbol, written both into a project
    library (<project>-eagle.kicad_sym) and embedded in each sheet; units = gates
  * Eagle power gates (all pins direction "pwr", e.g. the 74xx 'P' gate):
      - if the part's power gate is NOT placed in Eagle, its pins become hidden
        power_in pins on unit 0 (shared by all units), so KiCad connects them to
        VCC/GND by pin name exactly as Eagle does implicitly
      - if it IS placed, it is a normal visible unit and the Eagle wires apply
  * Eagle supply parts (GND, VCC, +5V ...) -> KiCad power symbols
  * every net segment gets a global label carrying the Eagle net name, snapped to a
    wire endpoint, so connectivity is by name across sheets (Eagle nets are global)
  * pins of placed units that Eagle leaves unconnected get no-connect flags
  * buses are drawn as cosmetic lines only
  * pin numbers come from the device's <connect> table (gate/pin -> pad)

Geometry: Eagle symbol coordinates and rotations map 1:1 onto KiCad's (both are
y-up, CCW in symbol space); the sheet is flipped to KiCad's y-down page. An Eagle mirrored
placement (rot="MRnn": rotate, THEN flip x) is KiCad `(at x y nn) (mirror y)`, which KiCad also applies as
rotate-then-mirror (checked on MR90 wire ends and against kicad-cli renders). Eagle's per-gate offsets in a
deviceset are placement hints only and are ignored.

Text (2026-09-23, readability pass; measured with tools/kicad/sch_overlaps.py):
  * NAME/VALUE come from where Eagle draws them: the smashed instance's <attribute>, else the symbol's >NAME/>VALUE
    text carried through the instance transform; Eagle size, ratio (-> thickness), align and layer. A symbol without
    that text (con-vg FEM has no >VALUE), a hidden layer or display="off" -> the field is hidden, as in Eagle.
  * Eagle draws a rotated/mirrored text readable inside the box the rotated text would cover; KiCad draws a field
    the same way, so each field gets the angle (0/90) and justify that reproduce Eagle's box (kicad_just()).
  * Where Eagle's gate name differs from KiCad's reference + unit letter ("X1-A3" vs "X1C"), the Reference is hidden
    and an "Eagle name" field shows Eagle's text.
  * Pin numbers/names are hidden per SYMBOL (KiCad ignores a per-pin hide) when every pin hides them in Eagle.
  * Texts and graphics on layers Eagle does not display (99 SpiceOrder) are dropped.
  * Net labels: each Eagle <label> is drawn on its own wire (or the nearest free end), running Eagle's way; a segment
    without one gets a converter label only when KiCad needs the name (net drawn in several segments, or an implicit
    power name), placed where it covers least; never on another net's wire (a label joins every wire through it).
    Nets on one sheet get local labels (Eagle's look), multi-sheet and power nets global labels (capped at 1.27 mm).
  * Page: each sheet is drawn once to measure it, then again on the smallest A4..A0 page (landscape, else portrait,
    else User) that holds it inside KiCad's frame, centred clear of the title block.

Correctness is verified separately by comparing KiCad's extracted netlist with the
netlist embedded in the imported board.
"""
import sys, os, math, uuid, re, hashlib, copy
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sch_overlaps as SO   # KiCad text metrics and box model (the same one the overlap checker measures with)

ROTSIGN = int(os.environ.get("ROTSIGN", "1"))

# ----------------------------------------------------------------------------- helpers
def det_uuid(*parts):
    h = hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()
    return str(uuid.UUID(h[:32]))

def f(x):
    s = "%.4f" % x
    s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s

def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')

def rot_of(s):
    if not s:
        return False, 0
    return s.startswith("M"), int(re.sub(r"[^0-9]", "", s) or 0)

def evec(x, y, mirror, ang):
    """Eagle placement of a local vector: rotate by ang (CCW), THEN mirror x (proven against wire ends on MR90 parts)"""
    x, y = SO.rot(x, y, ang)
    return (-x if mirror else x), y

def kvec(x, y, mirror, ang):
    """KiCad symbol transform of a local vector, (at .. ang) (mirror y): the same rotate-then-mirror"""
    return evec(x, y, mirror, ang)

ALIGN = {"bottom-left": ("left", "bottom"), "bottom-center": ("center", "bottom"), "bottom-right": ("right", "bottom"),
         "center-left": ("left", "center"), "center": ("center", "center"), "center-right": ("right", "center"),
         "top-left": ("left", "top"), "top-center": ("center", "top"), "top-right": ("right", "top")}

class TSpec:
    """an Eagle <text> or <attribute>: anchor, size, ratio, rotation (M = mirrored, S = spin), align, layer.
    A missing rot/align/ratio means Eagle's default (R0, bottom-left, 8 %), never the symbol text's: a smashed attribute
    carries its own absolute rotation. Only a missing size/layer falls back to `default` (the symbol's text)."""
    def __init__(self, el, default=None):
        d = default
        self.x, self.y = float(el.get("x") or 0), float(el.get("y") or 0)
        self.size = float(el.get("size") or (d.size if d is not None else 1.778))
        self.ratio = float(el.get("ratio") or 8)
        self.rot = r = el.get("rot") or "R0"
        self.mirror = "M" in r
        self.ang = int(round(float(re.sub(r"[^0-9.]", "", r) or 0) / 90.0)) * 90 % 360
        self.align = el.get("align") or "bottom-left"
        self.layer = el.get("layer") or (d.layer if d is not None else "94")

def eagle_rel(spec, imirror=False, iang=0):
    """Eagle text box relative to its anchor (y up, W=3 H=1 probe) after the text's own and the instance's transform,
    and whether it ends up horizontal. Eagle draws text readable INSIDE this box (a 180-degree text is flipped about its
    box, not left upside down), which is exactly how KiCad draws a field or text, so matching boxes = matching look."""
    h, v = ALIGN.get(spec.align, ("left", "bottom"))
    x0, y0, x1, y1 = SO.jbox(3.0, 1.0, {h, v})
    pts = []
    for u in (x0, x1):
        for w in (y0, y1):
            a, b = evec(u, w, spec.mirror, spec.ang)
            pts.append(evec(a, b, imirror, iang))
    box = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
    return box, (spec.ang + iang) % 180 == 0

def kicad_just(target, horiz, imirror=False, iang=0, field=True):
    """-> (angle, justify tokens) that make KiCad draw a text in the target box. For a symbol field the box goes
    through the symbol transform (imirror, iang); free text uses identity. Angles are 0 or 90 only (readable)."""
    for a in (0, 90):
        for h in ("left", "center", "right"):
            for v in ("bottom", "center", "top"):
                r = SO.rbox(*SO.jbox(3.0, 1.0, {h, v}), a)
                pts = [kvec(u, w, imirror, iang) for u in (r[0], r[2]) for w in (r[1], r[3])]
                box = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
                hz = (a + (iang if field else 0)) % 180 == 0
                if hz == horiz and all(abs(box[i] - target[i]) < 1e-6 for i in range(4)):
                    return a, " ".join(t for t in (h, v) if t != "center")
    return 0, ""

def font_sexpr(spec):
    sz = f(spec.size); th = f(max(spec.size * spec.ratio / 100.0, 0.1))
    return "(font (size %s %s) (thickness %s))" % (sz, sz, th)

def unit_letters(n):
    return SO.unit_suffix(n)

SYMTEXT_SCALE = float(os.environ.get("SYMTEXT_SCALE", "1.0"))   # symbol-internal text size vs Eagle's (was 0.8)

PIN_LEN = {"point": 0.0, "short": 2.54, "middle": 5.08, "long": 7.62, None: 5.08}
PIN_TYPE = {"in": "input", "out": "output", "io": "bidirectional", "oc": "open_collector",
            "pwr": "power_in", "sup": "power_in", "pas": "passive", "hiz": "tri_state",
            "nc": "passive", None: "passive"}   # Eagle designs do wire "nc" pins (a 2764 VPP labelled NC); KiCad drops no_connect pins from nets

def fp_name(package):
    """Footprint name as KiCad's Eagle board importer spells it: '/' and ':' are illegal in a LIB_ID item name and become '_'
    (Eagle '0207/10' -> '0207_10'), so the schematic's Footprint field resolves in the extracted .pretty."""
    return package.replace("/", "_").replace(":", "_")

def pin_name(n):
    out, bar = "", False
    for ch in n:
        if ch == "!":
            out += "}" if bar else "~{"
            bar = not bar
        else:
            out += ch
    return out + ("}" if bar else "")

def sanitize(name):
    return name.replace("*", "x").replace(" ", "_").replace(":", "_").replace("/", "_")

# ----------------------------------------------------------------------------- Eagle model
class _LibGroup:
    """Eagle 9 managed libraries can appear twice under one name (a urn: copy and a local copy);
    search every copy in document order so nothing is lost."""
    def __init__(self, libs): self.libs = libs
    def find(self, xpath):
        for l in self.libs:
            r = l.find(xpath)
            if r is not None: return r
        return None
    def findall(self, xpath): return [x for l in self.libs for x in l.findall(xpath)]
    def iter(self, tag=None): return (x for l in self.libs for x in l.iter(tag))
    def get(self, k, default=None): return self.libs[0].get(k, default)

class Eagle:
    def __init__(self, path):
        self.path = path
        self.root = ET.parse(path).getroot()
        self.sch = self.root.find("drawing/schematic")
        groups = {}
        for lib in self.sch.find("libraries"):
            groups.setdefault(lib.get("name"), []).append(lib)
        self.libs = {n: _LibGroup(ls) for n, ls in groups.items()}
        self.parts = {p.get("name"): p for p in self.sch.findall("parts/part")}
        self.sheets = self.sch.findall("sheets/sheet")
        # which gates of each part are placed anywhere
        self.placed = {}
        for sh in self.sheets:
            for i in sh.findall("instances/instance"):
                self.placed.setdefault(i.get("part"), set()).add(i.get("gate"))
        # layers Eagle displays (a text on a hidden layer, e.g. 99 SpiceOrder, is not drawn)
        self.layer_on = {l.get("number"): l.get("visible", "yes") == "yes" for l in self.root.iter("layer")}
        # how many segments (on all sheets) each net has, and on how many sheets it appears: a net drawn as ONE
        # segment needs no name label to hold together; a net on one sheet can use local labels
        self.net_segs, self.net_sheets = {}, {}
        for i, sh in enumerate(self.sheets):
            for net in sh.findall("nets/net"):
                n = net.get("name")
                self.net_segs[n] = self.net_segs.get(n, 0) + len(net.findall("segment"))
                self.net_sheets.setdefault(n, set()).add(i)

    def visible_layer(self, layer):
        return self.layer_on.get(str(layer), True)

    def symbol(self, lib, name):
        return self.libs[lib].find("symbols/symbol[@name='%s']" % name)

    def deviceset(self, lib, name):
        return self.libs[lib].find("devicesets/deviceset[@name='%s']" % name)

    def device(self, lib, dsname, devname):
        ds = self.deviceset(lib, dsname)
        for d in ds.findall("devices/device"):
            if (d.get("name") or "") == (devname or ""):
                return d
        return ds.find("devices/device")

    def is_power_gate(self, lib, gate):
        sym = self.symbol(lib, gate.get("symbol"))
        pins = sym.findall("pin")
        if not pins: return False
        if all(p.get("direction") == "pwr" for p in pins): return True
        # Eagle's power gates are 'request' gates; some carry a stray non-power pin (display-hp HTIL311A's PWR gate has
        # GND, VCC and an 'in' pin LEDSUP). Unplaced, Eagle still connects the pwr pins by name and leaves the rest open.
        return gate.get("addlevel") == "request" and any(p.get("direction") == "pwr" for p in pins)

# ----------------------------------------------------------------------------- symbol conversion
class SymbolBuilder:
    def __init__(self, eagle, libname, fplib):
        self.e = eagle
        self.libname = libname
        self.fplib = fplib
        self.cache = {}

    def build(self, lib, ds, dev, hidden_power):
        """hidden_power: True -> power gates become hidden unit-0 pins; False -> visible units."""
        k = (lib, ds, dev or "", hidden_power)
        if k in self.cache:
            return self.cache[k]
        dset = self.e.deviceset(lib, ds)
        device = self.e.device(lib, ds, dev)
        gates = dset.findall("gates/gate")
        prefix = dset.get("prefix") or "U"
        power_gates = {g.get("name") for g in gates if self.e.is_power_gate(lib, g)}
        # a supply symbol: single gate whose pins are all 'sup'
        is_power = len(gates) == 1 and all(p.get("direction") == "sup" for p in self.e.symbol(lib, gates[0].get("symbol")).findall("pin")) \
                   and len(self.e.symbol(lib, gates[0].get("symbol")).findall("pin")) == 1
        name = sanitize("%s_%s%s" % (lib, ds, ("_" + dev) if dev else ""))
        if hidden_power and power_gates:
            name += "_pwrhidden"
        padmap = {}
        for c in device.findall("connects/connect"):
            padmap.setdefault((c.get("gate"), c.get("pin")), []).append(c.get("pad"))
        units, unit_sexprs, shared = {}, [], []
        unitno = 0
        for g in gates:
            gname = g.get("name")
            if hidden_power and gname in power_gates:
                sym = self.e.symbol(lib, g.get("symbol"))
                for p in sym.findall("pin"):
                    if p.get("direction") != "pwr": continue   # a non-power pin of an unplaced power gate stays open, as in Eagle
                    for i, pad in enumerate(padmap.get((gname, p.get("name")), [])):
                        shared.append(self.pin_sexpr(p, pad, hidden=True))
                continue
            unitno += 1
            units[gname] = unitno
            unit_sexprs.append(self.unit_sexpr(name, unitno, lib, g, padmap, is_power))
        pins_out = {}
        for (g, p), pads in padmap.items():
            pins_out.setdefault(g, {})[p] = pads
        package = device.get("package") or ""
        body = ["(symbol \"%s\"" % name]
        if is_power:
            body.append("\t(power global)")
            body.append("\t(pin_numbers (hide yes))")
            body.append("\t(pin_names (offset 0) (hide yes))")
        else:
            # KiCad shows or hides pin numbers / names per SYMBOL (a per-pin hide inside a pin's name/number effects is
            # ignored when drawing). Eagle's per-pin visible= (both, pad, pin, off; default both) is almost always the
            # same for every pin of a device (rcl/led parts: off), so: hide when every drawn pin hides it.
            vis = [p.get("visible") or "both" for g in gates if not (hidden_power and g.get("name") in power_gates)
                   for p in self.e.symbol(lib, g.get("symbol")).findall("pin")]
            if vis and all(v in ("off", "pin") for v in vis):
                body.append("\t(pin_numbers (hide yes))")
            if vis and all(v in ("off", "pad") for v in vis):
                body.append("\t(pin_names (hide yes))")
        body.append("\t(exclude_from_sim no) (in_bom %s) (on_board %s)" % ("no" if is_power else "yes", "no" if is_power else "yes"))
        body.append("\t(property \"Reference\" \"%s\" (at 0 2.54 0) (effects (font (size 1.27 1.27))%s))" % (
            "#PWR" if is_power else esc(prefix), " (hide yes)" if is_power else ""))
        body.append("\t(property \"Value\" \"%s\" (at 0 -2.54 0) (effects (font (size 1.27 1.27))))" % esc(ds))
        body.append("\t(property \"Footprint\" \"%s\" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))" % (
            esc(self.fplib + ":" + fp_name(package)) if package else ""))
        body.append("\t(property \"Datasheet\" \"\" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))")
        body.append("\t(property \"Description\" \"Eagle %s:%s\" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))" % (esc(lib), esc(ds)))
        if shared:
            body.append("\t(symbol \"%s_0_1\"" % name)
            body.extend("\t\t" + s for s in shared)
            body.append("\t)")
        body.extend(unit_sexprs)
        body.append(")")
        entry = dict(sexpr="\n".join(body), units=units, power_gates=power_gates, is_power=is_power,
                     name=name, pins=pins_out, prefix=prefix, package=package, hidden_power=hidden_power,
                     ngates=len(gates))
        self.cache[k] = entry
        return entry

    def unit_sexpr(self, name, unitno, lib, gate, padmap, is_power):
        sym = self.e.symbol(lib, gate.get("symbol"))
        gname = gate.get("name")
        out = ["\t(symbol \"%s_%d_1\"" % (name, unitno)]
        for el in sym:
            t = el.tag
            if t in ("wire", "rectangle", "circle", "polygon", "text") and not self.e.visible_layer(el.get("layer")):
                continue   # e.g. rcl's "SpiceOrder 1/2" texts on layer 99, which Eagle does not display
            if t == "wire":
                out.append("\t\t" + self.wire_sexpr(el))
            elif t == "rectangle":
                out.append("\t\t(rectangle (start %s %s) (end %s %s) (stroke (width 0.254) (type default)) (fill (type background)))" % (
                    f(float(el.get("x1"))), f(float(el.get("y1"))), f(float(el.get("x2"))), f(float(el.get("y2")))))
            elif t == "circle":
                out.append("\t\t(circle (center %s %s) (radius %s) (stroke (width %s) (type default)) (fill (type none)))" % (
                    f(float(el.get("x"))), f(float(el.get("y"))), f(float(el.get("radius"))), f(max(float(el.get("width") or 0.254), 0.1))))
            elif t == "polygon":
                vs = el.findall("vertex")
                pts = " ".join("(xy %s %s)" % (f(float(v.get("x"))), f(float(v.get("y")))) for v in vs + vs[:1])
                out.append("\t\t(polyline (pts %s) (stroke (width 0.254) (type default)) (fill (type outline)))" % pts)
            elif t == "text":
                txt = (el.text or "").strip()
                if txt.upper() in (">NAME", ">VALUE", ">PART", ">GATE"):
                    continue
                sp = TSpec(el)
                sp.size *= SYMTEXT_SCALE
                box, horiz = eagle_rel(sp)
                a, jus = kicad_just(box, horiz, field=False)
                out.append("\t\t(text \"%s\" (at %s %s %d) (effects %s%s))" % (
                    esc(txt), f(sp.x), f(sp.y), a, font_sexpr(sp), (" (justify %s)" % jus) if jus else ""))
            elif t == "pin":
                pads = padmap.get((gname, el.get("name")), [])
                if is_power:
                    out.append("\t\t" + self.pin_sexpr(el, "1", hidden=False, power_name=True))
                elif not pads:
                    out.append("\t\t" + self.pin_sexpr(el, "", hidden=False))
                else:
                    for i, pad in enumerate(pads):
                        out.append("\t\t" + self.pin_sexpr(el, pad, hidden=(i > 0)))
        out.append("\t)")
        return "\n".join(out)

    def wire_sexpr(self, el):
        x1, y1, x2, y2 = (float(el.get(k)) for k in ("x1", "y1", "x2", "y2"))
        w = max(float(el.get("width") or 0.254), 0.15)
        curve = el.get("curve")
        if curve:
            th = math.radians(float(curve))
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            dx, dy = x2 - x1, y2 - y1
            d = math.hypot(dx, dy)
            if d > 1e-6 and abs(th) > 1e-6:
                h = d / (2 * math.tan(th / 2))
                nx, ny = -dy / d, dx / d
                ccx, ccy = cx + nx * h, cy + ny * h
                ca, sa = math.cos(th / 2), math.sin(th / 2)
                px, py = x1 - ccx, y1 - ccy
                mx, my = ccx + px * ca - py * sa, ccy + px * sa + py * ca
                return "(arc (start %s %s) (mid %s %s) (end %s %s) (stroke (width %s) (type default)) (fill (type none)))" % (
                    f(x1), f(y1), f(mx), f(my), f(x2), f(y2), f(w))
        return "(polyline (pts (xy %s %s) (xy %s %s)) (stroke (width %s) (type default)) (fill (type none)))" % (f(x1), f(y1), f(x2), f(y2), f(w))

    def pin_sexpr(self, p, number, hidden, power_name=False):
        x, y = float(p.get("x")), float(p.get("y"))
        _, a = rot_of(p.get("rot"))
        length = PIN_LEN.get(p.get("length"), 5.08)
        if hidden:
            # KiCad connects a hidden power pin by NAME, but also by POSITION if a wire end or label happens to sit exactly
            # on it (the video card's +5V label landed on IC15's hidden VCC pin and merged the two supplies). Park hidden
            # pins off-grid next to the symbol origin, where no Eagle wire (1 mil grid at worst) can ever end.
            x, y, length = 0.037, 0.053 + 0.011 * (sum(ord(c) for c in str(number)) % 40), 0
        etype = PIN_TYPE.get(p.get("direction"), "passive")
        shape = {"dot": "inverted", "clk": "clock", "dotclk": "inverted_clock"}.get(p.get("function"), "line")
        vis = p.get("visible")
        name = pin_name(p.get("name"))
        hide_name = vis in ("off", "pad") or power_name
        hide_num = vis in ("off", "pin") or power_name
        return "(pin %s %s (at %s %s %d) (length %s)%s (name \"%s\" (effects (font (size 1.27 1.27))%s)) (number \"%s\" (effects (font (size 1.27 1.27))%s)))" % (
            etype, shape, f(x), f(y), a % 360, f(length), " (hide yes)" if hidden else "",
            esc(name), " (hide yes)" if hide_name else "", esc(number), " (hide yes)" if hide_num else "")

# ----------------------------------------------------------------------------- schematic conversion
PWR_FLAG_SYMBOL = '''(symbol "PWR_FLAG"
	(power global)
	(pin_numbers (hide yes))
	(pin_names (offset 0) (hide yes))
	(exclude_from_sim no) (in_bom no) (on_board no)
	(property "Reference" "#FLG" (at 0 1.905 0) (effects (font (size 1.27 1.27)) (hide yes)))
	(property "Value" "PWR_FLAG" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
	(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
	(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
	(property "Description" "Marks a supply net as driven (added by the converter on VCC and GND)" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
	(symbol "PWR_FLAG_0_1"
		(polyline (pts (xy 0 0) (xy 0 1.27) (xy -1.016 1.905) (xy 0 2.54) (xy 1.016 1.905) (xy 0 1.27)) (stroke (width 0) (type default)) (fill (type none)))
	)
	(symbol "PWR_FLAG_1_1"
		(pin power_out line (at 0 0 90) (length 0) (name "pwr" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
	)
)'''

class Converter:
    def __init__(self, eagle_path, outdir, project):
        self.e = Eagle(eagle_path)
        self.outdir = outdir
        self.project = project
        self.libname = project + "-eagle"
        self.sb = SymbolBuilder(self.e, self.libname, self.libname)
        self.root_uuid = det_uuid(project, "root")
        self.sheet_uuids = [det_uuid(project, "sheet", i) for i in range(len(self.e.sheets))]
        self.flagged = set()
        self.stats = dict(symbols=0, wires=0, labels=0, junctions=0, buses=0, noconnects=0, skipped=[])

    def convert(self):
        os.makedirs(self.outdir, exist_ok=True)
        sheet_files = []
        for idx, sheet in enumerate(self.e.sheets):
            fn = "%s-sheet%d.kicad_sch" % (self.project, idx + 1)
            path = os.path.join(self.outdir, fn)
            # pass 1 draws the sheet unplaced, only to measure everything KiCad will draw (symbol bodies, field and label
            # text included); pass 2 draws it again on the smallest page that holds it, centred clear of the title block
            snap = (copy.deepcopy(self.stats), set(self.flagged))
            self.write_sheet(idx, sheet, path, ((lambda x: x), (lambda y: -y), '"User" 2000 2000'))
            self.stats, self.flagged = snap
            X, Y, paper = self.layout(path)
            self.write_sheet(idx, sheet, path, (X, Y, paper))
            sheet_files.append(fn)
        self.write_root(sheet_files)
        self.write_library()
        return self.stats

    def write_library(self):
        out = ["(kicad_symbol_lib", "\t(version 20241209)", "\t(generator \"eagle_sch_to_kicad\")", "\t(generator_version \"1.0\")"]
        for k in sorted(self.sb.cache, key=lambda k: self.sb.cache[k]["name"]):
            out.append("\n".join("\t" + line for line in self.sb.cache[k]["sexpr"].splitlines()))
        out.append("\n".join("\t" + line for line in PWR_FLAG_SYMBOL.splitlines()))
        out.append(")")
        with open(os.path.join(self.outdir, self.libname + ".kicad_sym"), "w") as fh:
            fh.write("\n".join(out) + "\n")
        with open(os.path.join(self.outdir, "sym-lib-table"), "w") as fh:
            fh.write("(sym_lib_table\n\t(version 7)\n\t(lib (name \"%s\")(type \"KiCad\")(uri \"${KIPRJMOD}/%s.kicad_sym\")(options \"\")(descr \"Symbols converted from the Eagle schematic\"))\n)\n" % (self.libname, self.libname))
        with open(os.path.join(self.outdir, "fp-lib-table"), "w") as fh:
            fh.write("(fp_lib_table\n\t(version 7)\n\t(lib (name \"%s\")(type \"KiCad\")(uri \"${KIPRJMOD}/%s.pretty\")(options \"\")(descr \"Footprints extracted from the imported Eagle board\"))\n)\n" % (self.libname, self.libname))

    def write_root(self, sheet_files):
        out = ["(kicad_sch", "\t(version 20250114)", "\t(generator \"eagle_sch_to_kicad\")", "\t(generator_version \"1.0\")",
               "\t(uuid \"%s\")" % self.root_uuid, "\t(paper \"A4\")",
               "\t(title_block (title \"%s\") (comment 1 \"Converted from Eagle schematic; see README.md\"))" % esc(self.project),
               "\t(lib_symbols)"]
        for i, fn in enumerate(sheet_files):
            # sheet symbols in columns of five, left to right, clear of the A4 frame and title block (20 fit)
            x, y = 25.4 + (i // 5) * 76.2, 25.4 + (i % 5) * 25.4
            su = self.sheet_uuids[i]
            out.append("\t(sheet (at %s %s) (size 50.8 15.24) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (fields_autoplaced yes)" % (f(x), f(y)))
            out.append("\t\t(stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0)) (uuid \"%s\")" % su)
            out.append("\t\t(property \"Sheetname\" \"Sheet %d\" (at %s %s 0) (effects (font (size 1.27 1.27)) (justify left bottom)))" % (i + 1, f(x), f(y - 0.7)))
            out.append("\t\t(property \"Sheetfile\" \"%s\" (at %s %s 0) (effects (font (size 1.27 1.27)) (justify left top)))" % (fn, f(x), f(y + 15.9)))
            out.append("\t\t(instances (project \"%s\" (path \"/%s\" (page \"%d\"))))" % (self.project, self.root_uuid, i + 2))
            out.append("\t)")
        out.append("\t(sheet_instances (path \"/\" (page \"1\")))")
        out.append(")")
        with open(os.path.join(self.outdir, self.project + ".kicad_sch"), "w") as fh:
            fh.write("\n".join(out) + "\n")

    def sym_texts(self, lib, symname):
        """-> {'NAME': TSpec|None, 'VALUE': TSpec|None}: the symbol's first >NAME / >VALUE text on a displayed layer"""
        out = {"NAME": None, "VALUE": None}
        for t in self.e.symbol(lib, symname).findall("text"):
            k = (t.text or "").strip().upper()[1:]
            if (t.text or "").strip().startswith(">") and k in out and out[k] is None and self.e.visible_layer(t.get("layer")):
                out[k] = TSpec(t)
        return out

    def fields_for(self, inst, lib, symname, mirror, ang, kang, X, Y):
        """where and how Eagle draws this instance's NAME and VALUE -> {'NAME': (x, y, angle, effects, hidden), ...}
        smashed: the instance's own <attribute> (absolute); not smashed: the symbol's >NAME / >VALUE text carried
        through the instance transform. No text at all (e.g. con-vg FEM has no >VALUE) = Eagle shows nothing = hidden."""
        st = self.sym_texts(lib, symname)
        attrs = {a.get("name"): a for a in inst.findall("attribute")}
        ix, iy = float(inst.get("x")), float(inst.get("y"))
        out = {}
        for k in ("NAME", "VALUE"):
            a_ = attrs.get(k)
            if a_ is not None and a_.get("x") is not None:
                sp = TSpec(a_, default=st[k])
                box, horiz = eagle_rel(sp)
                ax, ay = sp.x, sp.y
                hide = a_.get("display") == "off" or not self.e.visible_layer(sp.layer)
            elif st[k] is not None and inst.get("smashed") != "yes":
                sp = st[k]
                box, horiz = eagle_rel(sp, mirror, ang)
                dx, dy = evec(sp.x, sp.y, mirror, ang)
                ax, ay = ix + dx, iy + dy
                hide = False
            else:
                out[k] = (X(ix), Y(iy), 0, "(font (size 1.27 1.27))", True, 1.27, ""); continue
            fa, jus = kicad_just(box, horiz, mirror, kang, field=True)
            out[k] = (X(ax), Y(ay), fa, font_sexpr(sp) + ((" (justify %s)" % jus) if jus else ""), hide, sp.size, jus)
        return out

    @staticmethod
    def prop_sexpr(name, value, fld, force_hide=False):
        x, y, a, eff, hide = fld[:5]
        return "\t\t(property \"%s\" \"%s\" (at %s %s %d) (effects %s%s))" % (
            esc(name), esc(value), f(x), f(y), a, eff, " (hide yes)" if (hide or force_hide) else "")

    @staticmethod
    def field_box(fld, text, kmirror, kang):
        """KiCad sheet box of a symbol field (same model as tools/kicad/sch_overlaps.py)"""
        x, y, a, eff, hide, size, jus = fld
        tw, th = SO.text_wh(text, size, size)
        r = SO.rbox(*SO.jbox(tw, th, set(jus.split())), a)
        pts = [kvec(u, w, kmirror, kang) for u in (r[0], r[2]) for w in (r[1], r[3])]
        return (x + min(p[0] for p in pts), y - max(p[1] for p in pts), x + max(p[0] for p in pts), y - min(p[1] for p in pts))

    def occupy_symbol(self, inst, lib, symname, mirror, ang, X, Y):
        """record a placed symbol's body box, pin lines and pin-text areas (KiCad sheet coords) for label placement"""
        ix, iy = float(inst.get("x")), float(inst.get("y"))
        W = lambda lx, ly: (lambda d: (X(ix + d[0]), Y(iy + d[1])))(evec(lx, ly, mirror, ang))
        pts = []
        for el in self.e.symbol(lib, symname):
            if el.tag == "wire":
                pts += [W(float(el.get("x1")), float(el.get("y1"))), W(float(el.get("x2")), float(el.get("y2")))]
            elif el.tag == "rectangle":
                pts += [W(float(el.get("x1")), float(el.get("y1"))), W(float(el.get("x2")), float(el.get("y2")))]
            elif el.tag == "circle":
                r = float(el.get("radius")); c = W(float(el.get("x")), float(el.get("y")))
                pts += [(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)]
            elif el.tag == "polygon":
                pts += [W(float(v.get("x")), float(v.get("y"))) for v in el.findall("vertex")]
            elif el.tag == "pin":
                L = PIN_LEN.get(el.get("length"), 5.08)
                _, pa = rot_of(el.get("rot"))
                dx, dy = SO.rot(L, 0, pa)
                a_ = W(float(el.get("x")), float(el.get("y"))); b_ = W(float(el.get("x")) + dx, float(el.get("y")) + dy)
                self._occseg.append((a_[0], a_[1], b_[0], b_[1]))
                if L > 0 and el.get("visible") not in ("off",):
                    m = 1.4   # pin number above / pin name beside: keep labels off the pin's text band
                    self._occ.append((min(a_[0], b_[0]) - (m if a_[0] == b_[0] else 0), min(a_[1], b_[1]) - (m if a_[1] == b_[1] else 0),
                                      max(a_[0], b_[0]) + (m if a_[0] == b_[0] else 0), max(a_[1], b_[1]) + (m if a_[1] == b_[1] else 0)))
        if pts:
            self._occ.append((min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)))

    def pin_outward(self, part, gate, pin):
        """KiCad direction letter pointing from a placed pin's end away from its symbol"""
        inst = self._inst.get((part, gate)); p = self.e.parts.get(part)
        g = self.e.deviceset(p.get("library"), p.get("deviceset")).find("gates/gate[@name='%s']" % gate)
        pe = self.e.symbol(p.get("library"), g.get("symbol")).find("pin[@name='%s']" % pin)
        mirror, ang = rot_of(inst.get("rot")); _, pa = rot_of(pe.get("rot"))
        ox, oy = evec(*SO.rot(-1, 0, pa), mirror, ang)
        return ("R" if ox > 0 else "L") if abs(ox) >= abs(oy) else ("U" if oy > 0 else "D")

    def pin_world(self, part, gate, pin):
        """Eagle-sheet coordinates of a pin of a placed instance, or None."""
        inst = self._inst.get((part, gate))
        p = self.e.parts.get(part)
        if inst is None or p is None:
            return None
        lib, ds = p.get("library"), p.get("deviceset")
        g = self.e.deviceset(lib, ds).find("gates/gate[@name='%s']" % gate)
        pe = self.e.symbol(lib, g.get("symbol")).find("pin[@name='%s']" % pin)
        if pe is None:
            return None
        mirror, ang = rot_of(inst.get("rot"))
        dx, dy = evec(float(pe.get("x")), float(pe.get("y")), mirror, ang)
        return float(inst.get("x")) + dx, float(inst.get("y")) + dy

    PAGES = [("A4", 297, 210), ("A3", 420, 297), ("A2", 594, 420), ("A1", 841, 594), ("A0", 1189, 841)]
    PAGE_PAD = 5.0

    def layout(self, path):
        """-> (X, Y, paper) for the final pass: the smallest A-size page (landscape, else portrait) whose drawing area
        holds everything on the sheet, either above the title block or beside it, with the drawing centred there;
        a sheet too big for A0 gets a User page. Offsets stay on the 1.27 mm grid (wire ends keep their grid)."""
        texts, bodies, lines = SO.sheet_items(path)
        xs, ys = [], []
        for b in [t.box for t in texts] + [bd[:4] for bd in bodies] + [(min(l[0], l[2]), min(l[1], l[3]), max(l[0], l[2]), max(l[1], l[3])) for l in lines]:
            xs += [b[0], b[2]]; ys += [b[1], b[3]]
        if not xs: xs, ys = [0.0], [0.0]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        w, h = x1 - x0, y1 - y0
        m = SO.FRAME_IN + self.PAGE_PAD
        region = paper = None
        for name, W, H in self.PAGES:
            for pw, ph, tag in ((W, H, ""), (H, W, " portrait")):
                if w <= pw - 2 * m and h <= ph - 2 * m - SO.TB_H:          # above the title block, full width
                    region = (m, m, pw - m, ph - m - SO.TB_H)
                elif w <= pw - 2 * m - SO.TB_W and h <= ph - 2 * m:        # beside it, full height
                    region = (m, m, pw - m - SO.TB_W, ph - m)
                if region:
                    paper = '"%s"%s' % (name, tag); break
            if region: break
        if region is None:
            pw, ph = math.ceil(w + 2 * m), math.ceil(h + 2 * m + SO.TB_H)
            region = (m, m, pw - m, ph - m - SO.TB_H)
            paper = '"User" %d %d' % (pw, ph)
        g = 1.27
        dx = round(((region[0] + region[2]) / 2 - (x0 + x1) / 2) / g) * g
        dy = round(((region[1] + region[3]) / 2 - (y0 + y1) / 2) / g) * g
        return (lambda x: x + dx), (lambda y: dy - y), paper

    def write_sheet(self, idx, sheet, path, xform):
        X, Y, paper = xform
        self._XY = (X, Y)
        self._inst = {(i.get("part"), i.get("gate")): i for i in sheet.findall("instances/instance")}
        supply_net = {pr.get("part"): net.get("name") for net in sheet.findall("nets/net") for seg in net.findall("segment") for pr in seg.findall("pinref")}
        su = self.sheet_uuids[idx]
        sheet_path = "/%s/%s" % (self.root_uuid, su)
        body, used_symbols = [], {}
        self._occ, self._occseg, self._supply_parts = [], [], set()   # KiCad-sheet boxes / lines already drawn (label placement)
        # pins referenced by nets on this sheet: (part, gate, pin)
        used_pins = set()
        for net in sheet.findall("nets/net"):
            for pr in net.iter("pinref"):
                used_pins.add((pr.get("part"), pr.get("gate"), pr.get("pin")))
        # ---- placed symbols
        for inst in sheet.findall("instances/instance"):
            pname, gname = inst.get("part"), inst.get("gate")
            part = self.e.parts.get(pname)
            if part is None:
                self.stats["skipped"].append(("no part", pname)); continue
            lib, ds, dev = part.get("library"), part.get("deviceset"), part.get("device")
            dset = self.e.deviceset(lib, ds)
            pg = {g.get("name") for g in dset.findall("gates/gate") if self.e.is_power_gate(lib, g)}
            hidden_power = bool(pg) and not (pg & self.e.placed.get(pname, set()))
            entry = self.sb.build(lib, ds, dev, hidden_power)
            used_symbols[entry["name"]] = entry["sexpr"]
            unit = entry["units"].get(gname)
            if unit is None:
                self.stats["skipped"].append(("no unit", pname, gname)); continue
            x, y = X(float(inst.get("x"))), Y(float(inst.get("y")))
            mirror, ang = rot_of(inst.get("rot"))
            ref = ("#" + pname) if entry["is_power"] else pname
            if not entry["is_power"] and ref[:1].isdigit():
                ref = "UNK" + ref   # KiCad's Eagle board importer prefixes references that start with a digit (Eagle "5V" -> "UNK5V0"; "-RESET" stays)
                self.stats.setdefault("renamed", set()).add((pname, ref))
            if not re.search(r"[0-9]$", ref):
                ref += "0"   # KiCad references must end in a number; KiCad's own Eagle board importer appends 0
                self.stats.setdefault("renamed", set()).add((pname, ref))
            value = part.get("value") or ds
            if entry["is_power"]:
                sym = self.e.symbol(lib, dset.find("gates/gate").get("symbol"))
                value = sym.find("pin").get("name")
                # a KiCad power symbol names its net after its Value. In Eagle the NET name wins: the video card has a VCC
                # supply symbol sitting on a net Eagle calls +5V (and a separate implicit VCC net), so use the Eagle net name.
                value = supply_net.get(pname, value)
            kang = (ROTSIGN * ang) % 360
            fields = self.fields_for(inst, lib, dset.find("gates/gate[@name='%s']" % gname).get("symbol"), mirror, ang, kang, X, Y)
            # the Eagle name of a gate is part + gate ("X1-A3", "IC5P"); KiCad shows reference + unit letter ("X1C",
            # "IC5E"). Where they differ, the Reference is hidden and an "Eagle name" field shows Eagle's text instead.
            eagle_name = None
            if not entry["is_power"] and entry["ngates"] > 1 and len(entry["units"]) > 1 and unit_letters(unit) != gname:
                eagle_name = pname + gname
            if entry["is_power"]: self._supply_parts.add(pname)
            self.occupy_symbol(inst, lib, dset.find("gates/gate[@name='%s']" % gname).get("symbol"), mirror, ang, X, Y)
            for k, txt in (("NAME", None if (entry["is_power"] or eagle_name) else ref + (unit_letters(unit) if len(entry["units"]) > 1 else "")),
                           ("VALUE", value), ("NAME", eagle_name)):
                if txt and not fields[k][4]:
                    self._occ.append(self.field_box(fields[k], txt, mirror, kang))
            suid = det_uuid(self.project, idx, pname, gname)
            s = ["\t(symbol (lib_id \"%s:%s\") (at %s %s %d)%s (unit %d)" % (
                self.libname, entry["name"], f(x), f(y), kang, " (mirror y)" if mirror else "", unit)]   # Eagle MRnn = rotate, then flip x = KiCad (at nn) (mirror y); proven on the protocard 2026-09-20
            s.append("\t\t(exclude_from_sim no) (in_bom %s) (on_board %s) (dnp no) (uuid \"%s\")" % (
                "no" if entry["is_power"] else "yes", "no" if entry["is_power"] else "yes", suid))
            s.append(self.prop_sexpr("Reference", ref, fields["NAME"], force_hide=entry["is_power"] or eagle_name is not None))
            s.append(self.prop_sexpr("Value", value, fields["VALUE"]))
            if eagle_name:
                s.append(self.prop_sexpr("Eagle name", eagle_name, fields["NAME"]))
            s.append("\t\t(property \"Footprint\" \"%s\" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))" % (
                esc(self.libname + ":" + fp_name(entry["package"])) if entry["package"] else "", f(x), f(y)))
            s.append("\t\t(property \"Datasheet\" \"\" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))" % (f(x), f(y)))
            for g, pins in entry["pins"].items():
                if entry["units"].get(g) == unit or (entry["hidden_power"] and g in entry["power_gates"]):
                    for p, pads in pins.items():
                        for pad in pads:
                            s.append("\t\t(pin \"%s\" (uuid \"%s\"))" % (esc(pad), det_uuid(suid, pad)))
            if entry["is_power"]:
                s.append("\t\t(pin \"1\" (uuid \"%s\"))" % det_uuid(suid, "1"))
            s.append("\t\t(instances (project \"%s\" (path \"%s\" (reference \"%s\") (unit %d))))" % (self.project, sheet_path, esc(ref), unit))
            s.append("\t)")
            body.append("\n".join(s))
            self.stats["symbols"] += 1
            if entry["is_power"] and value not in self.flagged:
                # KiCad wants one power_out per supply net: add a PWR_FLAG on the pin of the first supply symbol
                self.flagged.add(value)
                pp = self.pin_world(pname, gname, self.e.symbol(lib, dset.find("gates/gate").get("symbol")).find("pin").get("name"))
                fx, fy = X(pp[0]), Y(pp[1])
                fuid = det_uuid(self.project, "pwrflag", value)
                used_symbols["PWR_FLAG"] = PWR_FLAG_SYMBOL
                body.append("\t(symbol (lib_id \"%s:PWR_FLAG\") (at %s %s 0) (unit 1)\n\t\t(exclude_from_sim no) (in_bom no) (on_board no) (dnp no) (uuid \"%s\")\n"
                            "\t\t(property \"Reference\" \"#FLG%d\" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))\n"
                            "\t\t(property \"Value\" \"PWR_FLAG\" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))\n"
                            "\t\t(property \"Footprint\" \"\" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))\n"
                            "\t\t(property \"Datasheet\" \"\" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))\n"
                            "\t\t(pin \"1\" (uuid \"%s\"))\n"
                            "\t\t(instances (project \"%s\" (path \"%s\" (reference \"#FLG%d\") (unit 1))))\n\t)" % (
                                self.libname, f(fx), f(fy), fuid, len(self.flagged), f(fx), f(fy - 1.9), f(fx + 2.54), f(fy - 3.8), f(fx), f(fy), f(fx), f(fy),
                                det_uuid(fuid, "1"), self.project, sheet_path, len(self.flagged)))
            # ---- no-connect flags for pins of this unit that no net references
            if not entry["is_power"]:
                g = dset.find("gates/gate[@name='%s']" % gname)
                sym = self.e.symbol(lib, g.get("symbol"))
                for pe in sym.findall("pin"):
                    if (pname, gname, pe.get("name")) in used_pins:
                        continue
                    dx, dy = evec(float(pe.get("x")), float(pe.get("y")), mirror, ang)
                    wx, wy = float(inst.get("x")) + dx, float(inst.get("y")) + dy
                    if pe.get("direction") == "pwr":
                        # Eagle connects an unwired 'pwr' pin of a PLACED gate implicitly to the supply net named like the pin
                        # (e.g. VPGM on a 2764's pin 1): give it a global label with that name so KiCad does the same
                        _, pa = rot_of(pe.get("rot"))
                        ox, oy = evec(*SO.rot(-1, 0, pa), mirror, ang)   # from the pin's end away from the body
                        d = ("R" if ox > 0 else "L") if abs(ox) >= abs(oy) else ("U" if oy > 0 else "D")
                        body.append(self.global_label(pe.get("name"), X(wx), Y(wy), d, idx, "pwrpin", pname, pe.get("name")))
                        self.stats["pwrpins"] = self.stats.get("pwrpins", 0) + 1
                        continue
                    body.append("\t(no_connect (at %s %s) (uuid \"%s\"))" % (f(X(wx)), f(Y(wy)), det_uuid(suid, "nc", pe.get("name"))))
                    self.stats["noconnects"] += 1
        # ---- nets
        # Eagle lets wires of DIFFERENT nets end at the same point (typically two bus stubs meeting on the bus line, e.g.
        # BDATA2/BDATA3 on the ALU) or end on another net's wire; KiCad would join them. Find those points first and pull
        # every net but the first back by 0.635 mm there.
        allw = {}
        for net in sheet.findall("nets/net"):
            for w in net.iter("wire"):
                allw.setdefault(net.get("name"), []).append(((float(w.get("x1")), float(w.get("y1"))), (float(w.get("x2")), float(w.get("y2")))))
        def on_seg(p, w):
            (x1, y1), (x2, y2) = w; x, y = p
            if abs((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) > 1e-3: return False
            return min(x1, x2) - 1e-3 <= x <= max(x1, x2) + 1e-3 and min(y1, y2) - 1e-3 <= y <= max(y1, y2) + 1e-3
        trim = set()   # (net name, rounded point) whose wire ends must be pulled back
        names = sorted(allw)
        for i, na in enumerate(names):
            for wa in allw[na]:
                for p in wa:
                    for nb in names:
                        if nb == na: continue
                        if any(on_seg(p, wb) for wb in allw[nb]):
                            loser = nb if nb > na else na   # the alphabetically later net gives way; only its ends move
                            if loser == na: trim.add((na, (round(p[0], 3), round(p[1], 3))))
                            elif any(abs(q[0] - p[0]) < 1e-3 and abs(q[1] - p[1]) < 1e-3 for wb in allw[nb] for q in wb):
                                trim.add((nb, (round(p[0], 3), round(p[1], 3))))
        if trim: self.stats["trimmed"] = self.stats.get("trimmed", 0) + len(trim)
        reqs = []   # per net segment: what its labels need (placed after every wire is known)
        def pull(p, q):
            """endpoint p of wire p-q moved 0.635 mm towards q (or to the middle of a very short wire)"""
            d = math.hypot(q[0] - p[0], q[1] - p[1]); t = min(0.635, d / 2) / d if d else 0
            return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
        for net in sheet.findall("nets/net"):
            nname = net.get("name")
            for si, seg in enumerate(net.findall("segment")):
                wires = seg.findall("wire")
                ends, segw = [], []
                moved = {}   # collision point -> new endpoints of this net's wires there (re-joined below)
                for w in wires:
                    p1 = (float(w.get("x1")), float(w.get("y1"))); p2 = (float(w.get("x2")), float(w.get("y2")))
                    k1, k2 = (round(p1[0], 3), round(p1[1], 3)), (round(p2[0], 3), round(p2[1], 3))
                    if (nname, k1) in trim: n1 = pull(p1, p2); moved.setdefault(k1, []).append(n1); p1 = n1
                    if (nname, k2) in trim: n2 = pull(p2, p1); moved.setdefault(k2, []).append(n2); p2 = n2
                    ends += [p1, p2]; segw.append((p1, p2))
                    body.append("\t(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid \"%s\"))" % (
                        f(X(p1[0])), f(Y(p1[1])), f(X(p2[0])), f(Y(p2[1])), det_uuid(self.project, idx, "w", nname, si, p1, p2)))
                    self.stats["wires"] += 1
                for k, pts in moved.items():
                    for a, b in zip(pts, pts[1:]):   # two or more of this net's wires met at the point: keep them joined
                        body.append("\t(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid \"%s\"))" % (
                            f(X(a[0])), f(Y(a[1])), f(X(b[0])), f(Y(b[1])), det_uuid(self.project, idx, "wj", nname, si, k, a, b)))
                for j in seg.findall("junction"):
                    body.append("\t(junction (at %s %s) (diameter 0) (color 0 0 0 0) (uuid \"%s\"))" % (
                        f(X(float(j.get("x")))), f(Y(float(j.get("y")))), det_uuid(self.project, idx, "j", nname, j.get("x"), j.get("y"))))
                    self.stats["junctions"] += 1
                labels = seg.findall("label")
                # endpoints that sit on a pin of a placed symbol are not free; labels prefer free ends
                pinpts = set()
                for pr in seg.findall("pinref"):
                    pp = self.pin_world(pr.get("part"), pr.get("gate"), pr.get("pin"))
                    if pp:
                        pinpts.add((round(pp[0], 3), round(pp[1], 3)))
                # endpoints shared by two wires of this segment are interior corners, also not free
                cnt = {}
                for e in ends:
                    cnt[(round(e[0], 3), round(e[1], 3))] = cnt.get((round(e[0], 3), round(e[1], 3)), 0) + 1
                free = [e for e in ends if (round(e[0], 3), round(e[1], 3)) not in pinpts and cnt[(round(e[0], 3), round(e[1], 3))] == 1]
                segw += [(a, b) for k, pts in moved.items() for a, b in zip(pts, pts[1:])]
                reqs.append(dict(net=nname, si=si, wires=segw, ends=ends, free=free, cnt=cnt, pinpts=pinpts, labels=labels,
                                 supply=any(pr.get("part") in self._supply_parts for pr in seg.findall("pinref"))))
                if not wires and not labels:
                    # pins that touch with no wire (an LED dropped straight onto a resistor, a supply symbol onto a pin):
                    # KiCad joins coincident pins itself, so a name label is only needed where the name must reach other
                    # segments or an implicit power net - one label, running out from the first pin
                    n_ = nname
                    need = not reqs[-1]["supply"] and (self.e.net_segs.get(n_, 0) > 1 or n_ in self.power_names())
                    done = 0
                    for pr in seg.findall("pinref")[:1] if need else []:
                        pp = self.pin_world(pr.get("part"), pr.get("gate"), pr.get("pin"))
                        if pp:
                            d = self.pin_outward(pr.get("part"), pr.get("gate"), pr.get("pin"))
                            glob = len(self.e.net_sheets.get(n_, ())) > 1 or n_ in self.power_names()
                            body.append((self.global_label if glob else self.local_label)(
                                n_, X(pp[0]), Y(pp[1]), d, idx, si, "pinonly", (pr.get("part"), pr.get("gate"), pr.get("pin"))))
                            done += 1
                    self.stats["pinonly"] = self.stats.get("pinonly", 0) + done
        # ---- net labels
        for bus in sheet.findall("busses/bus"):
            for w in bus.iter("wire"):
                self._occseg.append((X(float(w.get("x1"))), Y(float(w.get("y1"))), X(float(w.get("x2"))), Y(float(w.get("y2")))))
        for r in reqs:
            for p1, p2 in r["wires"]:
                self._occseg.append((X(p1[0]), Y(p1[1]), X(p2[0]), Y(p2[1])))
        self._netwires = [(r["net"], p1, p2) for r in reqs for p1, p2 in r["wires"]]
        for r in reqs:
            body.extend(self.place_labels(r, idx, X, Y))
        # ---- buses (cosmetic)
        for bus in sheet.findall("busses/bus"):
            for w in bus.iter("wire"):
                body.append("\t(polyline (pts (xy %s %s) (xy %s %s)) (stroke (width 0.5) (type default) (color 0 0 132 1)) (uuid \"%s\"))" % (
                    f(X(float(w.get("x1")))), f(Y(float(w.get("y1")))), f(X(float(w.get("x2")))), f(Y(float(w.get("y2")))),
                    det_uuid(self.project, idx, "bus", bus.get("name"), w.get("x1"), w.get("y1"), w.get("x2"), w.get("y2"))))
                self.stats["buses"] += 1
            # Eagle shows a bus's name only where the bus has a <label>: one text per label, as Eagle places it
            nm = bus.get("name").split(":")[0] if ":" in bus.get("name") else bus.get("name")
            for l in bus.iter("label"):
                if self.e.visible_layer(l.get("layer")):
                    body.append(self.free_text(nm, l, idx, "bustext", bus.get("name")))
        # ---- plain texts
        plain = sheet.find("plain")
        if plain is not None:
            for t in plain.findall("text"):
                if self.e.visible_layer(t.get("layer")):
                    body.append(self.free_text((t.text or "").strip(), t, idx, "text"))
        # ---- assemble
        out = ["(kicad_sch", "\t(version 20250114)", "\t(generator \"eagle_sch_to_kicad\")", "\t(generator_version \"1.0\")",
               "\t(uuid \"%s\")" % su, "\t(paper %s)" % paper,
               "\t(title_block (title \"%s sheet %d\") (comment 1 \"Converted from Eagle: %s sheet %d\"))" % (esc(self.project), idx + 1, esc(os.path.basename(self.e.path)), idx + 1),
               "\t(lib_symbols"]
        for nm in sorted(used_symbols):
            lines = used_symbols[nm].splitlines()
            lines[0] = lines[0].replace("(symbol \"", "(symbol \"%s:" % self.libname, 1)
            out.append("\n".join("\t\t" + line for line in lines))
        out.append("\t)")
        out.extend(body)
        out.append(")")
        with open(path, "w") as fh:
            fh.write("\n".join(out) + "\n")

    def free_text(self, txt, el, idx, *key):
        """a sheet text drawn where and how Eagle draws it (size, ratio, align; 180/270 kept readable like Eagle)"""
        sp = TSpec(el)
        box, horiz = eagle_rel(sp)
        a, jus = kicad_just(box, horiz, field=False)
        X, Y = self._XY
        return "\t(text \"%s\" (exclude_from_sim no) (at %s %s %d) (effects %s%s) (uuid \"%s\"))" % (
            esc(txt), f(X(sp.x)), f(Y(sp.y)), a, font_sexpr(sp), (" (justify %s)" % jus) if jus else "",
            det_uuid(self.project, idx, *(key + (el.get("x"), el.get("y")))))

    # KiCad label direction (sheet coords, y down) -> (angle, justify of a global label)
    DIRS = {"R": (0, "left"), "L": (180, "right"), "U": (90, "left"), "D": (270, "right")}

    def global_label(self, name, x, y, d, idx, si, lx, ly, size=1.27):
        """a global label at (x, y) whose flag runs in direction d (R/L/U/D) away from its wire"""
        self.stats["labels"] += 1
        a, j = self.DIRS[d]
        return "\t(global_label \"%s\" (shape passive) (at %s %s %d) (fields_autoplaced yes) (effects (font (size %s %s)) (justify %s)) (uuid \"%s\")" \
               "\n\t\t(property \"Intersheetrefs\" \"${INTERSHEET_REFS}\" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))\n\t)" % (
                   esc(name), f(x), f(y), a, f(size), f(size), j, det_uuid(self.project, idx, "lbl", name, si, lx, ly), f(x), f(y))

    def local_label(self, name, x, y, d, idx, si, lx, ly, size=1.27):
        """a sheet-local label (plain text just above / left of its wire, like an Eagle label) running in direction d"""
        self.stats["labels"] += 1
        a, j = self.DIRS[d]
        return "\t(label \"%s\" (at %s %s %d) (fields_autoplaced yes) (effects (font (size %s %s)) (justify %s bottom)) (uuid \"%s\"))" % (
            esc(name), f(x), f(y), a, f(size), f(size), j, det_uuid(self.project, idx, "lbl", name, si, lx, ly))

    def power_names(self):
        """net names KiCad also creates implicitly (hidden power pins, supply symbols): labels on them must be global"""
        if not hasattr(self, "_pwr_names"):
            self._pwr_names = {p.get("name") for lib in self.e.sch.find("libraries") for p in lib.iter("pin")
                               if p.get("direction") in ("pwr", "sup")}
        return self._pwr_names

    def label_score(self, kind, name, size, x, y, d, cost):
        """lower is better: preference cost + area over drawn things + wires/pins crossed (KiCad sheet coords)"""
        a, j = self.DIRS[d]
        b = SO.label_box("glabel" if kind == "g" else "label", name, size, size, x, y, a, j)
        b = SO.shrink(b, 0.1)
        sc = cost
        for o in self._occ:
            w = min(b[2], o[2]) - max(b[0], o[0]); h = min(b[3], o[3]) - max(b[1], o[1])
            if w > 0 and h > 0: sc += 4 * w * h + 2
        for (x1, y1, x2, y2) in self._occseg:
            # the box starts AT the anchor, so a wire merely ending there (or crossing there) only touches its shrunk
            # edge; a wire running INTO the box - its own wire included - counts
            if SO.seg_hits(b, x1, y1, x2, y2): sc += 3
        return sc, b

    def place_labels(self, r, idx, X, Y):
        """labels for one Eagle net segment. Every Eagle <label> is drawn (at its own spot on the wire, running the way
        Eagle's text runs). A segment with no Eagle label gets one converter label only if KiCad needs the name to join it
        to other segments or to an implicit power net; its spot is the free wire end / corner / wire middle that covers
        the least of what is already drawn. Nets on one sheet get local labels (Eagle's look), multi-sheet nets and
        power names get global labels."""
        n, si = r["net"], r["si"]
        glob = len(self.e.net_sheets.get(n, ())) > 1 or n in self.power_names() or any(l.get("xref") == "yes" for l in r["labels"])
        kind = "g" if glob else "l"
        emit = self.global_label if glob else self.local_label
        K = lambda p: (round(p[0], 3), round(p[1], 3))
        def kdir(vx, vy):   # Eagle vector (y up) -> KiCad direction letter
            return ("R" if vx > 0 else "L") if abs(vx) >= abs(vy) else ("U" if vy > 0 else "D")
        def outward(e):
            for p1, p2 in r["wires"]:
                if K(p1) == K(e): return kdir(p1[0] - p2[0], p1[1] - p2[1])
                if K(p2) == K(e): return kdir(p2[0] - p1[0], p2[1] - p1[1])
            return "R"
        wires = [(p1, p2) for p1, p2 in r["wires"] if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) > 1e-6]
        out = []
        def foreign(pt):
            """a label joins EVERY wire through its anchor (a wire end on another wire's middle does not): never put
            one where another net's wire runs or ends, e.g. a crossing, or a T that Eagle leaves unjoined"""
            x, y = pt
            for nn, (x1, y1), (x2, y2) in self._netwires:
                if nn == n: continue
                if abs((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) <= 1e-3 * max(1.0, math.hypot(x2 - x1, y2 - y1)) and \
                        min(x1, x2) - 1e-3 <= x <= max(x1, x2) + 1e-3 and min(y1, y2) - 1e-3 <= y <= max(y1, y2) + 1e-3:
                    return True
            return False
        def best(cands, name, size):
            scored = []
            ok = [c for c in cands if not foreign(c[0])]
            if not ok:   # every preferred spot touches another net: any end or wire middle of this segment will do
                more = [(e, outward(e), 4) for e in r["ends"]]
                for p1, p2 in wires:
                    m = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
                    more += [(m, d, 5) for d in (("U", "D") if abs(p2[0] - p1[0]) >= abs(p2[1] - p1[1]) else ("R", "L"))]
                ok = [c for c in more if not foreign(c[0])]
            cands = ok or cands
            for (ex, ey), d, cost in cands:
                sc, b = self.label_score(kind, name, size, X(ex), Y(ey), d, cost)
                scored.append((sc, (ex, ey), d, b))
            scored.sort(key=lambda t: t[0])
            return scored[0]
        used = set()
        for l in r["labels"]:
            sp = TSpec(l)
            lx, ly = sp.x, sp.y
            # Eagle's label sits on (or right by) a wire of its segment: anchor it at the nearest wire point
            q = None
            for p1, p2 in wires or [(e, e) for e in r["ends"][:1]]:
                dx, dy = p2[0] - p1[0], p2[1] - p1[1]; L2 = dx * dx + dy * dy
                t = max(0.0, min(1.0, ((lx - p1[0]) * dx + (ly - p1[1]) * dy) / L2)) if L2 else 0.0
                c = (p1[0] + t * dx, p1[1] + t * dy)
                dd = (c[0] - lx) ** 2 + (c[1] - ly) ** 2
                if q is None or dd < q[0]: q = (dd, c, (dx, dy))
            if q is None:
                continue
            box, horiz = eagle_rel(sp)
            ed = ("R" if box[0] >= -1e-6 else "L") if horiz else ("U" if box[1] >= -1e-6 else "D")
            # candidates: Eagle's own spot, and the segment's free wire ends (a label there also closes the dangling end
            # that KiCad's ERC would otherwise report; Eagle usually puts its label right by that end anyway)
            cands = [(q[1], ed, 1.0)]
            for e in r["free"]:
                if K(e) in used: continue
                dist = math.hypot(e[0] - lx, e[1] - ly)
                if glob:
                    cands.append((e, outward(e), 0.05 * dist))
                else:
                    cands += [(e, ed, 0.05 * dist), (e, outward(e), 0.3 + 0.05 * dist)]
            if glob:
                # a global label's flag must not lie along its own wire: also offer the perpendiculars at Eagle's spot
                wdx, wdy = q[2]
                perp = ("U", "D") if abs(wdx) >= abs(wdy) else ("R", "L")
                cands += [(q[1], d, 1.5) for d in perp]
            size = min(sp.size, 1.27) if glob else sp.size   # a global label's flag is ~1.9 x its text: 1.27 fits a 2.54 pitch
            cands = [c for c in cands if K(c[0]) not in used]
            if not cands:
                continue        # a second Eagle label of this segment with nowhere else to go: one label already names it
            sc, pt, d, b = best(cands, n, size)
            used.add(K(pt))
            out.append(emit(n, X(pt[0]), Y(pt[1]), d, idx, si, l.get("x"), l.get("y"), size=size))
            self._occ.append(b)
        need = not r["labels"] and not r["supply"] and (self.e.net_segs.get(n, 0) > 1 or n in self.power_names())
        if need and r["ends"]:
            cands = [(e, outward(e), 0) for e in r["free"]]
            for p1, p2 in wires:
                for e in (p1, p2):   # corners: two wires meet, not on a pin; offer the directions no wire takes
                    if r["cnt"].get(K(e), 0) == 2 and K(e) not in r["pinpts"]:
                        taken = {kdir(q2[0] - q1[0], q2[1] - q1[1]) if K(q1) == K(e) else kdir(q1[0] - q2[0], q1[1] - q2[1])
                                 for q1, q2 in wires if K(q1) == K(e) or K(q2) == K(e)}
                        cands += [(e, d, 2) for d in "RLUD" if d not in taken]
                L = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                if L >= 2.5:   # the middle of a wire, flag across it
                    m = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
                    perp = ("U", "D") if abs(p2[0] - p1[0]) >= abs(p2[1] - p1[1]) else ("R", "L")
                    cands += [(m, d, 3) for d in perp]
            if not cands:
                cands = [(r["ends"][0], outward(r["ends"][0]), 5)]
            sc, pt, d, b = best(cands, n, 1.27)
            out.append(emit(n, X(pt[0]), Y(pt[1]), d, idx, si, "auto", pt))
            self._occ.append(b)
        return out

# ----------------------------------------------------------------------------- main
if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: eagle_sch_to_kicad.py <eagle.sch> <outdir> <project-name>"); sys.exit(1)
    c = Converter(sys.argv[1], sys.argv[2], sys.argv[3])
    st = c.convert()
    print("converted: %d symbols, %d wires, %d labels, %d junctions, %d bus lines, %d no-connects" % (
        st["symbols"], st["wires"], st["labels"], st["junctions"], st["buses"], st["noconnects"]))
    if st.get("renamed"):
        print("renamed references:", sorted(st["renamed"]))
    if st["skipped"]:
        print("skipped:", st["skipped"][:20])
