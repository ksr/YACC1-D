# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""v30_netlist.py - the YACC1 video card V3: THE single source of its circuit (2026-11-11).

The card: an HD63484P8 ACRTC on I/O ports PA-PD, 640 x 480 VGA from a 25.175 MHz dot clock, a frame buffer of two
128K x 8 static RAMs with the font EPROM in the upper half of its address space, the PS/2 keyboard and mouse section
of the V2.0 card on ports PE / PF. The design note is docs/cards/video-v3.md: section 5 the bus side, 10a the parts,
10b the memory cycle and every equation used here, 10c text method A, 10d the simulation and the timing check.
Plain Python data, no KiCad import; the generator for the schematic and the board (as V2.0's gen_v20.py reads
v20_netlist.py) is still to be written.

NOT A BOARD YET. In it: the bus and port decode with RS and R/W held through the chip's CS, the chip, the dot counter
that keeps step with the chip's MCYC, the address latches, RAM, EPROM and their control (section 10b's table, gate
for gate), the shift registers, the control register taken from the chip's attribute byte (three colour bits, the
two syncs' polarity, the text layer's three), the VGA output, the PS/2 section. The parts are the ones the timing
check was run with (tests/video/v30_netsim.py, the data-sheet numbers of each): 74F for the counter, the
flip-flops, the shift registers and the two gates that must be fast, 74ACT for the rest of the memory side.

