#!/usr/bin/env python3
"""gen_mem_v2.py - write the KiCad schematic and the placement-option boards of the YACC1 memory card v2.0 (2026-09-24).

Run with KiCad's bundled Python (the board half needs pcbnew); build.sh does that:

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 gen_mem_v2.py sch
    ... gen_mem_v2.py board a <net>   (one placement option; placements.py holds the options)

v2.0 = the memory card v1.3 + the CompactFlash section (mem_v2_netlist.py says exactly what that is). This script:

  sch    copies the v1.3 schematic (../v1.3, 6 sheets converted from Eagle) unchanged except for
           - project/sheet-file names memory-v1.3 -> memory-v2.0 and the title blocks,
           - sheet 1: the IO-ADDR0-3 / -IO-RD / -IO-WR labels on X1 become global labels (sheet 7 uses those nets)
             and a note says so,
         adds sheet 7 = the CF section, drawn with the CF card's own sheet writer (hardware/cards/cf/kicad/v1.0/gen_cf.py,
         class Sheet: KiCad standard symbols, short wire stubs to labels / power symbols, no-connect flags) from
         mem_v2_netlist.py; nets shared with v1.3 are boxed global labels, as on the converted v1.3 sheets;
         copies the v1.3 symbol + footprint libraries (nickname memory-v1.3-eagle kept, so nothing is re-linked).
  board  starts from the v1.3 board (same outline, X1 at the same place: it plugs into the same backplane), keeps every
         v1.3 footprint and its copper, adds the CF footprints (KiCad standard libraries, as on the CF card v1.0),
         puts EVERY pad on the net the v2.0 schematic gives it (names from a netlist export of the schematic), renames
         the v1.3 tracks to the same names, applies the option's moves and placements (placements.py: first the
         TMP registers IC26-IC29 and RN5/RN6 onto the board where the fabricated card has them - the converted v1.3
         board keeps them OUTSIDE the outline, as the tree's Eagle board does), deletes the v1.3 track segments/vias
         that sat on a pad that moved, adds the silkscreen (title V2.0, "CF: P8/P9"), the CF-to-IDE adapter zones
         (User.Drawings) and the reserved spot of the fabricated card's IC15 (User.Comments). build.sh then trims the
         v1.3 copper the moves broke (kicad-cli DRC) - the CF section itself is NOT routed: ratsnest only.
  trim / check / review   the steps after the board: see build.sh.
"""
import os, sys, re, json, shutil, subprocess, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", ".."))
V13 = os.path.join(HERE, "..", "v1.3")
sys.path.insert(0, HERE)
import mem_v2_netlist as NL                                # noqa: E402  (puts the CF card folder on sys.path)
import gen_cf                                              # noqa: E402  the CF card v1.0's sheet writer (read-only reuse)

PROJ = "memory-v2.0"
OLD = "memory-v1.3"
CLI = gen_cf.CLI
KFP = gen_cf.KFP
G = 2.54
ROOT_UUID = "42231b4d-4c5f-cebb-da74-8d622a2f1dd4"        # the v1.3 root sheet's UUID, kept (footprint paths stay valid)
SHEET7 = gen_cf.U("memory-v2.0", "sheet7", "instance")
SHEET7_FILE_UUID = gen_cf.U("memory-v2.0", "sheet7", "file")
TITLE_OLD, TITLE_NEW = "YACC1 MEMORY BOARD V1.3", "YACC1 MEMORY BOARD V2.0"


def gx(n):
    return n * G


# ---------------------------------------------------------------------------------------------------------------------
# 1. schematic
def copy_libs():
    shutil.copy(os.path.join(V13, OLD + "-eagle.kicad_sym"), os.path.join(HERE, OLD + "-eagle.kicad_sym"))
    dst = os.path.join(HERE, OLD + "-eagle.pretty")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(os.path.join(V13, OLD + "-eagle.pretty"), dst)
    for t in ("sym-lib-table", "fp-lib-table"):
        shutil.copy(os.path.join(V13, t), os.path.join(HERE, t))


def global_label(net, x, y, ang, uid):
    just = {0: "left", 180: "right", 90: "left", 270: "right"}[ang]
    return ('\t(global_label %s (shape passive) (at %s %s %d) (fields_autoplaced yes) (effects (font (size 1.27 1.27)) '
            '(justify %s)) (uuid "%s")\n\t\t(property "Intersheetrefs" "${INTERSHEET_REFS}" (at %s %s 0) '
            '(effects (font (size 1.27 1.27)) (hide yes)))\n\t)' % (gen_cf.q(net), gen_cf.f(x), gen_cf.f(y), ang, just,
                                                                   uid, gen_cf.f(x), gen_cf.f(y)))


def copy_v13_sheets():
    for n in range(1, 7):
        t = open(os.path.join(V13, "%s-sheet%d.kicad_sch" % (OLD, n))).read()
        t = t.replace('(project "%s"' % OLD, '(project "%s"' % PROJ)
        note = "Unchanged from v1.3 (converted from Eagle Memory V1.3.sch sheet %d)" % n
        if n == 1:
            note = "v1.3 sheet 1 + IO-ADDR0-3, -IO-RD, -IO-WR made global (CF section, sheet 7) + note"
            cnt = 0
            for net in sorted(set(NL.V13_RENAMED.values())):
                for m in list(re.finditer(r'\t\(label "%s" \(at ([\d.]+) ([\d.]+) (\d+)\).*?\(uuid "([^"]+)"\)\)'
                                          % re.escape(net), t)):
                    t = t.replace(m.group(0), global_label(net, float(m.group(1)), float(m.group(2)),
                                                           int(m.group(3)), m.group(4)))
                    cnt += 1
            assert cnt == len(NL.V13_RENAMED), "sheet 1: expected %d labels, converted %d" % (len(NL.V13_RENAMED), cnt)
            txt = ("Memory card v2.0: IO-ADDR0-3 (C7-C10), -IO-RD (B25), -IO-WR (B26) and -RESET (C30) also feed the\n"
                   "CompactFlash section on sheet 7 (I/O ports P8 = register latch, P9 = data; its own 74LS138 IC30,\n"
                   "enabled by IO-ADDR3). DATA0-7 reach its data buffer IC34 and latch IC32. v1.3 used none of the I/O\n"
                   "signals: the six labels above were X1-only local labels and are global labels now.")
            t = t.rstrip()
            assert t.endswith(")")
            t = t[:-1] + ('\t(text %s (exclude_from_sim no) (at 111.76 236.22 0) (effects (font (size 1.778 1.778) '
                          '(thickness 0.254) bold) (justify left top)) (uuid "%s"))\n)\n'
                          % (gen_cf.q(txt), gen_cf.U("memory-v2.0", "sheet1-note")))
        t2 = re.sub(r'\(title_block \(title "%s sheet %d"\) \(comment 1 "[^"]*"\)\)' % (re.escape(OLD), n),
                    '(title_block (title "%s sheet %d") (date "%s") (rev "%s") (comment 1 %s))'
                    % (PROJ, n, NL.DATE, NL.REV, gen_cf.q(note)), t)
        assert t2 != t, "sheet %d: title block not found" % n
        open(os.path.join(HERE, "%s-sheet%d.kicad_sch" % (PROJ, n)), "w").write(t2)


