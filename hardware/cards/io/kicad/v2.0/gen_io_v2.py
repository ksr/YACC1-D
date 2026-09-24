#!/usr/bin/env python3
"""gen_io_v2.py - write the KiCad schematic and the placement-option boards of the YACC1 I/O card v2.0 (2026-09-23).

Run with KiCad's bundled Python (the board half needs pcbnew); build.sh does that:

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 gen_io_v2.py sch
    ... gen_io_v2.py board a <net>  (one placement option -> options/io-v2.0-option-a.kicad_pcb; placements.py)

v2.0 = the I/O card v1.1 + the CompactFlash section (io_v2_netlist.py says exactly what that is). This script:

  sch    copies the v1.1 schematic (../v1.1, 6 sheets converted from Eagle) unchanged except for
           - project/sheet-file names io-v1.1 -> io-v2.0 and the title blocks,
           - sheet 5: the -IO-SEL4 / -IO-SEL5 labels become global labels (sheet 7 uses those nets) and a note at the
             IO-ADDR-HL strap (P0-P7 only; CF on P4/P5),
         adds sheet 7 = the CF section, drawn with the CF card's own sheet writer (hardware/cards/cf/kicad/v1.0/gen_cf.py,
         class Sheet: KiCad standard symbols, short wire stubs to labels / power symbols, no-connect flags) from
         io_v2_netlist.py; nets shared with v1.1 are boxed global labels, as on the converted v1.1 sheets;
         copies the v1.1 symbol + footprint libraries (nickname io-v1.1-eagle kept, so nothing is re-linked).
  board  starts from the v1.1 board (same outline, X1 at the same place: it plugs into the same backplane), keeps every
         v1.1 footprint and its copper, adds the CF footprints (KiCad standard libraries, as on the CF card v1.0),
         puts EVERY pad on the net the v2.0 schematic gives it (names from a netlist export of the schematic), renames
         the v1.1 tracks to the same names, applies the option's moves and placements (placements.py), deletes the v1.1
         track segments/vias that sat on a pad that moved, adds silkscreen notes and the CF-to-IDE adapter outline
         (User.Drawings, dashed). build.sh then trims the v1.1 copper the moves broke (tools: kicad-cli DRC) - the
         CF section itself is NOT routed: ratsnest only. Option B was chosen (2026-09-23); route_v2.py turns it into
         the routed board io-v2.0.kicad_pcb, and the option boards in options/ are the review record.
"""
import os, sys, re, json, shutil, subprocess, collections, math

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", ".."))
V11 = os.path.join(HERE, "..", "v1.1")
sys.path.insert(0, HERE)
import io_v2_netlist as NL                                 # noqa: E402  (puts the CF card folder on sys.path)
import gen_cf                                              # noqa: E402  the CF card v1.0's sheet writer (read-only reuse)

PROJ = "io-v2.0"
OLD = "io-v1.1"
CLI = gen_cf.CLI
KFP = gen_cf.KFP
G = 2.54
ROOT_UUID = "2f58bdc4-1582-e328-aca7-6011ff713d0f"        # the v1.1 root sheet's UUID, kept (footprint paths stay valid)
SHEET7 = gen_cf.U("io-v2.0", "sheet7", "instance")
SHEET7_FILE_UUID = gen_cf.U("io-v2.0", "sheet7", "file")


def gx(n):
    return n * G


# ---------------------------------------------------------------------------------------------------------------------
# 1. schematic
def copy_libs():
    shutil.copy(os.path.join(V11, OLD + "-eagle.kicad_sym"), os.path.join(HERE, OLD + "-eagle.kicad_sym"))
    dst = os.path.join(HERE, OLD + "-eagle.pretty")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(os.path.join(V11, OLD + "-eagle.pretty"), dst)
    for t in ("sym-lib-table", "fp-lib-table"):
        shutil.copy(os.path.join(V11, t), os.path.join(HERE, t))


