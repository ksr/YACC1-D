# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""The video card V1.0 at gate level: its revisions (the card as fitted and the variants without each rework), the
bus-path decode evaluated from the netlist for every combination of the bus inputs it reaches, and the C header
y1ucemu -G uses (2026-10-11).

The card (docs/cards/video.md): a 74S85 (IC18) compares ADDR12-15 with jumpers SV3 while -VMA is asserted
(BOARDSEL); ADDR11 low = the IDT7134's bus port (IC15, -CER = NAND(BOARDSEL, /ADDR11)), ADDR11 high = the 6845 (IC17,
-CS = NAND(BOARDSEL, ADDR11 AND /A0)) at even addresses and the JP1 read-back latch (IC2, a 74LS373 enabled by
BOARDSEL AND ADDR11 AND ADDR0, inverted by a 7416) at odd ones; the 6845's E is -MEM-RD XOR -MEM-WR through the R1/C1
one-shot. No bus buffer: the RAM, the 6845 and the latch sit on DATA0..7 directly.

Revisions are data: the netlist, the board's own connections (netlist-compare.txt), the jumper settings, the fitted
sockets and the reworks, each with the document it comes from.
"""
import itertools, os
from .netlist import Netlist
from .logic import Circuit, DualPort, CRTC, BusLatch, X, ttl, mos

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
CARD = "hardware/cards/video/kicad/v1.0-fusion-export-2026-09-18/reports/"
NET = CARD + "netlist.net"
COMPARE = CARD + "netlist-compare.txt"

# the backplane pins (docs/system/BUS.md): the bus signals the card can see, and its power pins
BUS = {"ADDR%d" % i: ("X1", "A%d" % (3 + i)) for i in range(16)}
BUS.update({"DATA%d" % i: ("X1", "A%d" % (19 + i)) for i in range(8)})
BUS.update({"-MEM-RD": ("X1", "B23"), "-MEM-WR": ("X1", "B24"), "-VMA": ("X1", "C12"), "-RESET": ("X1", "C30")})
POWER_PINS = {("X1", "%s%d" % (row, n)) for row in "ABC" for n in (1, 2, 31, 32)}

FIX_DOC = "hardware/cards/video/docs/fix-6845-register-select.md"
SETTINGS = [("jumper", "SV3", "5", "SV3", "6", "SV3 5-6 fitted, the other pairs open: the block $D000 (docs/cards/video.md 3.1, "
                                              "hardware/cards/video/README.md)")]
REWORK_5V = [("short", "VCC", "+5V", "the +5V rail joined to VCC by a wire, 2026-09-21 (hardware/cards/video/README.md; "
                                     "docs/cards/video.md 3.7): the design left +5V with no connector pin")]
REWORK_RS = [("lift", "IC17", "24", "6845 pin 24 (RS) bent out of its socket (%s)" % FIX_DOC),
             ("wire", "IC17", "24", "IC15", "41", "pin 24 wired to IC15 pin 41 = ADDR1: RS = A1 (%s)" % FIX_DOC)]
WRONG_FIX = [("lift", "IC1", "13", "the fix the document warns against: IC1 pin 13 (/A0) lifted (%s, 'Don't do that')" % FIX_DOC),
             ("wire", "IC1", "13", "X1", "A2", "IC1 pin 13 tied high: the 6845 selected at odd addresses too")]
ALL = None                                                           # every socket filled
NO_6845 = {"IC1", "IC2", "IC15", "IC18", "IC19", "IC20", "IC21", "IC22", "IC23", "IC24", "IC25", "IC26", "IC27", "IC28"}

REVS = {
    "v1.0": dict(edits=REWORK_5V + REWORK_RS, fitted=ALL,
                 title="V1.0 as fitted: the +5V wire, the 6845 with RS on A1 (what the ROM's driver and videomodel.h assume)"),
    "v1.0-no6845": dict(edits=REWORK_5V, fitted=NO_6845,
                        title="V1.0 as in the machine today: the +5V wire, the 6845 socket empty (docs/system/MACHINE.md)"),
    "v1.0-no-rs": dict(edits=REWORK_5V, fitted=ALL,
                       title="v1.0 without the RS fix: the 6845 fitted as drawn, RS = A0, its data register unreachable"),
    "v1.0-no-5v": dict(edits=[], fitted=NO_6845,
                       title="v1.0-no6845 without the +5V wire: the card on the bench on 2026-09-18 (the write-through fault)"),
    "v1.0-drawn": dict(edits=[], fitted=ALL, title="V1.0 exactly as drawn, a 6845 fitted: neither rework"),
    "v1.0-a0fix": dict(edits=REWORK_5V + WRONG_FIX, fitted=ALL,
                       title="V1.0 with the wrong fix (/A0 tied high): the 6845 and the JP1 latch together at odd addresses"),
}
DEFAULT = "v1.0"
NAMES = {"IC15": "IC15 (display RAM)", "IC17": "IC17 (6845)", "IC2": "IC2 (JP1 latch)"}


class Card:
    def __init__(self, rev, root=ROOT):
        if rev not in REVS: raise ValueError("video card revision %r: one of %s" % (rev, ", ".join(REVS)))
        spec = REVS[rev]; self.rev = rev; self.title = spec["title"]
        self.nl = Netlist(os.path.join(root, NET))
        self.nl.board(os.path.join(root, COMPARE))
        self.nl.apply(SETTINGS + spec["edits"])
        self.c = Circuit(self.nl, BUS, POWER_PINS, spec["fitted"])
        self.dev = {d.kind: d for d in self.c.devices}
        for d in self.c.devices:                                     # the data pins: DATAn = bit n of each device
            for i, n in enumerate(d.data):
                if self.c.net_signal.get(n) != "DATA%d" % i:
                    raise ValueError("%s data bit %d on %s, not DATA%d: the generated model needs straight data lines" % (d.ref, i, n, i))

    # ------------------------------------------------------------------ one bus cycle -> what the card does
    def access(self, levels):
        """levels: {bus signal: 0/1}. -> dict(ram, crtc, rs, latch, lval, lfloat, events, undriven, sel)"""
        v, fights = self.c.cycle(levels)
        e = dict(ram="none", crtc="none", rs=0, latch=0, lval=0xFF, lfloat=0, events=[], undriven="", sel=[])
        ev = e["events"]
        ev += ["contention on the card: %s" % f for f in fights]
        read_cycle = levels.get("-MEM-RD") == 0 and levels.get("-MEM-WR") == 1 and levels.get("-VMA") == 0
        drivers = []
        d = self.dev.get("DPRAM")
        if d and d.fitted and self.c.powered(d.supply):
            ce, oe, rw = (mos(v.get(n)) for n in (d.ce, d.oe, d.rw))
            if ce != 1:
                e["sel"].append(d.ref)
                op = "write" if rw == 0 else "read" if oe == 0 else "idle" if (rw == 1 and oe == 1) else "read" if rw == 1 else "write"
                if X in (rw, oe) and (rw != 1 or oe != 1): ev.append("%s R/~{WR}=%s ~{OER}=%s undefined" % (NAMES[d.ref], rw, oe))
                if ce == X and op != "idle": ev.append("%s ~{CER} undefined: a %s may %s" % (NAMES[d.ref], op, "land" if op == "write" else "drive the bus"))
                e["ram"] = op
                if op == "read": drivers.append(d.ref)
        c = self.dev.get("CRTC")
        if c:
            cs, en, rw, rs = (mos(v.get(n)) for n in (c.cs, c.e, c.rw, c.rs))
            if cs != 1:
                e["sel"].append(c.ref)
                if not c.fitted:
                    if read_cycle: e["undriven"] = "%s socket empty: its select (CS) is low, nothing drives DATA0..7" % c.ref
                elif en != 0:
                    if cs == X: ev.append("%s CS undefined (E=%s)" % (NAMES[c.ref], en))
                    if en == X: ev.append("%s E undefined (CS=%s)" % (NAMES[c.ref], cs))
                    if rs == X: ev.append("%s RS undefined: taken as 0" % NAMES[c.ref]); rs = 0
                    if rw == X: ev.append("%s R/~{W} undefined: taken as a read" % NAMES[c.ref]); rw = 1
                    e["crtc"] = "read" if rw == 1 else "write"; e["rs"] = rs
                    if rw == 1 and rs == 1: drivers.append(c.ref)
                    elif rw == 1 and read_cycle:
                        e["undriven"] = "%s read with RS = 0: the address register is write-only, nothing drives DATA0..7" % NAMES[c.ref]
                elif read_cycle: e["undriven"] = "%s selected with E low: nothing drives DATA0..7" % NAMES[c.ref]
        l = self.dev.get("LATCH")
        if l and l.fitted and self.c.powered(l.supply):
            oc = ttl(v.get(l.oc))
            if oc != 1:
                if oc == X: ev.append("%s output enable undefined" % NAMES[l.ref])
                enc = ttl(v.get(l.enc)); val = flo = 0
                for i, n in enumerate(l.d):
                    raw = v.get(n); b = ttl(raw) if enc == 1 else X
                    if raw is None: flo |= 1 << i
                    if b == X: b = 1
                    val |= b << i
                if enc != 1: ev.append("%s ENC low or undefined: it drives what it held at power-up, taken as 1s" % NAMES[l.ref])
                e["latch"], e["lval"], e["lfloat"] = 1, val, flo
                drivers.append(l.ref)
        if len(drivers) > 1:
            ev.append("contention on the card: %s drive DATA0..7 together" % " + ".join(NAMES[r] for r in drivers))
        if read_cycle and not drivers and not e["undriven"] and e["sel"] and e["ram"] != "read":
            e["undriven"] = "%s selected, nothing drives DATA0..7" % " + ".join(NAMES.get(r, r) for r in e["sel"])
        return e

    def describe(self):
        out = ["video card %s: %s" % (self.rev, self.title), "  netlist: %s (the board's connections from %s)" % (NET, COMPARE)]
        for op, what, why in self.nl.edits:
            out.append("  %-6s %s%s" % (op, what, "" if op == "board" else "  - " + why))
        out.append("  bus path: %s" % ", ".join(sorted({g.ref if g.op == "rc" else g.ref.split(".")[0] for g in self.c.gates}, key=_icnum)))
        out.append("  gates: " + "; ".join("%s = %s(%s)" % (g.out, g.op if g.drive != "oc" else "inv(oc)", ", ".join(g.ins))
                                          for g in self.c.order if not g.op.startswith("cmp85")) +
                   "; BOARDSEL = A=B of IC18 (A0-3 = SV3, B0-3 = ADDR12-15, cascade A=B = /-VMA)")
        out.append("  bus devices: %s" % ", ".join("%s %s%s" % (d.ref, d.kind, "" if d.fitted else " (socket empty)") for d in self.c.devices))
        out.append("  bus inputs: %s" % " ".join(self.c.inputs))
        if self.c.unmodelled:
            out.append("  off the bus path (checked from the netlist, not simulated): " +
                       " ".join("%s %s" % (r, self.nl.parts[r].value) for r in sorted(self.c.unmodelled, key=_icnum)))
        return "\n".join(out)


def _icnum(r):
    digits = "".join(ch for ch in r.split("/")[0] if ch.isdigit())
    return (r.rstrip("0123456789"), int(digits or 0))


# ---------------------------------------------------------------------------------------------- the C header
def index_signals(cards):
    """the bus inputs any revision's decode reaches, in index order: address bits, then -VMA, -MEM-RD, -MEM-WR"""
    sig = set()
    for c in cards: sig |= set(c.c.inputs)
    if "-RESET" in sig: raise ValueError("a decode that reaches -RESET: not supported by the generated model")
    addr = sorted((s for s in sig if s.startswith("ADDR")), key=lambda s: int(s[4:]))
    return addr + ["-VMA", "-MEM-RD", "-MEM-WR"]


