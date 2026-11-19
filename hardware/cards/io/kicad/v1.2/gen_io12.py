#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""gen_io12.py - the YACC1 I/O card V1.2 (2026-11-18): the schematic, the project rules and the 4-layer board with its
placement, all from io12_netlist.py (the circuit: the V1.1 card in the machine, with a data buffer, a DS12885 clock on
ports 6 and 7, a TTL serial header and the DB9 at the top edge). Theory of the card: docs/cards/io.md (section 8 has
what V1.2 changes).

Made from the video card V4.0's generator (hardware/cards/video/kicad/v4.0/gen_v40.py): the sheet writer's use, the
silkscreen placer, the planes, the checks and the order's files are its code; the sheets, the local parts, the
placement, the legends and the key connections are this card's. That card's clocks, laid before the router, have no
counterpart here; the clock chip's crystal has (xtal(): its two tracks drawn, the room round them kept clear).

The schematic is a root sheet and one sheet per functional block (SHEETS), each drawn by tools/kicad/sch_wire.py: ELK
places the parts and the nets between them are wires; the bus signals, power and one-pin nets keep a stub to a label or
a power symbol (the CF card's sheet writer gen_cf.py underneath). Local symbols (io-v1.2-local): the DS12885, the
TIL311 and the LCD module. Local footprints: the built V1.1 card's own for the parts whose fit is proven on it - the DB9, the M9040P
toggle, the TIL311, the LCD module and the trimmer (hardware/cards/io/kicad/v1.1/io-v1.1-eagle.pretty), copied here
with a body outline on the Fab layer and a courtyard.
The board: the blank V3.2 card's X1 and outline at 218 mm (LENGTH: every long card's; V1.1 is 178 mm), 4 layers
(In1.Cu GND plane, In2.Cu VCC plane, as the video V4.0 and memory v2.0 boards), every part placed here, every pad on its
schematic net, keepouts round X1's two screws. The panel is at the front (the top with the card standing in the
backplane): the LEDs and the DB9 on the edge, the switches under them, then the LCD and the TIL311s.

Run with KiCad's bundled Python (pcbnew), from this folder:
  gen_io12.py sch                          -> local libraries + io-v1.2.kicad_sch (the root) and its sheets
                                              io-v1.2-<block>.kicad_sch (needs node + elkjs: tools/kicad)
  gen_io12.py checknet <netlist>           -> the netlist KiCad exports from the schematic against io12_netlist.py
  gen_io12.py project                      -> io-v1.2.kicad_pro + .kicad_dru (signals 0.25 mm / 0.2 mm, vias 0.8/0.4;
                                              class Power = GND, VCC: planes, never routed)
  gen_io12.py board <netlist> <out.pcb>    -> the unrouted board
  gen_io12.py place <pcb>                  -> the placement check: courtyards apart, everything inside the outline, the
                                              DIP sockets' outlines clear of each other and of the other parts
  gen_io12.py xtal <pcb> <out.pcb>         -> the crystal's two tracks to the clock chip, locked, and the keepouts
                                              round them, before Freerouting
  gen_io12.py drawing <pcb> [out.pdf]      -> the placement drawing, io-v1.2-placement.pdf, on a landscape sheet
  gen_io12.py geom <pcb> <out.json>        -> the board's outline, silkscreen, bodies, pads and holes in mm, for
                                              print_1to1.py (the 1:1 check print, io-v1.2-1to1.pdf)
  gen_io12.py silk <pcb> [out]             -> the silkscreen texts placed clear (board() does it on every new board)
  gen_io12.py planes <pcb>                 -> each plane one piece (on the routed board)
  gen_io12.py padnets <netlist> <pcb>      -> the routed board kept: open through-hole pads that the netlist now has on
                                              GND or VCC given that net (the plane joins them); any other change refused
  gen_io12.py dsn|shuffle|ses|stats ...    -> as gen_v13.py (Specctra export/import, Freerouting seeds, route stats)
  gen_io12.py link <netlist> <pcb>         -> the footprints' schematic links (path) set from the netlist, nothing else
  gen_io12.py verify <netlist> <pcb>       -> the key connections pin by pin (schematic and board), layers, planes
  gen_io12.py bom                          -> BOM.md: the bill of materials from io12_netlist.PARTS (plain Python)
  gen_io12.py fab <pcb>                    -> the order's files: gerbers/ and io-v1.2-gerbers.zip (nothing is ordered)