Rules the circuit keeps, each the result of a fault the simulation found (10d):
  * nothing is clocked, cleared or latched by a gate that decodes counter bits: P56 (IC7/A, dots 5 and 6 of every
    cycle) is the one timing signal that is used as an edge, and it is a flip-flop's output;
  * the RAMs, the font and its copy drive the RAM data lines only from the end of AS to the end of the cycle (MOE#);
  * the MAD buffers come on a dot later for a read than for a write.

Text method A (docs/cards/video-v3.md 8A, 10c): the parts in TEXT_A are sockets that the first build leaves
empty. The card works without them (the chip in interleaved access, glyphs copied in the bitmap); with them and
the chip in superimposed access a character screen of 80 x 30 is laid over the graphics. text_a_check() proves
that those parts drive nothing in the fitted logic but TDOT, which R19 holds low when they are absent.

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
# the DE-15 socket: KiCad's footprint for the common right-angle part (pins 3.03 mm, mounting holes 4.94 mm from the edge)
FP_VGA = "Connector_Dsub:DSUB-15-HD_Socket_Horizontal_P2.29x1.90mm_EdgePinOffset3.03mm_Housed_MountingHolesOffset4.94mm"
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
    "IC39": ("74HCT573", "74xx:74LS573", DIP[20], "RS and R/W held while CS is low (an IN record drops the port number with its strobe)"),
    # --- clock and control
    "OSC1": ("25.175MHz", "Oscillator:CXO_DIP14", "Oscillator:Oscillator_DIP-14", "dot clock, in a socket"),
    "IC6":  ("74F163A", "74xx:74LS161", DIP[16], "dot counter: QB = 2CLK, QC follows MCYC (loaded in dots 3 and 7)"),
    "IC7":  ("74F74", "74xx:74LS74", DIP[14], "A: P56, dots 5 and 6 of every cycle (the RAM's -WE, the attribute register's clock, a read's buffers); B: VALID (AS came: the memories' outputs)"),
    "IC16": ("74ACT04", "74xx:74LS04", DIP[14], "NOT AS, MCYC, QB, QC, MA19, DISP1"),
    "IC17": ("74ACT02", "74xx:74LS02", DIP[14], "W = NOR(DRAW, MRD): a drawing write; the three guns' gates"),
    "IC18": ("74ACT10", "74xx:74LS10", DIP[14], "the P56 flip-flop's D; the memories' -OE; the blanked dot"),
    "IC19": ("74ACT11", "74xx:74LS11", DIP[14], "a Background cycle; a Window cycle; one spare"),
    "IC20": ("74ACT32", "74xx:74LS32", DIP[14], "the font copy's enable; graphics OR text; a read's buffers wait for dot 6; not a drawing write"),
    "IC21": ("74ACT08", "74xx:74LS08", DIP[14], "HSYNC buffered, the control register's clock; display on AND a read; the buffers' enable held 16 ns; the RAMs' -CE"),
    "IC37": ("74F74", "74xx:74LS74", DIP[14], "A: the MAD buffers' enable, on in dots 5-7 of a drawing write, 6-7 of a read; B: the dot retimed to the dot clock"),
    "IC38": ("74F21", "74xx:74LS21", DIP[14], "the buffers' enable flip-flop's D; the graphics load (one fast gate each from the counter)"),
    "IC31": ("74ACT00", "74xx:74LS00", DIP[14], "the counter's -LOAD; NOT DRAW; the RAM's -WE; the mixed dot"),
    "IC32": ("74ACT86", "74xx:74LS86", DIP[14], "the two syncs' polarity"),
    "IC34": ("74ACT273", "74xx:74LS273", DIP[20], "MAD0-7 as dot 7 begins, every cycle: in the last cycle before HSYNC rises, the attribute byte"),
    "IC35": ("74ACT273", "74xx:74LS273", DIP[20], "the control register: IC34 copied when HSYNC rises; -RESET clears it"),
    "IC36": ("74ACT32", "74xx:74LS32", DIP[14], "CHR into the address: a character screen is the RAM's top 64K words; the font's -CE"),
    "IC40": ("74F299", "74xx:74LS299", DIP[20], "the graphics dot delayed 8 dots (shifting only), into step with the text"),
    # --- text method A: sockets, empty on the first build (TEXT_A)
    "IC41": ("74F74", "74xx:74LS74", DIP[14], "A: the character latches' clock (after dot 3 of a Window cycle); B: WPH, the cycle after one"),
    "IC42": ("74F21", "74xx:74LS21", DIP[14], "dot 3 of a Window cycle; the text shifter's load"),
    "IC43": ("74ACT32", "74xx:74LS32", DIP[14], "a Window cycle or the one after it"),
    "IC44": ("74ACT574", "74xx:74LS574", DIP[20], "the left character's code (the word's low byte)"),
    "IC45": ("74ACT574", "74xx:74LS574", DIP[20], "the right character's code (the high byte)"),
    "IC46": ("74ACT574", "74xx:74LS574", DIP[20], "the raster line RA0-RA4 of the Window cycle"),
    "IC47": ("AT27C256R-70", "Memory_EPROM:27C256", DIPW[28], "character generator, 70 ns: line + 16 x code; A12 CUD1, A13 the second font, A14 CUD2"),
    "IC48": ("74F299", "74xx:74LS299", DIP[20], "the text's dots, 8 a character"),
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
    "J1":   ("VGA", "Connector:DE15_Socket_HighDensity_MountingHoles", FP_VGA, "monitor: 1 R, 2 G, 3 B, 13 HSYNC, 14 VSYNC; SH the shell"),
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
    "C53":  ("22p", "Device:C", FP_C, "Y1 load"),
    "C54":  ("22p", "Device:C", FP_C, "Y1 load"),
    "C55":  ("100n", "Device:C", FP_C, "FTDI DTR auto-reset"),
    # --- passives, jumpers
    "R1":   ("10k", "Device:R", FP_R, "the chip's DONE pull-up"),
    "R16":  ("10k", "Device:R", FP_R, "TEXT pull-down: IN PE bit 3 = 0 until method A's parts and JP3 are fitted"),
    "R17":  ("330", "Device:R", FP_R, "PWR LED"),
    "R18":  ("1k", "Device:R", FP_R, "PU: the F parts' unused inputs high"),
    "R19":  ("10k", "Device:R", FP_R, "TDOT pull-down: no text while method A's parts are not fitted"),
    "LED1": ("PWR", "Device:LED", "LED_THT:LED_D5.0mm", "power"),
    "RN1":  ("10k x8", "Device:R_Network08", FP_RN, "MAD0-7 pull-ups (MAD floats in a display cycle's data half)"),
    "RN2":  ("10k x8", "Device:R_Network08", FP_RN, "MAD8-15 pull-ups"),
    "RN3":  ("10k x8", "Device:R_Network08", FP_RN, "RAM data low byte pull-ups (undriven at the start of a write cycle)"),
    "RN4":  ("10k x8", "Device:R_Network08", FP_RN, "RAM data high byte pull-ups"),
    "RN5":  ("10k x8", "Device:R_Network08", FP_RN, "the chip's D0-7 pull-ups (undriven between accesses)"),
    "JP1":  ("IRQ-EN", "Connector_Generic:Conn_01x02", FP_H % 2, "fitted: the chip's IRQ reaches -INT"),
    "JP2":  ("KBD-INT", "Connector_Generic:Conn_01x02", FP_H % 2, "fitted: the PS/2 section may drive -INT"),
    "JP3":  ("TEXT", "Connector_Generic:Conn_01x02", FP_H % 2, "fitted with method A's parts: IN PE bit 3 = 1"),
    "JP4":  ("RAM 128K/512K", "Connector_Generic:Conn_01x03", FP_H % 3, "the RAMs' pin 30: 1-2 CE2 = VALID (128K), 2-3 A17 (512K)"),
    "C1":   ("47u 16V", "Device:C_Polarized", "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm", "bulk"),
}
DECOUPLE = {"C%d" % (n + 1): "IC%d" % n for n in range(1, 49) if n != 33}   # one for each IC
DECOUPLE["C50"] = "IC1"                                                   # the chip's second Vcc pin
DECOUPLE["C51"] = "OSC1"
DECOUPLE["C52"] = "IC24"                                                  # the ATmega's AVCC
for cap, ic in DECOUPLE.items():
    PARTS[cap] = ("100n", "Device:C", FP_C, "%s decoupling" % ic)

