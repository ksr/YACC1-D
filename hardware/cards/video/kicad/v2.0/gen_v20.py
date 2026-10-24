#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""gen_v20.py - the YACC1 video card V2.0 (2026-10-22): the schematic, the project rules and the unrouted 4-layer board,
all from v20_netlist.py (the circuit); build.sh routes and checks it. Design note: BACKLOG.md "Video card V2.0".

The schematic is drawn by the CF card's sheet writer (hardware/cards/cf/kicad/v1.0/gen_cf.py: every pin a short stub to
a net label or a power symbol, no-connect flags, functional boxes) on one A0 sheet; parts KiCad has no symbol for
(IDT7134, the RCA jack, the DB9 and the Mini-DIN with their shields) are drawn into the local library
video-v2.0-local, with the Mini-DIN footprint drawn from the Same Sky MD-60SM data sheet (minidin_footprint()). The board: the blank V3.2 card's X1 and outline lengthened to 218 mm (the sequencer logic V2.1l's
length: x 17.747..236.167), 4 layers (In1.Cu GND plane, In2.Cu VCC plane, as the v1.3 and memory v2.0 boards), every
part placed here, every pad on its schematic net, keepouts round X1's two screws.

Run with KiCad's bundled Python (pcbnew), from this folder:
  gen_v20.py sch                          -> local libraries + video-v2.0.kicad_sch (+ the netlist check against
                                             v20_netlist.py)
  gen_v20.py project                      -> video-v2.0.kicad_pro + .kicad_dru (signals 0.25 mm / 0.2 mm, vias 0.8/0.4;
                                             class Power = GND, VCC: planes, never routed)
  gen_v20.py board <netlist> <out.pcb>    -> the unrouted board
  gen_v20.py place <pcb>                  -> the placement check: courtyards apart, everything inside the outline, the
                                             DIP sockets' outlines clear of each other and of the other parts
  gen_v20.py silk <pcb> [out]             -> the silkscreen texts placed clear (board() does it on every new board)
  gen_v20.py dsn|shuffle|ses|stats ...    -> as gen_v13.py (Specctra export/import, Freerouting seeds, route stats)
  gen_v20.py verify <netlist> <pcb>       -> the key connections pin by pin (schematic and board), layers, planes
  gen_v20.py bom                          -> BOM.md: the bill of materials from v20_netlist.PARTS and BUY (plain Python)
