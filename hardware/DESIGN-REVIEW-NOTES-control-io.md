# Design review — control paths and I/O (sequencer logic/memory, IO, bus tester, backplane, video) — 2026-09-21

Second pass after the mechanical one in `DESIGN-REVIEW.md`. Read from the KiCad netlists (`reports/netlist.net`, pin
types from the Eagle symbols), chip values from the Eagle boards, the firmware that drives the ATmegas
(`embedded/bus-tester/bus-driver`, `embedded/sequencer-card/sequencer4`) and the microcode generator
(`firmware/microcode/ucode-generator2`). Gate pin-outs were checked against the symbol pin functions (I0/I1/O for
7400/08/32, O/I/I for 7402; 74175/74/192/244/374 pin functions as printed in the netlist).

Every finding: the trace (ref.pin -> net -> ref.pin, chip types), the failure scenario, severity
(HIGH = stops the card / damages parts, MED = unreliable or latent, LOW = housekeeping), and how to confirm it on
the bench. Already-known items (BACKLOG.md, video README) are not repeated except where a new detail changes them.
Report only; no redesign.

Scripts used (not committed): a netlist dumper (parts + nets with pin function/type), an SV1/SV2 pin-by-pin
comparator, a bus-driver-table-vs-tester-wiring check and a microcode-bit-vs-RAM-wiring check; the results of the
three checks are in the "checked, no issue" lists below.

---

## 1. Sequencer logic v2.1 (`hardware/cards/sequencer-logic/kicad/v2.1`)

### 1.1 HIGH — 17 bus lines are driven by the logic card no matter what -BUS-EN says (extends the BACKLOG item)

The BACKLOG's "CPU off switch" item assumes that de-asserting -BUS-EN silences the card. It silences the nine
pipeline 74LS374s (IC7, IC12, IC14, IC16, IC17, IC19, IC20, IC28) and the two microcode-address 74LS244s
(IC15, IC35), and nothing else. These stay on the bus:

| Bus pin(s) | Driver | Enable / control | Trace |
|---|---|---|---|
| B9–B12 REG-RD-ID0..3, B13–B16 REG-LD-ID0..3 | IC4 74LS244 (both halves) | -ONE-OPERAND-SEL = IC31 74LS04 p4 | IC16 74LS374 p16 (7Q, -2-BYTE-OPERAND-SEL) -> IC31 p3; IC31 p4 -> IC4 p1/p19 and IC18 p19 |
| same 8 lines | IC5 74LS244 | -2-BYTE-OPERAND-SEL directly | IC16 p16 -> IC5 p1/p19 |
| C3–C6 ADDR-REG-ID0..3 | IC18 74LS244 B half (p9/7/5/3) | -ONE-OPERAND-SEL (IC18 p19) | inputs = LADDR-REG-ID0..3 from IC19 74LS374 |
| C3–C6 | IC18 A half, IC11 74LS244 A half | SRC-ADDR (IC17 p5 -> IC18 p1), DEST-ADDR (IC16 p19 -> IC11 p1) | inputs = operand register IC6 74LS374 |
| B18 -REG-LD-LO | IC31 74LS04 p10 (totem pole) | none | IC27 74LS08 p11 -> IC31 p11 |
| B20 -REG-LD-HI | IC31 74LS04 p12 (totem pole) | none | IC24 74LS08 p6 -> IC31 p13 |
| C30 -RESET | IC36 74LS04 p6 (totem pole) | none | front-panel RESET latch (IC32 74ALS02 p4) -> IC36 p5 |
| C27 OUT | IC22 74ALS02 p13 (totem pole) | none | OUT-ON/OUT-OFF SR latch IC22 gates C/D |
| C28 -BUS-EN | IC36 74LS04 p8 | none | known (BACKLOG) |

IC4 and IC5 have complementary enables (IC31 inverts one into the other), so one of them is always on. With
-BUS-EN high, IC16 p16 floats, IC31 p3 reads high, IC31 p4 goes low and IC4 + IC18B drive whatever the floating
LREG-*/LADDR-* nets happen to read onto B9–B16 and C3–C6.

Failure: the bus tester (`bus-driver.ino` `setup()`) makes every signal in its table a push-pull MCP23017 output —
including -RESET, OUT, -REG-LD-LO/HI, REG-RD-ID, REG-LD-ID, ADDR-REG-ID — and puts the address and data buses in
WRITE mode; only BR-COND, -INT and IN are left as inputs. With the logic card fitted there are two totem-pole
drivers on each of these 17 lines. The tester reads back wrong levels and, worse, an LS244/LS374 output high
(short-circuit current 40–225 mA) into an MCP23017 output low (absolute maximum 25 mA per pin) can kill the
expander pin. This is why the tester "cannot load RAM with the logic card fitted" — but the v2.2 fix as written
(OEs of the 374/244s through a switch, OC driver for -BUS-EN) would still leave B9–B20, C3–C6, C27 and C30 driven.

