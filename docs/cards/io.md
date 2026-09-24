# I/O card V1.1 — theory of operation

The machine's console and front panel on one card: a 16550-class UART behind two I/O ports, eight toggle switches,
eight LEDs, two TIL311 hex displays, an HD44780 character LCD, the input-switch line the branch instructions test,
and the ON/OFF LED.

Written 2026-09-23 from the YACC1-D tree.

Sources: `hardware/cards/io/eagle/v1.1/IO V1.1.sch` and `.brd` (parts and nets parsed from the Eagle XML),
`hardware/cards/io/eagle/v1.1/Notes.md`, `hardware/cards/io/README.md`, `firmware/monitor/monitor.asm` (the EQUs and
the `uartout`/`uartoutw`/`uartin`/`switchin`/`ledout`/`TIL311out`/`const` routines and the old LCD test),
`firmware/microcode/ucode-generator2/io.c` and `docs/isa/steps.txt` (OUTI/OUTA/INP step timing),
`firmware/microcode/yaccsignaldata2.h`, `software/ucemu/y1ucemu.c` (the I/O card model), `software/opcodes.h`,
`software/assembler/yacc1.def`, `hardware/DESIGN-REVIEW.md`, `hardware/DESIGN-REVIEW-NOTES-control-io.md`
(section 3 and the cross-card notes), `docs/isa/MICROCODE-REVIEW-NOTES.md` (1.5, 1.6, L-2), `firmware/abi/README.md`,
`docs/system/OS-PLAN.md`, `software/cfmodel.h`, `docs/system/MACHINE.md`, `hardware/FABRICATED.md`,
`tests/bus-tester-scripts/IO/*`, `tests/assembler/{ledcount,romcount,romdiag}/README.md`, `BACKLOG.md`.

## 1. Purpose and place in the machine

The YACC1 has sixteen I/O ports, addressed by the four IO-ADDR lines that the sequencer's pipeline drives directly
from the `IOADDR0..3` field of the control word, and strobed by -IO-RD and -IO-WR. This card decodes eight of the
sixteen (which eight is a strap) and wires two of them:

- **P0, the control port** (write only): an 8-bit latch (IC10) whose bits select which device the data port talks
  to and, for the UART, which of its eight registers.
- **P1, the data port**: reads and writes go to whichever device the control latch has selected — the UART, the
  switches (read) and LEDs (write), the LCD, or the TIL311 displays.

That "select, then transfer" pattern is why the monitor writes P0 before every P1 access, and it is the pattern
`docs/system/OS-PLAN.md` adopts for every later device (CompactFlash on P8/P9, the 6845 on PA/PB). Besides the ports,
the card is the source of the bus line **IN** (a toggle switch that `BRINH`/`BRINL` test), the sink of **OUT** (the
LED that `ON`/`OFF` drive) and, optionally, the source of **-INT** from the UART's interrupt output.

```
   bus DATA0..7 (A19..A26)  ---+----------------+----------------+---------------+-----------+
                               |                |                |               |           |
   IO-ADDR0..2 (C7..C9)   +----v-----+    +-----v-----+    +-----v-----+   +-----v-----+ +---v----+
   IO-ADDR3 (C10) -strap->| IC5      |    | IC10 273  |    | IC1       |   | IC4 273   | | IC9 273|
                          | 74LS138  |    | control   |    | XR16C550  |   | LEDs 0..7 | | TIL311 |
                          | -IO-SEL0 |    | latch P0  |    | UART      |   +-----------+ | LO, HI |
                          |   ..7    |    | Q1..Q8    |    | A0..2,CS1 |<--UART-A0..2,   +--------+
                          +--+---+---+    +-----+-----+    +--+--------+   UART-CS (Q4..Q7)
      IO-ADDR hdr: which     |   |              |             |  TX/RX
      -IO-SELn = P0 ---------+   |   SWITCH-LED, LCD-ENABLE,  |          +--------+   +------+  JP1  +-----+
      DATA-ADDR hdr: which       |   LCD-REGISTER, TIL311     +--------->| IC2    |---| null |--| J1  |
      -IO-SELn = P1 -------------+                                       | MAX232 |   | modem|  | DB9 |
                                 |                                       +--------+   +------+  +-----+
   -IO-RD (B25), -IO-WR (B26) -> IC8 74LS06 (open collector) -> IO-RD, IO-WR (pull-ups RN2)
                                 -> IC6/IC11 74LS10, IC7 74LS00: per-device strobes
   S0..S7 toggles -> IC3 74LS244 -> DATA0..7 (read of P1 with SWITCH-LED)      X2 HD44780 LCD on DATA0..7
   IN toggle -> INPUT hdr -> bus IN (C26)      bus OUT (C27) -> OUT LED       UART INT -> INT hdr -> IC8 -> -INT (C13)
```