"""
import os, sys, re, json, uuid, shutil, subprocess, collections, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
CFDIR = os.path.join(ROOT, "hardware", "cards", "cf", "kicad", "v1.0")
V13DIR = os.path.join(HERE, "..", "v1.3")
sys.path.insert(0, HERE)
sys.path.insert(0, CFDIR)
import v20_netlist as N                                    # noqa: E402
import gen_cf                                              # noqa: E402  (the CF card's sheet writer, reused read-only)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


G13 = _load(os.path.join(V13DIR, "gen_v13.py"), "gen_v13")   # dsn / shuffle / ses / stats / refill / plane
P = "video-v2.0"
CLI = gen_cf.CLI
KFP = gen_cf.KFP
LOCAL = N.LOCAL
G = 2.54
X0, X1R, Y0, Y1B = 17.747, 236.167, 10.025, 123.995      # the outline: the blank card lengthened to 218.42 mm
gen_cf.N = N
gen_cf.NETOF = {(r, p): n for n, conns in N.NETS.items() for r, p in conns}
gen_cf.NC = {(r, p) for r, ps in N.NO_CONNECT.items() for p in ps}
gen_cf.PROJ = P
gen_cf.ROOT_UUID = gen_cf.U("video-v2.0", "root")


# ---------------------------------------------------------------------------------------------------------------------
# 1. local libraries
def pin_line(num, name, etype, x, y, ang, length=2.54):
    eff = "(effects (font (size 1.27 1.27)))"
    return ('\t\t\t(pin %s line (at %s %s %d) (length %s) (name %s %s) (number %s %s))'
            % (etype, gen_cf.f(x), gen_cf.f(y), ang, gen_cf.f(length), gen_cf.q(name), eff, gen_cf.q(num), eff))


def box_symbol(name, ref, desc, left=(), right=(), top=(), bottom=(), width=None):
    """a rectangle with pins on its sides; each side a list of (number, name, type)"""
    L = 2.54
    rows = max(len(left), len(right), 1)
    h = rows * G + G
    w = width or max(15.24, 2.54 * (max(len(top), len(bottom), 1) + 1))
    w = round(w / G) * G
    eff = "(effects (font (size 1.27 1.27)))"
    hid = "(effects (font (size 1.27 1.27)) (hide yes))"
    out = ['\t(symbol "%s"' % name, '\t\t(pin_names (offset 0.762))', '\t\t(exclude_from_sim no) (in_bom yes) (on_board yes)',
           '\t\t(property "Reference" "%s" (at 0 %s 0) %s)' % (ref, gen_cf.f(h / 2 + L + 2.54), eff),
           '\t\t(property "Value" "%s" (at 0 %s 0) %s)' % (name, gen_cf.f(-(h / 2 + L + 2.54)), eff),
           '\t\t(property "Footprint" "" (at 0 0 0) %s)' % hid,
           '\t\t(property "Datasheet" "" (at 0 0 0) %s)' % hid,
           '\t\t(property "Description" %s (at 0 0 0) %s)' % (gen_cf.q(desc), hid),
           '\t\t(symbol "%s_0_1"' % name,
           '\t\t\t(rectangle (start %s %s) (end %s %s) (stroke (width 0.254) (type default)) (fill (type background)))'
           % (gen_cf.f(-w / 2), gen_cf.f(h / 2), gen_cf.f(w / 2), gen_cf.f(-h / 2)), '\t\t)',
           '\t\t(symbol "%s_1_1"' % name]
    y0 = h / 2 - G
    for i, (num, pn, et) in enumerate(left):
        out.append(pin_line(num, pn, et, -w / 2 - L, y0 - i * G, 0))
    for i, (num, pn, et) in enumerate(right):
        out.append(pin_line(num, pn, et, w / 2 + L, y0 - i * G, 180))
    for i, (num, pn, et) in enumerate(top):
        out.append(pin_line(num, pn, et, -w / 2 + G + i * G, h / 2 + L, 270))
    for i, (num, pn, et) in enumerate(bottom):
        out.append(pin_line(num, pn, et, -w / 2 + G + i * G, -h / 2 - L, 90))
    out += ['\t\t)', '\t\t(embedded_fonts no)', '\t)']
    return "\n".join(out)


def local_symbols():
    io, inp, pas, pw, tri = "bidirectional", "input", "passive", "power_in", "tri_state"
    s7134 = box_symbol(
        "IDT7134", "IC", "IDT7134 4K x 8 dual-port static RAM, DIL48 (the V1.x card's IC15)",
        left=[(str(p), "A%dL" % i, inp) for i, p in enumerate((6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 4, 3))] +
             [(str(16 + i), "I/O%dL" % i, io) for i in range(8)] +
             [("1", "~{CEL}", inp), ("2", "R/~{WL}", inp), ("5", "~{OEL}", inp)],
        right=[(str(p), "A%dR" % i, inp) for i, p in enumerate((42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 44, 45))] +
              [(str(25 + i), "I/O%dR" % i, io) for i in range(8)] +
              [("47", "~{CER}", inp), ("46", "R/~{WR}", inp), ("43", "~{OER}", inp)],
        top=[("48", "VCC", pw)], bottom=[("24", "GND", pw)], width=22.86)
    rca = box_symbol("RCA", "J", "RCA (phono) jack: C1 centre, S1-S3 the shell's three tags",
                     left=[("C1", "C", pas)], right=[("S1", "S", pas), ("S2", "S", pas), ("S3", "S", pas)], width=10.16)
    de9 = box_symbol("DE9_SHIELD", "X", "DE-9 female, right angle, with its two shell (mounting) tags G1/G2",
                     left=[(str(i), str(i), pas) for i in range(1, 10)], right=[("G1", "SHELL", pas), ("G2", "SHELL", pas)],
                     width=12.7)
    mdin = box_symbol("MINIDIN6", "J", "Mini-DIN-6 female (PS/2): 1 data, 3 GND, 4 +5V, 5 clock, 2/6 unused; S = shell",
                      left=[(str(i), ("DATA", "nc", "GND", "+5V", "CLK", "nc")[i - 1], pas) for i in range(1, 7)],
                      right=[("S", "SHELL", pas)], width=12.7)
    text = "\n".join(['(kicad_symbol_lib', '\t(version 20251024)', '\t(generator "gen_v20")', '\t(generator_version "1.0")',
                      s7134, rca, de9, mdin, ')', ''])
    path = os.path.join(HERE, LOCAL + ".kicad_sym")
    open(path, "w").write(text)
    gen_cf.kicad_cli("sym", "upgrade", "--force", path)


# The Mini-DIN-6 jack J2 / J3: Same Sky (formerly CUI Devices) MD-60SM, drawn 2026-10-22 from its data sheet "SERIES:
# MD-SM", rev 1.09 of 2024-09-12, page 3, "Recommended PCB Layout, Top View (Date Codes after 03/03/2022)" (the layout
# of the current production; the earlier date codes had another pattern). Datum: the mating face (the front of the
# housing), which this footprint puts at x = 0 with the opening towards +x; the drawing's dimensions are from it:
#   signal pins 6 x dia 0.9 +0.1/-0: pins 4, 2, 1, 3 in a row 8.5 behind the face at 6.8 / 2.6 mm spacing
#   (+-3.4, +-1.3 about the centre line), pins 6, 5 11.0 behind it at +-3.4;
#   the earth terminal: a 2.2 x 0.7 (+0.1/-0) slot, centre 4.7 behind the face, on the centre line;
#   the shield's two side legs: slots 13.5 apart, centres 5.5 behind the face (drawn like the earth slot, 0.7 x 2.2,
#   long side front-to-back; the legs are 0.54 thick);
#   body 14.0 wide, 13.0 deep, 12.8 high.
# The drawing is a top (component-side) view, as this footprint: looking into the jack, pins 6 / 4 / 2 are on the left,
# which is +y here - the PS/2 face numbering (1 data, 3 GND, 4 +5 V, 5 clock). Drills 1.0, the earth slot 0.8 x 2.3 mm
# and the side-leg slots 1.2 x 2.6 mm (R2-1), plated: the shell and the earth terminal are on GND (pad S).
MINIDIN_PADS = [("1", -8.5, -1.3), ("2", -8.5, 1.3), ("3", -8.5, -3.4), ("4", -8.5, 3.4), ("5", -11.0, -3.4),
                ("6", -11.0, 3.4)]
# R2-1 (2026-10-23): the side-leg slots 2.6 x 1.2 (pads 3.3 x 1.9) for the data sheet's 0.54 mm legs 13.2 mm apart
# (0.8 mm left 0.01 mm at the outer face); centres unchanged. The earth slot stays 0.8 x 2.3.
MINIDIN_SLOTS = [(-4.7, 0.0, 0.8, 2.3), (-5.5, -6.75, 2.6, 1.2), (-5.5, 6.75, 2.6, 1.2)]   # (x, y, drill x, drill y)


def minidin_footprint():
    """Same Sky MD-60SM, a right-angle PCB Mini-DIN-6 (PS/2) jack: the mating face at x = 0, the opening towards +x"""
    L = ['(footprint "MiniDIN6_MD-60SM"', '\t(version 20241229)', '\t(generator "gen_v20")', '\t(layer "F.Cu")',
         '\t(descr "Mini-DIN-6 (PS/2) right-angle PCB jack Same Sky (CUI) MD-60SM, data sheet MD-SM rev 1.09 '
         '2024-09-12, PCB layout for date codes after 03/03/2022; mating face at x = 0, opening towards +x '
         '(YACC1 video V2.0)")', '\t(attr through_hole)',
         '\t(property "Reference" "REF**" (at -6.5 -8.2 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
         '\t(property "Value" "MD-60SM" (at -6.5 8.2 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
         '\t(fp_rect (start -13.25 -7.25) (end 0.25 7.25) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))',
         '\t(fp_rect (start -13.0 -7.0) (end 0 7.0) (stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab"))',
         '\t(fp_line (start 0 -4.0) (end 0 4.0) (stroke (width 0.3) (type solid)) (layer "F.Fab"))']
    # the body outline on the silk (R2-9): the back and the two sides, broken round the side-leg pads (they stand across
    # the body's sides) and stopped 0.5 mm short of the mating face, which lies on the board edge
    lx, ly, ldx, ldy = MINIDIN_SLOTS[1]                     # a side-leg slot; its pad is ldx + 0.7 long
    g0, g1 = lx - (ldx + 0.7) / 2 - 0.25, lx + (ldx + 0.7) / 2 + 0.25
    segs = [((-13.0, -7.0), (-13.0, 7.0))]
    for s in (-7.0, 7.0):
        segs += [((-13.0, s), (g0, s)), ((g1, s), (-0.5, s))]
    for (ax, ay), (bx, by) in segs:
        L.append('\t(fp_line (start %s %s) (end %s %s) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))'
                 % (gen_cf.f(ax), gen_cf.f(ay), gen_cf.f(bx), gen_cf.f(by)))
    for num, x, y in MINIDIN_PADS:
        L.append('\t(pad "%s" thru_hole circle (at %s %s) (size 1.6 1.6) (drill 1.0) (layers "*.Cu" "*.Mask"))'
                 % (num, gen_cf.f(x), gen_cf.f(y)))
    for x, y, dx, dy in MINIDIN_SLOTS:
        L.append('\t(pad "S" thru_hole oval (at %s %s) (size %s %s) (drill oval %s %s) (layers "*.Cu" "*.Mask"))'
                 % (gen_cf.f(x), gen_cf.f(y), gen_cf.f(dx + 0.7), gen_cf.f(dy + 0.7), gen_cf.f(dx), gen_cf.f(dy)))
    L += ['\t(embedded_fonts no)', ')', '']
    return "\n".join(L)


def local_libs():
    for ext in (".kicad_sym",):
        shutil.copy(os.path.join(CFDIR, N.BUSLIB + ext), os.path.join(HERE, N.BUSLIB + ext))
    for lib in (N.BUSLIB, LOCAL):
        d = os.path.join(HERE, lib + ".pretty")
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)
    shutil.copy(os.path.join(CFDIR, N.BUSLIB + ".pretty", "FABC96R.kicad_mod"), os.path.join(HERE, N.BUSLIB + ".pretty"))
    v13p = os.path.join(V13DIR, "video-v1.3-eagle.pretty")
    for fp in ("F09HP", "RCA"):
        shutil.copy(os.path.join(v13p, fp + ".kicad_mod"), os.path.join(HERE, LOCAL + ".pretty"))
    open(os.path.join(HERE, LOCAL + ".pretty", "MiniDIN6_MD-60SM.kicad_mod"), "w").write(minidin_footprint())
    local_symbols()
    open(os.path.join(HERE, "sym-lib-table"), "w").write(
        '(sym_lib_table\n\t(version 7)\n'
        '\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.kicad_sym")(options "")(descr "YACC1 bus connector, three rows"))\n'
        '\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.kicad_sym")(options "")(descr "IDT7134, RCA, DB9, Mini-DIN (gen_v20.py)"))\n'
        ')\n' % (N.BUSLIB, N.BUSLIB, LOCAL, LOCAL))
    open(os.path.join(HERE, "fp-lib-table"), "w").write(
        '(fp_lib_table\n\t(version 7)\n'
        '\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.pretty")(options "")(descr "FABC96R from the blank V3.2 card"))\n'
        '\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.pretty")(options "")(descr "F09HP, RCA from the V1.x card; MiniDIN6_MD-60SM (gen_v20.py)"))\n'
        ')\n' % (N.BUSLIB, N.BUSLIB, LOCAL, LOCAL))


_libtext = {}


def std_symbol(libid):
    lib, name = libid.split(":")
    path = os.path.join(HERE, lib + ".kicad_sym") if lib in (N.BUSLIB, LOCAL) else os.path.join(gen_cf.KSYM, lib + ".kicad_sym")
    if path not in _libtext:
        _libtext[path] = open(path).read()
    return gen_cf.LibSym(libid, gen_cf.lib_block(_libtext[path], name))


gen_cf.std_symbol = std_symbol


# ---------------------------------------------------------------------------------------------------------------------
# 2. the schematic: every part's units flowed into functional boxes on one A0 sheet
class Sheet(gen_cf.Sheet):
    def write(self, path):
        head = ['(kicad_sch', '\t(version 20260306)', '\t(generator "gen_v20")', '\t(generator_version "1.0")',
                '\t(uuid "%s")' % gen_cf.ROOT_UUID, '\t(paper "A0")',
                '\t(title_block (title "YACC1 video card V2.0") (date "%s") (rev "%s") (company "YACC1")' % (N.DATE, N.REV),
                '\t\t(comment 1 "Text + graphics (8-dot mode), 6845 and every register on ports PA-PE, PS/2 keyboard and mouse")',
                '\t\t(comment 2 "Circuit source: v20_netlist.py; this sheet is generated by gen_v20.py")',
                '\t\t(comment 3 "Design note: BACKLOG.md Video card V2.0; theory: docs/cards/video.md"))',
                '\t(lib_symbols']
        for libid in sorted(self.syms):
            head.append(self.syms[libid].text)
        head.append('\t)')
        tail = ['\t(sheet_instances (path "/" (page "1")))', '\t(embedded_fonts no)', ')', '']
        open(path, "w").write("\n".join(head + self.out + tail))


def unit_extent(S, ref, unit):
    """(x0, y0, x1, y1) of a unit drawn at (0, 0): body, pin stubs and their labels (sheet mm, y down)"""
    value, symid, fpid, note = N.PARTS[ref]
    s = S.lib(gen_cf.SYM_SUB.get(symid, symid))
    b = s.unit_body(unit) or (-2.54, -2.54, 2.54, 2.54)
    xs, ys = [b[0], b[2]], [-b[1], -b[3]]
    for p in s.unit_pins(unit):
        px, py = p["x"], -p["y"]
        dx, dy = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}[(p["ang"] + 180) % 360]
        net = gen_cf.NETOF.get((ref, p["num"]), "")
        ln = 2 * G + (6 if net in ("VCC", "GND") else 1.0 * len(net) + 2)
        xs += [px, px + dx * ln]; ys += [py, py + dy * ln]
    return min(xs) - 2, min(ys) - 4, max(xs) + 2, max(ys) + 3


# functional groups: (title, box x0, y0, x1, y1 in mm, [(ref, unit), ...])
def groups(S):
    def units(ref):
        s = S.lib(gen_cf.SYM_SUB.get(N.PARTS[ref][1], N.PARTS[ref][1]))
        return list(s.units)
    pw = lambda ref: units(ref)[-1]                       # the 74xx power unit is the last
    gate = lambda ref, *u: [(ref, k) for k in u]
    G1 = [("X1", 1), ("X1", 2), ("X1", 3)]
    G2 = [("IC18", 1), ("SV3", 1), ("RN2", 1)] + gate("IC20", 5, 6) + gate("IC19", 2) + [("IC15", 1)]
    G3 = [("IC17", 1), ("IC30", 1)] + gate("IC31", 1, 2, 3, 4) + gate("IC32", 1) + gate("IC1", 1) + gate("IC26", 3) + \
         [("IC33", 1), ("IC34", 1), ("R27", 1)]
    G4 = [("Q2", 1), ("R8", 1), ("R9", 1)] + gate("IC20", 1, 2, 3, 4) + [("IC21", 1), ("SV4", 1), ("IC28", 1), ("R10", 1),
         ("JP2", 1), ("R15", 1)] + gate("IC19", 3) + [("IC23", 1), ("IC25", 1), ("IC24", 1), ("IC22", 1)] + gate("IC26", 1, 2)
    G5 = [("IC35", 1), ("IC36", 1), ("IC37", 1), ("IC38", 1), ("IC39", 1), ("RN3", 1), ("IC40", 1), ("IC41", 1),
          ("IC55", 1), ("IC42", 1), ("IC43", 1), ("R25", 1)] + gate("IC44", 1, 2) + [("R26", 1)] + gate("IC45", 1, 2) + \
         gate("IC46", 1, 2, 3, 6) + gate("IC47", 2, 3) + gate("IC1", 2) + gate("IC19", 1, 4) + gate("IC26", 4) + \
         gate("IC32", 3, 4) + gate("IC48", 3) + gate("IC54", 1, 3, 4)
    G6 = gate("IC1", 3, 4) + gate("IC47", 1) + gate("IC46", 4, 5) + gate("IC32", 2) + gate("IC48", 1, 2) + \
         gate("IC27", 1, 2, 3) + [("R11", 1), ("R12", 1), ("X2", 1), ("J1", 1), ("R2", 1), ("LED1", 1)]
    G7 = [("IC49", 1), ("Y1", 1), ("C55", 1), ("C56", 1), ("R16", 1), ("C57", 1), ("R21", 1)] + gate("IC27", 5, 6) + \
         [("J4", 1), ("F1", 1), ("J2", 1), ("J3", 1), ("R17", 1), ("R18", 1), ("R19", 1), ("R20", 1), ("R22", 1),
          ("R23", 1), ("R24", 1), ("IC50", 1), ("IC51", 1), ("IC52", 1)] + \
         gate("IC53", 1, 2) + gate("IC47", 4) + gate("IC54", 2) + gate("IC27", 4) + [("JP3", 1)]
    pwr = []
    for ref in sorted(N.PARTS, key=lambda r: (len(r), r)):
        if ref.startswith("IC") and len(units(ref)) > 1:
            pwr.append((ref, pw(ref)))
    G8 = pwr + [(c, 1) for c in sorted(N.DECOUPLE, key=lambda r: int(r[1:]))] + [("C16", 1)]
    return [("BUS  X1  DIN 41612 (YACC1 V3.2)", 10, 25, 200, 245, G1),
            ("BOARD SELECT ($D000 BLOCK) + TEXT RAM $D000-$D7FF", 205, 25, 420, 245, G2),
            ("PORTS PA-PE: 6845 (PA/PB), CONTROL + STATUS (PC)", 425, 25, 830, 245, G3),
            ("CLOCKS + CHARACTER PIPELINE (DOTS: 6 OR 8 DOTS A CHARACTER)", 10, 250, 330, 580, G4),
            ("GRAPHICS RAM $D800-$DFFF: SLOT LOGIC (GFX-ON = 1) / DIRECT MODE (GFX-ON = 0)", 335, 250, 620, 820, G5),
            ("DOT COMBINE + VIDEO OUT", 625, 250, 830, 400, G6),
            ("PS/2: ATMEGA328P + LATCHES (PD, PE), INT", 625, 405, 830, 820, G7),
            ("POWER UNITS + DECOUPLING", 835, 25, 1180, 820, G8)]


def build_schematic():
    S = Sheet()
    S.pwr = 0
    for title, x0, y0, x1, y1, items in groups(S):
        S.box(x0, y0, x1, y1, title)
        cx, cy, rowh = x0 + 3, y0 + 10, 0
        for ref, unit in items:
            e = unit_extent(S, ref, unit)
            w, h = e[2] - e[0], e[3] - e[1]
            if cx + w > x1 - 2 and cx > x0 + 3:
                cx, cy, rowh = x0 + 3, cy + rowh + 3, 0
            ux = round((cx - e[0]) / G) * G
            uy = round((cy - e[1]) / G) * G
            S.part(ref, unit, ux, uy)
            cx += w + 3
            rowh = max(rowh, h)
        if cy + rowh > y1:
            print("schematic: box '%s' overflows by %.0f mm" % (title, cy + rowh - y1))
    for kind, y in (("VCC", 590), ("GND", 600)):
        S.wire(20, y, 30, y)
        S.power(kind, 20, y, "U" if kind == "VCC" else "D")
        S.power(kind, 30, y, "U", flag=True)
    S.text(40, 586, "PWR_FLAGs: the bus supplies VCC and GND (X1, six pins each).", size=1.5)
    for ref, (value, symid, fpid, note) in N.PARTS.items():
        s = S.lib(gen_cf.SYM_SUB.get(symid, symid))
        if S.placed[ref] != set(s.units):
            raise SystemExit("schematic: %s units placed %s, symbol has %s" % (ref, sorted(S.placed[ref]), s.units))
    missing = [k for k in list(gen_cf.NETOF) + list(gen_cf.NC) if k not in S.pinhits]
    if missing:
        raise SystemExit("schematic: pins not drawn: %s" % missing)
    S.write(os.path.join(HERE, P + ".kicad_sch"))
    return S


def check_schematic_netlist(netfile):
    """the schematic's exported netlist = v20_netlist.NETS (label nets come back as /NAME)"""
    s = open(netfile).read()
    s = s[s.index("(nets"):]
    got = {}
    for blk in re.split(r'\(net\s*\(code', s)[1:]:
        name = re.search(r'\(name "([^"]*)"', blk).group(1)
        if name.startswith("unconnected-"):
            continue
        got[name.lstrip("/")] = set(re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"', blk))
    want = {n: set(v) for n, v in N.NETS.items()}
    bad = [n for n in set(got) | set(want) if got.get(n) != want.get(n)]
    for n in sorted(bad)[:20]:
        print("  net %s: schematic %s, v20_netlist %s" % (n, sorted(got.get(n, ()))[:6], sorted(want.get(n, ()))[:6]))
    print("schematic netlist vs v20_netlist.py: %s (%d nets)" % ("MATCH" if not bad else "%d DIFFER" % len(bad), len(want)))
    return not bad


def sch():
    probs = N.check()
    if probs:
        raise SystemExit("v20_netlist.check():\n" + "\n".join(probs))
    local_libs()
    S = build_schematic()
    gen_cf.kicad_cli("sch", "upgrade", "--force", os.path.join(HERE, P + ".kicad_sch"))
    print("schematic: %s (%d symbols, %d power symbols)" % (P + ".kicad_sch", len(S.syms), S.pwr))


# ---------------------------------------------------------------------------------------------------------------------
# 3. the project rules (as gen_v13.py's) and the board
DRU = G13.DRU.replace("video card v1.3", "video card V2.0").replace("gen_v13.py", "gen_v20.py")


def project():
    pro = json.load(open(os.path.join(ROOT, "tools", "kicad", "project-template.kicad_pro")))
    R = G13.RULES
    ds = pro["board"]["design_settings"]
    ds["rules"].update(min_clearance=R["clearance"], min_track_width=R["track"], min_via_diameter=R["via"],
                       min_through_hole_diameter=R["via_drill"], min_via_annular_width=R["annular"],
                       min_copper_edge_clearance=R["edge"], min_hole_to_hole=R["hole_to_hole"],
                       min_hole_clearance=R["hole_clearance"], min_text_height=0.8, min_text_thickness=0.12)
    ds["rule_severities"]["footprint_symbol_field_mismatch"] = "ignore"
    ds["track_widths"] = [0.0, R["track"]]
    ds["via_dimensions"] = [{"diameter": 0.0, "drill": 0.0}, {"diameter": R["via"], "drill": R["via_drill"]}]
    base = pro["net_settings"]["classes"][0]
    base.update(track_width=R["track"], clearance=R["clearance"], via_diameter=R["via"], via_drill=R["via_drill"])
    power = dict(base, name="Power", priority=0, track_width=0.4)
    pro["net_settings"]["classes"] = [base, power]
    pro["net_settings"]["netclass_patterns"] = [{"netclass": "Power", "pattern": "GND"},
                                                {"netclass": "Power", "pattern": "VCC"}]
    pro["meta"]["filename"] = P + ".kicad_pro"
    pro["sheets"] = [[gen_cf.ROOT_UUID, "Root"]]
    json.dump(pro, open(os.path.join(HERE, P + ".kicad_pro"), "w"), indent=2)
    open(os.path.join(HERE, P + ".kicad_dru"), "w").write(DRU)
    print("project: Default %.2f mm / %.2f mm, vias %.1f / %.1f mm; class Power = GND, VCC (planes)" % (
        R["track"], R["clearance"], R["via"], R["via_drill"]))


# --- placement: (x, y, rotation) of each footprint's origin (pad 1 of every DIP / header / resistor / capacitor) --------
ROW = {"A": 15.0, "B": 45.0, "C": 82.0, "D": 104.0}
COL = lambda k: 100.0 + 14.0 * k                      # the 300-mil columns right of the 600-mil parts
PLACE = {
    # row A (y 15): the port and bus-facing latches, WRQ, the video output
    "IC30": (32, ROW["A"], 0), "IC31": (46, ROW["A"], 0), "IC46": (60, ROW["A"], 0), "IC33": (74, ROW["A"], 0),
    "IC34": (88, ROW["A"], 0), "IC52": (102, ROW["A"], 0), "IC50": (116, ROW["A"], 0), "IC51": (130, ROW["A"], 0),
    "IC41": (144, ROW["A"], 0), "IC40": (158, ROW["A"], 0), "IC44": (172, ROW["A"], 0), "IC27": (186, ROW["A"], 0),
    # rows B-D, left: the 600-mil parts and the board select
    "IC15": (32, ROW["B"], 0), "IC17": (55, ROW["B"], 0), "IC39": (78, ROW["B"], 0), "IC25": (78, ROW["C"], 0),
    "IC18": (55, ROW["D"], 0),
    # row B: graphics address muxes, display latch and shifter, the ATmega
    "IC35": (COL(0), ROW["B"], 0), "IC36": (COL(1), ROW["B"], 0), "IC37": (COL(2), ROW["B"], 0),
    "IC38": (COL(3), ROW["B"], 0), "IC42": (COL(4), ROW["B"], 0), "IC43": (COL(5), ROW["B"], 0),
    "IC49": (199, ROW["B"], 0),
    # row C: the text pipeline and the gates
    "IC23": (COL(0), ROW["C"], 0), "IC24": (COL(1), ROW["C"], 0), "IC22": (COL(2), ROW["C"], 0),
    "IC26": (COL(3), ROW["C"], 0), "IC19": (COL(4), ROW["C"], 0), "IC1": (COL(5), ROW["C"], 0),
    "IC47": (COL(6), ROW["C"], 0), "IC53": (199, ROW["C"], 0),
    # row D: the clock chain and the rest of the gates
    "IC28": (COL(0), ROW["D"], 0), "IC21": (COL(1), ROW["D"], 0), "IC32": (COL(2), ROW["D"], 0),
    "IC48": (COL(3), ROW["D"], 0), "IC45": (COL(4), ROW["D"], 0), "IC20": (COL(5), ROW["D"], 0),
    # beside IC20 (row D): the oscillator, the dot clock jumper, the counters' pull-up
    "Q2": (186.0, 117.0, 90), "R8": (190.0, 105.5, 0), "R9": (190.0, 110.0, 0), "SV4": (191.0, 116.0, 90),
    "R10": (191.0, 120.5, 0),
    # the ATmega's neighbours (row B, left of it): R23 RDCMD pull-up, the reset parts, the crystal, R22 LDDATA pull-up;
    # R24 (INTREQ pull-down) right of it
    "R23": (185.0, 46.0, 270), "R16": (189.0, 46.0, 270), "C57": (193.0, 46.0, 270),
    "Y1": (189.0, 64.0, 90), "C55": (186.0, 71.0, 270), "C56": (192.0, 71.0, 270),
    "R22": (195.8, 70.3, 270), "R24": (209.8, 47.0, 270),
    # IC27/E,F's pull-up (the bus -RESET to MRST), beside IC27
    "R21": (197.5, 22.0, 270),
    # IN PC bit 3's pull-up, beside IC34
    "R27": (98.82, 22.0, 270),
    # the direct-mode read buffer on its side under the display latch and shifter (the band under the muxes stays free
    # for routing); the GD pull-ups standing between IC38 and IC42; the text-only pull-downs in the gaps beside IC1;
    # IC54 (turned round: VCC at the bottom) between the clock parts and J4
    "IC55": (156.0, 78.7, 90),     # R2-2: 0.6 mm up, its socket clears IC19's / IC1's and IC42's (socket_check)
    "RN3": (152.5, 51.0, 270),     # 0.3 mm left of the middle: clear of IC55's socket end wall (socket_check)
    "R26": (166.82, 88.5, 270), "R25": (180.82, 88.5, 270),
    "IC54": (208.12, 117.24, 180),
    # the PS/2 +5 V fuse
    "F1": (212.0, 91.5, 0),
    # the right edge: DB9, RCA, the two Mini-DINs (opening at the edge), pull-ups, FTDI, LED
    "X2": (223.487, 28.745, -90), "J1": (227.297, 49.065, -90),
    "J2": (X1R, 70.0, 0), "J3": (X1R, 88.0, 0),                 # MD-60SM: the mating face at the board edge
    "R17": (213.6, 60.0, 270), "R18": (216.9, 60.0, 270), "R19": (213.6, 78.0, 270), "R20": (216.9, 78.0, 270),
    "J4": (212.0, 99.0, 0), "JP3": (204.5, 16.0, 0),
    "LED1": (227.0, 118.5, 0), "R2": (213.0, 118.5, 0),
    # between rows A and B: the sync node resistors
    "R11": (186.0, 41.5, 0), "R12": (196.0, 41.5, 0),
    # bottom left: the block jumper, its pull-ups, DOTS, the bulk capacitor
    "SV3": (69.6, 106.0, 0), "RN2": (69.6, 120.5, 0), "JP2": (96.6, 108.0, 0), "R15": (84.0, 120.0, 0),
    "C16": (38.0, 112.0, 0),
}


def ic_size(ref):
    fp = N.PARTS[ref][2]
    n = int(re.search(r"DIP-(\d+)", fp).group(1))
    w = 15.24 if "W15.24" in fp else 7.62
    return n, w


for _cap, _ic in N.DECOUPLE.items():                     # each 100 nF beside its IC's top right pin, standing
    _x, _y, _ = PLACE[_ic]
    _n, _w = ic_size(_ic)
    PLACE[_cap] = (_x + _w + 3.2, _y, 270)
PLACE["C54"] = (PLACE["IC49"][0] + 7.62 + 3.2, PLACE["IC49"][1] + 8 * 2.54, 270)   # at the ATmega's AVCC (pin 20)
# V2-16: three packages whose VCC pin is not at the top right corner get their capacitor beside that pin
PLACE["C18"] = (57.0, 98.0, 0)                           # the 6845's VCC is pin 20 (bottom left): just below it
PLACE["C49"] = (195.6, 60.24, 270)                       # the ATmega's VCC / GND are pins 7 / 8
PLACE["C22"] = (110.82, 113.0, 270)                      # the 74LS90's VCC is pin 5
PLACE["C58"] = (201.5, 121.2, 0)                         # IC54 turned round: VCC (pin 14) at the bottom left
PLACE["C59"] = (152.5, 75.5, 270)                        # IC55 on its side: VCC (pin 20) at the left end; 0.3 mm
                                                         # left of RN3's old line, clear of IC55's socket (socket_check)


def board(netfile, out):
    import pcbnew
    from pcbnew import VECTOR2I
    FM = pcbnew.FromMM
    nodes, comps = read_netlist(netfile)
    # the blank V3.2 card at the text level: its layer set, X1's place and the site text; a new, longer outline
    src = open(os.path.join(ROOT, "hardware", "bus", "blank-card", "kicad", "v3.2", "blank-card-v3.2.kicad_pcb")).read()
    src = src.replace('\t\t(2 "B.Cu" signal)', '\t\t(4 "In1.Cu" signal)\n\t\t(6 "In2.Cu" signal)\n\t\t(2 "B.Cu" signal)', 1)
    keep, x1at = [], None
    for form in G13.top_forms(src):
        kind = re.match(r"\((\w+)", form).group(1)
        if kind == "footprint":
            if '"Reference" "X1"' in form:
                x1at = [float(v) for v in re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+) ?([-\d.]*)\)', form).groups() if v]
            continue
        if kind in ("segment", "via", "arc", "zone") or (kind == "gr_line" and "Edge.Cuts" in form):
            continue
        if kind == "gr_text":
            continue                                   # the card name and the site text are placed below
        keep.append(form)
    pts = [(X0, Y0), (X1R, Y0), (X1R, Y1B), (X0, Y1B)]
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        keep.append('(gr_line (start %s %s) (end %s %s) (stroke (width 0.1) (type default)) (layer "Edge.Cuts") '
                    '(uuid "%s"))' % (ax, ay, bx, by, uuid.uuid4()))
    keep += [G13.plane("GND", "In1.Cu", pts), G13.plane("VCC", "In2.Cu", pts)]
    open(out, "w").write("(kicad_pcb\n\t" + "\n\t".join(keep) + "\n)\n")
    b = pcbnew.LoadBoard(out)
    nets = {}

    def net(name):
        if name not in nets:
            ni = b.FindNet(name)
            if ni is None:
                ni = pcbnew.NETINFO_ITEM(b, name)
                b.Add(ni)
            nets[name] = ni
        return nets[name]

    fps = {}
    for ref, (value, symid, fpid, note) in N.PARTS.items():
        lib, name = fpid.split(":")
        libdir = os.path.join(HERE, lib + ".pretty") if lib in (N.BUSLIB, LOCAL) else os.path.join(KFP, lib + ".pretty")
        fp = pcbnew.FootprintLoad(libdir, name)
        if fp is None:
            raise SystemExit("board: footprint %s not found" % fpid)
        fp.SetFPIDAsString(fpid)
        fp.SetReference(ref)
        fp.SetValue(value)
        fp.SetPath(pcbnew.KIID_PATH(comps[ref]))
        b.Add(fp)
        fps[ref] = fp
        if ref == "X1":
            x, y, rot = x1at[0], x1at[1], (x1at[2] if len(x1at) > 2 else 0)
        else:
            x, y, rot = PLACE[ref]
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(VECTOR2I(FM(x), FM(y)))
    n = 0
    for ref, fp in fps.items():
        for p in fp.Pads():
            key = (ref, p.GetNumber())
            if key in nodes:
                p.SetNet(net(nodes[key])); n += 1
            elif p.GetNumber() and key in UNCONNECTED:
                p.SetNet(net(UNCONNECTED[key]))
            else:
                p.SetNetCode(0)
    import math
    for p in fps["X1"].Pads():                          # copper keepouts round the DIN connector's two screws
        if p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            continue
        cx, cy = pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)
        z = pcbnew.ZONE(b)
        ls = pcbnew.LSET()
        for layer in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
            ls.AddLayer(layer)
        z.SetLayerSet(ls)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowZoneFills(True); z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
        o = z.Outline(); o.NewOutline()
        for i in range(32):
            a = 2 * math.pi * i / 32
            o.Append(FM(cx + 4.0 * math.cos(a)), FM(cy + 4.0 * math.sin(a)))
        b.Add(z)
    for s, x, y, size, *ang in SILK:
        t = pcbnew.PCB_TEXT(b)
        t.SetText(s); t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(VECTOR2I(FM(size), FM(size))); t.SetTextThickness(FM(max(0.15, size * 0.15)))
        if ang:                                           # a turned legend: (x, y) is its centre
            t.SetTextAngleDegrees(ang[0])
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER); t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        else:
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        t.SetPosition(VECTOR2I(FM(x), FM(y)))
        b.Add(t)
    unclear = silk_place(b)
    pcbnew.SaveBoard(out, b)
    print("silk: every reference and legend placed clear of other silk, the pads and the edge%s" % (
        "" if not unclear else " except %s" % ", ".join(unclear)))
    G13.refill(out)
    print("board %s: %d footprints placed, %d pads on nets, %.2f x %.2f mm, 4 layers (In1 GND, In2 VCC planes)" % (
        os.path.basename(out), len(fps), n, X1R - X0, Y1B - Y0))