Confirm: logic card fitted, sequencer READY high, tester plugged in. With the CPU held in reset, drive
REG-RD-ID0 (B9), -REG-LD-LO (B18), ADDR-REG-ID0 (C3), OUT (C27) and -RESET (C30) from the tester and read them back;
a meter on the line shows an intermediate level (~0.5–1.5 V) instead of the commanded one.

### 1.2 HIGH (documentation / rebuild) — IC33 and IC34 are drawn and BOM'd as 74LS192 (BCD decade); the microcode addressing needs binary counters

Trace: N$4 (IC38 74LS08 p6) -> IC33 UP p5; IC33 QA p3 -> IC35 74LS244 p2 -> p18 = CNT-CLK (the pipeline
clock, via IC25 74LS32 p13/p11 = BUS-LATCH-CLK); IC33 QB/QC/QD (p2/6/7) -> IC35 -> CADDR0/1/2 (SV1 p14/16/18);
IC33 CO p12 -> IC34 UP p5; IC34 QA/QB/QC -> CADDR3/4/5; IC34 QD p7 -> COUNT-FAULT -> IC26 74LS32 p12. Each
microstep is two counter clocks (QA is the phase bit, QB.. are the step address); 64 steps need a 7-bit binary
count. The generator (`controlLine.c writeCurrentLine`, `main.c loadNextInstruction`) writes lines 0,1,2,… per
opcode and the fetch alone is lines 0–5.

With decade parts the step address sequence would be 0,1,2,3,4, 8,9,10,11,12, 16,… (line 5 of the fetch — the one
that drops -REG-UP and -MEM-RD — never executes, then line 8 runs) and COUNT-FAULT fires after 40 steps, not 64.
The machine executes the switch-ROM program (MACHINE.md 2026-09-21), so binary parts are almost certainly what is
soldered in — but `Sequencer-Logic-Prod-V2.1l.brd` (value 74LS192N), the BOM CSV and both KiCad symbols (74*192)
say decade. The same symbol/BOM entry appears 16 times on the index-register card (`register/eagle/v1.1` BOM: 16 ×
74LS192N for the 16-bit registers, where decade counters would make the PC count in BCD) — outside this review's
scope but the same discrepancy. A rebuild from the BOM would order the wrong part.

Confirm: read the markings on IC33/IC34 (and on the register cards' counters). If they are 193s, correct the
value/BOM; if they really are 192s, the fetch sequence works only by accident of which lines are skipped and
`tests/sequencer` should dump the step address (JP4 p3 / SV1 CADDR pins) while single-stepping.

### 1.3 MED — The pipeline is not reloaded when reset is asserted, only when it is released; during reset (and from power-up until the first reset release) the 374s drive the last/random word onto the bus

Trace of the reset-release pulse: RESET (IC32 74ALS02 p4) -> IC37 74LS04 p1->p2 (N$44) -> IC37 p9->p8 (N$42) ->
IC36 74LS04 p11->p10 (N$46) -> IC32 p9; IC32 p8 = RESET; IC32 p10 = N$32 = NOR(RESET, RESET delayed 3 gates).
N$32 is a ~30–45 ns positive pulse only on the falling edge of RESET; it is ORed with CNT-CLK in IC25 (p12/p13 ->
p11 = BUS-LATCH-CLK). COUNT-RESET (IC26 p3 = RESET OR (UCODE-COUNT-RESET AND N$4)) clears IC33/IC34 during reset,
so CNT-CLK falls to 0 and never rises. Nothing clocks the pipeline while RESET is high; nothing clears it either
(-RESET goes only to IC8/IC9 74LS175 CLR p1). -BUS-EN stays asserted (IC36 p8 follows READY).

Consequence: while the front-panel switch sits in RESET the bus carries whatever the pipeline last held — the step
that was executing when reset was hit, or power-up garbage. BACKLOG.md's description ("in reset the pipeline still
drives ... word instruction 0 step 0") is what happens *after* the switch goes to EXECUTE (N$32 latches address
IR=0/step=0); during reset it is worse than that. Memory-card side: -RESET presets the boot flip-flop (memory IC12
74LS74 PRE p4) so the 28C64 answers every address (FORCE-ROM); memory IC6 74LS04 p9->p8->p3->p4 (N$4) feeds
-MEM-WR straight to the -WE (p27) of IC1, IC2 and the EEPROM IC13; -ROM-CS comes from the address decode with -VMA
(IC7 74LS138 G2A). A stale pipeline word with -MEM-WR and -VMA asserted therefore writes the EEPROM during reset.
The ROM was byte-identical to `rom/shipped` on 2026-09-18, so either it has not happened yet or the fitted 28C64
has data protection.

