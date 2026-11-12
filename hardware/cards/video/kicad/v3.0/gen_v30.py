#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""gen_v30.py - the YACC1 video card V3.0 (HD63484 ACRTC, VGA; 2026-11-11): the schematic, the project rules and the
unrouted 4-layer board, all from v30_netlist.py (the circuit). Design note:
docs/cards/video-v3.md (10a the parts, 10b and 10c every equation, 10d the simulation that timed them).

Made from the V2.0 card's gen_v20.py: the sheet writer's use, the silkscreen placer and the checks are its; the sheets,
the local symbols and footprints, the placement and the key connections are this card's.

THE SCHEMATIC IS DONE; THERE IS NO BOARD, AND THE CARD IS NOT BUILT (decided 2026-11-12). The work stopped after the
schematic. At the V2.0 card's spacing (columns 14 mm apart, a capacitor beside every chip, 6.3 mm between the chips of
a column) the 47 ICs need about 250 mm, against the 218 mm of every long card; a 250 mm card was chosen (2026-11-11:
LENGTH) and `gen_v30.py board` shows the columns, but the small parts are not placed clear (`gen_v30.py place` fails)
and there is no build.sh. The design is kept as the starting point for a video card on another machine: the design
note's section 13.

The schematic is a root sheet and one sheet per functional block (SHEETS), each drawn by tools/kicad/sch_wire.py: ELK
places the parts and the nets between them are wires; the bus signals, power and one-pin nets keep a stub to a label or
a power symbol (the CF card's sheet writer gen_cf.py underneath). Parts KiCad has no symbol for (the HD63484, the
32-pin static RAM, the Mini-DIN with its shield) are drawn into the local library video-v3.0-local.
One local footprint: the Mini-DIN, drawn from the Same Sky MD-60SM data sheet (minidin_footprint(), as V2.0's); the
DE-15 is KiCad's own.
The board: the blank V3.2 card's X1 and outline, lengthened (LENGTH), 4 layers (In1.Cu GND plane, In2.Cu VCC plane, as
the V2.0 and memory v2.0 boards), every part placed here, every pad on its schematic net, keepouts round X1's two screws.

Run with KiCad's bundled Python (pcbnew), from this folder:
  gen_v30.py sch                          -> local libraries + video-v3.0.kicad_sch (the root) and its sheets
                                             video-v3.0-<block>.kicad_sch (needs node + elkjs: tools/kicad)
  gen_v30.py project                      -> video-v3.0.kicad_pro + .kicad_dru (signals 0.25 mm / 0.2 mm, vias 0.8/0.4;
                                             class Power = GND, VCC: planes, never routed)
  gen_v30.py board <netlist> <out.pcb>    -> the unrouted board
  gen_v30.py place <pcb>                  -> the placement check: courtyards apart, everything inside the outline, the
                                             DIP sockets' outlines clear of each other and of the other parts
  gen_v30.py silk <pcb> [out]             -> the silkscreen texts placed clear (board() does it on every new board)
  gen_v30.py planes <pcb>                 -> each plane one piece: pads walled in by a same-net neighbour's thermal
                                             relief connected solid, the zones refilled (build.sh, on the routed board)
  gen_v30.py dsn|shuffle|ses|stats ...    -> as gen_v13.py (Specctra export/import, Freerouting seeds, route stats)
  gen_v30.py link <netlist> <pcb>         -> the footprints' schematic links (path) set from the netlist, nothing else
  gen_v30.py verify <netlist> <pcb>       -> the key connections pin by pin (schematic and board), layers, planes
  gen_v30.py bom                          -> BOM.md: the bill of materials from v30_netlist.PARTS (plain Python)