SILK = [("YACC1 Video Card V2.0", 60.0, 40.6, 1.5), ("onepagecomputer.com", 120.0, 40.6, 1.0),
        ("DOTS", 95.4, 105.6, 0.8), ("INT-EN", 202.0, 13.6, 0.8),
        # R2-9: the jack legends turned, beside each jack's body (between it and the pull-ups), clear of J1 and J2's ref
        ("KBD (PURPLE)", 220.6, 70.0, 1.0, 90), ("MOUSE (GREEN)", 220.6, 88.0, 1.0, 90),
        ("TEXT-ONLY: R25 R26", 160.0, 100.3, 0.8)]
SILK += [(t, 214.0, 99.0 + 2.54 * k, 1.0) for k, t in enumerate(("1 GND (BLK)", "CTS", "VCC nc", "TXD", "RXD", "DTR"))]
UNCONNECTED = {}                                         # filled from the schematic's netlist by board()


def silk_place(b):
    """R2-9 (2026-10-23): the silkscreen texts placed clear of each other, of every footprint's silk graphics, of the
    pads, of the board edge and of every other part's body (its Fab outline). The legends (SILK) stay where they are unless they meet something, then move by up to
    3 mm; each reference field goes to the free spot nearest its footprint's default (above, below, beside the body,
    turned if need be; inside a DIP's outline as the last resort). Geometry by bounding boxes (a slanted line as a chain
    of small boxes), so it is a little stricter than KiCad's DRC. X2's library text "F09" goes to the Fab layer, X1's
    small texts are raised to the board's 0.8 mm / 0.12 mm minimum. -> the texts left where they still meet something"""
    import math
    import pcbnew
    from pcbnew import VECTOR2I
    MM, FM = pcbnew.ToMM, pcbnew.FromMM
    CLR_SILK, CLR_PAD, EDGE = 0.15, 0.2, 0.4

    def bx(bb, g=0.0):
        return (MM(bb.GetLeft()) - g, MM(bb.GetTop()) - g, MM(bb.GetRight()) + g, MM(bb.GetBottom()) + g)

    def hit(a, c):
        return a[0] < c[2] and c[0] < a[2] and a[1] < c[3] and c[1] < a[3]

    def shape_boxes(s, g):
        w = MM(s.GetWidth()) / 2 + g
        kind = s.GetShapeStr()
        if kind in ("Rect", "Line"):
            pts = [(MM(v.x), MM(v.y)) for v in s.GetRectCorners()] if kind == "Rect" else \
                  [(MM(s.GetStart().x), MM(s.GetStart().y)), (MM(s.GetEnd().x), MM(s.GetEnd().y))]
            edges = list(zip(pts, pts[1:] + pts[:1])) if kind == "Rect" else [tuple(pts)]
            out = []
            for (ax, ay), (cx, cy) in edges:
                n = max(1, int(math.hypot(cx - ax, cy - ay)))
                for i in range(n):
                    x0, y0 = ax + (cx - ax) * i / n, ay + (cy - ay) * i / n
                    x1, y1 = ax + (cx - ax) * (i + 1) / n, ay + (cy - ay) * (i + 1) / n
                    out.append((min(x0, x1) - w, min(y0, y1) - w, max(x0, x1) + w, max(y0, y1) + w))
            return out
        return [bx(s.GetBoundingBox(), g)]

    fixed, placed, unclear = [], [], []
    fps = list(b.GetFootprints())
    for fp in fps:
        ref = fp.GetReference()
        for p in fp.Pads():
            fixed.append(bx(p.GetBoundingBox(), CLR_PAD))
        for it in fp.GraphicalItems():
            if it.GetLayer() != pcbnew.F_SilkS:
                continue
            if it.GetClass() == "PCB_TEXT":
                if ref == "X2" and it.GetText() == "F09":
                    it.SetLayer(pcbnew.F_Fab)
                    continue
                if it.GetTextHeight() < FM(0.8):
                    it.SetTextSize(VECTOR2I(FM(0.8), FM(0.8)))
                if it.GetTextThickness() < FM(0.12):
                    it.SetTextThickness(FM(0.12))
                fixed.append(bx(it.GetBoundingBox(), CLR_SILK))
            else:
                fixed.extend(shape_boxes(it, CLR_SILK))
    bodies = {}                                         # each part's body (its Fab outline): no other part's text in it
    for fp in fps:
        qs = [bx(it.GetBoundingBox()) for it in fp.GraphicalItems()
              if it.GetLayer() == pcbnew.F_Fab and it.GetClass() != "PCB_TEXT"]
        if qs:
            bodies[fp.GetReference()] = (min(q[0] for q in qs), min(q[1] for q in qs), max(q[2] for q in qs),
                                         max(q[3] for q in qs))

    def free(t, owner=None):
        r = bx(t.GetBoundingBox())
        if r[0] < X0 + EDGE or r[1] < Y0 + EDGE or r[2] > X1R - EDGE or r[3] > Y1B - EDGE:
            return False
        if any(hit(r, q) for ref, q in bodies.items() if ref != owner):
            return False
        return not any(hit(r, q) for q in fixed) and not any(hit(r, q) for q in placed)

    def place(t, cands, name, owner=None):
        for x, y, a in cands:
            t.SetTextAngleDegrees(a)
            t.SetPosition(VECTOR2I(FM(x), FM(y)))
            if free(t, owner):
                break
        else:
            x, y, a = cands[0]
            t.SetTextAngleDegrees(a)
            t.SetPosition(VECTOR2I(FM(x), FM(y)))
            unclear.append(name)
        placed.append(bx(t.GetBoundingBox(), CLR_SILK))

    for d in b.GetDrawings():                           # 1. the legends, near their own place
        if d.GetClass() == "PCB_TEXT" and d.GetLayer() == pcbnew.F_SilkS:
            x, y, a = MM(d.GetPosition().x), MM(d.GetPosition().y), d.GetTextAngleDegrees()
            offs = sorted({(i * 0.25, j * 0.25) for i in range(-12, 13) for j in range(-12, 13)},
                          key=lambda o: (abs(o[0]) + abs(o[1]), abs(o[1]), o))
            place(d, [(x + i, y + j, a) for i, j in offs], d.GetText())
    order = lambda fp: (not fp.GetReference().startswith("IC"), fp.GetReference())
    for fp in sorted(fps, key=order):                   # 2. the references, ICs first
        t = fp.Reference()
        if not t.IsVisible() or t.GetLayer() != pcbnew.F_SilkS:
            continue
        if t.GetTextThickness() < FM(0.15):
            t.SetTextThickness(FM(0.15))
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        boxes = [bx(p.GetBoundingBox()) for p in fp.Pads()] + \
                [bx(it.GetBoundingBox()) for it in fp.GraphicalItems()
                 if it.GetLayer() == pcbnew.F_SilkS and it.GetClass() != "PCB_TEXT"]
        x0, y0 = min(q[0] for q in boxes), min(q[1] for q in boxes)
        x1, y1 = max(q[2] for q in boxes), max(q[3] for q in boxes)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        dx, dy, da = MM(t.GetPosition().x), MM(t.GetPosition().y), t.GetTextAngleDegrees() % 180
        cands = [(dx, dy, da, 0)]
        for a in (0, 90):
            t.SetTextAngleDegrees(a)
            t.SetPosition(VECTOR2I(0, 0))
            r = bx(t.GetBoundingBox())
            w, h = r[2] - r[0], r[3] - r[1]
            for gap in (0.2, 0.6, 1.2, 2.0):
                for k in range(-16, 17):
                    s = k * 0.5
                    cands += [(cx + s, y0 - gap - h / 2, a, 0), (cx + s, y1 + gap + h / 2, a, 0),
                              (x0 - gap - w / 2, cy + s, a, 0), (x1 + gap + w / 2, cy + s, a, 0)]
            cands.append((cx, cy, a, 4))                # inside the body: the last resort
        cands.sort(key=lambda c: math.hypot(c[0] - dx, c[1] - dy) + (1.5 if c[2] != da else 0) + c[3])
        place(t, [c[:3] for c in cands], fp.GetReference(), fp.GetReference())
    return unclear