Confirm: scope B24 (-MEM-WR) and C12 (-VMA) at power-up and with RESET held, several times; run
`tools/verify_firmware.py` against the chip after a batch of power cycles. Related: the N$32 pulse (3 × LS04 tpd)
is right at the LS374's 15 ns minimum clock width — fine with LS parts, marginal if IC36/IC37 are ever replaced
by faster families.

### 1.4 MED — SPARE3 pipeline bit is wired to the sequencer-memory ATmega reset through JP2, and the microcode holds that bit at 0

Trace: RAM IC5 I/O5 (SV1-side name SPARE3) -> memory JP1 p1 -> logic JP1 p1 (USPARE3) -> IC16 74LS374 p7 (3D);
IC16 p6 (3Q, SPARE3) -> JP2 p2; JP2 p1 -> -MEM-CPU-RESET -> logic JP1 p2 -> memory JP1 p2 -> ATmega IC15 p1
/RESET and all five MCP23017 /RESET (p18), R4 10k pull-up. The generator's `initCurrentLine`
(`main.c:94`) calls `clearSignal` on every name; for a name without a '-' prefix that is `bitOff` = 0
(`main.c:76-86`). SPARE3 is never set anywhere, so every microcode line has SPARE3 = 0.

Failure: if JP2 is ever fitted the sequencer-memory card is held in reset (READY low, -BUS-EN high, RAM control
lines floating) and the CPU can never run. Harmless today only because JP2 is open. Confirm: JP2 open.

### 1.5 LOW — -REG-LD-LO / -REG-LD-HI are combinational with unequal paths (latent glitch)

-REG-LD-LO = NOT(LREG-LD-LO AND N$53) [IC27 74LS08 p13/p12 -> p11 -> IC31 p11 -> p10 -> B18];
N$53 = IC30 74LS32 p6 = (REG-LD-ID != 0) OR (branch latch N$71 AND REG-LD-ID == 0), where REG-LD-ID is taken from
the bus (B13–B16) through IC25/IC30 ORs, IC37 p13->p12, IC27 p9/p10; the branch latch N$71 is the gate SR latch
IC26 p8 / IC37 p3->4 / IC30 p3 / IC37 p5->6. Two gates on the LREG-LD-LO path versus seven on the ID path: if a
step raises LREG-LD-LO on the same edge that moves REG-LD-ID from non-zero to 0 with the branch not taken, B18
pulses low for ~40–60 ns before N$53 falls (a runt load strobe to R0 on the register cards' 74LS32 inputs
IC1/IC15/IC25/IC47 p10). The current generator does not do that: `branch.c` writes `setLdId(PC)` one line before
it raises REG-LD-LO/HI, and REG-LD-ID is 0 from `initCurrentLine` anyway. A future microcode that changes the ID
and the strobe together will hit it. Confirm (if the microcode is changed): scope IC31 p10 across the step edge.

### 1.6 LOW — Interrupt jumper JP3 needs two jumpers; edge mode triggers on the release of -INT

IC23A 74LS74: CLK p3 = INT-EDGE (JP3 p2), PRE p4 = IC36 p12 = NOT(INT-LEVEL, JP3 p4), CLR p1 = IC36 p4 =
NOT(INT-START OR RESET), D p2 = VCC. -INT (C13) is JP3 p3, GND on p1 and p5, pull-up selectable by the
-INT-PULLUP header (R5 10k). Mode select = -INT to p2 (edge) or p4 (level); the *other* input must be jumpered to
its GND neighbour, otherwise IC36 p13 floats high (PRE permanently asserted, DO-INT whenever enabled) or the
LS74 clock floats. In edge mode the LS74 clocks on the rising edge, i.e. an interrupt is registered when -INT is
released, not when it is asserted. Confirm: JP3 population; in edge mode pulse -INT low from the tester and watch
IC23 p5 set on the trailing edge.

### 1.7 LOW — Counter clock gated by asynchronous levels

N$4 = IC38 p6 = (UCODE-CLK AND RUN AND NOT(COUNT-FAULT OR DO-HALT)) with UCODE-CLK = (QG1 AND FREE-RUN) OR
(SINGLE-STEP/WAIT AND SINGLE-STEP-CLK) (IC38 p8/p11, IC26 p6). RUN (IC32 p1), the halt flip-flop (IC23B p9) and
the SS/WAIT latch (IC29) change asynchronously to QG1, so CONT, EXECUTE or flipping SS/WAIT while running can
produce a runt pulse on IC33 UP. Front-panel only; the switch latches (IC29/IC32 NOR pairs with R6–R11
pull-downs) are debounced, the HALT/CONT push buttons (R3/R4 pull-ups into IC31) are not, but they only feed a
set-only / clear-only flip-flop, so the bounce is harmless.

### 1.8 LOW — All pipeline outputs float when -BUS-EN is high (no pull-ups anywhere)