"""
import os, sys, re, json, uuid, shutil, subprocess, collections, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
CFDIR = os.path.join(ROOT, "hardware", "cards", "cf", "kicad", "v1.0")
V13DIR = os.path.join(ROOT, "hardware", "cards", "video", "kicad", "v1.3")
V11FP = os.path.join(HERE, "..", "v1.1", "io-v1.1-eagle.pretty")      # the built card's footprints
sys.path.insert(0, HERE)
sys.path.insert(0, CFDIR)
sys.path.insert(0, os.path.join(ROOT, "tools", "kicad"))
import io12_netlist as N                                   # noqa: E402
import gen_cf                                              # noqa: E402  (the CF card's sheet writer, reused read-only)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


G13 = _load(os.path.join(V13DIR, "gen_v13.py"), "gen_v13")   # dsn / shuffle / ses / stats / refill / plane
P = "io-v1.2"
CLI = gen_cf.CLI
KFP = gen_cf.KFP
LOCAL = N.LOCAL
G = 2.54
LENGTH = 218.0                                             # mm: the card from the bus connector's edge to the front (every long card's)
X0, Y0, Y1B = 17.747, 10.025, 123.995                      # the blank card's left, top and bottom edges
X1R = X0 + LENGTH                                          # the front edge
gen_cf.N = N
gen_cf.NETOF = {(r, p): n for n, conns in N.NETS.items() for r, p in conns}
gen_cf.NC = {(r, p) for r, ps in N.NO_CONNECT.items() for p in ps}
gen_cf.PROJ = P
gen_cf.ROOT_UUID = gen_cf.U("io-v1.2", "root")


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


def local_symbols():
    io, inp, out, pas, pw, oc = "bidirectional", "input", "output", "passive", "power_in", "open_collector"
    # the DS12885, 24-pin PDIP (Maxim data sheet rev 3, 2/07; the pins as System-5's IO panel has them, read from it on
    # 2026-11-18): 12 and 16 are both GND, 22 is the only N.C., -RCLR has its own pull-up
    rtc = box_symbol(
        "DS12885", "IC", "DS12885 real-time clock, calendar and 114 bytes of RAM, 24-pin PDIP",
        left=[("14", "AS", inp), ("17", "DS", inp), ("15", "R/~{W}", inp), ("13", "~{CS}", inp), ("1", "MOT", inp),
              ("18", "~{RESET}", inp), ("21", "~{RCLR}", inp), ("2", "X1", pas), ("3", "X2", pas), ("20", "VBAT", pas)],
        right=[(str(4 + i), "AD%d" % i, io) for i in range(8)] + [("19", "~{IRQ}", oc), ("23", "SQW", out),
                                                                   ("22", "NC", "no_connect")],
        top=[("24", "VCC", pw)], bottom=[("12", "GND", pw), None, ("16", "GND", pw)], width=20.32)
    # the TIL311 (HP 5082-7340: the same pins), as the V1.1 card wires it: 3 / 2 / 13 / 12 = the data A-D, 5 the latch
    # strobe, 8 the blanking, 1 the LEDs' supply, 14 the logic's
    til = box_symbol(
        "TIL311", "DS", "TIL311 hexadecimal display with latch and decoder",
        left=[("3", "A", inp), ("2", "B", inp), ("13", "C", inp), ("12", "D", inp), ("5", "~{STROBE}", inp),
              ("8", "BLANK", inp)],
        right=[("4", "DP_L", pas), ("10", "DP_R", pas)],
        top=[("14", "VCC", pw), None, ("1", "LED_VCC", pw)], bottom=[("7", "GND", pw)], width=15.24)
    # the LCD module's 16 pins (HD44780, 1602): the backlight's two as passive pins (the anode is fed through R11)
    lcd = box_symbol(
        "LCD1602", "DS", "HD44780 16 x 2 character LCD module, 16 pins in a row",
        left=[("4", "RS", inp), ("5", "R/~{W}", inp), ("6", "E", inp)] + [(str(7 + i), "DB%d" % i, io) for i in range(8)],
        right=[("3", "VO", pas), ("15", "A", pas), ("16", "K", pas)],
        top=[("2", "VDD", pw)], bottom=[("1", "VSS", pw)], width=15.24)
    text = "\n".join(['(kicad_symbol_lib', '\t(version 20251024)', '\t(generator "gen_io12")', '\t(generator_version "1.0")',
                      rtc, til, lcd, ')', ''])
    path = os.path.join(HERE, LOCAL + ".kicad_sym")
    open(path, "w").write(text)
    gen_cf.kicad_cli("sym", "upgrade", "--force", path)


# The built V1.1 card's footprints, for the parts that are known to fit them: the name here, V1.1's file, the pads
# renamed. Each is copied with a body outline on F.Fab and a courtyard round all it draws and all its pads (the Eagle
# conversion has neither; the placement check and the silkscreen placer work by them).
#   the DB9: a right-angle socket, its two pin rows 2.84 mm apart about the footprint's y = 0, the body and the mating
#   face towards -y: the board's edge lies 10.17 mm from the origin (V1.1: 124.00 - 113.83) and the D reaches 5.6 mm
#   past it. Its two mounting holes are the shell: pads SH here (G1, G2 on V1.1, where nothing was on them).
#   the toggle M9040P: three pads 4.70 mm apart in a line, the pole in the middle.
#   the LCD module: 80 x 36 mm from its origin, the 16 pins in a row 33.46 mm above it, four 2.8 mm holes.
LOCAL_FP = {
    "DSUB-9_Socket_Horizontal_IO-V1.1": ("DB9", {"G1": "SH", "G2": "SH"}),
    "SW_Toggle_M9040P": ("M9040P", {}),
    "HTIL311A": ("HTIL311A", {}),
    "LCD1602": ("LCD1602", {}),
    "Potentiometer_Trim_3386_Inline": ("TRIM-3386", {}),
}
DB9_EDGE = 10.17                                           # from the DB9 footprint's origin to the board's edge


def local_footprint(name, v11, rename):
    t = open(os.path.join(V11FP, v11 + ".kicad_mod")).read()
    t = re.sub(r'^\(footprint "[^"]*"', '(footprint "%s"' % name, t, count=1)
    t = re.sub(r'\(property "Reference" "[^"]*"', '(property "Reference" "REF**"', t, count=1)
    for a, b in rename.items():
        t = t.replace('(pad "%s" ' % a, '(pad "%s" ' % b)
    xs, ys = [], []
    for m in re.finditer(r'\((fp_line|fp_rect|fp_circle|fp_arc|fp_poly)\b.*?\n\t\)', t, re.S):
        for a, b in re.findall(r'\((?:start|end|mid|center|xy) ([-\d.]+) ([-\d.]+)\)', m.group(0)):
            xs.append(float(a)); ys.append(float(b))
    for a, b, w, h in re.findall(r'\(pad "[^"]*" \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+)(?: [-\d.]+)?\)\s*\(size ([-\d.]+) ([-\d.]+)\)', t):
        r = max(float(w), float(h)) / 2
        xs += [float(a) - r, float(a) + r]; ys += [float(b) - r, float(b) + r]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    extra = ['\t(fp_rect (start %s %s) (end %s %s) (stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab"))'
             % (gen_cf.f(x0), gen_cf.f(y0), gen_cf.f(x1), gen_cf.f(y1)),
             '\t(fp_rect (start %s %s) (end %s %s) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))'
             % (gen_cf.f(x0 - 0.25), gen_cf.f(y0 - 0.25), gen_cf.f(x1 + 0.25), gen_cf.f(y1 + 0.25))]
    i = t.rindex(")")
    return t[:i].rstrip() + "\n" + "\n".join(extra) + "\n)\n"


def local_libs():
    for ext in (".kicad_sym",):
        shutil.copy(os.path.join(CFDIR, N.BUSLIB + ext), os.path.join(HERE, N.BUSLIB + ext))
    for lib in (N.BUSLIB, LOCAL):
        d = os.path.join(HERE, lib + ".pretty")
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)
    shutil.copy(os.path.join(CFDIR, N.BUSLIB + ".pretty", "FABC96R.kicad_mod"), os.path.join(HERE, N.BUSLIB + ".pretty"))
    for name, (v11, rename) in LOCAL_FP.items():
        open(os.path.join(HERE, LOCAL + ".pretty", name + ".kicad_mod"), "w").write(local_footprint(name, v11, rename))
    local_symbols()
    open(os.path.join(HERE, "sym-lib-table"), "w").write(
        '(sym_lib_table\n\t(version 7)\n'
        '\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.kicad_sym")(options "")(descr "YACC1 bus connector, three rows"))\n'
        '\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.kicad_sym")(options "")(descr "DS12885, TIL311, the LCD module (gen_io12.py)"))\n'
        ')\n' % (N.BUSLIB, N.BUSLIB, LOCAL, LOCAL))
    open(os.path.join(HERE, "fp-lib-table"), "w").write(
        '(fp_lib_table\n\t(version 7)\n'
        '\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.pretty")(options "")(descr "FABC96R from the blank V3.2 card"))\n'
        '\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.pretty")(options "")(descr "the built V1.1 card\'s DB9, toggle, TIL311, LCD and trimmer (gen_io12.py)"))\n'
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
    ("bus", "Bus and ports", "THE BUS, THE DATA BUFFER, THE PORT DECODE, THE STROBES, THE CONTROL LATCH",
     _whole("IC12") + _g("IC13", 3, 6, 8) + _whole("RN2", "IC5", "JP3", "JP10", "JP4", "JP5") + _g("IC8", 2, 4, 6, 8, 10) +
     _whole("RN1") + _g("IC7", 11, 6) + _whole("IC10"),
     (_u("X1", 1, 2, 3), "left"),
     "X1: the YACC1 V3.2 bus (DIN 41612). IC12 stands between the bus's DATA0-7 and the card's ID0-7: towards the card\n"
     "but in a read (-IO-RD), and enabled only while one of the card's ports is addressed (BUFEN, IC13). IC5 decodes\n"
     "IO-ADDR0-2 into the eight ports of the card's half (JP3: IO-ADDR3 low or high; JP10: always, or only while -BUS-EN\n"
     "is low: the bus tester drives the card with -BUS-EN high); JP4 picks the control port and JP5\n"
     "the data port (port 0 and port 1 in the machine); ports 6 and 7 are the clock's (sheet 6). IC8, open collector with\n"
     "RN1: the strobes IO-RD and IO-WR, RESET and -B-RESET, IO-SELDATA. IC10 is the control latch (a write of P0)."),
    ("uart", "UART", "THE CONSOLE UART, ITS CLOCK, THE RS-232 DRIVER, THE DB9, THE TTL HEADER, THE UART'S -INT",
     _whole("OSC1", "IC1", "IC2", "C1", "C2", "C3", "C4", "JP1", "J1", "JP2", "R12", "J2") + _g("IC8", 12) + _whole("JP7"),
     None,
     "IC1 is selected by IO-SELDATA (a P1 access) AND UART-CS, its register by UART-A0-2: all from the control latch.\n"
     "OSC1, 1.8432 MHz: divisor 3 is 38400 baud. TX goes to the MAX232 and to the TTL header J2; JP2 picks where RX comes\n"
     "from. JP1 puts the MAX232's two lines on the DB9's pins 2 and 3, either way round. The UART's INT reaches the bus\n"
     "-INT through IC8/F and JP7: with JP7 off the card never touches -INT."),
    ("panel", "Panel", "THE SWITCHES, THE LEDS, THE TIL311 DISPLAYS, IN AND OUT",
     _whole(*["S%d" % n for n in range(8)]) + _whole("IC3") + _g("IC6", 6, 12) + _whole("IC4") +
     _whole(*["R%d" % (n + 3) for n in range(8)]) + _whole(*["LED%d" % n for n in range(8)]) + _g("IC11", 12) +
     _whole("IC9", "DS1", "DS2", "S8", "JP6", "R1", "LED8"),
     None,
     "With SWITCH-LED in the control latch a read of P1 is the switches (IC3: up = 1, S0 = bit 0) and a write of P1 the\n"
     "LEDs (IC4). With TIL311 a write of P1 is the two hex displays (IC9: LO the low nibble). S8 is the bus line IN (JP6);\n"
     "LED8 shows the bus line OUT."),
    ("lcd", "LCD", "THE LCD MODULE",
     _g("IC6", 8) + _g("IC7", 3) + _whole("DS3", "RV1", "R11"),
     None,
     "With LCD-ENABLE a write of P1 is a pulse on the module's E; LCD-REGISTER is its RS. Write only: R/W is on GND.\n"
     "RV1 sets the contrast; R11 stands in series with the backlight."),
    ("rtc", "Clock", "THE REAL-TIME CLOCK ON PORTS 6 AND 7",
     _g("IC14", 3, 6, 8) + _g("IC7", 8) + _whole("IC15", "Y1", "BT1", "JP8", "JP9"),
     None,
     "IC15, a DS12885: a write of port 6 is the register number (AS, taken as it falls), port 7 that register's data\n"
     "(the chip's DS and R/W in Intel timing: MOT low). -CS low, -RESET high. Y1 32.768 kHz, 6 pF; BT1 a CR2032.\n"
     "JP8 puts the chip's open-drain -IRQ on the bus -INT. JP9, fitted with the power off, clears the chip's RAM."),
    ("power", "Power", "POWER UNITS, DECOUPLING, POWER LED, THE SPARE GATES",
     _whole("R2", "LED9") + _g("IC11", 6, 8) + _g("IC13", 11) + _g("IC14", 11), (None, "top"),
     "One 100 nF per IC beside its VCC pin (C21 at the oscillator), C5 47 uF bulk. The bus supplies VCC and GND (X1,\n"
     "six pins each): the PWR_FLAGs. Spare, their inputs on GND: two gates of IC11, one of IC13, one of IC14."),
]


def _power_units(S):
    out = []
    for ref in sorted(N.PARTS, key=lambda r: (len(r), r)):
        s = S.lib(gen_cf.SYM_SUB.get(N.PARTS[ref][1], N.PARTS[ref][1]))
        if ref.startswith("IC") and len(s.units) > 1:
            out.append((ref, s.units[-1]))
    return out + [(c, 1) for c in sorted(N.DECOUPLE, key=lambda r: int(r[1:]))] + \
        [("C5", 1)]


def sheet_uuid(key):
    return gen_cf.U("io-v1.2", "sheet", key, "instance")


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
        head = ['(kicad_sch', '\t(version 20260306)', '\t(generator "gen_io12")', '\t(generator_version "1.0")',
                '\t(uuid "%s")' % file_uuid, '\t(paper "%s")' % paper,
                '\t(title_block (title "YACC1 I/O card V1.2: %s") (date "%s") (rev "%s") (company "YACC1")'
                % (title, N.DATE, N.REV),
                '\t\t(comment 1 "Sheet %s of the I/O card V1.2 schematic (root: io-v1.2.kicad_sch)")' % page,
                '\t\t(comment 2 "Circuit source: io12_netlist.py; this sheet is generated by gen_io12.py")',
                '\t\t(comment 3 "Design note and theory: docs/cards/io.md"))',
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
        S = SubSheet("io-v1.2/" + key, lambda net: "hier", shape=lambda net, n=name: pin_shape(D, n, net))
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
        S.write(os.path.join(HERE, fname), gen_cf.U("io-v1.2", "sheet", key, "file"), name, paper, page)
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
                          gen_cf.U("io-v1.2", "rline", key)))
        for side, i, n, s, k in placed:
            py = y + (i + 1) * G
            px = x if side == "L" else x + w
            L.append('\t\t(pin %s %s (at %s %s %d) %s (justify %s)) (uuid "%s"))'
                     % (gen_cf.q(n), s, gen_cf.f(px), gen_cf.f(py), 180 if side == "L" else 0, eff,
                        "left" if side == "L" else "right", gen_cf.U("io-v1.2", "spin", key, n + k)))
            ex = px - 2 * G if side == "L" else px + 2 * G
            out.append('\t(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid "%s"))'
                       % (gen_cf.f(px), gen_cf.f(py), gen_cf.f(ex), gen_cf.f(py),
                          gen_cf.U("io-v1.2", "rw", key, n + k)))
            ang, just = (180, "right bottom") if side == "L" else (0, "left bottom")
            out.append('\t(label %s (at %s %s %d) %s (justify %s)) (uuid "%s"))'
                       % (gen_cf.q(n), gen_cf.f(ex), gen_cf.f(py), ang, eff, just,
                          gen_cf.U("io-v1.2", "rl", key, n + k)))
            nl += 1
        L += ['\t\t(instances (project "%s" (path "/%s" (page "%d"))))' % (P, ROOT_UUID, page), '\t)']
        out.append("\n".join(L))
        X = x + w + rw + 10
        rowh = max(rowh, h)
    note = ["The I/O card V1.2, one sheet per functional block:"]
    note += ["  sheet %d  %-12s %s" % (page, name, title) for key, name, title, fname, su, page, pins in blocks]
    note += ["", "Every net of a sheet is a pin of its sheet symbol here, and the local label at each pin names the net",
             "(/NAME, the names on the board). Above the dashed line: the nets the sheet shares with other sheets (left:",
             "it reads them, right: it drives them). Below it: the nets drawn on that sheet only, a pin on each side",
             "(KiCad's ERC counts a root label as connected only when another label of its name is on the root sheet).",
             "VCC and GND are power symbols on the sheets."]
    out.append('\t(text %s (exclude_from_sim no) (at 25.4 15.24 0) (effects (font (size 1.5 1.5)) (justify left top)) '
               '(uuid "%s"))' % (gen_cf.q("\n".join(note)), gen_cf.U("io-v1.2", "rootnote")))
    paper = W.paper_for(X - 25.4, Y + rowh + 10 - 22.86)[0]
    head = ['(kicad_sch', '\t(version 20260306)', '\t(generator "gen_io12")', '\t(generator_version "1.0")',
            '\t(uuid "%s")' % ROOT_UUID, '\t(paper "%s")' % paper,
            '\t(title_block (title "YACC1 I/O card V1.2") (date "%s") (rev "%s") (company "YACC1")' % (N.DATE, N.REV),
            '\t\t(comment 1 "Console UART, switches, LEDs, TIL311s and LCD behind ports P0 / P1; a DS12885 clock on ports 6 / 7; a data buffer")',
            '\t\t(comment 2 "Circuit source: io12_netlist.py; these sheets are generated by gen_io12.py")',
            '\t\t(comment 3 "Design note and theory: docs/cards/io.md"))',
            '\t(lib_symbols)']
    tail = ['\t(sheet_instances (path "/" (page "1")))', '\t(embedded_fonts no)', ')', '']
    open(os.path.join(HERE, P + ".kicad_sch"), "w").write("\n".join(head + out + tail))
    return nl


def check_schematic_netlist(netfile):
    """the schematic's exported netlist = io12_netlist.NETS (label nets come back as /NAME)"""
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
        print("  net %s: schematic %s, io12_netlist %s" % (n, sorted(got.get(n, ()))[:6], sorted(want.get(n, ()))[:6]))
    print("schematic netlist vs io12_netlist.py: %s (%d nets)" % ("MATCH" if not bad else "%d DIFFER" % len(bad), len(want)))
    return not bad