SIDE_WALL, END_WALL = 1.3, 1.9          # a DIP socket's walls beyond its pin rows / its end pins (stamped sockets' worst)


def socket_check(b):
    """R2-2 (2026-10-23): every DIP in a socket - the socket's outline (the pin rows + 1.3 mm at the sides, the end pins +
    1.9 mm at the ends) must clear every other socket's outline and every other part's pads and body (each pad, Fab and
    silk shape on its own: a resistor's pad and its body outline are not one box); a courtyard is only ~0.5 mm round the pins. -> (problems, the smallest gaps)"""
    import pcbnew
    MM = pcbnew.ToMM
    socks, bodies = {}, {}
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if "DIP-" in fp.GetFPIDAsString():
            xs = [MM(p.GetPosition().x) for p in fp.Pads()]
            ys = [MM(p.GetPosition().y) for p in fp.Pads()]
            ax, ay = (END_WALL, SIDE_WALL) if max(xs) - min(xs) > max(ys) - min(ys) else (SIDE_WALL, END_WALL)
            socks[ref] = (min(xs) - ax, min(ys) - ay, max(xs) + ax, max(ys) + ay)
        elif ref != "X1":                                # each pad, each Fab / silk shape on its own
            bodies[ref] = [(MM(r.GetLeft()), MM(r.GetTop()), MM(r.GetRight()), MM(r.GetBottom())) for r in
                           [p.GetBoundingBox() for p in fp.Pads()] + [it.GetBoundingBox() for it in fp.GraphicalItems()
                            if it.GetLayer() in (pcbnew.F_Fab, pcbnew.F_SilkS) and it.GetClass() != "PCB_TEXT"]]
    gap = lambda A, C: max(C[0] - A[2], A[0] - C[2], C[1] - A[3], A[1] - C[3])
    res = []
    refs = sorted(socks)
    for i, a in enumerate(refs):
        res += [(gap(socks[a], socks[c]), a, c, "socket") for c in refs[i + 1:]]
        res += [(min(gap(socks[a], B) for B in bs), a, c, "body") for c, bs in bodies.items()]
    res.sort()
    probs = ["socket %s meets %s %s (%.2f mm)" % (a, "socket" if k == "socket" else "the body of", c, g)
             for g, a, c, k in res if g < 0]
    return probs, res[:6], len(socks)