## 2. Bus signals used

| Signal | Bus pin | Dir | What it does on this card |
|---|---|---|---|
| DATA0..7 | A19..A26 | bidir | the UART's D0..7, the LCD's DB0..7, the D inputs of the three 74273 latches (IC4, IC9, IC10), and the outputs of the switch buffer IC3. **No bus buffer**: the devices sit on the bus directly |
| IO-ADDR0..2 | C7..C9 | in | IC5 (74LS138) A, B, C: the port number within the card's half |
| IO-ADDR3 | C10 | in | to the IO-ADDR-HL strap only: chooses whether the card decodes P0-P7 or P8-P15 |
| -IO-RD | B25 | in | inverted by IC8/A (74LS06, open collector, pull-up RN2) into IO-RD: the UART's active-high IOR and the read qualifier of the switch buffer |
| -IO-WR | B26 | in | inverted by IC8/B into IO-WR: the UART's IOW, and NANDed with the selects into the clocks of the three latches and the LCD E pulse |
| -IO-ADDR-LD | C11 | — | **connector only**: no node on the card (the port is decoded combinationally; `MICROCODE-REVIEW-NOTES.md` 1.5, L-2) |
| IN | C26 | out | driven by the IN toggle switch through the INPUT header (VCC or GND, hard) |
| OUT | C27 | in | lights the OUT LED through R1 |
| -INT | C13 | out (OC) | IC8/F output, from the UART's INT pin through the INT header; the only -INT source in the machine |
| -RESET | C30 | in | IC8/C makes RESET (active high, the 16550's MR); IC8/D makes -B-RESET, the CLR of IC4, IC9, IC10 |
| VCC / GND | A2,B2,C2,A31,B31,C31 / A1,B1,C1,A32,B32,C32 | power | C5-C17 decoupling; PWR LED through R2 330 Ω |

Not used: -VMA, -BUS-EN, the address bus, DATA8..15, every register/ALU strobe. The port decoder is address-only
(review 3.3); every device access is qualified by IO-RD or IO-WR, and those are inactive while the sequencer's
pipeline is tri-stated because the 74LS06 inputs read a floating bus line as high.

How the sequencer drives them (`firmware/microcode/ucode-generator2/io.c`, `docs/isa/steps.txt`):

| Instruction | Opcode | Steps that touch this card |
|---|---|---|
| `OUTI Pn,byte` | $70 \| n | the operand byte is fetched from [PC] and held on the bus by -MEM-RD from step 1 to 9; `IOADDR` = n in every step of the record; -IO-ADDR-LD at step 6 (unused here); **-IO-WR at step 8**; 13 steps |
| `OUTA Pn` | $60 \| n | -AC-RD with -ALU-FUNC from step 6 (the ALU drives DATA0..7 = ACC, DATA8..15 = $FF); -IO-ADDR-LD at step 7; **-IO-WR at step 9**; 12 steps |
| `INP Pn` | $90 \| n | -ALU-FUNC with ALU = DATA from step 6; **-IO-RD from step 8 to 11**; -AC-LD at step 9 — the accumulator latches on the *leading* edge of step 9, so the card has one step (two clock periods) from -IO-RD falling to put the byte on the bus; 12 steps |
| `ON` / `OFF` | $01 / $02 | OUT-ON / OUT-OFF set or clear the OUT latch on the sequencer (IC22 there); the level arrives here on C27 |
| `BRINH addr` / `BRINL addr` | $A3 / $A4 | the ALU's condition mux (74LS251, select 5 = `ALUIN`) samples the bus line IN; no strobe reaches this card |
| `OUTVR Pn,Rm` | $80 \| n | in `yacc1.def` and `opcodes.h`, **no microcode** (an all-zero record, H-4 in the microcode review): never use it |

The I/O latches clock on the **trailing** edge of -IO-WR (the 74273s clock on the rising edge of a NAND that falls
with IO-WR), which is why the generator holds the data source one step past the strobe. `software/ucemu/y1ucemu.c`
models exactly this (`io_write()` at the step where -IO-WR is asserted and the next step is not) and samples an
`INP` once at the leading edge of -IO-RD (`io_rd_hold`).

## 3. Schematic walkthrough, IC by IC

Chip types from `IO V1.1.brd`: IC1 XR-16C550P (value empty; deviceset `XR-16C550P`, `exar` library), IC2 MAX232,
IC3 74LS244, IC4/IC9/IC10 74273 (the board says `74273N`, no family letter), IC5 74LS138, IC6/IC11 74LS10, IC7
74LS00, IC8 74LS06, Y1 `ECS-2100AX-200`, X2 `HD44780LCD-1602`, LO/HI `HTIL311A`, TM1 10k trimmer, J1 DB9 female.

### 3.1 Port decode: IC5 (74LS138), the IO-ADDR-HL strap, the IO-ADDR and DATA-ADDR headers

IC5's A, B, C are IO-ADDR0..2. G2B is grounded. G1 (N$29) and G2A (N$27) go to the 2x3 header IO-ADDR-HL, whose
other pins are GND (pin 1), IO-ADDR3 (pins 2 and 5) and VCC (pin 6). Two jumpers set the half:

- decode **P0-P7**: G1 = VCC (pin 4 to 6), G2A = IO-ADDR3 (pin 3 to 5) — the decoder is enabled only while
  IO-ADDR3 is low;
- decode **P8-P15**: G1 = IO-ADDR3 (pin 4 to 2), G2A = GND (pin 3 to 1).

The eight outputs -IO-SEL0..7 (active low while that port number is on the bus, strobe or not) go to two 2x8
headers. On **IO-ADDR** every odd pin (1, 3, ... 15) is the net -IO-ADDRSEL and the even pins carry -IO-SEL7 (pin 2)
down to -IO-SEL0 (pin 16); one jumper picks which port is the control port. On **DATA-ADDR** the odd pins are
-IO-DATASEL and the even pins the same selects; one jumper picks the data port. The monitor's `CNTL-PORT: EQU "P0"`
and `DATAPORT: EQU "P1"` mean the jumpers sit on pins 15-16 of IO-ADDR (-IO-SEL0) and pins 13-14 of DATA-ADDR
(-IO-SEL1). Nothing stops both headers selecting the same port, or a port being selected on neither; the six other
selects have no consumer on the card (OS-PLAN reserves them "to the I/O card").

### 3.2 Strobes: IC8 (74LS06 open-collector inverters) and RN2

IC8/A: -IO-RD to IO-RD (pull-up RN2/-6). IC8/B: -IO-WR to IO-WR (RN2/-5). IC8/E: -IO-DATASEL to IO-SELDATA
(RN2/-2), the active-high "data port addressed" that the UART's CS0 and the three device NANDs use. IC8/C: -RESET to
RESET (RN2/-4), the 16550's active-high reset; IC8/D: RESET back to -B-RESET (RN2/-3), the CLR of IC4, IC9 and IC10 —
so every latch clears on reset and the control latch comes up with no device selected. IC8/F: the INT header to
-INT (RN2/-1). RN2 is an RNX6 (RN-7 footprint) with common pin 1 on VCC; its value is empty in both files (review
3.2, cross-card notes). **To verify:** RN2's value; the review's point is that every strobe's *rising* edge comes
through this pull-up and, if it is 10 kΩ, takes a few hundred ns through the LS10/LS00 inputs.

### 3.3 The control latch: IC10 (74273) and IC7

IC7/D (74LS00 as an inverter) turns -IO-ADDRSEL into IO-ADDRSEL (N$67); IC7/B NANDs it with IO-WR into N$40, the CLK
of IC10. The NAND output falls at the start of a write to P0 and rises at its end: the 74273 captures DATA0..7 at the
trailing edge of -IO-WR. The Q outputs are the bit map the monitor's EQUs name (`firmware/monitor/monitor.asm`
lines 23-27):

