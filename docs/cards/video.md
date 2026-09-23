# Video card V1.0 / v1.1 — theory of operation

A memory-mapped alphanumeric display: an MC6845 CRTC reads a dual-port RAM that the CPU writes through the bus, a
character-generator EPROM and a shift register turn the characters into dots, and the result leaves the card as
separate video/HS/VS on a DB9 and as a sync signal on an RCA jack. Built once, in the machine for bring-up **without
the 6845 fitted**; the RAM half is proven, the CRTC half is not.

Written 2026-09-23 from the YACC1-D tree.

Sources: `hardware/cards/video/eagle/v1.0-fusion-export-2026-09-18/Video_1.0.sch` and `.brd` (the built card, as
exported from Fusion 360; parts and nets parsed from the Eagle XML), `hardware/cards/video/kicad/v1.1/README.md` (the
design master since 2026-09-21), `hardware/cards/video/kicad/v1.0-fusion-export-2026-09-18/README.md` (the netlist
proof that found the rail fault), `hardware/cards/video/README.md`, `hardware/cards/video/docs/fix-6845-register-
select.md`, `hardware/DESIGN-REVIEW.md`, `hardware/DESIGN-REVIEW-NOTES-control-io.md` section 6, `docs/system/
MACHINE.md`, `docs/system/OS-PLAN.md` (decisions 2 and 4), `tests/video/README.md`, `tests/video/video_ram_test.py`,
`tests/video/hold_address.py`, `tests/memory/memory_full_test.py` and `full-run-2026-09-21.log`, `tools/alias_min.py`,
`BACKLOG.md`, `hardware/FABRICATED.md`.

## 1. Purpose and place in the machine

The memory card leaves the $D000 4K block undecoded (its block jumper is absent, `docs/cards/memory.md` section 3.2)
so that this card can answer there. A 4-bit comparator on the card matches ADDR12..15 against four jumpers, and
while the match holds and -VMA is asserted the card owns the bus cycle: with ADDR11 low it is the CPU-side port of
an IDT7134 dual-port RAM (2K reachable: A11 of the chip is grounded on that port), with ADDR11 high it is the 6845's
register interface (and, at odd addresses, a jumper read-back latch). The CRTC-side port of the same RAM is scanned
by the 6845's MA0..11 continuously, so the CPU never has to wait for the display and the display never sees the CPU.

The video generator is the textbook 6845 chain: a crystal dot clock, a counter that makes one character clock every
few dots, a 2732 character generator addressed by the character code and the CRTC's row address, a 74LS166
parallel-to-serial shift register, a cursor/attribute XOR, and display-enable gating, all through 7416 open-collector
drivers to the connectors.

```
    bus ADDR12..15 --> IC18 74S85 <-- SV3 jumpers (RN2 pull-ups)  --BOARDSEL--+
    -VMA --IC20/F--> IC18 A=B_in                                              |
                                                                              v
    ADDR0..10 ------> IC15 IDT7134 right port  <-- -CER = NAND(BOARDSEL, /ADDR11)   [IC19/B]
    DATA0..7  <-----> (A11R = GND, -OER = -MEM-RD, R/-WR = -MEM-WR)
                          | left port (read only, always enabled)
                          | VADDR0..11 <---- IC17 MC6845 MA0..11      IC17: -CS = NAND(BOARDSEL, ADDR11./ADDR0)
                          v VDATA0..5,7                                     RS = ADDR0, R/-W = -MEM-WR, E = one-shot
    IC23 74LS174 (char code, CHARCLOCK) --> IC25 2732 char gen <-- RA0..2 (IC17)
                                                | O3..O7
    IC22 74LS175 (cursor^attr, DE pipeline)     v
                                          IC24 74LS166 shift (DOTCLOCK, load on CHARCLOCK) --QH--> IC26/B XOR --> IC19/D NAND DE --> IC27/A --R11--> DB9 pin 7
    Q2 crystal + IC20 --> IC21 74LS90 /2 --> SV4 --DOTCLOCK--> IC28 74HC160 --QC--> CRTCCLOCK (IC17 CLK)
                                                                 \--NAND(QA,QC)--> CHARCLOCK (and IC28 -CLR)
    IC17 HS, VS --> IC27/C, /B (wired-OR, R12) --> RCA U$3;  HS --> DB9 pin 8, VS --> DB9 pin 9
    JP1 (2x7) --> IC2 74LS373 --> DATA0..7 at odd addresses with ADDR11 high
```