With READY low (54 s microcode copy) or the tester holding -BUS-EN high, IC16's -INT-JMP (p12) and -BRANCH-RD
(p2) — the output enables of IC10/IC3 and IC21/IC13 (74LS374 on DATA0–15) — float, as do OPERAND-CLK,
BRANCH-LD-*, INT-LD-*, OUT-ON/OFF, LD-INS-REG, UCODE-COUNT-RESET, CNT-CLK and COUNT-FAULT. LS inputs read a
floating pin as high, which is the inactive level for all of them (COUNT-FAULT high even stops the counter clock),
so it works by convention; noise on -BRANCH-RD/-INT-JMP could put the branch/interrupt registers on the data bus
while the tester drives it. Confirm: with READY low, scope IC16 p2/p12.

### Checked, no issue (sequencer logic)
- SV1/SV2: all 80 pins carry the same signal on both cards (U-prefix on the logic side); JP1 1:1 SPARE3 /
  -MEM-CPU-RESET / SRC-ADDR / DEST-ADDR on both cards.
- Instruction register IC8/IC9 74LS175: CLK = IC24 p3 = LD-INS-REG AND RUN, CLR = -RESET; opcode source is
  IC2 74LS244 (DATA0–7, enable DO-INT low) or IC1 74LS244 (all inputs VCC = $FF, enable -DO-INT) — complementary
  through IC36 p1->p2.
- Microcode address: CADDR6–13 = IC15 74LS244 from IC9/IC8 Q outputs; CADDR0–5 from the step counter (1.2).
- Operand paths: IC6 74LS374 (OPERAND-CLK, OC = GND) -> IC5/IC18A/IC11A; IC4 vs IC5 exactly one enabled.
- Branch latch and conditional PC load logic as the Notes.md V2.1 change list describes; BR-COND (C24) input only.
- OUT SR latch IC22 gates C/D; IN (C26) unconnected on this card; -RUN (C29) unconnected everywhere.
- Halt: IC23B set by (FP-HALT AND UCODE-COUNT-RESET) OR SOFT-HALT (IC24 p11, IC25 p6), cleared by RESET OR CONT
  (IC32 p13); SOFT-HALT and USOFT-HALT are one net (Notes.md item resolved).
- Spare gates: IC37 p11 grounded; IC11B inputs grounded and enabled (harmless).
- Step-clock source jumper SS-SEL (front-panel latch IC29 gates C/D or external JP4 p2); JP4 exposes
  UCODE-COUNT-RESET.

---

## 2. Sequencer memory v2.1 (`hardware/cards/sequencer-memory/kicad/v2.1`)

### 2.1 LOW — RAM control lines float whenever the ATmega is in reset or in its bootloader

-CMEMSEL (IC15 PB2 p16) -> all eight 62256 -CS p20; -CMEMRD (PB1 p15) -> -OE p22; -CMEMWR (PB0 p14) -> -WE p27;
no pull-ups on any of the three. Until `setup()` runs (Arduino bootloader delay after power-up, or any time
-MEM-CPU-RESET is pulled low by LOCAL-CPU-RESET / JP1) the pins are inputs and the RAMs see undefined
-CS/-OE/-WE while the expanders (also held in reset) are inputs. Any corruption is repaired by the copy + verify
that follows, so this is housekeeping; BUS-READY (PD7 p13 -> SV1 p12 -> logic IC36 p9) also floats high in that
window, so -BUS-EN is asserted and the logic card puts its stale pipeline word on the bus (see 1.3). Confirm:
scope IC15 p14 during power-up.

### 2.2 LOW — DTR auto-reset dead-ends; FTDI-VCC jumper

DTR-RESET0 solder jumper: p1 = FTDI DTR (JP3 P$1, N$33), p2 = N$8 which has no other node — nothing reaches
/RESET and there is no series 100 nF. Same on the bus tester (DTR-RESET0 p2 = N$9, single node). Flashing needs
the local reset button. FTDI-VCC0 (both cards) would parallel the FTDI's 5 V with the backplane rail if closed
while the card is on the bus.

### Checked, no issue (sequencer memory)
- Run-mode gating in `sequencer4`: after the verified copy `setAddressInput()`, `setDataInput()`,
  `uCodeRamRead(true)` (-OE low), `uCodeRamSelect(true)` (-CS low), -WE left high, then READYLINE high. In load
  mode -BUS-EN is high (READY low -> IC36 p8) so IC35/IC15 on the logic card are off the CADDR lines while IC10
  drives them. The firmware's own hint ("is -BUS-EN inactive?") covers the tester-asserts--BUS-EN case (BACKLOG).
- Microcode bit map: all 64 `yaccsignaldata2.h` (chip,port,bit) entries land on the RAM I/O pin whose SV1/SV2
  (or JP1) pin reaches the 74LS374 D input of the same-named signal on the logic card; generator byte index
  `(chip-1)*2+port` (`controlLine.c:103`) equals the loader's `writeGPIOAB` low/high byte order.