def write_root():
    t = open(os.path.join(V13, OLD + ".kicad_sch")).read()
    assert '(uuid "%s")' % ROOT_UUID in t
    t = t.replace('(project "%s"' % OLD, '(project "%s"' % PROJ)
    t = t.replace('"%s-sheet' % OLD, '"%s-sheet' % PROJ)
    old_tb = '(title_block (title "%s") (comment 1 "Converted from Eagle schematic; see README.md"))' % OLD
    assert old_tb in t
    t = t.replace(old_tb, '(title_block (title "YACC1 memory card v2.0") (date "%s") (rev "%s") (comment 1 %s) '
                  '(comment 2 %s))' % (NL.DATE, NL.REV,
                                       gen_cf.q("Sheets 1-6 = memory card v1.3 (sheet 1: six bus labels made global); "
                                                "sheet 7 = CompactFlash on P8/P9 (the CF card v1.0 circuit)"),
                                       gen_cf.q("Circuit source: mem_v2_netlist.py; generated by gen_mem_v2.py; "
                                                "see README.md")))
    block = ('\t(sheet (at 101.6 50.8) (size 50.8 15.24) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) '
             '(fields_autoplaced yes)\n\t\t(stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0)) (uuid "%s")\n'
             '\t\t(property "Sheetname" "%s" (at 101.6 50.1 0) (effects (font (size 1.27 1.27)) (justify left bottom)))\n'
             '\t\t(property "Sheetfile" "%s-sheet7.kicad_sch" (at 101.6 66.7 0) (effects (font (size 1.27 1.27)) '
             '(justify left top)))\n\t\t(instances (project "%s" (path "/%s" (page "8"))))\n\t)\n'
             % (SHEET7, NL.CF_SHEET, PROJ, PROJ, ROOT_UUID))
    i = t.index("\t(sheet_instances")
    t = t[:i] + block + t[i:]
    open(os.path.join(HERE, PROJ + ".kicad_sch"), "w").write(t)


class CFSheet(gen_cf.Sheet):
    """gen_cf's sheet writer; nets shared with the v1.3 sheets get boxed global labels"""
    def label(self, x, y, net, d):
        if net not in NL.SHARED:
            return super().label(x, y, net, d)
        if (round(x, 3), round(y, 3), net) in self.labels:
            return
        self.labels.add((round(x, 3), round(y, 3), net))
        ang = {"R": 0, "L": 180, "U": 90, "D": 270}[d]
        self.out.append(global_label(net, x, y, ang, gen_cf.U("gl", x, y, net)))

    def write(self, path):
        head = ['(kicad_sch', '\t(version 20260306)', '\t(generator "gen_mem_v2")', '\t(generator_version "1.0")',
                '\t(uuid "%s")' % SHEET7_FILE_UUID, '\t(paper "A3")',
                '\t(title_block (title "%s sheet 7: CompactFlash interface") (date "%s") (rev "%s") (company "YACC1")'
                % (PROJ, NL.DATE, NL.REV),
                '\t\t(comment 1 "CF (True IDE, 8-bit) on I/O ports P8 (register latch) / P9 (data) - docs/cards/cf.md")',
                '\t\t(comment 2 "The CF card v1.0 circuit minus its bus connector, PWR LED and DASP LED")',
                '\t\t(comment 3 "Circuit source: mem_v2_netlist.py; this sheet is generated by gen_mem_v2.py"))',
                '\t(lib_symbols']
        for libid in sorted(self.syms):
            head.append(self.syms[libid].text)
        head.append('\t)')
        open(path, "w").write("\n".join(head + self.out + ['\t(embedded_fonts no)', ')', '']))


