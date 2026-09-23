#!/usr/bin/env python3
"""gen_cf.py - write the KiCad schematic, board and project of the YACC1 CF card v1.0 from cf_netlist.py.

Run with KiCad's bundled Python (the board half needs the pcbnew module):

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 gen_cf.py

cf_netlist.py is the circuit (parts, nets, no-connects); this script only draws it. It writes, next to itself:

  blank-card-v3.2-eagle.kicad_sym   the local bus-connector symbol FABC96R (three units = DIN rows a, b, c; pin numbers
                                    A1..C32 as on the blank V3.2 card's footprint, pin names = the V3.2 bus signals)
  blank-card-v3.2-eagle.pretty/     the local FABC96R footprint (copied unchanged from the blank V3.2 card)
  sym-lib-table, fp-lib-table       project library tables for the two local libraries
  yacc1-cf-card.kicad_sch           the schematic: KiCad standard symbols (embedded in lib_symbols), every pin wired by a
                                    short stub to a net label or a power symbol, no-connect flags on the NO_CONNECT pins
                                    and on the bus pins the card does not use, functional groups, design notes, title block
  yacc1-cf-card.kicad_pcb           the unrouted board: a copy of the blank V3.2 card (outline, X1 at its place) with the
                                    blank card's own LED/resistor removed, every part placed, every pad on its net, GND
                                    pours (both layers) and copper keepouts around the two DIN mounting screws
  yacc1-cf-card.kicad_pro           the project (tools/kicad/project-template.kicad_pro with this card's design rules)

Routing, fill, checks and fab outputs are build.sh's job. Every footprint is linked to its schematic symbol (UUID path),
so "Update PCB from Schematic" and DRC's schematic-parity check see one design.

Symbol names follow PARTS, except Device:CP, which KiCad 10 calls Device:C_Polarized (same pins: 1 = +).
The FABC96R symbol is redrawn from the blank card's Eagle import (96 one-pin units, unnamed pins) as three 32-pin
units with the bus signal names, so the sheet shows the whole bus pinout; pin numbers and footprint are unchanged.

2026-09-23. Board helpers modelled on ~/Developer/p8x/generators/gen_kicad.py (placement by pad origin, keepouts).
"""
import os, sys, re, json, uuid, shutil, subprocess, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", ".."))
sys.path.insert(0, HERE)
import cf_netlist as N

APP = "/Applications/KiCad/KiCad.app/Contents"
KSYM = APP + "/SharedSupport/symbols"
KFP = APP + "/SharedSupport/footprints"
CLI = APP + "/MacOS/kicad-cli"
BLANK = os.path.join(ROOT, "hardware", "bus", "blank-card", "kicad", "v3.2")
PROJ = "yacc1-cf-card"
LIB = "blank-card-v3.2-eagle"
SYM_SUB = {"Device:CP": "Device:C_Polarized"}           # KiCad 10 renamed CP
POWER_NETS = ("VCC", "GND")
G = 2.54
NS = uuid.UUID("6b1f3c1e-2d4a-4c55-9a3e-5f0c0cfca4d1")   # fixed namespace: stable UUIDs run to run


def U(*key):
    return str(uuid.uuid5(NS, "/".join(str(k) for k in key)))


def f(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


# ---------------------------------------------------------------------------------------------------------------------
# a small s-expression reader (enough for .kicad_sym files)
_TOK = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


def sparse(s):
    toks = _TOK.findall(s)
    pos = [0]

    def rd():
        out = []
        while pos[0] < len(toks):
            t = toks[pos[0]]; pos[0] += 1
            if t == "(":
                out.append(rd())
            elif t == ")":
                return out
            else:
                out.append(t)
        return out
    return rd()


def unq(t):
    return t[1:-1].replace('\\"', '"').replace("\\\\", "\\") if t.startswith('"') else t


def sfind(lst, key):
    return [x for x in lst if isinstance(x, list) and x and x[0] == key]


def lib_block(text, name):
    """The text of one top-level (symbol "name" ...) in a .kicad_sym file."""
    i = text.index('\n\t(symbol "%s"\n' % name) + 1
    d = 0; j = i; ins = False
    while True:
        c = text[j]
        if ins:
            if c == "\\": j += 1
            elif c == '"': ins = False
        elif c == '"': ins = True
        elif c == "(": d += 1
        elif c == ")":
            d -= 1
            if d == 0:
                return text[i:j + 1]
        j += 1


def kicad_cli(*args):
    r = subprocess.run([CLI] + list(args), capture_output=True, text=True)
    if r.returncode != 0 or "Unable" in r.stdout + r.stderr:
        raise SystemExit("kicad-cli %s failed:\n%s%s" % (" ".join(args[:2]), r.stdout, r.stderr))


def top_forms(text):
    """the top-level (...) forms inside a KiCad s-expression file"""
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


class LibSym:
    """One library symbol: its text (renamed lib:name for lib_symbols), pins per unit, property offsets."""
    def __init__(self, libid, block):
        self.libid = libid
        bare = libid.split(":")[1]
        self.text = block.replace('(symbol "%s"' % bare, '(symbol "%s"' % libid, 1)
        sym = sparse(block)[0]
        if sfind(sym, "extends"):
            raise SystemExit("%s: derived symbols are not handled" % libid)
        self.props, self.just = {}, {}
        for p in sfind(sym, "property"):
            at = sfind(p, "at")[0]
            self.props[unq(p[1])] = (float(at[1]), float(at[2]), float(at[3]))
            eff = sfind(p, "effects")
            j = sfind(eff[0], "justify") if eff else []
            self.just[unq(p[1])] = " ".join(j[0][1:]) if j else ""
        self.pins = collections.defaultdict(list)          # unit -> [pin dict]  (unit 0 = common to all units)
        self.body = collections.defaultdict(list)          # unit -> body outline points (library coords, y up)
        for sub in sfind(sym, "symbol"):
            m = re.match(r'"(.*)_(\d+)_(\d+)"$', sub[1])
            unit, style = int(m.group(2)), int(m.group(3))
            if style > 1:
                continue                                    # De Morgan alternates: same pins
            for g in sub[2:]:
                if not isinstance(g, list) or not g:
                    continue
                if g[0] in ("rectangle", "arc"):
                    self.body[unit] += [(float(k[1]), float(k[2])) for k in g if isinstance(k, list) and k[0] in ("start", "mid", "end")]
                elif g[0] in ("polyline", "bezier"):
                    self.body[unit] += [(float(k[1]), float(k[2])) for k in sfind(sfind(g, "pts")[0], "xy")]
                elif g[0] == "circle":
                    c, r = sfind(g, "center")[0], float(sfind(g, "radius")[0][1])
                    self.body[unit] += [(float(c[1]) - r, float(c[2]) - r), (float(c[1]) + r, float(c[2]) + r)]
            for p in sfind(sub, "pin"):
                at = sfind(p, "at")[0]
                self.pins[unit].append(dict(num=unq(sfind(p, "number")[0][1]), x=float(at[1]), y=float(at[2]),
                                            ang=int(float(at[3])), etype=p[1]))
        self.units = sorted(u for u in self.pins if u > 0) or [0]

    def unit_pins(self, unit):
        return self.pins.get(0, []) + (self.pins.get(unit, []) if unit else [])

    def unit_body(self, unit):
        """(x0, y0, x1, y1) of the unit's graphics, library coords (y up), or None"""
        pts = self.body.get(0, []) + (self.body.get(unit, []) if unit else [])
        if not pts:
            return None
        return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)


