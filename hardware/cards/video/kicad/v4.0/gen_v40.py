#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""gen_v40.py - the YACC1 video card V4.0 (a 6845 at 16 dots a count, VGA; 2026-11-12): the schematic, the project rules
and the unrouted 4-layer board with its placement, all from v40_netlist.py (the circuit). Design note:
docs/cards/video-v4.md (section 5 the clock and the stage, 6 the text, 7 the graphics RAM's two modes, 8 the dots).

Made from the V3 design's gen_v30.py (itself from the V2.0 card's gen_v20.py): the sheet writer's use, the silkscreen
placer and the checks are theirs; the sheets, the local symbols, the placement and the key connections are this card's.

THE BOARD IS PLACED AND ROUTED (2026-11-12, build.sh; not ordered). The 46 ICs stand in thirteen columns, eleven of
300-mil sockets and two of 600-mil ones, a capacitor beside every chip's VCC pin. At the V2.0 card's spacing (columns 14 mm apart, 6.3 mm
between the chips of a column) this placement is 235 mm long, against the 218 mm of every long card; with one
column fewer and every column full to the last socket it would still be 221 mm, with nowhere for the oscillator, the
crystal, the jumpers and the resistors. The outline here is 250 mm (LENGTH), the V3 design's choice, with the
columns 15.24 mm apart: the 15 mm more are routing room, which the V2.0 board has none of (250 mm decided
2026-11-12). build.sh routes it with Freerouting and runs the reports and the checks.

The schematic is a root sheet and one sheet per functional block (SHEETS), each drawn by tools/kicad/sch_wire.py: ELK
places the parts and the nets between them are wires; the bus signals, power and one-pin nets keep a stub to a label or
a power symbol (the CF card's sheet writer gen_cf.py underneath). Parts KiCad has no symbol for (the IDT7134, the
32-pin static RAM, the Mini-DIN with its shield) are drawn into the local library video-v4.0-local.
One local footprint: the Mini-DIN, drawn from the Same Sky MD-60SM data sheet (minidin_footprint(), as V2.0's); the
DE-15 is KiCad's own.
The board: the blank V3.2 card's X1 and outline, lengthened (LENGTH), 4 layers (In1.Cu GND plane, In2.Cu VCC plane, as
the V2.0 and memory v2.0 boards), every part placed here, every pad on its schematic net, keepouts round X1's two screws.

Run with KiCad's bundled Python (pcbnew), from this folder:
  gen_v40.py sch                          -> local libraries + video-v4.0.kicad_sch (the root) and its sheets
                                             video-v4.0-<block>.kicad_sch (needs node + elkjs: tools/kicad)
  gen_v40.py checknet <netlist>           -> the netlist KiCad exports from the schematic against v40_netlist.py
  gen_v40.py project                      -> video-v4.0.kicad_pro + .kicad_dru (signals 0.25 mm / 0.2 mm, vias 0.8/0.4;
                                             class Power = GND, VCC: planes, never routed)
  gen_v40.py board <netlist> <out.pcb>    -> the unrouted board
  gen_v40.py place <pcb>                  -> the placement check: courtyards apart, everything inside the outline, the
                                             DIP sockets' outlines clear of each other and of the other parts
  gen_v40.py drawing <pcb> [out.pdf]      -> the placement drawing, video-v4.0-placement.pdf, on a landscape sheet
  gen_v40.py silk <pcb> [out]             -> the silkscreen texts placed clear (board() does it on every new board)
  gen_v40.py clockroute <pcb> <out.pcb>   -> the four clocks (CK, D2, D3, STG and the stubs to their series
                                             resistors) laid as trees from their sources and locked, before Freerouting
  gen_v40.py clocks <pcb> [report.txt]    -> the clock nets on a board: track, and the copper's length to every input
  gen_v40.py planes <pcb>                 -> each plane one piece (on the routed board)
  gen_v40.py dsn|shuffle|ses|stats ...    -> as gen_v13.py (Specctra export/import, Freerouting seeds, route stats)
  gen_v40.py link <netlist> <pcb>         -> the footprints' schematic links (path) set from the netlist, nothing else
  gen_v40.py verify <netlist> <pcb>       -> the key connections pin by pin (schematic and board), layers, planes
  gen_v40.py bom                          -> BOM.md: the bill of materials from v40_netlist.PARTS (plain Python)