def sch():
    probs = N.check()
    if probs:
        raise SystemExit("io12_netlist.check():\n" + "\n".join(probs))
    why = W.elk_ready()
    if why:
        raise SystemExit("gen_io12.py sch: " + why)
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
DRU = G13.DRU.replace("video card v1.3", "I/O card V1.2").replace("gen_v13.py", "gen_io12.py")


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
# THE PLACEMENT (2026-11-18), on the 218 mm outline. As drawn the bus connector is on the left and the front edge on
# the right; with the card standing in the backplane the front edge is the top and the drawing's top edge the left.
#
# The panel, from the front edge down (the board-layout rules: the outside connector, the LEDs and the switches at the
# front):
#   the edge     the eight LEDs, bit 7 at the left, then OUT and PWR, each with its resistor behind it; the DB9 at the
#                right, its face on the edge, the D off the card: a cable plugs straight down into it
#   under them   the eight switches, bit 7 at the left, 10.16 mm apart, and the IN switch under the DB9 (as on V1.1:
#                up = 1); the null-modem block and the RX jumper between the IN switch and the DB9
#   then         the LCD (80 x 36 mm, upright) and the two TIL311s at its right, HI then LO
# The ICs stand in columns between the bus connector and the LCD, pin 1 at the top left (the clock chip turned round,
# pin 1 at the bottom right: its crystal pins towards the free channel, its battery pin towards the cell), a capacitor
# beside each VCC pin: the buffer, the decode, the strobes and the buffer's enable by the bus connector; the control
# latch and its gates; the UART over the clock chip; the TIL311 gate and the MAX232 with its four capacitors and the
# oscillator; and, by the LCD, the panel's column: the switch buffer, the LED latch, the TIL311 latch. The jumpers
# are along the right side edge.
GAP = 6.3                                                 # between two chips in a column, end pin to end pin
PITCH = 15.24                                             # from one column of 300-mil sockets to the next
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
COLX = {"N0": 32.0, "N1": 47.24, "W0": 62.48, "N2": 85.34, "N3": 138.0}
COLUMNS = [("N0", ("IC12", "IC5", "IC8", "IC13")),               # the data buffer, the port decode, the strobes, the buffer's enable
           ("N1", ("IC10", "IC7", "IC6", "IC14")),               # the control latch, its gates, the clock chip's strobes
           ("W0", ("IC1", "~IC15")),                             # the UART over the clock chip
           ("N2", ("IC11", "IC2")),                              # the TIL311 latch's gate, the MAX232
           ("N3", ("IC3", "IC4", "IC9"))]                        # by the panel: the switch buffer, the LED latch, the TIL311 latch