| Bit | Mask | Net (IC10 output) | Meaning |
|---|---|---|---|
| 0 | $01 `SWITCHLED` | SWITCH-LED (Q1) | P1 read = switches (IC3), P1 write = LEDs (IC4) |
| 1 | $02 `LCDENABLE` | LCD-ENABLE (Q2) | P1 write pulses the LCD's E |
| 2 | $04 `LCDREGISTER` | LCD-REGISTER (Q3) | the LCD's RS: 0 = command, 1 = data |
| 3-5 | $08/$10/$20 (`UARTA0`..`UARTA7` = register << 3) | UART-A0..A2 (Q4..Q6) | the 16550 register address |
| 6 | $40 `UARTCS` | UART-CS (Q7) | the 16550's CS1 |
| 7 | $80 `TIL311` | TIL311 (Q8) | P1 write = both hex displays |

The bits are independent flags, not a code: the hardware lets software set SWITCHLED and UARTCS together, in which
case a P1 read has two drivers (IC3 and the UART). The design review (3.3) calls this a software rule; the monitor
never does it.

### 3.4 The UART: IC1 (XR16C550), Y1, IC2 (MAX232), JP1, J1

Chip selects: CS0 = IO-SELDATA (active high: the data port is addressed), CS1 = UART-CS (the latch bit), -CS2 = GND
(permanently true). The chip is selected only while both a P1 access and the UARTCS bit hold, and A0..A2 come from
the latch, so a register access is "write the control byte, then read or write P1". The strobes use the 16550's
active-high pair: IOR = IO-RD, IOW = IO-WR, with -IOR and -IOW tied to VCC; -AS (address strobe) is grounded, so the
address inputs are not latched inside the chip. RESET (active high) is the inverted bus reset. CTS, DSR, CD and RI
are tied to VCC (inactive: the modem lines are unused); RTS, DTR, OP1, OP2, DDIS, TXRDY, RXRDY are unconnected;
BAUDOUT feeds RCLK (net ICLK), the standard single-clock connection.