"""
import os, sys, re, json, uuid, shutil, subprocess, collections, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
CFDIR = os.path.join(ROOT, "hardware", "cards", "cf", "kicad", "v1.0")
V13DIR = os.path.join(HERE, "..", "v1.3")
sys.path.insert(0, HERE)
sys.path.insert(0, CFDIR)
sys.path.insert(0, os.path.join(ROOT, "tools", "kicad"))
import v40_netlist as N                                    # noqa: E402
import gen_cf                                              # noqa: E402  (the CF card's sheet writer, reused read-only)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


G13 = _load(os.path.join(V13DIR, "gen_v13.py"), "gen_v13")   # dsn / shuffle / ses / stats / refill / plane
P = "video-v4.0"
CLI = gen_cf.CLI
KFP = gen_cf.KFP
LOCAL = N.LOCAL
G = 2.54
LENGTH = 250.0                                             # mm: the card from the bus connector's edge to the front (218: every long card)
X0, Y0, Y1B = 17.747, 10.025, 123.995                      # the blank card's left, top and bottom edges
X1R = X0 + LENGTH                                          # the front edge
gen_cf.N = N
gen_cf.NETOF = {(r, p): n for n, conns in N.NETS.items() for r, p in conns}
gen_cf.NC = {(r, p) for r, ps in N.NO_CONNECT.items() for p in ps}
gen_cf.PROJ = P
gen_cf.ROOT_UUID = gen_cf.U("video-v4.0", "root")


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
    for i, pin in enumerate(top):                       # (None: a place left empty, to stand two power pins apart)
        if pin:
            out.append(pin_line(pin[0], pin[1], pin[2], -w / 2 + G + i * G, h / 2 + L, 270))
    for i, pin in enumerate(bottom):
        if pin:
            out.append(pin_line(pin[0], pin[1], pin[2], -w / 2 + G + i * G, -h / 2 - L, 90))
    out += ['\t\t)', '\t\t(embedded_fonts no)', '\t)']
    return "\n".join(out)


# the 128K x 8 static RAM in DIP-32 (Alliance AS6C1008, its data sheet's figure); pin 1 and pin 30 are A18 and A17 of
# the 512K part
SRAM32 = {1: "NC/A18", 2: "A16", 3: "A14", 4: "A12", 5: "A7", 6: "A6", 7: "A5", 8: "A4", 9: "A3", 10: "A2", 11: "A1",
          12: "A0", 13: "DQ0", 14: "DQ1", 15: "DQ2", 16: "VSS", 17: "DQ3", 18: "DQ4", 19: "DQ5", 20: "DQ6", 21: "DQ7",
          22: "~{CE}", 23: "A10", 24: "~{OE}", 25: "A11", 26: "A9", 27: "A8", 28: "A13", 29: "~{WE}", 30: "CE2/A17",
          31: "A15", 32: "VCC"}


def local_symbols():
    io, inp, pas, pw, tri = "bidirectional", "input", "passive", "power_in", "tri_state"
    # the IDT7134 (the V2.0 card's symbol): the left port the display's, the right port the CPU's
    s7134 = box_symbol(
        "IDT7134", "IC", "IDT7134 4K x 8 dual-port static RAM, DIL48",
        left=[(str(p), "A%dL" % i, inp) for i, p in enumerate((6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 4, 3))] +
             [(str(16 + i), "I/O%dL" % i, io) for i in range(8)] +
             [("1", "~{CEL}", inp), ("2", "R/~{WL}", inp), ("5", "~{OEL}", inp)],
        right=[(str(p), "A%dR" % i, inp) for i, p in enumerate((42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 44, 45))] +
              [(str(25 + i), "I/O%dR" % i, io) for i in range(8)] +
              [("47", "~{CER}", inp), ("46", "R/~{WR}", inp), ("43", "~{OER}", inp)],
        top=[("48", "VCC", pw)], bottom=[("24", "GND", pw)], width=22.86)
    adr = [12, 11, 10, 9, 8, 7, 6, 5, 27, 26, 23, 25, 4, 28, 3, 31, 2]
    sram = box_symbol(
        "SRAM_DIP32", "IC", "128K x 8 static RAM, DIP-32 600 mil (AS6C1008); pins 1 and 30 are A18 and A17 of the 512K part",
        left=[(str(p), SRAM32[p], inp) for p in adr + [30, 1, 22, 24, 29]],
        right=[(str(p), SRAM32[p], tri) for p in (13, 14, 15, 17, 18, 19, 20, 21)],
        top=[("32", "VCC", pw)], bottom=[("16", "VSS", pw)], width=20.32)
    mdin = box_symbol("MINIDIN6", "J", "Mini-DIN-6 female (PS/2): 1 data, 3 GND, 4 +5V, 5 clock, 2/6 unused; S = shell",
                      left=[(str(i), ("DATA", "nc", "GND", "+5V", "CLK", "nc")[i - 1], pas) for i in range(1, 7)],
                      right=[("S", "SHELL", pas)], width=12.7)
    text = "\n".join(['(kicad_symbol_lib', '\t(version 20251024)', '\t(generator "gen_v40")', '\t(generator_version "1.0")',
                      s7134, sram, mdin, ')', ''])
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
    L = ['(footprint "MiniDIN6_MD-60SM"', '\t(version 20241229)', '\t(generator "gen_v40")', '\t(layer "F.Cu")',
         '\t(descr "Mini-DIN-6 (PS/2) right-angle PCB jack Same Sky (CUI) MD-60SM, data sheet MD-SM rev 1.09 '
         '2024-09-12, PCB layout for date codes after 03/03/2022; mating face at x = 0, opening towards +x '
         '(YACC1 video V2.0 and V4.0)")', '\t(attr through_hole)',
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


# The DE-15 (VGA) socket J1 has KiCad's own footprint (v40_netlist.FP_VGA): a right-angle PCB part with a stamped
# shell, pins in three rows 2.29 mm apart along the rows and 1.90 mm from row to row, the front row 3.03 mm and the
# two 3.2 mm lock holes 4.94 mm inside the board's edge, 25 mm apart. Its origin is pin 1; the board's edge is the line
# y = 6.83 of the footprint, and the shell reaches 6.4 mm past it.
# The part (the design review's V4-3, 2026-11-13): Kycon K61X-E15S-NJ, whose drawing (rev A5) has the rows 1.95 mm
# apart, the front row 3.05 mm and the locks 5.00 mm from the edge, 24.99 mm apart: the footprint's pattern within
# 0.06 mm. Its drawing asks for 1.09 mm signal holes: board() drills J1's fifteen to DE15_DRILL (the footprint: 1.0).
# The other common pattern (rows 2.54 mm apart, 8.89 mm from the edge: Amphenol ICD15S13E..., NorComp 181) does not fit.
DE15_DRILL = 1.1
DE15_EDGE = 6.83                                         # the footprint's y of the board edge


def local_libs():
    for ext in (".kicad_sym",):
        shutil.copy(os.path.join(CFDIR, N.BUSLIB + ext), os.path.join(HERE, N.BUSLIB + ext))
    for lib in (N.BUSLIB, LOCAL):
        d = os.path.join(HERE, lib + ".pretty")
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)
    shutil.copy(os.path.join(CFDIR, N.BUSLIB + ".pretty", "FABC96R.kicad_mod"), os.path.join(HERE, N.BUSLIB + ".pretty"))
    open(os.path.join(HERE, LOCAL + ".pretty", "MiniDIN6_MD-60SM.kicad_mod"), "w").write(minidin_footprint())
    local_symbols()
    open(os.path.join(HERE, "sym-lib-table"), "w").write(
        '(sym_lib_table\n\t(version 7)\n'
        '\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.kicad_sym")(options "")(descr "YACC1 bus connector, three rows"))\n'
        '\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.kicad_sym")(options "")(descr "IDT7134, 32-pin static RAM, Mini-DIN (gen_v40.py)"))\n'
        ')\n' % (N.BUSLIB, N.BUSLIB, LOCAL, LOCAL))
    open(os.path.join(HERE, "fp-lib-table"), "w").write(
        '(fp_lib_table\n\t(version 7)\n'
        '\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.pretty")(options "")(descr "FABC96R from the blank V3.2 card"))\n'
        '\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.pretty")(options "")(descr "MiniDIN6_MD-60SM (gen_v40.py)"))\n'
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
# 2. the schematic (2026-10-24): a hierarchical root and one wired sheet per functional block (tools/kicad/sch_wire.py)
#
# Each block's parts are placed by ELK and its nets drawn as wires; the bus signals (X1), power and the one-pin nets of a
# sheet keep a stub to a label or a power symbol. Every net of a sub-sheet ends in a hierarchical label and every one
# of those is a pin of the sheet's symbol on the root sheet, where a local label of the same name joins them: KiCad
# names each net after that root label, "/NAME", exactly the names the flat sheet gave and the board (and its Gerbers)
# carries. A net that reaches several sheets is wired on each to a label of its own (left: driven on another sheet;
# right: driven here).
import sch_wire as W                                      # noqa: E402

ROOT_UUID = gen_cf.ROOT_UUID
BUS = {n for n, conns in N.NETS.items() if any(r == "X1" for r, p in conns)} - {"VCC", "GND"}


def _u(ref, *units):
    return [(ref, u) for u in units]


def _all(*refs):
    return [(r, 1) for r in refs]


def _g(ref, *pins):
    """the units of a multi-unit part that have these pins (a gate by its output pin), resolved by _units()"""
    return [(ref, "pin:%s" % p) for p in pins]


def _whole(*refs):
    """every unit of each part but its power unit"""
    return [(r, "*") for r in refs]


def _units(S, items):
    """a sheet's items with the units named: (ref, n) as it is, (ref, "*") every unit but the power unit, (ref, "pin:N")
    the unit that has pin N"""
    out = []
    for ref, u in items:
        s = S.lib(gen_cf.SYM_SUB.get(N.PARTS[ref][1], N.PARTS[ref][1]))
        if u == "*":
            out += [(ref, k) for k in (s.units[:-1] if len(s.units) > 1 else s.units)]
        elif isinstance(u, str):
            ks = [k for k in s.units if any(p["num"] == u[4:] for p in s.pins.get(k, []))]
            if len(ks) != 1:
                raise SystemExit("schematic: %s has no single unit with pin %s" % (ref, u[4:]))
            out.append((ref, ks[0]))
        else:
            out.append((ref, u))
    return out


# (key, sheet name, title, items, the units drawn label-style beside the wired ones and where, note)
SHEETS = [
    ("bus", "Bus and ports", "BUS INTERFACE: THE BLOCK SELECT, THE SIX PORTS' STROBES, THE TWO CONTROL REGISTERS, THE STATUS",
     _whole("IC1", "SV1", "RN1", "IC2", "IC3") + _g("IC4", 3, 6) + _g("IC8", 2, 4, 6, 8, 12) + _g("IC9", 3) +
     _g("IC37", 3, 6) + _g("IC23", 3, 6) + _whole("IC5", "IC6", "IC7", "R10"),
     (_u("X1", 1, 2, 3), "left"),
     "X1: the YACC1 V3.2 bus (DIN 41612). IC1 compares ADDR15-12 with SV1 (5-6 fitted: the $D000 block). The block's\n"
     "two halves: TXTCE (IC37/A), the text RAM at $D000-$D7FF; GSEL (IC23/A), the graphics window at $D800-$DFFF, with\n"
     "its write strobe GWR and its read GRDOE. IC2 decodes IO-ADDR0-3: ports PA-PF = 1010-1111; IC3 / IC4 gate each\n"
     "select with a strobe. IC5 = control 1 (OUT PC), IC6 = control 2 (OUT PF), IC7 = the status (IN PC): the ID 0111."),
    ("crtc", "CRTC and clock", "THE 6845, THE DOT CLOCK, THE DOT COUNTER, THE 6845'S CLOCK, THE STAGE REGISTERS",
     _whole("IC10") + _g("IC22", 3) + _whole("OSC1", "R20", "IC11", "R21", "R22", "IC12") + _g("IC13", 2, 4, 6) +
     _whole("R23", "IC15", "IC16"), None,
     "IC11 counts the 25.175 MHz dot clock: D0-D3, the 16 dots of a count. The 6845's clock is D3 a dot late (IC12/A):\n"
     "it steps as dot 1 begins. IC15 / IC16, the stage, take MA0-9, DE, CURSOR, HSYNC and VSYNC as dot 0 begins (STG =\n"
     "NOT D3), 15 dots later: SA0-9, SDE, SCUR, SHS, SVS, steady for a count. IC12/B is SDE2, SDE as dot 8 begins.\n"
     "The 6845's bus side: -CS = PA or PB (IC9/A, sheet 2), E = -IO-RD XOR -IO-WR (IC22/A), RS = IO-ADDR0.\n"
     "R20-R23 (33 ohm): series termination of CK, D2, D3 and STG at their sources."),
    ("text", "Text", "THE TEXT RAM, THE CODE REGISTER, THE CHARACTER GENERATOR, THE TEXT SHIFTER, THE CURSOR FLAG",
     _whole("IC14", "IC17", "IC18", "IC19") + _u("IC20", 1) + _g("IC21", 6) + _g("IC22", 6) + _g("IC23", 8) + _g("IC13", 10), None,
     "The text RAM's display port reads SA9-0 then D3 (the half: 0 the left character, 1 the right). IC17 takes a\n"
     "code as dots 4 and 12 begin (D2), and IC20/A with it the cursor flag: SCUR AND (the half = CURH). The character\n"
     "generator IC18 is addressed by RA0-3, the code and the flag (A12: the cursor's forms); IC19 loads its byte 8\n"
     "dots after the code was taken (TLOAD, IC21/A: dots 3 and 11 with SDE2) and shifts it out bit 7 first as TDOT."),
    ("gfx", "Graphics RAM", "THE GRAPHICS RAM: ADDRESS MULTIPLEXERS, WRITE BUFFER, THE TWO READ PATHS, BYTE LATCH, SHIFTER",
     _whole("IC24", "IC25", "IC26", "IC27", "IC28", "RN2", "IC29", "IC30", "IC31", "IC32", "IC33", "R8") + _g("IC4", 8, 11), None,
     "IC24-IC27 give the RAM the display's address (DPAGE, RA3-0, SA9-0, D3) or the CPU's (CPAGE, PLANE3-0,\n"
     "ADDR10-0): SELCPU. IC32 takes the display's byte on D2's rise and IC33 loads it with the text's (TLOAD).\n"
     "IC29 puts the bus on the RAM's data lines while -WE is low. A window read: in slot mode from IC30, which takes\n"
     "the RAM's byte as each CPU slot ends (RDCK); in direct mode through IC31. These parts are the text-only\n"
     "build's left-off ones (with IC34, sheet 6)."),
    ("slot", "Slots", "THE SLOT LOGIC: SELCPU, THE WRITE FLIP-FLOP, THE -WE PULSE, THE RAM'S -OE, THE READ LATCH'S CLOCK",
     _g("IC13", 8) + _g("IC36", 3, 6) + _whole("IC34", "R9", "IC35") + _g("IC21", 8) + _g("IC38", 12, 8) +
     _g("IC37", 8, 11) + _g("IC23", 11), None,
     "SELCPU = D2 OR NOT GFX-ON: with GFX-ON the display has the RAM in dots 0-3 and 8-11, the CPU in 4-7 and 12-15;\n"
     "without it the CPU has it for good (direct mode). WRQ (IC34/A) takes the window's write strobe as a CPU slot\n"
     "begins; P56 (IC35/A) is high in dots 5-6 and 13-14. -WE = NAND(WRQ, P56) AND NAND(NOT GFX-ON, GWR): a whole\n"
     "pulse in slot mode, the strobe itself in direct mode. GOE = (WRQ OR NOT GFX-ON) AND SELCPU AND GRDOE.\n"
     "RDCK (IC35/B) is high in dots 8 and 0. IC34/B holds TXTONLY low: the graphics parts are fitted."),
    ("video", "Dots and syncs", "THE TWO LAYERS MIXED, THE DOT RETIMED, THE THREE GUNS, THE SYNCS, THE VGA SOCKET",
     _whole("IC39") + _g("IC38", 6) + _g("IC36", 8) + _u("IC20", 2) + _whole("R3", "R4", "R5") + _g("IC8", 10) +
     _g("IC22", 8, 11) + _whole("IC40") + _g("IC13", 12) + _g("IC36", 11) + _whole("R6", "R7", "J1"), None,
     "VIDN = NOR(text, graphics) OR (text AND graphics AND XOR); IC20/B puts it on the dot clock; each gun is\n"
     "NOR(VIDN, its off bit) through 470 ohm into the monitor's 75. HSYNC: the stage's, inverted, XOR POLH. VSYNC:\n"
     "IC40 takes SVS at each HSYNC and again at the next; the pulse to the monitor lasts from SVS's rise to the\n"
     "second HSYNC after it (VS2), whatever the 6845's own length; XOR POLV. Both negative after -RESET."),
    ("ps2", "PS2", "PS/2: ATMEGA328P, LATCHES ON PD / PE, STATUS, FTDI, -INT, RESET",
     _whole("IC41", "Y1", "C50", "C51", "R11", "C52", "J4", "R12") + _g("IC9", 6, 8, 11) + _whole("IC46") +
     _whole("IC42", "IC43", "IC44", "IC45", "JP1", "F1", "R13", "R14", "R15", "R16", "R17", "R18", "R19", "J2", "J3"), None,
     "IC41 runs embedded/video-ps2. OUT PD loads a command into IC43 (BUSY set), IN PE reads a byte from IC42 (FULL\n"
     "cleared), IN PD the status IC44: FULL, SRC, BUSY. -INT = INTREQ AND FULL (IC9/B) through IC46/D and JP1.\n"
     "The bus -RESET reaches MRST through IC9/C, IC46/E and IC46/F (open collector, R12): it only ever pulls MRST low.\n"
     "The V2.0 card's section, its nets unchanged."),
    ("power", "Power", "POWER UNITS, DECOUPLING, POWER LED, THE F PARTS' PULL-UP",
     _whole("R1", "LED1", "R2"), (None, "top"),
     "One 100 nF per IC beside its VCC pin (C48 at the oscillator, C49 at the ATmega's AVCC), C1 47 uF bulk. The bus\n"
     "supplies VCC and GND (X1, six pins each): the PWR_FLAGs. PU (R2, 1k) holds the 74F parts' unused inputs high.\n"
     "Spare: one inverter of IC8, one OR of IC36 (inputs tied), three of IC46, control 2's bit 4."),
]


def _power_units(S):
    out = []
    for ref in sorted(N.PARTS, key=lambda r: (len(r), r)):
        s = S.lib(gen_cf.SYM_SUB.get(N.PARTS[ref][1], N.PARTS[ref][1]))
        if ref.startswith("IC") and len(s.units) > 1:
            out.append((ref, s.units[-1]))
    return out + [(c, 1) for c in sorted(N.DECOUPLE, key=lambda r: int(r[1:]))] + \
        [("C1", 1)]


def sheet_uuid(key):
    return gen_cf.U("video-v4.0", "sheet", key, "instance")


def sheet_items(S):
    """[(key, name, title, wired items, label-style items, where, note)]"""
    out = []
    for key, name, title, items, fixed, note in SHEETS:
        fx, where = (fixed or ([], None))
        if key == "power":
            fx = _power_units(S)
        out.append((key, name, title, _units(S, items), _units(S, fx or []), where, note))
    return out


def pin_shape(D, sheet, net):
    """a hierarchical label's / sheet pin's shape: output where this sheet drives the net, input where it only reads it"""
    kinds = {D.pin_etype[k] for k in D.sheet_pins[sheet][net]}
    if kinds & {"output", "tri_state", "open_collector"}:
        return "output"
    if "bidirectional" in kinds:
        return "bidirectional"
    if kinds <= {"input"}:
        return "input"
    return "passive"


class SubSheet(W.WSheet):
    def write(self, path, file_uuid, title, paper, page):
        head = ['(kicad_sch', '\t(version 20260306)', '\t(generator "gen_v40")', '\t(generator_version "1.0")',
                '\t(uuid "%s")' % file_uuid, '\t(paper "%s")' % paper,
                '\t(title_block (title "YACC1 video card V4.0: %s") (date "%s") (rev "%s") (company "YACC1")'
                % (title, N.DATE, N.REV),
                '\t\t(comment 1 "Sheet %s of the video card V4.0 schematic (root: video-v4.0.kicad_sch)")' % page,
                '\t\t(comment 2 "Circuit source: v40_netlist.py; this sheet is generated by gen_v40.py")',
                '\t\t(comment 3 "Design note and theory: docs/cards/video-v4.md"))',
                '\t(lib_symbols']
        for libid in sorted(self.syms):
            head.append(self.syms[libid].text)
        head.append('\t)')
        open(path, "w").write("\n".join(head + self.out + ['\t(embedded_fonts no)', ')', '']))


def build_schematic():
    lib = Sheet0()
    specs = sheet_items(lib)
    D = W.Design(N, BUS, [(name, items + fx) for key, name, title, items, fx, where, note in specs], lib.lib, hier=True)
    placed = collections.defaultdict(set)
    for key, name, title, items, fx, where, note in specs:
        for ref, unit in items + fx:
            if unit in placed[ref]:
                raise SystemExit("schematic: %s unit %d on two sheets" % (ref, unit))
            placed[ref].add(unit)
    for ref in N.PARTS:
        if placed[ref] != set(lib.lib(gen_cf.SYM_SUB.get(N.PARTS[ref][1], N.PARTS[ref][1])).units):
            raise SystemExit("schematic: %s units placed %s" % (ref, sorted(placed[ref])))
    blocks, pwr, flg, stats = [], 0, 0, []
    pinhits = set()
    for page, (key, name, title, items, fx, where, note) in enumerate(specs, 2):
        su = sheet_uuid(key)
        gen_cf.ROOT_UUID = ROOT_UUID + "/" + su
        S = SubSheet("video-v4.0/" + key, lambda net: "hier", shape=lambda net, n=name: pin_shape(D, n, net))
        S.pwr, S.flg = pwr, flg
        ox, oy = 15.24, 30.48
        ext = None
        if fx:                                            # the label-style units: a row at the left or the top
            rows = W.label_style_rows(D, fx, S.label_kind, width=150.0 if where == "left" else 380.0)
            if where == "left":
                rows = []
                x = 0
                for ref, unit in fx:
                    n = W.Node(D, None, ref, unit, set(), S.label_kind)
                    rows.append((n, x - n.box.x0, -n.box.y0))
                    x += n.box.x1 - n.box.x0 + 2
            ext = W.draw_rows(S, rows, ox, oy)
        def measure(L, ext=ext, where=where):
            dry = SubSheet("dry", lambda net: "hier")
            e0, _ = W.draw(dry, D, L, items, 0, 0, hier=True)
            w, h = e0.x1 - e0.x0, e0.y1 - e0.y0
            if ext is not None:
                fw, fh = ext.x1 - ext.x0, ext.y1 - ext.y0
                w, h = (fw + 7.62 + w, max(fh, h)) if where == "left" else (max(fw, w), fh + 10.16 + h)
            return w + 5, h + (oy - 12.7) + 5, dry.nwires
        L, layering = W.best_layout(D, name, items, S.label_kind, measure) if items else (None, None)
        unclear = []
        if items and L is not None:
            lx, ly = (ext.x1 + 7.62, oy) if (ext and where == "left") else (ox, (ext.y1 + 10.16) if ext else oy)
            dry = SubSheet("dry", lambda net: "hier")          # a dry run finds the drawing's extent (name labels too)
            e0, _ = W.draw(dry, D, L, items, 0, 0, hier=True)
            lx = round((lx - e0.x0) / G) * G
            ly = round((ly - e0.y0) / G) * G
            e2, unclear = W.draw(S, D, L, items, lx, ly, hier=True)
            ext = e2 if ext is None else ext | e2
        elif items:
            rows = W.label_style_rows(D, items, S.label_kind, width=560.0)
            e2 = W.draw_rows(S, rows, ox, (ext.y1 + 10.16) if ext else oy)
            ext = e2 if ext is None else ext | e2
        if key == "power":
            y = round((ext.y1 + 10.16) / G) * G
            for k, kind in enumerate(("VCC", "GND")):
                x = ox + 5.08 + 15.24 * k
                S.wire(x, y, x + 7.62, y)
                S.power(kind, x, y, "U" if kind == "VCC" else "D")
                S.power(kind, x + 7.62, y, "U", flag=True)
            S.text(ox + 40.64, y - 1.27, "PWR_FLAGs: the bus supplies VCC and GND (X1, six pins each).", size=1.5)
            ext = ext | W.Box(ox, y - 6, ox + 140, y + 6)
        S.text(ox, 12.7, title, size=2.5, bold=True)
        S.text(ox, 17.78, note, size=1.5)
        name_w = max(len(l) for l in note.split("\n")) * 1.5 * 0.8
        w, h = max(ext.x1, ox + name_w) - ox + 5, ext.y1 - 12.7 + 5
        paper, pw, ph = W.paper_for(w, h)
        fname = "%s-%s.kicad_sch" % (P, key)
        S.write(os.path.join(HERE, fname), gen_cf.U("video-v4.0", "sheet", key, "file"), name, paper, page)
        pwr, flg = S.pwr, S.flg
        pinhits |= S.pinhits
        nets = sorted({n for n in D.sheet_pins[name] if n not in ("VCC", "GND")})
        blocks.append((key, name, title, fname, su, page, [(n, pin_shape(D, name, n)) for n in nets]))
        stats.append((name, paper, len(items) + len(fx), S.nwired, S.nwires - S.nstubs, S.nstubs, S.nlabels, S.njunctions,
                      ("wired, ELK layering " + layering) if L is not None else "LABEL STYLE", unclear))
    gen_cf.ROOT_UUID = ROOT_UUID
    # a package's pin that its symbol does not draw (pins 3 and 11 of a 74x21: no connection inside) is left open
    drawn = lambda r: {q["num"] for ps in lib.lib(gen_cf.SYM_SUB.get(N.PARTS[r][1], N.PARTS[r][1])).pins.values() for q in ps}
    nopin = {(r, p) for r, p in gen_cf.NC if p not in drawn(r)}
    missing = [k for k in list(gen_cf.NETOF) + list(gen_cf.NC) if k not in pinhits and k not in nopin]
    if missing:
        raise SystemExit("schematic: pins not drawn: %s" % missing)
    write_root(blocks)
    return stats, lib


class Sheet0(gen_cf.Sheet):
    """only a symbol cache (the sub-sheets share it)"""


def write_root(blocks):
    """the root sheet: one sheet symbol per block, a pin for every net of the block and at each pin a local label: the
    net's name (/NAME). Nets that reach other sheets: inputs on the left, outputs on the right. A net drawn on this
    sheet only has a pin on both sides, below them (the same name twice): KiCad's ERC takes a root label for
    connected only when another label of its name stands on the root sheet (a pin's sheet does not count)"""
    out, nl = [], 0
    eff = "(effects (font (size 1.27 1.27))"
    X, Y = 25.4, 76.2
    rowh = 0
    nblocks = collections.Counter(n for b in blocks for n, s in b[6])
    for key, name, title, fname, su, page, pins in blocks:
        left = [(n, s) for n, s in pins if nblocks[n] > 1 and s in ("input", "passive")]
        right = [(n, s) for n, s in pins if nblocks[n] > 1 and s not in ("input", "passive")]
        local = [(n, s) for n, s in pins if nblocks[n] == 1]
        lw = max([len(n) for n, s in left + local] + [4]) * 1.0 + 9
        rw = max([len(n) for n, s in right + local] + [4]) * 1.0 + 9
        w = round((max([len(n) for n, s in pins] + [10]) * 2 * 1.0 + 12.7) / G) * G
        top = max(len(left), len(right))
        rows = top + (1 + len(local) if local else 0)
        h = (rows + 1) * G
        x = round((X + lw) / G) * G
        if x + w + rw > 820:
            X, Y, rowh = 25.4, Y + rowh + 20.32, 0
            x = round((X + lw) / G) * G
        y = Y
        L = ['\t(sheet (at %s %s) (size %s %s) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) '
             '(fields_autoplaced yes)' % (gen_cf.f(x), gen_cf.f(y), gen_cf.f(w), gen_cf.f(h)),
             '\t\t(stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0000)) (uuid "%s")' % su,
             '\t\t(property "Sheetname" %s (at %s %s 0) %s (justify left bottom)))'
             % (gen_cf.q(name), gen_cf.f(x), gen_cf.f(y - 0.7), eff),
             '\t\t(property "Sheetfile" %s (at %s %s 0) %s (justify left top)))'
             % (gen_cf.q(fname), gen_cf.f(x), gen_cf.f(y + h + 0.6), eff)]
        placed = [("L", i, n, s, "") for i, (n, s) in enumerate(left)] + \
                 [("R", i, n, s, "") for i, (n, s) in enumerate(right)]
        for i, (n, s) in enumerate(local):
            placed += [("L", top + 1 + i, n, s, ""), ("R", top + 1 + i, n, s, "2")]
        if local:
            out.append('\t(polyline (pts (xy %s %s) (xy %s %s)) (stroke (width 0.1524) (type dash)) (uuid "%s"))'
                       % (gen_cf.f(x), gen_cf.f(y + (top + 1) * G), gen_cf.f(x + w), gen_cf.f(y + (top + 1) * G),
                          gen_cf.U("video-v4.0", "rline", key)))
        for side, i, n, s, k in placed:
            py = y + (i + 1) * G
            px = x if side == "L" else x + w
            L.append('\t\t(pin %s %s (at %s %s %d) %s (justify %s)) (uuid "%s"))'
                     % (gen_cf.q(n), s, gen_cf.f(px), gen_cf.f(py), 180 if side == "L" else 0, eff,
                        "left" if side == "L" else "right", gen_cf.U("video-v4.0", "spin", key, n + k)))
            ex = px - 2 * G if side == "L" else px + 2 * G
            out.append('\t(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid "%s"))'
                       % (gen_cf.f(px), gen_cf.f(py), gen_cf.f(ex), gen_cf.f(py),
                          gen_cf.U("video-v4.0", "rw", key, n + k)))
            ang, just = (180, "right bottom") if side == "L" else (0, "left bottom")
            out.append('\t(label %s (at %s %s %d) %s (justify %s)) (uuid "%s"))'
                       % (gen_cf.q(n), gen_cf.f(ex), gen_cf.f(py), ang, eff, just,
                          gen_cf.U("video-v4.0", "rl", key, n + k)))
            nl += 1
        L += ['\t\t(instances (project "%s" (path "/%s" (page "%d"))))' % (P, ROOT_UUID, page), '\t)']
        out.append("\n".join(L))
        X = x + w + rw + 10
        rowh = max(rowh, h)
    note = ["The video card V4.0, one sheet per functional block:"]
    note += ["  sheet %d  %-12s %s" % (page, name, title) for key, name, title, fname, su, page, pins in blocks]
    note += ["", "Every net of a sheet is a pin of its sheet symbol here, and the local label at each pin names the net",
             "(/NAME, the names on the board). Above the dashed line: the nets the sheet shares with other sheets (left:",
             "it reads them, right: it drives them). Below it: the nets drawn on that sheet only, a pin on each side",
             "(KiCad's ERC counts a root label as connected only when another label of its name is on the root sheet).",
             "VCC and GND are power symbols on the sheets."]
    out.append('\t(text %s (exclude_from_sim no) (at 25.4 15.24 0) (effects (font (size 1.5 1.5)) (justify left top)) '
               '(uuid "%s"))' % (gen_cf.q("\n".join(note)), gen_cf.U("video-v4.0", "rootnote")))
    paper = W.paper_for(X - 25.4, Y + rowh + 10 - 22.86)[0]
    head = ['(kicad_sch', '\t(version 20260306)', '\t(generator "gen_v40")', '\t(generator_version "1.0")',
            '\t(uuid "%s")' % ROOT_UUID, '\t(paper "%s")' % paper,
            '\t(title_block (title "YACC1 video card V4.0") (date "%s") (rev "%s") (company "YACC1")' % (N.DATE, N.REV),
            '\t\t(comment 1 "6845 at 16 dots a count on ports PA / PB, 640 x 480 VGA, text RAM and graphics window in the $D000 block, PS/2 on PD / PE")',
            '\t\t(comment 2 "Circuit source: v40_netlist.py; these sheets are generated by gen_v40.py")',
            '\t\t(comment 3 "Design note and theory: docs/cards/video-v4.md"))',
            '\t(lib_symbols)']
    tail = ['\t(sheet_instances (path "/" (page "1")))', '\t(embedded_fonts no)', ')', '']
    open(os.path.join(HERE, P + ".kicad_sch"), "w").write("\n".join(head + out + tail))
    return nl


def check_schematic_netlist(netfile):
    """the schematic's exported netlist = v40_netlist.NETS (label nets come back as /NAME)"""
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
        print("  net %s: schematic %s, v40_netlist %s" % (n, sorted(got.get(n, ()))[:6], sorted(want.get(n, ()))[:6]))
    print("schematic netlist vs v40_netlist.py: %s (%d nets)" % ("MATCH" if not bad else "%d DIFFER" % len(bad), len(want)))
    return not bad


def sch():
    probs = N.check()
    if probs:
        raise SystemExit("v40_netlist.check():\n" + "\n".join(probs))
    why = W.elk_ready()
    if why:
        raise SystemExit("gen_v40.py sch: " + why)
    local_libs()
    stats, lib = build_schematic()
    tot = [0] * 5
    for name, paper, nitems, nnets, nw, ns, nlab, nj, how, unclear in stats:
        print("  sheet %-12s %s  %3d units, %3d nets wired (%4d wires), %4d stubs, %3d labels, %3d junctions  %s%s" % (
            name, paper, nitems, nnets, nw, ns, nlab, nj, how, ("  (name labels not clear: %s)" % ", ".join(unclear))
            if unclear else ""))
        tot = [a + b for a, b in zip(tot, (nnets, nw, ns, nlab, nj))]
    rw, rl, rj = W.count(os.path.join(HERE, P + ".kicad_sch"))
    print("schematic: %s (root: %d sheet pins and labels) + %d sheets: %d nets wired (%d wires), %d stubs, %d labels, "
          "%d junctions" % ((P + ".kicad_sch", rl, len(stats)) + tuple(tot)))


# ---------------------------------------------------------------------------------------------------------------------
# 3. the project rules (as gen_v13.py's) and the board
DRU = G13.DRU.replace("video card v1.3", "video card V4.0").replace("gen_v13.py", "gen_v40.py")


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
    pro["sheets"] = [[ROOT_UUID, "Root"]] + [[sheet_uuid(k[0]), k[1]] for k in SHEETS]
    json.dump(pro, open(os.path.join(HERE, P + ".kicad_pro"), "w"), indent=2)
    open(os.path.join(HERE, P + ".kicad_dru"), "w").write(DRU)
    print("project: Default %.2f mm / %.2f mm, vias %.1f / %.1f mm; class Power = GND, VCC (planes)" % (
        R["track"], R["clearance"], R["via"], R["via_drill"]))


# --- placement: (x, y, rotation) of each footprint's origin (pad 1 of every DIP / header / resistor / capacitor) --------
# THE PLACEMENT (2026-11-12), on the 250 mm outline. The ICs stand in columns, pin 1 at the top left (two parts turned
# round, pin 1 at the bottom right: ~), a capacitor beside each VCC pin. Left to right: the port decode and the block
# select by the bus connector; the character generator over the text RAM (turned: its CPU port towards the bus, its
# display port towards the next column); the code register and the stage, beside the text RAM's display port on one
# side and the 6845's MA pins on the other; the graphics RAM over the 6845; the address multiplexers; the RAM's
# latches and buffers; the two shifters; the clock (the counter at the bottom, over the oscillator); the slot logic;
# the dots' and syncs' gates; the control registers and the status; the PS/2 latches; the ATmega; the front edge with
# the VGA socket, the two PS/2 jacks, the INT jumper, the FTDI header and the LED.
# The first placement had the 6845 and the graphics RAM between the text RAM and the code register: its first routing
# left the code's lines VD5-VD7 unrouted in the 5 mm channel between the two columns of 600-mil sockets.
# Since the design review (2026-11-13, V4-2) the clock's column stands between the multiplexers and the RAM's latches
# (it was two columns further right, 84 mm from the stage and the code register that D2 and STG clock), and CK, D2, D3
# and STG each leave their source through a series resistor (R20-R23) standing beside it. Freerouting does not know a
# clock from any other net (how long the four came out differed from one component order to the next), so they are
# laid first, here: clockroute(), below.
GAP = 6.3                                                 # between two chips in a column, end pin to end pin
PITCH = 15.24                                             # from one column of 300-mil sockets to the next (V2.0: 14)
PLACE = {}


def ic_size(ref):
    fp = N.PARTS[ref][2]
    n = int(re.search(r"DIP-(\d+)", fp).group(1))
    w = 22.86 if "W22.86" in fp else 15.24 if "W15.24" in fp else 7.62
    return n, w


def stack(x, y, *refs):
    """a column of DIPs from y down, the first's top left pin at (x, y); a reference with a leading ~ is turned 180
    degrees (its pin 1 at the bottom right); -> the y after the last"""
    for r in refs:
        turned, r = r.startswith("~"), r.lstrip("~")
        n, w = ic_size(r)
        h = (n // 2 - 1) * G
        PLACE[r] = (x + w, y + h, 180) if turned else (x, y, 0)
        y += h + GAP
    return y


TOP = 15.0
COLUMNS = [("N0", ("IC2", "IC3", "IC4", "IC1")),                 # port decode, the strobes, the block select (over SV1)
           ("W0", ("IC18", "~IC14")),                            # character generator, text RAM
           ("N1", ("IC8", "IC17", "IC15", "IC16")),              # the bus's inverters, the code register, the stage
           ("W1", ("IC28", "IC10")),                             # the graphics RAM, the 6845
           ("N2", ("IC24", "IC25", "IC26", "IC27")),             # the graphics address multiplexers
           ("N5", ("IC21", "IC13", "IC12", "IC11")),             # the load, the inverters, the 6845's clock, the counter
           ("N3", ("IC32", "IC30", "IC29", "IC34")),             # byte latch, read latch, write buffer, WRQ
           ("N4", ("IC31", "IC33", "IC19", "IC20")),             # direct-mode buffer, the two shifters, CURF / the retimed dot
           ("N6", ("IC35", "IC36", "IC37", "IC38")),             # P56 and RDCK, the slot logic's gates
           ("N7", ("IC39", "IC22", "IC23", "IC40")),             # the guns, the XORs, the ANDs, the vertical sync
           ("N8", ("IC5", "IC6", "IC7", "IC9")),                 # control 1, control 2, the status, the bus-side ANDs
           ("N9", ("IC42", "IC43", "IC44", "IC45")),             # the PS/2 latches, status and flags
           ("N10", ("IC46", "~IC41"))]                           # the 7416, the ATmega (its crystal pins towards the front)
COLX = {}
_x = 32.0
for _name, _refs in COLUMNS:
    COLX[_name] = _x
    stack(_x, TOP, *_refs)
    _x += PITCH + (7.62 if _name.startswith("W") else 0.0)
GAPX = lambda col: COLX[col] + 7.62 + 3.2                 # the capacitors' line in the gap right of a 300-mil column


def pin_xy(ref, pin):
    """a DIP's pin on the board (rotation 0 or 180)"""
    x, y, rot = PLACE[ref]
    n, w = ic_size(ref)
    dx, dy = (0.0, (pin - 1) * G) if pin <= n // 2 else (w, (n - pin) * G)
    return (x + dx, y + dy) if rot == 0 else (x - dx, y - dy)


def cap_at(ref, pin, gnd):
    """a decoupling capacitor standing 3.2 mm outside a VCC pin, its other lead towards the GND pin"""
    x, y = pin_xy(ref, pin)
    n, w = ic_size(ref)
    left = min(pin_xy(ref, 1)[0], pin_xy(ref, n)[0])
    out = -3.2 if abs(x - left) < 0.01 else 3.2
    return (x + out, y, 270 if pin_xy(ref, gnd)[1] >= y else 90)


for _cap, _ic in N.DECOUPLE.items():
    if _ic.startswith("IC"):
        PLACE[_cap] = cap_at(_ic, N.POWER_PINS[_ic][0][0], N.POWER_PINS[_ic][1][0])
_ox, _oy = COLX["N2"] + 1.1, 119.0                        # the oscillator lying under the multiplexers and the counter:
PLACE["OSC1"] = (_ox, _oy, 0)                             # pin 1 bottom left, its output (pin 8) top right, under IC11
PLACE["C48"] = (COLX["W1"] + 15.24 + 3.2, 112.0, 270)     # at the oscillator's VCC pin (14, top left)
PLACE["C49"] = (COLX["N10"] - 3.2, 50.2, 270)             # the ATmega's AVCC (pin 20), a little below the pin: clear of
                                                          # IC43's capacitor in the same gap
X1F = X1R                                                 # the front edge
_a, _b = COLX["N10"] + 14.4, COLX["N10"] + 17.9           # two lines of standing resistors between the ATmega's
                                                          # column and the jacks
PLACE.update({
    # the bus side: the block jumper under the block select, its pull-ups beside it, the bulk capacitor
    "SV1": (33.0, 106.0, 0), "RN1": (31.5, 120.6, 0), "C1": (53.0, 119.5, 0),
    # the RAM's data pull-ups standing beside it
    "RN2": (COLX["W1"] + 15.24 + 3.2, 21.5, 270),
    # one resistor each beside the chip it belongs to, in the capacitors' line: GDOT's pull-down (IC33), WRQ's (IC34),
    # TXTONLY's pull-up (IC7), PU (the F parts)
    "R8": (GAPX("N4"), 50.0, 270), "R9": (GAPX("N3"), 108.3, 270), "R10": (GAPX("N8"), 79.2, 270),
    "R2": (GAPX("N5"), 63.9, 270),
    # the clocks' series resistors, each beside its source: R20 from the oscillator's pin 8 up to the counter's clock
    # (its pin 1 at the bottom), R21 and R22 at the counter's QC and QD, R23 at IC13's pin 2
    "R20": (GAPX("N2"), 104.0, 90), "R21": (GAPX("N5"), 85.0, 270), "R22": (GAPX("N5"), 95.0, 270),
    "R23": (GAPX("N2"), 45.0, 270),
    # the front edge: the VGA socket, its three video and two sync resistors lying left of it
    # (turned 90: the footprint's mating face, its +y, towards the edge; the socket then lies from y 10.8 to 42.8)
    "J1": (X1F - DE15_EDGE, 22.5, 90),
    "R3": (_a + 0.5, 14.0, 0), "R4": (_a + 0.5, 17.2, 0), "R5": (_a + 0.5, 20.4, 0), "R6": (_a + 0.5, 23.6, 0),
    "R7": (_a + 0.5, 26.8, 0),
    # the ATmega's crystal and its capacitors, right of its pins 9 and 10
    "Y1": (_a + 1.5, 44.0, 270), "C50": (_b + 3.0, 42.5, 270), "C51": (_b + 3.0, 48.2, 270),
    # the two PS/2 jacks with their pull-ups and the fuse
    "J2": (X1F, 58.0, 0), "J3": (X1F, 76.0, 0),
    "R16": (_a, 55.0, 270), "R17": (_b, 55.0, 270), "F1": (_a + 0.8, 66.3, 0), "R18": (_a, 71.0, 270), "R19": (_b, 71.0, 270),
    # under the ATmega: its reset pull-up, the DTR capacitor, RESETH's pull-up; the latches' pull-ups, INTREQ's pull-down
    # (kept to the left under the ATmega: the channel right of them, down from its pins 1-6 to the FTDI header, stays
    # open - the first routing left FTX unrouted there)
    "R11": (COLX["N10"] + 0.6, 82.0, 270), "C52": (COLX["N10"] + 4.4, 82.0, 270), "R12": (COLX["N10"] + 8.2, 82.0, 270),
    "R13": (COLX["N10"] + 0.6, 97.0, 270), "R14": (COLX["N10"] + 4.4, 97.0, 270), "R15": (COLX["N10"] + 8.2, 97.0, 270),
    # the INT jumper, the FTDI header and the LED at the front edge
    "JP1": (X1F - 2.2, 86.6, 0), "J4": (X1F - 2.2, 94.5, 0),
    "LED1": (X1F - 3.5, 113.5, 90), "R1": (X1F - 3.5, 120.0, 180),
})


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
    # the VGA socket's ground pins stand 2.29 mm apart among its other pins: thermal reliefs leave the GND plane no
    # way to three of them (the first routing's DRC). Connected solid, as X1's supply pins are
    for p in fps["J1"].Pads():
        if p.GetNetname() == "GND":
            p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        if p.GetNumber() != "SH":                       # the fifteen signal holes, for the Kycon part's pins
            p.SetDrillSize(VECTOR2I(FM(DE15_DRILL), FM(DE15_DRILL)))
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
    tb = b.GetTitleBlock()
    tb.SetTitle("YACC1 video card V4.0"); tb.SetDate(N.DATE); tb.SetRevision(N.REV); tb.SetCompany("YACC1")
    tb.SetComment(0, "%.0f mm, four layers: gen_v40.py and build.sh from v40_netlist.py" % LENGTH)
    unclear = silk_place(b, silk_texts(b))
    pcbnew.SaveBoard(out, b)
    print("silk: every reference and legend placed clear of other silk, the pads and the edge%s" % (
        "" if not unclear else " except %s" % ", ".join(unclear)))
    G13.refill(out)
    print("board %s: %d footprints placed, %d pads on nets, %.2f x %.2f mm, 4 layers (In1 GND, In2 VCC planes)" % (
        os.path.basename(out), len(fps), n, X1R - X0, Y1B - Y0))


SILK_H, SILK_W = 1.0, 0.15       # every text on the silk: JLCPCB's standard characters (>= 1.0 mm high, >= 0.15 mm strokes)
# the legends: (text, x, y, size) left-justified at (x, y), or (text, x, y, size, angle) centred on (x, y)
_lx = COLX["N6"] - 0.5
SILK = [("YACC1 Video Card V4.0", _lx, 100.3, 1.5), ("cottageworker.com", _lx, 103.6, 1.0),
        ("TEXT-ONLY BUILD: NO IC24-IC34,", _lx, 106.2, 1.0), ("RN2, C25-C35", _lx, 108.3, 1.0),
        ("1", _ox - 4.4, _oy + 0.2, 1.2, 0),                # the oscillator's pin 1 (V4-12): turned round it dies
        ("KEYBOARD (PURPLE)", X1R - 14.6, 58.0, 1.0, 90), ("MOUSE (GREEN)", X1R - 14.6, 76.0, 1.0, 90)]
_j4x, _j4y = PLACE["J4"][:2]
SILK += [(t, _j4x - 9.5, _j4y + 2.54 * k, 1.0) for k, t in enumerate(("1 GND (BLK)", "CTS", "VCC nc", "TXD", "RXD", "DTR"))]
# the jumpers' positions (the board-layout rules: every position labelled with what it selects; the function itself
# stands beside the reference, COMPANION)
_sv1x, _sv1y = PLACE["SV1"][:2]                           # the four positions, top to bottom: A15, A14, A13, A12
SILK += [("A%d" % (15 - k), _sv1x + 5.9, _sv1y + 2.54 * k + 0.05, 1.0, 0) for k in range(4)]
SILK += [("ON=0", _sv1x + 1.3, _sv1y - 2.9, 1.0, 0)]
_jp1x, _jp1y = PLACE["JP1"][:2]
SILK += [("ON: PS/2 -INT", _jp1x - 13.0, _jp1y + 1.3, 1.0)]
# the text beside a reference (the board-layout rules): each IC's type, the LED's and the jumpers' function, every
# resistor's, network's, capacitor's and crystal's value, the oscillator's frequency
TYPE_SHORT = {"IC10": "68B45", "IC28": "AS6C1008-55", "IC41": "ATmega328P"}
VALUE_SHORT = {"C1": "47u", "F1": "0.5A"}
COMPANION = dict({r: TYPE_SHORT.get(r, v[0]) for r, v in N.PARTS.items() if r.startswith("IC")},
                 **{r: VALUE_SHORT.get(r, v[0]) for r, v in N.PARTS.items() if re.match(r"(RN?|C|Q|Y|F)\d", r)},
                 OSC1="25.175MHz", LED1="PWR", JP1="INT-EN", SV1="BLOCK", X1="DIN41612 96", J1="VGA", J4="FTDI")
# the parts whose companion is the footprint's own value field, shown on the silk: their library footprints have no
# courtyard, so a free text cannot be told to belong to them (pcb-check's LABELS), but their own field can
VALUE_FIELD = {"X1"}
UNCONNECTED = {}                                         # filled from the schematic's netlist by board()


def silk_texts(b):
    """the board's own silkscreen texts written afresh: every legend of SILK and one text per COMPANION (placed by
    silk_place()); the old ones removed first, so a finished board takes the current lists. -> {ref: companion text}"""
    import pcbnew
    from pcbnew import VECTOR2I
    FM = pcbnew.FromMM
    for d in list(b.GetDrawings()):
        if d.GetClass() == "PCB_TEXT" and d.GetLayer() == pcbnew.F_SilkS:
            b.Delete(d)

    def text(s, size):
        t = pcbnew.PCB_TEXT(b)
        t.SetText(s); t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(VECTOR2I(FM(size), FM(size))); t.SetTextThickness(FM(max(SILK_W, size * 0.15)))
        b.Add(t)
        return t

    for s, x, y, size, *ang in SILK:
        t = text(s, size)
        if ang:                                           # centred on (x, y), turned by ang[0]
            t.SetTextAngleDegrees(ang[0])
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER); t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        else:
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        t.SetPosition(VECTOR2I(FM(x), FM(y)))
    comp = {}
    fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
    for ref, s in sorted(COMPANION.items()):
        if ref in VALUE_FIELD:
            t = comp[ref] = fps[ref].Value()
            assert t.GetText() == s, (ref, t.GetText())
            t.SetLayer(pcbnew.F_SilkS); t.SetVisible(True)
            t.SetTextSize(VECTOR2I(FM(SILK_H), FM(SILK_H))); t.SetTextThickness(FM(SILK_W))
        else:
            t = comp[ref] = text(s, SILK_H)
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER); t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    return comp