_libtext = {}


def std_symbol(libid):
    lib, name = libid.split(":")
    path = os.path.join(KSYM, lib + ".kicad_sym") if lib != LIB else os.path.join(HERE, LIB + ".kicad_sym")
    if path not in _libtext:
        _libtext[path] = open(path).read()
    return LibSym(libid, lib_block(_libtext[path], name))


# ---------------------------------------------------------------------------------------------------------------------
# 1. local libraries: the bus connector symbol (redrawn, three rows) and footprint (copied)
def bus_pin_names():
    t = open(os.path.join(BLANK, "blank-card-v3.2.kicad_pcb")).read()
    names = dict(re.findall(r'\(pad "([ABC]\d+)" thru_hole.*?\(net "([^"]*)"\)', t, re.S))
    assert len(names) == 96, "blank card: expected 96 named DIN pads, found %d" % len(names)
    return names


def write_local_libs():
    names = bus_pin_names()
    eff = "(effects (font (size 1.27 1.27)))"
    out = ['(kicad_symbol_lib', '\t(version 20251024)', '\t(generator "gen_cf")', '\t(generator_version "1.0")',
           '\t(symbol "FABC96R"', '\t\t(pin_names (offset 0.762))',
           '\t\t(exclude_from_sim no) (in_bom yes) (on_board yes)',
           '\t\t(property "Reference" "X" (at 8.89 6.35 0) %s)' % eff,
           '\t\t(property "Value" "FABC96R" (at 8.89 3.81 0) %s)' % eff,
           '\t\t(property "Footprint" "%s:FABC96R" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))' % LIB,
           '\t\t(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
           '\t\t(property "Description" %s (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))'
           % q("DIN 41612 96-pin connector, rows a/b/c (YACC1 bus V3.2). Unit A/B/C = row a/b/c; pin names are the "
               "V3.2 bus signals. Redrawn by gen_cf.py from the blank V3.2 card's Eagle import (con-vg FABC96R)."),
           '\t\t(property "ki_keywords" "DIN41612 bus YACC1" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))']
    for ui, row in enumerate("ABC", 1):
        out.append('\t\t(symbol "FABC96R_%d_1"' % ui)
        out.append('\t\t\t(rectangle (start 0 2.54) (end 17.78 -81.28) (stroke (width 0.254) (type default)) '
                   '(fill (type background)))')
        out.append('\t\t\t(text "row %s" (at 8.89 -83.82 0) %s)' % (row.lower(), eff))
        for k in range(1, 33):
            pn = "%s%d" % (row, k)
            out.append('\t\t\t(pin passive line (at 22.86 %s 180) (length 5.08) (name %s %s) (number %s %s))'
                       % (f(-(k - 1) * G), q(names[pn]), eff, q(pn), eff))
        out.append('\t\t)')
    out += ['\t\t(embedded_fonts no)', '\t)', ')', '']
    open(os.path.join(HERE, LIB + ".kicad_sym"), "w").write("\n".join(out))
    kicad_cli("sym", "upgrade", "--force", os.path.join(HERE, LIB + ".kicad_sym"))     # canonical format + load check
    pretty = os.path.join(HERE, LIB + ".pretty")
    os.makedirs(pretty, exist_ok=True)
    shutil.copy(os.path.join(BLANK, LIB + ".pretty", "FABC96R.kicad_mod"), os.path.join(pretty, "FABC96R.kicad_mod"))
    open(os.path.join(HERE, "sym-lib-table"), "w").write(
        '(sym_lib_table\n\t(version 7)\n\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.kicad_sym")(options "")'
        '(descr "YACC1 bus connector FABC96R (three rows), redrawn from the blank V3.2 card"))\n)\n' % (LIB, LIB))
    open(os.path.join(HERE, "fp-lib-table"), "w").write(
        '(fp_lib_table\n\t(version 7)\n\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.pretty")(options "")'
        '(descr "YACC1 bus connector FABC96R footprint, copied from the blank V3.2 card"))\n)\n' % (LIB, LIB))