for _name, _refs in COLUMNS:
    stack(COLX[_name], TOP, *_refs)
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
X1F = X1R                                                 # the front edge
# the clock chip's crystal, right of its pins 2 and 3 (IC15 is turned: they are the second and third up its right
# side), its two pads beside the two pins: 3 mm of track each (xtal())
_x15, _y15 = pin_xy("IC15", 2)
PLACE["Y1"] = (_x15 + 2.8, _y15 - 0.3, 90)
# the panel's rows
LEDX = X1F - 6.0 - 1.27                                   # an LED's pad 1: the LED stands 6 mm inside the front edge
LEDY = [15.0, 22.62, 30.24, 37.86, 46.75, 54.37, 61.99, 69.61]            # bit 7 .. bit 0: 7.62 mm apart, the nibbles 1.27 more
RESX = X1F - 19.25                                        # the LEDs' resistors, lying behind them
SWX = X1F - 33.0                                          # the switches' poles: 6 mm under the resistors, for their labels
SWY = [17.32 + 10.16 * k for k in range(8)]               # bit 7 .. bit 0 (V1.1's places along the card)
LCDX, LCDY = SWX - 9.7 - 36.0, 12.5                       # the LCD's lower left corner as it stands: 36 mm up, 80 mm across
for _n in range(8):
    PLACE["LED%d" % _n] = (LEDX, LEDY[7 - _n], 0)
    PLACE["R%d" % (_n + 3)] = (RESX, LEDY[7 - _n], 0)
    PLACE["S%d" % _n] = (SWX, SWY[7 - _n], 90)