def silk_place(b, comp=None):
    """R2-9 (2026-10-23), the board-layout rules (2026-10-24): the silkscreen texts placed clear of each other, of every
    footprint's silk graphics, of the pads, of the board edge and of every part's body - its own too: a reference stays
    readable with the part fitted. A DIP's body is its socket's outline (socket_check(): the widest stamped sockets),
    a part without a Fab outline (J1) its silk and pads, X1 its whole housing. The legends (SILK) stay where they are
    unless they meet something, then move by up to 3 mm; each reference goes to the free spot nearest its footprint's
    library default (above, below, beside the body, turned if need be; an IC's: above it, else below it, else turned in
    the gap at its right, then at its left), on one line with its companion text (an IC's
    type, a jumper's or the LED's function: "IC30 74LS138", read as one) or, for the non-ICs, with the companion under
    it; a spot beside the part (along its own side) is taken before one that reaches past it. A part's value (R, RN, C,
    Q, Y, F: 2026-11-03) that finds no such spot stands apart from the reference, beside the part or next to the
    reference, else in a legend ("C3 C20: 100n", LEGEND); a passive's texts stand nearer their own part than any other
    non-IC part; the parts that needed this are placed earlier in another round (SPLIT, LEGEND). Geometry by the texts'
    ink and the shapes' bounding boxes (a slanted line as a chain of small boxes), so it is a little stricter than
    KiCad's DRC. X2's library text "F09" goes to the Fab layer; X1's pin numbers "1" and "32" are raised to 0.8 mm /
    0.15 mm (at 1.0 mm "32" meets the housing's outline).
    -> the texts left where they still meet something"""
    import math
    import pcbnew
    from pcbnew import VECTOR2I
    MM, FM = pcbnew.ToMM, pcbnew.FromMM
    CLR_SILK, CLR_PAD, EDGE, CLR_IC = 0.15, 0.2, 0.4, 1.0
    comp = comp or {}

    def bx(bb, g=0.0):
        return (MM(bb.GetLeft()) - g, MM(bb.GetTop()) - g, MM(bb.GetRight()) + g, MM(bb.GetBottom()) + g)

    def ink(t, g=0.0):                                  # a text's strokes, not its (taller) text box
        return bx(t.GetEffectiveTextShape().BBox(), g)

    def hit(a, c):
        return a[0] < c[2] and c[0] < a[2] and a[1] < c[3] and c[1] < a[3]

    def apart(a, c):                                    # the distance between two boxes (0 when they meet)
        return math.hypot(max(c[0] - a[2], a[0] - c[2], 0.0), max(c[1] - a[3], a[1] - c[3], 0.0))

    def union(qs):
        return (min(q[0] for q in qs), min(q[1] for q in qs), max(q[2] for q in qs), max(q[3] for q in qs))

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
                if it.GetTextThickness() < FM(SILK_W):
                    it.SetTextThickness(FM(SILK_W))
                fixed.append(ink(it, CLR_SILK))
            else:
                fixed.extend(shape_boxes(it, CLR_SILK))
    bodies, outline = {}, {}                            # no text on any part's body; outline: what a text stands beside
    fabs = {}                                           # the Fab outline alone: no text's box on it (pcb-check's LABELS)
    for fp in fps:
        ref = fp.GetReference()
        fab = [bx(it.GetBoundingBox()) for it in fp.GraphicalItems()
               if it.GetLayer() == pcbnew.F_Fab and it.GetClass() != "PCB_TEXT"]
        silk = [bx(it.GetBoundingBox()) for it in fp.GraphicalItems()
                if it.GetLayer() == pcbnew.F_SilkS and it.GetClass() != "PCB_TEXT"]
        pads = [bx(p.GetBoundingBox()) for p in fp.Pads()]
        body = fab
        if "DIP-" in fp.GetFPIDAsString():              # the socket (socket_check's walls)
            xs = [MM(p.GetPosition().x) for p in fp.Pads()]
            ys = [MM(p.GetPosition().y) for p in fp.Pads()]
            ax, ay = (END_WALL, SIDE_WALL) if max(xs) - min(xs) > max(ys) - min(ys) else (SIDE_WALL, END_WALL)
            ax, ay = ax + 0.2, ay + 0.2                 # (the review's V4-14: a text's strokes stood up to 0.13 mm inside)
            body = fab + [(min(xs) - ax, min(ys) - ay, max(xs) + ax, max(ys) + ay)]
        elif ref in ("X1", "J1", "X2"):                 # the housings: their silk and pads (X1: also 2.5 mm past its
            body = fab + silk + pads                    # ends, the DIN 41612 housing's ends beyond its silk, with room)
            if ref == "X1":
                u = union(body)
                body = [(u[0], u[1] - 2.5, u[2], u[3] + 2.5)]
        if body:
            bodies[ref] = union(body)
        if fab:
            fabs[ref] = union(fab)
        outline[ref] = union(pads + silk + body)

    def free(r, t=None):                                # r: a text's ink; t: the text, whose whole box (KiCad's, taller
        if r[0] < X0 + EDGE or r[1] < Y0 + EDGE or r[2] > X1R - EDGE or r[3] > Y1B - EDGE:   # than the ink) stays off
            return False                                # every body (2026-11-10: pcb-check's LABELS measures that box)
        if any(hit(r, q) for q in bodies.values()):
            return False
        if t is not None and any(hit(bx(t.GetBoundingBox()), q) for q in fabs.values()):
            return False
        return not any(hit(r, q) for q in fixed) and not any(hit(r, q) for q in placed)

    def put(t, x, y, a):
        t.SetTextAngleDegrees(a)
        t.SetPosition(VECTOR2I(FM(x), FM(y)))

    compids = {c.m_Uuid.AsString() for c in comp.values()}
    for d in b.GetDrawings():                           # 1. the legends, near their own place
        if d.GetClass() != "PCB_TEXT" or d.GetLayer() != pcbnew.F_SilkS or d.m_Uuid.AsString() in compids:
            continue
        x, y, a = MM(d.GetPosition().x), MM(d.GetPosition().y), d.GetTextAngleDegrees()
        offs = sorted({(i * 0.25, j * 0.25) for i in range(-12, 13) for j in range(-12, 13)},
                      key=lambda o: (abs(o[0]) + abs(o[1]), abs(o[1]), o))
        for i, j in offs:
            put(d, x + i, y + j, a)
            if free(ink(d), d):
                break
        else:
            put(d, x, y, a)
            unclear.append(d.GetText())
        placed.append(ink(d, CLR_SILK))

    libfp = {}

    def default(fp):                                    # the library footprint's reference, where the board has it
        fpid = fp.GetFPIDAsString()
        if fpid not in libfp:
            lib, name = fpid.split(":")
            d = os.path.join(HERE, lib + ".pretty") if lib in (N.BUSLIB, LOCAL) else os.path.join(KFP, lib + ".pretty")
            libfp[fpid] = pcbnew.FootprintLoad(d, name)
        f = libfp[fpid]
        f.SetOrientation(fp.GetOrientation()); f.SetPosition(fp.GetPosition())
        r = f.Reference()
        return MM(r.GetPosition().x), MM(r.GetPosition().y), r.GetTextAngleDegrees() % 180

    def extent(t, a):                                   # the ink box of t at angle a, centred on (0, 0)
        put(t, 0, 0, a)
        return ink(t)

    SIDES = {"above": 0.0, "below": 2.0, "right": 4.0, "left": 6.0}
    del SPLIT[:]                                        # the parts whose value stands apart from the reference
    # 2. the references (ICs, then the others with a companion). A part that found no room beside it (far) is placed
    # earlier in the next round, before the neighbours that took its room; the round with the fewest such parts is kept.
    placed0, unclear0 = list(placed), list(unclear)

    def round_(first):
        order = lambda fp: (not fp.GetReference().startswith("IC"), fp.GetReference() not in first,
                            first.index(fp.GetReference()) if fp.GetReference() in first else 0,
                            fp.GetReference() not in comp, fp.GetReference())
        placed[:], unclear[:], far = list(placed0), list(unclear0), []   # far: not on one line / stacked
        del SPLIT[:]
        LEGEND.clear()
        for fp in sorted(fps, key=order):
            ref = fp.GetReference()
            t = fp.Reference()
            if ref == "J1":                                 # the RCA library footprint hides its reference
                t.SetVisible(True); t.SetLayer(pcbnew.F_SilkS)
            if not t.IsVisible() or t.GetLayer() != pcbnew.F_SilkS:
                continue
            t.SetTextSize(VECTOR2I(FM(SILK_H), FM(SILK_H))); t.SetTextThickness(FM(SILK_W))
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
            t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
            c = comp.get(ref)
            o = outline[ref]
            x0, y0, x1, y1 = o
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            dx, dy, da = default(fp)
            isic = ref.startswith("IC")

            def spots(U, a, pen, pc):                       # the places of a block U (ink box round its anchor text)
                out = []                                    # (cost, angle, (anchor x, y), (companion x, y) or None, beside)
                W, H = U[2] - U[0], U[3] - U[1]
                for gap in (0.2, 0.6, 1.2, 2.0):
                    for k in range(-40, 41):
                        s = k * 0.5
                        for side, bx0, by0 in (("above", cx + s - W / 2, y0 - gap - H), ("below", cx + s - W / 2, y1 + gap),
                                               ("left", x0 - gap - W, cy + s - H / 2), ("right", x1 + gap, cy + s - H / 2)):
                            along = "x" if side in ("above", "below") else "y"
                            if isic and (a == 0) != (along == "x"):
                                continue                    # an IC's reference and type run along the side they are on
                            # beside the part: the block within the outline's span on that side (1 mm over at most)
                            span, size = (x1 - x0, W) if along == "x" else (y1 - y0, H)
                            over = max(0.0, abs(s) - max(0.0, (span - size) / 2) - 1.0)
                            rx, ry = bx0 - U[0], by0 - U[1]
                            if isic:                        # an IC: above it, else below, else in the gap at its right, left
                                cost = SIDES[side] + 0.2 * abs(s) + gap + pen
                            else:                           # the rest: nearest the library's place
                                cost = math.hypot(bx0 + W / 2 - dx, by0 + H / 2 - dy) + (1.5 if a != da else 0) + pen
                            cost += 10 * min(over, 1.0) + over
                            out.append((cost, a, (rx, ry), (rx + pc[0], ry + pc[1]) if pc else None, over == 0))
                return out

            cands, alone, lone = [], [], []                 # the blocks; the reference alone; the companion alone
            for a in (0, 90):
                er = extent(t, a)
                ec = extent(c, a) if c else None
                # an IC's type goes on the reference's line; on a second line beside it (stacked) only where no line
                # fits anywhere round the chip (2026-11-10: IC49, "ATmega328P-P" in the gap at its left)
                arr = [("one", 0.0)] if c is None else [("line", 0.0), ("stack", 100.0 if isic else 0.8)]
                for kind, pen in arr:
                    # the companion's centre relative to the reference's, and the block's ink box around the reference's
                    if kind == "one":
                        pc, U = None, er
                    else:
                        if kind == "line" and a == 0:       # "IC30 74LS138": the companion after the reference
                            pc = (er[2] + 0.7 - ec[0], 0.0)
                        elif kind == "line":                # turned, read upwards: the companion above the reference
                            pc = (0.0, er[1] - 0.7 - ec[3])
                        elif a == 0:                        # stacked: the companion on the next line
                            pc = (0.0, er[3] + 0.35 - ec[1])
                        else:
                            pc = (er[2] + 0.35 - ec[0], 0.0)
                        U = union([er, (ec[0] + pc[0], ec[1] + pc[1], ec[2] + pc[0], ec[3] + pc[1])])
                    cands += spots(U, a, pen, pc)
                if c is not None and not isic:
                    alone += [q for q in spots(er, a, 0.0, None) if q[4]]
                    lone += spots(ec, a, 0.0, None)
            key = lambda q: (round(q[0], 6), q[1], q[2])
            cands.sort(key=key)
            alone.sort(key=key)

            others = [r for r in outline if r != ref and not r.startswith("IC")]

            passive = re.match(r"(RN?|C|Q|Y|F)\d", ref)

            def owns(q):                                    # a passive's text nearer its own part than any other part's
                g = apart(q, outline[ref])                  # but an IC's (the ICs' gaps hold the capacitors' texts)
                return not passive or all(g <= apart(q, outline[r]) for r in others)

            def block(qs, own=True):                        # the first block of qs clear of everything
                for cost, a, (rx, ry), cp, _ in qs:
                    put(t, rx, ry, a)
                    if not free(ink(t), t) or (own and not owns(ink(t))):
                        continue
                    if c is not None:
                        put(c, cp[0], cp[1], a)
                        if not free(ink(c), c) or hit(ink(c), ink(t, CLR_SILK)):
                            continue
                    return True
                return False

            def split(near):                                # the reference beside its part and the companion beside it too
                cfree = []                                  # (near) or next to the reference (1.5 mm from its ink), as
                for _, a, (x, y), _, beside in lone:        # close to the reference as the room allows
                    if near and not beside:
                        continue
                    put(c, x, y, a)
                    if free(ink(c), c) and (not near or owns(ink(c))):
                        cfree.append((a, (x, y), ink(c)))
                best, n = None, 0
                for cost, a, (rx, ry), _, _ in alone:
                    put(t, rx, ry, a)
                    if not free(ink(t), t) or not owns(ink(t)):
                        continue
                    ri = ink(t, CLR_SILK)
                    for ca, cp, ci in cfree:
                        if hit(ci, ri) or (not near and not hit(ci, ink(t, 1.5))):
                            continue
                        d = math.hypot((ci[0] + ci[2] - ri[0] - ri[2]) / 2, (ci[1] + ci[3] - ri[1] - ri[3]) / 2)
                        if best is None or cost + 2 * d < best[0] - 1e-9:
                            best = (cost + 2 * d, a, (rx, ry), ca, cp)
                    n += 1
                    if n >= 40:
                        break
                if best is None:
                    return False
                _, a, (rx, ry), ca, (x, y) = best
                put(t, rx, ry, a)
                put(c, x, y, ca)
                return True

            def alone_beside():                             # the reference by itself beside its part
                for cost, a, (rx, ry), _, _ in alone:
                    put(t, rx, ry, a)
                    if free(ink(t), t) and owns(ink(t)):
                        return True
                return False

            # an IC's label, a part without a companion: the best clear place; the others' reference and value: on one line
            # or stacked beside the part, else each beside the part, the value nearest the reference, else the reference
            # beside the part and the value next to it, else the reference beside the part and the value in a legend with
            # the others' in the same plight (LEGEND), else the block anywhere clear
            if isic or c is None:
                ok = block(cands)
            else:
                ok = block([q for q in cands if q[4]])
                if not ok:
                    far.append(ref)
                    ok = True
                    if split(True) or split(False):
                        SPLIT.append(ref)
                    elif alone_beside():
                        LEGEND[ref] = c.GetText()
                    else:
                        ok = block(cands) or block(cands, own=False)
            if not ok:
                cost, a, (rx, ry), cp, _ = cands[0]
                put(t, rx, ry, a)
                if c is not None:
                    put(c, cp[0], cp[1], a)
                unclear.append(ref)
            g = CLR_IC if ref.startswith("IC") else CLR_SILK  # an IC's label stands apart from the texts placed after it
            placed.append(ink(t, g))
            if c is not None and ref not in LEGEND:
                placed.append(ink(c, g))
        return (len(unclear), len(far) - len(SPLIT) - len(LEGEND), len(LEGEND), len(SPLIT)), far

    first, best, seen = [], None, set()
    for _ in range(8):
        score, far = round_(first)
        if best is None or score < best[0]:
            best = (score, list(first))
        if not far:
            break
        # the next round: the parts placed anywhere or given a legend first, then the earlier order, then the split ones
        worst = [r for r in far if r not in SPLIT]
        first = worst + [r for r in first if r not in worst] + [r for r in SPLIT if r not in first and r not in worst]
        if tuple(first) in seen:
            break
        seen.add(tuple(first))
    if first != best[1]:
        round_(best[1])
    # 3. the legends: "C3 C20: 100n" for the parts whose value found no room beside them, nearest those parts
    groups = collections.defaultdict(list)
    for ref, v in LEGEND.items():
        groups[v].append(ref)
    num = lambda r: (re.match(r"[A-Z]+", r).group(0), int(re.search(r"\d+", r).group(0)))
    for v, refs in sorted(groups.items()):
        refs.sort(key=num)
        t = comp[refs[0]]
        for r in refs[1:]:
            b.Delete(comp.pop(r))
        t.SetText("%s: %s" % (" ".join(refs), v))
        us = [outline[r] for r in refs]
        gx, gy = sum(u[0] + u[2] for u in us) / 2 / len(us), sum(u[1] + u[3] for u in us) / 2 / len(us)
        offs = sorted(((i * 0.25, j * 0.25) for i in range(-100, 101) for j in range(-100, 101)),
                      key=lambda o: (math.hypot(*o), o))
        for i, j in offs:
            put(t, gx + i, gy + j, 0)
            if free(ink(t), t):
                break
        else:
            unclear.append(t.GetText())
        placed.append(ink(t, CLR_SILK))
    return unclear