def global_label(net, x, y, ang, uid):
    just = {0: "left", 180: "right", 90: "left", 270: "right"}[ang]
    return ('\t(global_label %s (shape passive) (at %s %s %d) (fields_autoplaced yes) (effects (font (size 1.27 1.27)) '
            '(justify %s)) (uuid "%s")\n\t\t(property "Intersheetrefs" "${INTERSHEET_REFS}" (at %s %s 0) '
            '(effects (font (size 1.27 1.27)) (hide yes)))\n\t)' % (gen_cf.q(net), gen_cf.f(x), gen_cf.f(y), ang, just,
                                                                   uid, gen_cf.f(x), gen_cf.f(y)))


def copy_v11_sheets():
    for n in range(1, 7):
        t = open(os.path.join(V11, "%s-sheet%d.kicad_sch" % (OLD, n))).read()
        t = t.replace('(project "%s"' % OLD, '(project "%s"' % PROJ)
        note = "Unchanged from v1.1 (converted from Eagle IO V1.1.sch sheet %d)" % n
        if n == 5:
            note = "v1.1 sheet 5 + -IO-SEL4/-IO-SEL5 made global (CF section, sheet 7) + strap note"
            cnt = 0
            for net in ("-IO-SEL4", "-IO-SEL5"):
                for m in list(re.finditer(r'\t\(label "%s" \(at ([\d.]+) ([\d.]+) (\d+)\).*?\(uuid "([^"]+)"\)\)'
                                          % re.escape(net), t)):
                    t = t.replace(m.group(0), global_label(net, float(m.group(1)), float(m.group(2)),
                                                           int(m.group(3)), m.group(4)))
                    cnt += 1
            assert cnt == 4, "sheet 5: expected 4 -IO-SEL4/5 labels, converted %d" % cnt
            txt = ("I/O card v2.0: the IO-ADDR-HL strap MUST decode P0-P7 (jumpers 3-5 and 4-6):\n"
                   "IC5 Y4 (-IO-SEL4) = P4 = CF register-select latch, Y5 (-IO-SEL5) = P5 = CF data (sheet 7).\n"
                   "The IO-ADDR and DATA-ADDR jumpers must not select P4 or P5 (pins 7-8, 5-6).")
            t = t.rstrip()
            assert t.endswith(")")
            t = t[:-1] + ('\t(text %s (exclude_from_sim no) (at 20.32 160.02 0) (effects (font (size 1.778 1.778) '
                          '(thickness 0.254) bold) (justify left top)) (uuid "%s"))\n)\n'
                          % (gen_cf.q(txt), gen_cf.U("io-v2.0", "sheet5-note")))
        t = re.sub(r'\(title_block \(title "%s sheet %d"\) \(comment 1 "[^"]*"\)\)' % (re.escape(OLD), n),
                   '(title_block (title "%s sheet %d") (date "%s") (rev "%s") (comment 1 %s))'
                   % (PROJ, n, NL.DATE, NL.REV, gen_cf.q(note)), t)
        open(os.path.join(HERE, "%s-sheet%d.kicad_sch" % (PROJ, n)), "w").write(t)