def silk_cmd(pcb, out=None):
    """gen_v20.py silk <pcb> [out]: silk_place() on a finished board (board() runs it on every new one)"""
    import pcbnew
    b = pcbnew.LoadBoard(pcb)
    unclear = silk_place(b)
    pcbnew.SaveBoard(out or pcb, b)
    print("silk: %s" % ("every text clear" if not unclear else "still meeting something: " + ", ".join(unclear)))
    return not unclear


def placement_check(pcb):
    """courtyards must not overlap, every courtyard inside the outline (the connectors' fronts may reach the edge); the
    DIP sockets clear of each other and of the other parts (socket_check)"""
    import pcbnew
    b = pcbnew.LoadBoard(pcb)
    boxes = {}
    for fp in b.GetFootprints():
        bb = None
        for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            poly = fp.GetCourtyard(layer)
            if poly.OutlineCount():
                pb = poly.BBox()
                bb = (pcbnew.ToMM(pb.GetLeft()), pcbnew.ToMM(pb.GetTop()), pcbnew.ToMM(pb.GetRight()), pcbnew.ToMM(pb.GetBottom()))
        if bb is None:
            pb = fp.GetBoundingBox(False)
            bb = (pcbnew.ToMM(pb.GetLeft()), pcbnew.ToMM(pb.GetTop()), pcbnew.ToMM(pb.GetRight()), pcbnew.ToMM(pb.GetBottom()))
        boxes[fp.GetReference()] = bb
    bad = []
    refs = sorted(boxes)
    for i, a in enumerate(refs):
        A = boxes[a]
        if a != "X1" and not (A[0] >= X0 - 0.01 and A[1] >= Y0 - 0.01 and A[2] <= X1R + 0.01 and A[3] <= Y1B + 0.01):
            if a not in ("X2", "J1", "J2", "J3"):
                bad.append("%s outside the board %s" % (a, tuple(round(v, 1) for v in A)))
        for c in refs[i + 1:]:
            C = boxes[c]
            if A[0] < C[2] - 0.05 and C[0] < A[2] - 0.05 and A[1] < C[3] - 0.05 and C[1] < A[3] - 0.05:
                bad.append("%s overlaps %s" % (a, c))
    sp, smallest, nsock = socket_check(b)
    bad += sp
    for x in bad:
        print("  " + x)
    print("placement: %d footprints, %s" % (len(boxes), "clear" if not bad else "%d problems" % len(bad)))
    print("sockets: %d DIP sockets (+%.1f mm at the sides, +%.1f at the ends): %s; the closest: %s" % (
        nsock, SIDE_WALL, END_WALL, "PASS" if not sp else "%d FAIL" % len(sp),
        ", ".join("%s-%s %.2f" % (a, c, g) for g, a, c, k in smallest)))
    return not bad