SPLIT = []                              # silk_place(): the references whose value had to stand apart from them
LEGEND = {}                             # silk_place(): {ref: value} of the values that went into a legend
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
    """gen_v40.py silk <pcb> [out]: the silkscreen texts written afresh (silk_texts()) and placed (silk_place()) on a
    finished board - texts only: no footprint, pad, track, via or zone is touched (board() does the same on every new one)"""
    import pcbnew
    b = pcbnew.LoadBoard(pcb)
    unclear = silk_place(b, silk_texts(b))
    pcbnew.SaveBoard(out or pcb, b)
    print("silk: %s" % ("every text clear" if not unclear else "still meeting something: " + ", ".join(unclear)))
    if SPLIT:
        print("silk: the value apart from the reference (each beside the part): " + ", ".join(SPLIT))
    if LEGEND:
        print("silk: the value in a legend (no room beside the part): " + ", ".join(sorted(LEGEND)))
    return not unclear


def planes(pcb):
    """gen_v40.py planes <pcb>: each plane filled as one piece (2026-11-03). Where two pads of the plane's net stand side
    by side at 2.54 mm (X1's GND rows 1 and 32 and VCC rows 2 and 31, SV3's GND pins), their two 0.4 mm thermal gaps
    leave no room for the fill between them, and the two spokes that meet there form a pad-sized island joined to both
    pads (and through their other spokes to the plane) but to nothing else: harmless, but a plane in several pieces.
    Those pads are connected solid instead (no thermal relief on that plane; the island becomes part of the plane) and
    the zones filled again, until every plane is one piece. Only pads touching an island are changed; the routed copper,
    the outer layers and every other pad stay as they are. Refills and saves <pcb>."""
    import pcbnew
    changed = []
    for _ in range(3):
        G13.refill(pcb)
        b = pcbnew.LoadBoard(pcb)
        fix, pieces = [], []
        for z in b.Zones():
            lid = z.GetFirstLayer()
            if z.GetIsRuleArea() or not b.GetLayerName(lid).startswith("In"):
                continue
            poly = z.GetFilledPolysList(lid)
            big = max(range(poly.OutlineCount()), key=lambda i: abs(poly.Outline(i).Area()))
            pieces.append("%s %s %d" % (b.GetLayerName(lid), z.GetNetname(), poly.OutlineCount()))
            for i in range(poly.OutlineCount()):
                if i == big:
                    continue
                isl = pcbnew.SHAPE_POLY_SET()
                isl.AddOutline(poly.Outline(i))
                for fp in b.GetFootprints():
                    for p in fp.Pads():
                        if p.GetNetname() == z.GetNetname() and p.GetLocalZoneConnection() != pcbnew.ZONE_CONNECTION_FULL \
                                and isl.Collide(p.GetPosition(), int(p.GetSize(lid).x / 2) + pcbnew.FromMM(0.05)):
                            fix.append((fp, p))
        if not fix:
            break
        for fp, p in fix:
            p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
            changed.append("%s.%s" % (fp.GetReference(), p.GetNumber()))
        pcbnew.SaveBoard(pcb, b)
    print("planes: %s piece(s)%s" % (", ".join(pieces), "; connected solid: " + " ".join(sorted(set(changed)))
                                     if changed else ""))
    return not fix