PLACE.update({
    "LED8": (LEDX, 79.5, 0), "R1": (RESX, 79.5, 0),       # OUT
    "LED9": (LEDX, 87.1, 0), "R2": (RESX, 87.1, 0),       # PWR
    # the DB9: turned so that its face (the footprint's -y) is towards the front edge, the D reaching past it
    "J1": (X1F - DB9_EDGE, 106.5, 270),
    "S8": (SWX, 104.0, 90),                               # IN, under the DB9
    # between the IN switch and the DB9: the null-modem block and the RX jumper; along the side edge the TTL header
    # and the IN jumper (R12, the header's pull-up, stands with R11 under the TIL311s)
    "JP1": (X1F - 18.9, 101.0, 0), "JP2": (X1F - 17.6, 111.5, 0), "R12": (LCDX + 4.5, 116.2, 0),
    "J2": (X1F - 42.0, 119.8, 90), "JP6": (X1F - 22.0, 120.6, 90),
    # the LCD, upright, its pins along its upper edge; the TIL311s at its right; its trimmer and the backlight's
    # resistor under the TIL311s
    "DS3": (LCDX, LCDY, 270),
    "DS1": (LCDX + 36.0 - 9.65, 99.5, 270), "DS2": (LCDX + 36.0 - 9.65, 110.93, 270),
    "RV1": (LCDX + 7.0, 99.0, 90), "R11": (LCDX + 4.5, 110.0, 0),
    # the MAX232's four capacitors in the channel at its right, the oscillator under it with its capacitor
    "C1": (99.0, 43.0, 270), "C2": (99.0, 49.0, 270), "C3": (99.0, 55.0, 270), "C4": (99.0, 61.0, 270),
    "OSC1": (COLX["N2"], 77.0, 0), "C21": (COLX["N2"], 63.5, 0),
    # along the right side edge, from the bus connector: the half, the control port, the data port; the pull-ups; the
    # bulk capacitor; the three jumpers of -INT and of the clock chip's RAM
    "JP3": (33.0, 113.0, 90), "JP4": (43.0, 113.0, 90), "JP5": (43.0, 120.2, 90),
    "RN1": (64.5, 103.5, 0), "RN2": (64.5, 108.0, 0), "C5": (66.0, 116.5, 0),
    "JP7": (91.0, 113.0, 0), "JP8": (96.0, 113.0, 0), "JP9": (101.0, 113.0, 0),
    "JP10": (74.0, 121.3, 90),                            # the decoder's G2B, beside the bulk capacitor
    # the clock's cell, flat, in the room between the MAX232's column and the panel's
    "BT1": (106.5, 106.0, 0),
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
    tb = b.GetTitleBlock()
    tb.SetTitle("YACC1 I/O card V1.2"); tb.SetDate(N.DATE); tb.SetRevision(N.REV); tb.SetCompany("YACC1")
    tb.SetComment(0, "%.0f mm, four layers: gen_io12.py and build.sh from io12_netlist.py" % LENGTH)
    unclear = silk_place(b, silk_texts(b))
    pcbnew.SaveBoard(out, b)
    print("silk: every reference and legend placed clear of other silk, the pads and the edge%s" % (
        "" if not unclear else " except %s" % ", ".join(unclear)))
    G13.refill(out)
    print("board %s: %d footprints placed, %d pads on nets, %.2f x %.2f mm, 4 layers (In1 GND, In2 VCC planes)" % (
        os.path.basename(out), len(fps), n, X1R - X0, Y1B - Y0))


SILK_H, SILK_W = 1.0, 0.15       # every text on the silk: JLCPCB's standard characters (>= 1.0 mm high, >= 0.15 mm strokes)
# UP (2026-11-18, the board-layout rules, every board of every system): every silk text reads upright, left to right,
# with the card standing in the backplane, X1 down. X1 is on the left as drawn, so that is KiCad's angle 270 (0 reads
# up the card, 90 upside down). The one exception: the board's name and cottageworker.com, which may run up a side
# edge (angle 0 as drawn) and do
UP = 270
# the legends: (text, x, y, size) left-justified at (x, y) at angle 0 (the name only), or (text, x, y, size, angle)
# centred on (x, y)
SILK = [("YACC1 I/O Card V1.2", 112.0, 11.7, 1.5), ("cottageworker.com", 140.0, 11.9, 1.0)]
# every switch's two positions (the board-layout rules): 1 above it, 0 under it, with the card standing; and over the
# 1 its reference and what it is (the footprint's own reference text is hidden, HIDE_REF: the nine labels stand in
# one line here)
SILK += [(t, SWX + dx, y, 1.0, UP) for y in SWY + [104.0] for t, dx in (("1", 8.1), ("0", -8.1))]
SILK += [("S%d BIT %d" % (n, n), SWX + 10.2, SWY[7 - n], 1.0, UP) for n in range(8)] + [("S8 IN", SWX + 10.2, 104.0, 1.0, UP)]
# the ports of the two port blocks: a jumper's place by its port number, 0 at the top with the card standing. JP4 and
# JP5 lie along the card, pin 1 nearest the bus connector: pins 1-2 are port 7, pins 15-16 port 0
for _ref, _dy in (("JP4", -4.7), ("JP5", 2.3)):
    _jx, _jy = PLACE[_ref][:2]
    SILK += [("%d" % (7 - k), _jx + 2.54 * k, _jy + _dy, 1.0, UP) for k in range(8)]
# the half: the two jumpers on the block's upper four pins (3-5, 4-6) are ports 0-7, on its lower four (1-3, 2-4) 8-F
_jx, _jy = PLACE["JP3"][:2]
SILK += [("0-7", _jx + 6.9, _jy - 1.27, 1.0, UP), ("8-F", _jx - 1.9, _jy - 1.27, 1.0, UP)]
# the null-modem block (JP1 "TX PIN"): its three pairs of pins stand side by side with the card standing, 1-2 at the
# left. Two jumpers on the left four pins (1-3, 2-4) put the card's transmit on the DB9's pin 2 (a straight cable to a
# PC), on the right four (3-5, 4-6) on pin 3: a 2 and a 3 under the two places
_jx, _jy = PLACE["JP1"][:2]
SILK += [("2", _jx - 2.4, _jy + 1.27, 1.0, UP), ("3", _jx - 2.4, _jy + 3.81, 1.0, UP)]
# the RX jumper: 1-2 the DB9, 2-3 the TTL header
_jx, _jy = PLACE["JP2"][:2]
SILK += [("DB9", _jx - 2.4, _jy + 0.4, 1.0, UP), ("TTL", _jx - 2.4, _jy + 4.7, 1.0, UP)]
# the TTL header's pins (an FTDI cable's): each pin's name at its left with the card standing, pin 1 (the cable's
# black wire) at the bottom
_jx, _jy = PLACE["J2"][:2]
SILK += [(t, _jx + 2.54 * k, _jy - 2.0 - 0.45 * len(t), 1.0, UP)
         for k, t in enumerate(("GND: BLACK", "CTS", "VCC NC", "TXD", "RXD", "RTS"))]
# the decoder's jumper: its lower two pins (1-2) with the card standing, G2B on GND: the ports decoded always; its
# upper two (2-3), G2B on -BUS-EN
_jx, _jy = PLACE["JP10"][:2]
SILK += [("ALWAYS", _jx + 1.27, _jy - 2.0 - 0.45 * 6, 1.0, UP), ("-BUS-EN", _jx + 3.81, _jy - 2.0 - 0.45 * 7, 1.0, UP)]
# the 2-pin jumpers: what a shunt does
for _ref, _t in (("JP6", "ON: IN SWITCH"), ("JP7", "ON: UART INT"), ("JP8", "ON: RTC INT"), ("JP9", "ON, POWER OFF: CLEAR")):
    _jx, _jy = PLACE[_ref][:2]
    SILK += [(_t, _jx + (1.27 if _ref == "JP6" else 0.0), _jy + (-2.6 if _ref == "JP6" else 5.6), 1.0, UP)]
# the cell's polarity (2026-11-19): a + at the holder's positive end (BT1 pin 1, VBAT), just under that pin with the
# card standing, past the end of the holder: the line under the holder reads "BT1 CR2032 +". The footprint's own +
# is printed inside the holder's outline, between pin 1 and the cell: it shows which way round the holder goes while
# the board is bare and is covered once the holder is fitted, so this one is the mark that stays. (Beside the
# holder's neck there is bare board too, but the silkscreen placer and pcb-check both take the holder's body as the
# box round its drawing, and the neck's sides are inside that box: a + there was moved out and pushed the two labels
# 5 mm along.) Its place is exact: 1.2 mm high at 3.3 mm under the pin, its whole text box (which pcb-check's LABELS
# measures) ends 0.13 mm short of the holder's box and its strokes stand 0.33 mm off JP9's reference. A quarter of a
# millimetre nearer the bus connector and JP9's two labels are pushed away, as much nearer the holder and the placer
# moves the + itself
_jx, _jy = PLACE["BT1"][:2]
SILK += [("+", _jx - 3.3, _jy + 0.95, 1.2, UP)]
# the text beside a reference (the board-layout rules): each IC's type, every LED's, switch's and jumper's function,
# every resistor's, network's, capacitor's and crystal's value, the oscillator's frequency
TYPE_SHORT = {}
VALUE_SHORT = {"C5": "47u"}
COMPANION = dict({r: TYPE_SHORT.get(r, v[0]) for r, v in N.PARTS.items() if r.startswith("IC")},
                 **{r: VALUE_SHORT.get(r, v[0]) for r, v in N.PARTS.items() if re.match(r"(RN?|RV|C|Y)\d", r)},
                 **{r: v[0] for r, v in N.PARTS.items() if re.match(r"(JP|LED|DS|J)\d", r)},
                 OSC1="1.8432MHz", BT1="CR2032", X1="DIN41612 96")
COMPANION.update({"LED%d" % n: "BIT %d" % n for n in range(8)})
COMPANION["J2"] = "TTL"                                   # (its pins' names stand beside it)
# the parts whose companion is the footprint's own value field, shown on the silk: their library footprints have no
# courtyard, so a free text cannot be told to belong to them (pcb-check's LABELS), but their own field can
VALUE_FIELD = {"X1"}
# the parts whose library footprint hides its reference or keeps it off the silk: shown, on the silk
SHOW_REF = {"J1", "DS1", "DS2", "DS3", "RV1", "BT1"}
# the parts whose reference stands in a legend of SILK instead (the switches): the footprint's own text hidden
HIDE_REF = {"S%d" % n for n in range(9)}
# the labels given their place (2026-11-19): {reference: (x, y, "line" | "stack")} - where the reference's text
# stands (its centre) and how its companion stands to it: after it on its line, or on the next line down the standing
# card. silk_place() puts these before it places the rest, and names any that is not clear where it is put. They
# are the places where the placer, which keeps two texts 0.15 mm apart and knows nothing of what they say, left two
# labels reading as one (seen on the 1:1 print):
LABEL_AT = {
    # IC15's capacitor: 1.4 mm towards C19, as far as C19's outline lets it go. Its "100n" ended 0.33 mm before JP4's
    # "CTL PORT" on the same line: "C20 100nCTL PORT"
    "C20": (PLACE["C20"][0] - 2.25, PLACE["C20"][1] - 4.74, "line"),
    # the control port's block: its name a line higher, off the capacitor's line
    "JP4": (PLACE["JP4"][0] + 17.07, PLACE["JP4"][1] - 9.53, "stack"),
    # the pull-ups: beside the network's top end. It stood in JP10's legends: "RN2 ALWAYS" over "10k x8 JP10"
    "RN2": (PLACE["RN2"][0] + 20.61, PLACE["RN2"][1] + 4.07, "stack"),
    # the two displays: each one's name under it, on two lines. DS1's stood over it, its second line in the row of
    # the switches' 0s ("TIL311 HI 0"); DS2's, one line under it, goes the same way so that the pair reads alike
    "DS1": (PLACE["DS1"][0] - 10.95, PLACE["DS1"][1], "stack"),
    "DS2": (PLACE["DS2"][0] - 10.95, PLACE["DS2"][1], "stack"),
}
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
                if it.GetTextAngleDegrees() % 360 != UP:       # the library's own texts (X1's row letters a, b, c and
                    it.SetTextAngleDegrees(UP)                 # pin numbers): turned in place to read with the card standing
                it.SetKeepUpright(False)                       # (KiCad's "keep upright" would draw a 270 as a 90)
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
        elif ref in ("X1", "J1"):                       # the housings: their silk and pads (X1: also 2.5 mm past its
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
        # then, if nothing within 3 mm is clear (2026-11-18: the legends turned to UP), the nearest clear spot within 15
        offs += sorted({(i * 0.25, j * 0.25) for i in range(-60, 61) for j in range(-60, 61)} - set(offs),
                       key=lambda o: (math.hypot(*o), o))
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

    # an IC's label runs along the side it is on, and every label is at UP (along the chip's long side, as drawn): at the
    # chip's right as drawn (above it, with the card standing), else at its left
    SIDES = {"right": 0.0, "left": 2.0, "above": 4.0, "below": 6.0}
    del SPLIT[:]                                        # the parts whose value stands apart from the reference
    # 1b. the labels given their place (LABEL_AT): the reference there, its companion on its line or on the next one,
    # before the placer takes the rest. One that is not clear there is named: the place is to be chosen again
    byref = {fp.GetReference(): fp for fp in fps}
    for ref, (x, y, kind) in sorted(LABEL_AT.items()):
        t, c = byref[ref].Reference(), comp.get(ref)
        t.SetVisible(True); t.SetLayer(pcbnew.F_SilkS)
        for u in (t, c):
            if u is not None:
                u.SetTextSize(VECTOR2I(FM(SILK_H), FM(SILK_H))); u.SetTextThickness(FM(SILK_W))
                u.SetKeepUpright(False)
                u.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER); u.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        er = extent(t, UP)
        put(t, x, y, UP)
        ok = free(ink(t), t)
        if c is not None:
            ec = extent(c, UP)                          # (the same two arrangements as the placer's "line" and "stack")
            pc = (0.0, er[3] + 0.7 - ec[1]) if kind == "line" else (er[0] - 0.35 - ec[2], 0.0)
            put(c, x + pc[0], y + pc[1], UP)
            ok = ok and free(ink(c), c) and not hit(ink(c), ink(t, CLR_SILK))
        if not ok:
            unclear.append("%s (LABEL_AT)" % ref)
        placed.append(ink(t, CLR_SILK))
        if c is not None:
            placed.append(ink(c, CLR_SILK))
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
            if ref in LABEL_AT:                             # placed already, in 1b
                continue
            if ref in SHOW_REF:                             # a footprint that hides its reference, or keeps it off the silk
                t.SetVisible(True); t.SetLayer(pcbnew.F_SilkS)
            if ref in HIDE_REF:                             # its reference is one of SILK's legends
                t.SetVisible(False)
            if not t.IsVisible() or t.GetLayer() != pcbnew.F_SilkS:
                continue
            t.SetTextSize(VECTOR2I(FM(SILK_H), FM(SILK_H))); t.SetTextThickness(FM(SILK_W))
            t.SetKeepUpright(False)                         # KiCad's "keep upright" would draw UP (270) as 90
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
            t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
            c = comp.get(ref)
            if c is not None:
                c.SetKeepUpright(False)
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
                            if isic and (a % 180 == 0) != (along == "x"):
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
            for a in (UP,):
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
                        # (a = UP, 270: the text reads down the board as drawn, its top towards the front edge)
                        if kind == "line":                  # "IC30 74LS138": the companion after the reference
                            pc = (0.0, er[3] + 0.7 - ec[1])
                        else:                               # stacked: the companion on the next line, towards X1
                            pc = (er[0] - 0.35 - ec[2], 0.0)
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
            put(t, gx + i, gy + j, UP)
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
    """gen_io12.py silk <pcb> [out]: the silkscreen texts written afresh (silk_texts()) and placed (silk_place()) on a
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
    """gen_io12.py planes <pcb>: each plane filled as one piece (2026-11-03). Where two pads of the plane's net stand side
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


def padnets(netfile, pcb):
    """gen_io12.py padnets <netlist> <pcb>: the routed board kept through a change of the netlist that needs no new
    track (2026-11-18: the oscillator's pin 1 tied to VCC). Every pad's net on the board is compared with the
    schematic's netlist. A pad that was open (no net, or KiCad's net of one unconnected pin) and is now on a plane's net
    (GND or VCC) is given that net, if it is a through-hole pad: its hole stands in the plane, and the plane joins it
    with a thermal relief when it is filled again (planes(), which build.sh runs next). Anything else that differs - a
    pad that moves between two signals, a pad that leaves a plane, a surface pad - needs a route and is refused: that
    is build.sh's whole run. No footprint, track or via is touched; the title block's date follows the netlist's.
    Saves <pcb> when every difference could be settled."""
    import pcbnew
    nodes, comps = read_netlist(netfile)
    open_pins = read_unconnected(netfile)
    b = pcbnew.LoadBoard(pcb)
    plane = {z.GetNetname(): b.GetLayerName(z.GetFirstLayer()) for z in b.Zones()
             if not z.GetIsRuleArea() and b.GetLayerName(z.GetFirstLayer()).startswith("In")}
    join, refuse, same = [], [], 0
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        for p in fp.Pads():
            if not p.GetNumber():
                continue
            key = (ref, p.GetNumber())
            want = nodes.get(key) or open_pins.get(key) or ""
            have = p.GetNetname()
            if have == want:
                same += 1
            elif (not have or have.startswith("unconnected-")) and want in plane \
                    and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                join.append((ref, p, want))
            else:
                refuse.append("%s.%s: on the board %s, in the netlist %s" % (ref, p.GetNumber(), have or "open",
                                                                            want or "open"))
    if refuse:
        print("padnets: %d pad(s) need a route - the whole build (build.sh), not this step:" % len(refuse))
        for r in refuse[:20]:
            print("  " + r)
        return False
    for ref, p, want in join:
        p.SetNet(b.FindNet(want))
    b.GetTitleBlock().SetDate(N.DATE)
    pcbnew.SaveBoard(pcb, b)
    print("padnets: %d pads as the netlist has them; joined to a plane: %s" % (
        same, ", ".join("%s.%s to %s (%s)" % (ref, p.GetNumber(), want, plane[want]) for ref, p, want in join)
        or "none"))
    return True


# ---------------------------------------------------------------------------------------------------------------------
# The clock chip's crystal, before Freerouting sees the board
#
# The DS12885's data sheet asks for short leads from the crystal to X1 and X2, with no other signal beside or under
# them. Y1 stands beside the two pins (PLACE); xtal() draws the two tracks, 3 mm each on the front, and locks them
# (KiCad's Specctra export hands locked tracks to Freerouting as fixed wiring, and its session import leaves them
# alone), and lays two keepouts for tracks and vias: the back under the crystal and its tracks, and the front round the
# crystal on the three sides that are not the chip's. The GND plane inside stays whole under them.
XTAL_NETS = (("RTC-X1", "IC15", "2", "Y1", "1"), ("RTC-X2", "IC15", "3", "Y1", "2"))


def xtal(pcb, out):
    import pcbnew
    from pcbnew import VECTOR2I
    FM = pcbnew.FromMM
    b = pcbnew.LoadBoard(pcb)
    fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
    pad = lambda ref, num: [p for p in fps[ref].Pads() if p.GetNumber() == num][0]
    xs, ys = [], []
    for net, r1, p1, r2, p2 in XTAL_NETS:
        a, c = pad(r1, p1), pad(r2, p2)
        assert a.GetNetname().lstrip("/") == net and c.GetNetname().lstrip("/") == net, (net, a.GetNetname(), c.GetNetname())
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(a.GetPosition()); t.SetEnd(c.GetPosition())
        t.SetWidth(FM(G13.RULES["track"])); t.SetLayer(pcbnew.F_Cu); t.SetNet(a.GetNet()); t.SetLocked(True)
        b.Add(t)
        for p in (a, c):
            xs.append(pcbnew.ToMM(p.GetPosition().x)); ys.append(pcbnew.ToMM(p.GetPosition().y))
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)

    def keepout(layer, box):
        z = pcbnew.ZONE(b)
        ls = pcbnew.LSET(); ls.AddLayer(layer)
        z.SetLayerSet(ls)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowZoneFills(False); z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
        o = z.Outline(); o.NewOutline()
        for x, y in ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])):
            o.Append(FM(x), FM(y))
        b.Add(z)

    # the back: under the two tracks and the crystal, from just right of the chip's pads to past the crystal's
    keepout(pcbnew.B_Cu, (x0 + 1.1, y0 - 1.4, x1 + 1.6, y1 + 1.4))
    # the front: right of the crystal, above it and below it (the chip's own pads close the fourth side)
    keepout(pcbnew.F_Cu, (x1 + 0.9, y0 - 1.4, x1 + 1.6, y1 + 1.4))
    keepout(pcbnew.F_Cu, (x0 + 1.1, y0 - 1.4, x1 + 1.6, y0 - 0.9))
    keepout(pcbnew.F_Cu, (x0 + 1.1, y1 + 0.9, x1 + 1.6, y1 + 1.4))
    pcbnew.SaveBoard(out, b)
    print("xtal: Y1's two tracks drawn and locked (%.1f mm each), keepouts on the back under them and on the front round them"
          % (x1 - x0))