# the V2.0 key connections, checked pin by pin in the schematic netlist and on the board's pads
KEY = [
    # ports: decode, strobes, the 6845 on PA/PB
    ("IC30", "6", "IO-ADDR3"), ("IC30", "13", "PSEL_A"), ("IC30", "12", "PSEL_B"), ("IC30", "11", "PSEL_C"),
    ("IC30", "10", "PSEL_D"), ("IC30", "9", "PSEL_E"), ("IC1", "3", "CRTCCS"), ("IC17", "25", "CRTCCS"),
    ("IC17", "24", "IO-ADDR0"), ("IC17", "22", "-IO-WR"), ("IC17", "23", "CRTCE"), ("IC26", "8", "CRTCE"),
    ("IC26", "9", "-IO-RD"), ("IC26", "10", "-IO-WR"), ("IC31", "3", "CTLCLK"), ("IC33", "11", "CTLCLK"),
    ("IC31", "6", "STATOE"), ("IC34", "1", "STATOE"), ("IC31", "8", "CMDCLK"), ("IC51", "11", "CMDCLK"),
    ("IC31", "11", "PSTOE"), ("IC52", "1", "PSTOE"), ("IC32", "3", "PDOE"), ("IC50", "1", "PDOE"),
    # card ID $5x and DOTS on IN PC
    ("IC34", "2", "DOTS"), ("IC34", "11", "VCC"), ("IC34", "13", "GND"), ("IC34", "15", "VCC"), ("IC34", "17", "GND"),
    # graphics: the mux select (NMUX: 1 = CPU on I1), the RAM, the slot logic
    ("IC35", "1", "NMUX"), ("IC36", "1", "NMUX"), ("IC37", "1", "NMUX"), ("IC38", "1", "NMUX"),
    ("IC35", "3", "ADDR0"), ("IC35", "2", "VADDR0"), ("IC38", "5", "VROWS2"), ("IC38", "11", "DPAGE"),
    ("IC38", "10", "CPAGE"), ("IC39", "22", "WSLOT"), ("IC39", "27", "GWE"), ("IC45", "6", "GWE"),
    ("IC44", "3", "CHARCLOCK"), ("IC44", "2", "GWR"), ("IC44", "5", "WRQ"), ("IC41", "11", "CRTCCLOCK"),
    ("IC41", "1", "SRDOE"), ("IC19", "3", "GRDOE"), ("IC42", "11", "CHARCLOCK"), ("IC43", "15", "CHARCLOCK"),
    ("IC43", "13", "GDOT"), ("IC26", "11", "WEPH"),
    # V2-4: select = (QC OR RCO) (and GFX-ON): IC32/C, IC19/D
    ("IC32", "9", "CRTCCLOCK"), ("IC32", "10", "RCO"), ("IC32", "8", "QCR"), ("IC19", "12", "QCR"),
    ("IC19", "13", "GFXON"), ("IC19", "11", "NMUX"),
    # V2-5: the write buffer IC40 on only during -WE
    ("IC40", "1", "GWE"), ("IC40", "19", "GWE"),
    # direct mode (GFX-ON = 0): WRQ preset, WEPH forced, -WE from GWR, -OE from the window read, the bypass IC55
    ("IC33", "16", "GFXON"), ("IC44", "4", "GFXON"), ("IC46", "1", "GFXON"), ("IC46", "2", "NGFX"),
    ("IC32", "12", "WEPH"), ("IC32", "13", "NGFX"), ("IC32", "11", "WEPH2"), ("IC45", "4", "WEPH2"),
    ("IC45", "1", "WRQ"), ("IC45", "2", "NMUX"), ("IC45", "5", "GWR"), ("IC54", "1", "NMUX"), ("IC54", "2", "GRDOE"),
    ("IC54", "3", "OEY"), ("IC1", "4", "WRQ"), ("IC1", "5", "OEY"), ("IC1", "6", "WSLOT"),
    ("IC48", "9", "GSEL"), ("IC48", "10", "MEMRD"), ("IC48", "11", "GFXON"), ("IC48", "8", "SRDOE"),
    ("IC45", "9", "GSEL"), ("IC45", "10", "MEMRD"), ("IC45", "12", "NGFX"), ("IC45", "8", "DRDOE"),
    ("IC55", "1", "DRDOE"), ("IC55", "19", "DRDOE"), ("IC55", "2", "GD0"), ("IC55", "18", "DATA0"),
    ("IC55", "17", "GD7"), ("IC55", "3", "DATA7"), ("RN3", "1", "VCC"), ("RN3", "2", "GD0"), ("RN3", "9", "GD7"),
    # the text-only build: the pull-down pads and the status bit (IN PC bit 3)
    ("R25", "1", "GDOT"), ("R25", "2", "GND"), ("IC1", "12", "GDOT"), ("R26", "1", "WRQ"), ("R26", "2", "GND"),
    ("IC34", "8", "TXTONLY"), ("IC44", "9", "TXTONLY"), ("R27", "1", "TXTONLY"), ("R27", "2", "VCC"),
    ("IC44", "13", "GND"), ("IC44", "10", "VCC"),
    # the combine: graphics only in 8-dot mode
    ("IC46", "11", "DOTS"), ("IC46", "10", "EIGHT"), ("IC47", "2", "EIGHT"), ("IC48", "13", "XORM"),
    ("IC48", "5", "DE3"), ("IC48", "6", "VIDN"), ("IC27", "1", "VIDN"),
    # the V1.3 divider and font select kept
    ("IC28", "4", "DOTS"), ("IC28", "9", "CHARCLOCK"), ("IC28", "15", "RCO"),
    # V2-10: the 28C64 character generator (the 2732's pins + 2; A12, A11, A9, -CE, -OE low, -WE high, A10 = DOTS)
    ("IC25", "21", "DOTS"), ("IC25", "10", "VROWS0"), ("IC25", "8", "VROWS2"), ("IC25", "7", "CA3"),
    ("IC25", "25", "CA8"), ("IC25", "3", "CA7"), ("IC25", "2", "GND"), ("IC25", "23", "GND"), ("IC25", "24", "GND"),
    ("IC25", "20", "GND"), ("IC25", "22", "GND"), ("IC25", "27", "VCC"), ("IC25", "28", "VCC"), ("IC25", "14", "GND"),
    ("IC25", "11", "CG0"), ("IC25", "19", "CG7"),
    # PS/2: the ATmega, the latches, the flags, INT
    ("IC49", "4", "KCLK"), ("IC49", "5", "MCLK"), ("IC49", "6", "KDAT"), ("IC49", "11", "MDAT"),
    ("IC49", "12", "LDDATA"), ("IC49", "13", "RDCMD"), ("IC49", "16", "FULL"), ("IC49", "17", "BUSY"),
    ("IC49", "18", "INTREQ"), ("IC49", "19", "SRC"), ("IC53", "1", "FULLCLR"), ("IC53", "13", "RDCMD"),
    ("IC53", "9", "BUSY"), ("IC52", "6", "BUSY"), ("IC52", "4", "SRC"),
    # V2-7: -INT = INTREQ AND FULL (IC54/B), the pull-ups / pull-down
    ("IC54", "4", "INTREQ"), ("IC54", "5", "FULL"), ("IC54", "6", "INTG"), ("IC27", "9", "INTG"),
    ("R22", "1", "LDDATA"), ("R23", "1", "RDCMD"), ("R24", "1", "INTREQ"), ("R24", "2", "GND"),
    ("IC27", "8", "INTOC"), ("JP3", "1", "INTOC"), ("JP3", "2", "-INT"), ("X1", "C13", "-INT"),
    ("J2", "5", "KCLK"), ("J2", "1", "KDAT"), ("J3", "5", "MCLK"), ("J3", "1", "MDAT"), ("J2", "3", "GND"),
    ("J2", "4", "PS2VCC"), ("J3", "4", "PS2VCC"), ("F1", "2", "PS2VCC"), ("F1", "1", "VCC"),
    # V2-6: the bus -RESET to MRST through two open-collector inverters (no D1)
    # R2-3: IC27/E's input buffered by IC54/C (74HCT08, both inputs: -RESET and VCC) - the bus sees one HCT input
    ("IC54", "9", "-RESET"), ("IC54", "10", "VCC"), ("IC54", "8", "RESETB"), ("IC27", "11", "RESETB"),
    ("IC27", "10", "RESETH"), ("R21", "1", "RESETH"), ("IC27", "13", "RESETH"),
    ("IC27", "12", "MRST"), ("IC49", "1", "MRST"), ("R16", "1", "MRST"),
    # R2-14: the nets the review's fixes rest on - MEMWR into GWR, the WRQ clear, FULL's clear / clock / output, IC40
    ("IC46", "5", "-MEM-WR"), ("IC46", "6", "MEMWR"), ("IC47", "10", "MEMWR"), ("IC44", "1", "-RESET"),
    ("IC53", "1", "FULLCLR"), ("IC53", "3", "LDDATA"), ("IC53", "5", "FULL"),
    ("IC40", "2", "DATA0"), ("IC40", "18", "GD0"), ("IC40", "17", "DATA7"), ("IC40", "3", "GD7"),
    ("J2", "S", "GND"), ("J3", "S", "GND"),
]