"""
import os, sys, re, json, uuid, shutil, subprocess, collections, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
CFDIR = os.path.join(ROOT, "hardware", "cards", "cf", "kicad", "v1.0")
V13DIR = os.path.join(HERE, "..", "v1.3")
sys.path.insert(0, HERE)
sys.path.insert(0, CFDIR)
sys.path.insert(0, os.path.join(ROOT, "tools", "kicad"))
import v30_netlist as N                                    # noqa: E402
import gen_cf                                              # noqa: E402  (the CF card's sheet writer, reused read-only)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


G13 = _load(os.path.join(V13DIR, "gen_v13.py"), "gen_v13")   # dsn / shuffle / ses / stats / refill / plane
P = "video-v3.0"
CLI = gen_cf.CLI
KFP = gen_cf.KFP
LOCAL = N.LOCAL
G = 2.54
LENGTH = 250.0                                             # mm, PROVISIONAL: the card from the bus connector's edge to the front
X0, Y0, Y1B = 17.747, 10.025, 123.995                      # the blank card's left, top and bottom edges
X1R = X0 + LENGTH                                          # the front edge
gen_cf.N = N
gen_cf.NETOF = {(r, p): n for n, conns in N.NETS.items() for r, p in conns}
gen_cf.NC = {(r, p) for r, ps in N.NO_CONNECT.items() for p in ps}
gen_cf.PROJ = P
gen_cf.ROOT_UUID = gen_cf.U("video-v3.0", "root")


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


# the HD63484's 64 pins (the manual's figure 4.1): number -> (name, electrical type). D8-D15 are open in 8-bit mode
HD63484 = {1: ("~{CUD1}", "output"), 2: ("~{CUD2}", "output"), 3: ("R/~{W}", "input"), 4: ("~{CS}", "input"),
           5: ("RS", "input"), 6: ("~{RES}", "input"), 7: ("~{DONE}", "bidirectional"), 8: ("~{DREQ}", "output"),
           9: ("~{DACK}", "input"), 10: ("~{DTACK}", "open_collector"), 11: ("~{IRQ}", "open_collector"),
           12: ("~{HSYNC}", "output"), 13: ("~{VSYNC}", "output"), 14: ("VCC", "power_in"),
           15: ("~{EXSYNC}", "bidirectional"), 16: ("VSS", "power_in"), 33: ("RA4", "output"),
           34: ("MA19/RA3", "output"), 35: ("MA18/RA2", "output"), 36: ("MA17/RA1", "output"),
           37: ("MA16/RA0", "output"), 49: ("VCC", "power_in"), 50: ("2CLK", "input"), 51: ("VSS", "power_in"),
           52: ("MCYC", "output"), 53: ("~{AS}", "output"), 54: ("~{DRAW}", "output"), 55: ("MRD", "output"),
           56: ("CHR", "output"), 62: ("~{DISP2}", "output"), 63: ("~{DISP1}", "output"), 64: ("LPSTB", "input")}
HD63484.update({17 + i: ("D%d" % i, "bidirectional") for i in range(16)})
HD63484.update({38 + i: ("MAD%d" % (15 - i), "bidirectional") for i in range(11)})      # 38 = MAD15 ... 48 = MAD5
HD63484.update({57 + i: ("MAD%d" % (4 - i), "bidirectional") for i in range(5)})        # 57 = MAD4 ... 61 = MAD0
# the 128K x 8 static RAM in DIP-32 (Alliance AS6C1008, its data sheet's figure); pin 1 and pin 30 are A18 and A17 of
# the 512K part
SRAM32 = {1: "NC/A18", 2: "A16", 3: "A14", 4: "A12", 5: "A7", 6: "A6", 7: "A5", 8: "A4", 9: "A3", 10: "A2", 11: "A1",
          12: "A0", 13: "DQ0", 14: "DQ1", 15: "DQ2", 16: "VSS", 17: "DQ3", 18: "DQ4", 19: "DQ5", 20: "DQ6", 21: "DQ7",
          22: "~{CE}", 23: "A10", 24: "~{OE}", 25: "A11", 26: "A9", 27: "A8", 28: "A13", 29: "~{WE}", 30: "CE2/A17",
          31: "A15", 32: "VCC"}


def local_symbols():
    io, inp, pas, pw, tri = "bidirectional", "input", "passive", "power_in", "tri_state"
    side = lambda pins: [(str(p), HD63484[p][0], HD63484[p][1]) for p in pins]
    acrtc = box_symbol(
        "HD63484", "IC", "HD63484 ACRTC, DIP-64 (0.9 inch): the host side on the left, the frame memory side on the right",
        left=side([4, 3, 5, 6, 9, 7, 8, 10, 11, 15] + list(range(17, 33)) + [12, 13, 1, 2]),
        right=side([50, 52, 53, 54, 55, 56] + list(range(61, 56, -1)) + list(range(48, 37, -1)) + [37, 36, 35, 34, 33] +
                   [63, 62, 64]),
        top=side([14]) + [None] * 5 + side([49]), bottom=side([16]) + [None] * 5 + side([51]), width=27.94)
    adr = [12, 11, 10, 9, 8, 7, 6, 5, 27, 26, 23, 25, 4, 28, 3, 31, 2]
    sram = box_symbol(
        "SRAM_DIP32", "IC", "128K x 8 static RAM, DIP-32 600 mil (AS6C1008); pins 1 and 30 are A18 and A17 of the 512K part",
        left=[(str(p), SRAM32[p], inp) for p in adr + [30, 1, 22, 24, 29]],
        right=[(str(p), SRAM32[p], tri) for p in (13, 14, 15, 17, 18, 19, 20, 21)],
        top=[("32", "VCC", pw)], bottom=[("16", "VSS", pw)], width=20.32)
    mdin = box_symbol("MINIDIN6", "J", "Mini-DIN-6 female (PS/2): 1 data, 3 GND, 4 +5V, 5 clock, 2/6 unused; S = shell",
                      left=[(str(i), ("DATA", "nc", "GND", "+5V", "CLK", "nc")[i - 1], pas) for i in range(1, 7)],
                      right=[("S", "SHELL", pas)], width=12.7)
    text = "\n".join(['(kicad_symbol_lib', '\t(version 20251024)', '\t(generator "gen_v30")', '\t(generator_version "1.0")',
                      acrtc, sram, mdin, ')', ''])
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
    L = ['(footprint "MiniDIN6_MD-60SM"', '\t(version 20241229)', '\t(generator "gen_v30")', '\t(layer "F.Cu")',
         '\t(descr "Mini-DIN-6 (PS/2) right-angle PCB jack Same Sky (CUI) MD-60SM, data sheet MD-SM rev 1.09 '
         '2024-09-12, PCB layout for date codes after 03/03/2022; mating face at x = 0, opening towards +x '
         '(YACC1 video V2.0 and V3.0)")', '\t(attr through_hole)',
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


# The DE-15 (VGA) socket J1 has KiCad's own footprint (v30_netlist.FP_VGA): the common right-angle PCB part with a
# stamped shell, pins in three rows 2.29 mm apart along the rows, the first row 3.03 mm and the two 3.2 mm mounting
# holes 4.94 mm inside the board's edge, 25 mm apart. Its origin is pin 1; the board's edge is the line y = 6.83 of the
# footprint, and the shell reaches 6.4 mm past it.
# TO VERIFY against the part bought before any order: the rows' spacing (1.90 mm here; 1.98 on some makers' drawings).
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
        '\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.kicad_sym")(options "")(descr "HD63484, 32-pin static RAM, Mini-DIN (gen_v30.py)"))\n'
        ')\n' % (N.BUSLIB, N.BUSLIB, LOCAL, LOCAL))
    open(os.path.join(HERE, "fp-lib-table"), "w").write(
        '(fp_lib_table\n\t(version 7)\n'
        '\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.pretty")(options "")(descr "FABC96R from the blank V3.2 card"))\n'
        '\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.pretty")(options "")(descr "MiniDIN6_MD-60SM (gen_v30.py)"))\n'
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
    ("bus", "Bus and ports", "BUS INTERFACE: THE SIX PORTS' STROBES, THE CHIP'S CS, RS AND R/W, ITS DATA BUFFER",
     _whole("IC2", "IC3", "IC4", "IC39", "IC5", "RN5") + _g("IC30", 3) + _whole("R1", "JP1"),
     (_u("X1", 1, 2, 3), "left"),
     "X1: the YACC1 V3.2 bus (DIN 41612). IC2 (writes) and IC3 (reads) decode IO-ADDR0-3: ports PA-PF = 1010-1111.\n"
     "CS (IC4) = any of OUT PA, OUT PB, IN PC, IN PD. RS = IO-ADDR0 and R/W = IO-ADDR2 through IC39, a latch that CS\n"
     "closes: an IN record drops the port number with its strobe, and the chip wants them until CS has risen.\n"
     "IC5 between the chip's D0-7 and the bus: enabled by CS, direction R/W. IC30/A: -RESET to the chip's RES and DACK."),
    ("chip", "ACRTC and timing", "THE HD63484, THE DOT CLOCK, THE DOT COUNTER, P56 AND VALID",
     _whole("IC1", "OSC1", "IC6") + _g("IC16", 2, 4, 6, 8) + _g("IC31", 3) + _g("IC18", 12) + _whole("IC7"), None,
     "IC6 counts the 25.175 MHz dot clock: QB is the chip's 2CLK, QC follows its MCYC (the counter loads NOT MCYC in\n"
     "dots 3 and 7, so QA-QC are the dot number in a memory cycle). IC7/A is P56, a flip-flop high in dots 5 and 6\n"
     "of every cycle: the one edge the card times things with. IC7/B is VALID: AS came in this cycle (a dummy cycle\n"
     "has none). The chip's host side is on sheet 2, its memory side on sheets 4 to 7."),
    ("memory", "Frame memory", "ADDRESS LATCHES, THE TWO RAMS, THE FONT EPROM AND ITS COPY, THE MAD BUFFERS, THEIR CONTROL",
     _whole("IC8", "IC9", "RN1", "RN2", "IC36") + _g("IC16", 10) + _g("IC32", 11) + _g("IC21", 11) +
     _whole("JP4", "IC10", "IC11", "RN3", "RN4", "IC14", "IC15", "IC12", "IC13") + _g("IC17", 1) + _g("IC20", 6) +
     _g("IC18", 6) + _g("IC20", 8) + _g("IC31", 8) + _g("IC31", 6) + _g("IC20", 3) + _g("IC38", 6) + _u("IC37", 1) +
     _g("IC21", 8), None,
     "IC8 / IC9 hold MAD0-15 while AS is high. The RAM where MA19 is low or CHR is high, the font (IC14, its byte on\n"
     "both halves through IC15) where MA19 is high; CHR (a character screen) forces A16-18 high (IC36).\n"
     "MOE (IC18/B) = NAND(VALID, AS, NOT W): the memories drive the data lines from the end of AS to the end of the\n"
     "cycle, never in a drawing write (W, IC17/A). -WE = NAND(P56, W). IC12 / IC13 between the RAM and MAD in a\n"
     "drawing cycle: IC37/A, on in dots 5-7 of a write and 6-7 of a read. JP4: pin 30 of the RAMs, CE2 or A17."),
    ("dots", "Dots", "THE GRAPHICS SHIFT REGISTERS AND THEIR LOAD, THE DELAY LINE, THE TWO LAYERS MIXED, THE DOT RETIMED",
     _g("IC16", 12) + _g("IC21", 6) + _g("IC32", 8) + _whole("IC19") + _g("IC38", 8) +
     _whole("IC22", "IC23", "IC40") + _g("IC20", 11) + _g("IC18", 8) + _g("IC31", 11) + _u("IC37", 2) +
     _whole("R19"), None,
     "IC22 / IC23 load the RAM's word in dot 7 of a Background cycle with the display on (GLOAD, IC38/B) and shift\n"
     "it out bit 0 first; a word fetched with the display off is not loaded, which is the blanking. IC40 delays the\n"
     "dot 8 dots, into step with the text. VIDN = NOT ((G OR T) AND NOT (G AND T AND TXOR)); IC37/B puts it on the\n"
     "dot clock. DISPWN (IC19/C) marks a Window cycle for method A. R19 holds the text dot low without its parts."),
    ("video", "Control and video", "THE CONTROL REGISTER FROM THE ATTRIBUTE BYTE, THE THREE GUNS, THE SYNCS, THE VGA SOCKET",
     _whole("IC34", "IC35") + _g("IC21", 3) + _g("IC17", 4, 10, 13) + _g("IC32", 3, 6) +
     _whole("R2", "R3", "R4", "R5", "R6", "J1"), None,
     "IC34 takes MAD0-7 as dot 7 begins in every cycle (P56's end); IC35 copies it when HSYNC rises, the one moment\n"
     "it holds the chip's attribute byte (ATR). Bits 0-2: red, green, blue off; 3, 4: HSYNC, VSYNC positive; 5: text\n"
     "on; 6: XOR; 7: the second font. Each gun = the dot AND NOT its off bit, through 470 ohm into the monitor's 75."),
    ("text", "Text A", "TEXT METHOD A: EIGHT SOCKETS, EMPTY ON THE FIRST BUILD",
     _whole("IC41", "IC42", "IC43", "IC44", "IC45", "IC46", "IC47", "IC48"), None,
     "In superimposed access the Window's cycle reads a character word: IC44 / IC45 take its two codes and IC46 the\n"
     "raster line as dot 4 begins (WCK, IC41/A). The left code addresses the character generator IC47 for the rest\n"
     "of the cycle, the right one through the next (WPH, IC41/B); IC48 loads the 8 dots at each cycle's end and\n"
     "shifts them out as TDOT. CUD1, CUD2 and FONT2 are address lines of IC47: the cursor and a second font."),
    ("ps2", "PS2", "PS/2: ATMEGA328P, LATCHES ON PE / PF, THE CARD STATUS, FTDI, -INT, RESET",
     _whole("IC24", "Y1", "C53", "C54", "R7", "C55", "J4", "R8") + _g("IC30", 6, 8, 11) + _whole("IC29") +
     _whole("IC25", "IC26", "IC27", "IC28", "JP2", "JP3", "R16", "F1", "R9", "R10", "R11", "R12", "R13", "R14",
            "R15", "J2", "J3"), None,
     "IC24 runs embedded/video-ps2. OUT PE loads a command into IC26 (BUSY set), IN PF reads a byte from IC25 (FULL\n"
     "cleared), IN PE the status IC27: FULL, SRC, BUSY, TEXT (JP3: method A's parts are fitted) and the ID 0110.\n"
     "-INT = INTREQ AND FULL (IC30/B) through IC29/D and JP2. The bus -RESET reaches MRST through IC30/C, IC29/E\n"
     "and IC29/F (open collector, R8): it only ever pulls MRST low."),
    ("power", "Power", "POWER UNITS, DECOUPLING, POWER LED, THE F PARTS' PULL-UP",
     _whole("R17", "LED1", "R18"), (None, "top"),
     "One 100 nF per IC beside its VCC pin (C50 at the chip's second VCC pin, C52 at the ATmega's AVCC), C1 47 uF\n"
     "bulk. The bus supplies VCC and GND (X1, six pins each): the PWR_FLAGs. PU (R18, 1k) holds the 74F parts'\n"
     "unused inputs high. Spare gates: IC4/B, IC19/A, three of IC29, three of IC43."),
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
    return gen_cf.U("video-v3.0", "sheet", key, "instance")


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
        head = ['(kicad_sch', '\t(version 20260306)', '\t(generator "gen_v30")', '\t(generator_version "1.0")',
                '\t(uuid "%s")' % file_uuid, '\t(paper "%s")' % paper,
                '\t(title_block (title "YACC1 video card V3.0: %s") (date "%s") (rev "%s") (company "YACC1")'
                % (title, N.DATE, N.REV),
                '\t\t(comment 1 "Sheet %s of the video card V3.0 schematic (root: video-v3.0.kicad_sch)")' % page,
                '\t\t(comment 2 "Circuit source: v30_netlist.py; this sheet is generated by gen_v30.py")',
                '\t\t(comment 3 "Design note and theory: docs/cards/video-v3.md"))',
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
        S = SubSheet("video-v3.0/" + key, lambda net: "hier", shape=lambda net, n=name: pin_shape(D, n, net))
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
        S.write(os.path.join(HERE, fname), gen_cf.U("video-v3.0", "sheet", key, "file"), name, paper, page)
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
                          gen_cf.U("video-v3.0", "rline", key)))
        for side, i, n, s, k in placed:
            py = y + (i + 1) * G
            px = x if side == "L" else x + w
            L.append('\t\t(pin %s %s (at %s %s %d) %s (justify %s)) (uuid "%s"))'
                     % (gen_cf.q(n), s, gen_cf.f(px), gen_cf.f(py), 180 if side == "L" else 0, eff,
                        "left" if side == "L" else "right", gen_cf.U("video-v3.0", "spin", key, n + k)))
            ex = px - 2 * G if side == "L" else px + 2 * G
            out.append('\t(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid "%s"))'
                       % (gen_cf.f(px), gen_cf.f(py), gen_cf.f(ex), gen_cf.f(py),
                          gen_cf.U("video-v3.0", "rw", key, n + k)))
            ang, just = (180, "right bottom") if side == "L" else (0, "left bottom")
            out.append('\t(label %s (at %s %s %d) %s (justify %s)) (uuid "%s"))'
                       % (gen_cf.q(n), gen_cf.f(ex), gen_cf.f(py), ang, eff, just,
                          gen_cf.U("video-v3.0", "rl", key, n + k)))
            nl += 1
        L += ['\t\t(instances (project "%s" (path "/%s" (page "%d"))))' % (P, ROOT_UUID, page), '\t)']
        out.append("\n".join(L))
        X = x + w + rw + 10
        rowh = max(rowh, h)
    note = ["The video card V3.0, one sheet per functional block:"]
    note += ["  sheet %d  %-12s %s" % (page, name, title) for key, name, title, fname, su, page, pins in blocks]
    note += ["", "Every net of a sheet is a pin of its sheet symbol here, and the local label at each pin names the net",
             "(/NAME, the names on the board). Above the dashed line: the nets the sheet shares with other sheets (left:",
             "it reads them, right: it drives them). Below it: the nets drawn on that sheet only, a pin on each side",
             "(KiCad's ERC counts a root label as connected only when another label of its name is on the root sheet).",
             "VCC and GND are power symbols on the sheets."]
    out.append('\t(text %s (exclude_from_sim no) (at 25.4 15.24 0) (effects (font (size 1.5 1.5)) (justify left top)) '
               '(uuid "%s"))' % (gen_cf.q("\n".join(note)), gen_cf.U("video-v3.0", "rootnote")))
    paper = W.paper_for(X - 25.4, Y + rowh + 10 - 22.86)[0]
    head = ['(kicad_sch', '\t(version 20260306)', '\t(generator "gen_v30")', '\t(generator_version "1.0")',
            '\t(uuid "%s")' % ROOT_UUID, '\t(paper "%s")' % paper,
            '\t(title_block (title "YACC1 video card V3.0") (date "%s") (rev "%s") (company "YACC1")' % (N.DATE, N.REV),
            '\t\t(comment 1 "HD63484 ACRTC on ports PA-PD, 640 x 480 VGA, sockets for text method A, PS/2 keyboard and mouse on PE / PF")',
            '\t\t(comment 2 "Circuit source: v30_netlist.py; these sheets are generated by gen_v30.py")',
            '\t\t(comment 3 "Design note and theory: docs/cards/video-v3.md"))',
            '\t(lib_symbols)']
    tail = ['\t(sheet_instances (path "/" (page "1")))', '\t(embedded_fonts no)', ')', '']
    open(os.path.join(HERE, P + ".kicad_sch"), "w").write("\n".join(head + out + tail))
    return nl


def check_schematic_netlist(netfile):
    """the schematic's exported netlist = v30_netlist.NETS (label nets come back as /NAME)"""
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
        print("  net %s: schematic %s, v30_netlist %s" % (n, sorted(got.get(n, ()))[:6], sorted(want.get(n, ()))[:6]))
    print("schematic netlist vs v30_netlist.py: %s (%d nets)" % ("MATCH" if not bad else "%d DIFFER" % len(bad), len(want)))
    return not bad