# ---------------------------------------------------------------------------------------------------------------------
# 2. the schematic
NETOF = {(r, p): n for n, conns in N.NETS.items() for r, p in conns}
NC = {(r, p) for r, ps in N.NO_CONNECT.items() for p in ps}
ROOT_UUID = U("sheet", "root")
STUB = 2 * G


def rot_pt(x, y, rot):
    """screen-coordinate rotation, KiCad sense (positive = counter-clockwise as seen)"""
    return {0: (x, y), 90: (y, -x), 180: (-x, -y), 270: (-y, x)}[rot % 360]


def dir_name(dx, dy):
    return {(1, 0): "R", (-1, 0): "L", (0, -1): "U", (0, 1): "D"}[(dx, dy)]


class Sheet:
    def __init__(self):
        self.syms = {}           # libid -> LibSym
        self.out = []            # schematic items (text)
        self.pwr = 0
        self.flg = 0
        self.labels = set()      # (x, y, net) already labelled
        self.placed = collections.defaultdict(set)   # ref -> units placed
        self.pinhits = set()     # (ref, pin) drawn
        self.first_unit_uuid = {}

    def lib(self, libid):
        if libid not in self.syms:
            self.syms[libid] = std_symbol(libid)
        return self.syms[libid]

    def wire(self, x1, y1, x2, y2):
        self.out.append('\t(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid "%s"))'
                        % (f(x1), f(y1), f(x2), f(y2), U("w", x1, y1, x2, y2)))

    def label(self, x, y, net, d):
        if (round(x, 3), round(y, 3), net) in self.labels:
            return
        self.labels.add((round(x, 3), round(y, 3), net))
        ang, just = {"R": (0, "left bottom"), "L": (180, "right bottom"), "U": (90, "left bottom"),
                     "D": (270, "right bottom")}[d]
        self.out.append('\t(label %s (at %s %s %d) (effects (font (size 1.27 1.27)) (justify %s)) (uuid "%s"))'
                        % (q(net), f(x), f(y), ang, just, U("l", x, y, net)))

    def noconn(self, x, y):
        self.out.append('\t(no_connect (at %s %s) (uuid "%s"))' % (f(x), f(y), U("nc", x, y)))

    def text(self, x, y, s, size=1.524, bold=False, just="left top"):
        self.out.append('\t(text %s (exclude_from_sim no) (at %s %s 0) (effects (font (size %s %s)%s) (justify %s)) '
                        '(uuid "%s"))' % (q(s), f(x), f(y), f(size), f(size), " (bold yes)" if bold else "", just,
                                          U("t", x, y, s[:20])))

    def box(self, x1, y1, x2, y2, title):
        self.out.append('\t(rectangle (start %s %s) (end %s %s) (stroke (width 0.2) (type dash) (color 72 72 160 1)) '
                        '(fill (type none)) (uuid "%s"))' % (f(x1), f(y1), f(x2), f(y2), U("box", title)))
        self.text(x1 + 1.27, y1 + 1.27, title, size=2.0, bold=True)

    def power(self, kind, x, y, d, flag=False):
        """a power symbol (or PWR_FLAG) whose pin is at (x, y), its graphic pointing in direction d"""
        if flag:
            libid, self.flg = "power:PWR_FLAG", self.flg + 1
            ref, value = "#FLG%02d" % self.flg, "PWR_FLAG"
            rot = 0
        else:
            libid = "power:" + kind
            self.pwr += 1
            ref, value = "#PWR%03d" % self.pwr, kind
            up = {"U": 0, "L": 90, "D": 180, "R": 270}
            rot = up[d] if kind == "VCC" else (up[d] + 180) % 360
        s = self.lib(libid)
        vx, vy, _ = s.props["Value"]
        if rot in (90, 270):                              # sideways symbol: horizontal text clear of the graphic
            vy = 5.6 if vy > 0 else -5.6
        ox, oy = rot_pt(vx, -vy, rot)
        if rot in (90, 270):
            oy -= 0.9                                     # lift it off the stub line
        fa = (360 - rot) % 360                            # field angles are stored relative to the symbol
        uid = U("pwr", ref)
        self.out.append(
            '\t(symbol (lib_id %s) (at %s %s %d) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) '
            '(uuid "%s")\n\t\t(property "Reference" %s (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
            '\t\t(property "Value" %s (at %s %s %d) (effects (font (size 1.27 1.27))))\n'
            '\t\t(property "Footprint" "" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
            '\t\t(property "Datasheet" "" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
            '\t\t(pin "1" (uuid "%s"))\n'
            '\t\t(instances (project "%s" (path "/%s" (reference %s) (unit 1))))\n\t)'
            % (q(libid), f(x), f(y), rot, uid, q(ref), f(x), f(y), q(value), f(x + ox), f(y + oy), fa, f(x), f(y),
               f(x), f(y), U("pp", ref), PROJ, ROOT_UUID, q(ref)))

    @staticmethod
    def auto_fields(s, unit, rot, pins):
        """Reference/Value positions (sheet offsets + justify) that keep the text off the symbol body, for symbols whose
        library fields sit inside the body (KiCad's 74xx gates) or are drawn rotated (Device:R/C/LED; this sheet draws
        every field horizontal): pins only above/below the body -> both fields to its right, one line each side of the
        centre; otherwise Reference above the body and Value below it, left-aligned with the body. The field angle is
        written as (360 - rot), so the justify below acts in sheet terms."""
        b = s.unit_body(unit)
        if b is None:
            return {}
        corners = [rot_pt(u, -v, rot) for u in (b[0], b[2]) for v in (b[1], b[3])]
        x0, x1 = min(c[0] for c in corners), max(c[0] for c in corners)
        y0, y1 = min(c[1] for c in corners), max(c[1] for c in corners)       # sheet offsets, y down
        out = {}
        for key in ("Reference", "Value"):
            lx, ly, la = s.props.get(key, (0, 0, 0))
            inside = b[0] - 0.2 <= lx <= b[2] + 0.2 and b[1] - 0.2 <= ly <= b[3] + 0.2
            if not inside and la % 180 == (rot % 180):
                continue                                    # library placement is already clear and horizontal
            out[key] = None
        if not out:
            return {}
        dirs = set()
        for p in pins:
            dx, dy = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}[(p["ang"] + 180) % 360]
            dirs.add(rot_pt(dx, dy, rot))
        side = bool(dirs) and all(d[0] == 0 for d in dirs)
        if side:
            cy = (y0 + y1) / 2
            place = {"Reference": (x1 + 0.9, cy - 0.3, "left bottom"), "Value": (x1 + 0.9, cy + 0.3, "left top")}
        else:
            place = {"Reference": (x0, y0 - 0.6, "left bottom"), "Value": (x0, y1 + 0.6, "left top")}
        return {k: place[k] for k in out}

    def part(self, ref, unit, x, y, rot=0, stub=STUB, fields=None, skip=(), pstub=None):
        """place one unit of a PARTS symbol and draw every one of its pins: stub+label, stub+power symbol, or NC.
        fields: {'Reference': (dx, dy[, justify]), 'Value': ...} overrides of the property offsets (sheet mm); fields not
        given use the library position, or auto_fields() where that would put the text on the body."""
        value, symid, fpid, note = N.PARTS[ref]
        libid = SYM_SUB.get(symid, symid)
        s = self.lib(libid)
        uid = U("sym", ref, unit)
        self.first_unit_uuid.setdefault(ref, uid)
        if unit == min(s.units):
            self.first_unit_uuid[ref] = uid
        self.placed[ref].add(unit)
        pins = s.unit_pins(unit)
        props = []
        auto = self.auto_fields(s, unit, rot, pins)
        for key, val, hide in (("Reference", ref, False), ("Value", value, False), ("Footprint", fpid, True),
                               ("Datasheet", "", True), ("Description", note, True)):
            just = ""
            if fields and key in fields:
                px, py = fields[key][:2]
                just = fields[key][2] if len(fields[key]) > 2 else ""
            elif key in auto:
                px, py, just = auto[key]
            else:
                lx, ly, _ = s.props.get(key, (0, 0, 0))
                px, py = rot_pt(lx, -ly, rot)
                just = s.just.get(key, "") if rot == 0 else ""   # the library's own justify holds in its own frame
            props.append('\t\t(property "%s" %s (at %s %s %d) (effects (font (size 1.27 1.27))%s%s))'
                         % (key, q(val), f(x + px), f(y + py), (360 - rot) % 360,
                            (" (justify %s)" % just) if just else "", " (hide yes)" if hide else ""))
        self.out.append(
            '\t(symbol (lib_id %s) (at %s %s %d) (unit %d) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) '
            '(uuid "%s")\n%s\n%s\n\t\t(instances (project "%s" (path "/%s" (reference %s) (unit %d))))\n\t)'
            % (q(libid), f(x), f(y), rot, unit, uid, "\n".join(props),
               "\n".join('\t\t(pin %s (uuid "%s"))' % (q(p["num"]), U("pin", ref, p["num"])) for p in pins),
               PROJ, ROOT_UUID, q(ref), unit))
        ends = {}
        for p in pins:
            px, py = rot_pt(p["x"], -p["y"], rot)
            wx, wy = x + px, y + py
            a = (p["ang"] + 180) % 360                      # outward direction, library sense (y up)
            dx, dy = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}[a]
            dx, dy = rot_pt(dx, dy, rot)
            key = (ref, p["num"])
            self.pinhits.add(key)
            ends[p["num"]] = (wx, wy)
            if key in skip:
                continue
            net = NETOF.get(key)
            if net is None:
                if key in NC or ref == "X1":
                    self.noconn(wx, wy)
                    continue
                raise SystemExit("schematic: %s.%s is neither on a net nor a no-connect" % key)
            st = pstub if (pstub and net in POWER_NETS) else stub
            ex, ey = wx + dx * st, wy + dy * st
            self.wire(wx, wy, ex, ey)
            d = dir_name(dx, dy)
            if net in POWER_NETS:
                self.power(net, ex, ey, d)
            else:
                self.label(ex, ey, net, d)
        return ends

    def write(self, path):
        head = ['(kicad_sch', '\t(version 20260306)', '\t(generator "gen_cf")', '\t(generator_version "1.0")',
                '\t(uuid "%s")' % ROOT_UUID, '\t(paper "A3")',
                '\t(title_block (title "YACC1 CF card v1.0") (date "%s") (rev "%s") (company "YACC1")' % (N.DATE, N.REV),
                '\t\t(comment 1 "CompactFlash (True IDE, 8-bit) on I/O ports P8/P9 - theory: docs/cards/cf.md")',
                '\t\t(comment 2 "Circuit source: cf_netlist.py; this sheet is generated by gen_cf.py")',
                '\t\t(comment 3 "Bus: YACC1 V3.2 DIN 41612 (docs/system/BUS.md)"))',
                '\t(lib_symbols']
        for libid in sorted(self.syms):
            head.append(self.syms[libid].text)
        head.append('\t)')
        tail = ['\t(sheet_instances (path "/" (page "1")))', '\t(embedded_fonts no)', ')', '']
        open(path, "w").write("\n".join(head + self.out + tail))