# ---------------------------------------------------------------------------------------------------------------------
# The four clocks, routed here before Freerouting sees the board (2026-11-13)
#
# Freerouting knows no clock from any other net. Left to it, the way from a clock's source to its farthest input was
# 100 to 230 mm, by chance, on the routes of 2026-11-13; given the clocks alone on the empty board it strings a net's
# inputs into one chain (D2's last input 230 mm from the counter) and leaves connections open. So the clocks are laid
# by clockroute(): each net a tree that grows from its source, one input at a time, the next input always the one that
# is cheapest to reach from the tree so far, where "cheap" is the new track's length plus CK_ALPHA times the distance
# along the tree from the source to the point where it branches off (0 would be the least track, 1 every input by its
# own shortest way; the rule of Alpert, Hu, Huang and Kahng's Prim-Dijkstra trees). The paths are found on a grid of
# CK_GRID mm over both outer layers, round every other net's pads at the board's clearance, with 45-degree moves, a
# price for a bend and a higher price close to foreign pads (so a track runs down the middle of a channel when it
# can). The tracks are locked; KiCad's Specctra export hands them to Freerouting as fixed wiring, and its session
# import leaves locked tracks and vias alone.
#
# The clocks follow the board's grain (CK_GRAIN). Freerouting lays this board's tracks across the board on the top and
# up and down it on the bottom (the route of 3d9a12f: 9.2 m of the top's 11.3 m run across, 8.9 m of the bottom's
# 16.0 m up and down), so that the two layers cross anywhere without meeting. A track laid the other way is a wall
# on its layer: all that crosses it needs two vias, or goes round. The first clock trees had no vias and went any way
# that was short - 188 mm up and down on the top, 175 mm across on the bottom - and the rest could not be routed
# round them: 4 to 12 connections stayed open in each of four orders, with 580 to 680 vias for 377 (2026-11-13). So a
# step across a layer's grain costs CK_GRAIN[0] times its length and a slanted one CK_GRAIN[1] times, and a clock
# changes sides in a via (CK_VIA) as well as in its own through-hole pads: 1 mm across the grain on each layer, nine
# vias, and the board routes (2026-11-14: one order of four, 455 vias).
CLOCKS = (("OSCO", "OSC1", "8"), ("QC", "IC11", "12"), ("QD", "IC11", "11"), ("STGO", "IC13", "2"),   # net, its source:
          ("CK", "R20", "2"), ("D2", "R21", "2"), ("D3", "R22", "2"), ("STG", "R23", "2"))            # routed in this order
