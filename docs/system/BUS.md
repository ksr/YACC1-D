# YACC1 bus — the backplane and its signals

Every line of the 96-pin bus: which pin it is on, who drives it, who listens, at what level, and the timing rules that
every card relies on. Companion to `ARCHITECTURE.md` (what the machine does with the bus) and `MICROCODE.md` (which
control-store bit drives which line).

Written 2026-09-23 from the YACC1-D tree.

Sources: `docs/system/connector/README.md` and `YACC1 Connector - V3.2.pdf` (text extracted; the pinout was cross-checked
pad for pad against `hardware/bus/bus-template/eagle/v3.2/Bus Template V3.2.sch`, parsed with Python through the
library's gate/pin → pad connects), `hardware/bus/README.md`, `hardware/bus/backplane/README.md`, `blank-card/README.md`,
`bus-template/README.md`, the backplane schematic and board (`hardware/bus/backplane/eagle/v2.0/yacc2buss.sch/.brd`),
`hardware/bus/blank-card/eagle/v3.1/Blank V3.1.brd`, `firmware/microcode/yaccsignaldata2.h`,
`embedded/libraries/YACC/YACC_Common_header.h` (the bus tester's table), `docs/isa/MICROCODE-REVIEW-NOTES.md` section 1,
`hardware/DESIGN-REVIEW-NOTES-datapath.md`, `hardware/DESIGN-REVIEW-NOTES-control-io.md`, `software/ucemu/y1ucemu.c`,
`tools/ucode_wavedrom.py` and `tools/ucode_review.py`, `docs/system/waveforms/REG-LD.json` / `REG-RD.json`, the card
schematics (`hardware/cards/<card>/eagle/<rev>/*.sch`), `hardware/mechanical/README.md`, `hardware/FABRICATED.md`,
`docs/system/MACHINE.md`, `BACKLOG.md`.

Conventions: `-` prefix = active low; pin names are row letter + number (`A1`..`C32`) as on the DIN 41612 connector;
"driver" is the part whose output pin is on the net; **To verify:** marks what the tree does not settle.

---

## 1. The bus in one paragraph

The YACC1 bus is a 96-pin DIN 41612 backplane ("yacc2buss", V2.0, eight slots) carrying 5 V and ground on the twelve
outer pins of every slot and 84 signals on the rest: a 16-bit address bus, a 16-bit data bus, three 4-bit register-id
fields, the memory/I/O/register/TMP/ALU strobes and a handful of system lines. It is an **asynchronous, strobed bus
with no clock line and no bus master arbitration**: the sequencer-logic card's pipeline registers drive every control
line for the length of a microcode step, and each card acts on the strobes it sees. There are no pull-ups, no
terminators and no series resistors on any signal (control-io review 5: "every one of the 86 signal pins is a straight
8-member net"). The signal naming is the Bus Template V3.2 of 2020-09-10; four earlier versions differ only in the
C3–C6 names and the presence of `-VMA` (section 2).

---

## 2. Versions of the specification

`docs/system/connector/README.md`:

| Spec | Date | What changed |
|---|---|---|
| YACC 3.0-old | 2020 | the first 2020 bus, before `-VMA` |
| V3 (June-18-2020) | 2020-06-18 | C3–C6 = `-ADDR-REG-RD0/LD0/RD1/LD1`, the strobes of the Address+TMP card |
| V3.1 | 2020-08 | adds `-VMA` on C12 (`blank-card/eagle/v3.1/Notes.md`: "Added -Valid Memory Address (-VMA) to bus Row C pin 12") |
| **V3.2** | 2020-09-10 | C3–C6 = `ADDR-REG-ID0..3` (the index-register number) — **the machine as built**; `hardware/bus/bus-template/eagle/v3.2/` is the canonical schematic template |

Two naming residues survive on real boards. The built cards were re-saved with V3.2 net names on 2020-11-29 but the
PDF beside each card was never refreshed (`connector/README.md`). The **Blank V3.1** card template (fabricated, the base
of the video card) and everything drawn on it (Mem Switch, Mem Register, video) still label C3–C6 with the old
`-ADDR-REG-RD/LD` names; none of those cards uses the four pins, so it is harmless, and `hardware/bus/blank-card/eagle/v3.2/`
(derived 2026-09-20, design only) carries the corrected names for the next card (`blank-card/README.md`, `BACKLOG.md`).
The V3 notes also record that "IN and OUT converted from active low to active HI" and "several signals changed to active
negative" between 3.0 and 3.1/3.2 (the PDF's footer; `alu/eagle/v3.2/Notes.md`, `register/eagle/v1.1/Notes.md`).

---

## 3. The pinout

From the V3.2 PDF, confirmed by the V3.2 template schematic (all 96 pads). Columns: **Driver** = who puts a level on
the line in the machine as fitted (the bus tester, section 4.10, can drive everything and is not repeated); **Listens** =
inputs on the net; **Level** = the asserted level. Details per group follow in section 4.

### Row A — address and data

| Pin | Signal | Driver | Listens | Level |
|---|---|---|---|---|
| A1 | GND | backplane | all | — |
| A2 | VCC (+5 V) | backplane | all | — |
| A3–A18 | `ADDR0..15` | the index register selected by `ADDR-REG-ID` (74LS244 pairs on the register cards), while `-VMA` and `-BUS-EN` are low | memory card (IC8/IC9 buffers, IC11 mux, IC10 raw ADDR15 for FORCE-ROM), video (7485 board select on ADDR12–15, VRAM A0R–A10R), Mem Switch / Mem Register comparators | high = 1 |
| A19–A26 | `DATA0..7` | see 4.1 | see 4.1 | high = 1 |
| A27–A30 | `DATA8..11` | see 4.1 | see 4.1 | high = 1 |
| A31 | VCC | backplane | | |
| A32 | GND | backplane | | |

### Row B — data high nibble, register control, memory/I/O/TMP strobes

| Pin | Signal | Driver | Listens | Level |
|---|---|---|---|---|
| B1 | GND | | | |
| B2 | VCC | | | |
| B3–B6 | `DATA12..15` | see 4.1 | see 4.1 | high = 1 |
| B7 | `-REG-FUNC-RD` | sequencer pipeline (74LS374, OC = `-BUS-EN`) | register cards: card select `-RDSEL` (IC31/IC32 with `REG-RD-ID2..3`, J1) | low |
| B8 | `-REG-FUNC-LD` | pipeline | register cards: `-LDSEL` (J2) | low |
| B9–B12 | `REG-RD-ID0..3` | sequencer IC4 (pipeline field) **or** IC5 (operand register nibble) — 74LS244s enabled by `-2-BYTE-OPERAND-SEL` and its inverse, **not** by `-BUS-EN` | register cards: IC33 (bits 0–1 → register), IC32 (bits 2–3 → card) | high = 1 |
| B13–B16 | `REG-LD-ID0..3` | same as above | register cards (load decode); **the sequencer reads them back** for the N$53 gate (IC25/IC30) | high = 1 |
| B17 | `-REG-RD-LO` | pipeline | register cards: enables the low-byte read buffer (IC2 pin 3 = `-Rn-RDSEL OR -REG-RD-LO`) | low |
| B18 | `-REG-LD-LO` | sequencer IC31 (74LS04, totem pole, not tri-stated) = NOT(N$53 AND `LREG-LD-LO`) | register cards: 74LS192 LOAD of the low byte (IC1 pin 8) | low |
| B19 | `-REG-RD-HI` | pipeline | register cards: high-byte read buffer | low |
| B20 | `-REG-LD-HI` | sequencer IC31 (totem pole) | register cards: LOAD of the high byte | low |
| B21 | `-REG-DN` | pipeline | register cards: IC1 pin 6 → 74LS192 DN | low |
| B22 | `-REG-UP` | pipeline | register cards: IC1 pin 3 → 74LS192 UP | low |
| B23 | `-MEM-RD` | pipeline | memory card (IC5 DIR, RAM/ROM `-OE` via IC6), Mem Switch/Mem Register (read qualifier), video (VRAM `-OER`, E one-shot) | low |
| B24 | `-MEM-WR` | pipeline | memory card (`-WE` of both 62256 and the 28C64 via IC6), Mem Register (write qualifier), video (VRAM `R/-WR`, 6845 `R/-W`, E one-shot) | low |
| B25 | `-IO-RD` | pipeline | I/O card IC8 (7406) → `IO-RD` | low |
| B26 | `-IO-WR` | pipeline | I/O card IC8 → `IO-WR` | low |
| B27 | `-TMP-REG-RD0` | pipeline | memory card IC26/IC27 output enable | low |
| B28 | `-TMP-REG-LD0` | pipeline | memory card IC14 → IC26/IC27 clock | low |
| B29 | `-TMP-REG-RD1` | pipeline | memory card IC28/IC29 output enable | low |
| B30 | `-TMP-REG-LD1` | pipeline | memory card IC14 → IC28/IC29 clock | low |
| B31 | VCC | | | |
| B32 | GND | | | |

### Row C — address register select, I/O port, ALU, system

| Pin | Signal | Driver | Listens | Level |
|---|---|---|---|---|
| C1 | GND | | | |
| C2 | VCC | | | |
| C3–C6 | `ADDR-REG-ID0..3` (V3.1 and older: `-ADDR-REG-RD0`, `-ADDR-REG-LD0`, `-ADDR-REG-RD1`, `-ADDR-REG-LD1`) | sequencer IC18 gate B (pipeline `LADDR-REG-ID`, enabled by `-ONE-OPERAND-SEL`); IC18A / IC11A would add the operand register under the `SRC-ADDR`/`DEST-ADDR` jumpers; **IC11 gate B is drawn with grounded inputs and enable on the same nets** (H-5, To verify) | register cards IC38 (74LS139: bits 0–1 → register, bits 2–3 → card via J3), enabled by `-BUS-EN OR -VMA` | high = 1 |
| C7–C10 | `IOADDR0..3` (`IO-ADDR0..3` on the cards) | pipeline | I/O card IC5 (74LS138 on bits 0–2; bit 3 through the `IO-ADDR-HL` header) | high = 1 |
| C11 | `-IO-ADDR-LD` | pipeline | **nothing** (single-node net on I/O v1.1) | low |
| C12 | `-VMA` | pipeline; asserted in every microcode step | memory card (IC3 with `-BUS-EN` → chip-select gating, IC5 G, FORCE-ROM clock), register cards (IC40 → address-buffer enable), video (7485 A=B cascade input), bring-up cards (IC1/IC7 NOR qualifiers) | low |
| C13 | `-INT` | I/O card IC8 pin 12 (7406 open collector, RN2 pull-up) from the 16550 INT through the INT0 jumper; optional 10 k on the logic card (`-INT-PULLUP`) | sequencer JP3 (edge → IC23A CLK, or level → IC36 → IC23A PRE) | low (open collector) |
| C14 | `-INTA` | pipeline (IC17 1Q) — never asserted | nothing in the machine | low |
| C15 | `-ALU-FUNC` | pipeline | ALU: transceiver enable (IC7 with `-BUS-EN`), JP1 option for the condition mux | low |
| C16–C19 | `ALU0..3` | pipeline | ALU: IC8 function decoder, IC26 mux select, IC29/IC30 mode, IC28 serial select, carry-in gate | high = 1 |
| C20 | `-AC-LD-INV` | pipeline | ALU: IC2/IC3 (inverting/straight input buffers), IC27 (BR-COND inversion) | low |
| C21 | `-AC-RD` | pipeline | ALU: IC10/IC11 direction, IC12 enable | low |
| C22 | `-AC-LD` | pipeline | ALU: IC1 → `AC-LD` → IC5 clock (via JP2), carry FF clock gate | low |
| C23 | `-SR-LD` | pipeline | ALU: IC29/IC30 clock, IC9B clock | low |
| C24 | `BR-COND` | **ALU card** IC27 pin 8 (the one control line a datapath card drives) | sequencer IC27 (AND with BR-TEST → the branch-taken latch) | high = condition true |
| C25 | `-HL-SWAP` | pipeline | register cards IC34 (4077) / IC31 → swap transceiver IC37 | low |
| C26 | `IN` | I/O card: the IN0 toggle switch through the `INPUT0` jumper (hard VCC/GND) | ALU IC26 mux input D5 | high = 1 |
| C27 | `OUT` | sequencer IC22 (74ALS02 SR latch, totem pole) | I/O card LED (R1); the logic card's own OUT LED | high = on |
| C28 | `-BUS-EN` | sequencer IC36 pin 8 (74LS04, totem pole) = NOT(READY from the memory half) | sequencer pipeline OCs and CADDR buffers; memory card IC3/JP1; register cards IC31/IC40; ALU IC7; bring-up cards | low = bus enabled |
| C29 | `-RUN` | nobody (connector-only net on every card) | nobody | — |
| C30 | `-RESET` | sequencer IC36 pin 6 (74LS04, totem pole) from the front-panel latch | memory IC12A PRE, ALU IC9 CLR, register cards IC34 → 74LS192 CLR, I/O IC8 → 16550 reset and 74LS273 CLRs, video 6845 `-RES`, sequencer IC8/IC9 CLR | low |
| C31 | VCC | | | |
| C32 | GND | | | |

Signals that are **not** on the bus although they are control-store bits — `LD-INS-REG`, `UCODE-COUNT-RESET`,
`OPERAND-CLK`, `BRANCH-LD-HI/LO`, `-BRANCH-RD`, `INT-LD-HI/LO`, `-INT-JMP`, `INT-EN`, `INT-START`, `BR-TEST`,
`-2-BYTE-OPERAND-SEL`, `SOFT-HALT`, `OUT-ON/OFF`, `SPARE3`, `-SRC-ADDR`, `-DEST-ADDR` — stay on the sequencer-logic card
(`MICROCODE.md` section 3). `UCODE-COUNT-RESET` and an external single-step clock are brought to header JP4 for a
debugger; the branch register and INT vector reach the bus only as data through `-BRANCH-RD` / `-INT-JMP`.

---

## 4. The signal groups

### 4.1 Data bus `DATA0..15` (A19–A30, B3–B6)

The data bus is 16 bits wide, but most drivers use only the low byte. Which card can drive which lanes
(`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.2–1.5; `y1ucemu.c` `compute()`; control-io review 3 and 6):

| Driver | Enable | Lanes driven | Value on the other lanes |
|---|---|---|---|
| memory card IC5 (74LS245) | `-MEM-RD` with `-VMA` (G) | DATA0..7 | — (DATA8..15 untouched) |
| TMP0 (IC26/IC27), TMP1 (IC28/IC29) | `-TMP-REG-RD0/1` | DATA0..15 | — |
| register cards IC35 + IC36 | `-REG-FUNC-RD` selecting the card (straight) | DATA0..15 = ADATA0..15; a byte whose read buffer is not enabled reads the pull-ups ($FF) | — |
| register cards IC37 (swap) | `-REG-FUNC-RD` + `-HL-SWAP` | DATA0..7 = ADATA8..15 (the high byte) | DATA8..15 not driven |
| ALU IC10 + IC11 | `-ALU-FUNC` + `-AC-RD` | DATA0..7 = ACC | DATA8..15 = $FF (BDATA8..15 pull-ups RN2) |
| sequencer branch register IC13/IC21 | `-BRANCH-RD` | DATA0..15 | — |
| sequencer INT vector IC3/IC10 | `-INT-JMP` | DATA0..15 | — |
| I/O card: 16550, or IC3 (switches) | `-IO-RD` with the port and select bits | DATA0..7 | — |
| Mem Switch (74LS244s), Mem Register (74LS374s) | `-MEM-RD` + `-VMA` + `-BUS-EN` + address match | DATA0..7 | — |
| video IDT7134 right port | `-MEM-RD` + board select | DATA0..7 | — |

Loads from the bus: the ALU receives BDATA0..15 (IC10/IC11 without `-AC-RD`), the register cards receive ADATA (straight or
swapped), TMP0/1 take all 16 lines, the sequencer's IR / operand / branch / INT registers take **DATA0..7 only**
(their high bytes are loaded from the low byte in a second step), memory and the I/O latches take DATA0..7.

Three consequences:

- **A 16-bit word crosses in one step.** `-REG-RD-LO` together with `-REG-RD-HI` is one 16-bit transfer, not a bus
  fight (the mechanical pass's R2 assumed an 8-bit bus; corrected in the notes). MOVRR, the JSR/RET/BR PC loads and the
  TMP paths use this.
- **Byte order.** A word in memory is big-endian: STR writes the high byte at the address, the low byte at address+1;
  MVIW's immediate is high byte first; JSR pushes PC.hi at [SP] then PC.lo at [SP−1] (`register.c`, `branch.c`). Moving
  a high byte to or from an 8-bit source is what `-HL-SWAP` and the swap transceiver exist for.
- **Idle level.** The only passive elements on the data lines are the memory card's pull-down networks RN5/RN6 (value
  blank in the design, datapath review M8) and, when plugged in, the bus tester's pull-ups RN1–RN4 (value blank,
  control-io 4.2). "Reading an undecoded block returns the last value left on the bus" (`docs/system/MACHINE.md`)
  suggests the pull-downs are high-value or absent. **To verify:** RN5/RN6 and RN1–RN4 values.

### 4.2 Address bus `ADDR0..15` (A3–A18)

Driven by exactly one source in the running machine: the index register named by `ADDR-REG-ID`, through its pair of
74LS244s, enabled by `-Rn-ADDRSEL` from IC38 whose enable is `-BUS-EN OR -VMA` (IC40) — so **the address bus is driven
only during a `-VMA` cycle and floats otherwise** (`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.2; datapath review M1). Because
the generator asserts `-VMA` in every step with `ADDR-REG-ID` defaulting to PC, in practice the PC (or the register an
instruction names) is on the address bus continuously. The memory card buffers it (IC8/IC9), replaces bits 12–15 with
1111 while FORCE-ROM is set (IC11 74LS157) and decodes the result; the raw ADDR15 also clocks the FORCE-ROM flip-flop
(ARCHITECTURE 7.2). No card drives the address bus in response to anything else; DMA does not exist.

### 4.3 Register-id fields `ADDR-REG-ID0..3`, `REG-RD-ID0..3`, `REG-LD-ID0..3` (C3–C6, B9–B12, B13–B16)

Three 4-bit register numbers. On the register cards bits 0–1 pick one of the four registers and bits 2–3 must match the
card's jumpers (J3 for the address decode, J1 for read, J2 for load; all three set to the same card number,
`register/eagle/v1.1` schematic, datapath review). Only values 0–7 occur: bit 3 is always 0 in the image.

Their drivers differ, and the difference matters for the bus tester: `ADDR-REG-ID` comes from a pipeline register
through IC18B; `REG-RD-ID`/`REG-LD-ID` come from either the pipeline (IC4) or the operand register (IC5) depending on
`-2-BYTE-OPERAND-SEL`, and since IC4 and IC5 have complementary enables **one of them is always driving**, `-BUS-EN` or
not (control-io review 1.1). The sequencer also reads `REG-LD-ID` back off the bus to decide whether a load targets
R0 (the N$53 gate: loads of R0 pass only when the branch-taken latch is set, ARCHITECTURE 4.3).

The older names on C3–C6 (`-ADDR-REG-RD0/LD0/RD1/LD1`, V3.0–V3.1) were the read/load strobes of the retired Address+TMP
card, which held two 16-bit address registers in 74373 latches; the index-register design replaced strobes by a
register number (`hardware/cards/address-tmp/README.md`). Review H-5 (sequencer IC11 gate B with G, A1..A4 grounded and
Y1..Y4 on `ADDR-REG-ID0..3` in both the Eagle schematic and the KiCad netlist) would mean a permanent low drive on these
four lines against IC18B; the machine runs PC-relative code, which cannot show it. **To verify:** scope C3 during a
single-stepped `PUSH` (steps 7–9): a clean high means the board differs from the drawing.

### 4.4 Memory and I/O strobes `-MEM-RD`, `-MEM-WR`, `-IO-RD`, `-IO-WR`, `-VMA` (B23–B26, C12)

- `-VMA` (valid memory address, added in V3.1) is the qualifier every memory-side card ANDs with its decode: on the
  memory card it gates the low-RAM chip select, the 74LS138 high-half decoder and the data transceiver; on the register
  cards it enables the address drive; on the video card it is the comparator's cascade input; on the bring-up cards it
  is NORed with `-BUS-EN` and the strobe. Its purpose (memory notes 1.1→1.2: "so ROM & HI Ram can only be selected
  with -VMA asserted") is defeated by the microcode's permanent assertion (datapath review M1).
- `-MEM-RD`: sets the memory card's transceiver direction and, doubly inverted, the RAM/ROM `-OE`. Memory data appears
  ~150–250 ns after address and strobe (28C64 in the path) — the "mem" constant 0.30 of a step in
  `tools/ucode_wavedrom.py` and the budget of review M-2.
- `-MEM-WR`: doubly inverted, it is the `-WE` of both 62256s **and** the 28C64 (no write protect: datapath review M2).
  A 62256 write is WE-controlled: data is taken at the rising edge, the address must not change while `-CS` and `-WE`
  are both low. The generator satisfies this with one set-up, one strobe, one hold step (`putBustoRegMem()`).
  `-MEM-RD` and `-MEM-WR` are never asserted together by any record (review section 4, rule R1) — except by an all-zero
  record (H-4).
- `-IO-RD` / `-IO-WR`: inverted by the I/O card's open-collector 7406 (IC8) into `IO-RD`/`IO-WR` with pull-ups RN2, then
  ANDed with the port select. Writers latch on the fast falling edge of the OC output = the **trailing** edge of the bus
  strobe; readers drive the bus while `-IO-RD` is low, but only after the slow RC rise of the OC output — the slowest
  edge in the machine (review M-3; INP gives it one set-up step).

### 4.5 Register control `-REG-FUNC-RD/LD`, `-REG-RD-LO/HI`, `-REG-LD-LO/HI`, `-REG-UP/DN`, `-HL-SWAP`

Explained from the register card's netlist in ARCHITECTURE 4.2–4.3; the bus-level summary:

| Line | On the register card | Timing |
|---|---|---|
| `-REG-FUNC-RD` + `REG-RD-ID` | opens the card's transceivers toward the bus (card select `-RDSEL`); a register is read only if a read strobe also enables its buffer | level; **alone it drives $FFFF** (M-1) |
| `-REG-RD-LO` / `-REG-RD-HI` | enable the low / high byte read buffer onto ADATA0..7 / ADATA8..15 | level; byte lanes |
| `-REG-FUNC-LD` + `REG-LD-ID` | card select `-LDSEL`: transceivers toward the card (`BUS-DIR` = 1) | level |
| `-REG-LD-LO` / `-REG-LD-HI` | 74LS192 LOAD of the byte (asynchronous, level-sensitive) | value at the **trailing** edge; data valid through the whole strobe step (`docs/system/waveforms/REG-LD.json`) |
| `-REG-UP` / `-REG-DN` | ORed with the register's `-Rn-RDSEL` into UP / DN | counts at the rising edge of that OR: the **trailing** edge of the strobe, or the moment the selection changes (R2 hazard) |
| `-HL-SWAP` | routes ADATA8..15 to/from DATA0..7 through IC37 instead of the straight pair | level; same-card moves cannot swap (R3) |

The two load lines are the odd ones out electrically: they leave the sequencer as plain 74LS04 outputs
(`NOT(N$53 AND LREG-LD-LO/HI)`) and are **not** tri-stated by `-BUS-EN` (control-io review 1.1). Two 2020 WaveDrom
diagrams document the intended sequences: `REG-LD` (`REG-LD-ID` valid → `-REG-FUNC-LD` → `-RX-LDSEL` → `-REG-LD-LO` pulse
with valid bus data) and `REG-RD` (`-BUS-EN`, `REG-RD-ID` → `-REG-FUNC-RD` → `-RX-RDSEL` → `-REG-RD-LO` → data out)
(`docs/system/waveforms/README.md`). The register notes' one rule: "Up or Down on rising edge, other line must be high"
(`register/eagle/v1.1/Notes.md`).

### 4.6 TMP strobes `-TMP-REG-RD0/LD0/RD1/LD1` (B27–B30)

Four lines for the two 16-bit temporaries on the memory card. Loads are **leading-edge** (74LS374 clocked through an
inverter, datapath review M3): the source must be on the bus in the step before; reads drive all 16 lines. TMP0 is the
programmer's TMP, TMP1 the microcode's scratch (`MICROCODE.md`).

### 4.7 ALU and accumulator lines `-ALU-FUNC`, `ALU0..3`, `-AC-LD-INV`, `-AC-RD`, `-AC-LD`, `-SR-LD`, `BR-COND` (C15–C24)

The ALU card is the bus's only datapath card that both listens to control lines and **drives one**: `BR-COND` (C24) is
the selected condition XOR `AC-LD-INV`, read by the sequencer under `BR-TEST`. Everything else is an input: `-ALU-FUNC`
opens the transceivers, `-AC-RD` turns them outward, `ALU0..3` select the function (or the condition, or the shift mode),
`-AC-LD` and `-SR-LD` are leading-edge clocks, `-AC-LD-INV` chooses the inverting input buffer and flips BR-COND
(ARCHITECTURE 3). The ALU V3.2 notes list the changes that made the direction logic right: "IC10 DIR driven from -AC-RD
instead of inverse of -AC-LD" and "IC6 pin 10 - -ac-ld or ac-ld - added jumper - should be ac-ld" (`alu/eagle/v3.2/Notes.md`;
JP1 and JP2 on the schematic). `-VMA` and `-HL-SWAP` reach the ALU's connector and go nowhere on the card.

### 4.8 I/O port lines `IOADDR0..3`, `-IO-ADDR-LD` (C7–C11)

A static 4-bit port number, decoded combinationally on the I/O card; `-IO-ADDR-LD` was intended to latch it and is
unconnected on I/O v1.1 (review L-2 counts the wasted steps). The `IO-ADDR-HL` header decides which half of the port
space the card occupies (ARCHITECTURE 9.1).

### 4.9 System lines `-RESET`, `-BUS-EN`, `-RUN`, `-INT`, `-INTA`, `IN`, `OUT` (C13, C14, C26–C30)

- `-RESET` (C30): a totem-pole LS04 output on the sequencer-logic card from the front-panel RESET/EXECUTE latch; there
  is no power-on reset (datapath review S1). Consumers and their polarities are consistent (S2): a preset on the memory
  card's FORCE-ROM flip-flop, a clear on the ALU's carry/shift flip-flops, a clear (through the 4077) on all sixteen
  74LS192s of each register card, the 16550's active-high reset and the 74LS273 clears on the I/O card, the 6845's
  `-RES`. Both ATmega cards keep their own local resets off the bus.
- `-BUS-EN` (C28): NOT(READY) from the sequencer-memory card, driven by an LS04 on the logic card. It is the output
  enable of the nine pipeline 374s and the two CADDR buffers and a gating term on every other card's selects, so
  during the ~54 s microcode load nothing is selected. What it does **not** silence: the seventeen lines listed in
  control-io review 1.1 (the `REG-*-ID` and `ADDR-REG-ID` buffers, `-REG-LD-LO/HI`, `-RESET`, `OUT`, `-BUS-EN` itself). The
  bus tester drives `-BUS-EN` push-pull against that LS04 (4.1 / `BACKLOG.md` "CPU off switch").
- `-RUN` (C29): defined but connected on no card.
- `-INT` (C13): open collector, one source (the UART through the INT0 jumper), pull-up RN2 on the I/O card; the PDF marks
  it "??? Open Collector". `-INTA` (C14) is pipelined and never asserted (ARCHITECTURE 8).
- `IN` (C26, PDF: "??? Open Collector"): actually a hard VCC/GND from the IN0 switch through the `INPUT0` jumper on the
  I/O card (control-io review); the ALU's mux input D5; the tester keeps it as an input.
- `OUT` (C27): the sequencer's SR latch (ON/OFF opcodes), an LED on the I/O card.

### 4.10 The bus tester

The Bus Test Card v1.1 (`hardware/cards/bus-tester/`) puts six MCP23017 expanders straight onto the connector: IC1
(0x20) = ADDR0..15, IC2 (0x21) = DATA0..15, IC3–IC6 (0x22–0x25) = every control pin B7..C30 in pin order
(`YACC_Common_header.h`: chips 2–5 in that table, "chip" numbering offset by one from the microcode table's; the control-io
review checked all 52 bus entries against the V3.2 pins, "only the IOADDRn/IO-ADDRn spelling differs"). Its firmware
`embedded/bus-tester/bus-driver` makes every table entry a push-pull output at boot with the address and data buses in
WRITE mode, leaving only `BR-COND`, `-INT` and `IN` as inputs (control-io 4.1, HIGH): with the logic card fitted there are
two totem-pole drivers on each of the seventeen always-driven lines, and an LS output high into an MCP23017 output low
exceeds the expander's 25 mA pin rating. That is why "the tester cannot load RAM with the logic card fitted"
(`BACKLOG.md`) and why the 2026-09-21 sequencer boots taken with the tester asserting `-BUS-EN` dumped zeros. The 2020
redesign (v3.1: latches with enables, soft bus-enable and reset) was routed but never ordered (`FABRICATED.md`).
The host side is `tools/busdrv.py` (`CMD:OPERAND#`, `>>` prompt, 19200 baud) and the Processing command sender.

---

## 5. Timing conventions

### 5.1 The step and the LS timing model

A microcode step is two clock periods of the sequencer's oscillator; the control lines change ~30 ns after the
pipeline clock edge, and everything else follows combinationally (`tools/ucode_wavedrom.py` `TIMING`: `pipe` 0.05,
`reg` 0.12 — the selected register on the address bus ~40 ns after the selects settle —, `mem` 0.30 — data valid
~150–250 ns after address and `-MEM-RD` —, `latch` 0.00). Gate delays quoted by the reviews are LS-TTL typicals from
`docs/datasheets/`. The model's known errors and the step-length exceptions (the `UCODE-COUNT-RESET` step is one clock,
step 0 three) are in `MICROCODE.md` sections 4 and 6.

### 5.2 Leading edge or trailing edge

The single most important rule for anyone writing microcode or reading a diagram (`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.6):

| Takes the value at the **leading** edge (the bus of the previous step) | Takes the value at the **trailing** edge (the bus of the strobe step) |
|---|---|
| IR (`LD-INS-REG`), operand register (`OPERAND-CLK`), branch register (`BRANCH-LD-*`), INT vector (`INT-LD-*`), TMP0/1 (`-TMP-REG-LD*`), accumulator and carry (`-AC-LD`), shift register and shift-out (`-SR-LD`) | index-register bytes (`-REG-LD-LO/HI`, level-sensitive LOAD), index-register counts (`-REG-UP/DN`, rising edge of OR(select, strobe)), RAM/EEPROM writes (`-MEM-WR` → `-WE` rising), I/O latches (`-IO-WR` trailing edge through the 7406) |
| The source must be valid **one step before** the strobe; the strobe step itself can already carry the next set-up (review L-3). | The source and the address must be stable **through the whole strobe step**; the generator adds one hold step after. |

Why the difference: the leading-edge group are 74LS374/74LS175/74LS74 clocked by the strobe (often through one
inverter), the trailing-edge group are level-controlled parts (74LS192 LOAD, SRAM `-WE`) or clocked by the *inverse* of
the strobe. `y1ucemu.c` `do_step()` is organised exactly this way — a "leading edge" block that uses `prev` (the
previous step's bus), then `compute()` for the current step, then a "trailing edge" block that uses `cur`.

### 5.3 The set-up / strobe / release convention

Because the microcode cannot sense when a card has finished, every transfer is written as three lines: put the source
and selects up, assert the strobe, release the strobe with the source still up, then release the source
(`main.c` `putBustoRegMem()`, `accumulator.c` `aluOp()`). This gives one full step (two clocks) of set-up before any
edge and one step of hold after it, which is enough for the LS delays and the 62256 at the clocks used so far. The
steps where only one step of memory access precedes a leading-edge latch (LDTI, LDIVR, LDT, the BRANCH-LD and INT-LD
steps) are the first to fail at a faster clock: ~230–320 ns of path per step puts the limit around 6 MHz with the 28C64
(review M-2). Nothing in the tree records the clock actually used (ARCHITECTURE 11).

### 5.4 Pull-ups, weak drives and floating lines

- The register cards' internal bus has 10 k pull-ups (RN1/RN2), the ALU's BDATA has 10 k pull-ups (RN1 on 0..7, RN2 on
  8..15). These define what a "read of nothing" returns: $FF on the byte whose read buffer is off, $FF on DATA8..15
  under `-AC-RD`, $FF on a register whose card is not fitted (`y1ucemu -R 1`). The model calls the register card's
  $FFFF under a bare `-REG-FUNC-RD` a **weak drive** (it is a real LS245 drive, but of a known constant) and counts
  it separately from fights.
- The backplane has no pull-ups. All control lines are 374 outputs with OC = `-BUS-EN`, so before READY and whenever
  the tester holds `-BUS-EN` high they float; LS inputs read a floating pin as high, which is the inactive level for
  every active-low strobe (that is why the memory and I/O cards sit quietly during the microcode load), but the
  active-high lines (`REG-*-ID`, `ADDR-REG-ID`, `IOADDR`, `ALU0..3`, `BR-COND`, `OUT`, `IN`) are undefined then and the
  CMOS inputs (the 4077 on the register cards, the 74HC parts on the video card) see mid-rail (datapath M5/S3,
  control-io 5.1, 1.8). A pull-up bank is "the usual answer" for a future backplane revision.
- The memory card's RN5/RN6 pull-downs on DATA0..15 and the tester's RN1–RN4 pull-ups on address and data have no
  recorded value (4.1).

### 5.5 What a bus fight is, and how the reviews counted them

Two LS totem-pole outputs driving one line to different levels: the low one sinks the high one's short-circuit
current (an LS244/374 high can source 40–225 mA into a low output, control-io 1.1), the line sits at a mid level that
inputs read as 0, and the parts heat. The reviews used three instruments, each with a different notion of "driver":

1. `tools/ucode_review.py` rule **R2**: two or more of `-AC-RD, -REG-RD-LO, -REG-RD-HI, -TMP-REG-RD0/1, -BRANCH-RD,
   -MEM-RD, -IO-RD` in one step. Counts 37 before the 2026-09-22 fixes, 3 after (all three MOVRR's `-REG-RD-LO` +
   `-REG-RD-HI`, which is a 16-bit transfer, not a fight). It misses the register card under `-REG-FUNC-RD` alone and the
   ALU under `-AC-RD` + `-ALU-FUNC` (notes section 6).
2. The hand review (`docs/isa/MICROCODE-REVIEW-NOTES.md`), from the netlists: found H-1 (PUSHR), H-2 (BRZ family), M-1
   (327 weak-drive steps), and H-4 (the all-zero records).
3. `software/ucemu/y1ucemu`: per step and per byte lane, every source that would be enabled by the word is a driver;
   two drivers with different values are a fight, counted per (opcode, step) pair, listed with `-w`, resolved by
   `-F and` (the AND of the drivers: the usual TTL outcome) or `-F src`. With the fixed image the compiler suite, the
   ISA differential test and the monitor from reset run with **0 fights over 6 million steps**; the weak-drive count on
   the status line is the M-1 population.

On the bench the same thing is a mid-level (~0.5–1.5 V) on a scope where a clean logic level is expected, and a VCC
ripple at fetch step 4 (review M-1 "Confirm"). The listed bench checks in priority order are section 7 of the notes:
H-5 (`ADDR-REG-ID0` during PUSH), H-2 (BRZ with AC = 0), H-1 (PUSHR read-back), M-1 (DATA0 during fetch step 4), H-4
(fetch $80), M-2/M-3 (raise the clock until BR or INP fails).

---

## 6. Electrical notes collected by the reviews

| Topic | Finding | Source |
|---|---|---|
| Logic families | LS throughout the sequencer, memory, ALU, register and I/O cards; ALS on a few gates (memory IC10 74ALS00, IC4/IC18 74ALS30, sequencer IC22/IC32 74ALS02); one CMOS 4077 on each register card driven by LS levels (R1, MED); 74HC160/HC4078 on the video card driven by LS (6.3, MED) | datapath and control-io reviews |
| Open collectors | I/O card 7406 for the strobes and `-INT` (pull-ups RN2, value unknown); video card 7416 outputs with no pull-ups (open, HIGH for the E one-shot) | control-io 3.2, 6.1 |
| Drive contention | seventeen sequencer lines vs the bus tester (1.1/4.1); memory-card low RAM vs the bring-up cards at $0000–$001F and vs FORCE-ROM after reset (M4/B1) | control-io, datapath |
| Reset | manual RS latch, no POR (S1); pipeline not reloaded during reset — a stale `-MEM-WR`/`-VMA` word can write the EEPROM (1.3) | datapath S1, control-io 1.3 |
| Decoupling | backplane: one electrolytic per slot (C1–C8, value blank) + C7/C8 bulk added in V2.0; cards carry their own 100 nF (the mechanical review flags only the EEPROM adaptor and the backplane's single IC-count as having none) | `DESIGN-REVIEW.md`, backplane README |
| Power entry | single wire-pad pair (5V, GND) on the backplane, PWR LED through R1 330 Ω; each slot's twelve power pins | backplane schematic; control-io 5 |

---

## 7. Mechanical

What the tree records:

- **Connector**: 96-pin DIN 41612, three rows a/b/c × 32 (`hardware/bus/backplane/README.md`; Eagle library parts
  `FABC96S` on the backplane and `FABC96R` on every card). **To verify:** the exact connector types behind the two
  Eagle names (the suffixes suggest a straight female part on the backplane and a right-angle male part on the cards,
  but no datasheet or order record is in the tree). The blank card has two 2.794 mm holes on the connector's centre
  line at ±44.46 mm (88.9 mm apart), the connector's own mounting holes (`Blank V3.1.brd`).
- **Backplane V2.0** (`yacc2buss.brd`, 2021-07/08, `FABRICATED.md`): a 304.8 × 304.8 mm (12 in) board with eight slots
  arranged radially — X1, X3, X8, X2 on the four sides and X4..X7 on the diagonals, each 144.78 mm from the centre and
  rotated in 45° steps (element positions in the `.brd`) — so the cards stand like spokes around the square. V1.1 (2016)
  had seven slots; V2.0 added X8 and the two bulk capacitors. The Build Notes for the V1.1 bus cards
  (`backplane/eagle/deprecated/v1.1/Build Notes.md`) give the check sequence: the three outermost pins of each row are
  GND and the next three VCC on every slot, test for shorts, bolt the connectors in before soldering, then verify with
  the bus-test Arduino program.
- **Card size**: the standard card is 178 mm wide (177.78 mm in the board files of the blank card, ALU, memory, I/O and
  index-register boards; the READMEs of the protocard and blank card say 178 × 114 mm); the sequencer-logic V2.1l is the
  lengthened 218 × 114 mm board (`hardware/cards/sequencer-logic/README.md`, `FABRICATED.md`); the sequencer-memory card
  is 114 × 152 mm and has no bus connector; the never-built bus tester v3.1 is 114 × 178 mm 4-layer. The Eagle
  dimension layer of the 178 mm cards spans 164 mm in the other axis, which is more than the 114 mm the READMEs quote —
  **To verify:** whether that outline includes the connector body / a keep-out or the cards are really 164 mm tall.
- **Card guides and spacing**: `hardware/mechanical/` holds card divider clips (`clip.skp`, `clip12.skp/.stl`) and a
  `divider.stl`; its README also names a switch template, spacers and layout specs that are not in the folder
  (MIGRATION.md: the `mech parts` folder was iCloud-evicted; five files came across). The slot geometry above implies a
  card every 45° rather than a linear pitch.
- **Bus jumpers**: the horizontal (V3.2, 231 × 115 mm, 4-layer) and vertical (V3.0, 76 × 114 mm) jumper boards were
  built for an older bus arrangement and are not fitted ("obsolete", Ken 2026-09-20; `docs/system/MACHINE.md`).
- **Fasteners**: the tree does not say what screws hold the connectors or whether they are metal or nylon
  (`hardware/mechanical/README.md` is a one-line index). **To verify:** connector screw size and material, card
  retention, and how the sequencer-memory card is mounted relative to the logic card (ribbon length).

---

## 8. Quick reference: who drives what, when

```
                     sequencer-logic pipeline (OC = -BUS-EN)            other drivers
 control (B7-B30,    -REG-FUNC-*, -REG-RD-*, -REG-UP/DN, -MEM-*,        -REG-LD-LO/HI  (LS04, always)
  C3-C25 except      -IO-*, -TMP-REG-*, ADDR-REG-ID (IC18B), IOADDR,    REG-RD/LD-ID   (IC4 or IC5, always)
  C13, C24)          -IO-ADDR-LD, -VMA, -ALU-FUNC, ALU0..3, -AC-*,      BR-COND        (ALU card)
                     -SR-LD, -HL-SWAP, -INTA                            -INT           (I/O card, OC)
 system              -BUS-EN (LS04 from READY), -RESET (LS04), OUT      IN (I/O switch), -RUN (nobody)
 address A3-A18      the register named by ADDR-REG-ID, while -VMA
 data A19-B6         memory (0..7) | TMP0/1 (0..15) | register card (0..15, or hi->0..7 with -HL-SWAP)
                     | ALU (ACC on 0..7, $FF on 8..15) | branch reg / INT vector (0..15) | I/O (0..7)
```

One driver per lane per step is the whole discipline; `MICROCODE.md` section 8 tells what happened when it was broken.