- I2C: IC10 0x20 (address), IC14 0x21, IC13 0x22, IC11 0x23, IC12 0x24 — matches `mcp[i].begin(i)`; on-board
  IC9 24AA01 at 0x57 (A0–A2 = VCC) is displaced by the adaptor (devices 6 and 7).
- CADDR14: R5 10k pull-up, header CADDR14 to GND; jumper off = upper 16K, on = lower; the ATmega has no pin on it,
  so load and run address the same half.
- EEPROM WP (IC9 p7) on JP2 (GND / VCC); STARTSWITCH R1 pull-up; UCODE mode switch to VCC/GND.
- MCP23017 100k pull-ups left on in run mode (`setDataInput`) — negligible load on the RAM outputs.

---

## 3. IO card v1.1 (`hardware/cards/io/kicad/v1.1`)

### 3.1 Correction to DESIGN-REVIEW.md — XTAL2 floating is correct

Y1 (ECS-2100AX oscillator) p5 OUTPUT -> N$31 -> IC1 XR16C550 XTAL1 p16; XTAL2 p17 (N$61) open, which is the
datasheet connection for an external clock. Not a fault. The Eagle value "ECS-2100AX-200" is the package name,
not a frequency; `firmware/monitor/monitor.asm:74` programs divisor 3 for 38400 baud, which implies a 1.8432 MHz
oscillator (20 MHz would give 416 kbaud). Confirm: read the can; put the frequency in the BOM.

### 3.2 LOW — Strobe polarity is fine, but every strobe passes through an open-collector inverter with a pull-up of unknown value

-IO-RD (B25) -> IC8 74LS06 p1->p2 = IO-RD; -IO-WR (B26) -> p3->p4 = IO-WR; -RESET (C30) -> p5->p6 = RESET ->
IC1 p35 (active-high reset, correct) and -> p9->p8 = -B-RESET -> CLR of IC4/IC9/IC10 74LS273; -IO-DATASEL ->
p11->p10 = IO-SELDATA -> IC1 CS0 p12. Pull-ups are RN2 (value blank in the Eagle board). The UART's IOR/IOW
(p22/p19, active high) are used with -IOR/-IOW (p21/p18) tied to VCC — correct. The latching edges (273 clocks
N$40/N$41/N$75 = NAND of IO-WR with the select bits; LCD E = N$30; 16550 IOW trailing edge) all come from the
fast falling edge of the OC outputs, so the design is sound; the leading edges rise through RN2 and, if RN2 is
10k, take a few hundred ns through the LS10/LS00 inputs (IC6, IC7, IC11), where a slow edge can produce a double
transition on the LCD E line (N$30) = a double write. Confirm: scope IC8 p4 rise time; watch for doubled LCD
characters.

### 3.3 LOW — The port decoder is address-only and the device-select bits have no hardware exclusivity

IC5 74LS138: A/B/C = IO-ADDR0..2, G1/G2A from the IO-ADDR-HL0 jumper (IO-ADDR3 or fixed), G2B = GND; -IO-SEL0..7
go only to the two select headers (DATA-ADDR0, IO-ADDR0) that pick the data port and the control port. Every
consumer ANDs the select with IO-RD/IO-WR (IC6/IC7/IC11), so the lack of -VMA/-BUS-EN qualification (the V1.2
idea in Notes.md) has no functional effect; with the pipeline floating, -IO-RD/-IO-WR read high at IC8 and the
strobes are inactive. The control latch IC10 74LS273 (Q1 SWITCH-LED, Q2 LCD-ENABLE, Q3 LCD-REGISTER, Q4–Q6
UART-A0..2, Q7 UART-CS, Q8 TIL311) lets software set SWITCH-LED and UART-CS together, in which case IC3 74LS244
(enable IC6 p6) and the UART both drive DATA0–7 on a data-port read. Software rule; note it in `firmware/abi/`.

### 3.4 LOW — LCD backlight straight across the rail

X2 HD44780 p15 (A) = VCC, p16 (K) = GND with no series resistor: relies on the module having its own. Confirm on
the module.

### Checked, no issue (IO)
- UART register select vs chip select: CS0 = IO-SELDATA (data port decode), CS1 = UART-CS (control latch bit),
  -CS2 = GND, -AS = GND; A0–A2 from the control latch; every register access is "write control byte, then
  read/write data port" — reachable, no aliasing. RCLK p9 = -BAUDOUT p15 (ICLK). CTS/DSR/CD/RI tied high.
- -INT (C13) = IC8 p12 open collector with RN2 pull-up, from the UART INT (p30) through the INT0 jumper — the
  only -INT source in the machine; the tester keeps -INT as input; the logic card adds an optional 10k.
- Data bus: no buffer at all (Notes.md V1.2 idea); the only drivers are the UART (CS·IOR), IC3 (read of
  switches) and nothing else — LCD R/W = GND so the LCD never drives; 273s and TIL311 latches are loads only.
- 74LS273 latches clock on the trailing edge of IO-WR while the data source is still asserted (generator asserts
  the source one line before the strobe).