def verify(netfile, pcb):
    nodes, comps = read_netlist(netfile)
    t = open(pcb).read()
    pads = {}
    for fp in G13.top_forms(t):
        if not fp.startswith("(footprint"):
            continue
        ref = re.search(r'\(property "Reference" "([^"]+)"', fp).group(1)
        for m in re.finditer(r'\(pad "([^"]*)" .*?(?=\n\t\t\(pad |\Z)', fp, re.S):
            nn = re.search(r'\(net "([^"]*)"\)', m.group(0))
            pads[(ref, m.group(1))] = nn.group(1).lstrip("/") if nn else None
    bad = 0
    for ref, pad, want in KEY:
        sch = (nodes.get((ref, pad)) or "").lstrip("/")
        brd = pads.get((ref, pad), "(missing)")
        ok = sch == want and brd == want
        bad += not ok
        if not ok:
            print("  %-5s %-4s schematic %-11s board %-11s WANT %s" % (ref, pad, sch, brd, want))
    power = len(re.findall(r'\(segment[^()]*?(?:\([^()]*\)[^()]*?)*?\(net "(?:GND|VCC)"\)', t))
    layers = re.findall(r'\(\d+ "([^"]+\.Cu)" signal\)', t)
    zones = [z for z in G13.top_forms(t) if z.startswith("(zone") and '(net "' in z]
    planes = sorted((re.search(r'\(net "([^"]+)"', z).group(1), re.search(r'\(layer "([^"]+)"', z).group(1)) for z in zones)
    print("  %d key connections; copper layers %s; planes %s; tracks on GND/VCC %d" % (len(KEY), layers, planes, power))
    bad += layers != ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"] or planes != [("GND", "In1.Cu"), ("VCC", "In2.Cu")] or power != 0
    print("verify: %s" % ("PASS" if not bad else "%d FAIL" % bad))
    return not bad