# every pin a part has, for check(): DIP pins by number, the others by name
PINS = {"X1": ["%s%d" % (r, n) for r in "ABC" for n in range(1, 33)],
        "OSC1": ["1", "7", "8", "14"], "J1": [str(n) for n in range(1, 16)] + ["SH"], "Y1": ["1", "2"], "F1": ["1", "2"],
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
# RS = IO-ADDR0 and R/W = IO-ADDR2, through a latch that is open while CS is high and holds while it is low: the port
# number is on the bus two steps before a strobe, but the microcode's IN records drop it in the same step as -IO-RD,
# and CS, two gates behind the strobe, outlasts it. The chip wants RS and R/W until CS has risen, and the bus buffer
# its direction: without the latch every IN from the chip would end as the start of a write
c("IO-ADDR0", "IC39.2"); c("IO-ADDR2", "IC39.3"); c("CS#", "IC39.11"); c("GND", "IC39.1", *["IC39.%d" % n for n in range(4, 10)])
c("RS", "IC39.19", "IC1.5"); c("RWL", "IC39.18", "IC1.3", "IC5.1")        # R/W; the '245: high = chip (A) to bus (B)
for i in range(8):
    c("HD%d" % i, "IC1.%d" % (17 + i), "IC5.%d" % (2 + i), "RN5.%d" % (2 + i)); c("DATA%d" % i, "IC5.%d" % (18 - i))
c("VCC", "RN5.1")
c("-RESET", "IC30.1", "IC30.9"); c("VCC", "IC30.2", "IC30.10")
c("RESB#", "IC30.3", "IC1.6", "IC1.9")                                    # RES, and DACK with it: the 8-bit bus
c("DONE#", "IC1.7", "R1.1"); c("VCC", "R1.2"); c("GND", "IC1.64")        # LPSTB grounded
c("IRQ#", "IC1.11", "JP1.1"); c("-INT", "JP1.2")

# ---- the dot clock and the counter: OSC1, IC6 (docs/cards/video-v3.md 10b) ---------------------------------------------
c("CK", "OSC1.8", "IC6.2", "IC7.3", "IC22.12", "IC23.12", "IC37.3", "IC37.11", "IC40.12", "IC41.3", "IC48.12")
c(PU, "IC6.1", "IC6.7", "IC6.10")                                         # -CLR, ENP, ENT
c("GND", "IC6.3", "IC6.4", "IC6.6")                                       # A, B, D load 0
c("MCYC", "IC1.52", "IC16.3"); c("MCYCN", "IC16.4", "IC6.5")              # C loads NOT MCYC
c("QA", "IC6.14", "IC31.1", "IC38.9")
c("2CLK", "IC6.13", "IC1.50", "IC31.2", "IC16.5", "IC38.10")              # QB
c("QC", "IC6.12", "IC18.1", "IC16.9", "IC38.2", "IC38.12")
c("LD163#", "IC31.3", "IC6.9", "IC38.4")                                  # NAND(QA, QB): dots 3 and 7
c("QBN", "IC16.6", "IC18.2"); c("QCN", "IC16.8", "IC7.11")

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
c("AS#", "IC1.53", "IC16.1", "IC7.10", "IC18.4"); c("ASN", "IC16.2", "IC8.11", "IC9.11")       # LE = NOT AS; AS presets VALID
# CHR (10c): in a cycle on a character screen MA16-19 are the raster line RA0-RA3, not address: IC36 forces the
# RAM's A16 (and A17, A18 of the 512K part) high and the RAM selected, so a character screen is the RAM's top
# 64K words whatever the line
c("CHR", "IC1.56", "IC36.2", "IC36.5", "IC36.10", "IC36.13", "IC32.12"); c("VCC", "IC32.13"); c("CHRN", "IC32.11", "IC21.13")
c("MA16", "IC1.37", "IC36.1", "IC46.2"); c("RA16", "IC36.3", "IC10.2", "IC11.2")
c("MA17", "IC1.36", "IC36.4", "IC46.3"); c("RA17", "IC36.6", "JP4.3"); c("VALID", "JP4.1"); c("RSEL", "JP4.2", "IC10.30", "IC11.30")
c("MA18", "IC1.35", "IC36.9", "IC46.4"); c("RA18", "IC36.8", "IC10.1", "IC11.1")     # NC on the 128K part, A18 on the 512K one
c("MA19", "IC1.34", "IC16.11", "IC21.12", "IC46.5"); c("RAMCE#", "IC21.11", "IC10.22", "IC11.22")   # MA19 AND NOT CHR
c("MA19N", "IC16.10", "IC36.12"); c("ROMCE#", "IC36.11", "IC14.20", "IC20.9")        # NOT MA19 OR CHR

# ---- RAM data, the MAD buffers IC12 / IC13, the font IC14 and its copy IC15 --------------------------------------------
for i in range(8):
    c("DL%d" % i, "IC10.%d" % RAM_D[i], "IC12.%d" % (2 + i), "IC14.%d" % ROM_D[i], "RN3.%d" % (2 + i))
    c("DH%d" % i, "IC11.%d" % RAM_D[i], "IC13.%d" % (2 + i), "RN4.%d" % (2 + i))
    c("MAD%d" % i, "IC12.%d" % (18 - i)); c("MAD%d" % (8 + i), "IC13.%d" % (18 - i))
c("VCC", "RN3.1", "RN4.1", "IC14.1")                                      # the EPROM's Vpp
for i, (a, y) in enumerate(((2, 18), (4, 16), (6, 14), (8, 12), (11, 9), (13, 7), (15, 5), (17, 3))):
    c("DL%d" % i, "IC15.%d" % a); c("DH%d" % i, "IC15.%d" % y)

# ---- memory control (10b): W, -OE, -WE, the buffers' enable, VALID, the load -------------------------------------------
c("DRAW#", "IC1.54", "IC17.2", "IC19.4", "IC19.10", "IC31.4", "IC31.5", "IC20.4"); c("DRAWN", "IC31.6", "IC38.1")
c("MRD", "IC1.55", "IC17.3", "IC12.1", "IC13.1", "IC21.4", "IC32.9", "IC20.5"); c("VCC", "IC32.10"); c("MRDN", "IC32.8", "IC19.9")
c("W", "IC17.1", "IC31.10", "IC20.2"); c("WN", "IC20.6", "IC18.5")        # a drawing write; not one (DRAW OR MRD)
# the memories' outputs (the RAMs' and the font's -OE, and with the font's -CE its copy IC15) are on from the end of
# AS to the end of the cycle, in every cycle that has an AS and is not a drawing write: MOE# = NAND(VALID, AS, NOT W).
# So every cycle begins with nothing on the RAM data lines for the two dots of AS, and the RAM and the font, which
# are chosen by MA19, never hand over to each other with both on; a dummy cycle has them off throughout. The 128K
# RAMs' second chip enable (pin 30, JP4 1-2) is VALID itself: it takes the RAM off a gate sooner at a cycle's end
c("MOE#", "IC18.6", "IC10.24", "IC11.24", "IC14.22", "IC20.10")
# P56: IC7/A's D is NAND(QC, NOT QB), low in dots 4 and 5 of every cycle, so its Q (P56#) is low and its -Q (P56) high
# in dots 5 and 6 of every cycle: a flip-flop's edges, which no decode of counter bits changing together can give.
# Three things hang on it: the RAMs' -WE = NAND(P56, W); the attribute register's clock, P56#'s rise as dot 7 begins;
# and a drawing read's buffers, which wait for it
c("VCC", "IC18.13"); c("P56D", "IC18.12", "IC7.2"); c("P56#", "IC7.5", "IC34.11"); c("P56", "IC7.6", "IC31.9", "IC20.1")
c("WE#", "IC31.8", "IC10.29", "IC11.29")
c(PU, "IC7.1", "IC7.4", "IC7.13")
c("GND", "IC7.12"); c("VALID", "IC7.9", "IC19.5", "IC19.11", "IC18.3")    # B: D = 0 clocked by NOT QC, preset by AS
# the MAD buffers (MRD is their direction) are on in dots 5, 6 and 7 of a drawing write and in dots 6 and 7 of a
# drawing read: a read's wait a dot longer because the chip may hold its address on MAD until 50 ns into dot 4's
# half, and they are off about 16 ns after the cycle's last clock edge (a read's data is wanted 10 ns after it).
# IC37/A's D = NOT DRAW AND QC AND NOT (QA AND QB) AND (P56 OR W): high in dots 4-6 of a write, 5-6 of a read, one
# 74F21 gate after the counter; its -Q goes through a gate of IC21 for those 16 ns
c("BUFT", "IC20.3", "IC38.5"); c("BUFD", "IC38.6", "IC37.2"); c("BUFQN", "IC37.6", "IC21.9"); c("VCC", "IC21.10")
c("BUFEN#", "IC21.8", "IC12.19", "IC13.19"); c(PU, "IC37.1", "IC37.4", "IC37.10", "IC37.13")
c("F244#", "IC20.8", "IC15.1", "IC15.19")                                 # the font's -CE OR MOE#
# a display cycle is the Background's (MRD high: the graphics word, loaded into IC22 / IC23) or, in superimposed
# access, the Window's (MRD low: the character word, method A)
c("GND", "IC19.1", "IC19.2", "IC19.13")                                   # a spare AND
# the graphics load: dot 7 of a Background cycle with the display on (DISP1 low), one 74F21 gate after the counter. A
# word fetched with the display off is not loaded: the shift registers then run empty, which is the blanking
c("DISP1#", "IC1.63", "IC16.13"); c("DISPON", "IC16.12", "IC21.5"); c("BGON", "IC21.6", "IC19.3")
c("DISPBG", "IC19.6", "IC38.13"); c("GLOAD", "IC38.8", "IC22.19", "IC23.19")
c("DISPWN", "IC19.8", "IC41.12", "IC42.5", "IC43.1")

# ---- the shift registers IC22 (dots 8-15) and IC23 (dots 0-7) and the video --------------------------------------------
IO299 = {0: 7, 1: 13, 2: 6, 3: 14, 4: 5, 5: 15, 6: 4, 7: 16}
for i in range(8):
    c("DL%d" % i, "IC23.%d" % IO299[7 - i]); c("DH%d" % i, "IC22.%d" % IO299[7 - i])       # bit 0 leaves first
c(PU, "IC22.1", "IC22.2", "IC22.3", "IC22.9", "IC23.1", "IC23.2", "IC23.3", "IC23.9")      # S0, both -OE, -MR
c("GND", "IC22.11", "IC22.18", "IC23.18"); c("SR8", "IC22.17", "IC23.11")
# the graphics dot 8 dots later, in step with the text (10c): IC40, a 74F299 that only shifts
c("VDOT", "IC23.17", "IC40.11"); c("GDEL", "IC40.17", "IC20.12", "IC18.9")
c(PU, "IC40.1", "IC40.2", "IC40.3", "IC40.9", "IC40.7", "IC40.13", "IC40.6", "IC40.14", "IC40.5", "IC40.15", "IC40.4", "IC40.16")
c("GND", "IC40.19", "IC40.18")                                            # S1 low: shift; the other serial input
# the two layers: T = the text dot (its shifter is held clear unless TEXTON); OR, or XOR with TXOR:
# VIDN = NAND(G OR T, NAND(G, T, TXOR)), then IC37/B puts it on the dot clock: every dot one clock wide at the guns
c("TDOT", "IC48.17", "IC20.13", "IC18.10", "R19.1"); c("GND", "R19.2"); c("TEXTON", "IC35.15", "IC48.9"); c("TXOR", "IC35.16", "IC18.11")
c("GOT", "IC20.11", "IC31.12"); c("NBX", "IC18.8", "IC31.13")
c("VIDN", "IC31.11", "IC37.12"); c("VIDQ", "IC37.9", "IC17.5", "IC17.8", "IC17.11")
# the control register (10b): the attribute byte is on MAD in the data half of the last cycle before HSYNC rises, from
# 80 ns into that half until 10 ns after the cycle. IC34 takes MAD0-7 as dot 7 begins in every cycle (its clock is
# P56#, which rises there out of a flip-flop: no decode of the counter, which could give a runt pulse), and IC35
# copies IC34 when HSYNC rises (HSCK: the chip's HSYNC through a gate, for its edge) - the one moment in a line when
# IC34 holds the attribute byte, and in the blanking. -RESET clears both: white on black, both syncs negative, text off.
# Bits (the chip's DCR, ATR): 0, 1, 2 = red, green, blue OFF (0 = on: ATR 00 is white); 3, 4 = HSYNC, VSYNC positive
# (0 = negative, what 640 x 480 wants); 5 = the text layer on, 6 = text XOR graphics instead of OR; 7 = the second font
c("HSYNC#", "IC1.12", "IC21.1", "IC32.1"); c("VCC", "IC21.2"); c("HSCK", "IC21.3", "IC35.11")
c("RESB#", "IC34.1", "IC35.1")
Q273 = ((3, 2), (4, 5), (7, 6), (8, 9), (13, 12), (14, 15), (17, 16), (18, 19))       # (D, Q) bits 0..7
for i, (d, q) in enumerate(Q273):
    c("MAD%d" % i, "IC34.%d" % d); c("AT%d" % i, "IC34.%d" % q, "IC35.%d" % d)
c("OFFR", "IC35.2", "IC17.6"); c("OFFG", "IC35.5", "IC17.9"); c("OFFB", "IC35.6", "IC17.12")
c("POLH", "IC35.9", "IC32.2"); c("POLV", "IC35.12", "IC32.5")
c("VR", "IC17.4", "R2.1"); c("VG", "IC17.10", "R3.1"); c("VB", "IC17.13", "R4.1")
c("RED", "R2.2", "J1.1"); c("GREEN", "R3.2", "J1.2"); c("BLUE", "R4.2", "J1.3")
c("VSYNC#", "IC1.13", "IC32.4")
c("HSB", "IC32.3", "R5.1"); c("HSOUT", "R5.2", "J1.13"); c("VSB", "IC32.6", "R6.1"); c("VSOUT", "R6.2", "J1.14")
c("GND", "J1.5", "J1.6", "J1.7", "J1.8", "J1.10", "J1.SH")

# ---- text method A (10c): IC41-IC48, sockets ------------------------------------------------------------------------------
# A Window cycle's RAM data is the character word: two codes. It is steady before the cycle's dot 4, so the codes and
# the raster line are clocked into IC44 / IC45 / IC46 there (WCK: IC41/A, D = dot 3 of a Window cycle); the left code
# looks up the character generator for the rest of the cycle and its dots load at the cycle's end, the right code
# has the whole of the next cycle (WPH) and loads at its end. No Window cycle, no load: the text shifter runs empty.
c("QCN", "IC42.1", "IC41.11"); c("2CLK", "IC42.2", "IC42.12"); c("QA", "IC42.4", "IC42.9"); c("D3W", "IC42.6", "IC41.2")
c(PU, "IC41.1", "IC41.4", "IC41.10", "IC41.13")
c("WCK", "IC41.5", "IC44.11", "IC45.11", "IC46.11")
c("WPH", "IC41.9", "IC44.1", "IC43.2"); c("WPHN", "IC41.8", "IC45.1")             # which code drives the generator
c("WANY", "IC43.3", "IC42.10"); c("QC", "IC42.13"); c("TLOAD", "IC42.8", "IC48.19")   # dot 7 of either: one 74F21 gate after the counter
c("GND", "IC43.4", "IC43.5", "IC43.9", "IC43.10", "IC43.12", "IC43.13")
for i in range(8):
    c("DL%d" % i, "IC44.%d" % (2 + i)); c("DH%d" % i, "IC45.%d" % (2 + i))
    c("CA%d" % i, "IC44.%d" % (19 - i), "IC45.%d" % (19 - i), "IC47.%d" % ROM_A[4 + i])
    c("CG%d" % i, "IC47.%d" % ROM_D[i], "IC48.%d" % IO299[7 - i])                 # bit 0 is the left-hand dot
c("RA4", "IC1.33", "IC46.6"); c("GND", "IC46.1", "IC46.7", "IC46.8", "IC46.9")
for i in range(4):
    c("RL%d" % i, "IC46.%d" % (19 - i), "IC47.%d" % ROM_A[i])
# the cursor (10c): the chip's CUD1 and CUD2 (active low, a memory cycle = a character wide) are two more address
# lines of the character generator, live: a character whose look-up cycle has CUD1 low comes from the half of the
# EPROM that holds the cursor's form of every glyph, and is loaded with the cursor in it. A13 is ATR bit 7: a
# second font, line by line
c("CUD1#", "IC1.1", "IC47.2"); c("CUD2#", "IC1.2", "IC47.27"); c("FONT2", "IC35.19", "IC47.26")
c("GND", "IC47.20", "IC47.22"); c("VCC", "IC47.1")                           # -CE, -OE on; Vpp
c(PU, "IC48.1", "IC48.2", "IC48.3"); c("GND", "IC48.11", "IC48.18")

# ---- PS/2: IC24 ATmega328P, latches IC25 / IC26, status IC27, flags IC28, IC29, IC30 (V2.0's nets, new ports) --------
c("MRST", "IC24.1", "R7.1", "C55.2", "IC29.12"); c("VCC", "R7.2")
c("RESETB", "IC30.8", "IC29.11"); c("RESETH", "IC29.10", "R8.1", "IC29.13"); c("VCC", "R8.2")
c("FTX", "IC24.2", "J4.4"); c("FRX", "IC24.3", "J4.5"); c("FDTR", "J4.6", "C55.1"); c("GND", "J4.1", "J4.2")
c("KCLK", "IC24.4", "R12.1", "J2.5"); c("MCLK", "IC24.5", "R14.1", "J3.5")
c("KDAT", "IC24.6", "R13.1", "J2.1"); c("MDAT", "IC24.11", "R15.1", "J3.1")
c("VCC", "R12.2", "R13.2", "R14.2", "R15.2", "F1.1"); c("PS2VCC", "F1.2", "J2.4", "J3.4")
c("GND", "J2.3", "J3.3", "J2.S", "J3.S")
c("XT1", "IC24.9", "Y1.1", "C53.1"); c("XT2", "IC24.10", "Y1.2", "C54.1"); c("GND", "C53.2", "C54.2")
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
    "IC1": [8, 10, 15, 25, 26, 27, 28, 29, 30, 31, 32, 62],                # DREQ, DTACK, EXSYNC, D8-15, DISP2
    "IC2": [15, 14, 11, 10, 7], "IC3": [15, 14, 13, 12], "IC4": [3, 11, 8], "IC39": [12, 13, 14, 15, 16, 17],
    "IC6": [11, 15], "IC7": [8], "IC19": [12], "IC22": [8], "IC23": [8],
    "IC37": [5, 8], "IC38": [3, 11],
    "IC40": [8], "IC41": [6], "IC42": [3, 11], "IC43": [6, 8, 11], "IC46": [12, 13, 14, 15], "IC48": [8],
    "IC24": [21], "IC28": [6, 8], "IC29": [2, 4, 6], "J4": [3], "J2": [2, 6], "J3": [2, 6],
    "J1": [4, 9, 11, 12, 15], "OSC1": [1],
    "X1": [p for p in PINS["X1"] if p not in ("A1", "B1", "C1", "A32", "B32", "C32", "A2", "B2", "C2", "A31", "B31", "C31",
                                              "B25", "B26", "C30", "C13", "C7", "C8", "C9", "C10") and
           p not in ["A%d" % n for n in range(19, 27)]],
}
NO_CONNECT = {r: [str(p) for p in ps] for r, ps in NO_CONNECT.items()}