- TIL311 HI0/LO0: latch strobe p5 = GND (transparent), blanking p8 = GND (not blanked), as Notes.md V1.1 says.
- OUT (C27) drives only an LED through R1; IN (C26) is driven only by the IN0 switch (hard VCC/GND) through the
  INPUT0 jumper — fine while nothing else drives IN (tester: input; logic/register/video: unconnected).
- Spare gates IC7C, IC11B, IC11C: inputs grounded.

---

## 4. Bus tester v1.1 (`hardware/cards/bus-tester/kicad/v1.1`)

### 4.1 HIGH (the other side of 1.1) — nothing on the card can make the expanders passive; the firmware drives every control line and both buses from setup()

IC1 (0x20) A3–A18 = ADDR0–15, IC2 (0x21) A19–B6 = DATA0–15, IC3 (0x22) B7–B22, IC4 (0x23) B23–C10, IC5 (0x24)
C11–C26, IC6 (0x25) C27–C30 + the on-card LED/switch lines — MCP23017 GPIO pins straight onto the DIN pins, no
buffer, no enable. `bus-driver.ino setup()`: all pins INPUT first, then every table entry `pinMode(OUTPUT)` with
its inactive level, `dataBusDir(BUS_WRITE)`, `addrBusDir(BUS_WRITE)`, then only BR-COND, -INT and IN back to
INPUT. So from power-up the tester drives 32 bus + 52 control lines including -RESET (C30), -BUS-EN (C28), -RUN
(C29), OUT (C27) and the register-card ID/strobe lines that the logic card also drives (1.1). The 2020 V3.1
redesign (latches with enables) was the fix and was never built. Confirm: as 1.1.

### 4.2 LOW — RN1–RN4 pull up all 32 address/data lines on the bus; value not recorded

RN1–RN4 (RN-9, pin 1 = VCC) on A3–A18 and A19–B6. The v3.1 notes say "removing pull-ups ... on Data and Address
lines", so they are known to be there; the Eagle value is blank. If they are 1k each driver on the bus sinks
5 mA per line (fine for LS244/245, tight for anything weaker). Confirm: measure RN1 pin 1–2.

### Checked, no issue (bus tester)
- Signal table vs wiring vs bus: all 52 bus entries in `YACC_Common_header.h` (chip, port, pin) reach the DIN pin
  that carries that signal in the V3.2 pinout (only the IOADDRn/IO-ADDRn spelling differs); the 12 on-card
  entries (OUT-LED, IN-SWITCH, LEDS-LD, SWITCHES-RD, BIT0–7) are local.
- Local reset: ATmega p1, all six expander /RESET p18, CPU-RESET button and R2–R8 10k are one net that does
  not reach C30 — the bus -RESET is just IC6 GPA3.
- Switch/LED port: IC9 74LS244 enable = SWITCHES-RD (IC6 GPA7), outputs BIT0–7 shared with IC6 GPB0–7 and IC8
  74LS374 D inputs; firmware sets SWITCHES-RD high at setup and GPB to input before pulling it low
  (`read_switches`), so the only bus fight would be a firmware bug.
- I2C addresses 0x20–0x25 all distinct; EEPROM IC7 at 0x57; SCL/SDA 2.2k pull-ups.

---

## 5. Backplane v2.0 (`hardware/bus/backplane/kicad/v2.0`)

### Checked, no issue
- 8 × FABC96S; every one of the 86 signal pins is a straight 8-member net (nothing else on any of them): no
  pull-ups, no termination, no series resistors.
- Power: 5V on A2/B2/C2/A31/B31/C31 and GND on A1/B1/C1/A32/B32/C32 of every slot (6 + 6 pins per slot), eight
  electrolytics C1–C8 (one per slot, value blank), R1/PWR0 LED, single wire-pad entry for 5V and GND.

### 5.1 LOW — no pull-ups anywhere on the bus
Consequence for the scenarios above: whenever the logic card's 374/244s are off (READY low for ~54 s at every
boot; tester holding -BUS-EN high) the control lines float. LS inputs read that as high, which is inactive for
all the active-low strobes (that is why the memory and IO cards sit quietly during the microcode load), but the
active-high lines (REG-*-ID, ADDR-REG-ID, IO-ADDR, ALU0–3, BR-COND, OUT, IN) are undefined and the 4077/CMOS
inputs on other cards see mid-rail. Not a fault of the backplane as drawn; a pull-up bank on a future revision is
the usual answer.

---

## 6. Video card v1.1 (`hardware/cards/video/kicad/v1.1`) — beyond the README / fix-6845-register-select.md items

### 6.1 HIGH (untested path — no 6845 fitted yet) — the 6845 E clock is generated by an RC one-shot whose capacitor has no charging path except a TTL input