## 2. Bus signals used

| Signal | Bus pin | Dir | What it does on this card |
|---|---|---|---|
| ADDR0 | A3 | in | RAM A0R; the 6845's RS (as built); one term of the latch/CRTC select (through IC27/D, open collector) |
| ADDR1..10 | A4..A13 | in | RAM A1R..A10R (ADDR1 is also the pickup point for the RS fix) |
| ADDR11 | A14 | in | RAM half (0) or CRTC/latch half (1): IC19/B, IC1/B, IC1/D, IC20/E |
| ADDR12..15 | A15..A18 | in | IC18 comparator B inputs: the block select |
| DATA0..7 | A19..A26 | bidir | RAM right-port I/O, 6845 D0..7, IC2 latch outputs. No bus buffer |
| -MEM-RD | B23 | in | RAM -OER; one input of the E one-shot XOR (IC26/C) |
| -MEM-WR | B24 | in | RAM R/-WR; the 6845's R/-W; the other XOR input |
| -VMA | C12 | in | inverted by IC20/F into the comparator's A=B cascade input: no match without a valid address |
| -RESET | C30 | in | the 6845's -RES |
| VCC / GND | power pins | power | see the +5V rail note in section 4: as built, half the card's supply net had no connector pin |
| C3..C6 | | — | carry Blank V3.1's stale names (-ADDR-REG-RD0/LD0/RD1/LD1); connector only, unused |

DATA8..15, -BUS-EN, the strobes of the register/ALU/TMP world and the I/O lines are connector-only nets.

## 3. Schematic walkthrough, IC by IC

Chip types from `Video_1.0.brd`: IC1 74ALS08, IC2 74LS373, IC15 `VRAM` (deviceset `7134P`, IDT7134 4K x 8 dual-port,
DIL48), IC17 `6845` (DIL40, socket empty), IC18 74S85, IC19 74LS00, IC20 74LS04, IC21 74LS90, IC22 74LS175, IC23
74LS174, IC24 74LS166, IC25 `CHARGEN` (deviceset `2732`, DIL24), IC26 74LS86, IC27 7416, IC28 74HC160 (from the
`74xx-eu` library — the one HC part on a card of LS), Q2 crystal HC49U-V (value empty), R1 10K, R8/R9/R10 1K, R11 33,
R12 270, RN2 RNX4 (RN-5), C1 "1", C16 10.0 µF electrolytic, C3/C17-C29 0.1 µF, PWR LED with R2 330, U$3 RCA, X2 DB9
(`F09`), JP1 2x7, SV3 2x4, SV4 1x3.

### 3.1 Board select: IC18 (74S85), SV3, RN2, IC20/F

