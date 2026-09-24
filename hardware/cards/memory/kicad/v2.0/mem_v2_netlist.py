"""mem_v2_netlist.py - the YACC1 memory card v2.0 circuit: v1.3 unchanged + the CompactFlash section (2026-09-24).

THE single source of what v2.0 adds. Plain Python, no KiCad import.

    v2.0 = v1.3                      the netlist KiCad extracts from ../v1.3/memory-v1.3.kicad_sch (itself proved pin for
                                     pin against the Eagle board in hardware/cards/memory/eagle/v1.3; see ../v1.3/README.md).
                                     Not restated here: check_netlist.py exports it fresh and compares.
         + CF section                hardware/cards/cf/kicad/v1.0/cf_netlist.py (the standalone CF card v1.0), transformed
                                     by the explicit rules below - nothing else is added or changed.

Rules (Ken's decisions, 2026-09-24):
  1. The CF card v1.0 circuit AS DRAWN, including its own port decoder U1 (74LS138, G1 = IO-ADDR3, Y0 = P8, Y1 = P9):
     the CF stays on I/O ports P8 (register-select latch, write) / P9 (data, read/write), which the ROM in the machine
     and both emulators (software/cfmodel.h, firmware/monitor/monitor.asm) already use.
  2. The CF card's bus connector X1 is DROPPED: its bus nets (DATA0-7, IO-ADDR0-3, -IO-RD, -IO-WR, -RESET, VCC, GND)
     join the memory card's nets on the same X1 pins (check_netlist.py verifies every dropped CF X1 pin is on the
     same-named net of the memory card's X1). On v1.3, IO-ADDR0-3, -IO-RD and -IO-WR reach only X1 (sheet-1 local
     labels); on v2.0 they are global labels, because sheet 7 uses them. -RESET (IC12 PRE) and DATA0-7 were global
     already.
  3. The CF card's DASP LED (LED3 + R6) is DROPPED (Ken); -DASP keeps its 10k pull-up.
  4. The CF card's PWR LED (LED1 + R7) is DROPPED: the memory card v1.3 already has one (PWR0 + R2 330R).
  5. Every other CF part is kept with its value, KiCad symbol and footprint, renamed so nothing collides with v1.3
     (v1.3 uses IC1-IC14, IC18, IC26-IC29, C1-C24, R2, RN5-RN8, JP1, PWR0, U$1, X1) nor with the IC15 (74ALS11) that
     the FABRICATED card carries but no schematic in the tree has (README.md, "The fabricated v1.3"): REFMAP below.
     The CF card's per-IC 100 nF caps stay one per IC (C25-C29) and its 10 uF bulk cap (C30) stays beside the adapter
     power header.
The CF section's own nets keep their cf_netlist.py names (on sheet 7 of the schematic, so KiCad calls them
/Sheet 7/<name>); the shared ones are global labels / power symbols with the memory card's names.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", ".."))
CFDIR = os.path.join(ROOT, "hardware", "cards", "cf", "kicad", "v1.0")
sys.path.insert(0, CFDIR)
import cf_netlist as CF          # noqa: E402

CARD = "YACC1 memory card"
REV = "v2.0"
DATE = "2026-09-24"
CF_SHEET = "Sheet 7"             # the schematic sheet holding the CF section (net prefix /Sheet 7/)

# CF card v1.0 reference -> memory card v2.0 reference
REFMAP = {
    "U1": "IC30",    # 74LS138 port decode: Y0 = P8, Y1 = P9 (G1 = IO-ADDR3)
    "U2": "IC31",    # 74LS32  strobe gating: P8 latch clock, CF -IOR, CF -IOW
    "U3": "IC32",    # 74LS175 P8 latch: DA0-2 + CF reset bit
    "U4": "IC33",    # 74LS08  buffer enable, CF reset, ACT LED driver
    "U5": "IC34",    # 74LS245 data buffer bus <-> CF D0-7
    "J1": "J2",      # 40-pin IDE header (to the CF-to-IDE adapter)
    "J2": "J3",      # adapter power 1x4
    "JP1": "JP2",    # IDE pin 20 +5V jumper
    "RN1": "RN9",    # CF D0-7 pull-ups
    "R1": "R10", "R2": "R11", "R3": "R12", "R4": "R13",   # IORDY, -PDIAG, -DASP pull-ups, -DMACK held high
    "R5": "R14",     # ACT LED resistor
    "LED2": "LED1",  # ACT LED
    "C1": "C25", "C2": "C26", "C3": "C27", "C4": "C28", "C5": "C29",   # 100 nF, one per new IC
    "C6": "C30",     # 10 uF bulk beside the adapter power header
}
DROPPED = {
    "X1": "bus connector: the memory card's X1 carries the same bus nets",
    "LED1": "PWR LED: the memory card has PWR0 + R2",
    "R7": "PWR LED resistor",
    "LED3": "DASP LED (dropped, Ken 2026-09-24)",
    "R6": "DASP LED resistor",
}
# nets shared with the v1.3 part of the card: global labels (or power symbols) on sheet 7, same names as v1.3
SHARED = (["DATA%d" % i for i in range(8)] + ["IO-ADDR%d" % i for i in range(4)] + ["-IO-RD", "-IO-WR", "-RESET"])
POWER = ["VCC", "GND"]
# the v1.3 nets that become global because sheet 7 uses them (v1.3 had them as sheet-1 local labels on X1 only)
V13_RENAMED = {"/Sheet 1/%s" % n: n for n in ["IO-ADDR%d" % i for i in range(4)] + ["-IO-RD", "-IO-WR"]}

assert set(REFMAP) | set(DROPPED) == set(CF.PARTS) and not set(REFMAP) & set(DROPPED)

# the parts' description notes, reworded for the memory card (the CF card's say U2..U5, J2); value, symbol and
# footprint are cf_netlist.py's unchanged
NOTES = {
    "IC30": "CF port decode: Y0 = P8, Y1 = P9 (G1 = IO-ADDR3)",
    "IC31": "CF strobe gating: P8 latch clock, CF -IOR, CF -IOW",
    "IC32": "P8 latch: DA0..2 + CF reset bit",
    "IC33": "CF buffer enable, CF reset, ACT LED driver",
    "IC34": "P9 data buffer: bus <-> CF D0..7",
    "J2": "IDE 40: to the CF-to-IDE adapter (pin 20 kept)",
    "J3": "adapter power: 1 +5V, 2 GND, 3 GND, 4 n/c",
    "JP2": "fit only for adapters powered on IDE pin 20",
    "RN9": "CF D0..7 pull-ups (empty adapter reads $FF)",
    "R10": "IORDY pull-up", "R11": "-PDIAG pull-up", "R12": "-DASP pull-up", "R13": "-DMACK held inactive",
    "R14": "ACT LED",
    "LED1": "ACT: any P9 access (the buffer enabled)",
    "C25": "IC30 decoupling", "C26": "IC31 decoupling", "C27": "IC32 decoupling", "C28": "IC33 decoupling",
    "C29": "IC34 decoupling",
    "C30": "bulk, beside J3 (the CF draws up to ~100 mA)",
}
PARTS = {REFMAP[r]: v[:3] + (NOTES[REFMAP[r]],) for r, v in CF.PARTS.items() if r in REFMAP}
assert set(NOTES) == set(PARTS)


def _cf_nets():
    """-> (nets {name: [(ref, pin)]}, dropped X1 bus nodes {net: [pin]}), CF section only, v2.0 refs"""
    nets, x1 = {}, {}
    for name, conns in CF.NETS.items():
        kept = [(REFMAP[r], p) for r, p in conns if r in REFMAP]
        gone = [(r, p) for r, p in conns if r not in REFMAP]
        x1pins = [p for r, p in gone if r == "X1"]
        if x1pins:
            x1[name] = x1pins
        # a net may lose only the bus connector (shared nets) or a dropped LED/resistor (its own two-pin nets)
        for r, p in gone:
            if r != "X1" and r not in DROPPED:
                raise SystemExit("cf net %s: %s.%s neither kept nor dropped" % (name, r, p))
        if kept:                     # LEDA1 (R7-LED1) and LEDA3 (R6-LED3) lose both ends and vanish
            nets[name] = kept
    return nets, x1


NETS, X1_BUS = _cf_nets()
NO_CONNECT = {REFMAP[r]: list(ps) for r, ps in CF.NO_CONNECT.items() if r in REFMAP}


def check():
    """the CF section on its own: every pin of every kept part on exactly one net or a documented no-connect"""
    from cf_netlist import check as cf_check
    probs = list(cf_check())
    seen = {}
    for n, conns in NETS.items():
        for rp in conns:
            if rp in seen:
                probs.append("%s.%s on %s and %s" % (rp[0], rp[1], seen[rp], n))
            seen[rp] = n
    npins = {REFMAP[r]: n for r, n in {"U1": 16, "U2": 14, "U3": 16, "U4": 14, "U5": 20, "J1": 40, "J2": 4, "JP1": 2,
                                       "RN1": 9, **{x: 2 for x in ("R1", "R2", "R3", "R4", "R5", "LED2", "C1", "C2",
                                                                   "C3", "C4", "C5", "C6")}}.items()}
    assert set(npins) == set(PARTS), sorted(set(npins) ^ set(PARTS))
    for ref, n in npins.items():
        for p in range(1, n + 1):
            k = (ref, str(p))
            if (k in seen) == (str(p) in NO_CONNECT.get(ref, [])):
                probs.append("%s.%d: %s" % (ref, p, "on a net AND no-connect" if k in seen else "unaccounted"))
    for n in NETS:
        if n not in SHARED + POWER and len(NETS[n]) < 2 and n != "SRST":
            probs.append("net %s has one pin" % n)
    for n in SHARED + POWER:
        if n not in NETS:
            probs.append("shared net %s is not used by the CF section" % n)
    return probs


def expected(v13_nets, v13_parts):
    """v2.0 = v1.3 + CF section.
    v13_nets: {name: set((ref, pin))} of the v1.3 schematic netlist (every net, including one-pin and unconnected-()
    ones); v13_parts: {ref: (value, footprint)}.
    -> (nets {name: set}, parts {ref: (value, footprint)}, lone set((ref, pin)) = pins KiCad must leave unconnected,
        notes [str])"""
    nets, lone, notes = {}, set(), []
    for name, nodes in v13_nets.items():
        if name.startswith("unconnected-("):
            lone |= nodes
        else:
            nets[V13_RENAMED.get(name, name)] = set(nodes)
    # the v1.3 bus nets the CF section joins: IO-ADDR0-3 / -IO-RD / -IO-WR must reach X1 only on v1.3
    for old, new in V13_RENAMED.items():
        if old not in v13_nets:
            raise SystemExit("v1.3: net %s not found" % old)
        others = {r for r, p in v13_nets[old]} - {"X1"}
        if others:
            raise SystemExit("v1.3: %s is not X1-only: %s" % (old, sorted(v13_nets[old])))
    notes.append("v1.3 IO-ADDR0-3, -IO-RD, -IO-WR = X1 C7-C10, B25, B26 only (sheet-1 local labels); now global")
    # every dropped CF X1 bus pin must sit on the same-named net of the memory card's X1
    for net, pins in X1_BUS.items():
        for p in pins:
            if ("X1", p) not in nets.get(net, set()):
                raise SystemExit("bus pin X1.%s is %s on the CF card but not on the memory card" % (p, net))
    notes.append("CF card X1: %d bus pins on %d nets, each on the same-named net of the memory card's X1"
                 % (sum(len(v) for v in X1_BUS.values()), len(X1_BUS)))
    for name, conns in NETS.items():
        full = name if name in SHARED + POWER else "/%s/%s" % (CF_SHEET, name)
        if full in nets and name not in SHARED + POWER:
            raise SystemExit("CF net %s collides with a v1.3 net" % full)
        if name in SHARED + POWER and full not in nets:
            raise SystemExit("shared net %s is not a v1.3 net" % full)
        nets.setdefault(full, set()).update(conns)
    for ref, pins in NO_CONNECT.items():
        lone |= {(ref, p) for p in pins}
    parts = dict(v13_parts)
    for ref, (value, sym, fp, note) in PARTS.items():
        if ref in parts:
            raise SystemExit("reference %s collides with v1.3" % ref)
        parts[ref] = (value, fp)
    return nets, parts, lone, notes


if __name__ == "__main__":
    p = check()
    print("\n".join(p) if p else "mem_v2_netlist: CF section %d parts, %d nets, %d no-connect pins; every pin "
          "accounted for" % (len(PARTS), len(NETS), sum(len(v) for v in NO_CONNECT.values())))