Trace: -MEM-RD (B23) -> IC26 74LS86 p9, -MEM-WR (B24) -> IC26 p10, IC26 p8 = N$1 = "a memory strobe is active"
(not qualified by BOARDSEL — every memory access in the machine, fetches included). N$1 -> IC1 74ALS08 p1 and
-> IC27 7416 p13; IC27 p12 (open collector) = N$3 -> R1 10K -> N$4 = IC1 p2 with C1 (value "1", C025 ceramic) to
GND. IC1 p3 = E -> IC17 6845 p23. There is no pull-up on N$3 or N$4.

Behaviour: at the start of every strobe the 7416 turns on and discharges C1 through R1 (τ = 10 µs if C1 = 1 nF),
so E = strobe until N$4 crosses the ALS08 threshold — a one-shot, presumably so that a single-stepped access
still gives the 6845 a bounded E pulse. When the strobe ends the 7416 releases, but the only current that
recharges C1 is IC1's input current (74ALS08 IIL ≤ 0.1 mA, i.e. ≥ 14 µs per volt into 1 nF; 14 ms/V if C1 is
1 µF). At run speed memory strobes arrive every few µs, so N$4 sits at or below threshold and E is short, ragged
or absent — the CRTC's registers cannot be written even after the RS fix. The planned "pull-ups on the 7416
outputs" must include IC27 p12; with a pull-up on N$3 the R1/C1 network becomes a real one-shot whose width is
set by R1·C1 (the MC6845 wants E ≥ 450 ns; 280 ns for the 1.5/2 MHz grades), so C1's value must be confirmed.
Confirm (no 6845 needed): run any loop, scope IC1 p2 (expect it stuck below ~1.5 V) and IC1 p3.

### 6.2 MED — Character clock is a self-clear runt; the 74LS166 may never load

IC28 74HC160 (asynchronous -CLR): CLK p2 = DOTCLOCK (SV4), A–D = GND, LD/ENT/ENP = N$73 (R10 1k to VCC).
CHARCLOCK = IC19 74LS00 p8 = NAND(IC28 QA p14, IC28 QC p12) — low only while the count is 5 — and it is
IC28's own -CLR p1: the low lasts one clear-propagation (~30–60 ns) and the counter divides by 5. CHARCLOCK also
clocks IC22 74LS175 p9 and IC23 74LS174 p9 (rising-edge, fine) and is IC24 74LS166 SH/-LD p15, which is sampled
only on DOTCLOCK rising edges (IC24 p7): the parallel load happens only if the runt is still low at the next dot
clock edge, i.e. only for dot clocks faster than ~16–20 MHz. With a slower crystal (Q2 value blank) the shift
register never loads and the video output is blank. A synchronous-clear counter (74HC162) holds the state for a
full period. Confirm: scope IC19 p8 against IC28 p2; look for glyph bits on IC24 p13 (QH).

### 6.3 MED — 74HC inputs driven by 74LS outputs

IC28 (74HC160) CLK p2 comes from IC20 74LS04 p6 or p8 through SV4, and -CLR p1 from IC19 74LS00 p8. LS VOH is
2.7 V minimum (2.4 V under load) against the HC VIH of 3.15 V at 5 V: works on typical parts (LS outputs idle
near 3.4 V), not by specification. 74HCT160 or pull-ups on N$57/N$59 and CHARCLOCK. Confirm: measure the high
level at IC28 p2.

### 6.4 LOW — the JP1 read-back latch is enabled by address alone

IC2 74LS373 -OE p1 = N$16 = IC27 7416 p10 (open collector, no pull-up — known) = NOT(IC1 p8), IC1 p8 =
AND(BOARDSEL·A11 (IC1 p6->p9), ADDR0 p10). No -MEM-RD term: a *write* to $D401/$D403 turns IC2 onto DATA0–7
against the writing card. Software must never write odd addresses in the upper half of the block; worth a line
in the fix document.

### 6.5 LOW — MC6845 LPSTB (IC17 p3) floating
An NMOS input; tie low. MA12/MA13/RA3/RA4 unconnected outputs are fine.

### Checked, no issue (video)
- Board select: IC18 74S85 A0–A3 = SV3 jumpers with RN2 pull-ups (RN2 p1 = VCC in v1.1), B0–B3 = ADDR12–15,
  A=B_in p3 = VMA (IC20 p13->p12), A<B_in/A>B_in = GND; $D000 = only SV3 5–6 fitted, as the README says.
- VRAM IC15 right port: -CER p47 = IC19 p6 = NAND(BOARDSEL, /A11 (IC20 p11->p10)); -OER p43 = -MEM-RD; R/-WR p46
  = -MEM-WR; A0R–A10R = ADDR0–10, A11R = GND. Left port -CEL/-OEL = GND, R/-WL = VCC (read only), A0L–A11L =
  6845 MA0–11.
- 6845: -RES p2 = -RESET (active low, correct); R/-W p22 = -MEM-WR (low = write, correct); CLK p21 = IC28 QC;
  -CS as documented. IC2's D inputs from JP1 with LE p11 from JP1 p13 (transparent when open).
