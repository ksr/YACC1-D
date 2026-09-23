# Index Registers card (1.1) — theory of operation

Four 16-bit up/down-counting registers per card, two identical cards in the machine (R0..R3 on card 0, R4..R7 on card 1,
chosen by jumper), each register able to drive the address bus, be loaded or read a byte at a time over the data bus,
and count up or down. R0 is the program counter, R1 the stack pointer, R2 the memory-indirect scratch register.

Written 2026-09-23 from the YACC1-D tree.

Sources: `hardware/cards/register/eagle/v1.1/Index Registers - 1.1.sch` (parsed with Python's `xml.etree`; every net and
gate below comes from its `<part>`/`<net>/<pinref>` elements), `hardware/cards/register/README.md`, `eagle/v1.1/Notes.md`,
`eagle/deprecated/v1.0*/Notes.md`, `hardware/FABRICATED.md`, `hardware/PROVENANCE.md`, `hardware/NEWER-DESIGNS-vs-ACTIVE.txt`,
`hardware/DESIGN-REVIEW-NOTES-datapath.md` (register section R1–R3, S1, S2), `hardware/DESIGN-REVIEW-NOTES-control-io.md`
(1.2, the 74LS192 item), `docs/isa/MICROCODE-REVIEW-NOTES.md` (1.2, 1.6, H-1, M-1, M-4, L-6, L-9, section 4),
`firmware/microcode/yaccsignaldata2.h`, `firmware/microcode/ucode-generator2/{main.c,register.c,CodeGen.h}`,
`software/ucemu/y1ucemu.c`, `docs/system/MACHINE.md`, `docs/system/waveforms/`, `docs/system/connector/README.md`,
`BACKLOG.md`, `docs/history/general-notes/NOTES-Update from old project.md`, `tests/bus-tester-scripts/Index Register/`,
`tests/bus-tester-scripts/README.md`, `tests/assembler/{romcount,romdiag}`, `media/index register v1.1 top.jpeg`.

Eagle gate letters are used for the glue logic (IC1A = gate A of IC1). Net names `N$nn` are the schematic's own.

---

## 1. Purpose and place in the machine

The 2020 YACC1 replaced the gen-1 "address and TMP" latches (`docs/cards/address-tmp.md`) with a register file whose
members are **counters**: a 16-bit register that can increment or decrement on a strobe is a program counter, a stack
pointer and an auto-incrementing pointer at once, and the sequencer needs no adder to step through memory. Each card holds
four such registers; the sequencer names them with 4-bit fields on the bus — `ADDR-REG-ID` (which register drives the
address bus this step), `REG-RD-ID` (which one is read or counted), `REG-LD-ID` (which one is loaded) — and bits 2..3 of
each field select the card through three jumper headers, bits 0..1 the register within it.

```
    bus DATA0..15 <==IC35/IC36 74*245 (straight) / IC37 (byte swap DATA0..7 <-> ADATA8..15)==> ADATA0..15 (RN1/RN2 10k)
                        DIR = BUS-DIR (= load-selected), G from IC34 4077 + IC31C/D
                                              |
             +--------------------------------+--------------------------------+
             |  R0: IC3 IC4 IC5 IC6 (4 x 74*192/193, lo -> hi)  CLR = RESET     |   R1: IC9..IC12,  R2: IC19..IC22,
             |      read buffers IC7 (lo) IC8 (hi) -> ADATA                     |   R3: IC29 IC30 IC43 IC44
             |      address buffers IC41 (lo) IC42 (hi) -> ADDR0..15            |   (same structure)
             |      gates IC1 (UP/DN/LD), IC2 (RD-LO/RD-HI)                     |
             +-----------------------------------------------------------------+
    ADDR-REG-ID0..3 -> IC38 (74*139, G = -BUS-EN OR -VMA) -> J3 -> -Rn-ADDRSEL
    REG-RD-ID0..3   -> IC32A (G = -BUS-EN OR -REG-FUNC-RD) -> J1 -> -RDSEL -> IC33A -> -Rn-RDSEL
    REG-LD-ID0..3   -> IC32B (G = -BUS-EN OR -REG-FUNC-LD) -> J2 -> -LDSEL -> IC33B -> -Rn-LDSEL
    -REG-UP/-REG-DN, -REG-RD-LO/HI, -REG-LD-LO/HI, -HL-SWAP, -RESET
```