CK_GRID = 0.25
CK_ALPHA = 0.6
CK_TURN = 0.3                                              # a bend's price, in mm of track
CK_NEAR = (0.5, 0.6)                                       # within 0.5 mm more of a foreign pad a step costs 0.6 more
CK_GRAIN = (3.0, 1.5)                                      # a step across the layer's grain, a slanted step: times its length
CK_VIA = 3.0                                               # a via's price, in mm of track


def _clock_pads(b):
    """{net: [(ref, pin, x, y)]} of the board's pads, and every pad's box (net, left, top, right, bottom), in mm"""
    import pcbnew
    MM = pcbnew.ToMM
    bynet, boxes = collections.defaultdict(list), []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            n = p.GetNetname().lstrip("/"); q = p.GetBoundingBox()
            bynet[n].append((fp.GetReference(), p.GetNumber(), MM(p.GetPosition().x), MM(p.GetPosition().y)))
            boxes.append((n, MM(q.GetLeft()), MM(q.GetTop()), MM(q.GetRight()), MM(q.GetBottom())))
    return bynet, boxes


def clockroute(pcb, out):
    """gen_v40.py clockroute <unrouted.pcb> <out.pcb>: the eight clock nets (CLOCKS) laid as locked tracks and vias, nothing
    else touched"""
    import pcbnew, heapq, math
    b = pcbnew.LoadBoard(pcb); MM = pcbnew.ToMM; FM = pcbnew.FromMM
    R = G13.RULES; g = CK_GRID
    reach = R["track"] / 2 + R["clearance"] + 0.01          # a track's centre line from foreign copper's edge
    apart = R["track"] + R["clearance"] + 0.01              # ... and from another clock's centre line
    vreach = R["via"] / 2 + R["clearance"] + 0.01           # a via's centre from a pad's edge (the net's own too: the
    #                                                         holes stay apart, and a pad changes sides without a via)
    e = b.GetBoardEdgesBoundingBox()
    x0, y0 = MM(e.GetLeft()), MM(e.GetTop())
    W, H = int(MM(e.GetWidth()) / g) + 1, int(MM(e.GetHeight()) / g) + 1
    bynet, boxes = _clock_pads(b)
    keepout = [z.GetBoundingBox() for z in b.Zones() if z.GetIsRuleArea()]
    keepout = [(MM(k.GetLeft()), MM(k.GetTop()), MM(k.GetRight()), MM(k.GetBottom())) for k in keepout]

    def node(x, y): return int(round((x - x0) / g)), int(round((y - y0) / g))

    def mark(m, l, t, r, btm, d):
        i0, i1 = max(0, int(math.ceil((l - d - x0) / g))), min(W - 1, int(math.floor((r + d - x0) / g)))
        j0, j1 = max(0, int(math.ceil((t - d - y0) / g))), min(H - 1, int(math.floor((btm + d - y0) / g)))
        if i1 >= i0:
            for j in range(j0, j1 + 1): m[j * W + i0:j * W + i1 + 1] = b"\1" * (i1 - i0 + 1)

    def mark_track(m, xa, ya, xb, yb, d):
        i0, i1 = max(0, int((min(xa, xb) - d - x0) / g)), min(W - 1, int((max(xa, xb) + d - x0) / g) + 1)
        j0, j1 = max(0, int((min(ya, yb) - d - y0) / g)), min(H - 1, int((max(ya, yb) + d - y0) / g) + 1)
        dx, dy = xb - xa, yb - ya; L2 = dx * dx + dy * dy
        for j in range(j0, j1 + 1):
            y = y0 + j * g
            for i in range(i0, i1 + 1):
                x = x0 + i * g
                t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - xa) * dx + (y - ya) * dy) / L2))
                if (x - xa - t * dx) ** 2 + (y - ya - t * dy) ** 2 < d * d: m[j * W + i] = 1

    margin = int(math.ceil((R["edge"] + R["track"] / 2 + 0.25) / g))
    DIRS = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))
    STEP = tuple(g * (1.4142135623730951 if di and dj else 1.0) for di, dj in DIRS)
    COST = tuple(tuple(STEP[k] * (CK_GRAIN[1] if di and dj else 1.0 if (dj == 0) == (L == 0) else CK_GRAIN[0])
                       for k, (di, dj) in enumerate(DIRS)) for L in (0, 1))   # the top across the board, the bottom up and down
    laid = []                                               # (net, layer 0 / 1, xa, ya, xb, yb)
    holes = []                                              # (net, x, y): the vias
    vbase = bytearray(W * H)                                # where no via's centre may be, whatever its net
    for j in range(H):
        if j < margin + 2 or j >= H - margin - 2: vbase[j * W:(j + 1) * W] = b"\1" * W
        else: vbase[j * W:j * W + margin + 2] = b"\1" * (margin + 2); vbase[(j + 1) * W - margin - 2:(j + 1) * W] = b"\1" * (margin + 2)
    for k in keepout: mark(vbase, k[0], k[1], k[2], k[3], vreach)
    for n, l, t, r, btm in boxes: mark(vbase, l, t, r, btm, vreach)
    report = []
    for net, sref, spin in CLOCKS:
        mine = bynet[net]
        own = {node(x, y): (ref, pin, x, y) for ref, pin, x, y in mine}
        src = [nd for nd, (ref, pin, _, _) in own.items() if (ref, pin) == (sref, spin)]
        if len(src) != 1: raise SystemExit("clockroute: %s has no pad %s.%s" % (net, sref, spin))
        base, near = bytearray(W * H), bytearray(W * H)
        for j in range(H):
            if j < margin or j >= H - margin: base[j * W:(j + 1) * W] = b"\1" * W
            else: base[j * W:j * W + margin] = b"\1" * margin; base[(j + 1) * W - margin:(j + 1) * W] = b"\1" * margin
        for k in keepout: mark(base, k[0], k[1], k[2], k[3], reach)
        for n, l, t, r, btm in boxes:
            if n != net: mark(base, l, t, r, btm, reach); mark(near, l, t, r, btm, reach + CK_NEAR[0])
        blk = [bytearray(base), bytearray(base)]
        vb = bytearray(vbase)
        for n, L, xa, ya, xb, yb in laid:
            if n != net: mark_track(blk[L], xa, ya, xb, yb, apart); mark_track(vb, xa, ya, xb, yb, vreach + R["track"] / 2)
        for n, x, y in holes:
            if n != net:
                for m in blk: mark_track(m, x, y, x, y, vreach + R["track"] / 2)
                mark_track(vb, x, y, x, y, R["via"] + R["clearance"] + 0.01)
        tree = {(0,) + src[0]: 0.0, (1,) + src[0]: 0.0}     # node -> mm of copper from the source
        todo = {nd: v for nd, v in own.items() if nd != src[0]}
        segs, ways, nvia = [], {}, 0
        while todo:
            best, prev, pq, hit = {}, {}, [], None
            for nd, d in tree.items():
                best[nd] = CK_ALPHA * d; heapq.heappush(pq, (CK_ALPHA * d, nd, -1))
            while pq:
                c, nd, dr = heapq.heappop(pq)
                if c > best[nd]: continue
                L, i, j = nd
                if (i, j) in todo: hit = nd; break
                if (i, j) in own:                           # the net's own pad: through to the other side
                    o = (1 - L, i, j)
                    if c < best.get(o, 1e18): best[o] = c; prev[o] = nd; heapq.heappush(pq, (c, o, -1))
                elif not vb[j * W + i] and not blk[1 - L][j * W + i]:                  # a via
                    o = (1 - L, i, j)
                    if c + CK_VIA < best.get(o, 1e18): best[o] = c + CK_VIA; prev[o] = nd; heapq.heappush(pq, (c + CK_VIA, o, -1))
                m = blk[L]; cost = COST[L]
                for k in range(8):
                    di, dj = DIRS[k]; ii, jj = i + di, j + dj
                    if ii < 0 or jj < 0 or ii >= W or jj >= H or m[jj * W + ii]: continue
                    if di and dj and (m[j * W + ii] or m[jj * W + i]): continue        # no cutting a corner
                    cc = c + cost[k] + STEP[k] * CK_NEAR[1] * near[jj * W + ii] + (CK_TURN if dr >= 0 and dr != k else 0.0)
                    o = (L, ii, jj)
                    if cc < best.get(o, 1e18): best[o] = cc; prev[o] = nd; heapq.heappush(pq, (cc, o, k))
            if hit is None:
                raise SystemExit("clockroute: no way for %s to %s" % (net, ", ".join("%s.%s" % v[:2] for v in todo.values())))
            path = [hit]
            while path[-1] not in tree: path.append(prev[path[-1]])
            path.reverse()
            d = tree[path[0]]
            for a, c in zip(path, path[1:]):
                if a[0] == c[0]: d += math.hypot(c[1] - a[1], c[2] - a[2]) * g
                tree[c] = d
            tree[(1 - hit[0],) + hit[1:]] = d
            ref, pin, _, _ = todo.pop(hit[1:]); ways["%s.%s" % (ref, pin)] = d
            run = [path[0]]                                 # the path as straight pieces
            for a, c in zip(path, path[1:]):
                if a[0] != c[0]:
                    if len(run) > 1: segs.append((run[0], run[-1]))
                    if a[1:] not in own:                    # a via, and no other of this net beside it
                        x, y = x0 + a[1] * g, y0 + a[2] * g
                        holes.append((net, x, y)); nvia += 1; mark_track(vb, x, y, x, y, R["via"] + R["hole_to_hole"])
                    run = [c]; continue
                if len(run) > 1 and (run[-1][1] - run[-2][1], run[-1][2] - run[-2][2]) != (c[1] - a[1], c[2] - a[2]):
                    segs.append((run[0], run[-1])); run = [run[-1]]
                run.append(c)
            if len(run) > 1: segs.append((run[0], run[-1]))
        mm = 0.0
        for a, c in segs:
            xa, ya, xb, yb = x0 + a[1] * g, y0 + a[2] * g, x0 + c[1] * g, y0 + c[2] * g
            laid.append((net, a[0], xa, ya, xb, yb)); mm += math.hypot(xb - xa, yb - ya)
        used = {(a[0],) + a[1:] for a, c in segs} | {(c[0],) + c[1:] for a, c in segs}
        for nd, (ref, pin, x, y) in own.items():            # from the grid's point in a pad to the pad's centre
            for L in (0, 1):
                xn, yn = x0 + nd[0] * g, y0 + nd[1] * g
                if (L,) + nd in used and math.hypot(x - xn, y - yn) > 0.001: laid.append((net, L, xn, yn, x, y))
        report.append("%-5s %6.1f mm, %d vias, from %s.%s: %s" % (net, mm, nvia, sref, spin, ", ".join(
            "%s %.0f" % (k, v) for k, v in sorted(ways.items(), key=lambda kv: kv[1]))))
    for net, L, xa, ya, xb, yb in laid:
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(FM(xa), FM(ya))); t.SetEnd(pcbnew.VECTOR2I(FM(xb), FM(yb)))
        t.SetWidth(FM(R["track"])); t.SetLayer(pcbnew.B_Cu if L else pcbnew.F_Cu)
        t.SetNet(b.FindNet("/" + net)); t.SetLocked(True); b.Add(t)
    for net, x, y in holes:
        v = pcbnew.PCB_VIA(b)
        v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetPosition(pcbnew.VECTOR2I(FM(x), FM(y))); v.SetWidth(pcbnew.F_Cu, FM(R["via"])); v.SetDrill(FM(R["via_drill"]))
        v.SetNet(b.FindNet("/" + net)); v.SetLocked(True); b.Add(v)
    pcbnew.SaveBoard(out, b)
    across = [sum(math.hypot(xb - xa, yb - ya) for n, L, xa, ya, xb, yb in laid
                  if L == k and (abs(xb - xa) < 0.4 * abs(yb - ya) if k == 0 else abs(yb - ya) < 0.4 * abs(xb - xa))) for k in (0, 1)]
    print("clockroute: %d nets, %d locked tracks, %d vias (grid %.2f mm, alpha %.1f); across the grain %.0f mm on the top, "
          "%.0f mm on the bottom" % (len(CLOCKS), len(laid), len(holes), g, CK_ALPHA, across[0], across[1]))
    for r in report: print("  " + r)