Y1 is a canned oscillator (`ECS-2100AX-200` is the Eagle package/deviceset name, not a frequency) into XTAL1; XTAL2 is
open, which is the datasheet connection for an external clock (`DESIGN-REVIEW.md` flagged XTAL2 as floating; the
control/IO notes 3.1 correct that to "not a fault"). The monitor programs divisor 3 for 38400 baud
(`OUTI P1,3 ;38400`, with a commented `12 ;9600`), which implies a 1.8432 MHz oscillator (16 x 38400 x 3). **To
verify:** the frequency printed on the can (a 20 MHz part would give 416 kbaud).

TX goes to the MAX232's T1IN; T1OUT is the net TX-OUT on JP1 pins 2 and 5; R1IN is RX-IN on JP1 pins 1 and 6; R1OUT
is RX to the UART. The DB9 J1 has pin 2 on JP1 pin 4, pin 3 on JP1 pin 3, pin 5 on GND. The 2x3 header therefore
routes TX-OUT and RX-IN to DB9 pins 2 and 3 either way round ("null modem logic to route tx/rx", `Notes.md`):
jumpers 1-3 and 2-4 put the card's transmit on DB9 pin 2 and its receive on pin 3; jumpers 3-5 and 4-6 swap them.
Which pair is fitted, and which orientation the physical header has, is not in the tree. **To verify:** the JP1
jumper positions and which cable (straight or null-modem) reaches the Mac. The MAX232 charge-pump capacitors are C1-C4
(polarised, `E2,5-6E`), values empty.

### 3.5 Switches and LEDs: S0-S7, IC3 (74LS244), IC4 (74273), R3-R10, LEDs 0-7

Each toggle switch S0..S7 (`M9040P`) has its pole on a 74LS244 input, one throw on VCC and the other on GND: a hard
level, no pull-up needed. IC3's two enables (N$32) come from IC6/B = NAND(IO-RD, IO-SELDATA, SWITCH-LED): the buffer
drives DATA0..7 only during a read of P1 with SWITCHLED set. Switch S0 is DATA0.

IC4's CLK (N$41) is IC6/A = NAND(IO-WR, IO-SELDATA, SWITCH-LED): a write of P1 with SWITCHLED set latches the byte at
the end of the strobe. Q1..Q8 drive LEDs 0..7 through R3..R10 (values empty; **To verify**), cathodes to GND: LED n
shows bit n ("LEDS are reversed hi bit to low bit" in the 1.0-to-1.1 change list is the fix that made it so).

### 3.6 TIL311 displays: IC9 (74273), LO and HI

IC9's CLK (N$75) is IC11/A = NAND(IO-WR, IO-SELDATA, TIL311): a write of P1 with TIL311 set latches the byte. Q1..Q4
drive LO's D0..D3, Q5..Q8 HI's D0..D3, so the two digits show the byte in hex, low nibble on LO. Both displays have
their latch strobe (L-SI) and blanking input (BI) grounded — transparent and never blanked, so they always show what
IC9 holds (`Notes.md` 1.1: "TIL311 data latch connect to gnd so they always show data latch"; "TIL311 vcc to pin 14").

### 3.7 The LCD: X2 (HD44780 16x2), IC6/C, IC7/A, TM1

