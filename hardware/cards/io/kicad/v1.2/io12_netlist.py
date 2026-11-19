# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""io12_netlist.py - the YACC1 I/O card V1.2: THE single source of its circuit (2026-11-18).

The card is the V1.1 card in the machine (docs/cards/io.md: the console UART, eight switches, eight LEDs, two TIL311
hex displays, the LCD, the IN switch and the OUT LED behind the two ports P0 and P1) with what its section 8 lists for
a next revision. To software it is the same card: the control latch's bits, the ports and the UART are V1.1's, pin for
pin, so the ROM in the machine runs on it unchanged. Plain Python data, no KiCad import; gen_io12.py reads it for the
schematic and the board. `python3 io12_netlist.py` runs check() and v11_check().

What V1.2 adds or changes (docs/cards/io.md section 8):

  the buffer     IC12, a 74LS245, stands between the bus's DATA0-7 and the card's own data lines ID0-7, on which the
                 UART, the three latches, the switch buffer, the LCD and the clock sit. Its direction is the bus's
                 -IO-RD (low: card to bus); it is enabled while one of the card's ports is addressed: BUFEN# = the AND
                 of the control port's and the data port's selects and of the clock's two (IC13). The enable is the
                 address alone, not a strobe: the latches clock late, through the open-collector strobes, and the
                 microcode holds the port number and the data a step past -IO-WR. RN2 holds ID0-7 high while the
                 buffer is off.
  the clock      IC15, a DS12885 with a 32.768 kHz crystal (Y1) and a CR2032 (BT1), on the card's ports 6 and 7 (P6 and
                 P7 with the card in the low half): a write of P6 is the register number (AS, taken as it falls), P7
                 is that register's data. Intel bus timing (MOT low), -CS low, -RESET high, as on System-5's IO panel.
                 AS = NOT(-IO-SEL6 OR -IO-WR), the chip's DS = -IO-SEL7 OR -IO-RD, its R/-W = -IO-SEL7 OR -IO-WR: from
                 the bus's own strobes (IC14, and IC7/C, V1.1's spare gate, as AS's inverter). Its open-drain -IRQ
                 reaches the bus -INT through JP8 (off until something uses interrupts). JP9 grounds -RCLR: fitted
                 with the power off it clears the chip's RAM, never the clock.
  -INT           V1.1's INT header stood before IC8/F: open, the gate's input floated high and the gate held -INT
                 low. Here the UART's INT goes straight to IC8/F and the jumper (JP7) stands between the gate's
                 output and the bus: off, the card never touches -INT.
  the serial     J2, a 6-pin TTL-level header with an FTDI cable's pins, beside the DB9: the UART's TX goes to both;
                 JP2 picks where its RX comes from (the MAX232 or the header). R12 holds the header's line high with
                 no cable.
  the panel      J1, the DB9, at the top edge (the edge opposite the bus connector), facing off the card; the LEDs,
                 the switches, the TIL311s and the LCD below it (gen_io12.py has the places).
  small things   the oscillator's pin 1 tied high (as the video card V4.0's); a resistor in series with the LCD's
                 backlight (R11); the MAX232's unused inputs tied off; pull-ups on the two port-select lines (no
                 jumper: no port); the DB9's shell on GND; every resistor's value written down.

Not taken from the list: IC5's G2B on -BUS-EN. The bus tester drives this card with -BUS-EN high (tests/io/io_test.py:
it owns the bus then), and the decoder would be off. G2B stays on GND. And the device bits stay four flags, not a
code: a decoder in their place would change what the ROM writes to P0.