def build_sheet7():
    # point gen_cf's writer at the v2.0 CF section
    gen_cf.N = type("CFSection", (), dict(PARTS=NL.PARTS, NETS=NL.NETS, NO_CONNECT=NL.NO_CONNECT))
    gen_cf.NETOF = {(r, p): n for n, conns in NL.NETS.items() for r, p in conns}
    gen_cf.NC = {(r, p) for r, ps in NL.NO_CONNECT.items() for p in ps}
    gen_cf.PROJ = PROJ
    gen_cf.ROOT_UUID = ROOT_UUID + "/" + SHEET7          # symbol instance path /root/sheet7
    S = CFSheet()
    S.pwr = 700                                           # #PWR701.. (the v1.3 sheets use #GNDn / #P+n / #FLGn)
    # --- where the bus signals come from -----------------------------------------------------------------------------
    S.box(gx(5), gx(11), gx(57), gx(52.5), "FROM THE BUS (memory card X1, sheet 1)")
    S.text(gx(6), gx(16), "The CF section has no bus connector of its own: it shares the memory\n"
           "card's X1. Boxed global labels = nets shared with sheets 1-6:\n\n"
           "  IO-ADDR0-3   X1 C7-C10   port number -> IC30 (74LS138)\n"
           "  -IO-RD       X1 B25      -> IC31 gate 2 (CF -IOR)\n"
           "  -IO-WR       X1 B26      -> IC31 gates 1 and 3 (latch clock, CF -IOW)\n"
           "  -RESET       X1 C30      -> IC32 CLR, IC33 gate 2 (also IC12 PRE)\n"
           "  DATA0-7      X1 A19-A26  -> IC34 A side; DATA0-3 -> IC32 D1-D4\n"
           "  VCC, GND     the card's supply (six pins each on X1)\n\n"
           "On v1.3, IO-ADDR0-3, -IO-RD and -IO-WR reached X1 only.\n"
           "The CF section drives the data bus only while the CPU\n"
           "reads port P9 (IC34 enabled by -CFOE, DIR = -IOR).", size=1.27)
    # --- decode + strobe gating --------------------------------------------------------------------------------------
    S.box(gx(58), gx(5), gx(105), gx(42), "PORT DECODE + STROBE GATING")
    S.part("IC30", 1, gx(72), gx(22))
    for u, y in ((1, 12), (2, 21), (3, 30), (4, 38)):
        S.part("IC31", u, gx(95), gx(y))
    S.text(gx(59), gx(34), "IC30: IO-ADDR3 = 1 enables;\nY0 = port 8, Y1 = port 9.\nIC31 gate 1: P8 latch clock\n"
           "IC31 gate 2: CF -IOR\nIC31 gate 3: CF -IOW\nIC31 gate 4: unused", size=1.27)
    # --- latch + CF reset --------------------------------------------------------------------------------------------
    S.box(gx(58), gx(43), gx(105), gx(68), "P8 LATCH: DA0-2 + CF RESET")
    S.part("IC32", 1, gx(72), gx(56))
    S.part("IC33", 2, gx(95), gx(52))
    S.text(gx(86), gx(57), "IC33 gate 2: -CFRESET =\n-RESET AND -SRST\n(bus reset or latch bit 3)", size=1.27)
    # --- data buffer + its enable ------------------------------------------------------------------------------------
    S.box(gx(106), gx(5), gx(131), gx(63), "P9 DATA BUFFER")
    S.part("IC34", 1, gx(118), gx(17))
    S.part("IC33", 1, gx(118), gx(37))
    S.part("IC33", 3, gx(118), gx(46))
    S.part("IC33", 4, gx(118), gx(54))
    S.text(gx(107), gx(58.5), "DIR = -IOR (low: CF -> bus)\n-CFOE = -IOR AND -IOW\nACTK sinks the ACT LED", size=1.27)
    # --- IDE header, pull-ups, adapter power -------------------------------------------------------------------------
    S.box(gx(132), gx(5), gx(160.5), gx(63), "IDE HEADER J2 (CF-TO-IDE ADAPTER)")
    S.part("J2", 1, gx(142), gx(18), fields={"Reference": (-1.27, -27.94), "Value": (3.81, -27.94)}, pstub=G)
    S.part("RN9", 1, gx(142), gx(37))
    for i, r in enumerate(("R10", "R11", "R12", "R13")):
        S.part(r, 1, gx(136 + 3 * i), gx(50))
    S.part("JP2", 1, gx(155), gx(47))
    S.part("J3", 1, gx(155), gx(55))
    S.part("C30", 1, gx(157.5), gx(56))
    S.text(gx(133), gx(59), "CSEL = GND (master)\n-CS0 = GND, -CS1 = VCC", size=1.27)
    # --- ACT LED -----------------------------------------------------------------------------------------------------
    S.box(gx(106), gx(66), gx(131), gx(97), "ACT LED")
    S.part("R14", 1, gx(118), gx(73))
    S.part("LED1", 1, gx(118), gx(80), rot=90)
    S.text(gx(107), gx(89), "ACT: any P9 access (the buffer\nenable). No PWR LED here: the\n"
           "card has PWR0 + R2 (sheet 1).\nNo DASP LED on v2.0 (Ken).", size=1.27)
    # --- power + decoupling ------------------------------------------------------------------------------------------
    S.box(gx(5), gx(54), gx(57), gx(76), "POWER + DECOUPLING (one 100 nF per new IC)")
    for i, c in enumerate(("C25", "C26", "C27", "C28", "C29")):
        S.part(c, 1, gx(8 + 5 * i), gx(65))
    S.part("IC31", 5, gx(38), gx(65))
    S.part("IC33", 5, gx(47), gx(65))
    S.text(gx(6), gx(71.5), "C25 IC30, C26 IC31, C27 IC32, C28 IC33, C29 IC34.\n"
           "C30 10 uF bulk at J3. PWR_FLAGs: sheet 1.", size=1.27)
    # --- notes -------------------------------------------------------------------------------------------------------
    S.box(gx(5), gx(78), gx(105), gx(112), "DESIGN NOTES (MEMORY CARD v2.0, CF SECTION)")
    S.text(gx(5.5), gx(81), "\n".join([
        "1. Two I/O ports. P8 (write): 74LS175 latch IC32 - bits 0-2 = the ATA task-file register (CF DA0-2), bit 3 = CF",
        "   reset (1 = held in reset). P9 (read/write): the selected ATA register, 8-bit True IDE, through the 74LS245 IC34.",
        "2. Decode: 74LS138 IC30 on IO-ADDR0-2, enabled by IO-ADDR3 (Y0 = port 8, Y1 = port 9), as on the CF card v1.0.",
        "   The ROM in the machine and both emulators use P8/P9. The I/O card must keep its IO-ADDR-HL strap at P0-P7.",
        "3. IC31 (74LS32) ORs each port select with -IO-WR / -IO-RD: -IOR, -IOW and the latch clock are low only during",
        "   the bus strobe for this port. -CS0 (J2 pin 37) LOW and -CS1 (38) HIGH: the strobes alone define every cycle",
        "   (docs/cards/cf.md section 4: gating -CS0 would break the chip-select hold time after -IOR).",
        "4. J2 = 40-pin IDE header (pin 20 kept) for a CF-to-IDE adapter: plugged straight on (TAODAN CF-IDE40, standing",
        "   off the component side) or on a short ribbon (SinLoon). Adapter power: J3 (1 = +5 V, 2 and 3 = GND, 4 not",
        "   used) or, with JP2 fitted, IDE pin 20 for adapters powered there.",
        "5. Pull-ups: CF D0-7 (RN9: an empty adapter reads $FF = 'no card' to the ROM driver), IORDY, -PDIAG, -DASP;",
        "   -DMACK held inactive; CSEL grounded (master). SRST (IC32 Q4) is a one-pin net by design (a probe point).",
        "6. From hardware/cards/cf/kicad/v1.0/cf_netlist.py: U1->IC30 U2->IC31 U3->IC32 U4->IC33 U5->IC34 J1->J2 J2->J3",
        "   JP1->JP2 RN1->RN9 R1-R5->R10-R14 LED2->LED1 C1-C6->C25-C30. Dropped: X1 (the card's bus connector), the",
        "   PWR LED (LED1, R7: the card has PWR0 + R2) and the DASP LED (LED3, R6).",
        "Theory: docs/cards/cf.md, docs/cards/memory.md. Circuit source: mem_v2_netlist.py (edit, then re-run build.sh)."]),
        size=1.5)
    for ref, (value, symid, fpid, note) in NL.PARTS.items():
        s = S.lib(gen_cf.SYM_SUB.get(symid, symid))
        if S.placed[ref] != set(s.units):
            raise SystemExit("sheet 7: %s units placed %s, symbol has %s" % (ref, sorted(S.placed[ref]), s.units))
    missing = [k for k in list(gen_cf.NETOF) + list(gen_cf.NC) if k not in S.pinhits]
    if missing:
        raise SystemExit("sheet 7: pins not drawn: %s" % missing)
    S.write(os.path.join(HERE, PROJ + "-sheet7.kicad_sch"))
    return S


