"""cf_netlist.py - the YACC1 CompactFlash card v1.0: THE single source of its circuit (2026-09-23).

gen_cf.py reads this module to write the KiCad schematic and to build the board; nothing else defines the circuit.
Plain Python data, no KiCad import, so tools and tests can load it anywhere.

The card (docs/cards/cf.md has the full theory of operation):
  * two I/O ports, as docs/system/OS-PLAN.md decided and software/cfmodel.h models:
      P8 write  -> a 74LS175 latch: bits 0..2 = the ATA task-file register (CF DA0..2), bit 3 = CF reset (1 = held)
      P9 read/write -> the selected ATA register, 8-bit True IDE, through a 74LS245
  * decode: 74LS138 on IOADDR0..2 enabled by IOADDR3 (Y0 = port 8, Y1 = port 9); the other six outputs are unused
  * strobes: 74LS32 ORs the port select with the bus -IO-WR / -IO-RD, so the CF's -IOR/-IOW (and the latch clock) are
    low only during the bus strobe for the card's own port. The microcode sets IOADDR two steps before the strobe and
    keeps it through the strobe (firmware/microcode/ucode-generator2/io.c), so each strobe starts and ends cleanly.
  * -CS0 is tied LOW and -CS1 HIGH: the strobes alone define every cycle. Gating -CS0 with the port-9 decode would
    release it on the same clock edge as -IO-RD at the end of an INP, a gate delay BEFORE -IOR rises, breaking the
    CF's chip-select hold time (t9) on the data-register reads that advance its sector buffer.
  * the CF sits in a commercial CF-to-IDE adapter on a 40-pin IDE header (J1), as on the P8X; the adapter is powered
    from J2 (floppy-style 4-pin) or, through JP1, from IDE pin 20 for adapters that take it there.
  * pull-ups: CF D0..7 (so an empty adapter reads $FF, which the ROM driver treats as "no card"), IORDY, -PDIAG,
    -DASP; -DMACK held inactive; CSEL grounded (master).
  * LEDs: power (the blank card's), ACT (any access, from the buffer enable), DASP (the CF's own busy/activity pin).

Pin numbers are the physical pins of the DIP packages (TI/Fairchild pinouts, as in the KiCad 74xx symbols) and of the
40-pin IDE header (odd pins 1..39 one row, even 2..40 the other; data D0..7 on pins 17,15,..,3 - the P8X CF card's
proven assignment, ~/Developer/p8x/generators/gen_eagle.py). Bus pins are the V3.2 DIN 41612 (docs/system/BUS.md,
cross-checked 2026-09-23 against the I/O card v1.1 schematic's connector: DATA0 A19 .. DATA7 A26, IO-ADDR0..3
C7..C10, -IO-RD B25, -IO-WR B26, -RESET C30).
"""

CARD = "YACC1 CF card"
REV = "v1.0"
DATE = "2026-09-23"