def fab(pcb):
    """gen_io12.py fab <pcb>: the order's files beside the board - gerbers/ (the four copper layers, both masks, both
    silkscreens, the outline, the plated and the non-plated drill file with their maps) and <board>-gerbers.zip of
    them, with the export options of the memory card v2.0's order (finish_v2.py fab). It orders nothing: the zip is
    what pcb-check reads before an order"""
    import glob, zipfile
    d = os.path.dirname(os.path.abspath(pcb)); name = os.path.basename(pcb)[:-len(".kicad_pcb")]
    ger, zipf = os.path.join(d, "gerbers"), os.path.join(d, name + "-gerbers.zip")
    if os.path.isdir(ger): shutil.rmtree(ger)
    os.makedirs(ger)
    run = lambda *a: subprocess.run(list(a), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run(CLI, "pcb", "export", "gerbers", "--no-protel-ext", "--layers",
        "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts", "-o", ger + "/", pcb)
    run(CLI, "pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm", "--generate-map",
        "--map-format", "gerberx2", "--excellon-separate-th", "-o", ger + "/", pcb)
    if os.path.exists(zipf): os.remove(zipf)
    files = sorted(glob.glob(ger + "/*"))
    with zipfile.ZipFile(zipf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files: z.write(f, os.path.basename(f))
    holes = {}
    for kind in ("PTH", "NPTH"):                            # the drill files' own count: a hole is a line X..Y.., a
        text = open(os.path.join(ger, "%s-%s.drl" % (name, kind))).read()                  # slot one with G85 after it
        holes[kind] = len(re.findall(r"^X-?[\d.]+Y-?[\d.]+", text, re.M)); holes[kind + " slots"] = text.count("G85")
    print("fab: %d files in gerbers/ and %s; %d plated holes, %d of them slots; %d not plated"
          % (len(files), os.path.basename(zipf), holes["PTH"], holes["PTH slots"], holes["NPTH"]))


def drawing(pcb, out=None):
    """gen_io12.py drawing <pcb> [out.pdf]: the placement drawing - the outline, every part's body with its reference
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


def geom(pcb, out):
    """gen_io12.py geom <pcb> <out.json>: what print_1to1.py draws, in board mm, read from the board itself - the
    outline; the front silkscreen as KiCad's own filled outlines, texts included, so the print shows it as the board
    has it; the parts' bodies (the Fab layer's lines) the same way; every pad's outline with its hole; each part's
    place and the box of its body; and the board file's SHA-256, which the print carries: a sheet of paper can be
    matched to the board it was made from"""
    import pcbnew, hashlib
    b = pcbnew.LoadBoard(pcb)
    T = lambda v: round(pcbnew.ToMM(v), 3)
    ring = lambda c: [(T(c.CPoint(k).x), T(c.CPoint(k).y)) for k in range(c.PointCount())]

    def rings(ps):                                         # [[outline, hole, hole...], ...]
        return [[ring(ps.Outline(i))] + [ring(ps.Hole(i, h)) for h in range(ps.HoleCount(i))]
                for i in range(ps.OutlineCount())]

    silk = pcbnew.SHAPE_POLY_SET()                         # the whole layer, texts and all, as it is plotted
    b.ConvertBrdLayerToPolygonalContours(pcbnew.F_SilkS, silk)
    fab = pcbnew.SHAPE_POLY_SET()                          # the bodies' lines alone: the Fab layer's texts (each part's
    for f in b.GetFootprints():                            # reference and value again, turned with the part) left out
        for g in f.GraphicalItems():
            if g.GetClass() == "PCB_SHAPE" and g.GetLayer() == pcbnew.F_Fab:
                g.TransformShapeToPolygon(fab, pcbnew.F_Fab, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_INSIDE)
    fab.Simplify()

    cuts = [d for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    ends = [(T(p.x), T(p.y)) for d in cuts for p in (d.GetStart(), d.GetEnd())]
    edge = (min(x for x, y in ends), min(y for x, y in ends), max(x for x, y in ends), max(y for x, y in ends))
    if len(cuts) != 4 or any(d.GetShape() != pcbnew.SHAPE_T_SEGMENT for d in cuts) or \
            any(x not in (edge[0], edge[2]) or y not in (edge[1], edge[3]) for x, y in ends):
        raise SystemExit("geom: the outline is no longer four straight lines: print_1to1.py draws a rectangle")
    back = [f.GetReference() for f in b.GetFootprints() if f.GetLayer() != pcbnew.F_Cu]
    if back:
        raise SystemExit("geom: parts on the back (%s): print_1to1.py draws the front only" % ", ".join(back))
    fps = []
    for f in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
        pads, box = [], None
        for p in f.Pads():
            ps = pcbnew.SHAPE_POLY_SET()
            p.TransformShapeToPolygon(ps, pcbnew.F_Cu, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_INSIDE)
            size = p.GetSize(pcbnew.F_Cu)
            pads.append(dict(n=p.GetNumber(), x=T(p.GetPosition().x), y=T(p.GetPosition().y), poly=ring(ps.Outline(0)),
                             size=sorted((T(size.x), T(size.y))), drill=(T(p.GetDrillSize().x), T(p.GetDrillSize().y)),
                             plated=p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH))
        for g in f.GraphicalItems():                       # the body: what is drawn on the Fab layer, texts apart,
            if g.GetClass() == "PCB_SHAPE" and g.GetLayer() == pcbnew.F_Fab:               # to the middle of its lines
                bb, w = g.GetBoundingBox(), pcbnew.ToMM(g.GetWidth()) / 2
                r = (T(bb.GetX()) + w, T(bb.GetY()) + w, T(bb.GetRight()) - w, T(bb.GetBottom()) - w)
                box = r if box is None else (min(box[0], r[0]), min(box[1], r[1]), max(box[2], r[2]), max(box[3], r[3]))
        fps.append(dict(ref=f.GetReference(), value=f.GetValue(), fp=f.GetFPID().GetUniStringLibItemName(),
                        x=T(f.GetPosition().x), y=T(f.GetPosition().y), rot=f.GetOrientationDegrees(), pads=pads, box=box))
    tb = b.GetTitleBlock()
    d = dict(card=N.CARD, rev=N.REV, date=tb.GetDate(), pcb=os.path.basename(pcb),
             sha256=hashlib.sha256(open(pcb, "rb").read()).hexdigest(), edge=edge,
             silk=rings(silk), fab=rings(fab), fps=fps)
    json.dump(d, open(out, "w"))
    print("geom: %d parts, %d pads, %d silkscreen and %d body outlines -> %s"
          % (len(fps), sum(len(f["pads"]) for f in fps), len(d["silk"]), len(d["fab"]), os.path.basename(out)))


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
            if a not in ("J1",):                            # (the DB9's D reaches past the front edge)
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


# the V1.2 key connections, checked pin by pin in the schematic netlist and on the board's pads: written from
# docs/cards/io.md's walk through the V1.1 card (section 3) and from what V1.2 adds, not from io12_netlist.py
KEY = [
    # the bus and the buffer
    ("X1", "A19", "DATA0"), ("X1", "A26", "DATA7"), ("IC12", "2", "DATA0"), ("IC12", "9", "DATA7"),
    ("IC12", "18", "ID0"), ("IC12", "11", "ID7"), ("IC12", "1", "-IO-RD"), ("IC12", "19", "BUFEN#"),
    ("X1", "B25", "-IO-RD"), ("X1", "B26", "-IO-WR"), ("X1", "C30", "-RESET"), ("X1", "C13", "-INT"),
    ("X1", "C26", "IN"), ("X1", "C27", "OUT"), ("X1", "C7", "IO-ADDR0"), ("X1", "C8", "IO-ADDR1"),
    ("X1", "C9", "IO-ADDR2"), ("X1", "C10", "IO-ADDR3"),
    ("IC13", "1", "-IO-ADDRSEL"), ("IC13", "2", "-IO-DATASEL"), ("IC13", "4", "-IO-SEL6"), ("IC13", "5", "-IO-SEL7"),
    ("IC13", "3", "SELPORT#"), ("IC13", "9", "SELPORT#"), ("IC13", "6", "SELRTC#"), ("IC13", "10", "SELRTC#"),
    ("IC13", "8", "BUFEN#"),
    # the decode, the half, the two port blocks
    ("IC5", "1", "IO-ADDR0"), ("IC5", "2", "IO-ADDR1"), ("IC5", "3", "IO-ADDR2"), ("IC5", "4", "HALF-G2A"),
    ("IC5", "5", "G2B#"), ("JP10", "2", "G2B#"), ("JP10", "1", "GND"), ("JP10", "3", "-BUS-EN"), ("X1", "C28", "-BUS-EN"),
    ("IC5", "6", "HALF-G1"), ("IC5", "15", "-IO-SEL0"), ("IC5", "14", "-IO-SEL1"),
    ("IC5", "9", "-IO-SEL6"), ("IC5", "7", "-IO-SEL7"),
    ("JP3", "1", "GND"), ("JP3", "2", "IO-ADDR3"), ("JP3", "3", "HALF-G2A"), ("JP3", "4", "HALF-G1"),
    ("JP3", "5", "IO-ADDR3"), ("JP3", "6", "VCC"),
    ("JP4", "16", "-IO-SEL0"), ("JP4", "15", "-IO-ADDRSEL"), ("JP4", "2", "-IO-SEL7"), ("JP4", "1", "-IO-ADDRSEL"),
    ("JP5", "14", "-IO-SEL1"), ("JP5", "13", "-IO-DATASEL"), ("JP5", "16", "-IO-SEL0"),
    # the strobes
    ("IC8", "1", "-IO-RD"), ("IC8", "2", "IO-RD"), ("IC8", "3", "-IO-WR"), ("IC8", "4", "IO-WR"),
    ("IC8", "5", "-RESET"), ("IC8", "6", "RESET"), ("IC8", "9", "RESET"), ("IC8", "8", "-B-RESET"),
    ("IC8", "11", "-IO-DATASEL"), ("IC8", "10", "IO-SELDATA"), ("IC8", "13", "UART-INT"), ("IC8", "12", "UINT#"),
    ("JP7", "1", "UINT#"), ("JP7", "2", "-INT"),
    ("RN1", "1", "VCC"), ("RN1", "2", "-INT"), ("RN1", "3", "IO-SELDATA"), ("RN1", "4", "-B-RESET"),
    ("RN1", "5", "RESET"), ("RN1", "6", "IO-WR"), ("RN1", "7", "IO-RD"), ("RN1", "8", "-IO-ADDRSEL"),
    ("RN1", "9", "-IO-DATASEL"), ("RN2", "1", "VCC"), ("RN2", "2", "ID0"), ("RN2", "9", "ID7"),
    # the control latch: the ROM's bit map
    ("IC7", "12", "-IO-ADDRSEL"), ("IC7", "13", "-IO-ADDRSEL"), ("IC7", "11", "IO-ADDRSEL"), ("IC7", "4", "IO-ADDRSEL"),
    ("IC7", "5", "IO-WR"), ("IC7", "6", "CTLCK"), ("IC10", "11", "CTLCK"), ("IC10", "1", "-B-RESET"),
    ("IC10", "3", "ID0"), ("IC10", "18", "ID7"), ("IC10", "2", "SWITCH-LED"), ("IC10", "5", "LCD-ENABLE"),
    ("IC10", "6", "LCD-REGISTER"), ("IC10", "9", "UART-A0"), ("IC10", "12", "UART-A1"), ("IC10", "15", "UART-A2"),
    ("IC10", "16", "UART-CS"), ("IC10", "19", "TIL311"),
    # the UART
    ("IC1", "1", "ID0"), ("IC1", "8", "ID7"), ("IC1", "12", "IO-SELDATA"), ("IC1", "13", "UART-CS"),
    ("IC1", "14", "GND"), ("IC1", "25", "GND"), ("IC1", "28", "UART-A0"), ("IC1", "27", "UART-A1"),
    ("IC1", "26", "UART-A2"), ("IC1", "19", "IO-WR"), ("IC1", "22", "IO-RD"), ("IC1", "18", "VCC"),
    ("IC1", "21", "VCC"), ("IC1", "35", "RESET"), ("IC1", "9", "ICLK"), ("IC1", "15", "ICLK"),
    ("IC1", "16", "UCLK"), ("OSC1", "5", "UCLK"), ("OSC1", "1", "VCC"), ("OSC1", "8", "VCC"), ("OSC1", "4", "GND"),
    ("IC1", "36", "VCC"), ("IC1", "37", "VCC"), ("IC1", "38", "VCC"), ("IC1", "39", "VCC"), ("IC1", "30", "UART-INT"),
    ("IC1", "11", "TX"), ("IC2", "11", "TX"), ("J2", "5", "TX"), ("IC1", "10", "RX"), ("JP2", "2", "RX"),
    ("JP2", "1", "RX-232"), ("IC2", "12", "RX-232"), ("JP2", "3", "RX-TTL"), ("J2", "4", "RX-TTL"),
    ("J2", "1", "GND"), ("J2", "2", "GND"),
    ("IC2", "14", "TX-OUT"), ("JP1", "2", "TX-OUT"), ("JP1", "5", "TX-OUT"), ("IC2", "13", "RX-IN"),
    ("JP1", "1", "RX-IN"), ("JP1", "6", "RX-IN"), ("JP1", "3", "DB9-3"), ("J1", "3", "DB9-3"),
    ("JP1", "4", "DB9-2"), ("J1", "2", "DB9-2"), ("J1", "5", "GND"), ("J1", "SH", "GND"),
    ("IC2", "1", "C1+"), ("IC2", "3", "C1-"), ("IC2", "4", "C2+"), ("IC2", "5", "C2-"), ("IC2", "2", "V+"),
    ("IC2", "6", "V-"), ("C3", "2", "VCC"), ("C4", "1", "GND"), ("IC2", "16", "VCC"), ("IC2", "15", "GND"),
    # switches and LEDs
    ("IC6", "3", "IO-RD"), ("IC6", "4", "IO-SELDATA"), ("IC6", "5", "SWITCH-LED"), ("IC6", "6", "SWOE#"),
    ("IC3", "1", "SWOE#"), ("IC3", "19", "SWOE#"), ("IC3", "2", "SW0"), ("S0", "2", "SW0"), ("S0", "1", "VCC"),
    ("S0", "3", "GND"), ("IC3", "17", "SW7"), ("S7", "2", "SW7"), ("IC3", "18", "ID0"), ("IC3", "3", "ID7"),
    ("IC6", "1", "IO-WR"), ("IC6", "2", "IO-SELDATA"), ("IC6", "13", "SWITCH-LED"), ("IC6", "12", "LEDCK"),
    ("IC4", "11", "LEDCK"), ("IC4", "1", "-B-RESET"), ("IC4", "3", "ID0"), ("IC4", "18", "ID7"),
    ("IC4", "2", "LQ0"), ("R3", "2", "LQ0"), ("R3", "1", "LEDA0"), ("LED0", "2", "LEDA0"), ("LED0", "1", "GND"),
    ("IC4", "19", "LQ7"), ("R10", "2", "LQ7"), ("R10", "1", "LEDA7"), ("LED7", "2", "LEDA7"),
    # the TIL311s
    ("IC11", "1", "IO-WR"), ("IC11", "2", "IO-SELDATA"), ("IC11", "13", "TIL311"), ("IC11", "12", "TILCK"),
    ("IC9", "11", "TILCK"), ("IC9", "1", "-B-RESET"), ("IC9", "3", "ID0"), ("IC9", "18", "ID7"),
    ("IC9", "2", "TL0"), ("DS2", "3", "TL0"), ("IC9", "5", "TL1"), ("DS2", "2", "TL1"), ("IC9", "6", "TL2"),
    ("DS2", "13", "TL2"), ("IC9", "9", "TL3"), ("DS2", "12", "TL3"), ("IC9", "12", "TH0"), ("DS1", "3", "TH0"),
    ("IC9", "19", "TH3"), ("DS1", "12", "TH3"), ("DS1", "1", "VCC"), ("DS1", "14", "VCC"), ("DS1", "5", "GND"),
    ("DS1", "7", "GND"), ("DS1", "8", "GND"), ("DS2", "1", "VCC"), ("DS2", "14", "VCC"), ("DS2", "7", "GND"),
    # the LCD
    ("IC6", "9", "IO-SELDATA"), ("IC6", "10", "LCD-ENABLE"), ("IC6", "11", "IO-WR"), ("IC6", "8", "LCDSTB#"),
    ("IC7", "1", "LCDSTB#"), ("IC7", "2", "LCDSTB#"), ("IC7", "3", "LCD-E"), ("DS3", "6", "LCD-E"),
    ("DS3", "4", "LCD-REGISTER"), ("DS3", "5", "GND"), ("DS3", "1", "GND"), ("DS3", "2", "VCC"), ("DS3", "3", "LCD-VO"),
    ("RV1", "2", "LCD-VO"), ("DS3", "7", "ID0"), ("DS3", "14", "ID7"), ("DS3", "15", "LCD-BL"), ("R11", "2", "LCD-BL"),
    ("R11", "1", "VCC"), ("DS3", "16", "GND"),
    # IN and OUT
    ("S8", "2", "INSW"), ("JP6", "2", "INSW"), ("JP6", "1", "IN"), ("R1", "2", "OUT"), ("R1", "1", "OUTA"),
    ("LED8", "2", "OUTA"), ("LED8", "1", "GND"),
    # the clock
    ("IC14", "1", "-IO-SEL6"), ("IC14", "2", "-IO-WR"), ("IC14", "3", "AS#"), ("IC7", "9", "AS#"), ("IC7", "10", "AS#"),
    ("IC7", "8", "RTC-AS"), ("IC15", "14", "RTC-AS"), ("IC14", "4", "-IO-SEL7"), ("IC14", "5", "-IO-RD"),
    ("IC14", "6", "RTC-RD#"), ("IC15", "17", "RTC-RD#"), ("IC14", "9", "-IO-SEL7"), ("IC14", "10", "-IO-WR"),
    ("IC14", "8", "RTC-WR#"), ("IC15", "15", "RTC-WR#"), ("IC15", "4", "ID0"), ("IC15", "11", "ID7"),
    ("IC15", "1", "GND"), ("IC15", "13", "GND"), ("IC15", "18", "VCC"), ("IC15", "12", "GND"), ("IC15", "16", "GND"),
    ("IC15", "24", "VCC"), ("IC15", "2", "RTC-X1"), ("Y1", "1", "RTC-X1"), ("IC15", "3", "RTC-X2"), ("Y1", "2", "RTC-X2"),
    ("IC15", "20", "VBAT"), ("BT1", "1", "VBAT"), ("BT1", "2", "GND"), ("IC15", "19", "RTC-IRQ#"),
    ("JP8", "1", "RTC-IRQ#"), ("JP8", "2", "-INT"), ("IC15", "21", "RCLR#"), ("JP9", "1", "RCLR#"), ("JP9", "2", "GND"),
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
    """BOM.md from io12_netlist.PARTS: one line per value, footprint and note"""
    rows = collections.OrderedDict()
    order = lambda r: (re.match(r"[A-Z]+", r).group(0), int(re.search(r"\d+", r).group(0)))
    for ref in sorted(N.PARTS, key=order):
        value, symid, fpid, note = N.PARTS[ref]
        if ref in N.DECOUPLE:
            note = "decoupling, 0.1 inch leads"
        key = (value, fpid.split(":")[1], N.BUY.get(ref, ""))
        rows.setdefault(key, [[], note])[0].append(ref)
    nsock = collections.Counter(ic_size(r) for r in N.PARTS if "DIP-" in N.PARTS[r][2] and r.startswith("IC"))
    L = ["# I/O card V1.2 - bill of materials", "",
         "GENERATED by `gen_io12.py bom` from `io12_netlist.py` (%s) - do not edit. %d parts. Buy %s: %s; a 4-pin "
         "socket for the oscillator, two 14-pin sockets for the TIL311s and a 16-way socket strip for the LCD."
         % (N.DATE, len(N.PARTS), N.SOCKETS,
            ", ".join("%d x %d-pin %.2f mm" % (n, p, w) for (p, w), n in sorted(nsock.items()))), "",
         "| Qty | Value | Footprint | References | Buy / note |", "|---|---|---|---|---|"]
    for (value, fp, buy), (refs, note) in rows.items():
        L.append("| %d | %s | %s | %s | %s |" % (len(refs), value, fp, ", ".join(refs),
                                                 buy or (note if len(refs) == 1 else "")))
    L += ["", "Shunts: one each for JP4 and JP5 (the two ports), JP2 and JP10 (on 1-2, as V1.1, unless the decoder is to "
          "follow -BUS-EN), two each for JP3 and JP1, one for JP6 (IN); JP7, JP8 and JP9 are left open.", "",
          "The 74LS types are the V1.1 card's. The three latches may be 74HCT273 (the LEDs are a little brighter); "
          "the buffer IC12 stays a 74LS245 or 74HCT245 (TTL input levels on both sides).", ""]
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
    elif cmd == "geom":
        geom(*a)
    elif cmd == "silk":
        ok = silk_cmd(*a)
    elif cmd == "planes":
        ok = planes(*a)
    elif cmd == "padnets":
        ok = padnets(*a)
    elif cmd == "xtal":
        xtal(*a)
    elif cmd == "verify":
        ok = verify(*a)
    elif cmd == "fab":
        fab(*a)
    elif cmd == "bom":
        bom()
    elif cmd in ("dsn", "shuffle", "ses", "stats", "refill"):
        getattr(G13, cmd)(*a)
    else:
        raise SystemExit(__doc__)
    sys.stdout.flush()
    os._exit(0 if ok else 1)