def write_project():
    pro = json.load(open(os.path.join(V13, OLD + ".kicad_pro")))
    pro["meta"]["filename"] = PROJ + ".kicad_pro"
    json.dump(pro, open(os.path.join(HERE, PROJ + ".kicad_pro"), "w"), indent=2)
    return pro


def main_sch():
    probs = NL.check()
    if probs:
        raise SystemExit("mem_v2_netlist.check() failed:\n" + "\n".join(probs))
    copy_libs()
    copy_v13_sheets()
    write_root()
    S = build_sheet7()
    write_project()
    print("schematic: %s.kicad_sch + sheets 1-6 (v1.3) + sheet 7 (CF: %d parts, %d power symbols)"
          % (PROJ, len(NL.PARTS), S.pwr - 700))


# ---------------------------------------------------------------------------------------------------------------------
# 2. boards
def read_netlist(path):
    """-> ({(ref, pin): net}, {ref: symbol path}) from a kicad-cli kicadsexpr netlist"""
    root = gen_cf.sparse(open(path).read())[0]
    nodes, paths = {}, {}
    for comp in gen_cf.sfind(gen_cf.sfind(root, "components")[0], "comp"):
        ref = gen_cf.unq(gen_cf.sfind(comp, "ref")[0][1])
        sp = gen_cf.sfind(comp, "sheetpath")[0]
        tst = gen_cf.unq(gen_cf.sfind(sp, "tstamps")[0][1])
        ts = [gen_cf.unq(t[1]) for t in gen_cf.sfind(comp, "tstamps")]
        paths[ref] = tst + ts[0]
    for net in gen_cf.sfind(gen_cf.sfind(root, "nets")[0], "net"):
        name = gen_cf.unq(gen_cf.sfind(net, "name")[0][1])
        for nd in gen_cf.sfind(net, "node"):
            nodes[(gen_cf.unq(gen_cf.sfind(nd, "ref")[0][1]), gen_cf.unq(gen_cf.sfind(nd, "pin")[0][1]))] = name
    return nodes, paths


def header_geometry(O):
    """the IDE header J2 of an option -> dict: axis box of the header body (x0, y0, x1, y1), the adapter zones.
    J2 = Connector_IDC:IDC-Header_2x20_P2.54mm_Vertical; origin = pad 1. rot 0: pins 1,3,..39 down the left column,
    2..40 in the right column 2.54 mm to the right; rot 90: pins run to the right (+x), even row above (-y)."""
    x, y, rot = O["place"]["J2"]
    L = 19 * G
    if rot % 180 == 0:
        sgn = 1 if rot == 0 else -1
        ax0, ax1 = sorted((y, y + sgn * L))
        cx = x + sgn * G / 2
        return dict(axis="y", c=cx, a0=ax0, a1=ax1)
    sgn = 1 if rot == 90 else -1
    ax0, ax1 = sorted((x, x + sgn * L))
    cy = y - sgn * G / 2
    return dict(axis="x", c=cy, a0=ax0, a1=ax1)


# the TAODAN CF-IDE40 plugged straight onto J2: its board (70 mm along the header axis, 63 mm tall) stands
# perpendicular to the card, its lower edge ~9-10 mm above the card surface, overhanging each end of the 50.8 mm pin
# row by ~10 mm. Below it, and beside the header on the side it faces (unknown until the adapter is in hand: both
# sides are kept low), nothing may be taller than ~8 mm.
TAODAN_LEN = 70.0
LOW_BEYOND = 12.0      # keep-low distance beyond each end of the pin row, along the axis (Ken: ~12 mm)
LOW_SIDE = 7.0         # keep-low half-width either side of the header centre line (shroud 4.45 + ~2.5 mm)
TALL = {"C30": "10 uF radial, ~11 mm", "LED1": "5 mm LED, ~8.6 mm", "PWR0": "5 mm LED, ~8.6 mm",
        "JP2": "pin header + shunt, ~8.5 mm", "J3": "power header + cable plug", "JP1": "pin header + shunt",
        "U$1": "3x8 header + jumpers, ~8.5 mm", "X1": "DIN 41612 connector"}


def adapter_zones(O):
    g = header_geometry(O)
    m = (g["a0"] + g["a1"]) / 2
    zone = (m - (g["a1"] - g["a0"]) / 2 - LOW_BEYOND, m + (g["a1"] - g["a0"]) / 2 + LOW_BEYOND)
    strip = (m - TAODAN_LEN / 2, m + TAODAN_LEN / 2)
    if g["axis"] == "y":
        keep = (g["c"] - LOW_SIDE, zone[0], g["c"] + LOW_SIDE, zone[1])
        taodan = (g["c"] - 4.0, strip[0], g["c"] + 4.0, strip[1])
    else:
        keep = (zone[0], g["c"] - LOW_SIDE, zone[1], g["c"] + LOW_SIDE)
        taodan = (strip[0], g["c"] - 4.0, strip[1], g["c"] + 4.0)
    return g, keep, taodan