Pin numbers are the physical pins. Bus pins: the V3.2 DIN 41612 connector (docs/system/BUS.md, tools/bus_pins.py).
Net names ending in # are active low; the bus's own names keep their leading minus.
"""

CARD = "YACC1 I/O card"
REV = "V1.2"
DATE = "2026-11-18"

DIP = {n: "Package_DIP:DIP-%d_W7.62mm" % n for n in (14, 16, 20)}
DIPW = {n: "Package_DIP:DIP-%d_W15.24mm" % n for n in (24, 40)}
FP_R = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"
FP_C = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm"            # 0.1-inch leads: the rule for every bypass capacitor
FP_CP = "Capacitor_THT:CP_Radial_D5.0mm_P2.50mm"
FP_H = "Connector_PinHeader_2.54mm:PinHeader_1x%02d_P2.54mm_Vertical"
FP_H2 = "Connector_PinHeader_2.54mm:PinHeader_2x%02d_P2.54mm_Vertical"
FP_LED = "LED_THT:LED_D5.0mm"
LOCAL = "io-v1.2-local"
BUSLIB = "blank-card-v3.2-eagle"
# the parts whose footprints are the built V1.1 card's own (hardware/cards/io/kicad/v1.1/io-v1.1-eagle.pretty): they
# fit the parts in hand. gen_io12.py copies them into the local library under these names
FP_DB9 = LOCAL + ":DSUB-9_Socket_Horizontal_IO-V1.1"
FP_SW = LOCAL + ":SW_Toggle_M9040P"
FP_TIL = LOCAL + ":HTIL311A"
FP_LCD = LOCAL + ":LCD1602"
FP_TRIM = LOCAL + ":Potentiometer_Trim_3386_Inline"

# ---- parts: reference -> (value, symbol lib:name, footprint lib:name, note) ------------------------------------------
PARTS = {
    "X1":   ("DIN41612 96", BUSLIB + ":FABC96R", BUSLIB + ":FABC96R", "bus connector (blank V3.2 card)"),
    # --- the ports, the strobes and the control latch (V1.1's, pin for pin)
    "IC5":  ("74LS138", "74xx:74LS138", DIP[16], "port decode: -IO-SEL0..7, the eight ports of the card's half (JP3)"),
    "IC8":  ("74LS06", "74xx:74LS06", DIP[14], "open collector: IO-RD, IO-WR, RESET, -B-RESET, IO-SELDATA, the UART's -INT"),
    "IC7":  ("74LS00", "74xx:74LS00", DIP[14], "the LCD's E; the control latch's clock; the clock chip's AS; IO-ADDRSEL"),
    "IC6":  ("74LS10", "74xx:74LS10", DIP[14], "the LEDs' clock; the switch buffer's enable; the LCD's strobe"),
    "IC11": ("74LS10", "74xx:74LS10", DIP[14], "the TIL311 latch's clock; two gates spare"),
    "IC10": ("74LS273", "74xx:74LS273", DIP[20], "control latch (P0): SWITCH-LED, LCD-ENABLE, LCD-REGISTER, UART-A0..2, UART-CS, TIL311"),
    # --- the data buffer (new)
    "IC12": ("74LS245", "74xx:74LS245", DIP[20], "data buffer: the bus's DATA0-7 to the card's ID0-7, direction from -IO-RD"),
    "IC13": ("74LS08", "74xx:74LS08", DIP[14], "the buffer's enable: one of the card's four ports addressed; one gate spare"),
    # --- the UART and the serial line
    "IC1":  ("16C550", LOCAL + ":UART_16550_DIP40", DIPW[40], "console UART behind P0 / P1"),
    "OSC1": ("1.8432MHz", "Oscillator:CXO_DIP8", "Oscillator:Oscillator_DIP-8", "the UART's clock: divisor 3 = 38400 baud"),
    "IC2":  ("MAX232", "Interface_UART:MAX232", DIP[16], "RS-232 levels for the DB9"),
    "C1":   ("1u", "Device:C_Polarized", FP_CP, "MAX232 charge pump, C1+ / C1-"),
    "C2":   ("1u", "Device:C_Polarized", FP_CP, "MAX232 charge pump, C2+ / C2-"),
    "C3":   ("1u", "Device:C_Polarized", FP_CP, "MAX232 V+ (to VCC)"),
    "C4":   ("1u", "Device:C_Polarized", FP_CP, "MAX232 V- (from GND)"),
    "J1":   ("RS-232", "Connector:DE9_Socket_MountingHoles", FP_DB9, "console: 2 and 3 through JP1, 5 GND"),
    "JP1":  ("NULL MODEM", "Connector_Generic:Conn_02x03_Odd_Even", FP_H2 % 3, "1-3 and 2-4: the card sends on DB9 pin 2; 3-5 and 4-6: on pin 3"),
    "J2":   ("TTL SERIAL", "Connector_Generic:Conn_01x06", FP_H % 6, "GND CTS VCC(nc) TXD RXD RTS(nc): an FTDI TTL-232R cable"),
    "JP2":  ("RX FROM", "Connector_Generic:Conn_01x03", FP_H % 3, "1-2: the UART hears the DB9; 2-3: the TTL header"),
    "R12":  ("10k", "Device:R", FP_R, "the TTL header's line into the UART held high with no cable"),
    # --- switches, LEDs, TIL311s
    "IC3":  ("74LS244", "74xx:74LS244", DIP[20], "switch buffer: S0-S7 to ID0-7 (IN P1 with SWITCH-LED)"),
    "IC4":  ("74LS273", "74xx:74LS273", DIP[20], "LED latch (OUT P1 with SWITCH-LED)"),
    "IC9":  ("74LS273", "74xx:74LS273", DIP[20], "TIL311 latch (OUT P1 with TIL311): LO the low nibble, HI the high"),
    "DS1":  ("TIL311 HI", LOCAL + ":TIL311", FP_TIL, "hex display, the high nibble"),
    "DS2":  ("TIL311 LO", LOCAL + ":TIL311", FP_TIL, "hex display, the low nibble"),
    "S8":   ("IN", "Switch:SW_SPDT", FP_SW, "the bus line IN (BRINH / BRINL): up = 1"),
    "JP6":  ("IN-EN", "Connector_Generic:Conn_01x02", FP_H % 2, "fitted: the IN switch drives the bus line IN"),
    "LED8": ("OUT", "Device:LED", FP_LED, "the bus line OUT (ON / OFF)"),
    "LED9": ("PWR", "Device:LED", FP_LED, "power"),
    "R1":   ("330", "Device:R", FP_R, "OUT LED"),
    "R2":   ("330", "Device:R", FP_R, "PWR LED"),
    # --- the LCD
    "DS3":  ("LCD 1602", "Display_Character:WC1602A", FP_LCD, "HD44780 16 x 2 module: write only (R/W on GND)"),
    "RV1":  ("10k", "Device:R_Potentiometer_Trim", FP_TRIM, "LCD contrast"),
    "R11":  ("47", "Device:R", FP_R, "LCD backlight, in series with the module's pin 15"),
    # --- the clock (new)
    "IC15": ("DS12885+", LOCAL + ":DS12885", DIPW[24], "real-time clock, calendar, 114 bytes of RAM: ports 6 (register) and 7 (data)"),
    "IC14": ("74LS32", "74xx:74LS32", DIP[14], "the clock chip's strobes from the bus's -IO-RD and -IO-WR; one gate spare"),
    "Y1":   ("32.768kHz", "Device:Crystal", "Crystal:Crystal_C26-LF_D2.1mm_L6.5mm_Vertical", "the clock's crystal, 6 pF"),
    "BT1":  ("CR2032", "Device:Battery_Cell", "Battery:BatteryHolder_Keystone_103_1x20mm", "the clock's cell, in a flat holder"),
    "JP8":  ("RTC INT", "Connector_Generic:Conn_01x02", FP_H % 2, "fitted: the clock's -IRQ drives -INT"),
    "JP9":  ("RAM CLR", "Connector_Generic:Conn_01x02", FP_H % 2, "fitted with the power off: the clock chip's RAM is cleared"),
    # --- jumpers of the ports and of -INT, pull-ups, power
    "JP3":  ("HALF", "Connector_Generic:Conn_02x03_Odd_Even", FP_H2 % 3, "3-5 and 4-6: ports P0-P7; 1-3 and 2-4: P8-PF"),
    "JP4":  ("CTL PORT", "Connector_Generic:Conn_02x08_Odd_Even", FP_H2 % 8, "one jumper: the control port. 15-16 = port 0 ... 1-2 = port 7"),
    "JP5":  ("DATA PORT", "Connector_Generic:Conn_02x08_Odd_Even", FP_H2 % 8, "one jumper: the data port. 13-14 = port 1"),
    "JP7":  ("UART INT", "Connector_Generic:Conn_01x02", FP_H % 2, "fitted: the UART's INT drives -INT"),
    "RN1":  ("2.2k x8", "Device:R_Network08", "Resistor_THT:R_Array_SIP9", "pull-ups: the open-collector strobes, -INT, the two port selects"),
    "RN2":  ("10k x8", "Device:R_Network08", "Resistor_THT:R_Array_SIP9", "ID0-7 pull-ups (the buffer off)"),
    "C5":   ("47u 16V", "Device:C_Polarized", "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm", "bulk"),
}
for n in range(8):                                             # bit n: its switch, its LED and the LED's resistor
    PARTS["S%d" % n] = ("%d" % n, "Switch:SW_SPDT", FP_SW, "switch bit %d: up = 1" % n)
    PARTS["LED%d" % n] = ("%d" % n, "Device:LED", FP_LED, "LED bit %d" % n)
    PARTS["R%d" % (n + 3)] = ("330", "Device:R", FP_R, "LED %d" % n)
NIC = 15
DECOUPLE = {"C%d" % (n + 5): "IC%d" % n for n in range(1, NIC + 1)}       # one for each IC: C6-C20
DECOUPLE["C21"] = "OSC1"
for cap, ic in DECOUPLE.items():
    PARTS[cap] = ("100n", "Device:C", FP_C, "%s decoupling" % ic)

# every pin a part has, for check(): DIP pins by number, the others as their symbols and footprints name them
PINS = {"X1": ["%s%d" % (r, n) for r in "ABC" for n in range(1, 33)],
        "OSC1": ["1", "4", "5", "8"], "J1": [str(n) for n in range(1, 10)] + ["0"],
        "DS1": ["1", "2", "3", "4", "5", "7", "8", "10", "12", "13", "14"],
        "DS2": ["1", "2", "3", "4", "5", "7", "8", "10", "12", "13", "14"],
        "DS3": [str(n) for n in range(1, 17)], "RV1": ["1", "2", "3"],
        "RN1": [str(n) for n in range(1, 10)], "RN2": [str(n) for n in range(1, 10)],
        "Y1": ["1", "2"], "BT1": ["1", "2"]}                               # BT1: 1 +, 2 -
for ref, (val, sym, fp, note) in PARTS.items():
    if ref in PINS: continue
    if ref.startswith("IC"): PINS[ref] = [str(n) for n in range(1, int(fp.split("DIP-")[1].split("_")[0]) + 1)]
    elif "_2x" in fp: PINS[ref] = [str(n) for n in range(1, 2 * int(fp.split("_2x")[1][:2]) + 1)]
    elif "_1x" in fp: PINS[ref] = [str(n) for n in range(1, int(fp.split("_1x")[1][:2]) + 1)]
    elif ref.startswith("S"): PINS[ref] = ["1", "2", "3"]                  # 1 and 3 the throws, 2 the pole
    else: PINS[ref] = ["1", "2"]                                           # R, C (1 +), LED (1 K, 2 A)

POWER_PINS = {  # ref -> (VCC pins, GND pins)
    "IC2": ((16,), (15,)), "IC15": ((24,), (12, 16)),
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


D273 = (3, 4, 7, 8, 13, 14, 17, 18)                                        # a 74273's D1..D8
Q273 = (2, 5, 6, 9, 12, 15, 16, 19)                                        # and its Q1..Q8

# ---- power -----------------------------------------------------------------------------------------------------------
for ref, (vcc, gnd) in POWER_PINS.items():
    c("VCC", *["%s.%d" % (ref, p) for p in vcc]); c("GND", *["%s.%d" % (ref, p) for p in gnd])
for cap in DECOUPLE:
    c("VCC", cap + ".1"); c("GND", cap + ".2")
c("VCC", "C5.1", "OSC1.8", *["X1.%s" % p for p in ("A2", "B2", "C2", "A31", "B31", "C31")])
c("GND", "C5.2", "OSC1.4", *["X1.%s" % p for p in ("A1", "B1", "C1", "A32", "B32", "C32")])
c("VCC", "OSC1.1")                                                         # a can's pin 1: nothing, or its enable (on when high)
c("VCC", "R2.2"); c("PWRA", "R2.1", "LED9.2"); c("GND", "LED9.1")
c("VCC", "RN1.1", "RN2.1")

# ---- the data buffer IC12: the bus on its A side, the card on its B side ----------------------------------------------
for i in range(8):
    c("DATA%d" % i, "X1.A%d" % (19 + i), "IC12.%d" % (2 + i))
    c("ID%d" % i, "IC12.%d" % (18 - i), "RN2.%d" % (2 + i))
c("-IO-RD", "X1.B25", "IC12.1")                                            # DIR: high = bus to card, low (a read) = card to bus
c("BUFEN#", "IC12.19", "IC13.8")
c("-IO-ADDRSEL", "IC13.1"); c("-IO-DATASEL", "IC13.2"); c("SELPORT#", "IC13.3", "IC13.9")
c("-IO-SEL6", "IC13.4"); c("-IO-SEL7", "IC13.5"); c("SELRTC#", "IC13.6", "IC13.10")
c("GND", "IC13.12", "IC13.13")                                             # the spare gate

# ---- the port decode IC5, the half (JP3), the control and data ports (JP4, JP5) --------------------------------------
c("IO-ADDR0", "X1.C7", "IC5.1"); c("IO-ADDR1", "X1.C8", "IC5.2"); c("IO-ADDR2", "X1.C9", "IC5.3")
c("IO-ADDR3", "X1.C10", "JP3.2", "JP3.5")
c("GND", "JP3.1", "IC5.5"); c("VCC", "JP3.6")                              # G2B on GND, as V1.1 (not -BUS-EN: the tester)
c("HALF-G2A", "JP3.3", "IC5.4"); c("HALF-G1", "JP3.4", "IC5.6")
for n, pin in enumerate((15, 14, 13, 12, 11, 10, 9, 7)):                   # Y0..Y7; header pin 16 = port 0 ... pin 2 = port 7
    c("-IO-SEL%d" % n, "IC5.%d" % pin, "JP4.%d" % (16 - 2 * n), "JP5.%d" % (16 - 2 * n))
c("-IO-ADDRSEL", *["JP4.%d" % p for p in range(1, 16, 2)])
c("-IO-DATASEL", *["JP5.%d" % p for p in range(1, 16, 2)])

# ---- the strobes: IC8, open collector, with RN1 -----------------------------------------------------------------------
c("-IO-RD", "IC8.1"); c("IO-RD", "IC8.2", "RN1.7")
c("-IO-WR", "X1.B26", "IC8.3"); c("IO-WR", "IC8.4", "RN1.6")
c("-RESET", "X1.C30", "IC8.5"); c("RESET", "IC8.6", "IC8.9", "RN1.5")
c("-B-RESET", "IC8.8", "RN1.4")
c("-IO-DATASEL", "IC8.11", "RN1.9"); c("IO-SELDATA", "IC8.10", "RN1.3")
c("-IO-ADDRSEL", "RN1.8")
c("UART-INT", "IC1.30", "IC8.13"); c("UINT#", "IC8.12", "JP7.1"); c("-INT", "JP7.2", "X1.C13", "RN1.2")

# ---- the control latch IC10 and its clock ------------------------------------------------------------------------------
c("-IO-ADDRSEL", "IC7.12", "IC7.13"); c("IO-ADDRSEL", "IC7.11", "IC7.4")
c("IO-WR", "IC7.5"); c("CTLCK", "IC7.6", "IC10.11")
c("-B-RESET", "IC10.1", "IC4.1", "IC9.1")
for i in range(8):
    c("ID%d" % i, "IC10.%d" % D273[i], "IC4.%d" % D273[i], "IC9.%d" % D273[i])
c("SWITCH-LED", "IC10.2", "IC6.13", "IC6.5")
c("LCD-ENABLE", "IC10.5", "IC6.10")
c("LCD-REGISTER", "IC10.6", "DS3.4")
c("UART-A0", "IC10.9", "IC1.28"); c("UART-A1", "IC10.12", "IC1.27"); c("UART-A2", "IC10.15", "IC1.26")
c("UART-CS", "IC10.16", "IC1.13")
c("TIL311", "IC10.19", "IC11.13")

# ---- the UART IC1, its clock, the MAX232, the DB9 and the TTL header --------------------------------------------------
for i in range(8):
    c("ID%d" % i, "IC1.%d" % (1 + i))
c("ICLK", "IC1.9", "IC1.15")                                               # -BAUDOUT to RCLK
c("IO-SELDATA", "IC1.12"); c("GND", "IC1.14", "IC1.25")                    # CS0; -CS2 and -ADS low
c("IO-WR", "IC1.19"); c("IO-RD", "IC1.22"); c("VCC", "IC1.18", "IC1.21")   # the active-high strobes; -WR and -RD high
c("RESET", "IC1.35"); c("VCC", "IC1.36", "IC1.37", "IC1.38", "IC1.39")     # MR; -CTS, -DSR, -DCD, -RI high
c("UCLK", "OSC1.5", "IC1.16")
c("TX", "IC1.11", "IC2.11", "J2.5")
c("RX", "IC1.10", "JP2.2"); c("RX-232", "IC2.12", "JP2.1"); c("RX-TTL", "J2.4", "JP2.3", "R12.1"); c("VCC", "R12.2")
c("GND", "J2.1", "J2.2")                                                   # the cable's CTS low: it may always send
c("C1+", "IC2.1", "C1.1"); c("C1-", "IC2.3", "C1.2"); c("C2+", "IC2.4", "C2.1"); c("C2-", "IC2.5", "C2.2")
c("V+", "IC2.2", "C3.1"); c("VCC", "C3.2"); c("V-", "IC2.6", "C4.2"); c("GND", "C4.1")
c("VCC", "IC2.10"); c("GND", "IC2.8")                                      # T2IN, R2IN: the second channel is not used
c("TX-OUT", "IC2.14", "JP1.2", "JP1.5"); c("RX-IN", "IC2.13", "JP1.1", "JP1.6")
c("DB9-3", "JP1.3", "J1.3"); c("DB9-2", "JP1.4", "J1.2"); c("GND", "J1.5", "J1.0")

# ---- switches and LEDs --------------------------------------------------------------------------------------------------
c("IO-RD", "IC6.3"); c("IO-SELDATA", "IC6.4", "IC6.2", "IC6.9", "IC11.2"); c("IO-WR", "IC6.1", "IC6.11", "IC11.1")
c("SWOE#", "IC6.6", "IC3.1", "IC3.19")
c("LEDCK", "IC6.12", "IC4.11")
for n, (a, y) in enumerate(((2, 18), (4, 16), (6, 14), (8, 12), (11, 9), (13, 7), (15, 5), (17, 3))):
    c("SW%d" % n, "S%d.2" % n, "IC3.%d" % a); c("VCC", "S%d.1" % n); c("GND", "S%d.3" % n)
    c("ID%d" % n, "IC3.%d" % y)
    c("LQ%d" % n, "IC4.%d" % Q273[n], "R%d.2" % (n + 3)); c("LEDA%d" % n, "R%d.1" % (n + 3), "LED%d.2" % n)
    c("GND", "LED%d.1" % n)

# ---- the TIL311s: IC9's low nibble to LO (DS2), its high nibble to HI (DS1); inputs A, B, C, D = pins 3, 2, 13, 12 ----
c("TILCK", "IC11.12", "IC9.11")
for k, pin in enumerate((3, 2, 13, 12)):
    c("TL%d" % k, "IC9.%d" % Q273[k], "DS2.%d" % pin); c("TH%d" % k, "IC9.%d" % Q273[4 + k], "DS1.%d" % pin)
for d in ("DS1", "DS2"):
    c("VCC", d + ".1", d + ".14"); c("GND", d + ".5", d + ".7", d + ".8")  # the latch open, never blanked
c("GND", "IC11.3", "IC11.4", "IC11.5", "IC11.9", "IC11.10", "IC11.11")     # the two spare gates

# ---- the LCD ------------------------------------------------------------------------------------------------------------
c("LCDSTB#", "IC6.8", "IC7.1", "IC7.2"); c("LCD-E", "IC7.3", "DS3.6")
for i in range(8):
    c("ID%d" % i, "DS3.%d" % (7 + i))
c("GND", "DS3.1", "DS3.5", "DS3.16"); c("VCC", "DS3.2")
c("VCC", "RV1.1"); c("GND", "RV1.3"); c("LCD-VO", "RV1.2", "DS3.3")
c("VCC", "R11.1"); c("LCD-BL", "R11.2", "DS3.15")

# ---- IN and OUT ---------------------------------------------------------------------------------------------------------
c("VCC", "S8.1"); c("GND", "S8.3"); c("INSW", "S8.2", "JP6.2"); c("IN", "JP6.1", "X1.C26")
c("OUT", "X1.C27", "R1.2"); c("OUTA", "R1.1", "LED8.2"); c("GND", "LED8.1")

# ---- the clock IC15 on ports 6 and 7 -------------------------------------------------------------------------------------
for i in range(8):
    c("ID%d" % i, "IC15.%d" % (4 + i))
c("-IO-SEL6", "IC14.1"); c("-IO-WR", "IC14.2"); c("AS#", "IC14.3", "IC7.9", "IC7.10"); c("RTC-AS", "IC7.8", "IC15.14")
c("-IO-SEL7", "IC14.4", "IC14.9"); c("-IO-RD", "IC14.5"); c("-IO-WR", "IC14.10")
c("RTC-RD#", "IC14.6", "IC15.17"); c("RTC-WR#", "IC14.8", "IC15.15")
c("GND", "IC14.12", "IC14.13")                                             # the spare gate
c("GND", "IC15.1", "IC15.13"); c("VCC", "IC15.18")                         # MOT low: Intel timing; -CS low; -RESET high
c("RTC-X1", "IC15.2", "Y1.1"); c("RTC-X2", "IC15.3", "Y1.2")
c("VBAT", "IC15.20", "BT1.1"); c("GND", "BT1.2")
c("RTC-IRQ#", "IC15.19", "JP8.1"); c("-INT", "JP8.2")
c("RCLR#", "IC15.21", "JP9.1"); c("GND", "JP9.2")                          # no pull-up: the chip has its own

# ---- pins left open ----------------------------------------------------------------------------------------------------
NO_CONNECT = {
    "IC1": [17, 23, 24, 29, 31, 32, 33, 34],     # XTAL2, DDIS, -TXRDY, -RXRDY, -OUT2, -RTS, -DTR, -OUT1
    "IC2": [7, 9], "IC11": [6, 8], "IC13": [11], "IC14": [11], "IC15": [22, 23],       # IC15: N.C., SQW
    "DS1": [4, 10], "DS2": [4, 10],              # the decimal points
    "J1": [1, 4, 6, 7, 8, 9], "J2": [3, 6],
}
_X1_USED = ({"A1", "B1", "C1", "A32", "B32", "C32", "A2", "B2", "C2", "A31", "B31", "C31", "B25", "B26",
             "C7", "C8", "C9", "C10", "C13", "C26", "C27", "C30"} | {"A%d" % n for n in range(19, 27)})
NO_CONNECT["X1"] = [p for p in PINS["X1"] if p not in _X1_USED]
NO_CONNECT = {r: [str(p) for p in ps] for r, ps in NO_CONNECT.items()}

# outputs that drive a net (for check(): no two on one net). ID0-7 are shared by parts enabled at different times, and
# -INT by open collectors: those nets are left out.
SHARED = ("ID", "DATA", "-INT")
_GATE4 = (3, 6, 8, 11)
OUTPUTS = {"IC1": (11, 15, 30), "IC2": (12, 14), "IC3": (18, 16, 14, 12, 9, 7, 5, 3), "IC4": Q273,
           "IC5": (15, 14, 13, 12, 11, 10, 9, 7), "IC6": (12, 6, 8), "IC7": _GATE4, "IC8": (2, 4, 6, 8, 10, 12),
           "IC9": Q273, "IC10": Q273, "IC11": (12, 6, 8), "IC12": (), "IC13": _GATE4, "IC14": _GATE4, "IC15": (19, 23)}

# ---- what to buy: the parts whose exact type matters (for the bill of materials) --------------------------------------
BUY = {
    "IC1":  "a 16550 in DIP-40: Exar XR16C550CP (the V1.1 card's), TI TL16C550CN or PC16550DN",
    "OSC1": "1.8432 MHz oscillator, 5 V, half-size (8-pin DIP) can, as the V1.1 card's (ECS-2100AX): the monitor's "
            "divisor 3 gives 38400 baud. Its pin 1 is tied to +5 V on the board: not connected in the can, or an "
            "enable that is on when high",
    "IC2":  "MAX232 with 1 uF capacitors (a MAX232A or MAX202 runs on them too)",
    "IC15": "DS12885+ (Analog Devices / Maxim), the 24-pin PDIP: not the DS12887 module (its pins 2, 3, 20 are not connected)",
    "Y1":   "32.768 kHz watch crystal for a 6 pF load (the DS12885 has the load capacitors inside): a 12.5 pF "
            "crystal runs fast",
    "BT1":  "Keystone 103, a flat holder for one CR2032 (an upright holder is taller than the room between cards)",
    "J1":   "9-way D socket (female), right angle, as the V1.1 card's: pin rows 2.84 mm apart, 10.2 mm behind the "
            "board's edge, mounting holes 25.0 mm apart",
    "J2":   "6-pin header, 2.54 mm: an FTDI TTL-232R-5V cable's socket, its black wire (GND) on pin 1",
    "DS1":  "TIL311 (or HP 5082-7340: same pins), in a socket",
    "DS2":  "TIL311 (or HP 5082-7340), in a socket",
    "DS3":  "HD44780 16 x 2 module, 80 x 36 mm, a 16-pin row along its upper edge (pin 1 at the left), on a 16-way socket "
            "strip and four 2.5 mm standoffs",
    "R11":  "47 ohm for a module with no resistor of its own for its backlight; a wire link if the module has one",
    "RV1":  "10k trimmer, Bourns 3386 with its three pins in a row",
    "LED9": "5 mm LED",
}
for _n in range(9):
    BUY["S%d" % _n] = "M9040P toggle (on-on, PCB pins), as the V1.1 card's"
SOCKETS = "every IC in a socket (the UART, the clock chip and the TIL311s at least)"
TEXT_ONLY_LEFT_OFF = ()                                         # (the video card's generator asks for it; nothing here)


def check():
    """the wiring's own checks: every pin on a net or listed as open, no pin on two nets, no net with one pin, no two
    outputs on a net, an output on every net of ICs, a capacitor for every IC"""
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
        drivers = [(r, p) for r, p in pins if p.isdigit() and int(p) in OUTPUTS.get(r, ())]
        if len(drivers) > 1: faults.append("net %s has %d outputs: %r" % (net, len(drivers), drivers))
        if not drivers and net not in ("VCC", "GND") and all(r.startswith("IC") for r, p in pins):
            faults.append("net %s has no output on it" % net)
    for ref in PARTS:
        if ref.startswith("IC") and ref not in OUTPUTS: faults.append("%s has no OUTPUTS entry" % ref)
        if (ref.startswith("IC") or ref == "OSC1") and ref not in DECOUPLE.values(): faults.append("%s has no capacitor" % ref)
    if sum(1 for r in PARTS if r.startswith("IC")) != NIC: faults.append("NIC is not the number of ICs")
    return faults


# ---- V1.2 against the V1.1 card in the machine ------------------------------------------------------------------------
# V1.1's parts under their V1.2 names (hardware/cards/io/kicad/v1.1/io-v1.1.kicad_pcb, the built card's board)
V11_REF = {"HI0": "DS1", "LO0": "DS2", "X2": "DS3", "TM1": "RV1", "Y1": "OSC1", "RN2": "RN1", "IN0": "S8",
           "INPUT0": "JP6", "INT0": "JP7", "IO-ADDR-HL0": "JP3", "IO-ADDR0": "JP4", "DATA-ADDR0": "JP5",
           "OUT0": "LED8", "PWR0": "LED9"}
V11_REF.update({"UNK%d" % n: "LED%d" % n for n in range(8)})
V11_PIN = {"LED": {"A": "2", "K": "1"}, "C": {"+": "1", "-": "2"}}          # V1.1's pad names for LEDs and polarised capacitors
# what is meant to differ. A V1.1 connection (two pins on one net) must be a V1.2 connection too, unless one of its
# pins is listed here:
V11_CHANGED = {
    "X1.A19", "X1.A20", "X1.A21", "X1.A22", "X1.A23", "X1.A24", "X1.A25", "X1.A26",   # DATA0-7: behind the buffer now
    "JP7.1", "JP7.2", "IC8.12",    # the INT jumper: after IC8/F here, before it on V1.1
    "IC7.9", "IC7.10",             # V1.1's spare gate (inputs on GND): AS's inverter here
    "IC2.12", "IC1.10",            # R1OUT to the UART's RX: through JP2 here
    "DS3.15",                      # the backlight: through R11 here
    "C6", "C7", "C8", "C9", "C10", "C11", "C12", "C13", "C14", "C15", "C16", "C17",   # V1.1's decoupling, numbered anew
    "C5",
}


def v11_nets():
    """the built V1.1 card's nets from its board file: net -> set of "REF.PIN" in V1.2's names"""
    import os, re
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "v1.1", "io-v1.1.kicad_pcb")
    t = open(path).read()
    nets = {}
    for m in re.finditer(r'\n\t\(footprint "', t):
        s = m.start(); d = 0; j = s + 1
        while True:
            ch = t[j]
            if ch == "(": d += 1
            elif ch == ")":
                d -= 1
                if d == 0: break
            j += 1
        fp = t[s:j + 1]
        ref = re.search(r'\(property "Reference" "([^"]*)"', fp).group(1)
        ref = V11_REF.get(ref, ref)
        for pm in re.finditer(r'\(pad "([^"]*)" (\w+) .*?(?=\n\t\t\(pad |\Z)', fp, re.S):
            nn = re.search(r'\(net (?:\d+ )?"([^"]*)"\)', pm.group(0))
            pin = pm.group(1)
            if not nn or not pin: continue
            for prefix, names in V11_PIN.items():
                if ref.startswith(prefix) and not ref.startswith("CR"): pin = names.get(pin, pin)
            nets.setdefault(nn.group(1), set()).add("%s.%s" % (ref, pin))
    return nets


def v11_check():
    """every connection of the V1.1 card that V1.2 is not meant to change is a connection of V1.2: the pins of each
    V1.1 net (those not in V11_CHANGED) are all on one V1.2 net, and what V1.1 has on a rail is on that rail. -> faults"""
    mine = {"%s.%s" % (r, p): net for net, pins in NETS.items() for r, p in pins}
    faults = []
    for net, pins in sorted(v11_nets().items()):
        on = {}
        for p in sorted(pins):
            if p in V11_CHANGED or p.split(".")[0] in V11_CHANGED:
                continue
            if p.startswith("X1.") and p not in mine:          # a bus pin this card does not use: open here, named there
                continue
            on.setdefault(mine.get(p, "(open)"), []).append(p)
        if net in ("VCC", "GND"):
            for n, ps in sorted(on.items()):
                if n != net: faults.append("V1.1 has %s on %s; here on %s" % (" ".join(ps), net, n))
        elif len(on) > 1:
            faults.append("V1.1 net %s is %d nets here: %s" % (net, len(on), "; ".join(
                "%s: %s" % (n, " ".join(ps)) for n, ps in sorted(on.items()))))
    return faults


if __name__ == "__main__":
    f = check()
    ics = sum(1 for r in PARTS if r.startswith("IC"))
    print("%s %s: %d parts (%d ICs), %d nets, %d pins on nets" % (CARD, REV, len(PARTS), ics, len(NETS),
                                                                 sum(len(p) for p in NETS.values())))
    for x in f: print("  " + x)
    print("check: %s" % ("%d faults" % len(f) if f else
                         "every pin accounted for, no net with one pin, no two outputs on a net"))
    g = v11_check()
    for x in g: print("  " + x)
    print("against V1.1: %s" % ("%d differences not on the list" % len(g) if g else
                                "every connection of the built card that V1.2 keeps is here"))
    raise SystemExit(1 if f or g else 0)