def sch():
    probs = N.check()
    if probs:
        raise SystemExit("v30_netlist.check():\n" + "\n".join(probs))
    why = W.elk_ready()
    if why:
        raise SystemExit("gen_v30.py sch: " + why)
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
DRU = G13.DRU.replace("video card v1.3", "video card V3.0").replace("gen_v13.py", "gen_v30.py")


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
# PROVISIONAL (2026-11-11): a first trial on a 250 mm outline. The ICs' columns are clear of each other; the resistors,
# the networks, the oscillator and the PS/2 corner are not sorted out. It waits for the card's length to be decided.
# The ICs stand in columns, pin 1 at the top left, their decoupling capacitor beside the VCC pin (the top right one).
# Left to right: the bus side; the chip, its host pins towards the bus; the address latches and MAD buffers with the
# counter; the control gates; the RAMs; the font; the shift registers and the video; text method A's sockets; the PS/2
# section; the front edge with the VGA socket, the two PS/2 jacks, the FTDI header and the LED.
GAP = 6.3                                                 # between two chips in a column, end pin to end pin
PLACE = {}


def ic_size(ref):
    fp = N.PARTS[ref][2]
    n = int(re.search(r"DIP-(\d+)", fp).group(1))
    w = 22.86 if "W22.86" in fp else 15.24 if "W15.24" in fp else 7.62
    return n, w