# ---- parts: reference -> (value, KiCad symbol lib:name, KiCad footprint lib:name, note) ----------------------------
PARTS = {
    "X1":  ("DIN41612 96", "blank-card-v3.2-eagle:FABC96R", "blank-card-v3.2-eagle:FABC96R", "bus connector (blank V3.2 card)"),
    "U1":  ("74LS138", "74xx:74LS138", "Package_DIP:DIP-16_W7.62mm", "port decode: Y0 = P8, Y1 = P9"),
    "U2":  ("74LS32",  "74xx:74LS32",  "Package_DIP:DIP-14_W7.62mm", "strobe gating"),
    "U3":  ("74LS175", "74xx:74LS175", "Package_DIP:DIP-16_W7.62mm", "P8 latch: DA0..2 + CF reset bit"),
    "U4":  ("74LS08",  "74xx:74LS08",  "Package_DIP:DIP-14_W7.62mm", "buffer enable, CF reset, ACT LED driver"),
    "U5":  ("74LS245", "74xx:74LS245", "Package_DIP:DIP-20_W7.62mm", "data buffer bus <-> CF D0..7"),
    "J1":  ("IDE 40",  "Connector_Generic:Conn_02x20_Odd_Even", "Connector_IDC:IDC-Header_2x20_P2.54mm_Vertical", "to the CF-to-IDE adapter"),
    "J2":  ("POWER",   "Connector_Generic:Conn_01x04", "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", "adapter power: 1 +5V, 2 GND, 3 GND, 4 n/c"),
    "JP1": ("PIN20 5V", "Connector_Generic:Conn_01x02", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "fit only for adapters powered on IDE pin 20"),
    "RN1": ("10k x8",  "Device:R_Network08", "Resistor_THT:R_Array_SIP9", "CF D0..7 pull-ups (empty adapter reads $FF)"),
    "R1":  ("10k", "Device:R", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", "IORDY pull-up"),
    "R2":  ("10k", "Device:R", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", "-PDIAG pull-up"),
    "R3":  ("10k", "Device:R", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", "-DASP pull-up"),
    "R4":  ("10k", "Device:R", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", "-DMACK held inactive"),
    "R5":  ("1k",  "Device:R", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", "ACT LED"),
    "R6":  ("1k",  "Device:R", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", "DASP LED"),
    "R7":  ("1k",  "Device:R", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", "PWR LED"),
    "LED1": ("PWR green",  "Device:LED", "LED_THT:LED_D5.0mm", "power"),
    "LED2": ("ACT yellow", "Device:LED", "LED_THT:LED_D5.0mm", "any port-9 access (the buffer enabled)"),
    "LED3": ("DASP red",   "Device:LED", "LED_THT:LED_D5.0mm", "the CF's own activity/busy"),
    "C1":  ("100n", "Device:C", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm", "U1 decoupling"),
    "C2":  ("100n", "Device:C", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm", "U2 decoupling"),
    "C3":  ("100n", "Device:C", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm", "U3 decoupling"),
    "C4":  ("100n", "Device:C", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm", "U4 decoupling"),
    "C5":  ("100n", "Device:C", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm", "U5 decoupling"),
    "C6":  ("10u",  "Device:CP", "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm", "bulk, beside J2 (the CF draws up to ~100 mA)"),
}

# ---- nets: name -> [(ref, pin), ...] ----------------------------------------------------------------------------
BUS_VCC = ["A2", "A31", "B2", "B31", "C2", "C31"]
BUS_GND = ["A1", "A32", "B1", "B32", "C1", "C32"]
IDE_GND = ["2", "19", "22", "24", "26", "30", "40"]

NETS = {
    "VCC": [("X1", p) for p in BUS_VCC] + [
        ("U1", "16"), ("U2", "14"), ("U3", "16"), ("U4", "14"), ("U5", "20"),
        ("C1", "1"), ("C2", "1"), ("C3", "1"), ("C4", "1"), ("C5", "1"), ("C6", "1"),
        ("J2", "1"), ("JP1", "1"), ("J1", "38"),                       # -CS1 inactive
        ("RN1", "1"), ("R1", "1"), ("R2", "1"), ("R3", "1"), ("R4", "1"), ("R5", "1"), ("R6", "1"), ("R7", "1"),
    ],
    "GND": [("X1", p) for p in BUS_GND] + [("J1", p) for p in IDE_GND] + [
        ("U1", "8"), ("U2", "7"), ("U3", "8"), ("U4", "7"), ("U5", "10"),
        ("C1", "2"), ("C2", "2"), ("C3", "2"), ("C4", "2"), ("C5", "2"), ("C6", "2"),
        ("J2", "2"), ("J2", "3"),
        ("U1", "4"), ("U1", "5"),                                      # 138 -G2A, -G2B enabled
        ("J1", "37"),                                                  # -CS0 always selected (see the docstring)
        ("J1", "28"),                                                  # CSEL: master
        ("U2", "12"), ("U2", "13"),                                    # 74LS32 gate 4 unused: inputs tied
        ("U4", "12"), ("U4", "13"),                                    # 74LS08 gate 4 unused: inputs tied
        ("LED1", "1"),                                                 # PWR LED cathode
    ],
    # bus data <-> buffer A side, and the latch inputs
    **{"DATA%d" % b: [("X1", "A%d" % (19 + b)), ("U5", str(2 + b))] for b in range(8)},
    # port number and strobes from the bus
    "IO-ADDR0": [("X1", "C7"), ("U1", "1")],
    "IO-ADDR1": [("X1", "C8"), ("U1", "2")],
    "IO-ADDR2": [("X1", "C9"), ("U1", "3")],
    "IO-ADDR3": [("X1", "C10"), ("U1", "6")],                          # G1: ports 8..15 only
    "-IO-RD":   [("X1", "B25"), ("U2", "5")],
    "-IO-WR":   [("X1", "B26"), ("U2", "2"), ("U2", "10")],
    "-RESET":   [("X1", "C30"), ("U3", "1"), ("U4", "4")],             # latch clear; CF reset AND
    # decode
    "-P8SEL":   [("U1", "15"), ("U2", "1")],
    "-P9SEL":   [("U1", "14"), ("U2", "4"), ("U2", "9")],
    # strobe gating (74LS32): 1: P8 latch clock   2: CF -IOR   3: CF -IOW
    "LATCHCLK": [("U2", "3"), ("U3", "9")],
    "-IOR":     [("U2", "6"), ("J1", "25"), ("U5", "1"), ("U4", "1")],  # also the 245's DIR (low = CF -> bus)
    "-IOW":     [("U2", "8"), ("J1", "23"), ("U4", "2")],
    # 74LS08: 1: buffer enable = -IOR AND -IOW   2: CF reset = -RESET AND -SRST   3: ACT LED sink
    "-CFOE":    [("U4", "3"), ("U5", "19"), ("U4", "9"), ("U4", "10")],
    "-CFRESET": [("U4", "6"), ("J1", "1")],
    "ACTK":     [("U4", "8"), ("LED2", "1")],
    # the P8 latch (74LS175: CLR 1, Q1 2, -Q1 3, D1 4, D2 5, -Q2 6, Q2 7, CLK 9, Q3 10, -Q3 11, D3 12, D4 13, -Q4 14, Q4 15)
    "DA0":      [("U3", "2"), ("J1", "35")],
    "DA1":      [("U3", "7"), ("J1", "33")],
    "DA2":      [("U3", "10"), ("J1", "36")],
    "SRST":     [("U3", "15")],                                        # bit 3, readable on a test point only
    "-SRST":    [("U3", "14"), ("U4", "5")],
    # CF side of the buffer, with pull-ups
    **{"CFD%d" % b: [("U5", str(18 - b)), ("J1", str(17 - 2 * b)), ("RN1", str(2 + b))] for b in range(8)},
    # CF status/handshake pins
    "IORDY":    [("J1", "27"), ("R1", "2")],
    "-PDIAG":   [("J1", "34"), ("R2", "2")],
    "-DASP":    [("J1", "39"), ("R3", "2"), ("LED3", "1")],
    "-DMACK":   [("J1", "29"), ("R4", "2")],
    "PIN20":    [("J1", "20"), ("JP1", "2")],
    # LEDs
    "LEDA2":    [("R5", "2"), ("LED2", "2")],
    "LEDA3":    [("R6", "2"), ("LED3", "2")],
    "LEDA1":    [("R7", "2"), ("LED1", "2")],
}
# the P8 latch's data inputs D1..D4 share the bus data nets DATA0..3
NETS["DATA0"].append(("U3", "4")); NETS["DATA1"].append(("U3", "5"))
NETS["DATA2"].append(("U3", "12")); NETS["DATA3"].append(("U3", "13"))

# pins deliberately left unconnected (documented, so a check can tell them from mistakes)
NO_CONNECT = {
    "U1": ["13", "12", "11", "10", "9", "7"],                          # Y2..Y7: ports 10..15 not used by this card
    "U2": ["11"],                                                      # gate 4 output
    "U3": ["3", "6", "11"],                                            # -Q1..-Q3
    "U4": ["11"],                                                      # gate 4 output
    "J1": ["4", "6", "8", "10", "12", "14", "16", "18",                # D8..D15 (8-bit mode)
           "21", "31", "32"],                                          # DMARQ, INTRQ, -IOCS16
    "J2": ["4"],                                                       # the floppy connector's +12 V: not used
}


def check():
    """Every pin of every part is either on exactly one net or listed as no-connect."""
    pins = {"U1": 16, "U2": 14, "U3": 16, "U4": 14, "U5": 20, "J1": 40, "J2": 4, "JP1": 2, "RN1": 9,
            **{r: 2 for r in ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "LED1", "LED2", "LED3",
                              "C1", "C2", "C3", "C4", "C5", "C6")}}
    seen = {}
    for net, conns in NETS.items():
        for ref, pin in conns:
            if (ref, pin) in seen: raise SystemExit("%s.%s on %s and %s" % (ref, pin, seen[(ref, pin)], net))
            seen[(ref, pin)] = net
    problems = []
    for ref, n in pins.items():
        for p in range(1, n + 1):
            if (ref, str(p)) not in seen and str(p) not in NO_CONNECT.get(ref, []):
                problems.append("%s.%d unconnected" % (ref, p))
            if (ref, str(p)) in seen and str(p) in NO_CONNECT.get(ref, []):
                problems.append("%s.%d is on %s but listed as no-connect" % (ref, p, seen[(ref, str(p))]))
    for net, conns in NETS.items():
        if len(conns) < 2 and net not in ("SRST",): problems.append("net %s has %d pin(s)" % (net, len(conns)))
    return problems


if __name__ == "__main__":
    p = check()
    print("\n".join(p) if p else "cf_netlist: %d parts, %d nets, every pin accounted for" % (len(PARTS), len(NETS)))