def write_root():
    t = open(os.path.join(V11, OLD + ".kicad_sch")).read()
    assert '(uuid "%s")' % ROOT_UUID in t
    t = t.replace('(project "%s"' % OLD, '(project "%s"' % PROJ)
    t = t.replace('"%s-sheet' % OLD, '"%s-sheet' % PROJ)
    t = t.replace('(title_block (title "%s") (comment 1 "Converted from Eagle schematic; see README.md"))' % OLD,
                  '(title_block (title "YACC1 I/O card v2.0") (date "%s") (rev "%s") (comment 1 %s) (comment 2 %s))'
                  % (NL.DATE, NL.REV, gen_cf.q("Sheets 1-6 = I/O card v1.1 (unchanged); sheet 7 = CompactFlash on "
                                                 "P4/P5 (from the CF card v1.0)"),
                     gen_cf.q("Circuit source: io_v2_netlist.py; generated by gen_io_v2.py; see README.md")))
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
    """gen_cf's sheet writer; nets shared with the v1.1 sheets get boxed global labels"""
    def label(self, x, y, net, d):
        if net not in NL.SHARED:
            return super().label(x, y, net, d)
        if (round(x, 3), round(y, 3), net) in self.labels:
            return
        self.labels.add((round(x, 3), round(y, 3), net))
        ang = {"R": 0, "L": 180, "U": 90, "D": 270}[d]
        self.out.append(global_label(net, x, y, ang, gen_cf.U("gl", x, y, net)))

    def write(self, path):
        head = ['(kicad_sch', '\t(version 20260306)', '\t(generator "gen_io_v2")', '\t(generator_version "1.0")',
                '\t(uuid "%s")' % SHEET7_FILE_UUID, '\t(paper "A3")',
                '\t(title_block (title "%s sheet 7: CompactFlash interface") (date "%s") (rev "%s") (company "YACC1")'
                % (PROJ, NL.DATE, NL.REV),
                '\t\t(comment 1 "CF (True IDE, 8-bit) on I/O ports P4 (register latch) / P5 (data) - docs/cards/cf.md")',
                '\t\t(comment 2 "From the CF card v1.0 minus its 74LS138, bus connector, PWR + DASP LEDs")',
                '\t\t(comment 3 "Circuit source: io_v2_netlist.py; this sheet is generated by gen_io_v2.py"))',
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
    S.pwr = 700                                           # #PWR701.. (the v1.1 sheets use #GNDn / #P+n)
    # --- strobe gating -----------------------------------------------------------------------------------------------
    S.box(gx(5), gx(5), gx(52), gx(44), "P4 / P5 STROBE GATING  (IC12 74LS32)")
    for u, y in ((1, 12), (2, 21), (3, 30), (4, 38)):
        S.part("IC12", u, gx(40), gx(y))
    S.text(gx(6), gx(10), "-IO-SEL4 = IC5 Y4 (sheet 5): port P4\n-IO-SEL5 = IC5 Y5 (sheet 5): port P5\n"
           "IC5 decodes P0-P7 only with the\nIO-ADDR-HL strap in P0-P7.\n\n"
           "gate 1: P4 latch clock\n  = -IO-SEL4 OR -IO-WR\ngate 2: CF -IOR\n  = -IO-SEL5 OR -IO-RD\n"
           "gate 3: CF -IOW\n  = -IO-SEL5 OR -IO-WR\ngate 4: unused", size=1.27)
    # --- latch + CF reset -------------------------------------------------------------------------------------------
    S.box(gx(5), gx(46), gx(52), gx(72), "P4 LATCH: DA0-2 + CF RESET  (IC13 74LS175)")
    S.part("IC13", 1, gx(18), gx(59))
    S.part("IC14", 2, gx(42), gx(55))
    S.text(gx(33), gx(60), "IC14 gate 2: -CFRESET =\n-RESET AND -SRST\n(bus reset or latch bit 3)", size=1.27)
    # --- data buffer + enables --------------------------------------------------------------------------------------
    S.box(gx(54), gx(5), gx(80), gx(65), "P5 DATA BUFFER  (IC15 74LS245)")
    S.part("IC15", 1, gx(66), gx(19))
    S.part("IC14", 1, gx(66), gx(37))
    S.part("IC14", 3, gx(66), gx(46))
    S.part("IC14", 4, gx(66), gx(54))
    S.text(gx(55), gx(60.5), "DIR = -IOR (low: CF -> bus)\n-CFOE = -IOR AND -IOW\nACTK sinks the ACT LED", size=1.27)
    # --- IDE header, pull-ups, adapter power ------------------------------------------------------------------------
    S.box(gx(82), gx(5), gx(110.5), gx(65), "IDE HEADER J2 (TO THE CF ADAPTER)")
    S.part("J2", 1, gx(92), gx(18), fields={"Reference": (-1.27, -27.94), "Value": (3.81, -27.94)}, pstub=G)
    S.part("RN3", 1, gx(92), gx(37))
    for i, r in enumerate(("R11", "R12", "R13", "R14")):
        S.part(r, 1, gx(86 + 3 * i), gx(50))
    S.part("JP2", 1, gx(105), gx(47))
    S.part("J3", 1, gx(105), gx(55))
    S.part("C22", 1, gx(107.5), gx(56))
    S.text(gx(83), gx(60.5), "CSEL = GND (master)\n-CS0 = GND, -CS1 = VCC", size=1.27)
    # --- ACT LED ------------------------------------------------------------------------------------------------------
    S.box(gx(112), gx(5), gx(135), gx(34), "ACT LED")
    S.part("R15", 1, gx(123), gx(12))
    S.part("LED1", 1, gx(123), gx(19), rot=90)
    S.text(gx(113), gx(29), "ACT: any P5 access\n(PWR LED: the card's PWR0;\nno DASP LED on v2.0)", size=1.27)
    # --- power + decoupling -------------------------------------------------------------------------------------------
    S.box(gx(112), gx(36), gx(160), gx(58), "POWER + DECOUPLING (one 100 nF per new IC)")
    for i, c in enumerate(("C18", "C19", "C20", "C21")):
        S.part(c, 1, gx(116 + 5 * i), gx(47))
    S.part("IC12", 5, gx(140), gx(47))
    S.part("IC14", 5, gx(149), gx(47))
    S.text(gx(113), gx(54.5), "C18 IC12, C19 IC13, C20 IC14, C21 IC15. PWR_FLAGs: sheet 1.", size=1.27)
    # --- notes -------------------------------------------------------------------------------------------------------
    S.box(gx(5), gx(75), gx(112), gx(108), "DESIGN NOTES (I/O CARD v2.0, CF SECTION)")
    S.text(gx(5.5), gx(78), "\n".join([
        "1. Two I/O ports on the I/O card's own decoder IC5 (sheet 5): P4 (write) = 74LS175 latch IC13 - bits 0-2 = the ATA",
        "   task-file register (CF DA0-2), bit 3 = CF reset (1 = held in reset); P5 (read/write) = the selected ATA register,",
        "   8-bit True IDE, through the 74LS245 IC15. The IO-ADDR-HL strap MUST decode P0-P7; the IO-ADDR / DATA-ADDR",
        "   jumpers must not select P4 or P5 (they would put the control latch or the UART/switch port on a CF port).",
        "2. IC12 (74LS32) ORs each port select with -IO-WR / -IO-RD, so -IOR, -IOW and the latch clock are low only during",
        "   the bus strobe for this port (the microcode sets IOADDR two steps before the strobe and holds it through it).",
        "3. -CS0 (J2 pin 37) is tied LOW and -CS1 (pin 38) HIGH: the strobes alone define every cycle (CF card v1.0 note 3,",
        "   docs/cards/cf.md section 4: gating -CS0 would break the chip-select hold time after -IOR).",
        "4. J2 = 40-pin IDE header, a short ribbon to a CF-to-IDE adapter mounted above the card on standoffs. Adapter power:",
        "   J3 (1 = +5 V, 2 and 3 = GND, 4 = +12 V, not used) or, with JP2 fitted, IDE pin 20 for adapters powered there.",
        "5. Pull-ups: CF D0-7 (RN3: an empty adapter reads $FF = 'no card' to the ROM driver), IORDY, -PDIAG, -DASP;",
        "   -DMACK held inactive; CSEL grounded (master). SRST (IC13 Q4) is a one-pin net by design (a probe point).",
        "6. From hardware/cards/cf/kicad/v1.0/cf_netlist.py: U2->IC12 U3->IC13 U4->IC14 U5->IC15 J1->J2 J2->J3 JP1->JP2",
        "   RN1->RN3 R1-R5->R11-R15 LED2->LED1 C2-C6->C18-C22. Dropped: U1 (74LS138: IC5 Y4/Y5 replace -P8SEL/-P9SEL), X1",
        "   (the card's bus connector), C1, the PWR LED (LED1, R7: the card has PWR0) and the DASP LED (LED3, R6).",
        "Theory: docs/cards/cf.md, docs/cards/io.md. Circuit source: io_v2_netlist.py (edit, then re-run build.sh)."]),
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
    pro = json.load(open(os.path.join(V11, OLD + ".kicad_pro")))
    pro["meta"]["filename"] = PROJ + ".kicad_pro"
    # net classes for routing the CF section (route_v2.py): Default = v1.1's rules (0.1524 mm track, 0.127 mm
    # clearance) with v1.1's via (0.508 / 0.254 mm, all 158 of its vias); Power = GND + VCC at 0.3048 mm, wider
    # than v1.1's 0.1524 mm power tracks
    cls = pro["net_settings"]["classes"]
    assert len(cls) == 1 and cls[0]["name"] == "Default"
    cls[0]["via_diameter"], cls[0]["via_drill"] = 0.508, 0.254
    pw = dict(cls[0], name="Power", track_width=0.3048, priority=0)
    cls.append(pw)
    pro["net_settings"]["netclass_patterns"] = [{"netclass": "Power", "pattern": n} for n in ("GND", "VCC")]
    json.dump(pro, open(os.path.join(HERE, PROJ + ".kicad_pro"), "w"), indent=2)
    return pro


def main_sch():
    probs = NL.check()
    if probs:
        raise SystemExit("io_v2_netlist.check() failed:\n" + "\n".join(probs))
    copy_libs()
    copy_v11_sheets()
    write_root()
    S = build_sheet7()
    write_project()
    print("schematic: %s.kicad_sch + sheets 1-6 (v1.1) + sheet 7 (CF: %d parts, %d power symbols)"
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


def build_board(opt, netfile, out=None):
    import pcbnew
    from pcbnew import VECTOR2I
    import placements
    O = placements.OPTIONS[opt]
    FM = pcbnew.FromMM
    P = lambda x, y: VECTOR2I(FM(x), FM(y))
    nodes, paths = read_netlist(netfile)

    src = open(os.path.join(V11, OLD + ".kicad_pcb")).read()
    assert src.count('"YACC1 IO V1.1"') == 1
    src = src.replace('"YACC1 IO V1.1"', '"YACC1 IO V2.0"')
    out = out or os.path.join(HERE, "options", "%s-option-%s.kicad_pcb" % (PROJ, opt))
    open(out, "w").write(src)
    b = pcbnew.LoadBoard(out)

    fps = {f.GetReference(): f for f in b.GetFootprints()}
    # v1.1 net -> v2.0 net, through the pads (a v1.1 net keeps its pads, so this is a function)
    ren = {}
    for ref, f in fps.items():
        for p in f.Pads():
            if p.GetNumber() == "":
                continue
            old, new = p.GetNetname(), nodes.get((ref, p.GetNumber()))
            if new is None:                                 # a footprint pad the symbol has no pin for (Y1 pin 1)
                if old:
                    raise SystemExit("board: %s.%s is on %s but has no pin in the schematic" % (ref, p.GetNumber(), old))
                continue
            if old and not new.startswith("unconnected-("):
                if ren.setdefault(old, new) != new:
                    raise SystemExit("board: v1.1 net %s maps to %s and %s" % (old, ren[old], new))

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
    for ref, (value, symid, fpid, note) in NL.PARTS.items():
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

    # moves of v1.1 parts: remember the old pad positions, drop the copper that ended on them
    moved_pads = []
    for ref, mv in O["moves"].items():
        fp = fps[ref]
        for p in fp.Pads():
            moved_pads.append((p.GetPosition().x, p.GetPosition().y))
        pos = fp.GetPosition()
        dx, dy = mv[0], mv[1]
        fp.SetPosition(VECTOR2I(pos.x + FM(dx), pos.y + FM(dy)))
        if len(mv) > 2:
            fp.SetOrientationDegrees(mv[2])
    for ref, (x, y, rot) in O["place"].items():
        fp = fps[ref]
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(P(x, y))
    missing = [r for r in NL.PARTS if r not in O["place"]]
    if missing:
        raise SystemExit("option %s: CF parts not placed: %s" % (opt, missing))
    tol = FM(0.05)
    kill = set()
    for t in tracks:
        ends = [t.GetStart(), t.GetEnd()] if t.Type() != pcbnew.PCB_VIA_T else [t.GetPosition()]
        for e in ends:
            if any(abs(e.x - px) < tol and abs(e.y - py) < tol for px, py in moved_pads):
                kill.add(t.m_Uuid.AsString())
    # texts moved (the board title etc.)
    for d in b.GetDrawings():
        if d.GetClass() == "PCB_TEXT" and d.GetText() in O.get("text_moves", {}):
            x, y = O["text_moves"][d.GetText()]
            d.SetPosition(P(x, y))

    # --- silkscreen / user layer ------------------------------------------------------------------------------------
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

    def line(x1, y1, x2, y2, layer, w=0.15, dash=False):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(x1, y1))
        s.SetEnd(P(x2, y2))
        s.SetLayer(layer)
        s.SetWidth(FM(0.301 if dash else w))           # 0.301 = marker: made dashed at the text level below
        b.Add(s)

    for s, x, y, size, angle in O.get("silk", []):
        text(s, x, y, size, angle)
    ax, ay, aw, ah, edge = O["adapter"]
    for (x1, y1, x2, y2) in ((ax, ay, ax + aw, ay), (ax + aw, ay, ax + aw, ay + ah), (ax + aw, ay + ah, ax, ay + ah),
                             (ax, ay + ah, ax, ay)):
        line(x1, y1, x2, y2, pcbnew.Dwgs_User, 0.3, dash=True)
    ex = {"top": (ax + 2, ay + 2.5), "bottom": (ax + 2, ay + ah - 1.5), "left": (ax + 1.5, ay + 3),
          "right": (ax + aw - 1.5, ay + 3)}[edge]
    text("CF-to-IDE adapter above the card, ~%dx%d mm (standoff holes TBD)" % (round(aw), round(ah)),
         ax + 1.5, ay + ah / 2, 1.2, 0, pcbnew.Dwgs_User)
    text("adapter IDE connector on this edge", ex[0], ex[1], 1.0, 90 if edge in ("left", "right") else 0,
         pcbnew.Dwgs_User, pcbnew.GR_TEXT_H_ALIGN_LEFT if edge != "right" else pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    text("Option %s: %s" % (opt.upper(), O["title"]), 20.0, 8.0, 1.5, 0, pcbnew.Dwgs_User)

    # reference text of the CF parts: plain, next to the part (KiCad library positions)
    pcbnew.SaveBoard(out, b)
    # drop the killed copper at the text level (KiCad 10's SWIG containers misbehave after Remove())
    t = open(out).read()
    forms = gen_cf.top_forms(t)
    keep = [f for f in forms if not (re.match(r"\((segment|via|arc)\b", f) and
                                     re.search(r'\(uuid "([^"]+)"\)', f).group(1) in kill)]
    keep = [re.sub(r"\(width 0\.301\)(\s*)\(type (?:solid|default)\)", r"(width 0.3)\1(type dash)", f)
            if f.startswith("(gr_line") else f for f in keep]            # pcbnew's Python has no line-style setter
    assert t.startswith("(kicad_pcb")
    open(out, "w").write("(kicad_pcb\n\t" + "\n\t".join(keep) + "\n)\n")
    print("board option %s: %s (%d footprints, %d CF parts placed, %d v1.1 parts moved, %d v1.1 copper items on "
          "moved pads removed)" % (opt, os.path.basename(out), len(fps), len(O["place"]), len(O["moves"]), len(kill)))


# ---------------------------------------------------------------------------------------------------------------------
# 3. after the board is written: trim broken v1.1 copper, check the placement, make the review images
KILL_TYPES = {"clearance", "shorting_items", "tracks_crossing", "hole_clearance", "copper_edge_clearance",
              "track_dangling", "via_dangling", "items_not_allowed", "hole_to_hole", "solder_mask_bridge"}


def drc_json(pcb, out):
    r = subprocess.run([CLI, "pcb", "drc", "--severity-all", "--format", "json", "-o", out, pcb],
                       capture_output=True, text=True)
    return json.load(open(out))


def trim(pcb, baseline):
    """delete the v1.1 track segments / vias that a move or a new part broke: any track or via DRC names in a
    clearance / short / crossing / dangling / keepout violation that the v1.1 board does not already have; repeat
    until none is left (a dangling chain is eaten back to its junction or pad)"""
    base = drc_json(baseline, pcb + ".base.json")
    os.remove(pcb + ".base.json")
    seen = {(v["type"], tuple(sorted(i.get("uuid", "") for i in v["items"]))) for v in base["violations"]}
    total = 0
    for it in range(40):
        d = drc_json(pcb, pcb + ".drc.json")
        kill = set()
        for v in d["violations"]:
            if v["type"] not in KILL_TYPES:
                continue
            if (v["type"], tuple(sorted(i.get("uuid", "") for i in v["items"]))) in seen:
                continue                                  # already on v1.1 (e.g. LCD pads in its own keepout)
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
    print("trim %s: %d more v1.1 copper items removed in %d DRC passes; %d kept" % (os.path.basename(pcb), total, it, n))


def body_boxes(b):
    """ref -> (x0, y0, x1, y1) mm: the courtyard of a KiCad library footprint; for the Eagle (v1.1) footprints, which
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


def check_placement(pcb, opt):
    import pcbnew
    import placements
    O = placements.OPTIONS[opt]
    b = pcbnew.LoadBoard(pcb)
    v11 = pcbnew.LoadBoard(os.path.join(V11, OLD + ".kicad_pcb"))
    boxes, base = body_boxes(b), body_boxes(v11)
    changed = set(O["moves"]) | set(O["place"])
    probs = []
    refs = sorted(boxes)
    for i, a in enumerate(refs):
        for c in refs[i + 1:]:
            if a not in changed and c not in changed:
                continue
            A, C = boxes[a], boxes[c]
            ox = min(A[2], C[2]) - max(A[0], C[0])
            oy = min(A[3], C[3]) - max(A[1], C[1])
            if ox > 0.05 and oy > 0.05:
                # a pair that already overlapped on v1.1 by as much is not new
                if a in base and c in base:
                    B1, B2 = base[a], base[c]
                    bx = min(B1[2], B2[2]) - max(B1[0], B2[0])
                    by = min(B1[3], B2[3]) - max(B1[1], B2[1])
                    if bx > 0 and by > 0 and a not in changed and c not in changed:
                        continue
                probs.append("%s / %s overlap %.2f x %.2f mm" % (a, c, ox, oy))
    # pads against the board edge (0.5 mm) and the LCD keepout
    E = b.GetBoardEdgesBoundingBox()
    T = pcbnew.ToMM
    ex0, ey0, ex1, ey1 = T(E.GetX()), T(E.GetY()), T(E.GetRight()), T(E.GetBottom())
    for f in b.GetFootprints():
        if f.GetReference() not in changed:
            continue
        for p in f.Pads():
            pb = p.GetBoundingBox()
            x0, y0, x1, y1 = T(pb.GetX()), T(pb.GetY()), T(pb.GetRight()), T(pb.GetBottom())
            if min(x0 - ex0, y0 - ey0, ex1 - x1, ey1 - y1) < 0.5:
                probs.append("%s pad %s within 0.5 mm of the board edge" % (f.GetReference(), p.GetNumber()))
            if 131.97 < x1 and x0 < 167.68 and 13.43 < y1 and y0 < 93.59:
                probs.append("%s pad %s under the LCD (keepout)" % (f.GetReference(), p.GetNumber()))
    ax, ay, aw, ah, edge = O["adapter"]
    under = sorted(r for r, bx in boxes.items() if bx[0] < ax + aw and ax < bx[2] and bx[1] < ay + ah and ay < bx[3])
    print("placement %s: %s" % (os.path.basename(pcb), "OK - no new overlaps, pads clear of edge and LCD keepout"
                                if not probs else "%d problem(s)" % len(probs)))
    for x in probs:
        print("    ", x)
    print("    under the adapter outline: %s" % ", ".join(under))
    return not probs


def review_copy(pcb, out, what):
    """a copy of the board for the review images only: the adapter outline (User.Drawings) duplicated onto the front
    silkscreen so the 3D render shows it ('render'), or the ratsnest (from DRC's unconnected items) drawn on User.Eco1
    ('plot')"""
    import pcbnew
    b = pcbnew.LoadBoard(pcb)
    FM = pcbnew.FromMM
    if what == "render":
        for d in list(b.GetDrawings()):
            if d.GetLayer() == pcbnew.Dwgs_User and d.GetClass() in ("PCB_SHAPE", "PCB_TEXT"):
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
    elif sys.argv[1] == "check":
        ok = check_placement(sys.argv[2], sys.argv[3])
        sys.stdout.flush()
        os._exit(0 if ok else 1)
    elif sys.argv[1] == "review":
        review_copy(sys.argv[2], sys.argv[3], sys.argv[4])
    sys.stdout.flush()
    os._exit(0)