- Character generator IC25: -CE/-OE = GND; A0–A2 = RA0–2, A3–A8 = IC23 Q6..Q1 = VDATA0–5 (64-character set),
  A9–A11 = GND; O0–O2 unused, O3–O7 -> IC24 D–H with A/B/C/SER = GND (5-dot glyph in an 8-dot cell). VDATA6
  (IC15 p22) intentionally unused; VDATA7 = inverse attribute into IC26 p2.
- Pipeline IC22 (cursor XOR attribute, DE) and IC23 (character code) both on CHARCLOCK, CLR from N$73 (high).
- Sync/video mix: IC27 p4/p6 (HS/VS) wired-OR on N$85 with R12 270 to VCC — the one 7416 net that does have a
  pull-up; video IC27 p2 through R11 33 Ω; RCA ground.
- Dot clock: Q2 Pierce oscillator on IC20 gates A/B with R8/R9 1k, buffered by gate C; IC21 74LS90 ÷2 (QA) with
  R0/R9 inputs grounded; SV4 picks osc or /2.
- IC1 74ALS08 gate assignment re-derived from the netlist: E = p1·p2; N$17 = BOARDSEL·A11; N$6 = N$17·A0; N$2 =
  A11·/A0 — consistent with the README's -CS analysis.
- +5V/VCC merge and RN2 = 10k: as recorded in the README.

---

## Cross-card notes

- Two drivers on -RESET, OUT, -REG-LD-LO/HI, REG-RD-ID, REG-LD-ID, ADDR-REG-ID (logic card totem poles vs tester
  push-pull) — 1.1 / 4.1 — is the item that decides whether the tester can ever be used with the logic card in.
- Reset polarity is consistent across the cards: -RESET active low on C30; logic card inverts its internal RESET
  (IC36 p6); IO card re-inverts to the 16550's active-high pin; memory card uses it as a 74LS74 preset; video
  card as the 6845's active-low reset; register card into a 4077; tester and sequencer-memory keep their local
  ATmega resets separate.
- Floating-bus dependence: the machine relies on "LS input floating = high = inactive" for every strobe during the
  54 s microcode load and whenever the tester tri-states; the backplane has no pull-ups (5.1).
- BOM/value gaps found on the way (all "value" blank in the Eagle boards): logic card R-values are present, but
  IO card RN2 and R1; bus tester RN1–RN4; video Q2, C1 ("1"), C16 ("10.0"); backplane C1–C8. Each is load-bearing
  for one of the findings above.

## Summary

HIGH: (1.1/4.1) the logic card drives 17 bus lines regardless of -BUS-EN — IC4/IC5/IC18 74LS244 enables come
from the pipeline, not from -BUS-EN, and -REG-LD-LO/HI, -RESET and OUT are plain LS04/ALS02 outputs — while the
bus tester's firmware makes every one of those lines a push-pull output at boot; the planned v2.2 "CPU off" fix
must cover them. (1.2) IC33/IC34 and the register-card counters are drawn and BOM'd as 74LS192 decade counters;
the microcode layout needs binary parts, so either the boards carry 193s or the fetch runs by accident — read the
chips, fix the BOM. (6.1) The video card's 6845 E clock is an RC one-shot (IC26/IC27 p12/R1/C1/IC1) with no
pull-up on the open-collector output, so C1 can only recharge through IC1's input current; at run speed E is
unreliable and the CRTC is unreachable independently of the RS fix. MED: (1.3) reset does not reload the pipeline
(only reset release does), so a stale -MEM-WR/-VMA word sits on the bus for the whole reset with the EEPROM mapped
everywhere; (1.4) JP2 would hold the sequencer-memory ATmega in reset because SPARE3 is 0 in every microcode line;
(6.2/6.3) the character clock is a ~50 ns self-clear runt used as the 74LS166 load, and 74HC160 inputs are driven
by LS levels. LOW items: interrupt jumper needs two jumpers / edge mode fires on release; combinational
-REG-LD-LO/HI (not exercised by the current microcode); floating pipeline outputs and a pull-up-free backplane;
sequencer-memory RAM control lines float during ATmega reset; DTR auto-reset dead-ends on both ATmega cards;
IO strobes through OC inverters with an unrecorded RN2; IO device-select bits not mutually exclusive; LCD
backlight resistor; video read-back latch enabled on writes; 6845 LPSTB floating; tester pull-ups RN1–RN4 of
unknown value. Checked and clean: SV1/SV2 and JP1 pinouts (80/80, 4/4), microcode bit map to RAM to pipeline
(64/64), bus-driver signal table to tester wiring to V3.2 pinout (52/52), sequencer4 run-mode RAM gating, I2C
address maps, UART register/chip select, reset polarity on every card, the IO XTAL2 "floating" item (false
positive), backplane power distribution.