The LCD's DB0..7 are on the bus, RS = LCD-REGISTER (IC10 Q3), R/W = GND (write only — the busy flag can never be
read, so software must time its commands), E = N$30 = IC7/A(N$33) where N$33 = IC6/C = NAND(IO-SELDATA, LCD-ENABLE,
IO-WR): E is high for the duration of a P1 write with LCDENABLE set and falls at its end, which is the edge the
HD44780 latches on. Contrast VO comes from the 10k trimmer TM1; the backlight A/K pins are straight across VCC/GND
with no series resistor (review 3.4: relies on the module's own resistor; **To verify** on the fitted module). The
monitor contains only a commented-out LCD test (`;LCD` block near line 1200): select LCDENABLE, write $3C, $01, $0F
with delays between, then LCDENABLE|LCDREGISTER and write 'A', 'B'. No shipped code drives the LCD.

### 3.8 IN, OUT and -INT: the INPUT, INT headers, R1, OUT LED

The IN toggle (pole to INPUT header pin 2, throws to VCC and GND) reaches the bus line IN (C26) when the 1x2 INPUT
header is jumpered. IN is an active-high line (`memory` v1.1 notes: "Signal IN and OUT converted from active low to
Active HI"); no other card drives it (review: "tester: input; logic/register/video: unconnected"), so the switch is its
only source. The OUT line (C27) goes through R1 (value empty) to the OUT LED: `ON` lights it, `OFF` clears it.

The UART's INT output goes to INT header pin 1; pin 2 feeds IC8/F, whose open-collector output is the bus -INT with
RN2's pull-up. Jumper the header and the UART can interrupt the CPU; the sequencer's own JP3 then selects edge or level
mode (control/IO notes 1.6: two jumpers needed there, and edge mode fires on the *release* of -INT). No shipped code
enables UART interrupts (`uart_ier` is written 0 by the monitor's init: `OUTI P0,(UARTA1!UARTCS)` / `OUTI P1,00`).

### 3.9 Spare gates

IC7/C, IC11/B, IC11/C have their inputs grounded (review: fine). IC6 and IC11 together use four of six 3-input NANDs.

## 4. Programming model

Every access is two instructions: select on P0, transfer on P1. The monitor's routines are the reference
(`firmware/monitor/monitor.asm`); `firmware/abi/README.md` lists the BIOS vectors that wrap them.

### 4.1 UART registers

Register number r (0..7) is presented as `UARTCS | (r << 3)`, i.e. `UARTAr` in the EQUs (`UARTA0` = $00 ... `UARTA7`
= $38). The 16550 map with DLAB (LCR bit 7): 0 = RBR/THR (DLL when DLAB), 1 = IER (DLM when DLAB), 2 = IIR/FCR,
3 = LCR, 4 = MCR, 5 = LSR, 6 = MSR, 7 = SCR. `software/ucemu/y1ucemu.c` `io_read()`/`io_write()` implement exactly
this table (LSR reads $60 | data-ready).

Initialisation (monitor lines 77-88):
```
OUTI P0,(UARTA3!UARTCS)   ; LCR
OUTI P1,080H              ; DLAB = 1
OUTI P0,(UARTA0!UARTCS)   ; DLL
OUTI P1,3                 ; 38400 (12 = 9600)  -> 1.8432 MHz / (16 x 3)
OUTI P0,(UARTA1!UARTCS)   ; DLM
OUTI P1,00
OUTI P0,(UARTA3!UARTCS)   ; LCR
OUTI P1,03H               ; 8 data bits, 1 stop, no parity, DLAB = 0
```

Transmit (`uartout` -> `uartoutw`): `BRDEV` first sends the instruction-level emulator to `OUTA P2`; on the machine
poll LSR bit 6 (THRE):
```
uartoutw: OUTI P0,(UARTCS!UARTA5)   ; LSR
          INP  P1
          ANDI 040H                 ; transmitter holding register empty?
          BRZ  uartoutw
          OUTI P0,UARTCS            ; THR (register 0)
          OUTA P1
```
Receive (`uartin`): poll LSR bit 0 (DR), then read RBR; the monitor turns CR into LF, shows the byte on the LEDs
(`JSR LEDOUT`) and echoes it (`JSR uartout`). `const` (BIOS $FFF8) is the DR test alone: `OUTI P0,(UARTCS!UARTA5)` /
`INP P1` / `ANDI 1`.

### 4.2 Switches, LEDs, TIL311

```
switchin:  OUTI P0,(SWITCHLED)   INP  P1      ; ACC = S7..S0 (1 = the throw on VCC)
ledout:    OUTI P0,(SWITCHLED)   OUTA P1      ; LEDs = ACC, bit n on LED n
TIL311out: OUTI P0,(TIL311)      OUTA P1      ; HI = ACC[7:4], LO = ACC[3:0]
```
`tests/assembler/ledcount` (10 bytes for the switch ROM), `romcount` and `romdiag` are built from these three idioms;
the emulator's `-s BYTE` sets what the switches read and `-L` reports LED/TIL311/ON writes (`y1ucemu.c` usage).

### 4.3 LCD

With `LCDENABLE` in P0 every `OUTA P1`/`OUTI P1` pulses E; `LCDREGISTER` chooses command (0) or data (1). R/W is
grounded, so use delays instead of busy polling. The only code in the tree is the commented monitor test (section
3.7); the initialisation bytes it used were $3C, $01, $0F. **To verify:** whether an LCD module is fitted to the card
in the machine (MACHINE.md does not say).

### 4.4 IN, OUT

`BRINH addr` branches while the IN toggle is on the VCC throw, `BRINL addr` while it is on GND; the monitor's
`switchtoggle` waits for a full off-on-off transition with a delay loop as debounce. `ON`/`OFF` drive the OUT LED.
The monitor's start-up uses IN to choose between the command loop and the built-in tests (`BRINH cmdloop`).

### 4.5 The rule the hardware does not enforce

Set exactly one device bit (SWITCHLED, LCDENABLE, TIL311, UARTCS) at a time. SWITCHLED with UARTCS on a P1 read puts
IC3 and the UART on the bus together (review 3.3).

## 5. Timing and the design-review findings

The one timing figure that matters is the `INP` window: -IO-RD asserted at step 8, the accumulator latched at the
leading edge of step 9 (`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.6). In that one step -IO-RD must propagate through
IC8/A (the fast falling edge of an open-collector output), IC6/B (the switch case) or the UART's IOR-to-data delay,
and settle on the bus. For a *read* the enabling edge is the fast one; the slow RC-limited edge (IO-RD returning high
through RN2) only ends the cycle. The review therefore calls the port decode sound and lists only LOW items:

| ID | Severity | Finding | Status 2026-09-23 |
|---|---|---|---|
| DESIGN-REVIEW.md, io | MED (retracted) | IC1 XTAL2 floating | Not a fault: an external oscillator on XTAL1 leaves XTAL2 open (control/IO notes 3.1) |
| 3.1 | note | "ECS-2100AX-200" is a package name; the monitor's divisor implies 1.8432 MHz | **To verify:** read the can, put the frequency in the BOM |
| 3.2 | LOW | strobes through 74LS06 with a pull-up of unknown value; slow rising edges through IC6/IC7/IC11 could double-pulse the LCD E line (a doubled character) | Open; RN2 value to record |
| 3.3 | LOW | decoder is address-only, device bits not mutually exclusive | Software rule (section 4.5); the V1.2 idea of -BUS-EN on IC5 pin 5 has no functional effect since every consumer is strobe-qualified |
| 3.4 | LOW | LCD backlight across the rail with no resistor | **To verify** on the module |
| L-2 (microcode review) | LOW | -IO-ADDR-LD reaches nothing; the OUTI/OUTA/INP records spend 2-3 steps on it | Microcode clean-up item; harmless on the card |
| 1.5 (microcode review) | note | the open-collector rise after -IO-RD is "the slowest edge in the machine" | By design; matters only if the clock is raised |
| cross-card | LOW | the machine relies on floating LS inputs reading high while the pipeline is off the bus; IO-RD/IO-WR are inactive then, so this card sits quietly during the 54 s microcode load | By convention (backplane has no pull-ups, control/IO notes 5.1) |
| H-4 (microcode review) | HIGH, microcode | OUTVR ($80-$8F) has all-zero records: fetching one asserts every strobe for 61 steps, -IO-RD and -IO-WR included | Open in the generator (fill undefined records); never emit OUTVR |

Nothing on this card is on the H-1/H-2/H-3 path; those fixes (2026-09-22) concern PUSHR and the branch records.

## 6. Jumpers, switches, LEDs, connectors

| Item | Pins / meaning | Setting in the machine |
|---|---|---|
| IO-ADDR-HL (2x3) | 1 GND, 2 IO-ADDR3, 3 IC5 G2A, 4 IC5 G1, 5 IO-ADDR3, 6 VCC | low half P0-P7 (MACHINE.md, OS-PLAN: "it stays in the low half"): 3-5 and 4-6. **To verify** physically |
| IO-ADDR (2x8) | odd pins = -IO-ADDRSEL; even pins 16..2 = -IO-SEL0..7 | P0 = control: pins 15-16 |
| DATA-ADDR (2x8) | odd pins = -IO-DATASEL; even pins as above | P1 = data: pins 13-14 |
| JP1 (2x3) | 1,6 RX-IN; 2,5 TX-OUT; 3 DB9 pin 3; 4 DB9 pin 2 | **To verify:** straight (1-3, 2-4) or crossed (3-5, 4-6) |
| INPUT (1x2) | 1 = bus IN, 2 = IN switch pole | fitted (BRINH/BRINL work: romcount/romdiag) |
| INT (1x2) | 1 = UART INT, 2 = IC8/F input | **To verify:** open or fitted; the monitor does not enable UART interrupts either way |
| S0-S7 (M9040P toggles) | bit 0..7 of the switch byte; VCC throw = 1 | operator's choice |
| IN (M9040P) | the IN line | rests low for the monitor's tests / romcount's mirror phase |
| LEDs 0-7, OUT, PWR | bit n, the OUT line, VCC | — |
| LO, HI (TIL311) | low, high nibble of the last TIL311 write | — |
| TM1 10k | LCD contrast | — |
| J1 DB9 female | pins 2/3 through JP1, 5 = GND; RS-232 levels from the MAX232 | to the Mac at 38400 8N1 (MACHINE.md) |
| X2 | HD44780 1602 module footprint; `Notes.md` 1.1 added a keep-out under it | **To verify:** fitted or not |
| X1 | DIN 41612 96-pin, `FABC96R` | slot not recorded |

`BACKLOG.md`'s loader note speaks of "the FTDI on the card's TTL header"; the V1.1 schematic has no TTL-level serial
header, only the DB9 behind the MAX232. **To verify:** how the Mac is actually cabled to the console (an FTDI RS-232
cable on J1, or a TTL tap that is not in the drawing).

## 7. Bring-up and test

Proof so far:

- **From the bus tester (2020):** `tests/bus-tester-scripts/IO/serialout`, `serialin`, `basic-out` drive the card
  without a CPU: `-BUS-EN:1#`, `IOADDR0..3:0#`, `DATABUS-WR-MODE:1#`, then pairs of `WR-DATABUS:58#` / `-IO-WR:1#` /
  `-IO-WR:0#` on port 0 and `IOADDR0:1#` / `WR-DATABUS:80#` / `-IO-WR` on port 1 — the same LCR/DLAB/divisor sequence
  as the monitor's init, byte by byte ($58 = UARTCS|UARTA3, $80 = DLAB; $40/$0C = DLL 12 = 9600 baud in the script;
  $48/$00 = DLM; $58/$03 = 8N1).
- **From the switch ROM (2026-09-21):** `tests/assembler/ledcount` counted on the LEDs with the function-generator
  clock (MACHINE.md).
- **From the EEPROM (2026-09-22/23):** `tests/assembler/romcount` mirrored the switches to the LEDs and TIL311s, then
  counted overnight after the input switch was flipped (the ON LED lit); `romdiag` stages 0-11 read the switches, LEDs,
  ON LED and IN line and found the missing second register card.
- **The UART with the CPU:** the 2021 monitor ran on the machine at 38400 (MACHINE.md "UART behind P0/P1 at
  38400"); the tree's rebuilt monitor is not yet burned. `software/ucemu/y1ucemu.c` runs the same routines against its
  16550 model, so a console fault on the machine and not on the emulator points at the card.

If it misbehaves:

| Symptom | Check |
|---|---|
| LEDs never change | IC10 Q1 (SWITCH-LED) after `OUTI P0,1`; IC6/A pin 6 (N$41) pulsing on `OUTA P1`; -B-RESET high (IC8 pin 8) |
| LEDs show the wrong bit order | R3..R10 wiring; the 1.1 change list swapped them once |
| switches read $FF or $00 | IC3 enable N$32 (IC6 pin 6) should pulse low during `INP P1`; RN2/-6 pull-up on IO-RD; the -IO-RD step window (section 5) |
| TIL311 blank or stuck | IC9 CLK N$75 (IC11 pin 12); TIL311 pin 14 VCC and BI/L-SI grounded |
| no console output | LSR polling loop in `uartoutw`: read LSR through P0 = $68; if THRE never sets, CS1 (IC10 Q7) or the oscillator; scope Y1 output for the frequency; TX-OUT on JP1; the JP1 routing |
| characters garbled | baud: divisor 3 assumes 1.8432 MHz; try `12` (9600) if the can is 7.3728 MHz, or read the can |
| doubled LCD characters | review 3.2: slow IO-WR rise through RN2; scope IC8 pin 4 |
| BRINH/BRINL never branch | INPUT jumper; IN line C26 at the ALU's 74LS251 D5; the IN switch throws |
| ON never lights | the sequencer's OUT latch (IC22 there), R1, the OUT LED polarity |
| -INT stuck low | INT header fitted with IER non-zero; IC8/F |

## 8. Revision history and what a next revision should change

| Rev | Date | Status | Changes (`Notes.md`, `hardware/FABRICATED.md`) |
|---|---|---|---|
| V1.0 | 2020-07 | fabricated, retired 2021-01 | no IC9 latch / IC11; two 1x10 headers instead of the 2x3 jumper (README) |
| V1.1 | 2020-11-29 | **in the machine** (`media/io v1.1 top.jpeg`, `bottom.jpeg`) | TIL311 latch pins to GND and VCC to pin 14; LED bit order; keep-out under the LCD; DB9 with the null-modem jumper; TIL311 broken out to its own control bit (bit 7). The Working copy of 2020-07-31 was the same board with the V3.1 bus names; folded 2026-09-20 |

The never-done **V1.2** ideas (`Notes.md`, `BACKLOG.md`):

1. **A directional data-bus buffer driven by -IO-RD.** Today the UART, the LCD and the three 74273 D-inputs load the
   bus directly and IC3/the UART drive it directly. A 74LS245 with DIR = -IO-RD and G from the card select would
   isolate the card (the same question the index-register notes ask about -RD-SEL).
2. **IC5 pin 5 (G2B) to -BUS-EN**, so the decoder is off while the tester owns the bus. The review found no
   functional need (everything is strobe-qualified) but it costs nothing.
3. From the reviews: record RN2, R1, R3-R10 values; make the device bits exclusive in hardware (a 74LS138 on Q0..Q2
   instead of four flags) or at least document the rule; a series resistor for the LCD backlight; a TTL-level serial
   header beside the DB9 if that is how the Mac is cabled.
4. Leave -IO-ADDR-LD unconnected as now, and let the generator drop its steps (L-2).

### The next device on the ports: CompactFlash on P8/P9

Decided 2026-09-22 (`docs/system/OS-PLAN.md` decision 1, `firmware/abi/README.md`, `software/cfmodel.h`), not built.
The circuit is the CF card v1.0's (`hardware/cards/cf/kicad/v1.0`, designed 2026-09-23, never ordered; theory in
[`cf.md`](cf.md)); since 2026-09-24 it is planned onto the memory card, not onto a card of its own (not designed yet).
(An I/O card V2.0 carrying the CF interface on P4/P5, decoded by this card's IC5, was designed on 2026-09-23 and
dropped on 2026-09-24; this card stays V1.1.)

- **Two ports, same select-then-data pattern as this card.** P8 = write-only register-select latch (bits 0-2 = the ATA
  task-file register 0-7: 0 data, 1 error/feature, 2 sector count, 3-5 LBA0-2, 6 drive/head, 7 status/command; bit 3
  = CF reset, 1 = held); P9 = the data port — a read or write of P9 strobes the CF's -IOR/-IOW on the selected
  register.
- **Parts (the v1.0 circuit):** a 74LS138 port decode (enabled by IO-ADDR3 high, Y0/Y1 = P8/P9 — so it lives in the
  *other* half from this card, which stays at P0-P7), a 74LS32 gating -IO-RD/-IO-WR with the two selects, a 74LS175
  select latch, a 74LS08 (buffer enable, CF reset, ACT LED), a 74LS245 data buffer, the CF status pull-ups and a 40-pin
  IDE header for a CF-to-IDE adapter; 8-bit True IDE mode (SET FEATURES $EF with feature $01 at init); otherwise the
  P8X CF card's circuit.
- **The driver already exists in the ROM** (`monitor.asm` `cfinit`/`cfread`/`cfwrite`, vectors $FFEC/$FFF0/$FFF4):
  `OUTI P8,CFSEL_CMD` / `INP P9` polls status (BSY bit 7, DRQ bit 3, bounded to 65536 polls so an absent card times
  out with ACC = 1); a sector transfer selects register 0 once and loops `INP P9` / `STAVR Rn` / `INCR Rn` 512 times.
- **The emulators model it** (`software/cfmodel.h`: `CF_PORT_SEL` 8 sets the select, `CF_PORT_DATA` 9 reads/writes
  the selected register; no image attached = $FF like a floating bus), so the driver runs on the emulators first and
  the hardware can be bench-tested with the bus tester (`OUTI P8` / `INP P9` by hand, as the 2020 IO scripts did for
  the UART).
- Port map afterwards (OS-PLAN decision 3): P0/P1 this card, P2-P7 decoded by it but unused (reserved to it in the
  plan; `BACKLOG.md` 2026-09-24: probably free for another card), P8/P9 CF, PA/PB the next video
  card's 6845 address/data registers, PC/PD a PS/2 keyboard controller, PE/PF free.
