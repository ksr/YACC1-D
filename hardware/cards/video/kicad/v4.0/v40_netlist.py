# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""v40_netlist.py - the YACC1 video card V4: THE single source of its circuit (2026-11-12).

The card: a 6845 on I/O ports PA / PB that counts 16 dots at a time, VGA (640 x 480, 31.47 kHz) from a 25.175 MHz dot
clock, 80 x 25 characters of 8 x 16 dots from the V2.0 card's dual-port text RAM, a 640 x 400 graphics layer in a 128K
static RAM behind the window $D800-$DFFF, two control registers (OUT PC, OUT PF), the card status (IN PC) and the PS/2
keyboard and mouse section of the V2.0 card on ports PD / PE. The design note is docs/cards/video-v4.md: section 5
the clock, the stage and one count dot by dot, 6 the text, 7 the graphics RAM's two modes, 8 the dot path, 9 the ports.
Plain Python data, no KiCad import; the generator for the schematic and the board (as V2.0's gen_v20.py reads
v20_netlist.py) is still to be written.

NOT A BOARD YET. check() below proves the wiring is complete (every pin on a net or listed as open, no net with one
pin, no two outputs on a net, the text-only build). tests/video/v40_netsim.py runs this netlist as a circuit with the
parts' data-sheet delays at both ends of their ranges: that is the proof that it does what the note says, and the
timing check (docs/cards/video-v4.md section 5 has its figures). The parts here are the ones it was run with.

