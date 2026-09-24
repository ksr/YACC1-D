"""io_v2_netlist.py - the YACC1 I/O card v2.0 circuit: v1.1 unchanged + the CompactFlash section (2026-09-23).

THE single source of what v2.0 adds. Plain Python, no KiCad import.

    v2.0 = v1.1                      the netlist KiCad extracts from ../v1.1/io-v1.1.kicad_sch (itself proved pin for pin
                                     against the Eagle board that was fabricated; see ../v1.1/README.md). Not restated
                                     here: check_netlist.py exports it fresh and compares.
         + CF section                hardware/cards/cf/kicad/v1.0/cf_netlist.py (the standalone CF card v1.0), transformed
                                     by the explicit rules below - nothing else is added or changed.

Rules (Ken's decisions, 2026-09-23):
  1. The CF card's port decoder U1 (74LS138) is DROPPED. The I/O card's IC5 (74LS138, strapped to P0-P7 by the
     IO-ADDR-HL header) already decodes the ports: Y4 (pin 11, net -IO-SEL4) replaces -P8SEL and Y5 (pin 10, -IO-SEL5)
     replaces -P9SEL. So the CF ports move from P8/P9 to P4 (register-select latch, write) / P5 (data, read/write).
     On v1.1, -IO-SEL4/-IO-SEL5 reach only the IO-ADDR and DATA-ADDR jumper headers (pins 8/6): the jumpers must not
     select P4 or P5 on v2.0.
  2. The CF card's bus connector X1 is DROPPED: its bus nets (DATA0-7, -IO-RD, -IO-WR, -RESET, VCC, GND) join the I/O
     card's nets of the same name (check_netlist.py verifies every dropped X1 pin is on the same-named net of the I/O
     card's X1). IO-ADDR0-3 on the CF card fed only U1, so they leave the CF section with it.
  3. The CF card's DASP LED (LED3 + R6) is DROPPED (Ken); -DASP keeps its 10k pull-up.
  4. The CF card's PWR LED (LED1 + R7) is DROPPED: v1.1 already has one (PWR0 + R2 330R).
  5. The CF card's U1 decoupling cap (C1) goes with U1.
  6. Every other CF part is kept with its value, KiCad symbol and footprint, renamed so nothing collides with v1.1
     (v1.1 uses IC1-IC11, C1-C17, R1-R10, RN2, J1, JP1, X1, X2, Y1, TM1): REFMAP below.
The CF section's own nets keep their cf_netlist.py names (on sheet 7 of the schematic, so KiCad calls them
/Sheet 7/<name>); the shared ones are global labels / power symbols with the I/O card's names.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", ".."))
CFDIR = os.path.join(ROOT, "hardware", "cards", "cf", "kicad", "v1.0")
sys.path.insert(0, CFDIR)
import cf_netlist as CF          # noqa: E402

CARD = "YACC1 I/O card"
REV = "v2.0"
DATE = "2026-09-23"
CF_SHEET = "Sheet 7"             # the schematic sheet holding the CF section (net prefix /Sheet 7/)

# CF card v1.0 reference -> I/O card v2.0 reference
REFMAP = {
    "U2": "IC12",    # 74LS32  strobe gating: P4 latch clock, CF -IOR, CF -IOW
    "U3": "IC13",    # 74LS175 P4 latch: DA0-2 + CF reset bit
    "U4": "IC14",    # 74LS08  buffer enable, CF reset, ACT LED driver
    "U5": "IC15",    # 74LS245 data buffer bus <-> CF D0-7
    "J1": "J2",      # 40-pin IDE header (ribbon to the CF-to-IDE adapter)
    "J2": "J3",      # adapter power 1x4
    "JP1": "JP2",    # IDE pin 20 +5V jumper
    "RN1": "RN3",    # CF D0-7 pull-ups
    "R1": "R11", "R2": "R12", "R3": "R13", "R4": "R14",   # IORDY, -PDIAG, -DASP pull-ups, -DMACK held high
    "R5": "R15",     # ACT LED resistor
    "LED2": "LED1",  # ACT LED
    "C2": "C18", "C3": "C19", "C4": "C20", "C5": "C21",   # 100 nF, one per new IC
    "C6": "C22",     # 10 uF bulk beside the adapter power header
}
DROPPED = {
    "X1": "bus connector: the I/O card's X1 carries the same bus nets",
    "U1": "port decoder: IC5 Y4/Y5 of the I/O card replace -P8SEL/-P9SEL",
    "C1": "U1's decoupling capacitor",
    "LED1": "PWR LED: the I/O card has PWR0 + R2",
    "R7": "PWR LED resistor",
    "LED3": "DASP LED (dropped, Ken 2026-09-23)",
    "R6": "DASP LED resistor",
}
# CF card nets whose driver is replaced by an I/O card node (the net is renamed to the I/O card's net)
NETMAP = {"-P8SEL": "-IO-SEL4", "-P9SEL": "-IO-SEL5"}
IO_NODES = {"-IO-SEL4": [("IC5", "11")],   # 74LS138 Y4 = port 4
            "-IO-SEL5": [("IC5", "10")]}   # 74LS138 Y5 = port 5
# nets shared with the v1.1 part of the card: global labels (or power symbols) on sheet 7, same names as v1.1
SHARED = ["DATA%d" % i for i in range(8)] + ["-IO-RD", "-IO-WR", "-RESET", "-IO-SEL4", "-IO-SEL5"]
POWER = ["VCC", "GND"]
# the v1.1 nets that become global because sheet 7 uses them (v1.1 had them as sheet-5 local labels)
V11_RENAMED = {"/Sheet 5/-IO-SEL4": "-IO-SEL4", "/Sheet 5/-IO-SEL5": "-IO-SEL5"}

assert set(REFMAP) | set(DROPPED) == set(CF.PARTS) and not set(REFMAP) & set(DROPPED)

# the parts' description notes, reworded for the I/O card (the CF card's say U2..U5, P8/P9, J2); value, symbol and
# footprint are cf_netlist.py's unchanged
NOTES = {
    "IC12": "strobe gating: P4 latch clock, CF -IOR, CF -IOW",
    "IC13": "P4 latch: DA0..2 + CF reset bit",
    "IC14": "buffer enable, CF reset, ACT LED driver",
    "IC15": "P5 data buffer: bus <-> CF D0..7",
    "J2": "IDE 40: ribbon to the CF-to-IDE adapter",
    "J3": "adapter power: 1 +5V, 2 GND, 3 GND, 4 n/c",
    "JP2": "fit only for adapters powered on IDE pin 20",
    "RN3": "CF D0..7 pull-ups (empty adapter reads $FF)",
    "R11": "IORDY pull-up", "R12": "-PDIAG pull-up", "R13": "-DASP pull-up", "R14": "-DMACK held inactive",
    "R15": "ACT LED",
    "LED1": "ACT: any P5 access (the buffer enabled)",
    "C18": "IC12 decoupling", "C19": "IC13 decoupling", "C20": "IC14 decoupling", "C21": "IC15 decoupling",
    "C22": "bulk, beside J3 (the CF draws up to ~100 mA)",
}
PARTS = {REFMAP[r]: v[:3] + (NOTES[REFMAP[r]],) for r, v in CF.PARTS.items() if r in REFMAP}
assert set(NOTES) == set(PARTS)


def _cf_nets():
    """-> (nets {name: [(ref, pin)]}, dropped X1 bus nodes {net: [pin]}), CF section only, v2.0 names/refs"""
    nets, x1 = {}, {}
    for name, conns in CF.NETS.items():
        new = NETMAP.get(name, name)
        kept = [(REFMAP[r], p) for r, p in conns if r in REFMAP]
        x1pins = [p for r, p in conns if r == "X1"]
        if x1pins:
            x1[new] = x1pins
        if name in NETMAP:
            gone = [(r, p) for r, p in conns if r not in REFMAP]
            assert all(r == "U1" for r, p in gone), (name, gone)       # only the dropped decoder drove it
        if kept:
            nets[new] = kept
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
    npins = {REFMAP[r]: n for r, n in {"U2": 14, "U3": 16, "U4": 14, "U5": 20, "J1": 40, "J2": 4, "JP1": 2, "RN1": 9,
                                       **{x: 2 for x in ("R1", "R2", "R3", "R4", "R5", "LED2", "C2", "C3", "C4", "C5",
                                                         "C6")}}.items()}
    assert set(npins) == set(PARTS)
    for ref, n in npins.items():
        for p in range(1, n + 1):
            k = (ref, str(p))
            if (k in seen) == (str(p) in NO_CONNECT.get(ref, [])):
                probs.append("%s.%d: %s" % (ref, p, "on a net AND no-connect" if k in seen else "unaccounted"))
    for n in NETS:
        if n not in SHARED + POWER and len(NETS[n]) < 2 and n != "SRST":
            probs.append("net %s has one pin" % n)
    for n in NETMAP.values():
        if n not in NETS:
            probs.append("mapped net %s vanished" % n)
    return probs


def expected(v11_nets, v11_parts):
    """v2.0 = v1.1 + CF section.
    v11_nets: {name: set((ref, pin))} of the v1.1 schematic netlist (every net, including one-pin and unconnected-()
    ones); v11_parts: {ref: (value, footprint)}.
    -> (nets {name: set}, parts {ref: (value, footprint)}, lone set((ref, pin)) = pins KiCad must leave unconnected,
        notes [str])"""
    nets, lone, notes = {}, set(), []
    for name, nodes in v11_nets.items():
        if name.startswith("unconnected-("):
            lone |= nodes
        else:
            nets[V11_RENAMED.get(name, name)] = set(nodes)
    # the IC5 outputs the CF section now uses: on v1.1 they must reach only the jumper headers
    for net, nodes in IO_NODES.items():
        for rp in nodes:
            have = [n for n, s in nets.items() if rp in s]
            if have != [net]:
                raise SystemExit("v1.1: %s.%s should be on %s, is on %s" % (rp[0], rp[1], net, have))
        others = {r for r, p in nets[net]} - {"IC5", "IO-ADDR0", "DATA-ADDR0"}
        notes.append("v1.1 %s = %s (IC5 and the two jumper headers only%s)" % (
            net, sorted(nets[net]), "" if not others else "; ALSO %s" % sorted(others)))
    # every dropped CF X1 bus pin must sit on the same-named net of the I/O card's X1
    for net, pins in X1_BUS.items():
        if net in ("IO-ADDR0", "IO-ADDR1", "IO-ADDR2", "IO-ADDR3"):
            continue                                              # fed only the dropped U1
        for p in pins:
            if ("X1", p) not in nets.get(net, set()):
                raise SystemExit("bus pin X1.%s is %s on the CF card but not on the I/O card" % (p, net))
    for name, conns in NETS.items():
        full = name if name in SHARED + POWER else "/%s/%s" % (CF_SHEET, name)
        if full in nets and name not in SHARED + POWER:
            raise SystemExit("CF net %s collides with a v1.1 net" % full)
        nets.setdefault(full, set()).update(conns)
    for ref, pins in NO_CONNECT.items():
        lone |= {(ref, p) for p in pins}
    parts = dict(v11_parts)
    for ref, (value, sym, fp, note) in PARTS.items():
        if ref in parts:
            raise SystemExit("reference %s collides with v1.1" % ref)
        parts[ref] = (value, fp)
    return nets, parts, lone, notes


if __name__ == "__main__":
    p = check()
    print("\n".join(p) if p else "io_v2_netlist: CF section %d parts, %d nets, %d no-connect pins; every pin accounted "
          "for" % (len(PARTS), len(NETS), sum(len(v) for v in NO_CONNECT.values())))
