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
y-up, CCW in symbol space); the sheet is flipped to KiCad's y-down page. Eagle's
per-gate offsets in a deviceset are placement hints only and are ignored.

Correctness is verified separately by comparing KiCad's extracted netlist with the
netlist embedded in the imported board.
"""
import sys, os, math, uuid, re, hashlib
import xml.etree.ElementTree as ET

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

PIN_LEN = {"point": 0.0, "short": 2.54, "middle": 5.08, "long": 7.62, None: 5.08}
PIN_TYPE = {"in": "input", "out": "output", "io": "bidirectional", "oc": "open_collector",
            "pwr": "power_in", "sup": "power_in", "pas": "passive", "hiz": "tri_state",
            "nc": "no_connect", None: "passive"}

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
        return bool(pins) and all(p.get("direction") == "pwr" for p in pins)

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
        body.append("\t(exclude_from_sim no) (in_bom %s) (on_board %s)" % ("no" if is_power else "yes", "no" if is_power else "yes"))
        body.append("\t(property \"Reference\" \"%s\" (at 0 2.54 0) (effects (font (size 1.27 1.27))%s))" % (
            "#PWR" if is_power else esc(prefix), " (hide yes)" if is_power else ""))
        body.append("\t(property \"Value\" \"%s\" (at 0 -2.54 0) (effects (font (size 1.27 1.27))))" % esc(ds))
        body.append("\t(property \"Footprint\" \"%s\" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))" % (
            esc(self.fplib + ":" + package) if package else ""))
        body.append("\t(property \"Datasheet\" \"\" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))")
        body.append("\t(property \"Description\" \"Eagle %s:%s\" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))" % (esc(lib), esc(ds)))
        if shared:
            body.append("\t(symbol \"%s_0_1\"" % name)
            body.extend("\t\t" + s for s in shared)
            body.append("\t)")
        body.extend(unit_sexprs)
        body.append(")")
        entry = dict(sexpr="\n".join(body), units=units, power_gates=power_gates, is_power=is_power,
                     name=name, pins=pins_out, prefix=prefix, package=package, hidden_power=hidden_power)
        self.cache[k] = entry
        return entry

    def unit_sexpr(self, name, unitno, lib, gate, padmap, is_power):
        sym = self.e.symbol(lib, gate.get("symbol"))
        gname = gate.get("name")
        out = ["\t(symbol \"%s_%d_1\"" % (name, unitno)]
        for el in sym:
            t = el.tag
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
                _, a = rot_of(el.get("rot"))
                sz = float(el.get("size") or 1.27) * 0.8
                out.append("\t\t(text \"%s\" (at %s %s %d) (effects (font (size %s %s)) (justify left bottom)))" % (
                    esc(txt), f(float(el.get("x"))), f(float(el.get("y"))), a % 360, f(sz), f(sz)))
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

    def transform_for(self, sheet):
        xs, ys = [], []
        for w in sheet.iter("wire"):
            xs += [float(w.get("x1")), float(w.get("x2"))]; ys += [float(w.get("y1")), float(w.get("y2"))]
        for i in sheet.findall("instances/instance"):
            xs.append(float(i.get("x"))); ys.append(float(i.get("y")))
        for l in sheet.iter("label"):
            xs.append(float(l.get("x"))); ys.append(float(l.get("y")))
        if not xs:
            xs, ys = [0.0], [0.0]
        minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
        margin = 25.4
        ox = math.floor((margin - minx) / 1.27) * 1.27
        oy = math.ceil((maxy + margin) / 1.27) * 1.27
        w = math.ceil((maxx - minx + 2 * margin + 50) / 10) * 10
        h = math.ceil((maxy - miny + 2 * margin + 50) / 10) * 10
        return (lambda x: x + ox), (lambda y: oy - y), (w, h)

    def convert(self):
        os.makedirs(self.outdir, exist_ok=True)
        sheet_files = []
        for idx, sheet in enumerate(self.e.sheets):
            fn = "%s-sheet%d.kicad_sch" % (self.project, idx + 1)
            self.write_sheet(idx, sheet, os.path.join(self.outdir, fn))
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
        y = 25.4
        for i, fn in enumerate(sheet_files):
            su = self.sheet_uuids[i]
            out.append("\t(sheet (at 25.4 %s) (size 50.8 15.24) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (fields_autoplaced yes)" % f(y))
            out.append("\t\t(stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0)) (uuid \"%s\")" % su)
            out.append("\t\t(property \"Sheetname\" \"Sheet %d\" (at 25.4 %s 0) (effects (font (size 1.27 1.27)) (justify left bottom)))" % (i + 1, f(y - 0.7)))
            out.append("\t\t(property \"Sheetfile\" \"%s\" (at 25.4 %s 0) (effects (font (size 1.27 1.27)) (justify left top)))" % (fn, f(y + 15.9)))
            out.append("\t\t(instances (project \"%s\" (path \"/%s\" (page \"%d\"))))" % (self.project, self.root_uuid, i + 2))
            out.append("\t)")
            y += 25.4
        out.append("\t(sheet_instances (path \"/\" (page \"1\")))")
        out.append(")")
        with open(os.path.join(self.outdir, self.project + ".kicad_sch"), "w") as fh:
            fh.write("\n".join(out) + "\n")

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
        lx, ly = float(pe.get("x")), float(pe.get("y"))
        if mirror:
            lx = -lx
        a = math.radians(ang)
        return float(inst.get("x")) + lx * math.cos(a) - ly * math.sin(a), float(inst.get("y")) + lx * math.sin(a) + ly * math.cos(a)

    def write_sheet(self, idx, sheet, path):
        X, Y, (pw, ph) = self.transform_for(sheet)
        self._inst = {(i.get("part"), i.get("gate")): i for i in sheet.findall("instances/instance")}
        su = self.sheet_uuids[idx]
        sheet_path = "/%s/%s" % (self.root_uuid, su)
        body, used_symbols = [], {}
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
            if not re.search(r"[0-9]$", ref):
                ref += "0"   # KiCad references must end in a number; KiCad's own Eagle board importer appends 0
                self.stats.setdefault("renamed", set()).add((pname, ref))
            value = part.get("value") or ds
            if entry["is_power"]:
                sym = self.e.symbol(lib, dset.find("gates/gate").get("symbol"))
                value = sym.find("pin").get("name")
            attrs = {a.get("name"): a for a in inst.findall("attribute")}
            def prop_pos(nm, ddx, ddy):
                a = attrs.get(nm)
                if a is not None:
                    _, ar = rot_of(a.get("rot"))
                    return X(float(a.get("x"))), Y(float(a.get("y"))), ar % 360
                return x + ddx, y + ddy, 0
            rx, ry, ra = prop_pos("NAME", 2.54, -2.54)
            vx, vy, va = prop_pos("VALUE", 2.54, 2.54)
            suid = det_uuid(self.project, idx, pname, gname)
            s = ["\t(symbol (lib_id \"%s:%s\") (at %s %s %d)%s (unit %d)" % (
                self.libname, entry["name"], f(x), f(y), (ROTSIGN * ang) % 360, " (mirror x)" if mirror else "", unit)]
            s.append("\t\t(exclude_from_sim no) (in_bom %s) (on_board %s) (dnp no) (uuid \"%s\")" % (
                "no" if entry["is_power"] else "yes", "no" if entry["is_power"] else "yes", suid))
            s.append("\t\t(property \"Reference\" \"%s\" (at %s %s %d) (effects (font (size 1.27 1.27))%s))" % (
                esc(ref), f(rx), f(ry), ra, " (hide yes)" if entry["is_power"] else ""))
            s.append("\t\t(property \"Value\" \"%s\" (at %s %s %d) (effects (font (size 1.27 1.27))))" % (esc(value), f(vx), f(vy), va))
            s.append("\t\t(property \"Footprint\" \"%s\" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))" % (
                esc(self.libname + ":" + entry["package"]) if entry["package"] else "", f(x), f(y)))
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
                            "\t\t(property \"Value\" \"PWR_FLAG\" (at %s %s 0) (effects (font (size 1.27 1.27))))\n"
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
                    if pe.get("direction") == "pwr":
                        continue
                    lx, ly = float(pe.get("x")), float(pe.get("y"))
                    a = math.radians(ang)
                    if mirror:
                        lx = -lx
                    wx = float(inst.get("x")) + lx * math.cos(a) - ly * math.sin(a)
                    wy = float(inst.get("y")) + lx * math.sin(a) + ly * math.cos(a)
                    body.append("\t(no_connect (at %s %s) (uuid \"%s\"))" % (f(X(wx)), f(Y(wy)), det_uuid(suid, "nc", pe.get("name"))))
                    self.stats["noconnects"] += 1
        # ---- nets
        for net in sheet.findall("nets/net"):
            nname = net.get("name")
            for si, seg in enumerate(net.findall("segment")):
                wires = seg.findall("wire")
                ends = []
                for w in wires:
                    p1 = (float(w.get("x1")), float(w.get("y1"))); p2 = (float(w.get("x2")), float(w.get("y2")))
                    ends += [p1, p2]
                    body.append("\t(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid \"%s\"))" % (
                        f(X(p1[0])), f(Y(p1[1])), f(X(p2[0])), f(Y(p2[1])), det_uuid(self.project, idx, "w", nname, si, p1, p2)))
                    self.stats["wires"] += 1
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
                placed_lbl = False
                used_ends = set()
                for l in labels:
                    _, lr = rot_of(l.get("rot"))
                    lx, ly = float(l.get("x")), float(l.get("y"))
                    cands = [e for e in free if e not in used_ends] or [e for e in ends if e not in used_ends] or ends
                    if cands:
                        ex, ey = min(cands, key=lambda p: (p[0] - lx) ** 2 + (p[1] - ly) ** 2)
                        lx, ly = ex, ey
                        used_ends.add((ex, ey))
                    body.append(self.global_label(nname, X(lx), Y(ly), lr, idx, si, l.get("x"), l.get("y")))
                    placed_lbl = True
                # every remaining free end gets a label too: it is where Eagle joined a bus or left a stub
                for e in free:
                    if e in used_ends:
                        continue
                    body.append(self.global_label(nname, X(e[0]), Y(e[1]), 0, idx, si, "free", e))
                    used_ends.add(e); placed_lbl = True
                if not placed_lbl and ends:
                    body.append(self.global_label(nname, X(ends[0][0]), Y(ends[0][1]), 0, idx, si, "auto", "auto"))
                if not wires and not labels:
                    self.stats["skipped"].append(("segment without wires", nname))
        # ---- buses (cosmetic)
        for bus in sheet.findall("busses/bus"):
            for w in bus.iter("wire"):
                body.append("\t(polyline (pts (xy %s %s) (xy %s %s)) (stroke (width 0.5) (type default) (color 0 0 132 1)) (uuid \"%s\"))" % (
                    f(X(float(w.get("x1")))), f(Y(float(w.get("y1")))), f(X(float(w.get("x2")))), f(Y(float(w.get("y2")))),
                    det_uuid(self.project, idx, "bus", bus.get("name"), w.get("x1"), w.get("y1"), w.get("x2"), w.get("y2"))))
                self.stats["buses"] += 1
            seg = bus.find("segment/wire")
            if seg is not None:
                nm = bus.get("name").split(":")[0] if ":" in bus.get("name") else bus.get("name")
                body.append("\t(text \"%s\" (exclude_from_sim no) (at %s %s 0) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid \"%s\"))" % (
                    esc(nm), f(X(float(seg.get("x1")))), f(Y(float(seg.get("y1"))) - 1.0), det_uuid(self.project, idx, "bustext", bus.get("name"))))
        # ---- plain texts
        plain = sheet.find("plain")
        if plain is not None:
            for t in plain.findall("text"):
                _, tr = rot_of(t.get("rot"))
                body.append("\t(text \"%s\" (exclude_from_sim no) (at %s %s %d) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid \"%s\"))" % (
                    esc((t.text or "").strip()), f(X(float(t.get("x")))), f(Y(float(t.get("y")))), tr % 360, det_uuid(self.project, idx, "text", t.get("x"), t.get("y"))))
        # ---- assemble
        out = ["(kicad_sch", "\t(version 20250114)", "\t(generator \"eagle_sch_to_kicad\")", "\t(generator_version \"1.0\")",
               "\t(uuid \"%s\")" % su, "\t(paper \"User\" %s %s)" % (f(pw), f(ph)),
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

    def global_label(self, name, x, y, rot, idx, si, lx, ly):
        self.stats["labels"] += 1
        return "\t(global_label \"%s\" (shape passive) (at %s %s %d) (fields_autoplaced yes) (effects (font (size 1.27 1.27)) (justify left)) (uuid \"%s\")" \
               "\n\t\t(property \"Intersheetrefs\" \"${INTERSHEET_REFS}\" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))\n\t)" % (
                   esc(name), f(x), f(y), rot % 360, det_uuid(self.project, idx, "lbl", name, si, lx, ly), f(x), f(y))

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