def dead_copper(b, refs):
    """uuids of the v1.3 tracks/vias in copper pieces that touch fewer than two pads of the footprints in refs.
    The tree's Eagle board (and so ../v1.3) is an earlier save than the fabricated card: with IC26-IC29 where the
    fabricated card has them, its DATA8 and DATA12-15 runs along the bottom edge (routed for an earlier TMP placement)
    reach X1 only. They are dead copper; build_board drops them before anything is placed."""
    import pcbnew
    T = pcbnew.ToMM
    par = {}

    def f(a):
        while par.setdefault(a, a) != a:
            par[a] = par.get(par[a], par[a])
            a = par[a]
        return a

    def u(a, c):
        par[f(a)] = f(c)

    segs, vias = [], []
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            vias.append(t)
        else:
            segs.append(t)
    S = [(t.m_Uuid.AsString(), t.GetLayer(), T(t.GetStart().x), T(t.GetStart().y), T(t.GetEnd().x), T(t.GetEnd().y),
          T(t.GetWidth())) for t in segs]
    for sid, ly, x0, y0, x1, y1, w in S:
        u(("s", sid), ("p", ly, round(x0, 3), round(y0, 3)))
        u(("s", sid), ("p", ly, round(x1, 3), round(y1, 3)))

    def on(px, py, s, tol):
        sid, ly, x0, y0, x1, y1, w = s
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        k = 0 if L2 == 0 else max(0, min(1, ((px - x0) * dx + (py - y0) * dy) / L2))
        return (x0 + k * dx - px) ** 2 + (y0 + k * dy - py) ** 2 <= tol * tol

    # T-junctions: an end on another segment of the same layer
    for s in S:
        for (px, py) in ((s[2], s[3]), (s[4], s[5])):
            for o in S:
                if o is not s and o[1] == s[1] and on(px, py, o, o[6] / 2):
                    u(("s", s[0]), ("s", o[0]))
    # vias join every layer at their position
    for v in vias:
        vx, vy, r = T(v.GetPosition().x), T(v.GetPosition().y), T(v.GetWidth(pcbnew.F_Cu)) / 2
        u(("v", v.m_Uuid.AsString()), ("v", v.m_Uuid.AsString()))
        for s in S:
            if on(vx, vy, s, r + s[6] / 2):
                u(("v", v.m_Uuid.AsString()), ("s", s[0]))
    # pads (through-hole: every layer)
    pads = collections.defaultdict(set)
    for fp in b.GetFootprints():
        if fp.GetReference() not in refs:
            continue
        for p in fp.Pads():
            for s in S:
                if p.HitTest(pcbnew.VECTOR2I(pcbnew.FromMM(s[2]), pcbnew.FromMM(s[3]))) or \
                        p.HitTest(pcbnew.VECTOR2I(pcbnew.FromMM(s[4]), pcbnew.FromMM(s[5]))):
                    pads[f(("s", s[0]))].add((fp.GetReference(), p.GetNumber()))
            for v in vias:
                if p.HitTest(v.GetPosition()):
                    pads[f(("v", v.m_Uuid.AsString()))].add((fp.GetReference(), p.GetNumber()))
    dead, length = set(), 0.0
    for s in S:
        if len(pads.get(f(("s", s[0])), ())) < 2:
            dead.add(s[0])
            length += ((s[4] - s[2]) ** 2 + (s[5] - s[3]) ** 2) ** 0.5
    for v in vias:
        if len(pads.get(f(("v", v.m_Uuid.AsString())), ())) < 2:
            dead.add(v.m_Uuid.AsString())
    return dead, length


