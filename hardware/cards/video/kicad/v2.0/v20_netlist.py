# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""v20_netlist.py - the YACC1 video card V2.0: THE single source of its circuit (2026-10-22).

gen_v20.py reads this module to write the KiCad schematic and to build the board; nothing else defines the circuit.
Plain Python data, no KiCad import. The design note is BACKLOG.md "Video card V2.0"; the theory docs/cards/video.md.

What V2.0 is: the V1.3 card (6845 + IDT7134 text RAM, the DOTS jumper and IC28's load-on-carry divider, 12 MHz, both
fonts in one 2732 - hardware/cards/video/kicad/v1.3, its parts and pin numbers kept) with
  * every register on I/O ports PA-PE (74LS138 IC30 + two 74LS32): the 6845 on PA/PB (E = -IO-RD XOR -IO-WR), the
    control register (74LS273 IC33) and the card status (74LS244 IC34) on PC, PS/2 status/commands on PD, data on PE;
    the V1.x memory-mapped 6845 decode, the JP1 latch IC2 and its pull-ups (R13, R14) are gone;
  * a graphics layer: a 62256 (IC39, two 16K pages) at RA2..0:MA10..0 for the display and CPAGE:PLANE:ADDR10..0 for
    the CPU window $D800-$DFFF, time-shared per character slot on IC28's QC (four 74LS157 IC35-IC38), a CPU read latch
    (IC41), a write buffer (IC40) with WRQ (IC44) and -WE (IC45), a display latch (IC42) and shifter (IC43), the
    combine (TEXT-OFF, GFX-ON, XOR; 8-dot mode only) in IC1, IC47, IC48, IC32;
  * two PS/2 ports on an ATmega328P (IC49) talking to the bus through latches IC50 (data, IN PE), IC51 (commands,
    OUT PD), IC52 (status, IN PD) and flags IC53 (FULL, BUSY); INTREQ to -INT through IC27/D and jumper JP3.