def clocks(pcb, out=None):
    """gen_v40.py clocks <pcb> [report.txt]: the clock nets as they are on a board - track, vias, and the copper's
    length from each net's source to every input (the shortest way through its tracks, vias and pads). False if an
    input is not reached, or if a clock's track is not locked"""
    import pcbnew, heapq, math
    b = pcbnew.LoadBoard(pcb); MM = pcbnew.ToMM
    bynet, _ = _clock_pads(b)
    boxes = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            q = p.GetBoundingBox()
            boxes[(fp.GetReference(), p.GetNumber())] = (MM(q.GetLeft()), MM(q.GetTop()), MM(q.GetRight()), MM(q.GetBottom()))
    segs, vias, free = collections.defaultdict(list), collections.defaultdict(list), 0
    names = {c[0] for c in CLOCKS}
    for t in b.GetTracks():
        n = t.GetNetname().lstrip("/")
        if n not in names: continue
        free += not t.IsLocked()
        if t.Type() == pcbnew.PCB_VIA_T: vias[n].append((MM(t.GetPosition().x), MM(t.GetPosition().y)))
        else: segs[n].append((t.GetLayerName(), (MM(t.GetStart().x), MM(t.GetStart().y)), (MM(t.GetEnd().x), MM(t.GetEnd().y))))
    d = lambda a, c: math.hypot(a[0] - c[0], a[1] - c[1])

    def on(p, a, c):                                        # p inside the piece a-c, not at its ends
        L = d(a, c)
        if L < 1e-6: return False
        t = ((p[0] - a[0]) * (c[0] - a[0]) + (p[1] - a[1]) * (c[1] - a[1])) / L / L
        return 1e-6 < t < 1 - 1e-6 and d(p, (a[0] + t * (c[0] - a[0]), a[1] + t * (c[1] - a[1]))) < 0.002
    key = lambda ly, p: (ly, round(p[0], 3), round(p[1], 3))
    lines, bad, total, far = [], 0, 0.0, {}
    for net, sref, spin in CLOCKS:
        g = collections.defaultdict(list)
        def link(u, v, w): g[u].append((v, w)); g[v].append((u, w))
        pts = collections.defaultdict(set)
        for ly, a, c in segs[net]: pts[ly].add(a); pts[ly].add(c)
        for v in vias[net]:
            for ly in ("F.Cu", "B.Cu"): pts[ly].add(v)
            link(key("F.Cu", v), key("B.Cu", v), 0.0)
        for ref, pin, x, y in bynet[net]:
            l, t, r, btm = boxes[(ref, pin)]
            for ly in ("F.Cu", "B.Cu"):
                for p in pts[ly]:
                    if l <= p[0] <= r and t <= p[1] <= btm: link((ref, pin), key(ly, p), d(p, (x, y)))
        for ly, a, c in segs[net]:
            chain = [a] + sorted((p for p in pts[ly] if on(p, a, c)), key=lambda p: d(a, p)) + [c]
            for u, v in zip(chain, chain[1:]): link(key(ly, u), key(ly, v), d(u, v))
        dist, h = {(sref, spin): 0.0}, [(0.0, 0, (sref, spin))]; k = 0
        while h:
            w, _, u = heapq.heappop(h)
            if w > dist.get(u, 1e18): continue
            for v, x in g[u]:
                if w + x < dist.get(v, 1e18): k += 1; dist[v] = w + x; heapq.heappush(h, (w + x, k, v))
        loads = sorted((dist.get((ref, pin), None), "%s.%s" % (ref, pin)) for ref, pin, _, _ in bynet[net] if (ref, pin) != (sref, spin))
        opens = [n for w, n in loads if w is None]; bad += len(opens)
        mm = sum(d(a, c) for _, a, c in segs[net]); total += mm
        if loads and not opens: far[net] = loads[-1][0]
        lines.append("%-5s %6.1f mm, %d vias, from %s.%s: %s%s" % (net, mm, len(vias[net]), sref, spin, ", ".join(
            "%s %.0f" % (n, w) for w, n in loads if w is not None), "; NOT REACHED: " + " ".join(opens) if opens else ""))
    lines.append("clock track in all %.0f mm; the farthest input of CK %.0f, D2 %.0f, D3 %.0f, STG %.0f mm from its resistor; "
                 "%s" % (total, far.get("CK", -1), far.get("D2", -1), far.get("D3", -1), far.get("STG", -1),
                         "every clock track locked" if not free else "%d clock tracks NOT locked" % free))
    text = "\n".join(lines)
    print(text)
    if out: open(out, "w").write("The clock nets on %s (gen_v40.py clocks): track, vias, and the copper's length in mm from each\n"
                                 "net's source to every input.\n\n%s\n" % (os.path.basename(pcb), text))
    ok = not bad and not free
    print("clocks: %s" % ("PASS" if ok else "FAIL"))
    return ok


def drawing(pcb, out=None):
    """gen_v40.py drawing <pcb> [out.pdf]: the placement drawing - the outline, every part's body with its reference
    (F.Fab) and the silkscreen's texts, in one orientation, on a landscape sheet as the board lies (the board-layout
    rules; pcb-check's DRAWING looks for *placement*.pdf beside the board)"""
    out = out or os.path.join(os.path.dirname(os.path.abspath(pcb)), P + "-placement.pdf")
    gen_cf.kicad_cli("pcb", "export", "pdf", "--mode-single", "--layers", "F.Fab,F.Silkscreen,Edge.Cuts",
                     "--black-and-white", "--exclude-value", "--include-border-title", "-o", out, pcb)
    m = re.search(rb"/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", open(out, "rb").read())
    w, h = float(m.group(3)) - float(m.group(1)), float(m.group(4)) - float(m.group(2))
    ok = (w > h) == (X1R - X0 > Y1B - Y0)
    print("drawing: %s, a %s sheet for a %s board: %s" % (os.path.basename(out), "landscape" if w > h else "portrait",
          "wide" if X1R - X0 > Y1B - Y0 else "tall", "PASS" if ok else "FAIL"))
    return ok


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