def bom():
    """BOM.md from v20_netlist.PARTS: one line per value and footprint, the text-only build marked"""
    rows = collections.OrderedDict()
    order = lambda r: (re.match(r"[A-Z]+", r).group(0), int(re.search(r"\d+", r).group(0)))
    for ref in sorted(N.PARTS, key=order):
        value, symid, fpid, note = N.PARTS[ref]
        if ref in N.DECOUPLE:
            note = "decoupling"
        key = (value, fpid.split(":")[1], N.BUY.get(ref, ""), "off" if ref in N.TEXT_ONLY_LEFT_OFF else
               "only" if ref in N.TEXT_ONLY_FITTED else "")
        rows.setdefault(key, []).append(ref)
    L = ["# Video card V2.0 - bill of materials", "",
         "GENERATED by `gen_v20.py bom` from `v20_netlist.py` (%s) - do not edit. %d parts. Buy %s. **Text-only "
         "build** (the recommended first build, README): leave off the parts marked *off*, fit the ones marked *only*." % (
             N.DATE, len(N.PARTS), N.SOCKETS), "",
         "| Qty | Value | Footprint | References | Text-only | Buy / note |", "|---|---|---|---|---|---|"]
    for (value, fp, buy, tob), refs in rows.items():
        L.append("| %d | %s | %s | %s | %s | %s |" % (len(refs), value, fp, ", ".join(refs), tob, buy))
    L += ["", "Fitted in both builds: everything not marked *off* or *only*. The text-only build leaves off %d parts "
          "(%s) and fits %s." % (len(N.TEXT_ONLY_LEFT_OFF), ", ".join(N.TEXT_ONLY_LEFT_OFF), ", ".join(N.TEXT_ONLY_FITTED)), ""]
    open(os.path.join(HERE, "BOM.md"), "w").write("\n".join(L))
    print("BOM.md: %d parts, %d lines" % (len(N.PARTS), len(rows)))


def read_netlist(path):
    """(ref, pad) -> the schematic's own net name (/NAME for a label net), ref -> the symbol's KIID path"""
    s = open(path).read()
    comps = {}
    for blk in re.split(r'\(comp\s*\n', s[:s.index("(libparts")] if "(libparts" in s else s)[1:]:
        ref = re.search(r'\(ref "([^"]+)"\)', blk).group(1)
        sp = re.search(r'\(sheetpath\s*\(names "[^"]*"\)\s*\(tstamps "([^"]*)"\)', blk)
        ts = re.search(r'\)\s*\(tstamps "([^"]*)"\)', blk[sp.end():] if sp else blk)
        comps[ref] = (sp.group(1) if sp else "/") + (ts.group(1) if ts else "")
    nodes = {}
    for blk in re.split(r'\(net\s*\(code', s[s.index("(nets"):])[1:]:
        name = re.search(r'\(name "([^"]*)"', blk).group(1)
        if name.startswith("unconnected-"):
            continue
        for r, p in re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"', blk):
            nodes[(r, p)] = name
    return nodes, comps


def read_unconnected(netfile):
    s = open(netfile).read()
    out = {}
    for name, body in re.findall(r'\(name "(unconnected-\([^"]*\))"\)(.*?)\n\t\t\)', s, re.S):
        nodes = re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', body)
        if len(nodes) == 1:
            out[nodes[0]] = name
    return out


if __name__ == "__main__":
    cmd, a = sys.argv[1], sys.argv[2:]
    ok = True
    if cmd == "sch":
        sch()
    elif cmd == "checknet":
        ok = check_schematic_netlist(*a)
    elif cmd == "project":
        project()
    elif cmd == "board":
        UNCONNECTED.update(read_unconnected(a[0]))
        board(*a)
    elif cmd == "place":
        ok = placement_check(*a)
    elif cmd == "silk":
        ok = silk_cmd(*a)
    elif cmd == "verify":
        ok = verify(*a)
    elif cmd == "bom":
        bom()
    elif cmd in ("dsn", "shuffle", "ses", "stats", "refill"):
        getattr(G13, cmd)(*a)
    else:
        raise SystemExit(__doc__)
    sys.stdout.flush()
    os._exit(0 if ok else 1)