Pin numbers are the physical DIP pins (TI pinouts = the KiCad 74xx symbols'; the 74LS163 uses the 74LS161 symbol, the
7416 the 74LS05's, the ATmega328P-P the ATmega48PV-10P's: same pinouts). Bus pins: V3.2 DIN 41612 (docs/system/BUS.md).
Net names: the V1.3 netlist's where a net is kept (its N$ names replaced by names saying what they are).
"""

CARD = "YACC1 video card"
REV = "V2.0"
DATE = "2026-10-22"

DIP = {n: "Package_DIP:DIP-%d_W7.62mm" % n for n in (14, 16, 20, 28)}
DIPW = {n: "Package_DIP:DIP-%d_W15.24mm" % n for n in (24, 28, 40, 48)}
FP_R = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"
FP_C = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm"
FP_CP = "Capacitor_THT:CP_Radial_D5.0mm_P2.50mm"
FP_H = "Connector_PinHeader_2.54mm:PinHeader_1x%02d_P2.54mm_Vertical"
LOCAL = "video-v2.0-local"
BUSLIB = "blank-card-v3.2-eagle"

# ---- parts: reference -> (value, symbol lib:name, footprint lib:name, note) ------------------------------------------
PARTS = {
    "X1":   ("DIN41612 96", BUSLIB + ":FABC96R", BUSLIB + ":FABC96R", "bus connector (blank V3.2 card)"),
    # --- the V1.3 video core (references kept)
    "IC1":  ("74ALS08", "74xx:74LS08", DIP[14], "6845 -CS, WSLOT, the text and graphics dot gates"),
    "IC15": ("IDT7134", LOCAL + ":IDT7134", DIPW[48], "text RAM, dual port: CPU $D000-$D7FF / 6845"),
    "IC17": ("MC6845", "GPU:MC6845", DIPW[40], "CRTC on ports PA (address) / PB (data)"),
    "IC18": ("74S85", "74xx:74LS85", DIP[16], "board select: ADDR15..12 = SV3 ($D000 block)"),
    "IC19": ("74LS00", "74xx:74LS00", DIP[14], "text RAM -CER, CHARCLOCK, CPU read latch -OE"),
    "IC20": ("74LS04", "74xx:74LS04", DIP[14], "oscillator, /ADDR11, VMA"),
    "IC21": ("74LS90", "74xx:74LS90", DIP[14], "dot clock / 2 (SV4 2-3)"),
    "IC22": ("74LS175", "74xx:74LS175", DIP[16], "attribute and DE delay"),
    "IC23": ("74LS174", "74xx:74LS174", DIP[16], "character code latch"),
    "IC24": ("74LS166", "74xx:74LS166", DIP[16], "text dot shifter"),
    "IC25": ("2732", LOCAL + ":2732", DIPW[24], "character generator (firmware/video/chargen-v13.bin)"),
    "IC26": ("74LS86", "74xx:74LS86", DIP[14], "cursor/attribute XORs, 6845 E, the -WE phase"),
    "IC27": ("7416", "74xx:74LS05", DIP[14], "open collector: video, syncs, -INT"),
    "IC28": ("74LS163", "74xx:74LS161", DIP[16], "character counter: load 8 or 10 on the carry (DOTS)"),
    # --- ports
    "IC30": ("74LS138", "74xx:74LS138", DIP[16], "port decode: Y2..Y7 = PA..PF (IO-ADDR3 = 1)"),
    "IC31": ("74LS32", "74xx:74LS32", DIP[14], "PC/PD strobes"),
    "IC32": ("74LS32", "74xx:74LS32", DIP[14], "PE strobe, text OR graphics"),
    "IC33": ("74LS273", "74xx:74LS273", DIP[20], "control register (OUT PC)"),
    "IC34": ("74LS244", "74xx:74LS244", DIP[20], "card status (IN PC)"),
    # --- graphics
    "IC35": ("74LS157", "74xx:74LS157", DIP[16], "graphics address mux GA0-3"),
    "IC36": ("74LS157", "74xx:74LS157", DIP[16], "graphics address mux GA4-7"),
    "IC37": ("74LS157", "74xx:74LS157", DIP[16], "graphics address mux GA8-11"),
    "IC38": ("74LS157", "74xx:74LS157", DIP[16], "graphics address mux GA12-14"),
    "IC39": ("62256", "Memory_RAM:KM62256CLP", DIPW[28], "graphics RAM, 32K = two pages, time-shared"),
    "IC40": ("74LS244", "74xx:74LS244", DIP[20], "graphics write buffer DATA -> GD"),
    "IC41": ("74LS374", "74xx:74LS374", DIP[20], "graphics CPU read latch GD -> DATA"),
    "IC42": ("74LS374", "74xx:74LS374", DIP[20], "graphics display latch"),
    "IC43": ("74LS166", "74xx:74LS166", DIP[16], "graphics dot shifter"),
    "IC44": ("74LS74", "74xx:74LS74", DIP[14], "WRQ: CPU write pending"),
    "IC45": ("74LS20", "74xx:74LS20", DIP[14], "graphics RAM -WE"),
    "IC46": ("74LS04", "74xx:74LS04", DIP[14], "inverters"),
    "IC47": ("74LS08", "74xx:74LS08", DIP[14], "graphics select, write, FULL clear"),
    "IC48": ("74LS10", "74xx:74LS10", DIP[14], "XOR term, video NAND"),
    # --- PS/2
    "IC49": ("ATmega328P-P", "MCU_Microchip_ATmega:ATmega48PV-10P", DIP[28], "PS/2 controller (embedded/video-ps2)"),
    "IC50": ("74LS374", "74xx:74LS374", DIP[20], "PS/2 data latch (IN PE)"),
    "IC51": ("74LS374", "74xx:74LS374", DIP[20], "PS/2 command latch (OUT PD)"),
    "IC52": ("74LS244", "74xx:74LS244", DIP[20], "PS/2 status (IN PD)"),
    "IC53": ("74LS74", "74xx:74LS74", DIP[14], "FULL and BUSY flags"),
    "Y1":   ("16MHz", "Device:Crystal", "Crystal:Crystal_HC49-U_Vertical", "ATmega clock"),
    "J2":   ("KEYBOARD", LOCAL + ":MINIDIN6", LOCAL + ":MiniDIN6_PS2", "PS/2 keyboard"),
    "J3":   ("MOUSE", LOCAL + ":MINIDIN6", LOCAL + ":MiniDIN6_PS2", "PS/2 mouse"),
    "J4":   ("FTDI", "Connector_Generic:Conn_01x06", FP_H % 6, "GND CTS VCC(nc) TXD RXD DTR: bootloader, console"),
    "JP3":  ("INT-EN", "Connector_Generic:Conn_01x02", FP_H % 2, "fitted: the card may drive -INT"),
    "D1":   ("1N4148", "Device:D", "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal", "bus -RESET resets the ATmega"),
    "R16":  ("10k", "Device:R", FP_R, "ATmega reset pull-up"),
    "R17":  ("4.7k", "Device:R", FP_R, "keyboard clock pull-up"),
    "R18":  ("4.7k", "Device:R", FP_R, "keyboard data pull-up"),
    "R19":  ("4.7k", "Device:R", FP_R, "mouse clock pull-up"),
    "R20":  ("4.7k", "Device:R", FP_R, "mouse data pull-up"),
    "C55":  ("22p", "Device:C", FP_C, "Y1 load"),
    "C56":  ("22p", "Device:C", FP_C, "Y1 load"),
    "C57":  ("100n", "Device:C", FP_C, "FTDI DTR auto-reset"),
    # --- kept passives, jumpers and connectors
    "Q2":   ("12MHz", "Device:Crystal", "Crystal:Crystal_HC49-U_Vertical", "dot clock crystal"),
    "R8":   ("1k", "Device:R", FP_R, "oscillator"),
    "R9":   ("1k", "Device:R", FP_R, "oscillator"),
    "R10":  ("1k", "Device:R", FP_R, "counter enables / clears high"),
    "R11":  ("33", "Device:R", FP_R, "video to the sync node"),
    "R12":  ("270", "Device:R", FP_R, "sync node pull-up"),
    "R15":  ("4.7k", "Device:R", FP_R, "DOTS pull-up"),
    "R2":   ("330", "Device:R", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", "PWR LED"),
    "LED1": ("PWR", "Device:LED", "LED_THT:LED_D5.0mm", "power (was PWR0)"),
    "RN2":  ("10k x4", "Device:R_Network04", "Resistor_THT:R_Array_SIP5", "SV3 pull-ups"),
    "SV3":  ("BLOCK", "Connector_Generic:Conn_02x04_Odd_Even", "Connector_PinHeader_2.54mm:PinHeader_2x04_P2.54mm_Vertical",
             "fitted = 0: 5-6 only = the $D000 block"),
    "SV4":  ("DOTCLK", "Connector_Generic:Conn_01x03", FP_H % 3, "1-2: the crystal, 2-3: half of it"),
    "JP2":  ("DOTS 8=ON", "Connector_Generic:Conn_01x02", FP_H % 2, "fitted: 8 dots (64 x 24, graphics), open: 6 (80 x 24)"),
    "X2":   ("DB9 F", LOCAL + ":DE9_SHIELD", LOCAL + ":F09HP", "TTL video: 7 video, 8 HSYNC, 9 VSYNC, 1 GND"),
    "J1":   ("RCA", LOCAL + ":RCA", LOCAL + ":RCA", "composite: video + sync (was U$3)"),
    "C16":  ("10u", "Device:C_Polarized", FP_CP, "bulk"),
}
DECOUPLE = {"C3": "IC1", "C17": "IC15", "C18": "IC17", "C19": "IC18", "C20": "IC19", "C21": "IC20", "C22": "IC21",
            "C23": "IC22", "C24": "IC23", "C25": "IC24", "C26": "IC25", "C27": "IC26", "C28": "IC27", "C29": "IC28"}
for n in range(30, 54):
    DECOUPLE["C%d" % n] = "IC%d" % n
DECOUPLE["C54"] = "IC49"                         # the ATmega's AVCC
for c, ic in DECOUPLE.items():
    PARTS[c] = ("100n", "Device:C", FP_C, "%s decoupling" % ic)

POWER_PINS = {  # ref -> (VCC pins, GND pins)
    "IC1": ((14,), (7,)), "IC15": ((48,), (24,)), "IC17": ((20,), (1,)), "IC18": ((16,), (8,)), "IC19": ((14,), (7,)),
    "IC20": ((14,), (7,)), "IC21": ((5,), (10,)), "IC22": ((16,), (8,)), "IC23": ((16,), (8,)), "IC24": ((16,), (8,)),
    "IC25": ((24,), (12,)), "IC26": ((14,), (7,)), "IC27": ((14,), (7,)), "IC28": ((16,), (8,)),
    "IC39": ((28,), (14,)), "IC49": ((7, 20), (8, 22)),
}
for ref in PARTS:
    if ref.startswith("IC") and ref not in POWER_PINS:
        sym = PARTS[ref][1]
        POWER_PINS[ref] = ((20,), (10,)) if any(k in sym for k in ("244", "273", "374")) else \
                          ((16,), (8,)) if any(k in sym for k in ("138", "157", "166")) else ((14,), (7,))

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
c("VCC", "C16.1", *["X1.%s" % p for p in ("A2", "B2", "C2", "A31", "B31", "C31")])
c("GND", "C16.2", *["X1.%s" % p for p in ("A1", "B1", "C1", "A32", "B32", "C32")])

# ---- the bus ---------------------------------------------------------------------------------------------------------
for i in range(16):
    c("ADDR%d" % i, "X1.A%d" % (3 + i))
for i in range(8):
    c("DATA%d" % i, "X1.A%d" % (19 + i))
c("-MEM-RD", "X1.B23"); c("-MEM-WR", "X1.B24"); c("-VMA", "X1.C12"); c("-RESET", "X1.C30")
for i in range(4):
    c("IO-ADDR%d" % i, "X1.C%d" % (7 + i))
c("-IO-RD", "X1.B25"); c("-IO-WR", "X1.B26"); c("-INT", "X1.C13")

# ---- board select: IC18 74S85 (A = SV3 with RN2 pull-ups, B = ADDR12..15, A=B in = VMA) ------------------------------
c("ADDR12", "IC18.9"); c("ADDR13", "IC18.11"); c("ADDR14", "IC18.14"); c("ADDR15", "IC18.1")
for i, (a_pin, sv, rn) in enumerate(((10, 7, 2), (12, 5, 3), (13, 3, 4), (15, 1, 5))):
    c("SEL%d" % i, "IC18.%d" % a_pin, "SV3.%d" % sv, "RN2.%d" % rn)
c("GND", "SV3.2", "SV3.4", "SV3.6", "SV3.8", "IC18.2", "IC18.4")
c("VCC", "RN2.1")
c("VMA", "IC18.3", "IC20.12"); c("-VMA", "IC20.13")
c("BOARDSEL", "IC18.6", "IC19.4", "IC47.4")

# ---- text RAM IC15 (IDT7134) -----------------------------------------------------------------------------------------
c("NADDR11", "IC20.10", "IC19.5"); c("ADDR11", "IC20.11", "IC47.5")
c("TXTCE", "IC19.6", "IC15.47")
c("GND", "IC15.1", "IC15.5", "IC15.45"); c("VCC", "IC15.2")       # -CEL, -OEL low; A11R low; R/-WL high
for i, pin in enumerate((42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 44)):
    c("ADDR%d" % i, "IC15.%d" % pin)
for i in range(8):
    c("DATA%d" % i, "IC15.%d" % (25 + i))
c("-MEM-RD", "IC15.43"); c("-MEM-WR", "IC15.46")
for i, pin in enumerate((6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 4, 3)):
    c("VADDR%d" % i, "IC15.%d" % pin, "IC17.%d" % (4 + i))
for i, pin in enumerate((16, 17, 18, 19, 20, 21)):
    c("VDATA%d" % i, "IC15.%d" % pin)
c("VDATA7", "IC15.23", "IC26.2")

# ---- 6845 IC17 on PA/PB ----------------------------------------------------------------------------------------------
c("-RESET", "IC17.2"); c("GND", "IC17.3")                          # LPSTB tied low
c("DE", "IC17.18", "IC22.12", "IC34.6"); c("CURSOR", "IC17.19", "IC26.1")
c("CRTCCLOCK", "IC17.21", "IC28.12", "IC46.1", "IC41.11")
c("-IO-WR", "IC17.22"); c("CRTCE", "IC17.23", "IC26.8"); c("IO-ADDR0", "IC17.24"); c("CRTCCS", "IC17.25", "IC1.3")
for i in range(8):
    c("DATA%d" % i, "IC17.%d" % (33 - i))
c("VROWS2", "IC17.36"); c("VROWS1", "IC17.37"); c("VROWS0", "IC17.38")
c("HSYNC", "IC17.39", "IC27.5", "X2.8"); c("VSYNC", "IC17.40", "IC27.3", "X2.9", "IC34.4")

# ---- clocks: Q2, IC20 oscillator, IC21 /2, SV4, IC28 counter, CHARCLOCK (IC19/C) -------------------------------------
c("OSCIN", "Q2.1", "R8.1", "IC20.1")
c("OSCMID", "IC20.2", "IC20.3", "R8.2", "R9.1")
c("OSCOUT", "IC20.4", "IC20.5", "Q2.2", "R9.2")
c("XTAL", "IC20.6", "IC21.14", "SV4.1")
c("XTALDIV2", "IC20.9", "IC21.1", "IC21.12"); c("DOTCLKH", "IC20.8", "SV4.3")
c("GND", "IC21.2", "IC21.3", "IC21.6", "IC21.7")
c("DOTCLOCK", "SV4.2", "IC28.2", "IC24.7", "IC43.7")
c("VCC", "IC28.1", "IC28.6"); c("GND", "IC28.3", "IC28.5")         # -CLR high; load 1 0 DOTS 0 = 8 or 10
c("DOTS", "IC28.4", "IC25.19", "JP2.1", "R15.2", "IC34.2", "IC46.11"); c("GND", "JP2.2"); c("VCC", "R15.1")
c("CNTEN", "IC28.7", "IC28.10", "R10.1", "IC22.1", "IC23.1", "IC24.9", "IC43.9"); c("VCC", "R10.2")
c("CHARCLOCK", "IC28.9", "IC19.8", "IC22.9", "IC23.9", "IC24.15", "IC43.15", "IC42.11", "IC44.3")
c("RCO", "IC28.15", "IC19.9", "IC19.10")
c("CNTQA", "IC28.14", "IC26.12"); c("CNTQB", "IC28.13", "IC26.13")

# ---- text pipeline: IC23 code latch, IC25 EPROM, IC24 shifter, IC22 delays, IC26 XORs --------------------------------
for vd, d_pin, q_pin, a_pin in ((5, 3, 2, 23), (4, 4, 5, 1), (3, 6, 7, 2), (2, 11, 10, 3), (1, 13, 12, 4), (0, 14, 15, 5)):
    c("VDATA%d" % vd, "IC23.%d" % d_pin)
    c("CA%d" % (8 - (5 - vd)), "IC23.%d" % q_pin, "IC25.%d" % a_pin)      # code bit vd -> EPROM A3 + vd
c("VROWS2", "IC25.6"); c("VROWS1", "IC25.7"); c("VROWS0", "IC25.8")
c("GND", "IC25.18", "IC25.20", "IC25.21", "IC25.22")                    # -CE, -OE, A11, A9
for k, (o_pin, s_pin) in enumerate(((9, 2), (10, 3), (11, 4), (13, 5), (14, 10), (15, 11), (16, 12), (17, 14))):
    c("CG%d" % k, "IC25.%d" % o_pin, "IC24.%d" % s_pin)
c("GND", "IC24.1", "IC24.6")
c("TDOT", "IC24.13", "IC26.5")
c("ATTR1", "IC26.3", "IC22.4"); c("ATTR2", "IC22.2", "IC22.5"); c("ATTR3", "IC22.7", "IC26.4")
c("DE2", "IC22.10", "IC22.13"); c("DE3", "IC22.15", "IC48.5")
c("TD", "IC26.6", "IC1.9")

# ---- video out: IC27 open collector, R11/R12, DB9, RCA ---------------------------------------------------------------
c("VIDN", "IC48.6", "IC27.1")
c("VIDEO", "IC27.2", "R11.2", "X2.7")
c("SYNC", "IC27.4", "IC27.6", "R11.1", "R12.2", "J1.C1"); c("VCC", "R12.1")
c("GND", "X2.1", "X2.G1", "X2.G2", "J1.S1", "J1.S2", "J1.S3")
c("PWRLED", "R2.1", "LED1.2"); c("VCC", "R2.2"); c("GND", "LED1.1")

# ---- E for the 6845: -IO-RD XOR -IO-WR (IC26/C) ----------------------------------------------------------------------
c("-IO-RD", "IC26.9"); c("-IO-WR", "IC26.10")
c("WEPH", "IC26.11", "IC45.4")                                          # QA XOR QB: counts 9, 10

# ---- port decode IC30, strobes IC31/IC32 -----------------------------------------------------------------------------
c("IO-ADDR0", "IC30.1"); c("IO-ADDR1", "IC30.2"); c("IO-ADDR2", "IC30.3"); c("IO-ADDR3", "IC30.6")
c("GND", "IC30.4", "IC30.5")
c("PSEL_A", "IC30.13", "IC1.1"); c("PSEL_B", "IC30.12", "IC1.2")
c("PSEL_C", "IC30.11", "IC31.1", "IC31.4"); c("PSEL_D", "IC30.10", "IC31.9", "IC31.12"); c("PSEL_E", "IC30.9", "IC32.1")
c("-IO-WR", "IC31.2", "IC31.10"); c("-IO-RD", "IC31.5", "IC31.13", "IC32.2")
c("CTLCLK", "IC31.3", "IC33.11"); c("STATOE", "IC31.6", "IC34.1", "IC34.19")
c("CMDCLK", "IC31.8", "IC51.11", "IC53.11"); c("PSTOE", "IC31.11", "IC52.1", "IC52.19")
c("PDOE", "IC32.3", "IC50.1", "IC47.12")

# ---- control register IC33 (OUT PC) and card status IC34 (IN PC) -----------------------------------------------------
c("-RESET", "IC33.1")
for i, (d, q) in enumerate(((3, 2), (4, 5), (7, 6), (8, 9), (13, 12), (14, 15), (17, 16), (18, 19))):
    c("DATA%d" % i, "IC33.%d" % d)
    c(("PLANE0", "PLANE1", "PLANE2", "CPAGE", "DPAGE", "TEXTOFF", "GFXON", "XORM")[i], "IC33.%d" % q)
# IC34: 1A1..1A4 (2, 4, 6, 8) -> 1Y (18, 16, 14, 12) = DATA0..3; 2A1..2A4 (11, 13, 15, 17) -> 2Y (9, 7, 5, 3) = DATA4..7
c("DATA0", "IC34.18"); c("DATA1", "IC34.16"); c("DATA2", "IC34.14"); c("DATA3", "IC34.12")
c("DATA4", "IC34.9"); c("DATA5", "IC34.7"); c("DATA6", "IC34.5"); c("DATA7", "IC34.3")
c("GND", "IC34.8", "IC34.13", "IC34.17"); c("VCC", "IC34.11", "IC34.15")      # bit 3 = 0, bits 7..4 = 0101 (ID $5x)

# ---- graphics address muxes IC35-IC38 (S = QC: 0 = CPU (I0), 1 = display (I1)) -------------------------------------
MUX = [("IC35", ("ADDR0", "VADDR0"), ("ADDR1", "VADDR1"), ("ADDR2", "VADDR2"), ("ADDR3", "VADDR3")),
       ("IC36", ("ADDR4", "VADDR4"), ("ADDR5", "VADDR5"), ("ADDR6", "VADDR6"), ("ADDR7", "VADDR7")),
       ("IC37", ("ADDR8", "VADDR8"), ("ADDR9", "VADDR9"), ("ADDR10", "VADDR10"), ("PLANE0", "VROWS0")),
       ("IC38", ("PLANE1", "VROWS1"), ("PLANE2", "VROWS2"), ("CPAGE", "DPAGE"), ("GND", "GND"))]
SECTIONS = ((2, 3, 4), (5, 6, 7), (11, 10, 9), (14, 13, 12))          # (I0, I1, Z) of a, b, c, d
for k, (ref, *sections) in enumerate(MUX):
    c("CRTCCLOCK", ref + ".1"); c("GND", ref + ".15")
    for j, ((cpu, disp), (i0, i1, z)) in enumerate(zip(sections, SECTIONS)):
        c(cpu, "%s.%d" % (ref, i0)); c(disp, "%s.%d" % (ref, i1))
        if k * 4 + j < 15:
            c("GA%d" % (k * 4 + j), "%s.%d" % (ref, z))

# ---- graphics RAM IC39 (62256, KM62256CLP pins) ----------------------------------------------------------------------
for i, pin in enumerate((10, 9, 8, 7, 6, 5, 4, 3, 25, 24, 21, 23, 2, 26, 1)):
    c("GA%d" % i, "IC39.%d" % pin)
for i, pin in enumerate((11, 12, 13, 15, 16, 17, 18, 19)):
    c("GD%d" % i, "IC39.%d" % pin)
c("GND", "IC39.20")                                                      # -CS
c("WSLOT", "IC39.22", "IC1.6", "IC46.13"); c("GWE", "IC39.27", "IC45.6")

# ---- write buffer IC40 (DATA -> GD while WSLOT), CPU read latch IC41, display latch IC42, shifter IC43 ----------------
c("-WSLOT", "IC46.12", "IC40.1", "IC40.19")
for i, (a, y) in enumerate(((2, 18), (4, 16), (6, 14), (8, 12), (11, 9), (13, 7), (15, 5), (17, 3))):
    c("DATA%d" % i, "IC40.%d" % a); c("GD%d" % i, "IC40.%d" % y)
L374 = ((3, 2), (4, 5), (7, 6), (8, 9), (13, 12), (14, 15), (17, 16), (18, 19))   # (D, Q) bits 0..7
for i, (d, q) in enumerate(L374):
    c("GD%d" % i, "IC41.%d" % d, "IC42.%d" % d); c("DATA%d" % i, "IC41.%d" % q)
    c("GL%d" % i, "IC42.%d" % q)
c("GRDOE", "IC41.1", "IC19.3"); c("GND", "IC42.1")
for i, pin in enumerate((2, 3, 4, 5, 10, 11, 12, 14)):                  # A..H, H shifted out first = bit 7
    c("GL%d" % i, "IC43.%d" % pin)
c("GND", "IC43.1", "IC43.6"); c("GDOT", "IC43.13", "IC1.12")

# ---- slot logic: WRQ (IC44), -WE (IC45), inverters (IC46), gates (IC1, IC47, IC48, IC19/A, IC32) --------------------
c("GWR", "IC47.8", "IC44.2", "IC45.5"); c("WRQ", "IC44.5", "IC1.4", "IC45.1"); c("-RESET", "IC44.1"); c("VCC", "IC44.4")
c("VCC", "IC44.13", "IC44.10"); c("GND", "IC44.12", "IC44.11")           # the second flip-flop: spare, inputs tied
c("NQC", "IC46.2", "IC1.5", "IC45.2")
c("-MEM-RD", "IC46.3"); c("MEMRD", "IC46.4", "IC19.2"); c("-MEM-WR", "IC46.5"); c("MEMWR", "IC46.6", "IC47.10")
c("TEXTOFF", "IC46.9"); c("TEXTON", "IC46.8", "IC1.10"); c("EIGHT", "IC46.10", "IC47.2")
c("TDG", "IC1.8", "IC32.4", "IC48.1"); c("GFXON", "IC1.13"); c("GDA", "IC1.11", "IC47.1")
c("GDG", "IC47.3", "IC32.5", "IC48.2"); c("GSEL", "IC47.6", "IC47.9", "IC19.1")
c("XORM", "IC48.13"); c("NBOTH", "IC48.12", "IC48.4"); c("GOR", "IC32.6", "IC48.3")
c("VCC", "IC45.9", "IC45.10", "IC45.12", "IC45.13", "IC48.9", "IC48.10", "IC48.11", "IC19.12", "IC19.13")
c("GND", "IC32.9", "IC32.10", "IC32.12", "IC32.13", "IC27.11", "IC27.13")
c("FULLCLR", "IC47.11", "IC53.1"); c("-RESET", "IC47.13")

# ---- PS/2: IC49 ATmega328P, Y1, reset, FTDI, latches IC50-IC52, flags IC53, jacks, INT -------------------------------
c("MRST", "IC49.1", "R16.1", "C57.2", "D1.2"); c("VCC", "R16.2"); c("-RESET", "D1.1")
c("FTX", "IC49.2", "J4.4"); c("FRX", "IC49.3", "J4.5"); c("FDTR", "J4.6", "C57.1"); c("GND", "J4.1", "J4.2")
c("KCLK", "IC49.4", "R17.1", "J2.5"); c("MCLK", "IC49.5", "R19.1", "J3.5")
c("KDAT", "IC49.6", "R18.1", "J2.1"); c("MDAT", "IC49.11", "R20.1", "J3.1")
c("VCC", "R17.2", "R18.2", "R19.2", "R20.2", "J2.4", "J3.4"); c("GND", "J2.3", "J3.3", "J2.S", "J3.S")
c("XT1", "IC49.9", "Y1.1", "C55.1"); c("XT2", "IC49.10", "Y1.2", "C56.1"); c("GND", "C55.2", "C56.2")
c("LDDATA", "IC49.12", "IC50.11", "IC53.3"); c("RDCMD", "IC49.13", "IC51.1", "IC53.13")
for i, pin in enumerate((23, 24, 25, 26, 27, 28, 14, 15)):
    c("MD%d" % i, "IC49.%d" % pin)
c("FULL", "IC49.16", "IC53.5", "IC52.2"); c("SRC", "IC49.17", "IC52.4"); c("INTREQ", "IC49.18", "IC27.9")
c("BUSY", "IC49.19", "IC53.9", "IC52.6")
for i, (d, q) in enumerate(L374):
    c("MD%d" % i, "IC50.%d" % d, "IC51.%d" % q); c("DATA%d" % i, "IC50.%d" % q, "IC51.%d" % d)
c("DATA0", "IC52.18"); c("DATA1", "IC52.16"); c("DATA2", "IC52.14"); c("DATA3", "IC52.12")
c("DATA4", "IC52.9"); c("DATA5", "IC52.7"); c("DATA6", "IC52.5"); c("DATA7", "IC52.3")
c("GND", "IC52.8", "IC52.11", "IC52.13", "IC52.15", "IC52.17")
c("VCC", "IC53.2", "IC53.4", "IC53.12", "IC53.10")                      # D high, -PRE high
c("INTOC", "IC27.8", "JP3.1"); c("-INT", "JP3.2")

# ---- pins left open (a no-connect flag each) --------------------------------------------------------------------------
NO_CONNECT = {
    "IC15": [22], "IC17": [16, 17, 34, 35], "IC18": [5, 7], "IC21": [8, 9, 11], "IC28": [11], "IC22": [3, 6, 11, 14],
    "IC19": [11], "IC27": [10, 12], "IC30": [14, 15, 7], "IC32": [8, 11], "IC38": [12], "IC44": [6, 8, 9],
    "IC45": [8], "IC48": [8], "IC49": [21], "IC53": [6, 8], "J4": [3], "J2": [2, 6], "J3": [2, 6], "X2": [2, 3, 4, 5, 6],
}
NO_CONNECT = {r: [str(p) for p in ps] for r, ps in NO_CONNECT.items()}

# single-pin nets that are deliberate (none on this card)
SINGLE_OK = set()


def check():
    """-> a list of problems: unknown parts, a pin on two nets, one-pin nets, a pin both connected and no-connect"""
    probs, seen = [], {}
    for net, conns in NETS.items():
        for ref, pin in conns:
            if ref not in PARTS:
                probs.append("%s: unknown part %s" % (net, ref))
            if (ref, pin) in seen and seen[(ref, pin)] != net:
                probs.append("%s.%s on %s and %s" % (ref, pin, seen[(ref, pin)], net))
            seen[(ref, pin)] = net
        if len(set(conns)) < 2 and net not in SINGLE_OK:
            probs.append("%s: one pin only (%s)" % (net, conns))
    for ref, pins in NO_CONNECT.items():
        for p in pins:
            if (ref, p) in seen:
                probs.append("%s.%s is a no-connect and on %s" % (ref, p, seen[(ref, p)]))
    return probs


if __name__ == "__main__":
    p = check()
    print("\n".join(p) or "v20_netlist: %d parts, %d nets, %d connections - OK" % (
        len(PARTS), len(NETS), sum(len(set(v)) for v in NETS.values())))