The names: D0-D3 are the dot counter's bits (IC11: the dot within a count, 0-15), and "as dot n begins" is the clock
edge at which the counter becomes n. Net names ending in # are active low.

  the clock      CRTCCK, the 6845's clock, is D3 a dot late (IC12/A): low in dots 1-8, high in 9-0. The 6845 steps as
                 it falls, as dot 1 begins.
  the stage      IC15 / IC16 take MA0-9, DE, CURSOR, HSYNC and VSYNC as dot 0 begins (STG = NOT D3), 15 dots after
                 the 6845 stepped: SA0-9, SDE, SCUR, SHS, SVS, steady for a count. RA0-3 are not staged (they move
                 once a line, in the blanking).
  the text       the text RAM's display address is SA9-0 then D3 (the half: 0 the left character, 1 the right). The
                 code register IC17 takes a code as dots 4 and 12 begin (D2), and with it the cursor flag CURF
                 (IC20/A: SCUR AND (the half = CURH)); the character generator IC18 is addressed by RA3-0, the code
                 and CURF; its byte loads into IC19 8 dots after the code was taken.
  the load       TLOAD = D0 AND D1 AND NOT D2 AND SDE2 (IC21/A, one fast gate after the counter): high in dots 3 and
                 11, so both shift registers load as dots 4 and 12 begin, and only where the display is enabled.
                 SDE2 is SDE taken as dot 8 begins (IC12/B): the same count's DE for both of its characters.
  the slots      SELCPU = D2 OR NOT GFX-ON (IC36/A) is the address multiplexers' select: with GFX-ON = 1 the display
                 has the graphics RAM in dots 0-3 and 8-11 and the CPU in dots 4-7 and 12-15; with GFX-ON = 0 the CPU
                 has it for good (direct mode). The byte latch IC32 takes the display's byte on D2's rise.
  a write        WRQ (IC34/A) is the window's write strobe GWR taken as a CPU slot begins (D2); GFX-ON = 0 holds it
                 clear. P56 (IC35/A) is high in dots 5-6 and 13-14, a flip-flop's pulse. -WE = WEP# AND WED#
                 (IC23/D): WEP# = NAND(WRQ, P56) (IC37/C) is slot mode's pulse - once WRQ has taken the strobe the
                 pulse is whole, whenever the strobe ends (the microcode holds the address and the data a step
                 longer) - and WED# = NAND(NOT GFX-ON, GWR) (IC37/D) is the strobe itself in direct mode. The write
                 buffer IC29 is enabled by -WE.
  the RAM's -OE  GOE# = (WRQ OR NOT GFX-ON) AND SELCPU AND GRDOE# (IC36/B, IC38/A): off in a CPU slot with a write
                 waiting; in direct mode on only while the window is read.
  a read         slot mode: IC30 takes the RAM's byte as every CPU slot ends (RDCK, IC35/B: high in dots 8 and 0) and
                 drives the bus while the window is read (SRDOE#). Direct mode: IC31 passes the RAM's byte (DRDOE#).
  the dots       VIDN = NOR(text, graphics) OR (text AND graphics AND XOR) (IC39/A, IC38/B, IC36/C), retimed by
                 IC20/B; three guns, each NOR(VIDN retimed, its off bit) (IC39).
  the syncs      HSYNC from the stage through an inverter and its polarity XOR; VSYNC cut to SVS AND NOT (SVS seen at
                 two HSYNCs) (IC40, IC13/F, IC36/D), then its polarity XOR. Both negative after -RESET.

The rules the circuit keeps (docs/cards/video-v4.md section 5, from the V3 design's timing check): no clock, clear,
preset or latch enable is a decode of counter bits - each is a counter bit, a counter bit inverted, or a flip-flop's
output; decodes go only to D inputs and to the shift registers' load. The parts are the families the timing is worked
out with: 74F for the counter, the flip-flops, the shift registers and the load gate, 74ACT for the rest of the dot
clock's side, LS / HCT where only the bus's strobes are seen.

The text-only build (as V2.0's): the graphics parts in TEXT_ONLY_LEFT_OFF may be left off; R8, R9 and R10 (always
fitted) hold GDOT and WRQ low and TXTONLY high without them, and IN PC bit 3 tells software which build it runs on.
text_only_check() proves that these are the only nets the left-off parts drive into fitted logic.

Pin numbers are the physical DIP pins. Bus pins: the V3.2 DIN 41612 connector (docs/system/BUS.md), as on V2.0.
`python3 v40_netlist.py` runs check().
"""

CARD = "YACC1 video card"
REV = "V4.0"
DATE = "2026-11-12"

DIP = {n: "Package_DIP:DIP-%d_W7.62mm" % n for n in (14, 16, 20, 28)}
DIPW = {n: "Package_DIP:DIP-%d_W15.24mm" % n for n in (28, 32, 40, 48)}
FP_R = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"
FP_C = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm"            # 0.1-inch leads: the rule for every bypass capacitor
FP_H = "Connector_PinHeader_2.54mm:PinHeader_1x%02d_P2.54mm_Vertical"
# the DE-15 socket: KiCad's footprint for the common right-angle part (pins 3.03 mm, mounting holes 4.94 mm from the edge)
FP_VGA = "Connector_Dsub:DSUB-15-HD_Socket_Horizontal_P2.29x1.90mm_EdgePinOffset3.03mm_Housed_MountingHolesOffset4.94mm"
LOCAL = "video-v4.0-local"
BUSLIB = "blank-card-v3.2-eagle"

# ---- parts: reference -> (value, symbol lib:name, footprint lib:name, note) ------------------------------------------
PARTS = {
    "X1":   ("DIN41612 96", BUSLIB + ":FABC96R", BUSLIB + ":FABC96R", "bus connector (blank V3.2 card)"),
    # --- the bus side, the ports and the registers
    "IC1":  ("74S85", "74xx:74LS85", DIP[16], "board select: ADDR15..12 = SV1 (the $D000 block)"),
    "IC2":  ("74LS138", "74xx:74LS138", DIP[16], "port decode: Y2..Y7 = PA..PF (IO-ADDR3 = 1)"),
    "IC3":  ("74LS32", "74xx:74LS32", DIP[14], "the PC and PD strobes: control 1's clock, the status, the PS/2 command and status"),
    "IC4":  ("74LS32", "74xx:74LS32", DIP[14], "the PE strobe, control 2's clock (OUT PF); which of the two read paths answers the window"),
    "IC5":  ("74HCT273", "74xx:74LS273", DIP[20], "control 1 (OUT PC): PLANE0-3, CPAGE, DPAGE, GFX-ON, XOR"),
    "IC6":  ("74HCT273", "74xx:74LS273", DIP[20], "control 2 (OUT PF): TEXT-OFF, CURH, HSYNC +, VSYNC +, spare, red / green / blue off"),
    "IC7":  ("74LS244", "74xx:74LS244", DIP[20], "card status (IN PC): 0, VSYNC, DE, TEXT-ONLY, the ID 0111"),
    "IC8":  ("74HCT04", "74xx:74LS04", DIP[14], "VMA, NOT ADDR11, MEMRD, MEMWR, NOT HSYNC; one spare"),
    "IC9":  ("74HCT08", "74xx:74LS08", DIP[14], "the 6845's -CS; INTREQ AND FULL; the -RESET buffer for IC46; FULL's clear"),
    # --- the 6845 and the clock
    "IC10": ("HD68B45SP / MC68B45P", "GPU:MC6845", DIPW[40], "CRTC on ports PA (address) / PB (data); a count is 16 dots"),
    "OSC1": ("25.175MHz", "Oscillator:CXO_DIP14", "Oscillator:Oscillator_DIP-14", "dot clock, in a socket"),
    "IC11": ("74F163A", "74xx:74LS161", DIP[16], "dot counter D0-D3: the 16 dots of a count"),
    "IC12": ("74F74", "74xx:74LS74", DIP[14], "A: the 6845's clock, D3 a dot late; B: SDE2, DE taken as dot 8 begins"),
    "IC13": ("74ACT04", "74xx:74LS04", DIP[14], "STG (NOT D3), NOT D2, NOT D1, NOT GFX-ON, TEXT-ON, NOT VSYNC"),
    # --- text
    "IC14": ("IDT7134", LOCAL + ":IDT7134", DIPW[48], "text RAM, dual port: CPU $D000-$D7FF / display SA9-0, half"),
    "IC15": ("74ACT574", "74xx:74LS574", DIP[20], "the stage: MA0-7 as dot 0 begins"),
    "IC16": ("74ACT574", "74xx:74LS574", DIP[20], "the stage: MA8, MA9, DE, CURSOR, HSYNC, VSYNC"),
    "IC17": ("74ACT574", "74xx:74LS574", DIP[20], "character code register (dots 4 and 12)"),
    "IC18": ("AT28C64B-15", "Memory_EEPROM:KM28C64A", DIPW[28], "character generator: line + 16 x code + 4096 x cursor"),
    "IC19": ("74F299", "74xx:74LS299", DIP[20], "text dot shifter, bit 7 first; held clear by TEXT-OFF"),
    "IC20": ("74F74", "74xx:74LS74", DIP[14], "A: CURF, the cursor flag of the code in IC17; B: the mixed dot retimed to the dot clock"),
    "IC21": ("74F21", "74xx:74LS21", DIP[14], "the shift registers' load (dots 3 and 11, display enabled); the P56 flip-flop's D (the fast gate after the inverter)"),
    "IC22": ("74ACT86", "74xx:74LS86", DIP[14], "the 6845's E; the cursor's half; the two syncs' polarity"),
    "IC23": ("74ACT08", "74xx:74LS08", DIP[14], "the window's select and write strobe; the cursor flag's D; the RAM's -WE"),
    # --- graphics (left off in the text-only build: IC24-IC34, RN2)
    "IC24": ("74ACT157", "74xx:74LS157", DIP[16], "graphics address mux GA0-3"),
    "IC25": ("74ACT157", "74xx:74LS157", DIP[16], "graphics address mux GA4-7"),
    "IC26": ("74ACT157", "74xx:74LS157", DIP[16], "graphics address mux GA8-11"),
    "IC27": ("74ACT157", "74xx:74LS157", DIP[16], "graphics address mux GA12-15"),
    "IC28": ("AS6C1008-55PCN", LOCAL + ":SRAM_DIP32", DIPW[32], "graphics RAM, 128K: two pages of sixteen 2K planes in its lower 64K"),
    "IC29": ("74ACT244", "74xx:74LS244", DIP[20], "graphics write buffer DATA -> GD (while -WE)"),
    "IC30": ("74ACT574", "74xx:74LS574", DIP[20], "graphics CPU read latch GD -> DATA (slot mode)"),
    "IC31": ("74HCT244", "74xx:74LS244", DIP[20], "direct-mode read buffer GD -> DATA (GFX-ON = 0)"),
    "IC32": ("74ACT574", "74xx:74LS574", DIP[20], "graphics display byte latch (dots 4 and 12)"),
    "IC33": ("74F299", "74xx:74LS299", DIP[20], "graphics dot shifter, bit 7 first; held clear while GFX-ON = 0"),
    "IC34": ("74F74", "74xx:74LS74", DIP[14], "A: WRQ, a window write waiting (held clear in direct mode); B: TXTONLY, held 0 (the graphics parts are fitted)"),
    "RN2":  ("10k x8", "Device:R_Network08", "Resistor_THT:R_Array_SIP9", "GD0-7 pull-ups (GD idles undriven in direct mode)"),
    # --- the slot logic and the dots (fitted in both builds)
    "IC35": ("74F74", "74xx:74LS74", DIP[14], "A: P56, dots 5-6 and 13-14 (the RAM's -WE); B: RDCK, dots 8 and 0 (the read latch's clock)"),
    "IC36": ("74ACT32", "74xx:74LS32", DIP[14], "SELCPU; a write waiting or direct mode (for the RAM's -OE); the mixed dot; VSYNC cut to two lines"),
    "IC37": ("74ACT00", "74xx:74LS00", DIP[14], "the text RAM's -CE; a window read; slot mode's write pulse; direct mode's write strobe"),
    "IC38": ("74ACT11", "74xx:74LS11", DIP[14], "the RAM's -OE; text AND graphics AND XOR; the read latch's clock flip-flop's D (dots 7 and 15)"),
    "IC39": ("74ACT02", "74xx:74LS02", DIP[14], "NOR(text, graphics); the three guns' gates"),
    "IC40": ("74HCT74", "74xx:74LS74", DIP[14], "VSYNC seen at one HSYNC and at two: the vertical sync's length"),
    "J1":   ("VGA", "Connector:DE15_Socket_HighDensity_MountingHoles", FP_VGA, "monitor: 1 R, 2 G, 3 B, 13 HSYNC, 14 VSYNC; SH the shell"),
    "R3":   ("470", "Device:R", FP_R, "video to R (0.7 V into 75 ohm)"),
    "R4":   ("470", "Device:R", FP_R, "video to G"),
    "R5":   ("470", "Device:R", FP_R, "video to B"),
    "R6":   ("68", "Device:R", FP_R, "HSYNC series"),
    "R7":   ("68", "Device:R", FP_R, "VSYNC series"),
    "R8":   ("10k", "Device:R", FP_R, "GDOT pull-down: no graphics dot in the text-only build (IC33 not fitted)"),
    "R9":   ("10k", "Device:R", FP_R, "WRQ pull-down for the text-only build (IC34 not fitted)"),
    "R10":  ("10k", "Device:R", FP_R, "TXTONLY pull-up: IN PC bit 3 = 1 when IC34 is not fitted"),
    # --- PS/2 (the V2.0 card's section; embedded/video-ps2)
    "IC41": ("ATmega328P-P", "MCU_Microchip_ATmega:ATmega48PV-10P", DIP[28], "PS/2 controller (embedded/video-ps2)"),
    "IC42": ("74LS374", "74xx:74LS374", DIP[20], "PS/2 data latch (IN PE)"),
    "IC43": ("74HCT374", "74xx:74LS374", DIP[20], "PS/2 command latch (OUT PD)"),
    "IC44": ("74LS244", "74xx:74LS244", DIP[20], "PS/2 status (IN PD): FULL, SRC, BUSY"),
    "IC45": ("74HCT74", "74xx:74LS74", DIP[14], "FULL and BUSY flags"),
    "IC46": ("7416", "74xx:74LS05", DIP[14], "open collector: the ATmega's reset, -INT"),
    "Y1":   ("16MHz", "Device:Crystal", "Crystal:Crystal_HC49-U_Vertical", "ATmega clock"),
    "J2":   ("KEYBOARD", LOCAL + ":MINIDIN6", LOCAL + ":MiniDIN6_MD-60SM", "PS/2 keyboard (Same Sky MD-60SM)"),
    "J3":   ("MOUSE", LOCAL + ":MINIDIN6", LOCAL + ":MiniDIN6_MD-60SM", "PS/2 mouse (Same Sky MD-60SM)"),
    "F1":   ("0.5A PTC", "Device:Polyfuse", "Fuse:Fuse_Bourns_MF-RHT050", "PS/2 +5 V (J2 / J3 pin 4), resettable"),
    "J4":   ("FTDI", "Connector_Generic:Conn_01x06", FP_H % 6, "GND CTS VCC(nc) TXD RXD DTR: bootloader, console"),
    "JP1":  ("INT-EN", "Connector_Generic:Conn_01x02", FP_H % 2, "fitted: the card may drive -INT"),
    "R11":  ("10k", "Device:R", FP_R, "ATmega reset pull-up"),
    "R12":  ("4.7k", "Device:R", FP_R, "RESETH pull-up (bus -RESET to MRST through IC46)"),
    "R13":  ("10k", "Device:R", FP_R, "LDDATA pull-up (idle high through the ATmega's reset)"),
    "R14":  ("10k", "Device:R", FP_R, "RDCMD pull-up"),
    "R15":  ("10k", "Device:R", FP_R, "INTREQ pull-down (an HCT input, the ATmega's pin floats in reset)"),
    "R16":  ("4.7k", "Device:R", FP_R, "keyboard clock pull-up"),
    "R17":  ("4.7k", "Device:R", FP_R, "keyboard data pull-up"),
    "R18":  ("4.7k", "Device:R", FP_R, "mouse clock pull-up"),
    "R19":  ("4.7k", "Device:R", FP_R, "mouse data pull-up"),
    "C50":  ("22p", "Device:C", FP_C, "Y1 load"),
    "C51":  ("22p", "Device:C", FP_C, "Y1 load"),
    "C52":  ("100n", "Device:C", FP_C, "FTDI DTR auto-reset"),
    # --- passives, jumpers
    "R1":   ("330", "Device:R", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", "PWR LED"),
    "R2":   ("1k", "Device:R", FP_R, "PU: the F parts' unused inputs high"),
    "LED1": ("PWR", "Device:LED", "LED_THT:LED_D5.0mm", "power"),
    "RN1":  ("10k x4", "Device:R_Network04", "Resistor_THT:R_Array_SIP5", "SV1 pull-ups"),
    "SV1":  ("BLOCK", "Connector_Generic:Conn_02x04_Odd_Even", "Connector_PinHeader_2.54mm:PinHeader_2x04_P2.54mm_Vertical",
             "fitted = 0: 5-6 only = the $D000 block"),
    "C1":   ("47u 16V", "Device:C_Polarized", "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm", "bulk"),
}
NIC = 46
DECOUPLE = {"C%d" % (n + 1): "IC%d" % n for n in range(1, NIC + 1)}       # one for each IC: C2-C47
DECOUPLE["C48"] = "OSC1"
DECOUPLE["C49"] = "IC41"                                                  # the ATmega's AVCC
for cap, ic in DECOUPLE.items():
    PARTS[cap] = ("100n", "Device:C", FP_C, "%s decoupling" % ic)

# every pin a part has, for check(): DIP pins by number, the others by name
PINS = {"X1": ["%s%d" % (r, n) for r in "ABC" for n in range(1, 33)],
        "OSC1": ["1", "7", "8", "14"], "J1": [str(n) for n in range(1, 16)] + ["SH"], "Y1": ["1", "2"], "F1": ["1", "2"],
        "J2": ["1", "2", "3", "4", "5", "6", "S"], "J3": ["1", "2", "3", "4", "5", "6", "S"], "LED1": ["1", "2"],
        "RN1": [str(n) for n in range(1, 6)], "RN2": [str(n) for n in range(1, 10)], "SV1": [str(n) for n in range(1, 9)]}
for ref, (val, sym, fp, note) in PARTS.items():
    if ref in PINS: continue
    if ref.startswith("IC"): PINS[ref] = [str(n) for n in range(1, int(fp.split("DIP-")[1].split("_")[0]) + 1)]
    elif ref.startswith(("JP", "J4")): PINS[ref] = [str(n) for n in range(1, int(fp.split("_1x")[1][:2]) + 1)]
    else: PINS[ref] = ["1", "2"]                                           # R, C

POWER_PINS = {  # ref -> (VCC pins, GND pins)
    "IC10": ((20,), (1,)), "IC41": ((7, 20), (8, 22)),
}
for ref in PARTS:
    if ref.startswith("IC") and ref not in POWER_PINS:
        n = len(PINS[ref])
        POWER_PINS[ref] = ((n,), (n // 2,))                                # the corner pins of every other DIP here

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
c("VCC", "R1.1"); c("LEDA", "R1.2", "LED1.2"); c("GND", "LED1.1")
c("VCC", "R2.1"); PU = "PU"                                                # the F parts' tie-high net (R2)
c(PU, "R2.2")

# ---- the bus ---------------------------------------------------------------------------------------------------------
for i in range(16):
    c("ADDR%d" % i, "X1.A%d" % (3 + i))
for i in range(8):
    c("DATA%d" % i, "X1.A%d" % (19 + i))
c("-MEM-RD", "X1.B23"); c("-MEM-WR", "X1.B24"); c("-VMA", "X1.C12"); c("-RESET", "X1.C30")
for i in range(4):
    c("IO-ADDR%d" % i, "X1.C%d" % (7 + i))
c("-IO-RD", "X1.B25"); c("-IO-WR", "X1.B26"); c("-INT", "X1.C13")

# ---- board select: IC1 74S85 (A = SV1 with RN1 pull-ups, B = ADDR12..15, A=B in = VMA), as V2.0 ----------------------
c("ADDR12", "IC1.9"); c("ADDR13", "IC1.11"); c("ADDR14", "IC1.14"); c("ADDR15", "IC1.1")
for i, (a_pin, sv, rn) in enumerate(((10, 7, 2), (12, 5, 3), (13, 3, 4), (15, 1, 5))):
    c("SEL%d" % i, "IC1.%d" % a_pin, "SV1.%d" % sv, "RN1.%d" % rn)
c("GND", "SV1.2", "SV1.4", "SV1.6", "SV1.8", "IC1.2", "IC1.4")
c("VCC", "RN1.1")
c("-VMA", "IC8.1"); c("VMA", "IC8.2", "IC1.3")
c("BOARDSEL", "IC1.6", "IC37.1", "IC23.1")
# the two halves of the block: $D000-$D7FF the text RAM (TXTCE#), $D800-$DFFF the graphics window (GSEL)
c("ADDR11", "IC8.3", "IC23.2"); c("NADDR11", "IC8.4", "IC37.2")
c("TXTCE#", "IC37.3", "IC14.47")                                           # NAND(BOARDSEL, NOT ADDR11)
c("GSEL", "IC23.3", "IC23.4", "IC37.4")                                    # BOARDSEL AND ADDR11
c("-MEM-RD", "IC8.5"); c("MEMRD", "IC8.6", "IC37.5")
c("-MEM-WR", "IC8.9"); c("MEMWR", "IC8.8", "IC23.5")
c("GWR", "IC23.6", "IC34.2", "IC37.13")                                    # GSEL AND MEMWR: a window write strobe
c("GRDOE#", "IC37.6", "IC38.13", "IC4.9", "IC4.12")                        # NAND(GSEL, MEMRD): a window read

# ---- text RAM IC14 (IDT7134): the right port the CPU's, the left port the display's ----------------------------------
c("GND", "IC14.1", "IC14.5", "IC14.3", "IC14.45"); c("VCC", "IC14.2")     # -CEL, -OEL low; A11L, A11R low; R/-WL high
for i, pin in enumerate((42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 44)):
    c("ADDR%d" % i, "IC14.%d" % pin)
for i in range(8):
    c("DATA%d" % i, "IC14.%d" % (25 + i))
c("-MEM-RD", "IC14.43"); c("-MEM-WR", "IC14.46")
c("D3", "IC14.6")                                                          # A0L = the half
for i, pin in enumerate((7, 8, 9, 10, 11, 12, 13, 14, 15, 4)):             # A1L-A10L = SA0-SA9
    c("SA%d" % i, "IC14.%d" % pin)
for i in range(8):
    c("VD%d" % i, "IC14.%d" % (16 + i), "IC17.%d" % (2 + i))               # the code, to its register

# ---- the 6845 IC10 on PA / PB (the bus side as V2.0), and the stage IC15 / IC16 -------------------------------------
c("-RESET", "IC10.2"); c("GND", "IC10.3")                                  # LPSTB tied low
for i in range(8):
    c("MA%d" % i, "IC10.%d" % (4 + i), "IC15.%d" % (2 + i)); c("SA%d" % i, "IC15.%d" % (19 - i))
c("MA8", "IC10.12", "IC16.2"); c("MA9", "IC10.13", "IC16.3")
c("DE", "IC10.18", "IC16.4"); c("CURSOR", "IC10.19", "IC16.5"); c("HSYNC", "IC10.39", "IC16.6"); c("VSYNC", "IC10.40", "IC16.7")
c("GND", "IC16.8", "IC16.9", "IC15.1", "IC16.1")                           # two spare bits; both -OE on
c("SA8", "IC16.19"); c("SA9", "IC16.18")
c("SDE", "IC16.17", "IC12.12", "IC7.6"); c("SCUR", "IC16.16", "IC23.9")
c("SHS", "IC16.15", "IC8.11", "IC40.3", "IC40.11"); c("SVS", "IC16.14", "IC13.13", "IC40.2", "IC7.4")
c("STG", "IC13.2", "IC15.11", "IC16.11", "IC22.4")                         # NOT D3: rises as dot 0 begins
c("CRTCCK", "IC12.5", "IC10.21")
c("-IO-WR", "IC10.22"); c("CRTCE", "IC22.3", "IC10.23"); c("IO-ADDR0", "IC10.24"); c("CRTCCS#", "IC9.3", "IC10.25")
for i in range(8):
    c("DATA%d" % i, "IC10.%d" % (33 - i))
for i, pin in enumerate((38, 37, 36, 35)):
    c("RA%d" % i, "IC10.%d" % pin)
c("-IO-RD", "IC22.1"); c("-IO-WR", "IC22.2")                               # E = -IO-RD XOR -IO-WR (IC22/A)

# ---- port decode IC2, strobes IC3 / IC4 ------------------------------------------------------------------------------
c("IO-ADDR0", "IC2.1"); c("IO-ADDR1", "IC2.2"); c("IO-ADDR2", "IC2.3"); c("IO-ADDR3", "IC2.6")
c("GND", "IC2.4", "IC2.5")
c("PSEL_A#", "IC2.13", "IC9.1"); c("PSEL_B#", "IC2.12", "IC9.2")           # the 6845's -CS = PSEL_A# AND PSEL_B# (IC9/A)
c("PSEL_C#", "IC2.11", "IC3.1", "IC3.4"); c("PSEL_D#", "IC2.10", "IC3.9", "IC3.12")
c("PSEL_E#", "IC2.9", "IC4.1"); c("PSEL_F#", "IC2.7", "IC4.4")
c("-IO-WR", "IC3.2", "IC3.10", "IC4.5"); c("-IO-RD", "IC3.5", "IC3.13", "IC4.2")
c("CTL1CK", "IC3.3", "IC5.11"); c("STATOE#", "IC3.6", "IC7.1", "IC7.19")
c("CMDCK", "IC3.8", "IC43.11", "IC45.11"); c("PSTOE#", "IC3.11", "IC44.1", "IC44.19")
c("PDOE#", "IC4.3", "IC42.1", "IC9.12"); c("CTL2CK", "IC4.6", "IC6.11")

# ---- the control registers IC5 (OUT PC), IC6 (OUT PF) and the card status IC7 (IN PC) --------------------------------
Q273 = ((3, 2), (4, 5), (7, 6), (8, 9), (13, 12), (14, 15), (17, 16), (18, 19))       # (D, Q) bits 0..7; a '374 the same
CTL1 = ("PLANE0", "PLANE1", "PLANE2", "PLANE3", "CPAGE", "DPAGE", "GFXON", "XORM")
CTL2 = ("TEXTOFF", "CURH", "POLH", "POLV", None, "OFFR", "OFFG", "OFFB")              # bit 4 spare
c("-RESET", "IC5.1", "IC6.1")
for i, (d, q) in enumerate(Q273):
    c("DATA%d" % i, "IC5.%d" % d, "IC6.%d" % d)
    c(CTL1[i], "IC5.%d" % q)
    if CTL2[i]: c(CTL2[i], "IC6.%d" % q)
Y244 = ((2, 18), (4, 16), (6, 14), (8, 12), (11, 9), (13, 7), (15, 5), (17, 3))       # (A, Y) bits 0..7
for i, (a, y) in enumerate(Y244):
    c("DATA%d" % i, "IC7.%d" % y)
c("GND", "IC7.2", "IC7.17"); c("VCC", "IC7.11", "IC7.13", "IC7.15")       # bit 0 = 0; bits 7..4 = 0111 (the ID $7x)
c("TXTONLY", "IC7.8", "IC34.9", "R10.1"); c("VCC", "R10.2")               # bit 3: 0 = graphics fitted (IC34/B's Q)

# ---- the dot clock, the counter IC11, the 6845's clock and SDE2 (IC12), the inverters IC13 ---------------------------
c("CK", "OSC1.8", "IC11.2", "IC12.3", "IC20.11", "IC35.3", "IC35.11", "IC19.12", "IC33.12")
c(PU, "IC11.1", "IC11.7", "IC11.9", "IC11.10")                             # -CLR, ENP, -LOAD, ENT: it only counts
c("GND", "IC11.3", "IC11.4", "IC11.5", "IC11.6")
c("D0", "IC11.14", "IC21.1", "IC38.9")
c("D1", "IC11.13", "IC21.2", "IC38.10", "IC13.5")
c("D2", "IC11.12", "IC13.3", "IC21.9", "IC17.11", "IC32.11", "IC20.3", "IC34.3", "IC36.1", "IC38.11")
c("D3", "IC11.11", "IC12.2", "IC12.11", "IC13.1")
c(PU, "IC12.1", "IC12.4", "IC12.10", "IC12.13")
c("SDE2", "IC12.9", "IC21.5")
c("D2N", "IC13.4", "IC21.4"); c("D1N", "IC13.6", "IC21.10")
c("GFXON", "IC13.9"); c("NGFX", "IC13.8", "IC36.2", "IC36.5", "IC4.10", "IC37.12")
c("TEXTOFF", "IC13.11"); c("TEXTON", "IC13.10", "IC19.9")
c("NSVS", "IC13.12", "IC36.12")

# ---- the text pipeline: code register IC17, character generator IC18, shifter IC19, the cursor flag ------------------
# IC18 (AT28C64B): A0-A3 = RA0-3, A4-A11 = the code, A12 = CURF (the upper half holds each glyph's cursor form);
# -CE, -OE low, -WE high (never written on the card), pins 1 and 26 not connected
ROM_A = {0: 10, 1: 9, 2: 8, 3: 7, 4: 6, 5: 5, 6: 4, 7: 3, 8: 25, 9: 24, 10: 21, 11: 23, 12: 2}
ROM_D = (11, 12, 13, 15, 16, 17, 18, 19)
IO299 = {0: 7, 1: 13, 2: 6, 3: 14, 4: 5, 5: 15, 6: 4, 7: 16}              # a '299's parallel pins A..H; H leaves first
c("GND", "IC17.1")
for i in range(4):
    c("RA%d" % i, "IC18.%d" % ROM_A[i])
for i in range(8):
    c("CA%d" % i, "IC17.%d" % (19 - i), "IC18.%d" % ROM_A[4 + i])
    c("CG%d" % i, "IC18.%d" % ROM_D[i], "IC19.%d" % IO299[i])              # bit 7 is the left-hand dot
c("GND", "IC18.20", "IC18.22"); c("VCC", "IC18.27")
c(PU, "IC19.1", "IC19.2", "IC19.3"); c("GND", "IC19.11", "IC19.18")       # S0 and both -OE high; zeros shifted in
c("TLOAD", "IC21.6", "IC19.19", "IC33.19")                                 # D0 AND D1 AND NOT D2 AND SDE2 (IC21/A)
c("TDOT", "IC19.17", "IC39.2", "IC38.3")
# the cursor: CURX = STG XOR CURH = 1 where the half (D3) equals CURH; CURF's D = SCUR AND CURX, taken with the code
c("CURH", "IC22.5"); c("CURX", "IC22.6", "IC23.10"); c("CURFD", "IC23.8", "IC20.2")
c("CURF", "IC20.5", "IC18.%d" % ROM_A[12])
c(PU, "IC20.1", "IC20.4", "IC20.10", "IC20.13")

# ---- graphics: the address muxes IC24-IC27 (S = SELCPU: 1 = the CPU on I1, 0 = the display on I0), the RAM IC28 ------
MUX = [("IC24", ("ADDR0", "D3"), ("ADDR1", "SA0"), ("ADDR2", "SA1"), ("ADDR3", "SA2")),
       ("IC25", ("ADDR4", "SA3"), ("ADDR5", "SA4"), ("ADDR6", "SA5"), ("ADDR7", "SA6")),
       ("IC26", ("ADDR8", "SA7"), ("ADDR9", "SA8"), ("ADDR10", "SA9"), ("PLANE0", "RA0")),
       ("IC27", ("PLANE1", "RA1"), ("PLANE2", "RA2"), ("PLANE3", "RA3"), ("CPAGE", "DPAGE"))]
SECTIONS = ((3, 2, 4), (6, 5, 7), (10, 11, 9), (13, 14, 12))              # (CPU = I1, display = I0, Z) of a, b, c, d
RAM_A = {0: 12, 1: 11, 2: 10, 3: 9, 4: 8, 5: 7, 6: 6, 7: 5, 8: 27, 9: 26, 10: 23, 11: 25, 12: 4, 13: 28, 14: 3, 15: 31, 16: 2}
RAM_D = (13, 14, 15, 17, 18, 19, 20, 21)
for k, (ref, *sections) in enumerate(MUX):
    c("SELCPU", ref + ".1"); c("GND", ref + ".15")
    for j, ((cpu, disp), (i1, i0, z)) in enumerate(zip(sections, SECTIONS)):
        c(cpu, "%s.%d" % (ref, i1)); c(disp, "%s.%d" % (ref, i0))
        c("GA%d" % (4 * k + j), "%s.%d" % (ref, z), "IC28.%d" % RAM_A[4 * k + j])
c("GND", "IC28.%d" % RAM_A[16], "IC28.22"); c("VCC", "IC28.30")          # A16 low: the lower 64K; -CE low, CE2 high
c("GOE#", "IC38.12", "IC28.24")
c("GWE#", "IC23.11", "IC28.29", "IC29.1", "IC29.19")                       # the write buffer is on only during -WE

# ---- the write buffer IC29, the read latch IC30, the direct-mode buffer IC31, the byte latch IC32, the shifter IC33 --
for i, (a, y) in enumerate(Y244):
    c("GD%d" % i, "IC28.%d" % RAM_D[i], "RN2.%d" % (2 + i), "IC29.%d" % y, "IC31.%d" % a, "IC30.%d" % (2 + i), "IC32.%d" % (2 + i))
    c("DATA%d" % i, "IC29.%d" % a, "IC31.%d" % y, "IC30.%d" % (19 - i))
    c("GL%d" % i, "IC32.%d" % (19 - i), "IC33.%d" % IO299[i])
c("VCC", "RN2.1")
c("RDCK", "IC35.9", "IC30.11")
c("SRDOE#", "IC4.8", "IC30.1")                                             # GRDOE# OR NOT GFX-ON: slot mode's read
c("DRDOE#", "IC4.11", "IC31.1", "IC31.19"); c("GFXON", "IC4.13")          # GRDOE# OR GFX-ON: direct mode's read
c("GND", "IC32.1")
c(PU, "IC33.1", "IC33.2", "IC33.3"); c("GND", "IC33.11", "IC33.18"); c("GFXON", "IC33.9")
c("GDOT", "IC33.17", "IC39.3", "IC38.4", "R8.1"); c("GND", "R8.2")

# ---- the slot logic: SELCPU, WRQ (IC34/A), P56 and RDCK (IC35), -WE, -OE ----------------------------------------------
c("SELCPU", "IC36.3", "IC38.2")                                            # D2 OR NOT GFX-ON (IC36/A)
c("P56D", "IC21.8", "IC35.2")                                              # D2 AND NOT D1 (IC21/B): dots 4, 5, 12, 13
c("P56", "IC35.5", "IC37.10")                                              # IC35/A's Q: dots 5-6 and 13-14
# WRQ: GWR taken on D2's rise; GFX-ON = 0 holds it clear, so no pulse can come as slot mode begins. Once WRQ is set
# the pulse WEP# = NAND(WRQ, P56) is a whole one: the strobe's end does not cut it short
c("WRQ", "IC34.5", "IC36.4", "IC37.9", "R9.1"); c("GND", "R9.2")
c("GFXON", "IC34.1"); c(PU, "IC34.4", "IC34.10")
c("WOE", "IC36.6", "IC38.1")                                               # WRQ OR NOT GFX-ON (IC36/B), for GOE#
c("WEP#", "IC37.8", "IC23.12"); c("WED#", "IC37.11", "IC23.13")           # -WE = WEP# AND WED# (IC23/D)
c("GND", "IC34.11", "IC34.12", "IC34.13")                                  # IC34/B: -CLR held low, Q = 0 = TXTONLY
c("RDCKD", "IC38.8", "IC35.12")                                            # D0 AND D1 AND D2 (IC38/C): dots 7 and 15
c(PU, "IC21.12", "IC21.13", "IC35.1", "IC35.4", "IC35.10", "IC35.13")

# ---- the dots: mix, retime, guns; the syncs; the VGA socket ----------------------------------------------------------
c("XORM", "IC38.5"); c("BX", "IC38.6", "IC36.10"); c("NGOT", "IC39.1", "IC36.9")
c("VIDN", "IC36.8", "IC20.12"); c("VIDNQ", "IC20.9", "IC39.5", "IC39.8", "IC39.11")
c("OFFR", "IC39.6"); c("OFFG", "IC39.9"); c("OFFB", "IC39.12")
c("VR", "IC39.4", "R3.1"); c("VG", "IC39.10", "R4.1"); c("VB", "IC39.13", "R5.1")
c("RED", "R3.2", "J1.1"); c("GREEN", "R4.2", "J1.2"); c("BLUE", "R5.2", "J1.3")
# HSYNC: the staged pulse inverted (IC8/E), then XOR POLH: negative after -RESET
c("NSHS", "IC8.10", "IC22.9"); c("POLH", "IC22.10"); c("HSB", "IC22.8", "R6.1"); c("HSOUT", "R6.2", "J1.13")
# VSYNC: IC40 takes SVS at each HSYNC (VQ1) and VQ1 at the next (VQ2); VS2# = NOT SVS OR VQ2 is low from SVS's rise
# to the second HSYNC after it, whatever length the 6845 gives its own pulse; then XOR POLV
c("VQ1", "IC40.5", "IC40.12"); c("VQ2", "IC40.9", "IC36.13")
c("VCC", "IC40.1", "IC40.4", "IC40.10", "IC40.13")
c("VS2#", "IC36.11", "IC22.12"); c("POLV", "IC22.13"); c("VSB", "IC22.11", "R7.1"); c("VSOUT", "R7.2", "J1.14")
c("GND", "J1.5", "J1.6", "J1.7", "J1.8", "J1.10", "J1.SH")
c("GND", "IC8.13")                                                         # the spare inverter

# ---- PS/2: IC41 ATmega328P, latches IC42 / IC43, status IC44, flags IC45, IC46, IC9 (V2.0's nets) --------------------
c("MRST", "IC41.1", "R11.1", "C52.2", "IC46.12"); c("VCC", "R11.2")
c("-RESET", "IC9.9", "IC9.13"); c("VCC", "IC9.10"); c("RESETB", "IC9.8", "IC46.11")
c("RESETH", "IC46.10", "R12.1", "IC46.13"); c("VCC", "R12.2")
c("FTX", "IC41.2", "J4.4"); c("FRX", "IC41.3", "J4.5"); c("FDTR", "J4.6", "C52.1"); c("GND", "J4.1", "J4.2")
c("KCLK", "IC41.4", "R16.1", "J2.5"); c("MCLK", "IC41.5", "R18.1", "J3.5")
c("KDAT", "IC41.6", "R17.1", "J2.1"); c("MDAT", "IC41.11", "R19.1", "J3.1")
c("VCC", "R16.2", "R17.2", "R18.2", "R19.2", "F1.1"); c("PS2VCC", "F1.2", "J2.4", "J3.4")
c("GND", "J2.3", "J3.3", "J2.S", "J3.S")
c("XT1", "IC41.9", "Y1.1", "C50.1"); c("XT2", "IC41.10", "Y1.2", "C51.1"); c("GND", "C50.2", "C51.2")
c("LDDATA", "IC41.12", "IC42.11", "IC45.3", "R13.1"); c("RDCMD", "IC41.13", "IC43.1", "IC45.13", "R14.1")
c("VCC", "R13.2", "R14.2")
for i, pin in enumerate((23, 24, 25, 26, 27, 28, 14, 15)):
    c("MD%d" % i, "IC41.%d" % pin)
for i, (d, q) in enumerate(Q273):
    c("MD%d" % i, "IC42.%d" % d, "IC43.%d" % q); c("DATA%d" % i, "IC42.%d" % q, "IC43.%d" % d)
c("FULL", "IC41.16", "IC45.5", "IC44.2", "IC9.5"); c("SRC", "IC41.19", "IC44.4")
c("INTREQ", "IC41.18", "IC9.4", "R15.1"); c("GND", "R15.2"); c("INTG", "IC9.6", "IC46.9")
c("BUSY", "IC41.17", "IC45.9", "IC44.6")
for i, (a, y) in enumerate(Y244):
    c("DATA%d" % i, "IC44.%d" % y)
c("GND", "IC44.8", "IC44.11", "IC44.13", "IC44.15", "IC44.17")
c("VCC", "IC45.2", "IC45.4", "IC45.12", "IC45.10")                        # D high, -PRE high
c("FULLCLR#", "IC9.11", "IC45.1")                                          # IN PE or -RESET clears FULL
c("INTOC", "IC46.8", "JP1.1"); c("-INT", "JP1.2")
c("GND", "IC46.1", "IC46.3", "IC46.5")                                     # three spare inverters

# ---- pins left open ----------------------------------------------------------------------------------------------------
NO_CONNECT = {
    "IC1": [5, 7], "IC2": [15, 14], "IC6": [12], "IC8": [12], "IC10": [14, 15, 16, 17, 34],     # MA10-13, RA4
    "IC11": [15], "IC12": [6, 8], "IC16": [13, 12], "IC18": [1, 26], "IC19": [8], "IC20": [6, 8], "IC21": [3, 11],
    "IC28": [1], "IC33": [8], "IC34": [6, 8], "IC35": [6, 8], "IC40": [6, 8],
    "IC41": [21], "IC45": [6, 8], "IC46": [2, 4, 6], "J4": [3], "J2": [2, 6], "J3": [2, 6],
    "J1": [4, 9, 11, 12, 15], "OSC1": [1],
}
_X1_USED = ({"A1", "B1", "C1", "A32", "B32", "C32", "A2", "B2", "C2", "A31", "B31", "C31", "B23", "B24", "B25", "B26",
             "C7", "C8", "C9", "C10", "C12", "C13", "C30"} | {"A%d" % n for n in range(3, 27)})
NO_CONNECT["X1"] = [p for p in PINS["X1"] if p not in _X1_USED]
NO_CONNECT = {r: [str(p) for p in ps] for r, ps in NO_CONNECT.items()}

# outputs that drive a net (for check(): no two on one net). The bus, GD and MD are shared by three-state parts
# enabled at different times, and -INT by open collectors: those nets are left out.
SHARED = ("DATA", "GD", "MD", "-INT")
_Q574 = tuple(range(12, 20))
_Q374 = tuple(q for d, q in Q273)
_Y244 = tuple(y for a, y in Y244)
_GATE4 = (3, 6, 8, 11)
_FF = (5, 6, 9, 8)
OUTPUTS = {"IC1": (5, 6, 7), "IC2": (15, 14, 13, 12, 11, 10, 9, 7), "IC3": _GATE4, "IC4": _GATE4, "IC5": _Q374, "IC6": _Q374,
           "IC7": _Y244, "IC8": (2, 4, 6, 8, 10, 12), "IC9": _GATE4,
           "IC10": tuple(range(4, 20)) + (34, 35, 36, 37, 38, 39, 40), "OSC1": (8,),
           "IC11": (11, 12, 13, 14, 15), "IC12": _FF, "IC13": (2, 4, 6, 8, 10, 12),
           "IC14": tuple(range(16, 24)), "IC15": _Q574, "IC16": _Q574, "IC17": _Q574, "IC18": ROM_D, "IC19": (8, 17),
           "IC20": _FF, "IC21": (6, 8), "IC22": _GATE4, "IC23": _GATE4,
           "IC24": (4, 7, 9, 12), "IC25": (4, 7, 9, 12), "IC26": (4, 7, 9, 12), "IC27": (4, 7, 9, 12),
           "IC28": RAM_D, "IC29": _Y244, "IC30": _Q574, "IC31": _Y244, "IC32": _Q574, "IC33": (8, 17), "IC34": _FF,
           "IC35": _FF, "IC36": _GATE4, "IC37": _GATE4, "IC38": (12, 6, 8), "IC39": (1, 4, 10, 13), "IC40": _FF,
           "IC42": _Q374, "IC43": _Q374, "IC44": _Y244, "IC45": _FF, "IC46": (2, 4, 6, 8, 10, 12),
           "RN2": tuple(range(2, 10))}

# ---- what to buy: the parts whose exact type matters (for the bill of materials) --------------------------------------
BUY = {
    "IC10": "HD68B45SP (Hitachi) or MC68B45P (Motorola), the 2 MHz (B) bus grade for a CPU clock above 1 MHz (a 6 MHz "
            "CPU's OUT gives E 333 ns high); the card's 1.573 MHz character clock is inside every grade. At the "
            "machine's 1 MHz the V1.0 card's 6845 fits",
    "IC14": "IDT7134 SA or LA, 55 ns (the commercial grade; the sheet's slowest is 70 ns, there is no 90), DIP-48; or the V1.0 card's chip",
    "IC18": "AT28C64B-15PU (Microchip), 150 ns, burned with the card's character generator image (256 glyphs of "
            "8 x 16 and their cursor forms: to be made)",
    "IC28": "AS6C1008-55PCN (Alliance, 128K x 8, 55 ns, 600-mil DIP-32)",
    "OSC1": "25.175 MHz oscillator, 5 V, TTL / HCMOS output, full-size DIP-14 can, in a 4-pin socket",
    "IC11": "74F163A: the type the timing is worked out with (not LS or HCT)",
    "IC12": "74F74", "IC20": "74F74", "IC34": "74F74", "IC35": "74F74", "IC19": "74F299", "IC33": "74F299", "IC21": "74F21",
    "IC30": "74ACT574: its hold time (1 ns) is what the read latch's clock is worked out with; it drives the bus",
    "IC29": "SN74ACT244N: the type the timing check was run with; TI's package list marked the DIP 'last time buy' in 2026-11",
    "IC31": "74HCT244; a 74ACT244 (24 mA) if DATA0's low level during a window read is above 0.5 V (V2.0's R2-6)",
    "IC41": "ATmega328P-PU with the Arduino Uno bootloader burned (ISP) before fitting",
    "IC1": "74S85 (the V1.x card's; a 74LS85 also works)",
    "J2": "Same Sky (CUI Devices) MD-60SM, date code after 2022-03-03 (the footprint follows that layout)",
    "J3": "Same Sky (CUI Devices) MD-60SM, date code after 2022-03-03",
    "F1": "Bourns MF-RHT050 (0.5 A hold, radial)",
    "J4": "1x6 pin header; a 5 V FTDI cable (TTL-232R-5V) or a 5 V FTDI Basic",
    "Y1": "16 MHz, HC-49/U, parallel resonant, 18-20 pF load (for C50 / C51 22 pF, as on an Arduino Uno)",
    "RN1": "10k x4 BUSSED, pin 1 common, 5-pin SIP; not an isolated network",
    "RN2": "10k x8 BUSSED, pin 1 common, 9-pin SIP; not an isolated network",
    "C1": "47 uF electrolytic, 16 V or more, radial 6.3 mm, 2.5 mm pitch",
    "J1": "DE-15 (HD-15) socket, right-angle PCB mount, 3.03 mm from the pins to the edge",
}
for _r, _p in PARTS.items():
    if _p[0] == "100n": BUY[_r] = "ceramic X7R, 50 V, 2.5 mm lead spacing"
    elif _p[0] == "22p": BUY[_r] = "ceramic C0G (NP0), 50 V, 2.5 mm lead spacing"
SOCKETS = "every IC in a socket (the 6845, the IDT7134, the 28C64, the RAM, the oscillator and the ATmega at least)"

# ---- the text-only build ----------------------------------------------------------------------------------------------
# Left off: the graphics parts. What their outputs reach in the fitted logic: GDOT (R8 holds it low), WRQ (R9 holds
# it low) and TXTONLY (R10 pulls it high: IN PC bit 3 = 1). IC35 - IC38 stay: they carry text and bus logic too.
TEXT_ONLY_LEFT_OFF = ["IC%d" % n for n in range(24, 35)] + ["RN2"] + ["C%d" % n for n in range(25, 36)]
THREE_STATE_TO_BUS = {"IC30", "IC31"}       # their outputs on DATA0..7 are released when the chip is absent
TEXT_ONLY_PULLS = {"GDOT": "R8", "WRQ": "R9", "TXTONLY": "R10"}


def text_only_check():
    """-> {net: [fitted pins]} for every net a left-off part drives (an output pin) that reaches a part still fitted;
    the 3-state bus drivers onto DATA are left out (absent = released)"""
    off = set(TEXT_ONLY_LEFT_OFF)
    out = {}
    for net, conns in NETS.items():
        if net in ("VCC", "GND", PU): continue
        drivers = [(r, p) for r, p in conns if r in off and p.isdigit() and int(p) in OUTPUTS.get(r, ()) and
                   not (r in THREE_STATE_TO_BUS and net.startswith("DATA"))]
        fitted = sorted({"%s.%s" % (r, p) for r, p in conns if r not in off})
        if drivers and fitted:
            out[net] = fitted
    return out


def check():
    """every pin accounted for once, no single-pin net, no two outputs on a net, a capacitor for every IC, the
    text-only build; returns the list of faults"""
    faults = []
    seen = {}
    for net, pins in NETS.items():
        for ref, pin in pins:
            if ref not in PARTS: faults.append("%s: %s is not a part" % (net, ref)); continue
            if pin not in PINS[ref]: faults.append("%s: %s has no pin %s" % (net, ref, pin))
            if (ref, pin) in seen: faults.append("%s.%s is on %s and on %s" % (ref, pin, seen[(ref, pin)], net))
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
        drivers = [(r, p) for r, p in pins if p.isdigit() and int(p) in OUTPUTS.get(r, ()) and not r.startswith("RN")]
        if len(drivers) > 1: faults.append("net %s has %d outputs: %r" % (net, len(drivers), drivers))
        # a net of ICs only needs an output among them (one with a connector, a resistor or the ATmega is driven from there)
        if not drivers and net not in ("VCC", "GND", PU) and all(r.startswith("IC") and r != "IC41" for r, p in pins):
            faults.append("net %s has no output on it" % net)
    for ref in PARTS:
        if ref.startswith("IC") and ref not in OUTPUTS and ref != "IC41": faults.append("%s has no OUTPUTS entry" % ref)
        if (ref.startswith("IC") or ref == "OSC1") and ref not in DECOUPLE.values(): faults.append("%s has no capacitor" % ref)
    if sum(1 for r in PARTS if r.startswith("IC")) != NIC: faults.append("NIC is not the number of ICs")
    tob = text_only_check()
    if sorted(tob) != sorted(TEXT_ONLY_PULLS):
        faults.append("text-only build: left-off parts drive %s into fitted logic (want %s)" % (sorted(tob), sorted(TEXT_ONLY_PULLS)))
    for net, r in TEXT_ONLY_PULLS.items():
        if r not in {ref for ref, _ in NETS.get(net, [])}: faults.append("text-only build: %s has no %s" % (net, r))
    return faults


if __name__ == "__main__":
    f = check()
    ics = sum(1 for r in PARTS if r.startswith("IC"))
    print("%s %s: %d parts (%d ICs), %d nets, %d pins on nets" % (CARD, REV, len(PARTS), ics, len(NETS),
                                                                 sum(len(p) for p in NETS.values())))
    for x in f: print("  " + x)
    off = sum(1 for r in TEXT_ONLY_LEFT_OFF if r.startswith("IC"))
    print("check: %s" % ("%d faults" % len(f) if f else "every pin accounted for, no net with one pin, no two outputs on a net; "
                         "the text-only build leaves off %d ICs, which drive only %s into fitted logic" % (
                             off, ", ".join(sorted(TEXT_ONLY_PULLS)))))
    raise SystemExit(1 if f else 0)