Two cards fabricated 2020-08-31 (`hardware/FABRICATED.md`), both in the machine since 2026-09-22 evening (card 1 was missing
during the first bring-up days — section 6). The generator hard-wires `PC` = 0, `SP` = 1, `IR` = 2 (`CodeGen.h`), so card 0
is indispensable and card 1 holds R4..R7, the general-purpose registers the monitor and compiler use (R7 = every string
pointer in the monitor, `MACHINE.md`; R3 = the compiler's accumulator register, `software/compiler`).

## 2. Bus signals

Direction is seen from this card. Pins are the DIN 41612 pins of X1 (`<net>` to `X1.-Bxx`).

| Pin | Signal | Dir | On this card |
|---|---|---|---|
| A3–A18 | ADDR0..15 | out | one register's outputs through its two 74*244 (IC41/IC42, IC17/IC18, IC27/IC28, IC49/IC50), enabled by `-Rn-ADDRSEL` |
| A19–A26, A27–A30, B3–B6 | DATA0..15 | in/out | IC35 (0..7), IC36 (8..15), IC37 (0..7 <-> ADATA8..15) |
| B7 | -REG-FUNC-RD | in | IC31A with `-BUS-EN` -> enable of the read/count card decoder IC32A |
| B8 | -REG-FUNC-LD | in | IC31B with `-BUS-EN` -> enable of the load card decoder IC32B |
| B9–B12 | REG-RD-ID0..3 | in | 0..1 -> IC33A (register), 2..3 -> IC32A (card, via J1) |
| B13–B16 | REG-LD-ID0..3 | in | 0..1 -> IC33B, 2..3 -> IC32B (via J2) |
| B17, B19 | -REG-RD-LO, -REG-RD-HI | in | byte-lane read enables: ORed with `-Rn-RDSEL` into the read buffers (IC2, IC26 gates) |
| B18, B20 | -REG-LD-LO, -REG-LD-HI | in | byte-lane load strobes: ORed with `-Rn-LDSEL` into the counters' `LD` (IC1C/D, IC15C/D, IC25C/D, IC47C/D). Already gated on the sequencer for R0 |
| B21, B22 | -REG-DN, -REG-UP | in | count strobes: ORed with `-Rn-RDSEL` into `DN`/`UP` of the low counter (IC1A/B ...) |
| B23–B30 | memory / IO / TMP strobes | – | connector only |
| C3–C6 | ADDR-REG-ID0..3 | in | 0..1 -> IC38A (register), 2..3 -> IC38B (card, via J3). Bus V3.2 names; the card was drawn against the June-2020 V3 PDF but re-saved with the V3.2 nets (`docs/system/connector/README.md`) |
| C7–C11 | IOADDR0..3, -IO-ADDR-LD | – | connector only |
| C12 | -VMA | in | IC40A with `-BUS-EN`: the address buffers drive only while `-VMA` is asserted |
| C13–C24 | interrupt, ALU, AC, SR, BR-COND | – | connector only |
| C25 | -HL-SWAP | in | IC34C (`N$41` = NOT -HL-SWAP) and IC31D: selects the byte-swap transceiver IC37 instead of IC35/IC36 |
| C26, C27, C29 | IN, OUT, -RUN | – | connector only |
| C28 | -BUS-EN | in | qualifies all three decoders (IC31A/B, IC40A) |
| C30 | -RESET | in | IC34A: `RESET` = XNOR(GND, -RESET) = NOT -RESET -> `CLR` of all sixteen counters (active high) |
| A2/B2/C2, A31/B31/C31; A1/B1/C1, A32/B32/C32 | VCC; GND | in | 47 x 100 nF C1–C47; PWR LED through R1 (330) |

How the sequencer uses them (`main.c`): `setAddrId(reg)`, `setRdId(reg)`, `setLdId(reg)` write the same 4-bit number to
all three fields (`ADDR-REG-ID`, `REG-RD-ID`, `REG-LD-ID`); `-VMA` and `ADDR-REG-ID` = PC are set in every line by
`initCurrentLine()`; `incrementReg()` = one line with `-REG-FUNC-RD` + ID + `-REG-UP`, then a line clearing both;
`decrementReg()` = a select-only line, then `-REG-DN`, then the clear; `MVIB`/`MVIW` (`register.c`) = source on the bus, then
`-REG-FUNC-LD` + ID, then `REG-LD-LO` (or HI) for one line, release, release `-REG-FUNC-LD`. The microcode-level emulator
(`y1ucemu.c compute()` and the trailing-edge block of `do_step()`) models the card as described in section 3 including the
`-R 1` case of an absent card 1.

## 3. Schematic walkthrough

Eight sheets: 1–4 one register each (R0..R3), 5 the address-enable gate and pull-ups, 6 the decoders and jumpers, 7 the
transceivers and the 4077, 8 the connector.

### 3.1 Sheet 6 — card and register selection

Three decoders, one per bus field, each a 74*139 half with its enable formed by `-BUS-EN` and the function line:

| Field | Enable | Card decode (bits 2..3) | Jumper | Register decode (bits 0..1) | Outputs |
|---|---|---|---|---|---|
| REG-RD-ID | IC31A `N$19` = `-BUS-EN` OR `-REG-FUNC-RD` | IC32A: Y0 = `-RRD0`, Y1 = `N$43`, Y2 = `N$46`, Y3 = `N$47` | J1 (2x4): pins 1/3/5/7 = Y0..Y3, pins 2/4/6/8 = `-RDSEL` | IC33A (`G` = `-RDSEL`) | `-R0-RDSEL` .. `-R3-RDSEL` |
| REG-LD-ID | IC31B `N$24` = `-BUS-EN` OR `-REG-FUNC-LD` | IC32B: Y0 = `-RLD0`, Y1..Y3 = `N$48..N$50` | J2 | IC33B (`G` = `-LDSEL`) | `-R0-LDSEL` .. `-R3-LDSEL` |
| ADDR-REG-ID | IC40A `N$45` = `-BUS-EN` OR `-VMA` | IC38B: Y0 = `-ARD0`, Y1..Y3 = `N$51..N$53` | J3 | IC38A (`G` = `-ADDRSEL`) | `-R0-ADDRSEL` .. `-R3-ADDRSEL` |

A jumper across pins 1–2 of a header makes the card answer to ID2..3 = 00 (R0..R3), across 3–4 to 01 (R4..R7), 5–6 to
10 (R8..R11), 7–8 to 11 (R12..R15). The three headers of one card must carry the same code, because the microcode sends the
same number in all three fields (section 2). Bits 2..3 exist for four cards; the machine has two (`MACHINE.md`: "selected by
ADDR-REG-ID2..3 via each card's J3", Ken 2026-09-20). The gen-1 note "Arrange so board select can either be driven from
unused 1 to become 3rd addr-reg signal" became this scheme (`NOTES-Update from old project.md`).

Note the asymmetry the review relies on: **reads and counts share one select** (`-Rn-RDSEL` from `-REG-FUNC-RD` + REG-RD-ID),
loads have their own (`-Rn-LDSEL`), and the address drive has its own (`-Rn-ADDRSEL` from `-VMA`, not from any function line).
So a register can be on the address bus while another is being read or loaded, and the PC can drive the address of the
byte being fetched while it is itself loaded at the end of a branch.

### 3.2 Sheets 1–4 — one register (R0 shown; R1..R3 are identical up to part numbers)

- **Counters**: IC3 (bits 0..3), IC4 (4..7), IC5 (8..11), IC6 (12..15), drawn 74*192 (BCD), fitted **SN74HC193N** (binary,
  `media/index register v1.1 top.jpeg`, all sixteen readable) — see 4.3. Parallel inputs `A..D` = `ADATA0..15`; `CLR` = `RESET`
  (active high, from IC34A); `UP` chain: IC3 `UP` = `N$17`, `CO` = `N$11` -> IC4 `UP`, IC4 `CO` = `N$13` -> IC5, IC5 `CO` = `N$15` ->
  IC6 (IC6's `CO` unconnected); `DN` chain: IC3 `DN` = `N$18`, `BO` = `N$10` -> IC4 `DN`, `N$12` -> IC5, `N$14` -> IC6.
- **Count gates** IC1 (74*32): A `N$17` = `-R0-RDSEL` OR `-REG-UP` -> `UP`; B `N$18` = `-R0-RDSEL` OR `-REG-DN` -> `DN`. A
  74x192/193 counts on the **rising** edge of `UP` (or `DN`) while the other input is high; the OR output idles high, falls
  when both the register is selected and the strobe is low, and rises again when *either* goes away — that rising edge is
  the count. The gen-1 note preserved in `Notes.md` says it: "Up or Down on rising edge other line must be high".
- **Load gates** IC1 (continued): C `N$16` = `-R0-LDSEL` OR `-REG-LD-LO` -> `LD` of IC3 and IC4; D `N$22` = `-R0-LDSEL` OR
  `-REG-LD-HI` -> `LD` of IC5 and IC6. `LD` on these counters is asynchronous and level-sensitive: while it is low the outputs
  follow `ADATA`, and the value present at its rising edge stays. The two strobes are byte lanes: a 16-bit load asserts both.
- **Read buffers** IC7 (74*244, `G` = `N$20` = IC2A = `-R0-RDSEL` OR `-REG-RD-LO`): counter outputs `N$115..N$122` (bits
  0..7) -> `ADATA0..7`; IC8 (`G` = `N$21` = IC2B with `-REG-RD-HI`): `N$123..N$130` -> `ADATA8..15`. Again byte lanes: with only
  `-REG-RD-LO` asserted, `ADATA8..15` stays at RN2's $FF.
- **Address buffers** IC41 (bits 0..7) and IC42 (8..15), 74*244 with `G` = `-R0-ADDRSEL` -> `ADDR0..15` directly.

R1 = IC9..IC12 (counters), IC13/IC14 (read, `N$25/N$26` from IC2C/D), IC17/IC18 (address), IC15 (gates); R2 = IC19..IC22,
IC23/IC24 (`N$67/N$68` from IC26A/B), IC27/IC28, IC25; R3 = IC29, IC30, IC43, IC44, IC45/IC46 (`N$95/N$96` from IC26C/D),
IC49/IC50, IC47. There is no IC16, IC39 or IC48.

### 3.3 Sheet 7 — the bus transceivers and the 4077

IC34 is a CD4077-class quad XNOR (Eagle library `40xx`, value 4077N; `Notes.md` 1.0: "IC38 switched to 4077 pin compatible
with 74266" — renumbered IC34 in 1.1). Its four gates, all with one input tied or used as an inverter:

| Gate | Inputs | Output | Meaning |
|---|---|---|---|
| A | GND, -RESET | `RESET` | = NOT -RESET: the counters' active-high CLR |
| B | GND, -LDSEL | `BUS-DIR` | = NOT -LDSEL: high (A -> B, bus -> ADATA) when this card is load-selected, low (ADATA -> bus) otherwise |
| C | GND, -HL-SWAP | `N$41` | = NOT -HL-SWAP = "swap requested" |
| D | -RDSEL, -LDSEL | `N$42` | 1 when both or neither select this card, 0 when exactly one does |

IC31C: `N$1` = `N$41` OR `N$42` = enable (active low) of IC35 (DATA0..7 <-> ADATA0..7) and IC36 (DATA8..15 <-> ADATA8..15).
IC31D: `N$37` = `N$42` OR `-HL-SWAP` = enable of IC37 (DATA0..7 <-> ADATA8..15). All three have `DIR` = `BUS-DIR`.

So the straight path is open when exactly one of read/load selects this card and no swap is asked; the swap path when
exactly one selects it and `-HL-SWAP` is low; when both select it (MOVRR between two registers of one card) all three close
and the copy runs on `ADATA` inside the card; when neither, the card is off the bus. This answers the "1.2" question in
`Notes.md` ("Is bus direction correct, should it be based on -rd-sel"): the review traced all four cases and found the
design correct as drawn (`DESIGN-REVIEW-NOTES-datapath.md`, "checked, no issue").

`-HL-SWAP` is how a byte reaches or leaves the **high** half over the 8-bit-wide sources: MVRHA (high byte -> AC on DATA0..7),
MVARH and MVIW's first byte (DATA0..7 -> the high byte), JSR/PUSHR pushing PC.hi. Three consequences documented in the reviews:
a same-card register-to-register move cannot swap (R3, a constraint, unused); reading with `-REG-RD-HI` and `-HL-SWAP` puts the
high byte on DATA0..7 and leaves the low byte inside the card; and — the important one — **the transceivers open on the
selects alone**: a step with `-REG-FUNC-RD` and a matching ID but no read strobe drives `ADATA` = the pull-ups = **$FFFF onto
DATA0..15** through two 74*245 (M-1: every increment step in every fetch does this, 327 steps, overlapping `-MEM-RD`; H-1 was
this with PC.hi and SP through the swap path during PUSHR's stack writes).

### 3.4 Sheet 5 — the address-enable gate and the pull-ups

IC40A `N$45` = `-BUS-EN` OR `-VMA` (IC40B/C/D grounded spares): the address buffers of the whole card are enabled only in a
`-VMA` cycle. The generator asserts `-VMA` in every line ("Hack prevent ROM mapping from triggering", `main.c:103`), so in
practice the selected register is always on the address bus and the memory card's FORCE-ROM race (its M1) never sees a
floating ADDR15. RN1 (ADATA0..7) and RN2 (ADATA8..15), 8 x 10k to VCC, define the internal bus and the $FF of an unread lane.

### 3.5 Sheet 8 — the connector

X1, DIN 41612 FABC96R, pinned as in section 2 (net names IOADDR0..3 on C7..C10, the V3.2 spelling).

## 4. Timing and the review findings that concern this card

Latch edges (`MICROCODE-REVIEW-NOTES.md` 1.2 and 1.6; the 2020 diagrams `docs/system/waveforms/REG-LD.svg` and `REG-RD.svg`
show the same):

| Action | Strobe | Takes effect at | Data / select must be |
|---|---|---|---|
| Load a byte lane | -REG-LD-LO / -REG-LD-HI with -REG-FUNC-LD + ID | trailing edge (rising edge of the OR output, level-sensitive load) | ADATA stable through the whole strobe step: the source is asserted one line before and held one line after (`register.c`, `branch.c`) |
| Count | -REG-UP / -REG-DN with -REG-FUNC-RD + ID | trailing edge — or the moment the select goes away while the strobe is still low | the select must not change while the strobe is low |
| Read | -REG-RD-LO / -REG-RD-HI with -REG-FUNC-RD + ID | level: the 244 + 245 path, ~75–100 ns with the 4077 in the enable chain | – |
| Drive the address | ADDR-REG-ID with -VMA | level, ~75 ns after -VMA (LS32 + two 139 halves + 244 enable, datapath review M1) | – |

Findings and status on 2026-09-23:

| Finding | On this card | Status |
|---|---|---|
| H-1 PUSHR (microcode) | the record left `-REG-FUNC-RD`, `-REG-RD-HI`/`-REG-RD-LO` and `-HL-SWAP` on after `-2-BYTE-OPERAND-SEL` was released, so this card drove PC.hi (swap path) and then SP (both lanes) onto DATA while TMP1 drove the byte to be written: the pushed word was corrupted (the emulator: PUSHR $ABCD pushed $21CC) | **fixed in the generator 2026-09-22**, verified on `software/ucemu`, EEPROM reloaded; bench check pending (`tests/ucemu/isa.asm` on the machine) |
| M-1: $FFFF on the bus in every increment step | 3.3: `-REG-FUNC-RD` without a read strobe opens IC35/IC36 with ADATA = pull-ups; 327 steps overlap `-MEM-RD` (a sustained short between the memory card's 245 and these) | **open**, functionally harmless (nothing latches in those steps); the fix is in the microcode (release `-MEM-RD` before `-REG-UP`) |
| M-4: source register changed while its read strobe stays on (PUSHR 17->18, STR 21->22) | same-card 139 outputs switching: a few ns of overlap | symptom of H-1/M-1, not a card fault |
| R2: count strobe = OR(select, strobe) counts a deselected register on an ID change | 3.2: if `-REG-UP` is low and the decoder deselects the register, the OR output rises and the register counts | **latent**: `incrementReg()` has no select-only set-up line; the review scanned all 218 records — no case today; the author's own comment at `main.c:202` flags it |
| R1: CD4077 driven by LS levels, ~100 ns in the enable/direction path | 3.3: IC34 inputs `-RESET` and `-HL-SWAP` come from the sequencer (74HC parts on the built logic card: rail-to-rail, moot), `-RDSEL`/`-LDSEL` come from IC32 — which the photo shows as a **74LS139N** (the other two 139s are SN74HC139N): LS VOH 2.7 V minimum against the 4077's 3.5 V VIH | **open** (MED): works on these parts; a meter on IC34 pins 6, 12, 13 when inactive settles it (**To verify**) |
| R3: no same-card swap | 3.3 | constraint, unused |
| L-6 (microcode): loads of R0 gated by the sequencer's branch-taken latch | the `-REG-LD-LO/HI` this card receives are already gated (`docs/cards/sequencer-logic.md` 3.4) | design behaviour; documented |
| L-9: R2 is a hidden scratch register | LDA/STA/LDT/STT/LDR/STR load the operand address into R2 and leave it (+2 for LDR/STR) | documented |
| S1: no power-on reset | the counters are undefined until `-RESET` (the sequencer's front-panel latch) is asserted once | **open** (machine-level) |
| Review 1.2 (control-io): 74LS192 in schematic and BOM (16 per card) | decade counters would make every register count in BCD | **resolved by the photo**: SN74HC193N fitted. Design files and BOM say 74LS192N — correct before any rebuild. **To verify:** on both cards in hand |
| 2026-09-22 bench: absent card 1 reads $FF | a read of R4..R7 with only card 0 fitted enables no transceiver, DATA stays at the memory card's / ALU's idle level, the ALU latched $FF; loads and counts to those registers vanish | explained; card 1 fitted 2026-09-22 evening; `y1ucemu -R 1` reproduces it |

### 4.3 74HC and 74LS mixed — what the photo shows

`media/index register v1.1 top.jpeg`: sixteen SN74HC193N counters, SN74HC244N read/address buffers, SN74HC245N transceivers,
SN74HC139N at IC33 and IC38 but 74LS139N (date code 7939) at IC32, and a mix of HD74LS32P / SN74LS32N and SN74HC32N for the
OR gates (IC1, IC26 are LS; IC31, IC40 and others HC). The 4077's marking is not readable in the photo. The schematic says
`74*xxN`, the BOM 74LS192N etc. Consequences: the 193 makes the design binary as required; the LS139 at IC32 is the one
part that still drives the CD4077 with LS levels (R1); LS gates ORing HC outputs are fine. **To verify:** the markings on
the second card (only one card was photographed) and the 4077's part.

## 5. Jumpers, headers, LEDs, connectors — settings in the machine

| Item | Function | Card 0 (R0..R3) | Card 1 (R4..R7) |
|---|---|---|---|
| J1 (2x4, silk `0 RD 3`) | read/count card select: 1–2 = code 0, 3–4 = 1, 5–6 = 2, 7–8 = 3 | 1–2 | 3–4 |
| J2 (2x4, silk `0 LD 3`) | load card select, same coding | 1–2 | 3–4 |
| J3 (2x4, silk `0 AD 3`) | address card select, same coding | 1–2 | 3–4 |
| PWR LED | R1 330 | – | – |
| X1 | DIN 41612 | any slot | any slot |

`docs/system/MACHINE.md` (Ken 2026-09-20): "two cards: R0–R3 and R4–R7, selected by ADDR-REG-ID2..3 via each card's J3".
The pin numbering of the coding above is from the schematic (J1 pin 1 = IC32A Y0); the silk prints `0` and `3` at the header
ends. **To verify:** the cap positions on both cards against this table (all three headers of a card must agree).

## 6. Bring-up and test

**How the card was proven.**

- 2020-08: the two WaveDrom diagrams `docs/system/waveforms/REG-LD.json` / `REG-RD.json` were drawn for this card (load:
  `-REG-FUNC-LD`, REG-LD-ID, `-REG-LD-LO`, data; read: `-BUS-EN`, REG-RD-ID, `-REG-FUNC-RD`, `-REG-RD-LO`, data out).
- 2020-10-09: `tests/bus-tester-scripts/Index Register/commands-1 copy.txt` (372 lines): reset; load $4321 into R0 with
  `-REG-FUNC-LD` + `-REG-LD-LO` + `-REG-LD-HI`; read it back (`RD-DATABUS:0#4321!`); `-REG-DN` -> $4320; two `-REG-UP` -> $4322;
  `-REG-UP` -> $4323; three `-REG-DN` -> $4320; read the low lane only (`RD-DATABUS-L:0#20!`), the high lane (`#43!`), then
  `-HL-SWAP` and read the low lines (`#43!`: the high byte arrives swapped); then a `WAIT` and the next register. The script
  is in the 2020 names and runs through `tools/busdrv.py` or the Processing sender. It exercises exactly sections 3.2 and 3.3.
- `tests/bus-tester-scripts/Gen Test Vectors/` generates register scripts for the **2016** card (REG-FUNC-LD, REG-BRD-LD-ID,
  WDATA/RDATAL): not usable on this card until rewritten (`BACKLOG.md`).
- 2026-09-21: `tests/assembler/ledcount` — the PC counting through 10 bytes and `BR` reloading it, on the function-generator
  clock (PC only: card 0).
- 2026-09-22: `tests/assembler/romcount` first build kept its count in R6 and its delay in R7; on the bench it mirrored the
  switches and then lit every LED. `tests/assembler/romdiag` — a staged check paced by the input switch — read $FF at
  stage 2 (`MVIW R3,2011H / MVRHA R3`: expected $20) on its first run and thereby found the cause: the bring-up machine
  had **one register card**. A read of an absent register leaves the bus to its pull-ups ($FF), loads and counts are lost,
  so the count showed $FF and the delay loop never ended. romdiag's stage 9 (`MVIW R7,2011H / MVRHA R7` = $20 with two
  cards, $FF with one) is now the "is card 1 fitted" test. Card 1 was fitted the same evening; `tests/assembler/romcount`
  (rebuilt to use R3 and TMP) then ran overnight into 2026-09-23 on the LEDs/TIL311s without a fault (`MACHINE.md`).
  `y1ucemu -R 1` models the missing card (`software/ucemu/y1ucemu.c`, `REG_PRESENT`).
- romdiag stages that test this card: 2 (MVRHA = read high lane through the swap path), 3 (MVRLA = low lane), 4 (`MVIW
  R3,0400H / DECR R3 / MVRHA R3` = $03: a 16-bit load and a borrow ripple through IC3->IC4->IC5), 9 (card 1), 10/11 (a
  $2000-turn DECR loop, i.e. 8,192 counts with borrows across all four chips).

**If it misbehaves — what to measure.**

1. Nothing fetches: `-Rn-ADDRSEL` (IC38A outputs) — exactly one low while `-VMA` is low; if none, J3 coding or `N$45`
   (IC40A) high because `-BUS-EN` is high (the sequencer-memory card not READY).
2. A register reads $FF: J1 coding (the card is not answering to this ID), or `-REG-FUNC-RD` not reaching IC31A; with the
   bus tester, run the 2020 script and watch `RD-DATABUS`.
3. A register loads garbage: the source was not stable through the strobe (level-sensitive `LD`) — with the tester, change
   the data while `-REG-LD-LO` is low and see the last value stick; on the machine, the fetch address on ADDR0..15 after a
   branch shows where the PC went (the H-2 check).
4. Counts are off by one: R2 (a deselect while the strobe is low) — scope `N$17` (IC1A output) for a second rising edge;
   or a stuck carry between chips (`N$11`, `N$13`, `N$15`).
5. Reset does not clear the registers: `RESET` (IC34A output) must reach ~5 V when `-RESET` is low; if it sits at 2–3 V
   the 4077's threshold is the problem (R1).
6. Bus fights: a mid-rail level on DATA0..7 during fetch step 4 (M-1) is expected; one during a register *load* is not
   — check `N$42`/`N$1` (IC34D/IC31C): both RDSEL and LDSEL on this card should close the transceivers.
7. Two cards answering at once (both J-headers coded the same): every read gives an AND of two registers — check the cap
   positions.

## 7. Revision history and what the next revision should change

| Revision | Date (PROVENANCE) | What | Source |
|---|---|---|---|
| gen-1 REGISTER-PROD-V1.2 | 2016 | a different card: data registers with an address-latch section, "REG-BRD-LD-ID" selection | `archive/gen1-2015-2018/`, `tests/bus-tester-scripts/Gen Test Vectors/` |
| 1.0 | 2020-06-18 | the first 2020 index-register card; "-IN and -OUT converted to IN and OUT, neither used"; "IC38 switched to 4077 pin compatible with 74266"; two fab variants, one "no address" (without the address-bus section) | `eagle/deprecated/v1.0/`, `v1.0-no-address/`, their `Notes.md` |
| 1.1 | 2020-08-31 | the built card ("Version 1.1 to production"): the 1.0 changes above carried in, Bus V3 June-2020 names, later re-saved with the V3.2 nets; "Big redesign - Card no longer has address bus section" refers to the gen-1 register card being replaced by this one plus the (retired) address card | `eagle/v1.1/Notes.md`, `FABRICATED.md`; **two in the machine** |
| "1.2" folder | – | the 1.1 files renamed plus one note ("is bus direction correct, should it be based on -rd-sel") — answered by the 2026-09-21 review: correct as drawn; folded in 2026-09-20 (`NEWER-DESIGNS-vs-ACTIVE.txt`: 0 differences) | README |

**A 1.2 design should** (from the reviews and `BACKLOG.md`):

1. Qualify the count inputs so that only the strobe's own edge counts: e.g. latch `-REG-UP/-REG-DN` with the select, or
   gate the OR with a flip-flop clocked by the strobe (R2).
2. Replace the CD4077 with a 74HC86/74HC266-class part or 74HCT logic so that every input is TTL-compatible and the 100 ns
   drops out of the enable path (R1); keep the XNOR trick (it is neat) but on a fast part.
3. Open the transceivers only when a read strobe (or a load) is actually asserted, not on the select alone (M-1, H-1's
   enabler) — one more OR term per enable.
4. Correct the design files and BOM to 74HC193 (binary) and the fitted logic families.
5. Consider a "card present" pull-down or a status LED per card: the 2026-09-22 evening was spent discovering an absent
   card from $FF reads.
6. The `BACKLOG.md` note "should TMP registers move to the ALU" (memory v1.3 notes) is about the memory card, but if a
   register-file revision is made, a same-card swap path (R3) and a 16-bit read strobe would simplify the microcode.

Related documents: `docs/cards/sequencer-logic.md` (where the ID fields and strobes come from, the R0 load gate),
`docs/cards/address-tmp.md` (what this card replaced), `docs/cards/memory.md` (TMP registers and the FORCE-ROM race that
depends on this card's address timing), `docs/system/waveforms/`.