# the V4.0 key connections, checked pin by pin in the schematic netlist and on the board's pads: written from the design
# note's equations (docs/cards/video-v4.md sections 5-9), not from v40_netlist.py
KEY = [
    # the block select and the two halves of the block
    ("IC1", "1", "ADDR15"), ("IC1", "14", "ADDR14"), ("IC1", "11", "ADDR13"), ("IC1", "9", "ADDR12"), ("IC1", "3", "VMA"),
    ("IC1", "6", "BOARDSEL"), ("IC8", "1", "-VMA"), ("IC8", "2", "VMA"), ("IC8", "3", "ADDR11"), ("IC8", "4", "NADDR11"),
    ("IC37", "1", "BOARDSEL"), ("IC37", "2", "NADDR11"), ("IC37", "3", "TXTCE#"), ("IC14", "47", "TXTCE#"),
    ("IC23", "1", "BOARDSEL"), ("IC23", "2", "ADDR11"), ("IC23", "3", "GSEL"), ("IC23", "4", "GSEL"), ("IC23", "5", "MEMWR"),
    ("IC23", "6", "GWR"), ("IC37", "4", "GSEL"), ("IC37", "5", "MEMRD"), ("IC37", "6", "GRDOE#"), ("IC8", "5", "-MEM-RD"),
    ("IC8", "9", "-MEM-WR"), ("X1", "B23", "-MEM-RD"), ("X1", "B24", "-MEM-WR"), ("X1", "C12", "-VMA"),
    # the ports: the decoder, the six strobes, the two control registers, the status and its ID
    ("IC2", "1", "IO-ADDR0"), ("IC2", "2", "IO-ADDR1"), ("IC2", "3", "IO-ADDR2"), ("IC2", "6", "IO-ADDR3"),
    ("IC2", "13", "PSEL_A#"), ("IC2", "12", "PSEL_B#"), ("IC2", "11", "PSEL_C#"), ("IC2", "10", "PSEL_D#"),
    ("IC2", "9", "PSEL_E#"), ("IC2", "7", "PSEL_F#"), ("IC3", "2", "-IO-WR"), ("IC3", "3", "CTL1CK"), ("IC5", "11", "CTL1CK"),
    ("IC3", "5", "-IO-RD"), ("IC3", "6", "STATOE#"), ("IC7", "1", "STATOE#"), ("IC7", "19", "STATOE#"),
    ("IC4", "4", "PSEL_F#"), ("IC4", "5", "-IO-WR"), ("IC4", "6", "CTL2CK"), ("IC6", "11", "CTL2CK"),
    ("IC5", "1", "-RESET"), ("IC6", "1", "-RESET"), ("IC5", "3", "DATA0"), ("IC5", "18", "DATA7"), ("IC6", "3", "DATA0"),
    ("IC5", "2", "PLANE0"), ("IC5", "9", "PLANE3"), ("IC5", "12", "CPAGE"), ("IC5", "15", "DPAGE"), ("IC5", "16", "GFXON"),
    ("IC5", "19", "XORM"), ("IC6", "2", "TEXTOFF"), ("IC6", "5", "CURH"), ("IC6", "6", "POLH"), ("IC6", "9", "POLV"),
    ("IC6", "15", "OFFR"), ("IC6", "16", "OFFG"), ("IC6", "19", "OFFB"),
    ("IC7", "2", "GND"), ("IC7", "4", "SVS"), ("IC7", "6", "SDE"), ("IC7", "8", "TXTONLY"), ("IC7", "11", "VCC"),
    ("IC7", "13", "VCC"), ("IC7", "15", "VCC"), ("IC7", "17", "GND"), ("IC7", "18", "DATA0"), ("IC7", "3", "DATA7"),
    ("X1", "A19", "DATA0"), ("X1", "A26", "DATA7"), ("X1", "B25", "-IO-RD"), ("X1", "B26", "-IO-WR"),
    # the 6845: its bus side, its clock, MA and the flags into the stage, RA
    ("IC9", "1", "PSEL_A#"), ("IC9", "2", "PSEL_B#"), ("IC9", "3", "CRTCCS#"), ("IC10", "25", "CRTCCS#"),
    ("IC22", "1", "-IO-RD"), ("IC22", "2", "-IO-WR"), ("IC22", "3", "CRTCE"), ("IC10", "23", "CRTCE"),
    ("IC10", "22", "-IO-WR"), ("IC10", "24", "IO-ADDR0"), ("IC10", "2", "-RESET"), ("IC10", "3", "GND"),
    ("IC10", "33", "DATA0"), ("IC10", "26", "DATA7"), ("IC10", "20", "VCC"), ("IC10", "1", "GND"),
    ("IC10", "21", "CRTCCK"), ("IC12", "5", "CRTCCK"), ("IC12", "2", "D3"), ("IC12", "3", "CK"),
    ("R20", "1", "OSCO"), ("R20", "2", "CK"), ("R21", "1", "QC"), ("R21", "2", "D2"), ("R22", "1", "QD"), ("R22", "2", "D3"),
    ("R23", "1", "STGO"), ("R23", "2", "STG"),
    ("IC10", "4", "MA0"), ("IC15", "2", "MA0"), ("IC15", "19", "SA0"), ("IC10", "13", "MA9"), ("IC16", "3", "MA9"),
    ("IC16", "18", "SA9"), ("IC10", "18", "DE"), ("IC16", "4", "DE"), ("IC16", "17", "SDE"), ("IC10", "19", "CURSOR"),
    ("IC16", "16", "SCUR"), ("IC10", "39", "HSYNC"), ("IC16", "15", "SHS"), ("IC10", "40", "VSYNC"), ("IC16", "14", "SVS"),
    ("IC15", "11", "STG"), ("IC16", "11", "STG"), ("IC13", "1", "D3"), ("IC13", "2", "STGO"), ("IC15", "1", "GND"),
    ("IC10", "38", "RA0"), ("IC10", "35", "RA3"), ("IC18", "10", "RA0"), ("IC18", "7", "RA3"),
    # the dot clock and the counter
    ("OSC1", "8", "OSCO"), ("IC11", "2", "CK"), ("IC11", "14", "D0"), ("IC11", "13", "D1"), ("IC11", "12", "QC"),
    ("IC11", "11", "QD"), ("IC11", "1", "PU"), ("IC11", "7", "PU"), ("IC11", "9", "PU"), ("IC11", "10", "PU"),
    ("R2", "1", "VCC"), ("R2", "2", "PU"),
    # the text: the display port's address, the code register, the character generator, the shifter and its load
    ("IC14", "6", "D3"), ("IC14", "7", "SA0"), ("IC14", "15", "SA8"), ("IC14", "4", "SA9"), ("IC14", "3", "GND"),
    ("IC14", "1", "GND"), ("IC14", "5", "GND"), ("IC14", "2", "VCC"), ("IC14", "42", "ADDR0"), ("IC14", "44", "ADDR10"),
    ("IC14", "45", "GND"), ("IC14", "25", "DATA0"), ("IC14", "43", "-MEM-RD"), ("IC14", "46", "-MEM-WR"),
    ("IC14", "16", "VD0"), ("IC17", "2", "VD0"), ("IC14", "23", "VD7"), ("IC17", "9", "VD7"), ("IC17", "11", "D2"),
    ("IC17", "19", "CA0"), ("IC18", "6", "CA0"), ("IC17", "12", "CA7"), ("IC18", "23", "CA7"), ("IC18", "2", "CURF"),
    ("IC18", "20", "GND"), ("IC18", "22", "GND"), ("IC18", "27", "VCC"), ("IC18", "11", "CG0"), ("IC19", "7", "CG0"),
    ("IC18", "19", "CG7"), ("IC19", "16", "CG7"), ("IC19", "12", "CK"), ("IC19", "19", "TLOAD"), ("IC19", "9", "TEXTON"),
    ("IC19", "11", "GND"), ("IC19", "17", "TDOT"), ("IC13", "11", "TEXTOFF"), ("IC13", "10", "TEXTON"),
    ("IC21", "1", "D0"), ("IC21", "2", "D1"), ("IC21", "4", "D2N"), ("IC21", "5", "SDE2"), ("IC21", "6", "TLOAD"),
    ("IC13", "3", "D2"), ("IC13", "4", "D2N"), ("IC12", "12", "SDE"), ("IC12", "11", "D3"), ("IC12", "9", "SDE2"),
    # the cursor flag
    ("IC22", "4", "STG"), ("IC22", "5", "CURH"), ("IC22", "6", "CURX"), ("IC23", "9", "SCUR"), ("IC23", "10", "CURX"),
    ("IC23", "8", "CURFD"), ("IC20", "2", "CURFD"), ("IC20", "3", "D2"), ("IC20", "5", "CURF"),
    # the graphics RAM: the multiplexers (A = the display, B = the CPU), the address, the data lines
    ("IC24", "1", "SELCPU"), ("IC27", "1", "SELCPU"), ("IC24", "15", "GND"), ("IC24", "2", "D3"), ("IC24", "3", "ADDR0"),
    ("IC24", "4", "GA0"), ("IC28", "12", "GA0"), ("IC24", "5", "SA0"), ("IC24", "6", "ADDR1"), ("IC26", "11", "SA9"),
    ("IC26", "10", "ADDR10"), ("IC26", "9", "GA10"), ("IC28", "23", "GA10"), ("IC26", "14", "RA0"), ("IC26", "13", "PLANE0"),
    ("IC26", "12", "GA11"), ("IC28", "25", "GA11"), ("IC27", "11", "RA3"), ("IC27", "10", "PLANE3"), ("IC27", "9", "GA14"),
    ("IC28", "3", "GA14"), ("IC27", "14", "DPAGE"), ("IC27", "13", "CPAGE"), ("IC27", "12", "GA15"), ("IC28", "31", "GA15"),
    ("IC28", "2", "GND"), ("IC28", "22", "GND"), ("IC28", "30", "VCC"), ("IC28", "24", "GOE#"), ("IC28", "29", "GWE#"),
    ("IC28", "13", "GD0"), ("IC28", "21", "GD7"), ("RN2", "1", "VCC"), ("RN2", "2", "GD0"),
    ("IC29", "1", "GWE#"), ("IC29", "19", "GWE#"), ("IC29", "2", "DATA0"), ("IC29", "18", "GD0"),
    ("IC30", "2", "GD0"), ("IC30", "19", "DATA0"), ("IC30", "11", "RDCK"), ("IC30", "1", "SRDOE#"),
    ("IC31", "2", "GD0"), ("IC31", "18", "DATA0"), ("IC31", "1", "DRDOE#"), ("IC31", "19", "DRDOE#"),
    ("IC32", "2", "GD0"), ("IC32", "11", "D2"), ("IC32", "1", "GND"), ("IC32", "19", "GL0"), ("IC33", "7", "GL0"),
    ("IC32", "12", "GL7"), ("IC33", "16", "GL7"), ("IC33", "12", "CK"), ("IC33", "19", "TLOAD"), ("IC33", "9", "GFXON"),
    ("IC33", "17", "GDOT"), ("R8", "1", "GDOT"), ("R8", "2", "GND"),
    ("IC4", "9", "GRDOE#"), ("IC4", "10", "NGFX"), ("IC4", "8", "SRDOE#"), ("IC4", "12", "GRDOE#"), ("IC4", "13", "GFXON"),
    ("IC4", "11", "DRDOE#"),
    # the slot logic: SELCPU, WRQ, P56, -WE, the RAM's -OE, the read latch's clock
    ("IC13", "9", "GFXON"), ("IC13", "8", "NGFX"), ("IC36", "1", "D2"), ("IC36", "2", "NGFX"), ("IC36", "3", "SELCPU"),
    ("IC34", "2", "GWR"), ("IC34", "3", "D2"), ("IC34", "1", "GFXON"), ("IC34", "4", "PU"), ("IC34", "5", "WRQ"),
    ("R9", "1", "WRQ"), ("R9", "2", "GND"), ("IC34", "13", "GND"), ("IC34", "9", "TXTONLY"), ("R10", "1", "TXTONLY"),
    ("R10", "2", "VCC"),
    ("IC21", "9", "D2"), ("IC21", "10", "D1N"), ("IC13", "5", "D1"), ("IC13", "6", "D1N"), ("IC21", "8", "P56D"),
    ("IC35", "2", "P56D"), ("IC35", "3", "CK"), ("IC35", "5", "P56"), ("IC37", "9", "WRQ"), ("IC37", "10", "P56"),
    ("IC37", "8", "WEP#"), ("IC37", "12", "NGFX"), ("IC37", "13", "GWR"), ("IC37", "11", "WED#"), ("IC23", "12", "WEP#"),
    ("IC23", "13", "WED#"), ("IC23", "11", "GWE#"),
    ("IC36", "4", "WRQ"), ("IC36", "5", "NGFX"), ("IC36", "6", "WOE"), ("IC38", "1", "WOE"), ("IC38", "2", "SELCPU"),
    ("IC38", "13", "GRDOE#"), ("IC38", "12", "GOE#"),
    ("IC38", "9", "D0"), ("IC38", "10", "D1"), ("IC38", "11", "D2"), ("IC38", "8", "RDCKD"), ("IC35", "12", "RDCKD"),
    ("IC35", "11", "CK"), ("IC35", "9", "RDCK"),
    # the dots: mixed, retimed, the guns, the VGA socket
    ("IC39", "2", "TDOT"), ("IC39", "3", "GDOT"), ("IC39", "1", "NGOT"), ("IC38", "3", "TDOT"), ("IC38", "4", "GDOT"),
    ("IC38", "5", "XORM"), ("IC38", "6", "BX"), ("IC36", "9", "NGOT"), ("IC36", "10", "BX"), ("IC36", "8", "VIDN"),
    ("IC20", "12", "VIDN"), ("IC20", "11", "CK"), ("IC20", "9", "VIDNQ"), ("IC39", "5", "VIDNQ"), ("IC39", "6", "OFFR"),
    ("IC39", "4", "VR"), ("IC39", "9", "OFFG"), ("IC39", "10", "VG"), ("IC39", "12", "OFFB"), ("IC39", "13", "VB"),
    ("R3", "1", "VR"), ("R3", "2", "RED"), ("J1", "1", "RED"), ("J1", "2", "GREEN"), ("J1", "3", "BLUE"),
    ("J1", "5", "GND"), ("J1", "10", "GND"), ("J1", "SH", "GND"),
    # the syncs
    ("IC8", "11", "SHS"), ("IC8", "10", "NSHS"), ("IC22", "9", "NSHS"), ("IC22", "10", "POLH"), ("IC22", "8", "HSB"),
    ("R6", "1", "HSB"), ("R6", "2", "HSOUT"), ("J1", "13", "HSOUT"),
    ("IC40", "2", "SVS"), ("IC40", "3", "SHS"), ("IC40", "5", "VQ1"), ("IC40", "12", "VQ1"), ("IC40", "11", "SHS"),
    ("IC40", "9", "VQ2"), ("IC13", "13", "SVS"), ("IC13", "12", "NSVS"), ("IC36", "12", "NSVS"), ("IC36", "13", "VQ2"),
    ("IC36", "11", "VS2#"), ("IC22", "12", "VS2#"), ("IC22", "13", "POLV"), ("IC22", "11", "VSB"), ("R7", "1", "VSB"),
    ("R7", "2", "VSOUT"), ("J1", "14", "VSOUT"),
    # PS/2: the ATmega, the latches, the flags, INT, reset (V2.0's nets)
    ("IC41", "4", "KCLK"), ("IC41", "5", "MCLK"), ("IC41", "6", "KDAT"), ("IC41", "11", "MDAT"), ("IC41", "12", "LDDATA"),
    ("IC41", "13", "RDCMD"), ("IC41", "16", "FULL"), ("IC41", "17", "BUSY"), ("IC41", "18", "INTREQ"), ("IC41", "19", "SRC"),
    ("IC41", "9", "XT1"), ("IC41", "10", "XT2"), ("Y1", "1", "XT1"), ("Y1", "2", "XT2"),
    ("IC3", "9", "PSEL_D#"), ("IC3", "8", "CMDCK"), ("IC43", "11", "CMDCK"), ("IC45", "11", "CMDCK"), ("IC3", "11", "PSTOE#"),
    ("IC44", "1", "PSTOE#"), ("IC44", "19", "PSTOE#"), ("IC4", "1", "PSEL_E#"), ("IC4", "3", "PDOE#"), ("IC42", "1", "PDOE#"),
    ("IC9", "12", "PDOE#"), ("IC9", "13", "-RESET"), ("IC9", "11", "FULLCLR#"), ("IC45", "1", "FULLCLR#"),
    ("IC45", "3", "LDDATA"), ("IC45", "5", "FULL"), ("IC45", "9", "BUSY"), ("IC45", "13", "RDCMD"), ("IC44", "2", "FULL"),
    ("IC44", "4", "SRC"), ("IC44", "6", "BUSY"), ("IC42", "11", "LDDATA"), ("IC43", "1", "RDCMD"),
    ("IC9", "4", "INTREQ"), ("IC9", "5", "FULL"), ("IC9", "6", "INTG"), ("IC46", "9", "INTG"), ("IC46", "8", "INTOC"),
    ("JP1", "1", "INTOC"), ("JP1", "2", "-INT"), ("X1", "C13", "-INT"), ("IC9", "9", "-RESET"), ("IC9", "8", "RESETB"),
    ("IC46", "11", "RESETB"), ("IC46", "10", "RESETH"), ("R12", "1", "RESETH"), ("IC46", "13", "RESETH"),
    ("IC46", "12", "MRST"), ("IC41", "1", "MRST"), ("R11", "1", "MRST"),
    ("J2", "5", "KCLK"), ("J2", "1", "KDAT"), ("J3", "5", "MCLK"), ("J3", "1", "MDAT"), ("J2", "3", "GND"),
    ("J2", "4", "PS2VCC"), ("J3", "4", "PS2VCC"), ("F1", "2", "PS2VCC"), ("F1", "1", "VCC"), ("J2", "S", "GND"),
    ("J3", "S", "GND"),
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
    """BOM.md from v40_netlist.PARTS: one line per value and footprint, the text-only build's left-off parts marked"""
    rows = collections.OrderedDict()
    order = lambda r: (re.match(r"[A-Z]+", r).group(0), int(re.search(r"\d+", r).group(0)))
    for ref in sorted(N.PARTS, key=order):
        value, symid, fpid, note = N.PARTS[ref]
        if ref in N.DECOUPLE:
            note = "decoupling, 0.1 inch leads"
        key = (value, fpid.split(":")[1], N.BUY.get(ref, ""), "off" if ref in N.TEXT_ONLY_LEFT_OFF else "")
        rows.setdefault(key, [[], note])[0].append(ref)
    nsock = collections.Counter(ic_size(r) for r in N.PARTS if "DIP-" in N.PARTS[r][2] and r.startswith("IC"))
    L = ["# Video card V4.0 - bill of materials", "",
         "GENERATED by `gen_v40.py bom` from `v40_netlist.py` (%s) - do not edit. %d parts. Buy %s: %s, and a 4-pin "
         "socket for the oscillator. **Text-only build**: leave off the parts marked *off*; nothing is fitted for "
         "that build only." % (N.DATE, len(N.PARTS), N.SOCKETS,
                               ", ".join("%d x %d-pin %.2f mm" % (n, p, w) for (p, w), n in sorted(nsock.items()))), "",
         "| Qty | Value | Footprint | References | Text-only | Buy / note |", "|---|---|---|---|---|---|"]
    for (value, fp, buy, tob), (refs, note) in rows.items():
        L.append("| %d | %s | %s | %s | %s | %s |" % (len(refs), value, fp, ", ".join(refs), tob,
                                                      buy or (note if len(refs) == 1 else "")))
    L += ["", "The text-only build leaves off %d parts (%s)." % (len(N.TEXT_ONLY_LEFT_OFF), ", ".join(N.TEXT_ONLY_LEFT_OFF)), "",
          "The 74ACT and 74F types are the ones the timing check was run with (`tests/video/v40_netsim.py`, "
          "`docs/cards/video-v4.md` section 5): a 74HCT or 74LS part in their place is another circuit.", ""]
    open(os.path.join(HERE, "BOM.md"), "w").write("\n".join(L))
    print("BOM.md: %d parts, %d lines" % (len(N.PARTS), len(rows)))


def read_netlist(path):
    """(ref, pad) -> the schematic's own net name (/NAME for a label net), ref -> the footprint path KiCad gives the
    symbol (its sheet path and first UUID: sch_wire.symbol_paths(), also for a multi-unit symbol)"""
    s = open(path).read()
    comps = W.symbol_paths(path)
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
    elif cmd == "link":
        W.link(*a)
    elif cmd == "place":
        ok = placement_check(*a)
    elif cmd == "drawing":
        ok = drawing(*a)
    elif cmd == "silk":
        ok = silk_cmd(*a)
    elif cmd == "planes":
        ok = planes(*a)
    elif cmd == "clockroute":
        clockroute(*a)
    elif cmd == "clocks":
        ok = clocks(*a)
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