def build_board(opt, netfile, out=None):
    import pcbnew
    from pcbnew import VECTOR2I
    import placements
    base = opt == "base"                    # v1.3 + the fabricated positions only: the reference for the options
    O = placements.OPTIONS[opt] if not base else dict(moves={}, place={}, silk=[], text_moves={}, title="")
    FM = pcbnew.FromMM
    P = lambda x, y: VECTOR2I(FM(x), FM(y))
    nodes, paths = read_netlist(netfile)

    src = open(os.path.join(V13, OLD + ".kicad_pcb")).read()
    assert src.count('"%s"' % TITLE_OLD) == 1
    src = src.replace('"%s"' % TITLE_OLD, '"%s"' % TITLE_NEW)
    out = out or os.path.join(HERE, "%s-option-%s.kicad_pcb" % (PROJ, opt))
    open(out, "w").write(src)
    b = pcbnew.LoadBoard(out)

    fps = {f.GetReference(): f for f in b.GetFootprints()}
    # v1.3 net -> v2.0 net, through the pads (a v1.3 net keeps its pads, so this is a function)
    ren = {}
    for ref, f in fps.items():
        for p in f.Pads():
            if p.GetNumber() == "":
                continue
            old, new = p.GetNetname(), nodes.get((ref, p.GetNumber()))
            if new is None:
                if old:
                    raise SystemExit("board: %s.%s is on %s but has no pin in the schematic" % (ref, p.GetNumber(), old))
                continue
            if old and not new.startswith("unconnected-("):
                if ren.setdefault(old, new) != new:
                    raise SystemExit("board: v1.3 net %s maps to %s and %s" % (old, ren[old], new))

    nets = {}

    def net(name):
        if name not in nets:
            ni = b.FindNet(name)
            if ni is None:
                ni = pcbnew.NETINFO_ITEM(b, name)
                b.Add(ni)
            nets[name] = ni
        return nets[name]

    # CF footprints
    for ref, (value, symid, fpid, note) in (NL.PARTS.items() if not base else ()):
        lib, name = fpid.split(":")
        fp = pcbnew.FootprintLoad(os.path.join(KFP, lib + ".pretty"), name)
        if fp is None:
            raise SystemExit("board: footprint %s not found" % fpid)
        fp.SetFPIDAsString(fpid)
        fp.SetReference(ref)
        fp.SetValue(value)
        fp.SetField("Description", note)                # as the schematic symbol (DRC schematic parity)
        b.Add(fp)
        fps[ref] = fp
    for ref, fp in fps.items():
        if ref not in paths:
            raise SystemExit("board: %s is not in the schematic" % ref)
        pth = "/" + "/".join(x for x in paths[ref].split("/") if x and x != ROOT_UUID)
        fp.SetPath(pcbnew.KIID_PATH(pth))
    # every pad on its schematic net
    for ref, fp in fps.items():
        for p in fp.Pads():
            if p.GetNumber() == "" or (ref, p.GetNumber()) not in nodes:
                continue
            p.SetNet(net(nodes[(ref, p.GetNumber())]))
    tracks = list(b.GetTracks())
    for t in tracks:
        o = t.GetNetname()
        if o in ren:
            t.SetNet(net(ren[o]))
        elif o:
            raise SystemExit("board: track on net %s, which no pad carries" % o)
    for z in b.Zones():
        if z.GetNetname() and z.GetNetname() in ren:
            z.SetNet(net(ren[z.GetNetname()]))

    # moves of v1.3 parts: remember the old pad positions, drop the copper that ended on them
    moved_pads = []
    moves = dict(placements.FAB_MOVES)
    moves.update(O["moves"])
    for ref, mv in moves.items():
        fp = fps[ref]
        for p in fp.Pads():
            moved_pads.append((p.GetPosition().x, p.GetPosition().y))
        pos = fp.GetPosition()
        dx, dy = mv[0], mv[1]
        if ref in placements.FAB_MOVES and ref in O["moves"]:     # an option's move is relative to the fab spot
            dx, dy = placements.FAB_MOVES[ref][0] + O["moves"][ref][0], placements.FAB_MOVES[ref][1] + O["moves"][ref][1]
        fp.SetPosition(VECTOR2I(pos.x + FM(dx), pos.y + FM(dy)))
        if len(mv) > 2:
            fp.SetOrientationDegrees(mv[2])
    for ref, (x, y, rot) in O["place"].items():
        fp = fps[ref]
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(P(x, y))
    missing = [r for r in NL.PARTS if r not in O["place"]]
    if missing and not base:
        raise SystemExit("option %s: CF parts not placed: %s" % (opt, missing))
    # reference texts of the CF parts: on or next to the body, clear of the v1.3 caps beside the slots
    def ref_at(ref, dx, dy, size, angle):
        fp = fps[ref]
        fld = fp.Reference()
        o = fp.GetPosition()
        fld.SetTextSize(VECTOR2I(FM(size), FM(size)))
        fld.SetTextThickness(FM(max(0.12, size * 0.15)))
        fld.SetTextAngleDegrees(angle)
        fld.SetPosition(VECTOR2I(o.x + FM(dx), o.y + FM(dy)))

    for ref, (x, y, rot) in O["place"].items():
        n = len(fps[ref].Pads())
        vert = rot % 180 == 90
        if ref.startswith("IC"):                           # DIP at rotation 90: body centre, horizontal
            ref_at(ref, (n // 2 - 1) * G / 2, -3.81, 1.27, 0)
        elif ref.startswith("RN"):                         # SIP: beside the row of pads
            ref_at(ref, *((-2.4, -4 * G, 1.0, 90) if vert else (4 * G, -2.4, 1.0, 0)))
        elif ref.startswith("R"):                          # axial 10.16 mm: on the body
            ref_at(ref, *((0, -5.08, 0.8, 90) if vert else (5.08, 0, 0.8, 0)))
        elif ref.startswith("C") and ref != "C30":         # 5 mm disc: on the body
            ref_at(ref, *((0, -2.5, 0.8, 90) if vert else (2.5, 0, 0.8, 0)))
        elif ref == "C30":
            ref_at(ref, 1.0, 0, 0.8, 0)
    tol = FM(0.05)
    kill = set()
    for t in tracks:
        ends = [t.GetStart(), t.GetEnd()] if t.Type() != pcbnew.PCB_VIA_T else [t.GetPosition()]
        for e in ends:
            if any(abs(e.x - px) < tol and abs(e.y - py) < tol for px, py in moved_pads):
                kill.add(t.m_Uuid.AsString())
    dead, dlen = dead_copper(b, {r for r in fps if r not in NL.PARTS})
    kill |= dead
    # texts moved (the board title etc.)
    for d in b.GetDrawings():
        if d.GetClass() == "PCB_TEXT" and d.GetText() in O.get("text_moves", {}):
            x, y = O["text_moves"][d.GetText()]
            d.SetPosition(P(x, y))

    # --- silkscreen / user layers -----------------------------------------------------------------------------------
    def text(s, x, y, size=1.0, angle=0, layer=pcbnew.F_SilkS, just=pcbnew.GR_TEXT_H_ALIGN_LEFT):
        t = pcbnew.PCB_TEXT(b)
        t.SetText(s)
        t.SetLayer(layer)
        t.SetTextSize(VECTOR2I(FM(size), FM(size)))
        t.SetTextThickness(FM(max(0.15, size * 0.15)))
        t.SetHorizJustify(just)
        t.SetTextAngleDegrees(angle)
        t.SetPosition(P(x, y))
        b.Add(t)

    def rect(x0, y0, x1, y1, layer, dash=False, w=0.2):
        for (a, c, d, e) in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
            s = pcbnew.PCB_SHAPE(b)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(P(a, c))
            s.SetEnd(P(d, e))
            s.SetLayer(layer)
            s.SetWidth(FM(0.301 if dash else w))        # 0.301 = marker: made dashed at the text level below
            b.Add(s)

    for s, x, y, size, angle in O.get("silk", []):
        text(s, x, y, size, angle)
    if base:
        return finish(b, out, kill, "base: v1.3 + fabricated positions, %d dead copper items (%.0f mm) and %d on moved "
                      "pads removed" % (len(dead), dlen, len(kill - dead)))
    g, keep, taodan = adapter_zones(O)
    rect(*keep, pcbnew.Dwgs_User, dash=True)
    rect(*taodan, pcbnew.Dwgs_User, w=0.3)
    # the legend, in the free strip between the RAMs and the cap column (x 146-154)
    for s, x in (("Solid: TAODAN CF-IDE40 on J2 (70 mm, standing up, lower edge ~9-10 mm above the card)", 149.4),
                 ("Dashed: keep-low zone, nothing over ~8 mm (12 mm past each end of J2, both sides)", 151.4)):
        text(s, x, 68.0, 1.0, 90, pcbnew.Dwgs_User, pcbnew.GR_TEXT_H_ALIGN_CENTER)
    x0, y0, x1, y1 = placements.IC15_SPOT
    rect(x0, y0, x1, y1, pcbnew.Cmts_User, dash=True)
    for i, s in enumerate(("reserved: IC15 74ALS11", "fabricated card only,", "not in the v1.3 schematic")):
        text(s, x0 + 1.0, y0 + 2.2 + 2.2 * i, 0.9, 0, pcbnew.Cmts_User)
    text("Option %s: %s" % (opt.upper(), O["title"]), 20.0, 7.0, 1.5, 0, pcbnew.Dwgs_User)
    finish(b, out, kill, "option %s: %d footprints, %d CF parts placed, %d v1.3 parts moved, %d dead v1.3 copper "
           "items (%.0f mm) and %d on moved pads removed" % (opt, len(fps), len(O["place"]), len(moves), len(dead),
                                                             dlen, len(kill - dead)))


def finish(b, out, kill, msg):
    import pcbnew
    pcbnew.SaveBoard(out, b)
    # drop the killed copper at the text level (KiCad 10's SWIG containers misbehave after Remove())
    t = open(out).read()
    forms = gen_cf.top_forms(t)
    keepf = [f for f in forms if not (re.match(r"\((segment|via|arc)\b", f) and
                                      re.search(r'\(uuid "([^"]+)"\)', f).group(1) in kill)]
    keepf = [re.sub(r"\(width 0\.301\)(\s*)\(type (?:solid|default)\)", r"(width 0.3)\1(type dash)", f)
             if f.startswith("(gr_line") else f for f in keepf]            # pcbnew's Python has no line-style setter
    assert t.startswith("(kicad_pcb")
    open(out, "w").write("(kicad_pcb\n\t" + "\n\t".join(keepf) + "\n)\n")
    print("board %s: %s" % (os.path.basename(out), msg))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# 3. after the board is written: trim broken v1.3 copper, check the placement, make the review images
KILL_TYPES = {"clearance", "shorting_items", "tracks_crossing", "hole_clearance", "copper_edge_clearance",
              "track_dangling", "via_dangling", "items_not_allowed", "hole_to_hole", "solder_mask_bridge"}


def drc_json(pcb, out, refill=False):
    subprocess.run([CLI, "pcb", "drc", "--severity-all", "--format", "json", "-o", out, pcb]
                   + (["--refill-zones"] if refill else []), capture_output=True, text=True)
    return json.load(open(out))


def trim(pcb, baseline):
    """delete the v1.3 track segments / vias that a move or a new part broke: any track or via DRC names in a
    clearance / short / crossing / dangling / keepout violation that the v1.3 board does not already have; repeat
    until none is left (a dangling chain is eaten back to its junction or pad)"""
    base = drc_json(baseline, pcb + ".base.json")
    os.remove(pcb + ".base.json")
    seen = {(v["type"], tuple(sorted(i.get("uuid", "") for i in v["items"]))) for v in base["violations"]}
    total = 0
    it = 0
    for it in range(40):
        d = drc_json(pcb, pcb + ".drc.json")
        kill = set()
        for v in d["violations"]:
            if v["type"] not in KILL_TYPES:
                continue
            if (v["type"], tuple(sorted(i.get("uuid", "") for i in v["items"]))) in seen:
                continue                                  # already on v1.3 (its 17 dangling Eagle stubs)
            for i in v["items"]:
                if re.match(r"(Track|Via|Arc)\b", i["description"]):
                    kill.add(i["uuid"])
        if not kill:
            break
        t = open(pcb).read()
        forms = gen_cf.top_forms(t)
        keep = [f for f in forms if not (re.match(r"\((segment|via|arc)\b", f) and
                                         re.search(r'\(uuid "([^"]+)"\)', f).group(1) in kill)]
        total += len(forms) - len(keep)
        open(pcb, "w").write("(kicad_pcb\n\t" + "\n\t".join(keep) + "\n)\n")
    os.remove(pcb + ".drc.json")
    n = sum(1 for f in gen_cf.top_forms(open(pcb).read()) if re.match(r"\((segment|via|arc)\b", f))
    print("trim %s: %d more v1.3 copper items removed in %d DRC passes; %d kept" % (os.path.basename(pcb), total, it, n))


def refill(pcb):
    """refill the GND (In1) / VCC (In2) planes so the new pads get their plane connections, and save"""
    subprocess.run([CLI, "pcb", "drc", "--refill-zones", "--save-board", "-o", pcb + ".tmp.rpt", pcb],
                   capture_output=True, text=True)
    if os.path.exists(pcb + ".tmp.rpt"):
        os.remove(pcb + ".tmp.rpt")


def body_boxes(b):
    """ref -> (x0, y0, x1, y1) mm: the courtyard of a KiCad library footprint; for the Eagle (v1.3) footprints, which
    have none, the pads plus the silkscreen/fab graphics without texts"""
    import pcbnew
    T = pcbnew.ToMM
    out = {}
    for f in b.GetFootprints():
        if hasattr(f, "BuildCourtyardCaches"):
            f.BuildCourtyardCaches()
        cy = f.GetCourtyard(pcbnew.F_CrtYd)
        boxes = []
        if cy.OutlineCount():
            boxes.append(cy.BBox())
        else:
            boxes += [p.GetBoundingBox() for p in f.Pads()]
            boxes += [g.GetBoundingBox() for g in f.GraphicalItems()
                      if g.GetClass() not in ("PCB_TEXT", "PCB_FIELD") and g.GetLayer() in (pcbnew.F_SilkS, pcbnew.F_Fab)]
        xs = [(T(q.GetX()), T(q.GetY()), T(q.GetRight()), T(q.GetBottom())) for q in boxes]
        out[f.GetReference()] = (min(q[0] for q in xs), min(q[1] for q in xs), max(q[2] for q in xs), max(q[3] for q in xs))
    return out


def overlap(A, C, m=0.05):
    ox = min(A[2], C[2]) - max(A[0], C[0])
    oy = min(A[3], C[3]) - max(A[1], C[1])
    return (ox, oy) if ox > m and oy > m else None


def check_placement(pcb, opt):
    import pcbnew
    import placements
    O = placements.OPTIONS[opt]
    b = pcbnew.LoadBoard(pcb)
    boxes = body_boxes(b)
    changed = set(placements.FAB_MOVES) | set(O["moves"]) | set(O["place"])
    probs = []
    refs = sorted(boxes)
    for i, a in enumerate(refs):
        for c in refs[i + 1:]:
            if a not in changed and c not in changed:
                continue                                  # two unmoved v1.3 parts: as built
            o = overlap(boxes[a], boxes[c])
            if o:
                probs.append("%s / %s overlap %.2f x %.2f mm" % (a, c, o[0], o[1]))
    # pads against the board edge (0.5 mm), bodies inside the outline
    E = b.GetBoardEdgesBoundingBox()
    T = pcbnew.ToMM
    ex0, ey0, ex1, ey1 = T(E.GetX()), T(E.GetY()), T(E.GetRight()), T(E.GetBottom())
    for f in b.GetFootprints():
        ref = f.GetReference()
        if ref not in changed:
            continue
        for p in f.Pads():
            pb = p.GetBoundingBox()
            x0, y0, x1, y1 = T(pb.GetX()), T(pb.GetY()), T(pb.GetRight()), T(pb.GetBottom())
            if min(x0 - ex0, y0 - ey0, ex1 - x1, ey1 - y1) < 0.5:
                probs.append("%s pad %s within 0.5 mm of the board edge" % (ref, p.GetNumber()))
        bx = boxes[ref]
        if bx[0] < ex0 or bx[1] < ey0 or bx[2] > ex1 or bx[3] > ey1:
            probs.append("%s body outside the board outline" % ref)
    # the fabricated card's IC15 spot stays free
    for ref, bx in boxes.items():
        if overlap(bx, placements.IC15_SPOT):
            probs.append("%s is in the reserved IC15 spot" % ref)
    # the TAODAN keep-low zone: no tall part in it (J2 itself excepted)
    g, keep, taodan = adapter_zones(O)
    under = sorted(r for r, bx in boxes.items() if r != "J2" and overlap(bx, keep))
    for r in under:
        if r in TALL:
            probs.append("%s (%s) in the TAODAN keep-low zone" % (r, TALL[r]))
    tall_near = []
    for r in TALL:
        if r in boxes and r != "J2":
            bx = boxes[r]
            dx = max(keep[0] - bx[2], bx[0] - keep[2], 0)
            dy = max(keep[1] - bx[3], bx[1] - keep[3], 0)
            tall_near.append((round((dx * dx + dy * dy) ** 0.5, 1), r))
    # distance of the header from the nearest board edge (the ribbon / adapter side)
    h = boxes["J2"]
    edge = min((h[0] - ex0, "x=%.1f edge" % ex0), (ex1 - h[2], "x=%.1f edge" % ex1), (h[1] - ey0, "y=%.1f edge" % ey0),
               (ey1 - h[3], "y=%.1f edge" % ey1))
    print("placement %s: %s" % (os.path.basename(pcb), "OK - no new overlaps, pads clear of the edge, IC15 spot free, "
                                "TAODAN keep-low zone clear of tall parts" if not probs else "%d problem(s)" % len(probs)))
    for x in probs:
        print("    ", x)
    print("    J2 courtyard %.1f mm from the %s; keep-low zone x %.1f-%.1f, y %.1f-%.1f holds: %s"
          % (edge[0], edge[1], keep[0], keep[2], keep[1], keep[3], ", ".join(under) or "nothing"))
    print("    nearest tall parts to the keep-low zone: %s" % ", ".join("%s %.1f mm" % (r, d) for d, r in sorted(tall_near)[:3]))
    return not probs


def airwire_stats(pcb, drcfile):
    """CF-section ratsnest: count and total length of the unconnected items that touch a CF part"""
    d = json.load(open(drcfile))
    n, tot, cf = 0, 0.0, 0.0
    cfrefs = set(NL.PARTS)
    for u in d.get("unconnected_items", []):
        its = u["items"]
        if len(its) != 2:
            continue
        L = ((its[0]["pos"]["x"] - its[1]["pos"]["x"]) ** 2 + (its[0]["pos"]["y"] - its[1]["pos"]["y"]) ** 2) ** 0.5
        n += 1
        tot += L
        if any(re.search(r" of (%s)\b" % "|".join(map(re.escape, cfrefs)), i["description"]) for i in its):
            cf += L
    return n, tot, cf


def review_copy(pcb, out, what):
    """a copy of the board for the review images only: the adapter zones (User.Drawings) and the IC15 spot
    (User.Comments) duplicated onto the front silkscreen so the 3D render shows them ('render'), or the ratsnest (from
    DRC's unconnected items) drawn on User.Eco1 ('plot')"""
    import pcbnew
    b = pcbnew.LoadBoard(pcb)
    FM = pcbnew.FromMM
    if what == "render":
        for d in list(b.GetDrawings()):
            if d.GetLayer() in (pcbnew.Dwgs_User, pcbnew.Cmts_User) and d.GetClass() in ("PCB_SHAPE", "PCB_TEXT"):
                c = d.Duplicate()
                c.SetLayer(pcbnew.F_SilkS)
                b.Add(c)
    else:
        d = drc_json(pcb, out + ".json")
        os.remove(out + ".json")
        for u in d.get("unconnected_items", []):
            its = u["items"]
            if len(its) != 2:
                continue
            s = pcbnew.PCB_SHAPE(b)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(pcbnew.VECTOR2I(FM(its[0]["pos"]["x"]), FM(its[0]["pos"]["y"])))
            s.SetEnd(pcbnew.VECTOR2I(FM(its[1]["pos"]["x"]), FM(its[1]["pos"]["y"])))
            s.SetLayer(pcbnew.Eco1_User)
            s.SetWidth(FM(0.12))
            b.Add(s)
        print("ratsnest: %d airwires" % len(d.get("unconnected_items", [])))
    pcbnew.SaveBoard(out, b)


if __name__ == "__main__":
    if sys.argv[1] == "sch":
        main_sch()
    elif sys.argv[1] == "board":
        build_board(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    elif sys.argv[1] == "trim":
        trim(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "refill":
        refill(sys.argv[2])
    elif sys.argv[1] == "check":
        ok = check_placement(sys.argv[2], sys.argv[3])
        sys.stdout.flush()
        os._exit(0 if ok else 1)
    elif sys.argv[1] == "review":
        review_copy(sys.argv[2], sys.argv[3], sys.argv[4])
    sys.stdout.flush()
    os._exit(0)