def stack(x, y, *refs):
    """a column of DIPs from y down, pin 1 at (x, y); -> the y after the last"""
    for r in refs:
        n, w = ic_size(r)
        PLACE[r] = (x, y, 0)
        y += (n // 2 - 1) * G + GAP
    return y


TOP = 15.0
stack(32.0, TOP, "IC39", "IC2", "IC5", "IC3")              # RS and R/W held, the two decoders, the chip's data buffer
stack(48.0, 20.5, "IC1")
PLACE["IC4"] = (48.0, 105.5, 0); PLACE["IC30"] = (62.0, 105.5, 0)        # under the chip: CS; -RESET's gates
stack(78.0, TOP, "IC8", "IC34", "IC9", "IC7")              # MAD0-7 latched, MAD0-7 for the attribute byte, MAD8-15, P56
stack(92.0, TOP, "IC12", "IC6", "IC13", "IC16")            # the two MAD buffers round the counter
stack(106.0, TOP, "IC18", "IC38", "IC20", "IC31", "IC37")  # the gates and flip-flops that time the memory
stack(120.0, TOP, "IC10", "IC11"); PLACE["OSC1"] = (120.0, 105.5, 0)
stack(143.0, TOP, "IC14", "IC15", "IC36", "IC21")          # the font and its copy; CHR in the address, the chip enables
stack(166.0, TOP, "IC22", "IC23", "IC40", "IC32")          # the two shift registers, the delay line
stack(180.0, TOP, "IC35", "IC17", "IC19", "IC48")          # the control register, the guns' gates; the text shifter
stack(194.0, TOP, "IC44", "IC45", "IC46", "IC41")          # text method A
stack(208.0, TOP, "IC47", "IC42", "IC43", "IC29")
stack(231.0, TOP, "IC28", "IC25", "IC26", "IC27")          # the PS/2 flags, latches and status
PLACE["IC24"] = (252.0, 87.0, 0)                          # the ATmega, under the two jacks


def pin_xy(ref, pin):
    """a DIP's pin on the board (rotation 0)"""
    x, y, rot = PLACE[ref]
    n, w = ic_size(ref)
    return (x, y + (pin - 1) * G) if pin <= n // 2 else (x + w, y + (n - pin) * G)


def cap_at(ref, pin, gnd):
    """a decoupling capacitor standing 3.2 mm outside a VCC pin, its other lead towards the GND pin"""
    x, y = pin_xy(ref, pin)
    n, w = ic_size(ref)
    out = -3.2 if pin <= n // 2 else 3.2
    return (x + out, y, 270 if pin_xy(ref, gnd)[1] >= y else 90)


for _cap, _ic in N.DECOUPLE.items():
    if _ic.startswith("IC") or _ic == "OSC1":
        _vcc, _gnd = (N.POWER_PINS[_ic][0][0], N.POWER_PINS[_ic][1][0]) if _ic != "OSC1" else (14, 7)
        PLACE[_cap] = cap_at(_ic, _vcc, _gnd)
PLACE["C50"] = cap_at("IC1", 49, 51)                      # the chip's second VCC pin
PLACE["C52"] = cap_at("IC24", 20, 22)                     # the ATmega's AVCC
_gapx = lambda col, w=7.62: col + w + 1.3 + 2.0           # a line in the gap right of a column, clear of its sockets
PLACE.update({
    # the bus side: the chip's data pull-ups, DONE's pull-up, the IRQ jumper and the bulk capacitor at the top edge
    "RN5": (44.5, 73.0, 270), "R1": (44.5, 24.0, 270), "JP1": (52.0, 13.2, 90), "C1": (62.0, 14.4, 0),
    # MAD's pull-ups in the gap between the chip and the latches; the RAM data lines' between the RAMs and the font
    "RN1": (74.4, 24.0, 270), "RN2": (74.4, 67.0, 270), "RN3": (139.1, 22.0, 270), "RN4": (139.1, 66.0, 270),
    "JP4": (133.0, 121.2, 90),                             # the RAMs' pin 30, at the bottom edge under them
    "R18": (115.6, 22.0, 270),                             # PU
    "R19": (189.6, 100.0, 270),                            # the text dot's pull-down, beside the text shifter
    # the front edge: the VGA socket and its five resistors, the two PS/2 jacks with their pull-ups and fuse
    "J1": (X1R - DE15_EDGE, 22.5, 270),
    "R2": (244.5, 17.0, 0), "R3": (244.5, 21.0, 0), "R4": (244.5, 25.0, 0), "R5": (244.5, 29.0, 0), "R6": (244.5, 33.0, 0),
    "J2": (X1R, 58.0, 0), "J3": (X1R, 76.0, 0),
    "R12": (244.0, 52.0, 270), "R13": (247.5, 52.0, 270), "R14": (244.0, 70.0, 270), "R15": (247.5, 70.0, 270),
    "F1": (244.0, 64.0, 0),
    # round the ATmega: reset, crystal, the latches' pull-ups, the FTDI header, the jumpers and the LED at the front edge
    "R7": (243.0, 87.0, 270), "C55": (246.5, 87.0, 270), "R8": (220.0, 100.0, 270),
    "Y1": (245.0, 107.3, 270), "C53": (241.8, 106.0, 270), "C54": (241.8, 112.0, 270),
    "R9": (243.0, 98.0, 270), "R10": (246.5, 98.0, 270), "R11": (246.5, 112.0, 270), "R16": (243.0, 116.0, 0),
    "J4": (X1R - 2.2, 94.0, 0), "JP2": (X1R - 2.2, 86.0, 0), "JP3": (X1R - 6.5, 86.0, 0),
    "LED1": (X1R - 3.5, 113.0, 90), "R17": (X1R - 3.5, 119.5, 180),
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
    unclear = silk_place(b, silk_texts(b))
    pcbnew.SaveBoard(out, b)
    print("silk: every reference and legend placed clear of other silk, the pads and the edge%s" % (
        "" if not unclear else " except %s" % ", ".join(unclear)))
    G13.refill(out)
    print("board %s: %d footprints placed, %d pads on nets, %.2f x %.2f mm, 4 layers (In1 GND, In2 VCC planes)" % (
        os.path.basename(out), len(fps), n, X1R - X0, Y1B - Y0))


SILK_H, SILK_W = 1.0, 0.15       # every text on the silk: JLCPCB's standard characters (>= 1.0 mm high, >= 0.15 mm strokes)
# the legends: (text, x, y, size) left-justified at (x, y), or (text, x, y, size, angle) centred on (x, y)
SILK = [("YACC1 Video Card V3.0", 150.0, 122.3, 1.5), ("cottageworker.com", 181.0, 122.3, 1.0),
        ("KEYBOARD (PURPLE)", X1R - 15.2, 58.0, 1.0, 90), ("MOUSE (GREEN)", X1R - 15.2, 76.0, 1.0, 90),
        ("TEXT A: IC41-IC48", 198.0, 122.3, 1.0)]
_j4x, _j4y = PLACE["J4"][:2]
SILK += [(t, _j4x - 9.5, _j4y + 2.54 * k, 1.0) for k, t in enumerate(("1 GND (BLK)", "CTS", "VCC nc", "TXD", "RXD", "DTR"))]
# the jumpers' positions (the board-layout rules: every position labelled with what it selects; the function itself
# stands beside the reference, COMPANION)
_jp4x, _jp4y = PLACE["JP4"][:2]                           # lying: pin 1 at the left
SILK += [("128K", _jp4x - 0.3, _jp4y - 2.6, 1.0, 0), ("512K", _jp4x + 5.4, _jp4y - 2.6, 1.0, 0)]
_jp1x, _jp1y = PLACE["JP1"][:2]
SILK += [("ON: IRQ TO -INT", _jp1x + 5.0, _jp1y, 1.0)]
_jp2x, _jp2y = PLACE["JP2"][:2]
SILK += [("ON: PS/2 -INT", _jp2x - 12.0, _jp2y - 3.0, 1.0)]
_jp3x, _jp3y = PLACE["JP3"][:2]
SILK += [("ON: TEXT A FITTED", _jp3x - 14.0, _jp3y + 5.6, 1.0)]
# the text beside a reference (the board-layout rules): each IC's type, the LED's and the jumpers' function, every
# resistor's, network's, capacitor's and crystal's value, the oscillator's frequency
TYPE_SHORT = {"IC10": "AS6C1008-55", "IC11": "AS6C1008-55"}
VALUE_SHORT = {"C1": "47u", "F1": "0.5A"}
COMPANION = dict({r: TYPE_SHORT.get(r, v[0]) for r, v in N.PARTS.items() if r.startswith("IC")},
                 **{r: VALUE_SHORT.get(r, v[0]) for r, v in N.PARTS.items() if re.match(r"(RN?|C|Q|Y|F)\d", r)},
                 OSC1="25.175MHz", LED1="PWR", JP1="IRQ-EN", JP2="KBD-INT", JP3="TEXT", JP4="RAM",
                 X1="DIN41612 96", J1="VGA", J4="FTDI")
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
    """gen_v30.py silk <pcb> [out]: the silkscreen texts written afresh (silk_texts()) and placed (silk_place()) on a
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
    """gen_v30.py planes <pcb>: each plane filled as one piece (2026-11-03). Where two pads of the plane's net stand side
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


# the V3.0 key connections, checked pin by pin in the schematic netlist and on the board's pads: written from the design
# note's equations (docs/cards/video-v3.md 10a-10c), not from v30_netlist.py
KEY = [
    # the ports: IO-ADDR on both decoders, the strobe that enables each, the four chip strobes into CS
    ("IC2", "1", "IO-ADDR0"), ("IC2", "2", "IO-ADDR1"), ("IC2", "3", "IO-ADDR2"), ("IC2", "6", "IO-ADDR3"),
    ("IC2", "4", "-IO-WR"), ("IC3", "4", "-IO-RD"), ("IC3", "6", "IO-ADDR3"), ("IC2", "13", "WRPA#"),
    ("IC2", "12", "WRPB#"), ("IC2", "9", "WRPE#"), ("IC3", "11", "RDPC#"), ("IC3", "10", "RDPD#"), ("IC3", "9", "RDPE#"),
    ("IC3", "7", "RDPF#"), ("IC4", "1", "WRPA#"), ("IC4", "2", "WRPB#"), ("IC4", "4", "RDPC#"), ("IC4", "5", "RDPD#"),
    ("IC4", "6", "CS#"), ("IC1", "4", "CS#"), ("IC5", "19", "CS#"),
    # RS and R/W through the latch that CS closes; the bus buffer's direction from the latched R/W
    ("IC39", "2", "IO-ADDR0"), ("IC39", "3", "IO-ADDR2"), ("IC39", "11", "CS#"), ("IC39", "1", "GND"),
    ("IC39", "19", "RS"), ("IC1", "5", "RS"), ("IC39", "18", "RWL"), ("IC1", "3", "RWL"), ("IC5", "1", "RWL"),
    ("IC5", "2", "HD0"), ("IC1", "17", "HD0"), ("IC5", "18", "DATA0"), ("IC5", "9", "HD7"), ("IC1", "24", "HD7"),
    ("IC5", "11", "DATA7"), ("X1", "A19", "DATA0"), ("X1", "A26", "DATA7"),
    # reset, the 8-bit mode, the chip's supply pins and the pins tied off
    ("IC30", "1", "-RESET"), ("IC30", "3", "RESB#"), ("IC1", "6", "RESB#"), ("IC1", "9", "RESB#"),
    ("IC1", "14", "VCC"), ("IC1", "49", "VCC"), ("IC1", "16", "GND"), ("IC1", "51", "GND"), ("IC1", "64", "GND"),
    ("IC1", "7", "DONE#"), ("R1", "1", "DONE#"), ("IC1", "11", "IRQ#"), ("JP1", "1", "IRQ#"), ("JP1", "2", "-INT"),
    # the dot clock and the counter: QB = 2CLK, the load in dots 3 and 7 with NOT MCYC on C
    ("OSC1", "8", "CK"), ("IC6", "2", "CK"), ("IC6", "13", "2CLK"), ("IC1", "50", "2CLK"), ("IC6", "14", "QA"),
    ("IC6", "12", "QC"), ("IC31", "1", "QA"), ("IC31", "2", "2CLK"), ("IC31", "3", "LD163#"), ("IC6", "9", "LD163#"),
    ("IC1", "52", "MCYC"), ("IC16", "3", "MCYC"), ("IC16", "4", "MCYCN"), ("IC6", "5", "MCYCN"), ("IC6", "3", "GND"),
    ("IC6", "4", "GND"), ("IC6", "6", "GND"),
    # P56 and VALID
    ("IC18", "1", "QC"), ("IC18", "2", "QBN"), ("IC18", "13", "VCC"), ("IC18", "12", "P56D"), ("IC7", "2", "P56D"),
    ("IC7", "3", "CK"), ("IC7", "5", "P56#"), ("IC7", "6", "P56"), ("IC1", "53", "AS#"), ("IC7", "10", "AS#"),
    ("IC7", "11", "QCN"), ("IC7", "12", "GND"), ("IC7", "9", "VALID"),
    # the address latches, the RAMs' and the font's selects, CHR in the address
    ("IC16", "1", "AS#"), ("IC16", "2", "ASN"), ("IC8", "11", "ASN"), ("IC9", "11", "ASN"), ("IC1", "61", "MAD0"),
    ("IC8", "2", "MAD0"), ("IC8", "19", "A0"), ("IC10", "12", "A0"), ("IC11", "12", "A0"), ("IC14", "10", "A0"),
    ("IC1", "38", "MAD15"), ("IC9", "9", "MAD15"), ("IC9", "12", "A15"), ("IC10", "31", "A15"),
    ("IC1", "56", "CHR"), ("IC1", "37", "MA16"), ("IC36", "1", "MA16"), ("IC36", "2", "CHR"), ("IC36", "3", "RA16"),
    ("IC10", "2", "RA16"), ("IC11", "2", "RA16"), ("IC1", "34", "MA19"), ("IC21", "12", "MA19"), ("IC21", "13", "CHRN"),
    ("IC21", "11", "RAMCE#"), ("IC10", "22", "RAMCE#"), ("IC11", "22", "RAMCE#"), ("IC36", "11", "ROMCE#"),
    ("IC14", "20", "ROMCE#"), ("JP4", "1", "VALID"), ("JP4", "2", "RSEL"), ("IC10", "30", "RSEL"), ("JP4", "3", "RA17"),
    # W, MOE, -WE, the font's copy
    ("IC1", "54", "DRAW#"), ("IC1", "55", "MRD"), ("IC17", "2", "DRAW#"), ("IC17", "3", "MRD"), ("IC17", "1", "W"),
    ("IC20", "4", "DRAW#"), ("IC20", "5", "MRD"), ("IC20", "6", "WN"), ("IC18", "3", "VALID"), ("IC18", "4", "AS#"),
    ("IC18", "5", "WN"), ("IC18", "6", "MOE#"), ("IC10", "24", "MOE#"), ("IC11", "24", "MOE#"), ("IC14", "22", "MOE#"),
    ("IC20", "9", "ROMCE#"), ("IC20", "10", "MOE#"), ("IC20", "8", "F244#"), ("IC15", "1", "F244#"), ("IC15", "19", "F244#"),
    ("IC31", "9", "P56"), ("IC31", "10", "W"), ("IC31", "8", "WE#"), ("IC10", "29", "WE#"), ("IC11", "29", "WE#"),
    ("IC10", "13", "DL0"), ("IC11", "13", "DH0"), ("IC14", "11", "DL0"), ("IC15", "2", "DL0"), ("IC15", "18", "DH0"),
    # the MAD buffers: their flip-flop's D, their enable held a gate longer, their direction
    ("IC31", "6", "DRAWN"), ("IC38", "1", "DRAWN"), ("IC38", "2", "QC"), ("IC38", "4", "LD163#"), ("IC20", "1", "P56"),
    ("IC20", "2", "W"), ("IC20", "3", "BUFT"), ("IC38", "5", "BUFT"), ("IC38", "6", "BUFD"), ("IC37", "2", "BUFD"),
    ("IC37", "3", "CK"), ("IC37", "6", "BUFQN"), ("IC21", "9", "BUFQN"), ("IC21", "8", "BUFEN#"), ("IC12", "19", "BUFEN#"),
    ("IC13", "19", "BUFEN#"), ("IC12", "1", "MRD"), ("IC13", "1", "MRD"), ("IC12", "2", "DL0"), ("IC12", "18", "MAD0"),
    ("IC13", "2", "DH0"), ("IC13", "18", "MAD8"),
    # the graphics load, the shift registers, the delay line
    ("IC1", "63", "DISP1#"), ("IC16", "13", "DISP1#"), ("IC16", "12", "DISPON"), ("IC21", "4", "MRD"),
    ("IC21", "5", "DISPON"), ("IC21", "6", "BGON"), ("IC19", "3", "BGON"), ("IC19", "4", "DRAW#"), ("IC19", "5", "VALID"),
    ("IC19", "6", "DISPBG"), ("IC38", "9", "QA"), ("IC38", "10", "2CLK"), ("IC38", "12", "QC"), ("IC38", "13", "DISPBG"),
    ("IC38", "8", "GLOAD"), ("IC22", "19", "GLOAD"), ("IC23", "19", "GLOAD"), ("IC22", "12", "CK"), ("IC23", "12", "CK"),
    ("IC22", "17", "SR8"), ("IC23", "11", "SR8"), ("IC23", "16", "DL0"), ("IC22", "16", "DH0"), ("IC23", "17", "VDOT"),
    ("IC40", "11", "VDOT"), ("IC40", "12", "CK"), ("IC40", "19", "GND"), ("IC40", "17", "GDEL"),
    # the layers mixed, the dot retimed, the guns
    ("IC20", "12", "GDEL"), ("IC20", "13", "TDOT"), ("IC20", "11", "GOT"), ("IC18", "9", "GDEL"), ("IC18", "10", "TDOT"),
    ("IC18", "11", "TXOR"), ("IC18", "8", "NBX"), ("IC31", "12", "GOT"), ("IC31", "13", "NBX"), ("IC31", "11", "VIDN"),
    ("IC37", "12", "VIDN"), ("IC37", "11", "CK"), ("IC37", "9", "VIDQ"), ("IC17", "5", "VIDQ"), ("IC17", "6", "OFFR"),
    ("IC17", "4", "VR"), ("R2", "1", "VR"), ("R2", "2", "RED"), ("J1", "1", "RED"), ("J1", "2", "GREEN"),
    ("J1", "3", "BLUE"), ("J1", "13", "HSOUT"), ("J1", "14", "VSOUT"), ("J1", "5", "GND"), ("J1", "SH", "GND"),
    ("R19", "1", "TDOT"), ("R19", "2", "GND"),
    # the control register: MAD0-7 at P56's end, copied when HSYNC rises; the syncs' polarity
    ("IC34", "11", "P56#"), ("IC34", "3", "MAD0"), ("IC34", "18", "MAD7"), ("IC34", "2", "AT0"), ("IC35", "3", "AT0"),
    ("IC1", "12", "HSYNC#"), ("IC21", "1", "HSYNC#"), ("IC21", "2", "VCC"), ("IC21", "3", "HSCK"), ("IC35", "11", "HSCK"),
    ("IC34", "1", "RESB#"), ("IC35", "1", "RESB#"), ("IC35", "2", "OFFR"), ("IC35", "9", "POLH"), ("IC35", "12", "POLV"),
    ("IC35", "15", "TEXTON"), ("IC35", "16", "TXOR"), ("IC35", "19", "FONT2"), ("IC32", "1", "HSYNC#"),
    ("IC32", "2", "POLH"), ("IC32", "3", "HSB"), ("IC1", "13", "VSYNC#"), ("IC32", "4", "VSYNC#"), ("IC32", "6", "VSB"),
    # text method A: the latches' clock, which code drives the generator, the shifter's load, the cursors
    ("IC42", "1", "QCN"), ("IC42", "2", "2CLK"), ("IC42", "4", "QA"), ("IC42", "5", "DISPWN"), ("IC42", "6", "D3W"),
    ("IC41", "2", "D3W"), ("IC41", "3", "CK"), ("IC41", "5", "WCK"), ("IC44", "11", "WCK"), ("IC45", "11", "WCK"),
    ("IC46", "11", "WCK"), ("IC41", "12", "DISPWN"), ("IC41", "11", "QCN"), ("IC41", "9", "WPH"), ("IC44", "1", "WPH"),
    ("IC41", "8", "WPHN"), ("IC45", "1", "WPHN"), ("IC43", "3", "WANY"), ("IC42", "9", "QA"), ("IC42", "10", "WANY"),
    ("IC42", "12", "2CLK"), ("IC42", "13", "QC"), ("IC42", "8", "TLOAD"), ("IC48", "19", "TLOAD"), ("IC48", "12", "CK"),
    ("IC48", "9", "TEXTON"), ("IC48", "17", "TDOT"), ("IC44", "2", "DL0"), ("IC45", "2", "DH0"), ("IC44", "19", "CA0"),
    ("IC47", "6", "CA0"), ("IC46", "19", "RL0"), ("IC47", "10", "RL0"), ("IC1", "1", "CUD1#"), ("IC47", "2", "CUD1#"),
    ("IC1", "2", "CUD2#"), ("IC47", "27", "CUD2#"), ("IC47", "26", "FONT2"), ("IC47", "11", "CG0"), ("IC48", "16", "CG0"),
    # PS/2: the ATmega, the latches, the flags, INT, reset
    ("IC24", "4", "KCLK"), ("IC24", "5", "MCLK"), ("IC24", "6", "KDAT"), ("IC24", "11", "MDAT"), ("IC24", "12", "LDDATA"),
    ("IC24", "13", "RDCMD"), ("IC24", "16", "FULL"), ("IC24", "17", "BUSY"), ("IC24", "18", "INTREQ"), ("IC24", "19", "SRC"),
    ("IC26", "11", "WRPE#"), ("IC28", "11", "WRPE#"), ("IC27", "1", "RDPE#"), ("IC27", "19", "RDPE#"), ("IC25", "1", "RDPF#"),
    ("IC30", "12", "RDPF#"), ("IC30", "13", "-RESET"), ("IC30", "11", "FULLCLR"), ("IC28", "1", "FULLCLR"),
    ("IC28", "3", "LDDATA"), ("IC28", "5", "FULL"), ("IC28", "9", "BUSY"), ("IC27", "2", "FULL"), ("IC27", "4", "SRC"),
    ("IC27", "6", "BUSY"), ("IC27", "8", "TEXT"), ("JP3", "1", "TEXT"), ("R16", "1", "TEXT"), ("IC27", "11", "GND"),
    ("IC27", "13", "VCC"), ("IC27", "15", "VCC"), ("IC27", "17", "GND"),
    ("IC30", "4", "INTREQ"), ("IC30", "5", "FULL"), ("IC30", "6", "INTG"), ("IC29", "9", "INTG"), ("IC29", "8", "INTOC"),
    ("JP2", "1", "INTOC"), ("JP2", "2", "-INT"), ("X1", "C13", "-INT"), ("IC30", "9", "-RESET"), ("IC30", "8", "RESETB"),
    ("IC29", "11", "RESETB"), ("IC29", "10", "RESETH"), ("R8", "1", "RESETH"), ("IC29", "13", "RESETH"),
    ("IC29", "12", "MRST"), ("IC24", "1", "MRST"), ("R7", "1", "MRST"),
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
    """BOM.md from v30_netlist.PARTS: one line per value and footprint, text method A's parts marked"""
    rows = collections.OrderedDict()
    order = lambda r: (re.match(r"[A-Z]+", r).group(0), int(re.search(r"\d+", r).group(0)))
    for ref in sorted(N.PARTS, key=order):
        value, symid, fpid, note = N.PARTS[ref]
        if ref in N.DECOUPLE:
            note = "decoupling, 0.1 inch leads"
        key = (value, fpid.split(":")[1], "A" if ref in N.TEXT_A else "")
        rows.setdefault(key, [[], note])[0].append(ref)
    nsock = collections.Counter(ic_size(r) for r in N.PARTS if "DIP-" in N.PARTS[r][2])   # (the oscillator's too)
    L = ["# Video card V3.0 - bill of materials", "",
         "GENERATED by `gen_v30.py bom` from `v30_netlist.py` (%s) - do not edit. %d parts. **Text method A's parts** "
         "(marked A) are sockets left empty on the first build. Every IC and the oscillator in a socket: %s." % (
             N.DATE, len(N.PARTS), ", ".join("%d x %d-pin %.2f mm" % (n, p, w) for (p, w), n in sorted(nsock.items()))), "",
         "| Qty | Value | Footprint | References | Text A | Note |", "|---|---|---|---|---|---|"]
    for (value, fp, a), (refs, note) in rows.items():
        L.append("| %d | %s | %s | %s | %s | %s |" % (len(refs), value, fp, ", ".join(refs), a, note if len(refs) == 1 else ""))
    L += ["", "The 74ACT and 74F types are the ones the timing check was run with (`tests/video/v30_netsim.py`, "
          "`docs/cards/video-v3.md` 10d): a 74HCT or 74LS part in their place is another circuit.", ""]
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
    elif cmd == "silk":
        ok = silk_cmd(*a)
    elif cmd == "planes":
        ok = planes(*a)
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
