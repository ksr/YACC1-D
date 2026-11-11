# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""v30_netlist.py - the YACC1 video card V3: THE single source of its circuit (first cut, 2026-11-11).

The card: an HD63484P8 ACRTC on I/O ports PA-PD, 640 x 480 VGA from a 25.175 MHz dot clock, a frame buffer of two
128K x 8 static RAMs with the font EPROM in the upper half of its address space, the PS/2 keyboard and mouse section
of the V2.0 card on ports PE / PF. The design note is docs/cards/video-v3.md: section 5 the bus side, 10a the parts,
10b the memory cycle and every equation used here. Plain Python data, no KiCad import; the generator for the
schematic and the board (as V2.0's gen_v20.py reads v20_netlist.py) is still to be written.

THIS IS A FIRST CUT, NOT A BOARD YET. In it: the bus and port decode, the chip, the dot counter that keeps step with
the chip's MCYC, the address latches, RAM, EPROM and their control (section 10b's table, gate for gate), the shift
registers, the control register taken from the chip's attribute byte (three colour bits, the two syncs'
polarity), blanking in step with the dots, the VGA output, the PS/2 section. Not in it yet, and to be added before
the generator runs (OPEN below): the cursor outputs, and text method A's sockets (the character generator laid
over the graphics).

Pin numbers are the physical DIP pins. Bus pins: the V3.2 DIN 41612 connector (docs/system/BUS.md), as on V2.0.
Net names ending in # are active low. `python3 v30_netlist.py` runs check(): every pin of every part is on a net or
listed in NO_CONNECT, no net has a single pin, no two outputs share a net.
"""

CARD = "YACC1 video card"
REV = "V3.0"
DATE = "2026-11-11"

DIP = {n: "Package_DIP:DIP-%d_W7.62mm" % n for n in (14, 16, 20, 28)}
DIPW = {n: "Package_DIP:DIP-%d_W15.24mm" % n for n in (28, 32)}
FP_R = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"
FP_C = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm"            # 0.1-inch leads: the rule for every bypass capacitor
FP_H = "Connector_PinHeader_2.54mm:PinHeader_1x%02d_P2.54mm_Vertical"
FP_RN = "Resistor_THT:R_Array_SIP9"
LOCAL = "video-v3.0-local"
BUSLIB = "blank-card-v3.2-eagle"

# ---- parts: reference -> (value, symbol lib:name, footprint lib:name, note) ------------------------------------------
PARTS = {
    "X1":   ("DIN41612 96", BUSLIB + ":FABC96R", BUSLIB + ":FABC96R", "bus connector (blank V3.2 card)"),
    # --- the chip and the bus side
    "IC1":  ("HD63484P8", LOCAL + ":HD63484", "Package_DIP:DIP-64_W22.86mm", "ACRTC on ports PA-PD, 8-bit host bus"),
    "IC2":  ("74HCT138", "74xx:74LS138", DIP[16], "write strobes: Y2 OUT PA, Y3 OUT PB, Y6 OUT PE"),
    "IC3":  ("74HCT138", "74xx:74LS138", DIP[16], "read strobes: Y4 IN PC, Y5 IN PD, Y6 IN PE, Y7 IN PF"),
    "IC4":  ("74HCT21", "74xx:74LS21", DIP[14], "the chip's CS = the AND of its four port strobes"),
    "IC5":  ("74HCT245", "74xx:74LS245", DIP[20], "the chip's D0-7 to the bus DATA0-7"),
    # --- clock and control
    "OSC1": ("25.175MHz", "Oscillator:CXO_DIP14", "Oscillator:Oscillator_DIP-14", "dot clock, in a socket"),
    "IC6":  ("74F163", "74xx:74LS161", DIP[16], "dot counter: QB = 2CLK, QC follows MCYC (loaded in dots 3 and 7)"),
    "IC7":  ("74F74", "74xx:74LS74", DIP[14], "A: the RAM's -WE (dots 5 and 6 of a write); B: VALID (AS came)"),
    "IC16": ("74ACT04", "74xx:74LS04", DIP[14], "NOT AS, MCYC, QB, QC, MA19, DISP1"),
    "IC17": ("74ACT02", "74xx:74LS02", DIP[14], "W = NOR(DRAW, MRD): a drawing write; the three guns' gates"),
    "IC18": ("74ACT10", "74xx:74LS10", DIP[14], "the -WE flip-flop's D; the counter's -LOAD; the blanked dot"),
    "IC19": ("74ACT11", "74xx:74LS11", DIP[14], "dot 7; the shift registers' load"),
    "IC20": ("74ACT32", "74xx:74LS32", DIP[14], "the MAD buffers' enable; the font copy's enable"),
    "IC21": ("74ACT08", "74xx:74LS08", DIP[14], "the read half of the buffers' enable"),
    "IC31": ("74ACT00", "74xx:74LS00", DIP[14], "the control register's two enables (dot 7, HSYNC low / high)"),
    "IC32": ("74ACT86", "74xx:74LS86", DIP[14], "the two syncs' polarity"),
    "IC33": ("74F74", "74xx:74LS74", DIP[14], "blanking in step with the dots: DISP1 taken at a load, then on the dot clock"),
    "IC34": ("74ACT377", "74xx:74LS377", DIP[20], "the attribute byte, taken at the end of every cycle while HSYNC is low"),
    "IC35": ("74ACT377", "74xx:74LS377", DIP[20], "the control register: IC34 copied while HSYNC is high"),
    # --- memory
    "IC8":  ("74ACT573", "74xx:74LS573", DIP[20], "address latch A0-7 (open while AS is low)"),
    "IC9":  ("74ACT573", "74xx:74LS573", DIP[20], "address latch A8-15"),
    "IC10": ("AS6C1008-55PCN", LOCAL + ":SRAM_DIP32", DIPW[32], "frame buffer, the word's low byte (128K; the 512K part fits)"),
    "IC11": ("AS6C1008-55PCN", LOCAL + ":SRAM_DIP32", DIPW[32], "frame buffer, the word's high byte"),
    "IC12": ("74ACT245", "74xx:74LS245", DIP[20], "RAM data low byte to MAD0-7 (drawing cycles)"),
    "IC13": ("74ACT245", "74xx:74LS245", DIP[20], "RAM data high byte to MAD8-15"),
    "IC14": ("27C256", "Memory_EPROM:27C256", DIPW[28], "the font, where MA19 is high (firmware/video/font-v3.bin)"),
    "IC15": ("74HCT244", "74xx:74LS244", DIP[20], "the font's byte onto the high half of the word"),
    # --- dots
    "IC22": ("74F299", "74xx:74LS299", DIP[20], "shift register, dots 8-15 of the word"),
    "IC23": ("74F299", "74xx:74LS299", DIP[20], "shift register, dots 0-7; QH' is the video"),
    "J1":   ("VGA", "Connector:DE15_Socket_HighDensity_MountingHoles", LOCAL + ":DE15_HD_RA", "monitor: 1 R, 2 G, 3 B, 13 HSYNC, 14 VSYNC"),
    "R2":   ("470", "Device:R", FP_R, "video to R (0.7 V into 75 ohm)"),
    "R3":   ("470", "Device:R", FP_R, "video to G"),
    "R4":   ("470", "Device:R", FP_R, "video to B"),
    "R5":   ("68", "Device:R", FP_R, "HSYNC series"),
    "R6":   ("68", "Device:R", FP_R, "VSYNC series"),
    # --- PS/2 (the V2.0 card's section; embedded/video-ps2)
    "IC24": ("ATmega328P-P", "MCU_Microchip_ATmega:ATmega48PV-10P", DIP[28], "PS/2 controller"),
    "IC25": ("74HCT374", "74xx:74LS374", DIP[20], "PS/2 data latch (IN PF)"),
    "IC26": ("74HCT374", "74xx:74LS374", DIP[20], "PS/2 command latch (OUT PE)"),
    "IC27": ("74HCT244", "74xx:74LS244", DIP[20], "card status (IN PE): FULL SRC BUSY TEXT, the ID 0110"),
    "IC28": ("74HCT74", "74xx:74LS74", DIP[14], "FULL and BUSY flags"),
    "IC29": ("7416", "74xx:74LS05", DIP[14], "open collector: the ATmega's reset, -INT"),
    "IC30": ("74HCT08", "74xx:74LS08", DIP[14], "-RESET buffers (the chip's RES and DACK; the ATmega's); INTREQ AND FULL; FULL's clear"),
    "Y1":   ("16MHz", "Device:Crystal", "Crystal:Crystal_HC49-U_Vertical", "ATmega clock"),
    "J2":   ("KEYBOARD", LOCAL + ":MINIDIN6", LOCAL + ":MiniDIN6_MD-60SM", "PS/2 keyboard (Same Sky MD-60SM)"),
    "J3":   ("MOUSE", LOCAL + ":MINIDIN6", LOCAL + ":MiniDIN6_MD-60SM", "PS/2 mouse (Same Sky MD-60SM)"),
    "F1":   ("0.5A PTC", "Device:Polyfuse", "Fuse:Fuse_Bourns_MF-RHT050", "PS/2 +5 V, resettable"),
    "J4":   ("FTDI", "Connector_Generic:Conn_01x06", FP_H % 6, "GND CTS VCC(nc) TXD RXD DTR: bootloader, console"),
    "R7":   ("10k", "Device:R", FP_R, "ATmega reset pull-up"),
    "R8":   ("4.7k", "Device:R", FP_R, "RESETH pull-up (bus -RESET to MRST through IC29)"),
    "R9":   ("10k", "Device:R", FP_R, "LDDATA pull-up"),
    "R10":  ("10k", "Device:R", FP_R, "RDCMD pull-up"),
    "R11":  ("10k", "Device:R", FP_R, "INTREQ pull-down"),
    "R12":  ("4.7k", "Device:R", FP_R, "keyboard clock pull-up"),
    "R13":  ("4.7k", "Device:R", FP_R, "keyboard data pull-up"),
    "R14":  ("4.7k", "Device:R", FP_R, "mouse clock pull-up"),
    "R15":  ("4.7k", "Device:R", FP_R, "mouse data pull-up"),
    "C40":  ("22p", "Device:C", FP_C, "Y1 load"),
    "C41":  ("22p", "Device:C", FP_C, "Y1 load"),
    "C42":  ("100n", "Device:C", FP_C, "FTDI DTR auto-reset"),
    # --- passives, jumpers
    "R1":   ("10k", "Device:R", FP_R, "the chip's DONE pull-up"),
    "R16":  ("10k", "Device:R", FP_R, "TEXT pull-down: IN PE bit 3 = 0 until method A's parts and JP3 are fitted"),
    "R17":  ("330", "Device:R", FP_R, "PWR LED"),
    "R18":  ("1k", "Device:R", FP_R, "PU: the F parts' unused inputs high"),
    "LED1": ("PWR", "Device:LED", "LED_THT:LED_D5.0mm", "power"),
    "RN1":  ("10k x8", "Device:R_Network08", FP_RN, "MAD0-7 pull-ups (MAD floats in a display cycle's data half)"),
    "RN2":  ("10k x8", "Device:R_Network08", FP_RN, "MAD8-15 pull-ups"),
    "RN3":  ("10k x8", "Device:R_Network08", FP_RN, "RAM data low byte pull-ups (undriven at the start of a write cycle)"),
    "RN4":  ("10k x8", "Device:R_Network08", FP_RN, "RAM data high byte pull-ups"),
    "RN5":  ("10k x8", "Device:R_Network08", FP_RN, "the chip's D0-7 pull-ups (undriven between accesses)"),
    "JP1":  ("IRQ-EN", "Connector_Generic:Conn_01x02", FP_H % 2, "fitted: the chip's IRQ reaches -INT"),
    "JP2":  ("KBD-INT", "Connector_Generic:Conn_01x02", FP_H % 2, "fitted: the PS/2 section may drive -INT"),
    "JP3":  ("TEXT", "Connector_Generic:Conn_01x02", FP_H % 2, "fitted with method A's parts: IN PE bit 3 = 1"),
    "JP4":  ("RAM 128K/512K", "Connector_Generic:Conn_01x03", FP_H % 3, "the RAMs' pin 30: 1-2 CE2 high (128K), 2-3 A17 (512K)"),
    "C1":   ("47u 16V", "Device:C_Polarized", "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm", "bulk"),
}
DECOUPLE = {"C%d" % (n + 1): "IC%d" % n for n in range(1, 36)}          # C2..C36, one for each IC
DECOUPLE["C37"] = "IC1"                                                   # the chip's second Vcc pin
DECOUPLE["C38"] = "OSC1"
DECOUPLE["C39"] = "IC24"                                                  # the ATmega's AVCC
for cap, ic in DECOUPLE.items():
    PARTS[cap] = ("100n", "Device:C", FP_C, "%s decoupling" % ic)

# every pin a part has, for check(): DIP pins by number, the others by name
PINS = {"X1": ["%s%d" % (r, n) for r in "ABC" for n in range(1, 33)],
        "OSC1": ["1", "7", "8", "14"], "J1": [str(n) for n in range(16)], "Y1": ["1", "2"], "F1": ["1", "2"],
        "J2": ["1", "2", "3", "4", "5", "6", "S"], "J3": ["1", "2", "3", "4", "5", "6", "S"], "LED1": ["1", "2"]}
for ref, (val, sym, fp, note) in PARTS.items():
    if ref in PINS: continue
    if ref.startswith("IC"): PINS[ref] = [str(n) for n in range(1, int(fp.split("DIP-")[1].split("_")[0]) + 1)]
    elif ref.startswith("RN"): PINS[ref] = [str(n) for n in range(1, 10)]
    elif ref.startswith(("JP", "J4")): PINS[ref] = [str(n) for n in range(1, int(fp.split("_1x")[1][:2]) + 1)]
    else: PINS[ref] = ["1", "2"]                                           # R, C

POWER_PINS = {  # ref -> (VCC pins, GND pins)
    "IC1": ((14, 49), (16, 51)), "IC10": ((32,), (16,)), "IC11": ((32,), (16,)), "IC14": ((28,), (14,)),
    "IC24": ((7, 20), (8, 22)),
}
for ref, (val, sym, fp, note) in PARTS.items():
    if ref.startswith("IC") and ref not in POWER_PINS:
        n = len(PINS[ref])
        POWER_PINS[ref] = ((n,), (n // 2,))                                # the corner pins of a 14, 16 or 20 pin DIP

NETS = {}


def c(net, *pins):
    """connect pins ("REF.PIN") to net"""
    for p in pins:
        ref, pin = p.rsplit(".", 1)
        NETS.setdefault(net, []).append((ref, pin))


# ---- power -----------------------------------------------------------------------------------------------------------
for ref, (vcc, gnd) in POWER_PINS.items():
    c("VCC", *["%s.%d" % (ref, p) for p in vcc]); c("GND", *["%s.%d" % (ref, p) for p in gnd])
for cap in DECOUPLE:
    c("VCC", cap + ".1"); c("GND", cap + ".2")
c("VCC", "C1.1", "OSC1.14", *["X1.%s" % p for p in ("A2", "B2", "C2", "A31", "B31", "C31")])
c("GND", "C1.2", "OSC1.7", *["X1.%s" % p for p in ("A1", "B1", "C1", "A32", "B32", "C32")])
c("VCC", "R17.1"); c("LEDA", "R17.2", "LED1.2"); c("GND", "LED1.1")
c("VCC", "R18.1"); PU = "PU"                                               # the F parts' tie-high net (R18)
c(PU, "R18.2")

# ---- the bus ---------------------------------------------------------------------------------------------------------
for i in range(8):
    c("DATA%d" % i, "X1.A%d" % (19 + i))
for i in range(4):
    c("IO-ADDR%d" % i, "X1.C%d" % (7 + i))
c("-IO-RD", "X1.B25"); c("-IO-WR", "X1.B26"); c("-RESET", "X1.C30"); c("-INT", "X1.C13")

# ---- ports: IC2 (writes), IC3 (reads), IC4 (CS) - docs/cards/video-v3.md 10a -------------------------------------------
for ic, strobe in (("IC2", "-IO-WR"), ("IC3", "-IO-RD")):
    c("IO-ADDR0", ic + ".1"); c("IO-ADDR1", ic + ".2"); c("IO-ADDR2", ic + ".3"); c("IO-ADDR3", ic + ".6")
    c(strobe, ic + ".4"); c("GND", ic + ".5")
c("WRPA#", "IC2.13", "IC4.1"); c("WRPB#", "IC2.12", "IC4.2"); c("WRPE#", "IC2.9", "IC26.11", "IC28.11")
c("RDPC#", "IC3.11", "IC4.4"); c("RDPD#", "IC3.10", "IC4.5")
c("RDPE#", "IC3.9", "IC27.1", "IC27.19"); c("RDPF#", "IC3.7", "IC25.1", "IC30.12")
c("CS#", "IC4.6", "IC1.4", "IC5.19")
c("GND", "IC4.9", "IC4.10", "IC4.12", "IC4.13")                           # the spare half

# ---- the chip's host side: IC1, IC5 ----------------------------------------------------------------------------------
c("IO-ADDR2", "IC1.3", "IC5.1")                                           # R/W; the '245: high = chip (A) to bus (B)
c("IO-ADDR0", "IC1.5")                                                    # RS
for i in range(8):
    c("HD%d" % i, "IC1.%d" % (17 + i), "IC5.%d" % (2 + i), "RN5.%d" % (2 + i)); c("DATA%d" % i, "IC5.%d" % (18 - i))
c("VCC", "RN5.1")
c("-RESET", "IC30.1", "IC30.9"); c("VCC", "IC30.2", "IC30.10")
c("RESB#", "IC30.3", "IC1.6", "IC1.9")                                    # RES, and DACK with it: the 8-bit bus
c("DONE#", "IC1.7", "R1.1"); c("VCC", "R1.2"); c("GND", "IC1.64")        # LPSTB grounded
c("IRQ#", "IC1.11", "JP1.1"); c("-INT", "JP1.2")

# ---- the dot clock and the counter: OSC1, IC6 (docs/cards/video-v3.md 10b) ---------------------------------------------
c("CK", "OSC1.8", "IC6.2", "IC7.3", "IC22.12", "IC23.12", "IC33.11", "IC34.11", "IC35.11")
c(PU, "IC6.1", "IC6.7", "IC6.10")                                         # -CLR, ENP, ENT
c("GND", "IC6.3", "IC6.4", "IC6.6")                                       # A, B, D load 0
c("MCYC", "IC1.52", "IC16.3"); c("MCYCN", "IC16.4", "IC6.5")              # C loads NOT MCYC
c("QA", "IC6.14", "IC18.3", "IC19.1"); c("2CLK", "IC6.13", "IC1.50", "IC18.4", "IC19.2", "IC16.5")     # QB
c("QC", "IC6.12", "IC19.13", "IC18.1", "IC16.9")
c("VCC", "IC18.5"); c("LD163#", "IC18.6", "IC6.9")                        # NAND(QA, QB): dots 3 and 7
c("QBN", "IC16.6", "IC18.2", "IC21.2"); c("QCN", "IC16.8", "IC20.2", "IC7.11")

# ---- the chip's memory side: the address latches IC8 / IC9, MAD's pull-ups ---------------------------------------------
MAD = {0: 61, 1: 60, 2: 59, 3: 58, 4: 57, 5: 48, 6: 47, 7: 46, 8: 45, 9: 44, 10: 43, 11: 42, 12: 41, 13: 40, 14: 39, 15: 38}
RAM_A = {0: 12, 1: 11, 2: 10, 3: 9, 4: 8, 5: 7, 6: 6, 7: 5, 8: 27, 9: 26, 10: 23, 11: 25, 12: 4, 13: 28, 14: 3, 15: 31, 16: 2}
RAM_D = (13, 14, 15, 17, 18, 19, 20, 21)
ROM_A = {0: 10, 1: 9, 2: 8, 3: 7, 4: 6, 5: 5, 6: 4, 7: 3, 8: 25, 9: 24, 10: 21, 11: 23, 12: 2, 13: 26, 14: 27}
ROM_D = (11, 12, 13, 15, 16, 17, 18, 19)
for i in range(16):
    latch, rn, k = ("IC8", "RN1", i) if i < 8 else ("IC9", "RN2", i - 8)
    c("MAD%d" % i, "IC1.%d" % MAD[i], "%s.%d" % (latch, 2 + k), "%s.%d" % (rn, 2 + k))
    c("A%d" % i, "%s.%d" % (latch, 19 - k), "IC10.%d" % RAM_A[i], "IC11.%d" % RAM_A[i])
    if i in ROM_A: c("A%d" % i, "IC14.%d" % ROM_A[i])
c("VCC", "RN1.1", "RN2.1"); c("GND", "IC8.1", "IC9.1")
c("AS#", "IC1.53", "IC16.1", "IC7.10"); c("ASN", "IC16.2", "IC8.11", "IC9.11")       # LE = NOT AS; AS presets VALID
c("MA16", "IC1.37", "IC10.2", "IC11.2")
c("MA17", "IC1.36", "JP4.3"); c("VCC", "JP4.1"); c("RSEL", "JP4.2", "IC10.30", "IC11.30")
c("MA18", "IC1.35", "IC10.1", "IC11.1")                                   # NC on the 128K part, A18 on the 512K one
c("MA19", "IC1.34", "IC10.22", "IC11.22", "IC16.11")                      # the RAMs' -CE
c("MA19N", "IC16.10", "IC14.20", "IC20.9")                                # the EPROM's -CE

# ---- RAM data, the MAD buffers IC12 / IC13, the font IC14 and its copy IC15 --------------------------------------------
for i in range(8):
    c("DL%d" % i, "IC10.%d" % RAM_D[i], "IC12.%d" % (2 + i), "IC14.%d" % ROM_D[i], "RN3.%d" % (2 + i))
    c("DH%d" % i, "IC11.%d" % RAM_D[i], "IC13.%d" % (2 + i), "RN4.%d" % (2 + i))
    c("MAD%d" % i, "IC12.%d" % (18 - i)); c("MAD%d" % (8 + i), "IC13.%d" % (18 - i))
c("VCC", "RN3.1", "RN4.1", "IC14.1")                                      # the EPROM's Vpp
for i, (a, y) in enumerate(((2, 18), (4, 16), (6, 14), (8, 12), (11, 9), (13, 7), (15, 5), (17, 3))):
    c("DL%d" % i, "IC15.%d" % a); c("DH%d" % i, "IC15.%d" % y)

# ---- memory control (10b): W, -OE, -WE, the buffers' enable, VALID, the load -------------------------------------------
c("DRAW#", "IC1.54", "IC17.2", "IC20.1", "IC19.4"); c("MRD", "IC1.55", "IC17.3", "IC21.1", "IC12.1", "IC13.1")
c("W", "IC17.1", "IC10.24", "IC11.24", "IC14.22", "IC18.13", "IC20.10")   # the RAMs' and the EPROM's -OE
c("WED", "IC18.12", "IC7.2"); c("WE#", "IC7.5", "IC10.29", "IC11.29")     # D = NAND(QC, NOT QB, W); Q low in dots 5, 6
c(PU, "IC7.1", "IC7.4", "IC7.13")
c("GND", "IC7.12"); c("VALID", "IC7.9", "IC19.5")                         # B: D = 0 clocked by NOT QC, preset by AS
c("RDHOLD", "IC21.3", "IC20.5"); c("E1", "IC20.3", "IC20.4")              # MRD AND NOT QB; DRAW OR NOT QC
c("BUFEN#", "IC20.6", "IC12.19", "IC13.19")
c("F244#", "IC20.8", "IC15.1", "IC15.19")                                 # NOT MA19 OR W
c("DOT7", "IC19.12", "IC19.3", "IC31.4", "IC31.9"); c("LOAD", "IC19.6", "IC22.19", "IC23.19", "IC33.3")
c("GND", "IC19.9", "IC19.10", "IC19.11", "IC20.12", "IC20.13")            # a spare AND, a spare OR
c("GND", "IC21.4", "IC21.5", "IC21.9", "IC21.10", "IC21.12", "IC21.13")   # three spare ANDs

# ---- the shift registers IC22 (dots 8-15) and IC23 (dots 0-7) and the video --------------------------------------------
IO299 = {0: 7, 1: 13, 2: 6, 3: 14, 4: 5, 5: 15, 6: 4, 7: 16}
for i in range(8):
    c("DL%d" % i, "IC23.%d" % IO299[7 - i]); c("DH%d" % i, "IC22.%d" % IO299[7 - i])       # bit 0 leaves first
c(PU, "IC22.1", "IC22.2", "IC22.3", "IC22.9", "IC23.1", "IC23.2", "IC23.3", "IC23.9")      # S0, both -OE, -MR
c("GND", "IC22.11", "IC22.18", "IC23.18"); c("SR8", "IC22.17", "IC23.11")
# blanking in step with the dots (10b): DISP1 is taken when a word is loaded (IC33/A, clocked by LOAD in dot 7) and passed
# on by the dot clock (IC33/B), so the picture goes on and off on a word's first dot
c("DISP1#", "IC1.63", "IC16.13"); c("DISPON", "IC16.12", "IC33.2"); c("DISPA", "IC33.5", "IC33.12")
c(PU, "IC33.1", "IC33.4", "IC33.10", "IC33.13")
c("DISPQ", "IC33.9", "IC18.9"); c("VDOT", "IC23.17", "IC18.10"); c("VCC", "IC18.11")
c("VIDN", "IC18.8", "IC17.5", "IC17.8", "IC17.11")                       # NAND(the dot, display on)
# the control register (10b): the attribute byte is on MAD in the data half of the last cycle before HSYNC rises. IC34
# takes MAD0-7 at the end of every cycle while HSYNC is low - the last one leaves the attribute byte in it - and IC35
# copies IC34 at the end of every cycle while HSYNC is high, so IC35 never shows what IC34 holds in between.
# Bits (the chip's DCR, ATR): 0, 1, 2 = red, green, blue OFF (0 = on: ATR 00 is white); 3, 4 = HSYNC, VSYNC positive
# (0 = negative, what 640 x 480 wants); 5, 6 for text method A (the layer on, XOR instead of OR); 7 spare
c("HSYNC#", "IC1.12", "IC31.1", "IC31.2", "IC31.10", "IC32.1"); c("HSLOW", "IC31.3", "IC31.5")
c("ATE1#", "IC31.6", "IC34.1"); c("ATE2#", "IC31.8", "IC35.1"); c("GND", "IC31.12", "IC31.13")
Q377 = ((3, 2), (4, 5), (7, 6), (8, 9), (13, 12), (14, 15), (17, 16), (18, 19))       # (D, Q) bits 0..7
for i, (d, q) in enumerate(Q377):
    c("MAD%d" % i, "IC34.%d" % d); c("AT%d" % i, "IC34.%d" % q, "IC35.%d" % d)
c("OFFR", "IC35.2", "IC17.6"); c("OFFG", "IC35.5", "IC17.9"); c("OFFB", "IC35.6", "IC17.12")
c("POLH", "IC35.9", "IC32.2"); c("POLV", "IC35.12", "IC32.5")
c("VR", "IC17.4", "R2.1"); c("VG", "IC17.10", "R3.1"); c("VB", "IC17.13", "R4.1")
c("RED", "R2.2", "J1.1"); c("GREEN", "R3.2", "J1.2"); c("BLUE", "R4.2", "J1.3")
c("VSYNC#", "IC1.13", "IC32.4"); c("GND", "IC32.9", "IC32.10", "IC32.12", "IC32.13")
c("HSB", "IC32.3", "R5.1"); c("HSOUT", "R5.2", "J1.13"); c("VSB", "IC32.6", "R6.1"); c("VSOUT", "R6.2", "J1.14")
c("GND", "J1.5", "J1.6", "J1.7", "J1.8", "J1.10", "J1.0")

# ---- PS/2: IC24 ATmega328P, latches IC25 / IC26, status IC27, flags IC28, IC29, IC30 (V2.0's nets, new ports) --------
c("MRST", "IC24.1", "R7.1", "C42.2", "IC29.12"); c("VCC", "R7.2")
c("RESETB", "IC30.8", "IC29.11"); c("RESETH", "IC29.10", "R8.1", "IC29.13"); c("VCC", "R8.2")
c("FTX", "IC24.2", "J4.4"); c("FRX", "IC24.3", "J4.5"); c("FDTR", "J4.6", "C42.1"); c("GND", "J4.1", "J4.2")
c("KCLK", "IC24.4", "R12.1", "J2.5"); c("MCLK", "IC24.5", "R14.1", "J3.5")
c("KDAT", "IC24.6", "R13.1", "J2.1"); c("MDAT", "IC24.11", "R15.1", "J3.1")
c("VCC", "R12.2", "R13.2", "R14.2", "R15.2", "F1.1"); c("PS2VCC", "F1.2", "J2.4", "J3.4")
c("GND", "J2.3", "J3.3", "J2.S", "J3.S")
c("XT1", "IC24.9", "Y1.1", "C40.1"); c("XT2", "IC24.10", "Y1.2", "C41.1"); c("GND", "C40.2", "C41.2")
c("LDDATA", "IC24.12", "IC25.11", "IC28.3", "R9.1"); c("RDCMD", "IC24.13", "IC26.1", "IC28.13", "R10.1")
c("VCC", "R9.2", "R10.2")
L374 = ((3, 2), (4, 5), (7, 6), (8, 9), (13, 12), (14, 15), (17, 16), (18, 19))   # (D, Q) bits 0..7
for i, pin in enumerate((23, 24, 25, 26, 27, 28, 14, 15)):
    c("MD%d" % i, "IC24.%d" % pin)
for i, (d, q) in enumerate(L374):
    c("MD%d" % i, "IC25.%d" % d, "IC26.%d" % q); c("DATA%d" % i, "IC25.%d" % q, "IC26.%d" % d)
c("FULL", "IC24.16", "IC28.5", "IC27.2", "IC30.5"); c("SRC", "IC24.19", "IC27.4")
c("INTREQ", "IC24.18", "IC30.4", "R11.1"); c("GND", "R11.2"); c("INTG", "IC30.6", "IC29.9")
c("BUSY", "IC24.17", "IC28.9", "IC27.6")
c("TEXT", "IC27.8", "R16.1", "JP3.1"); c("GND", "R16.2"); c("VCC", "JP3.2")
c("DATA0", "IC27.18"); c("DATA1", "IC27.16"); c("DATA2", "IC27.14"); c("DATA3", "IC27.12")
c("DATA4", "IC27.9"); c("DATA5", "IC27.7"); c("DATA6", "IC27.5"); c("DATA7", "IC27.3")
c("GND", "IC27.11", "IC27.17"); c("VCC", "IC27.13", "IC27.15")           # bits 7..4 = 0110: the ID $6x
c("VCC", "IC28.2", "IC28.4", "IC28.12", "IC28.10")                       # D high, -PRE high
c("-RESET", "IC30.13"); c("FULLCLR", "IC30.11", "IC28.1")                # IN PF or -RESET clears FULL
c("INTOC", "IC29.8", "JP2.1"); c("-INT", "JP2.2")
c("GND", "IC29.1", "IC29.3", "IC29.5")                                    # three spare inverters

# ---- pins left open ----------------------------------------------------------------------------------------------------
NO_CONNECT = {
    "IC1": [1, 2, 8, 10, 15, 25, 26, 27, 28, 29, 30, 31, 32, 33, 56, 62],   # CUD1/2, DREQ, DTACK, EXSYNC, D8-15, RA4, CHR, DISP2
    "IC2": [15, 14, 11, 10, 7], "IC3": [15, 14, 13, 12], "IC4": [3, 11, 8],
    "IC6": [11, 15], "IC7": [6, 8], "IC19": [8], "IC20": [11], "IC21": [6, 8, 11], "IC22": [8], "IC23": [8],
    "IC31": [11], "IC32": [8, 11], "IC33": [6, 8], "IC35": [15, 16, 19],     # ATR bits 5-7: text method A, a spare
    "IC24": [21], "IC28": [6, 8], "IC29": [2, 4, 6], "J4": [3], "J2": [2, 6], "J3": [2, 6],
    "J1": [4, 9, 11, 12, 15], "OSC1": [1],
    "X1": [p for p in PINS["X1"] if p not in ("A1", "B1", "C1", "A32", "B32", "C32", "A2", "B2", "C2", "A31", "B31", "C31",
                                              "B25", "B26", "C30", "C13", "C7", "C8", "C9", "C10") and
           p not in ["A%d" % n for n in range(19, 27)]],
}
NO_CONNECT = {r: [str(p) for p in ps] for r, ps in NO_CONNECT.items()}

# what the first cut leaves out (docs/cards/video-v3.md 10b): the pins they will use are in NO_CONNECT until then
OPEN = ("the cursor outputs CUD1 / CUD2 into the video",
        "text method A: the character latch, the character generator, its shift register, CHR and RA0-RA4")

# outputs that drive a net (for check(): no two on one net). The bus, MAD, DL / DH and HD are shared by three-state
# parts enabled at different times, and -INT by open collectors: those nets are left out.
SHARED = ("DATA", "MAD", "DL", "DH", "HD", "-INT", "MD")        # (AT0-7 are IC34's outputs alone)
OUTPUTS = {"IC2": (13, 12, 9), "IC3": (11, 10, 9, 7), "IC4": (6,), "IC6": (14, 13, 12), "IC7": (5, 9),
           "IC16": (2, 4, 6, 8, 10, 12), "IC17": (1, 4, 10, 13), "IC18": (12, 6, 8), "IC19": (12, 6), "IC20": (3, 6, 8),
           "IC21": (3,), "IC31": (3, 6, 8), "IC32": (3, 6), "IC33": (5, 9), "IC34": (2, 5, 6, 9, 12, 15, 16, 19),
           "IC35": (2, 5, 6, 9, 12), "IC22": (17,), "IC23": (17,), "IC28": (5, 9), "IC29": (8, 10, 12), "IC30": (3, 6, 8, 11),
           "IC1": (52, 53, 54, 55, 34, 35, 36, 37, 12, 13, 63, 11), "OSC1": (8,),
           "IC8": tuple(range(12, 20)), "IC9": tuple(range(12, 20))}


def check():
    """every pin accounted for once, no single-pin net, no two outputs on a net; returns the list of faults"""
    faults = []
    seen = {}
    for net, pins in NETS.items():
        for ref, pin in pins:
            if ref not in PARTS: faults.append("%s: %s is not a part" % (net, ref)); continue
            if pin not in PINS[ref]: faults.append("%s: %s has no pin %s" % (net, ref, pin))
            if (ref, pin) in seen and seen[(ref, pin)] != net:
                faults.append("%s.%s is on %s and on %s" % (ref, pin, seen[(ref, pin)], net))
            seen[(ref, pin)] = net
    for ref, pins in NO_CONNECT.items():
        for pin in pins:
            if (ref, pin) in seen: faults.append("%s.%s is on %s and in NO_CONNECT" % (ref, pin, seen[(ref, pin)]))
            seen[(ref, pin)] = None
    for ref in PARTS:
        for pin in PINS[ref]:
            if (ref, pin) not in seen: faults.append("%s.%s is not connected" % (ref, pin))
    for net, pins in NETS.items():
        if len(set(pins)) < 2: faults.append("net %s has one pin" % net)
        if net.rstrip("0123456789") in SHARED: continue
        drivers = [(r, p) for r, p in pins if int(p) in OUTPUTS.get(r, ()) ] if all(p.isdigit() for _, p in pins) else \
                  [(r, p) for r, p in pins if p.isdigit() and int(p) in OUTPUTS.get(r, ())]
        if len(drivers) > 1: faults.append("net %s has %d outputs: %r" % (net, len(drivers), drivers))
    return faults


if __name__ == "__main__":
    f = check()
    ics = sum(1 for r in PARTS if r.startswith("IC"))
    print("%s %s: %d parts (%d ICs), %d nets, %d pins on nets" % (CARD, REV, len(PARTS), ics, len(NETS),
                                                                 sum(len(p) for p in NETS.values())))
    for x in f: print("  " + x)
    print("open: " + "; ".join(OPEN))
    print("check: %s" % ("%d faults" % len(f) if f else "every pin accounted for, no net with one pin, no two outputs on a net"))
    raise SystemExit(1 if f else 0)