def table(card, signals):
    rows = []
    for idx in range(1 << len(signals)):
        levels = {s: 0 for s in BUS if not s.startswith("DATA")}
        levels["-RESET"] = 1
        for b, s in enumerate(signals): levels[s] = (idx >> b) & 1
        rows.append(card.access(levels))
    return rows


def ram_address(card):
    """C expression for the display RAM's chip address from the bus address a"""
    d = card.dev.get("DPRAM"); terms = []
    for i, n in enumerate(d.addr):
        if n in card.c.power:
            if card.c.power[n] == 1: terms.append("0x%X" % (1 << i))
            continue
        bit = int(card.c.net_signal[n][4:])
        terms.append("((a >> %d) & 1) << %d" % (bit, i) if bit != i else "(a & 0x%X)" % (1 << i))
    return " | ".join(terms) or "0"


def cname(rev): return "vg_" + rev.replace(".", "_").replace("-", "_")


def cstr(s): return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def generate(revs=None, root=ROOT):
    revs = revs or list(REVS)
    cards = [Card(r, root) for r in revs]
    signals = index_signals(cards)
    out = ["/* videogate.h - GENERATED by software/gatemodel (python3 software/gatemodel -o software/ucemu/videogate.h; the",
           "   Makefile runs it) from %s, the board's connections in" % NET,
           "   %s and the revisions in software/gatemodel/video.py: do not edit." % COMPARE,
           "",
           "   The video card's bus path at gate level, for y1ucemu -G REV (software/ucemu/README.md, docs/cards/video.md",
           "   section 9). The decode never depends on the data lines (checked when this was generated), so the gates were",
           "   evaluated once for every combination of the bus inputs they reach; a step looks its decode up here. Index",
           "   bits: %s (each the level on the bus pin). An entry says what the" % ", ".join("%d %s" % (i, s) for i, s in enumerate(signals)),
           "   display RAM's bus port (ram: 0 not selected, 1 selected and idle, 2 read = drives DATA0..7, 3 write), the",
           "   6845 (crtc: the same codes; rs) and the JP1 latch (latch: drives lval; lfloat = its inputs that float) do,",
           "   the events that hold whatever else is on the bus (ev) and why a CPU read finds DATA0..7 undriven when nothing",
           "   else drives it (undriven); both index msgs[], 0 = none. */",
           "#define VG_NSIG %d" % len(signals),
           "static const char *const vg_signals[] = { %s };" % ", ".join(cstr(s) for s in signals),
           "static inline unsigned vg_index(unsigned a, unsigned vma_n, unsigned rd_n, unsigned wr_n) {",
           "    return " + " | ".join(["((a >> %d) & 1u) << %d" % (int(s[4:]), i) for i, s in enumerate(signals) if s.startswith("ADDR")] +
                                     ["%s << %d" % (n, signals.index(s)) for s, n in (("-VMA", "vma_n"), ("-MEM-RD", "rd_n"), ("-MEM-WR", "wr_n"))]) + ";",
           "}",
           "enum { VG_NONE, VG_IDLE, VG_READ, VG_WRITE };",
           "struct vg_entry { uint32_t d; uint16_t ev, undriven; };   /* d: ram bits 0-1, crtc 2-3, rs 4, latch 5, lval 8-15, lfloat 16-23 */",
           "#define VG_RAM(e)    ((e)->d & 3)",
           "#define VG_CRTC(e)   (((e)->d >> 2) & 3)",
           "#define VG_RS(e)     (((e)->d >> 4) & 1)",
           "#define VG_LATCH(e)  (((e)->d >> 5) & 1)",
           "#define VG_LVAL(e)   (((e)->d >> 8) & 0xFF)",
           "#define VG_LFLOAT(e) (((e)->d >> 16) & 0xFF)",
           "struct vg_rev { const char *name, *title; const char *const *edits; const char *const *msgs; const struct vg_entry *t;",
           "                unsigned (*ramaddr)(unsigned a); };",
           ""]
    code = {"none": 0, "idle": 1, "read": 2, "write": 3}
    for card in cards:
        rows = table(card, signals); n = cname(card.rev)
        msgs = [""]; ix = {"": 0}

        def mid(s):
            if s not in ix: ix[s] = len(msgs); msgs.append(s)
            return ix[s]
        ents = []
        for r in rows:
            d = code[r["ram"]] | code[r["crtc"]] << 2 | r["rs"] << 4 | r["latch"] << 5
            if r["latch"]: d |= r["lval"] << 8 | r["lfloat"] << 16
            ents.append("{%s,%d,%d}" % ("0x%X" % d if d > 9 else d, mid("; ".join(r["events"])), mid(r["undriven"])))
        out.append("/* ---- %s: %s" % (card.rev, card.title))
        out += ["   " + l for l in card.describe().splitlines()[1:]]
        out[-1] += " */"
        out.append("static const char *const %s_edits[] = {" % n)
        out += ["    %s," % cstr("%s %s%s" % (op, what, "" if op == "board" else " - " + why)) for op, what, why in card.nl.edits]
        out.append("    0 };")
        out.append("static const char *const %s_msgs[] = {" % n)
        out += ["    %s," % cstr(m) for m in msgs]
        out.append("    0 };")
        out.append("static const struct vg_entry %s_t[%d] = {" % (n, len(ents)))
        for i in range(0, len(ents), 16): out.append("    " + ",".join(ents[i:i + 16]) + ",")
        out.append("};")
        out.append("static unsigned %s_ramaddr(unsigned a) { return %s; }" % (n, ram_address(card) if "DPRAM" in card.dev else "0"))
        out.append("")
    out.append("static const struct vg_rev vg_revs[] = {")
    for card in cards:
        n = cname(card.rev)
        out.append("    { %s, %s, %s_edits, %s_msgs, %s_t, %s_ramaddr }," % (cstr(card.rev), cstr(card.title), n, n, n, n))
    out.append("    { 0, 0, 0, 0, 0, 0 } };")
    out.append("#define VG_DEFAULT %s" % cstr(DEFAULT))
    return "\n".join(out) + "\n"