def gx(n):
    return n * G


def build_schematic():
    S = Sheet()
    # --- bus connector: three rows side by side, top left --------------------------------------------------------
    S.box(gx(5), gx(11), gx(57), gx(52.5), "BUS  X1  DIN 41612 (YACC1 V3.2)")
    for i, u in enumerate((1, 2, 3)):
        S.part("X1", u, gx(6 + 17 * i), gx(16), fields={"Reference": (8.89, -5.6), "Value": (8.89, -3.6)})
    S.text(gx(5.5), gx(50), "Unused bus pins carry no-connect flags. The card uses DATA0-7, IO-ADDR0-3, -IO-RD,\n"
           "-IO-WR, -RESET and the six VCC / six GND pins.", size=1.27)

    # --- decode + strobe gating ------------------------------------------------------------------------------------
    S.box(gx(58), gx(5), gx(105), gx(42), "PORT DECODE + STROBE GATING")
    S.part("U1", 1, gx(72), gx(22))
    for u, y in ((1, 12), (2, 21), (3, 30), (4, 38)):
        S.part("U2", u, gx(95), gx(y))
    S.text(gx(59), gx(34), "U1: IO-ADDR3 = 1 enables;\nY0 = port 8, Y1 = port 9.\nU2 gate 1: P8 latch clock\n"
           "U2 gate 2: CF -IOR\nU2 gate 3: CF -IOW\nU2 gate 4: unused", size=1.27)

    # --- latch + CF reset ------------------------------------------------------------------------------------------
    S.box(gx(58), gx(43), gx(105), gx(68), "P8 LATCH: DA0-2 + CF RESET")
    S.part("U3", 1, gx(72), gx(56))          # low enough that its VCC arrow clears the group title
    S.part("U4", 2, gx(95), gx(52))
    S.text(gx(86), gx(57), "U4 gate 2: -CFRESET =\n-RESET AND -SRST\n(bus reset or latch bit 3)", size=1.27)

    # --- data buffer + its enable ----------------------------------------------------------------------------------
    S.box(gx(106), gx(5), gx(131), gx(63), "DATA BUFFER")
    S.part("U5", 1, gx(118), gx(17))
    S.part("U4", 1, gx(118), gx(37))
    S.part("U4", 3, gx(118), gx(46))
    S.part("U4", 4, gx(118), gx(54))
    S.text(gx(107), gx(58.5), "DIR = -IOR (low: CF -> bus)\n-CFOE = -IOR AND -IOW\nACTK sinks the ACT LED", size=1.27)

    # --- IDE header, pull-ups, adapter power -----------------------------------------------------------------------
    S.box(gx(132), gx(5), gx(160.5), gx(63), "IDE HEADER J1 (CF-TO-IDE ADAPTER)")
    S.part("J1", 1, gx(142), gx(18), fields={"Reference": (-1.27, -27.94), "Value": (3.81, -27.94)},
           pstub=G)   # short power stubs: a sideways ground clears the label on the next pin (39 -DASP under 37 GND)
    S.part("RN1", 1, gx(142), gx(37))
    for i, r in enumerate(("R1", "R2", "R3", "R4")):
        S.part(r, 1, gx(136 + 3 * i), gx(50))
    S.part("JP1", 1, gx(155), gx(47))
    S.part("J2", 1, gx(155), gx(55))
    S.part("C6", 1, gx(157.5), gx(56))
    S.text(gx(133), gx(59), "CSEL = GND (master)\n-CS0 = GND, -CS1 = VCC", size=1.27)

    # --- LEDs (right, as on the board) -------------------------------------------------------------------------------
    S.box(gx(106), gx(66), gx(160.5), gx(97), "LEDS")
    for i, (r, led, cap) in enumerate((("R7", "LED1", "PWR"), ("R5", "LED2", "ACT: any P9 access"),
                                       ("R6", "LED3", "DASP: CF busy"))):
        x = gx(115 + 16 * i)
        S.part(r, 1, x, gx(73))
        S.part(led, 1, x, gx(80), rot=90)
        S.text(x - gx(3), gx(90), cap, size=1.27)

    # --- power + decoupling ------------------------------------------------------------------------------------------
    S.box(gx(5), gx(54), gx(57), gx(76), "POWER + DECOUPLING (one 100 nF per IC, at its VCC pin)")
    for i, c in enumerate(("C1", "C2", "C3", "C4", "C5")):
        S.part(c, 1, gx(8 + 5 * i), gx(65))
    S.part("U2", 5, gx(35), gx(65))
    S.part("U4", 5, gx(43), gx(65))
    for kind, y in (("VCC", gx(61)), ("GND", gx(69))):
        S.wire(gx(48), y, gx(52), y)
        S.power(kind, gx(48), y, "U" if kind == "VCC" else "D")
        S.power(kind, gx(52), y, "U", flag=True)
    S.text(gx(46), gx(71.5), "PWR_FLAGs: the bus\nsupplies VCC and GND", size=1.27)

    # --- notes -------------------------------------------------------------------------------------------------------
    S.box(gx(5), gx(78), gx(105), gx(112), "DESIGN NOTES")
    S.text(gx(5.5), gx(81), "\n".join([
        "1. Two I/O ports. P8 (write): 74LS175 latch U3 - bits 0-2 = the ATA task-file register (CF DA0-2), bit 3 = CF reset",
        "   (1 = held in reset). P9 (read/write): the selected ATA register, 8-bit True IDE, through the 74LS245 U5.",
        "2. Decode: 74LS138 U1 on IO-ADDR0-2, enabled by IO-ADDR3 (Y0 = port 8, Y1 = port 9). 74LS32 U2 ORs each port select",
        "   with -IO-WR / -IO-RD, so -IOR, -IOW and the latch clock are low only during the bus strobe for this card's port",
        "   (the microcode sets IOADDR two steps before the strobe and holds it through the strobe).",
        "3. -CS0 (J1 pin 37) is tied LOW and -CS1 (pin 38) HIGH: the strobes alone define every cycle. Gating -CS0 with the",
        "   port-9 decode would release it on the same clock edge as -IO-RD at the end of an INP, a gate delay BEFORE -IOR",
        "   rises, breaking the CF chip-select hold time (t9) on the data-register reads that advance its sector buffer.",
        "4. The CF card sits in a commercial CF-to-IDE adapter on the 40-pin header J1. The adapter is powered from J2",
        "   (floppy-style 4-pin: 1 = +5 V, 2 and 3 = GND, 4 = +12 V, not used) or, with JP1 fitted, from IDE pin 20 for",
        "   adapters that take their power there.",
        "5. Pull-ups: CF D0-7 (RN1: an empty adapter reads $FF, which the ROM driver treats as 'no card'), IORDY, -PDIAG,",
        "   -DASP; -DMACK held inactive; CSEL grounded (master).",
        "6. LEDs: PWR; ACT = any port-9 access (the buffer enable); DASP = the CF's own activity/busy pin.",
        "7. SRST (U3 Q3, latch bit 3 true output) is a named net with no other connection (a probe point).",
        "Theory of operation: docs/cards/cf.md. Circuit source: cf_netlist.py (edit it, then re-run build.sh)."]),
        size=1.6)

    # every pin of every part must have been drawn exactly once
    for ref, (value, symid, fpid, note) in N.PARTS.items():
        s = S.lib(SYM_SUB.get(symid, symid))
        want = set(s.units)
        if S.placed[ref] != want:
            raise SystemExit("schematic: %s units placed %s, symbol has %s" % (ref, sorted(S.placed[ref]), sorted(want)))
    missing = [k for k in list(NETOF) + list(NC) if k not in S.pinhits]
    if missing:
        raise SystemExit("schematic: pins not drawn: %s" % missing)
    path = os.path.join(HERE, PROJ + ".kicad_sch")
    S.write(path)
    return S