IC18 compares A (jumpers) with B (ADDR15..12: B3 = ADDR15, B0 = ADDR12). SV3 pins 1/3/5/7 go to A3/A2/A1/A0 (nets
N$51..N$48) with RN2 pulling them up to +5V; pins 2/4/6/8 are GND. A fitted jumper makes that bit 0. The cascade
inputs are A<B = GND, A>B = GND and A=B = N$89 = IC20/F(-VMA) = VMA, so A=B_out (BOARDSEL) is high only when the four
bits match *and* -VMA is asserted. For $D000 the pattern is 1101: A1 is the only 0, so the only jumper is SV3 5-6
(README; MACHINE.md's memory-card table reserves $D000 for it).

### 3.2 The RAM: IC15 (IDT7134) and IC19/B, IC20/E

Right (CPU) port: -CER = N$52 = IC19/B = NAND(BOARDSEL, N$87), N$87 = IC20/E(ADDR11) = /ADDR11 — selected for the
lower 2K of the block. -OER = -MEM-RD, R/-WR = -MEM-WR, A0R..A10R = ADDR0..10, A11R = GND (so the CPU reaches 2K of
the 4K chip, at $D000-$D7FF as the nets are named). Left (CRTC) port: -CEL and -OEL grounded, R/-WL tied to the +5V
net (read only), A0L..A11L = VADDR0..11 from the 6845's MA0..11, I/O0L..7L = VDATA0..7. The chip contains the
arbitration; nothing on the card sequences the two ports.

### 3.3 The CRTC interface: IC17 (MC6845), IC1, IC19/A, IC27/D, IC2, JP1

- **Select.** N$5 = IC27/D(ADDR0) = /A0 (open collector, **no pull-up**: it reads high only because it floats);
  N$2 = IC1/D = ADDR11 AND /A0; N$91 = IC19/A = NAND(BOARDSEL, N$2) = the 6845's -CS. So the chip is selected at even
  addresses in the upper half of the block.
- **Register select.** RS = ADDR0 directly. Since -CS needs A0 = 0 and RS = A0, the chip is only ever selected with
  RS = 0: **the data register cannot be reached as built.** This is the finding in `docs/fix-6845-register-select.md`;
  the fix moves IC17 pin 24 from ADDR0 to ADDR1 (section 5).
- **Read/write and E.** R/-W = -MEM-WR (low = write, the 6845 convention). E = CLK net = IC1/A = N$1 AND N$4. N$1 =
  IC26/C = -MEM-RD XOR -MEM-WR, high while exactly one strobe is active — for *every* memory cycle in the machine,
  BOARDSEL is not a term. N$3 = IC27/F(N$1) (open collector) through R1 10K to N$4 with C1 to GND: when a strobe starts
  the 7416 pulls N$3 low and C1 discharges through R1; E is the AND of the strobe and the not-yet-discharged C1 — an RC
  one-shot that bounds the E pulse even under single-stepping. When the strobe ends the 7416 releases, but the only
  charging path for C1 is IC1's input (there is no pull-up on N$3). Review finding 6.1 (section 4).
- **-RES** = -RESET (active low, correct). **LPSTB** floats (6.5). MA12/13, RA3/4 unconnected.
- **The read-back latch IC2 (74LS373).** Its eight D inputs are JP1 pins 1, 2, 4, 6, 8, 10, 12, 14; LE is JP1 pin 13;
  JP1 pin 3 is VCC, pin 5 GND. Its outputs sit on DATA0..7 and its -OC is N$16 = IC27/E(N$6), N$6 = IC1/C = N$17 AND
  ADDR0, N$17 = IC1/B = BOARDSEL AND ADDR11: the latch drives the bus at every **odd** address of the upper half, read
  or write (6.4). With JP1 open the inputs float and the latch reads as $FF — which is what `memory_full_test.py`'s
  phase F2 saw ("$D800-$DFFF ... reads 00 FF after writing 77 / 88").

### 3.4 Dot clock and character clock: Q2, IC20, IC21, SV4, IC28, IC19/C, R10

IC20/A and IC20/B with R8/R9 (1K) and Q2 form a Pierce oscillator; IC20/C buffers it onto N$57, which goes to SV4
pin 1 and to IC21's CKA. IC21 (74LS90, R0/R9 inputs grounded) divides by two on QA; IC20/D re-buffers QA onto N$59 =
SV4 pin 3. SV4 pin 2 is DOTCLOCK: the jumper picks the crystal or half of it. Q2's value is empty in the design
(**To verify:** read the crystal).

IC28 (74HC160) counts DOTCLOCK with A..D grounded and LD/ENT/ENP on N$73 (R10 to +5V, also the CLR of IC22/IC23/IC24).
CHARCLOCK = IC19/C = NAND(QA, QC), low only while the count is 5 (0101); it is IC28's own asynchronous -CLR, so the
counter divides by five and CHARCLOCK is a runt as wide as the clear propagation (6.2). QC is also CRTCCLOCK = the
6845's CLK. CHARCLOCK clocks IC22 and IC23 and is the SH/-LD of IC24.

### 3.5 Character pipeline: IC23, IC25, IC24, IC22, IC26/A, IC26/B, IC19/D

IC23 (74LS174) latches the character code VDATA0..5 on CHARCLOCK (D1 = VDATA5 ... D6 = VDATA0) and its Q6..Q1 drive
IC25's A3..A8; A0..A2 are the 6845's RA0..2 (row within the glyph); A9..A11 are grounded — a 64-character set, 8
rows, in the low 512 bytes of the 2732 (-CE and -OE grounded). O3..O7 go to IC24's D..H; O0..O2 are unused; IC24's
A, B, C, SER and INH are grounded. IC24 shifts on DOTCLOCK and loads when SH/-LD (CHARCLOCK) is low at a DOTCLOCK
edge; QH is the dot stream.

IC22 (74LS175) is a two-stage delay for the attribute and display-enable so they line up with the shifted glyph: D1 =
N$75 = IC26/A = CURSOR XOR VDATA7 (bit 7 of the character byte is an inverse-video attribute; VDATA6 is unused), Q1
to D2, Q2 to IC26/B; D3 = DE from the 6845, Q3 to D4, Q4 to IC19/D. IC26/B XORs the dot with the attribute; IC19/D
NANDs that with delayed DE; IC27/A (open collector) drives the result through R11 (33 Ω) to DB9 pin 7 (video).

### 3.6 Sync outputs: IC27/B, IC27/C, R12, U$3, X2

HS goes to IC27/C and DB9 pin 8, VS to IC27/B and DB9 pin 9. The two 7416 outputs are wired-OR on N$85 with R12
(270 Ω) to +5V — the one 7416 net with a pull-up — and go to the RCA jack U$3 (a combined sync). DB9 pin 1 is GND.
The `archive/eagle-projects/` LM1881 sync-separator project the README mentions is the related composite-video
experiment, not part of this card.

### 3.7 Power

The design has two 5 V nets. `VCC` reaches the bus pins A2/B2/C2/A31/B31/C31, R2, JP1 pin 3 and the *implicit* power
pins of IC17-IC28 (Eagle supplies those from the VCC symbol). `+5V` feeds IC1, IC2, IC15 pin 2 (R/-WL), RN2, R10,
R12, C16 and every decoupling capacitor — and reaches no connector pin. The KiCad netlist proof
(`kicad/v1.0-fusion-export-2026-09-18/README.md`: "MISMATCH (115/117 nets)", the two rails listed) found it on
2026-09-20; on the bench IC1, IC2 and the jumper pull-ups had been running on phantom power through input clamp
diodes, which is what produced the write-through fault below. Ken joined the rails with a wire on 2026-09-21; the
v1.1 master folds `+5V` into `VCC` with a joining track (proof 116/116).

## 4. Timing and the design-review findings

Two timing chains matter. The **bus side** is the memory card's: BOARDSEL needs IC20/F + IC18 (a 74S85, fast) and
IC19/B before -CER is valid, which happens within the address set-up step the microcode gives every memory access.
The **video side** runs on DOTCLOCK: IC24 must reload once per character and the 6845 must see an E pulse of at
least 450 ns (280 ns for the faster grades, per the review) for each register access. Neither has been measured: no
6845 has been fitted and no crystal value is in the tree.

| ID | Severity | Finding | Status 2026-09-23 |
|---|---|---|---|
| README, `fix-6845-register-select.md` | HIGH (functional) | RS = A0 while -CS requires A0 = 0: the 6845 data register is unreachable; the JP1 read-back latch occupies the odd addresses, so simply dropping /A0 from the select would make a bus fight. Fix: RS to A1 — a bent pin 24 wired to IC15 pin 41 (ADDR1) or bus A4 | **Open, bench job first** (BACKLOG); designed into `kicad/v1.1` as "still to do". After the fix: even addresses select the CRTC, A1 picks address (0) or data (1) register, odd addresses read the latch |
| 6.1 | HIGH (untested) | the E one-shot's capacitor C1 has no charging path except IC1's input current (no pull-up on IC27 pin 12); at run speed memory strobes arrive every few µs, N$4 sits below threshold, E is short, ragged or absent — the CRTC's registers cannot be written even after the RS fix | Open; goes with the 7416 pull-ups. Confirm without a 6845: run any loop, scope IC1 pin 2 (stuck below ~1.5 V) and pin 3 |
| 6.2 | MED | CHARCLOCK is a ~30-60 ns self-clear runt used as the 74LS166's load: the load only happens if the runt is still low at the next DOTCLOCK edge, i.e. for dot clocks above ~16-20 MHz; slower crystals give a blank display. A synchronous-clear counter (74HC162) holds the state for a full period | Open |
| 6.3 | MED | 74HC160 inputs (CLK, -CLR) driven by 74LS outputs: LS VOH 2.7 V min against HC VIH 3.15 V — works on typical parts, not by specification. 74HCT160 or pull-ups | Open |
| 6.4 | LOW | IC2's enable has no -MEM-RD term: a *write* to an odd upper-half address turns the latch onto the bus against the writer. Software must never write there | Open; noted for the fix document |
| 6.5 | LOW | LPSTB floating (NMOS input): tie low | Open |
| README | MED | 7416 outputs (IC27) drive IC1, IC2, IC26 with no pull-ups; /A0 (N$5) only reads high because it floats | Open ("pull-ups on the 7416 outputs" in BACKLOG) — the second v1.1 change |
| README | HIGH | +5V rail unfed (section 3.7) | **Resolved on the bench 2026-09-21** (wire), fixed in the v1.1 design |
| README | HIGH | write-through fault of 2026-09-18: a write to block 0 or 9 landed in the video RAM regardless of BOARDSEL | **Resolved 2026-09-21**: cause was the unpowered rail; `tests/video/video_ram_test.py` 8/8, `tools/alias_min.py` clean |
| DESIGN-REVIEW.md (mechanical) | MED | open-collector nets N$5 (IC27 p8) and N$16 (IC27 p10) without pull-up | Same as the 7416 item |
| README / FABRICATED.md | LOW | inherits Blank V3.1's pre-V3.2 names on C3-C6 | Harmless (unused pins); start the next card from Blank V3.2 |
| Naming (this document) | doc | the README, the fix document and the reviews quote the CRTC at `$D400`/`$D402` and describe the block as "2K, low half RAM"; the netlist (ADDR11 = bus pin A14, IC18 compares only ADDR12..15, IC15 A11R grounded) reads as a **4K** block with RAM at $D000-$D7FF and the CRTC/latch half at $D800-$DFFF. `memory_status.py` ("VIDEO $D000-$D7FF") and `memory_full_test.py` phase F2 ("$D800-$DFFF") use the 4K reading; `video_ram_test.py` tests $D000-$D3FF only | **To verify** with `tests/video/hold_address.py`: park $D400 and $D800 and meter IC17 pin 25 (-CS). Whichever is low is the CRTC address; the other documents then need the one-bit correction |

The memory-side conventions (floating LS inputs read high while the sequencer is off the bus; no pull-ups on the
backplane) apply here as on every card; this card adds the open-collector nets to the list of lines that depend on
it.

## 5. Jumpers, headers, connectors — and how the card is set

| Item | Pins / meaning | Setting in the machine (`docs/system/MACHINE.md`, README) |
|---|---|---|
| SV3 (2x4) | pairs 1-2 (A3), 3-4 (A2), 5-6 (A1), 7-8 (A0); fitted = 0, open = 1 (RN2 pull-up); compared with ADDR15..12 | only 5-6 fitted: block $D000 |
| RN2 | the SV3 pull-ups | 10k as designed (was 1k from the 2026-09-18 tests until 2026-09-21) |
| SV4 (1x3) | 1 = crystal, 2 = DOTCLOCK, 3 = crystal/2 | **To verify:** position |
| JP1 (2x7) | eight latch inputs (pins 1, 2, 4, 6, 8, 10, 12, 14), LE on 13, VCC on 3, GND on 5: a byte the CPU can read back at odd upper-half addresses (a configuration/ID byte; the README does not say what it was for) | **To verify:** whether anything is jumpered; F2's $FF says nothing is |
| IC17 socket | MC6845 | **empty** |
| X2 DB9 female | 7 video (R11), 8 HS, 9 VS, 1 GND | — |
| U$3 RCA | combined HS+VS (wired-OR, R12) | — |
| C16 10 µF, C17-C29 0.1 µF | bulk and per-IC decoupling — all on the former `+5V` net | — |
| Rail wire | +5V to VCC, added 2026-09-21 | fitted |
| Pins | two bent pins straightened 2026-09-18 | — |
| X1 | DIN 41612, Blank V3.1 names on C3-C6 | slot not recorded |

## 6. Bring-up and test

What was done, in order (`tests/video/README.md`, README, MACHINE.md):

1. 2026-09-18: card installed, two bent pins straightened, RN2 changed to 1k while chasing a fault; the bus-tester
   RAM test showed the **write-through fault** — writes to $0010/$9010 (block 0 or 9, A0 = 0, A11 = 0) also landed in
   $D010. `tools/alias_min.py` is the 20-line reproduction.
2. 2026-09-20: the KiCad conversion's netlist proof reported the two 5 V nets; 2026-09-21 Ken joined them with a wire.
3. 2026-09-21: `tests/video/video_ram_test.py` **8/8 PASS**, quick and full (1K, patterns, inverse, neighbour
   isolation, the four write-through checks, read stability with memory traffic in between — necessary because
   $D000 is undecoded on the memory card and a floating bus can fake a good read); RN2 restored to 10k, quick test
   8/8 again; `tests/memory/memory_full_test.py` phases E1-E5 and F2 PASS in the 14/14 run.
4. Not done: anything with a CRTC. `hold_address.py HEX [--rd]` exists for the RS-fix verification table in the fix
   document (park an address, meter IC17 pins 24/25).

If it misbehaves:

| Symptom | Check |
|---|---|
| RAM reads back what was written even at an address nothing should answer | the memory card's $D000 block echoes the bus; use `video_ram_test.py`'s ordering (other traffic between write and read) |
| writes elsewhere land in the video RAM | the +5V/VCC wire (IC1 pin 14, RN2 pin 1 must be at 5 V); BOARDSEL at IC18 pin 6 must be low for non-$Dxxx addresses |
| RAM answers at the wrong block | SV3 against ADDR15..12; RN2 pull-ups |
| (with a 6845) registers cannot be written | E (IC1 pin 3) per 6.1; -CS per the RS finding; hold $D400 vs $D800 to settle the block question |
| no picture | DOTCLOCK at SV4 pin 2; CHARCLOCK width at IC19 pin 8 against IC28 pin 2 (6.2); glyph bits on IC24 pin 13; DE and HS/VS from the 6845 |

## 7. Revision history and what the next revision changes

| Rev | Date | Status | Notes |
|---|---|---|---|
| V1.0 | designed in Fusion 360 (Ken), export 2026-09-18 | **built, in the machine** without CRTC | drawn on Blank V3.1; the board file was exported under the template's name and stored as `Video_1.0.brd`; no fab files in the tree (`hardware/FABRICATED.md`: "none in tree") |
| v1.1 | KiCad master since 2026-09-21 | design only | `+5V` folded into `VCC` with a joining track (proof 116/116, DRC clean). To do before ordering: RS from A0 to A1, pull-ups on the 7416 outputs (BACKLOG) |

Beyond v1.1, `docs/system/OS-PLAN.md` decision 2 changes the architecture: **video card v2 puts the 6845 registers on
I/O ports** — PA = address register, PB = data register, with RS = IO-ADDR0 and no latch — so the card needs only its
2K of display RAM in the memory map and the whole -CS/RS/E problem of the memory-mapped interface goes away
(the E pulse becomes a function of -IO-RD/-IO-WR on those two ports). The memory map then has two jumper-only
variants (decision 4): A, video stays at $D000 (nothing to change on the cards today); B, video moved to $E000 with
the memory card's $D000 jumper set to RAM for a 36K TPA. Phase 4 of the plan pairs the card with a PS/2 keyboard
controller behind the console vectors. The review items 6.2/6.3/6.5 (character clock, HC levels, LPSTB) and the
crystal/C1 values belong in that redesign whichever interface it keeps.