# nothing of the circuit is open. The bitmap console of the first build (text method B) has no hardware cursor: its
# driver draws one (a rectangle in XOR)
OPEN = ()

# text method A's parts: sockets left empty on the first build
TEXT_A = ["IC%d" % n for n in range(41, 49)] + ["C%d" % n for n in range(42, 50)]

# outputs that drive a net (for check(): no two on one net). The bus, MAD, DL / DH and HD are shared by three-state
# parts enabled at different times, and -INT by open collectors: those nets are left out.
SHARED = ("DATA", "MAD", "DL", "DH", "HD", "-INT", "MD", "CA")        # (AT0-7 are IC34's outputs alone)
OUTPUTS = {"IC2": (13, 12, 9), "IC3": (11, 10, 9, 7), "IC4": (6,), "IC6": (14, 13, 12), "IC7": (5, 6, 9),
           "IC16": (2, 4, 6, 8, 10, 12), "IC17": (1, 4, 10, 13), "IC18": (12, 6, 8), "IC19": (6, 8), "IC20": (3, 6, 8, 11),
           "IC21": (3, 6, 8, 11), "IC37": (6, 9), "IC38": (6, 8), "IC39": (18, 19), "IC31": (3, 6, 8, 11), "IC32": (3, 6, 8, 11), "IC34": (2, 5, 6, 9, 12, 15, 16, 19),
           "IC35": (2, 5, 6, 9, 12, 15, 16, 19), "IC36": (3, 6, 8, 11), "IC40": (17,), "IC41": (5, 9, 8), "IC42": (6, 8), "IC43": (3,),
           "IC46": (16, 17, 18, 19), "IC47": ROM_D, "IC48": (17,), "IC22": (17,), "IC23": (17,), "IC28": (5, 9), "IC29": (8, 10, 12), "IC30": (3, 6, 8, 11),
           "IC1": (52, 53, 54, 55, 34, 35, 36, 37, 12, 13, 63, 11, 1, 2, 33, 56), "OSC1": (8,),
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


def text_a_check():
    """method A's parts drive, of the nets that reach fitted parts, only TDOT (held low by R19 without them)"""
    faults = []
    for net, pins in NETS.items():
        if net in ("VCC", "GND", PU, "TDOT") or net.rstrip("0123456789") in ("DL", "DH"): continue
        a_out = [(r, p) for r, p in pins if r in TEXT_A and p.isdigit() and int(p) in OUTPUTS.get(r, ())]
        fitted = [(r, p) for r, p in pins if r not in TEXT_A]
        if a_out and fitted: faults.append("net %s: %r drives fitted parts %r" % (net, a_out, fitted))
    if ("R19", "1") not in NETS["TDOT"]: faults.append("TDOT has no pull-down")
    return faults


if __name__ == "__main__":
    f = check() + text_a_check()
    ics = sum(1 for r in PARTS if r.startswith("IC"))
    print("%s %s: %d parts (%d ICs), %d nets, %d pins on nets" % (CARD, REV, len(PARTS), ics, len(NETS),
                                                                 sum(len(p) for p in NETS.values())))
    for x in f: print("  " + x)
    if OPEN: print("open: " + "; ".join(OPEN))
    print("check: %s" % ("%d faults" % len(f) if f else "every pin accounted for, no net with one pin, no two outputs on a net; "
                         "method A's %d sockets drive only TDOT" % sum(1 for r in TEXT_A if r.startswith("IC"))))
    raise SystemExit(1 if f else 0)