# ---------------------------------------------------------------------------------------------------------------------
# 3. the board
def schematic_unconnected():
    """(ref, pin) -> KiCad's "unconnected-(...)" net name for every no-connect pin, from a netlist export of the
    sheet just written, so the board's unused pads carry the same names and DRC's schematic-parity check is clean"""
    import tempfile
    net = os.path.join(tempfile.gettempdir(), "_gen_cf_%d.net" % os.getpid())
    kicad_cli("sch", "export", "netlist", "--format", "kicadsexpr", "-o", net, os.path.join(HERE, PROJ + ".kicad_sch"))
    text = open(net).read()
    os.remove(net)
    out = {}
    for name, body in re.findall(r'\(name "(unconnected-\([^"]*\))"\)(.*?)\n\t\t\)', text, re.S):
        nodes = re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', body)
        assert len(nodes) == 1, name
        out[nodes[0]] = name
    return out


def build_board(first_unit_uuid, unconnected):
    import pcbnew
    from pcbnew import VECTOR2I
    FM = pcbnew.FromMM

    def P(x, y):
        return VECTOR2I(FM(x), FM(y))

    # Start from a copy of the blank V3.2 card, stripped at the text level (KiCad 10's SWIG layer stops iterating board
    # containers after a Remove(), so nothing is removed through pcbnew): keep the outline, layer setup and the site
    # text; drop the tracks, the three footprints (X1 comes back from the local library at the same place) and the
    # card-name / stray "0" texts.
    src = open(os.path.join(BLANK, "blank-card-v3.2.kicad_pcb")).read()
    keep, x1at = [], None
    for form in top_forms(src):
        kind = re.match(r"\((\w+)", form).group(1)
        if kind == "footprint":
            if '"Reference" "X1"' in form:
                x1at = [float(v) for v in re.search(r'\(footprint "[^"]*"\s*\(layer "F.Cu"\)\s*\(uuid "[^"]*"\)\s*'
                                                     r'\(at ([-\d.]+) ([-\d.]+) ?([-\d.]*)\)', form).groups() if v]
            continue
        if kind in ("segment", "via", "arc", "zone"):
            continue
        if kind == "gr_text" and "onepagecomputer.com" not in form:
            continue
        keep.append(form)
    assert x1at, "blank card: X1 not found"
    out = os.path.join(HERE, PROJ + ".kicad_pcb")
    open(out, "w").write("(kicad_pcb\n\t" + "\n\t".join(keep) + "\n)\n")
    b = pcbnew.LoadBoard(out)
    edges = [d for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    xs = [pcbnew.ToMM(p.x) for d in edges for p in (d.GetStart(), d.GetEnd())]
    ys = [pcbnew.ToMM(p.y) for d in edges for p in (d.GetStart(), d.GetEnd())]
    BX0, BX1, BY0, BY1 = min(xs), max(xs), min(ys), max(ys)

    nets = {}

    def net(name):
        if name not in nets:
            ni = pcbnew.NETINFO_ITEM(b, name)
            b.Add(ni)
            nets[name] = ni
        return nets[name]

    fps = {}
    for ref, (value, symid, fpid, note) in N.PARTS.items():
        lib, name = fpid.split(":")
        libdir = os.path.join(HERE, lib + ".pretty") if lib == LIB else os.path.join(KFP, lib + ".pretty")
        fp = pcbnew.FootprintLoad(libdir, name)
        if fp is None:
            raise SystemExit("board: footprint %s not found" % fpid)
        fp.SetFPIDAsString(fpid)
        fp.SetReference(ref)
        fp.SetValue(value)
        fp.SetPath(pcbnew.KIID_PATH("/" + first_unit_uuid[ref]))
        try:
            fp.SetSheetname("/")
            fp.SetSheetfile(PROJ + ".kicad_sch")
        except AttributeError:
            pass
        b.Add(fp)
        fps[ref] = fp

    def place(ref, x, y, rot=0):
        fp = fps[ref]
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(P(x, y))

    fps["X1"].SetOrientationDegrees(x1at[2] if len(x1at) > 2 else 0)
    fps["X1"].SetPosition(P(x1at[0], x1at[1]))

    # --- placement (footprint origin = pad 1 for every KiCad THT part used here) ---------------------------------------
    TOP = 52.0                                    # the IC row: pin 1 of every IC on this line
    for i, (u, c) in enumerate((("U1", "C1"), ("U2", "C2"), ("U3", "C3"), ("U4", "C4"), ("U5", "C5"))):
        x = 42.0 + 17.0 * i
        place(u, x, TOP)
        place(c, x + 7.62 + 3.3, TOP, 270)        # the 100 nF: pad 1 (VCC) level with the VCC pin, pad 2 below it
    J1X, J1Y = 160.0, 35.0
    place("J1", J1X, J1Y)                         # pin 1 top left; odd pins left column, even right
    place("RN1", 146.0, 34.0, 270)                # common pin 1 at the top, CFD0..7 downwards beside J1's data pins
    for i, r in enumerate(("R1", "R2", "R3", "R4")):
        place(r, 138.0, 63.0 + 5.08 * i)          # the status pull-ups: VCC end left, J1 end right
    place("JP1", 172.0, J1Y + 9 * 2.54 - 1.27)    # beside J1 pin 20
    place("J2", 145.0, 100.0, 90)                 # adapter power: pin 1 (+5 V) left
    place("C6", 158.0, 100.0)                     # bulk cap beside J2
    for ref_r, ref_l, y in (("R7", "LED1", 96.0), ("R5", "LED2", 106.0), ("R6", "LED3", 116.0)):
        place(ref_r, 172.0, y)                    # VCC end left
        place(ref_l, 191.5, y, 180)               # cathode (pad 1) at the edge side, anode towards its resistor

    # --- nets --------------------------------------------------------------------------------------------------------
    for (ref, pin), nname in unconnected.items():   # the schematic's own names for its no-connect pins (DRC parity)
        for p in fps[ref].Pads():
            if p.GetNumber() == pin:
                p.SetNet(net(nname))
    bad = []
    for nname, conns in N.NETS.items():
        ni = net(nname if nname in POWER_NETS else "/" + nname)   # the names the schematic gives its label nets
        for ref, pin in conns:
            hit = [p for p in fps[ref].Pads() if p.GetNumber() == pin]
            if len(hit) != 1:
                bad.append("%s.%s" % (ref, pin))
            for p in hit:
                p.SetNet(ni)
    if bad:
        raise SystemExit("board: pads not found: %s" % bad)

    # --- copper: GND pours both layers, keepouts round the DIN screws ----------------------------------------------------
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(b)
        z.SetLayer(layer)
        z.SetNet(nets["GND"])
        z.SetLocalClearance(FM(0.3))
        z.SetMinThickness(FM(0.25))
        z.SetThermalReliefGap(FM(0.5))
        z.SetThermalReliefSpokeWidth(FM(0.5))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        o = z.Outline()
        o.NewOutline()
        for x, y in ((BX0, BY0), (BX1, BY0), (BX1, BY1), (BX0, BY1)):
            o.Append(FM(x), FM(y))
        b.Add(z)
    import math
    for p in fps["X1"].Pads():
        if p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            continue
        cx, cy = pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)
        z = pcbnew.ZONE(b)
        ls = pcbnew.LSET()
        ls.AddLayer(pcbnew.F_Cu)
        ls.AddLayer(pcbnew.B_Cu)
        z.SetLayerSet(ls)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowZoneFills(True)
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
        o = z.Outline()
        o.NewOutline()
        for i in range(32):
            a = 2 * math.pi * i / 32
            o.Append(FM(cx + 4.0 * math.cos(a)), FM(cy + 4.0 * math.sin(a)))
        b.Add(z)

    # --- silkscreen --------------------------------------------------------------------------------------------------
    def silk(s, x, y, size=1.2, angle=0, just=pcbnew.GR_TEXT_H_ALIGN_CENTER):
        t = pcbnew.PCB_TEXT(b)
        t.SetText(s)
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(VECTOR2I(FM(size), FM(size)))
        t.SetTextThickness(FM(max(0.15, size * 0.15)))
        t.SetHorizJustify(just)
        t.SetTextAngleDegrees(angle)
        t.SetPosition(P(x, y))
        b.Add(t)

    def field(fld, x, y, size=1.0, angle=0, layer=None):
        fld.SetVisible(True)
        fld.SetLayer(layer if layer is not None else pcbnew.F_SilkS)
        fld.SetTextSize(VECTOR2I(FM(size), FM(size)))
        fld.SetTextThickness(FM(0.15))
        fld.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        fld.SetTextAngleDegrees(angle)
        fld.SetPosition(P(x, y))

    for ref, fp in fps.items():
        pos = fp.GetPosition()
        x, y = pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y)
        if ref.startswith("U"):
            npins = len(fp.Pads())
            h = (npins // 2 - 1) * 2.54
            field(fp.Reference(), x + 3.81, y - 2.6)
            field(fp.Value(), x + 3.81, y + h / 2, 1.0, 90)
        elif ref in ("C1", "C2", "C3", "C4", "C5"):
            field(fp.Reference(), x, y - 2.3, 0.9)
            field(fp.Value(), x + 2.4, y + 2.5, 0.8, 90)
        elif ref in ("R1", "R2", "R3", "R4"):
            fld_l = fp.Reference(); field(fld_l, x - 3.4, y, 0.9)
            field(fp.Value(), x + 13.4, y, 0.9)
        elif ref.startswith("R") and ref != "RN1":
            field(fp.Reference(), x + 5.08, y - 2.2, 0.9)
            field(fp.Value(), x + 5.08, y + 2.2, 0.9)
        elif ref.startswith("LED"):
            field(fp.Reference(), x - 1.27, y + 4.3, 0.9)
            field(fp.Value(), x - 1.27, y - 4.2, 0.8, layer=pcbnew.F_Fab)
    field(fps["RN1"].Reference(), 146.0 - 3.0, 34.0 + 10.16, 1.0, 90)
    field(fps["RN1"].Value(), 146.0 + 2.8, 34.0 + 10.16, 0.9, 90)
    field(fps["J1"].Reference(), J1X + 1.27, J1Y - 6.0, 1.2)
    field(fps["J1"].Value(), J1X + 1.27, J1Y + 55.5, 1.0)
    silk("1", J1X - 5.3, J1Y, 1.2)
    silk("IDE 40 (CF adapter)", J1X + 1.27, J1Y - 8.2, 1.0)
    field(fps["JP1"].Reference(), 172.0, J1Y + 9 * 2.54 - 4.2, 1.0)
    field(fps["JP1"].Value(), 172.0 + 5.2, J1Y + 9 * 2.54, 0.8, 90)
    field(fps["J2"].Reference(), 145.0 + 3.81, 100.0 - 3.0, 1.0)
    field(fps["J2"].Value(), 145.0 + 3.81, 100.0 + 3.0, 0.9)
    silk("+5 GND GND nc", 145.0 + 3.81, 100.0 + 5.0, 0.8)
    field(fps["C6"].Reference(), 158.0 + 1.0, 100.0 - 4.0, 0.9)
    field(fps["C6"].Value(), 158.0 + 1.0, 100.0 + 4.0, 0.9)
    field(fps["X1"].Reference(), 33.0, 20.0, 1.2)
    fps["X1"].Value().SetVisible(False)
    for ref_l, lab, y in (("LED1", "PWR", 96.0), ("LED2", "ACT", 106.0), ("LED3", "DASP", 116.0)):
        silk(lab, 184.8, y - 2.7, 1.1)
    silk("YACC1 CF card v1.0", 100.0, 16.0, 2.5)
    silk("CompactFlash / True IDE on ports P8 (latch) + P9 (data)   %s" % N.DATE, 100.0, 20.5, 1.1)
    silk("GND pour both sides; VCC on 0.6 mm tracks", 100.0, 118.5, 0.9)

    pcbnew.SaveBoard(out, b)
    return out, (BX1 - BX0, BY1 - BY0), len(fps)


# ---------------------------------------------------------------------------------------------------------------------
# 4. the project file (after SaveBoard, which may write its own)
def write_project(root_uuid):
    pro = json.load(open(os.path.join(ROOT, "tools", "kicad", "project-template.kicad_pro")))
    ds = pro["board"]["design_settings"]
    ds["rules"].update({
        "min_clearance": 0.25, "min_track_width": 0.25, "min_copper_edge_clearance": 0.5,
        "min_hole_clearance": 0.25, "min_hole_to_hole": 0.25, "min_through_hole_diameter": 0.3,
        "min_via_annular_width": 0.15, "min_via_diameter": 0.6, "min_text_height": 0.8,
        "min_text_thickness": 0.12})
    ds["rule_severities"]["footprint_symbol_field_mismatch"] = "ignore"
    ds["track_widths"] = [0.0, 0.3, 0.6, 1.0]
    ds["via_dimensions"] = [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.8, "drill": 0.4},
                            {"diameter": 1.0, "drill": 0.5}]
    classes = pro["net_settings"]["classes"]
    d = classes[0]
    d.update({"clearance": 0.25, "track_width": 0.3, "via_diameter": 0.8, "via_drill": 0.4})
    pw = dict(d)
    pw.update({"name": "Power", "clearance": 0.3, "track_width": 0.6, "via_diameter": 1.0, "via_drill": 0.5,
               "priority": 0})
    pro["net_settings"]["classes"] = [d, pw]
    pro["net_settings"]["netclass_patterns"] = [{"netclass": "Power", "pattern": "VCC"},
                                                {"netclass": "Power", "pattern": "GND"},
                                                {"netclass": "Power", "pattern": "/PIN20"}]
    pro["meta"]["filename"] = PROJ + ".kicad_pro"
    pro["sheets"] = [[root_uuid, "Root"]]
    json.dump(pro, open(os.path.join(HERE, PROJ + ".kicad_pro"), "w"), indent=2)


def main():
    probs = N.check()
    if probs:
        raise SystemExit("cf_netlist.check() failed:\n" + "\n".join(probs))
    write_local_libs()
    S = build_schematic()
    # let KiCad re-save the sheet in its own canonical format (also proves it loads)
    kicad_cli("sch", "upgrade", "--force", os.path.join(HERE, PROJ + ".kicad_sch"))
    print("schematic: %s (%d symbols embedded, %d power symbols, %d flags)" % (PROJ + ".kicad_sch", len(S.syms),
                                                                               S.pwr, S.flg))
    out, (w, h), n = build_board(S.first_unit_uuid, schematic_unconnected())
    write_project(ROOT_UUID)
    print("board: %s (%.2f x %.2f mm, %d footprints, unrouted)" % (os.path.basename(out), w, h, n))


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)                                          # skip the wx exit hang (everything is saved)
