# Design review, datapath cards (control-path pass) — 2026-09-21

Second pass after `DESIGN-REVIEW.md` (mechanical). Cards: ALU v3.2, Index Register 1.1, Memory v1.3, Mem Switch 1.1,
Mem Register 1.0. Method: every select / enable / strobe / clock / reset net was traced pin-to-pin from
`kicad/<ver>/reports/netlist.net` (pin names and types from the Eagle symbols) with chip types from the Eagle `.brd`,
and checked against the way the sequencer microcode actually drives the bus (`firmware/microcode/ucode-generator2/`),
because several hardware choices only work under a microcode convention. Signal polarity: `-` prefix = active low.
Gate delays quoted are LS-TTL typicals from the datasheets in `docs/datasheets/`.

Severity: HIGH = would stop the card working or damage parts; MED = unreliable / depends on a convention that is not
enforced by hardware; LOW = housekeeping or documentation.

---

## Memory card v1.3 (traced on `hardware/cards/memory/kicad/deprecated/v1.3-do-not-use/`, then filed as `kicad/v1.3`)

> **Note 2026-09-24:** this review traced what was then `kicad/v1.3` (now `kicad/deprecated/v1.3-do-not-use/`), which is an
> **earlier save** of the design, not the card that was fabricated (`hardware/cards/memory/eagle/v1.3/`, KiCad `kicad/v1.3/`;
> filed first as `v1.3-fusion-export-2026-09-24`).
> The one circuit difference: on the built card IC5's enable (pin 19) is IC15 pin 12 = AND(-LO-RAM, -HI-RAM, -ROM-CS),
> not `-VMA`, so where the findings below say "IC5 enable" read "the chip selects, through IC15". The findings
> themselves (M1-M8) are unchanged by that: every pin they name is wired the same on the built card.

### M1 — HIGH (masked by a microcode hack): FORCE-ROM clears on any -VMA cycle that starts with the address bus floating

Trace of the FORCE-ROM flip-flop clock:

- IC12A (74LS74): PRE(4) = `-RESET` (X1.C30), CLR(1) = VCC, D(2) = GND, Q(5) = `FORCE-ROM`, CLK(3) = `N$19`.
- `N$19` = IC10.8 (74ALS00) = NOT(`N$20`); `N$20` = IC10.6 = NAND(`ADDR15` [X1.A18, raw bus line into IC10.4], `N$22`);
  `N$22` = IC10.11 = NOT(`N$25`); `N$25` = IC3.3 (74LS32) = `-VMA` OR `-BUS-EN`.
  So CLK = ADDR15 AND VMA AND BUS-EN, three gate delays (~35 ns) after `-VMA` falls.
- The address is only driven onto the bus while `-VMA` is low: on the register card IC40.3 (74LS32) = `-BUS-EN` OR `-VMA`
  enables IC38 (74LS139, second half, pin 15) -> J3 -> IC38 first half (pin 1) -> `-Rx-ADDRSEL` -> IC41/42 (74LS244)
  output enables. That is ~75 ns typical (LS32 + two LS139 stages + 244 enable) before ADDR15 is driven.
- Between memory cycles nothing drives ADDR0-15 (no pull-ups or pull-downs on the backplane: `bus/backplane` v2.0
  contains only connectors and capacitors) and the memory card's LS inputs on ADDR15 (IC10.4, IC9.17) float high.

Failure scenario: on the first `-VMA` after reset, ADDR15 reads 1 (floating) for the ~40 ns before the register card
drives it low, so `N$19` produces a ~40 ns positive pulse (LS74 needs 25 ns) and clocks D=0 into IC12A: FORCE-ROM is
cleared on the very first fetch regardless of the address, and the CPU fetches from uninitialised low RAM instead of
the ROM. The bus-tester check of 2026-09-18 passed because the tester drives the address statically before it lowers
`-VMA`.

The designer met this: `ucode-generator2/main.c:102` and `:115` (`setSignal("-VMA"); // Hack prevent ROM mapping from
triggering`) assert `-VMA` in **every** microcode line with ADDR-REG-ID defaulting to PC, so the address bus never
floats while the machine runs. The hack works, but it removes the `-VMA` qualification from every chip select on this
card (the whole point of the v1.2 changes: IC7 G2A, IC10 `-LO-RAM`, IC5 enable are now permanently active), keeps IC5
(74LS245) driving BDATA from the bus at all times, and the hazard returns the moment any microcode line drops `-VMA`
or the bus tester drives `-VMA` with the address lines tri-stated.

Bench: scope IC12 pin 3 against pin 5 on the first cycle after reset with the register card fitted and a microcode
image that does not hold `-VMA`; or with the bus tester leave ADDR0-15 as inputs, hold `-BUS-EN` low, pulse `-VMA`
low, and read FORCE-ROM (IC12.5): it drops.

### M2 — MED: the 28C64 EEPROM is write-enabled by every -MEM-WR, including during FORCE-ROM

- IC13 (28C64) `-WE`(27) = `N$4` = IC6.4 = NOT(IC6.8 = NOT(`-MEM-WR`)): `-MEM-WR` re-buffered, no gating, no
  write-protect jumper. `-CE`(20) = `-ROM-CS` = IC6.12 = NOT(IC18.8), IC18 (74ALS30) fed by the ROM row of the U$1
  block jumpers (pull-ups RN7).
- While FORCE-ROM = 1, IC11 (74LS157, select pin 1 = FORCE-ROM, B inputs = VCC) forces BADDR12-15 = 1111, so **every**
  address selects block $F (IC7 Y7 -> jumper -> IC18 -> `-ROM-CS`).

Failure scenario: a write to any address while FORCE-ROM is still set (e.g. boot code initialising a RAM variable
before its first jump above $8000), or any later stray write into $E000-$FFFF, writes the EEPROM. A 28C64 then spends
~10 ms in an internal write cycle during which reads return the toggle/poll bits, so code executing from the ROM
crashes and the image is corrupted. The shipped monitor is safe by construction (`firmware/monitor/monitor.asm:58-61`:
first instruction at $F000 is `BR eprom` to $F003, which clears FORCE-ROM before any store), but nothing in hardware
enforces that.

Bench: with the bus tester, reset, write a byte to $0010 with `-MEM-WR`, then read $F010 through the ROM: it changed
(use a scratch EEPROM). With a meter, `-WE` on IC13.27 follows bus pin B24 one-for-one.

### M3 — MED: TMP registers latch on the leading edge of -TMP-REG-LDn; correct only under a microcode ordering rule

- IC26/IC27 (74LS374) CLK(11) = `N$33` = IC14.2 = NOT(`-TMP-REG-LD0`); IC28/IC29 CLK = `N$47` = IC14.12 =
  NOT(`-TMP-REG-LD1`). A 374 clocks on the rising edge of CLK, i.e. ~10 ns after the **falling** (leading) edge of the
  bus strobe, so whatever is on DATA0-15 at the start of the strobe is captured.
- Every register-card source needs far longer than 10 ns to appear on the bus after its own strobe (LS32 -> two LS139
  -> LS32 -> 244 enable -> CD4077 (~100 ns, see R1) -> LS32 -> 245 enable); a memory read needs ~150 ns.

The microcode compensates by asserting the data source one line before the LD strobe (`memory.c:24-28`,
`accumulator.c:343-349`, `branch.c:624-631`) — the hardware silently depends on that. `branch.c:14-22`
(`moveRegtoTmp`) asserts `-REG-FUNC-RD/-REG-RD-LO/-REG-RD-HI` and `-TMP-REG-LD0` in the same line and would latch
stale data; it currently has no callers, so the fault is latent.

Bench: bus tester: put a value on DATA, assert `-TMP-REG-LD0` low, change DATA while it is still low, release, read
back with `-TMP-REG-RD0`: the first value is returned.

### M4 — MED (configuration): low RAM cannot be removed from the map; conflicts with the bring-up cards and with FORCE-ROM

- `-LO-RAM` = IC10.3 (74ALS00) = NAND(`N$13` = NOT BADDR15 [IC14.4], `N$12` = NOT `-VMA` [IC14.10]). No jumper, no
  block decode: $0000-$7FFF is always RAM when `-VMA` is low.
- The Mem Switch card decodes $0000-$000F and the Mem Register card $0010-$001F (comparators IC4 on each, see below),
  both driving DATA0-7 on `-MEM-RD`.

Failure scenario: if the memory card is on the bus together with either bring-up card (MACHINE.md says they were
re-fitted 2026-09-21), every read of $0000-$001F has two drivers on DATA0-7: the 62256 through IC5 (74LS245, DIR =
`-MEM-RD`, G = `-VMA`) and the bring-up card's 74LS244/374 outputs. After reset it is three, because FORCE-ROM maps
the EEPROM onto $0000 as well. Bench: meter on any DATA0-7 line during a read of $0000 shows an intermediate level
(~1-2 V) if two drivers disagree.

### M5 — LOW: control inputs rely on floating-high when -BUS-EN is high

`-MEM-WR`, `-MEM-RD`, `-VMA`, `-TMP-REG-RD0/1`, `-TMP-REG-LD0/1` come from 74LS374 outputs on the sequencer whose OC
pins are `-BUS-EN` (sequencer IC7/12/14/28 pin 1), so all of them are tri-state until the sequencer-memory card
reports READY (~54 s after power-up) and whenever the bus is handed over. No card and not the backplane has a pull-up
on any of them (checked on all five cards plus io and sequencer). LS inputs float high so nothing is selected, but the
levels are undefined and the 62256/28C64 `-WE` depends on it. Bench: meter on B24 with the sequencer un-READY reads
~1.5-1.9 V, not a logic high.

### M6 — LOW: unused 74LS04 inputs left open

IC14 pins 5 and 9 have no net at all in the PCB (pads unconnected), so the mechanical pass, which looks for single-node
nets, could not see them. IC3 and IC12B unused inputs are tied off correctly.

### M7 — LOW: IC7 (74LS138) G2B needs JP1 fitted

IC7.5 = `N$24` = JP1 pin 2 only; JP1 pin 1 = `-BUS-EN`, pin 3 = GND. With no jumper the pin floats high and the whole
high-32K decode (RAM blocks and ROM) is dead. Note MACHINE.md's "jumper wire from IC7 pin 4, unconnected": pin 4 is
G2A = `-VMA`; if that wire ever replaces the track, pin 4 floats and the same symptom appears.

### M8 — LOW: DATA0-15 pull-down networks RN5/RN6 have no value in the design files

RN5/RN6 (RNX8, pin 1 = GND) are pull-downs on the bus DATA0-15. Their value is empty in both `.sch` and `.brd`. Below
~4.7 k they would exceed the LS IOH budget of every driver on the bus; MACHINE.md's observation that an undecoded read
"returns the last value left on the bus" suggests they are either high-value or not fitted. Confirm with a meter
(resistance from A19 to GND with the card out).

### Checked, no issue (memory card)

- 62256 `-OE` = `N$3` = `-MEM-RD` via two inverters; `-WE` = `-MEM-WR`; never both low; IC5 DIR = `-MEM-RD` so the
  245 receives during writes and drives during reads. Only a ~20-30 ns BDATA overlap at the end of a read (245 turns
  round before the RAM's -OE has released) — normal for LS designs.
- Write strobe ordering: `main.c:236-249` asserts ADDR-ID + `-VMA` + source in one line and `-MEM-WR` in the next, so
  address decode (IC8/9 244s, IC11 157, IC7 138, IC4/IC18 NAND8s) has a full step to settle before `-WE` falls, and the
  source is held one line after `-MEM-WR` rises: no cross-block write from decode glitches.
- Block jumpers: IC7 Y0-Y7 -> U$1 middle row; top row -> IC4 (74ALS30, pull-ups RN8) -> IC6.10 `-HI-RAM`; bottom row ->
  IC18 (pull-ups RN7) -> IC6.12 `-ROM-CS`. Unjumpered blocks are pulled inactive. ROM A12 = BADDR12 so both halves of
  the 8K are reachable when $E and $F are jumpered down.
- FORCE-ROM uses the raw ADDR15 (IC10.4) and not BADDR15, so the 157 feedback loop cannot hold it set.
- Reset polarity: IC12A PRE = `-RESET` (active low) matches the bus.
- Power-on state of FORCE-ROM is defined only by `-RESET`: see S1.

---

## Index Register card 1.1 (`hardware/cards/register/kicad/v1.1/`)

### R1 — MED: CD4077 (4000-series CMOS) driven by LS-TTL outputs, and it sits in every bus turn-around path

- IC34 is a `4077` from the Eagle `40xx` library (CD4077B-class, board value 4077N), VDD = 5 V. Its inputs:
  pin 2 = `-RESET` (sequencer IC36.6, 74LS04), pin 6 and 13 = `-LDSEL` (IC32.12/J2, 74LS139), pin 12 = `-RDSEL`
  (IC32.4/J1, 74LS139), pin 9 = `-HL-SWAP` (sequencer IC28.12, 74LS374). Other inputs are GND. No pull-ups on any of
  them (RN1/RN2 10 k are on ADATA, not here).
- A CD4077B needs VIH >= 3.5 V at 5 V; an LS output guarantees only 2.7 V (typically 3.4 V unloaded). Outputs:
  pin 3 = `RESET` (CLR of all sixteen 74LS192s), pin 4 = `BUS-DIR` (IC35/36/37 74LS245 DIR), pin 11 = `N$42` (XNOR of
  `-RDSEL`,`-LDSEL`: the 245 enable term), pin 10 = `N$41` (swap select). CD4077B propagation is ~100 ns typical,
  150+ ns max at 5 V, so it is the slowest element between a bus strobe and this card's data drivers.

Failure scenario: a register read/load that works on one card or one chip lot and not another, or a card that clears
its registers (RESET output high) when `-RESET` is only pulled to ~2.5-3 V. Bench: meter on IC34 pins 2, 6, 9, 12, 13
when the corresponding line is inactive; anything under 3.5 V is out of spec for the part. Scope pin 11 against pin 12
for the delay.

### R2 — MED: count strobe is a plain OR with the read select, so a change of REG-RD-ID while -REG-UP/-REG-DN is low counts the *deselected* register

- Per register (R0 shown; R1 = IC15, R2 = IC25, R3 = IC47 identical): IC1.3 (74LS32) `N$17` = `-R0-RDSEL` OR `-REG-UP`
  -> IC3.5 (74LS192 UP); IC1.6 `N$18` = `-R0-RDSEL` OR `-REG-DN` -> IC3.4 (DN); carries cascade IC3->IC4->IC5->IC6.
  `-R0-RDSEL` = IC33.4 (74LS139) from REG-RD-ID0-1, gated by `-RDSEL` <- J1 <- IC32 (ID2-3) gated by `N$19` = IC31.3 =
  `-BUS-EN` OR `-REG-FUNC-RD`.
- A 74LS192 counts on the rising edge of UP (DN high). `N$17` rises when **either** input rises. If `-REG-UP` is low
  and the decoder deselects R0 (ID changes, or `-REG-FUNC-RD` released first), R0 counts.

The microcode's `incrementReg()` (`main.c:203-214`) sets ID + `-REG-FUNC-RD` + `-REG-UP` in one line and clears
`-REG-UP` and `-REG-FUNC-RD` together, which yields exactly one edge — but only if `-REG-FUNC-RD` was not already
active with a different ID in the preceding line; the author's own comment at `main.c:202` ("might be an issue if
current setRdId reg is different") is this hazard. Bench: bus tester: `-BUS-EN` low, `-REG-FUNC-RD` low with ID = R1,
`-REG-UP` low, change ID to R0, release: R1 has incremented.

### R3 — LOW: same-card register-to-register moves cannot use -HL-SWAP

With both `-RDSEL` and `-LDSEL` active on one card, `N$42` = 1 disables IC35/36 and (through IC31.11 = `N$42` OR
`-HL-SWAP`) IC37, so the move goes over the internal ADATA bus with no byte-swap path. Cross-card moves swap fine.
Microcode only uses `-HL-SWAP` with memory/TMP transfers today, so this is a constraint, not a fault.

### Checked, no issue (register card)

- Bus direction (the note's open question "should it be based on -RD-SEL"): `BUS-DIR` = XNOR(GND, `-LDSEL`) = 1
  (DATA->ADATA) only when this card is load-selected, 0 (ADATA->DATA) otherwise; the 245s are enabled (`N$1` =
  `N$41` OR `N$42` low) only when exactly one of RD/LD is on this card and no swap is requested. All four cases
  (read here / load elsewhere, load here / read elsewhere, both here, neither) resolve to a single driver. The design
  as drawn is correct.
- Swap path: IC37 (DATA0-7 <-> ADATA8-15) enabled only when `-HL-SWAP` low AND `N$42` low; IC35/36 disabled then
  (`N$41` = HL-SWAP). Mutually exclusive.
- Register load: IC3/IC4 LD = `N$16` = `-R0-LDSEL` OR `-REG-LD-LO`; IC5/IC6 LD = `N$22` = `-R0-LDSEL` OR
  `-REG-LD-HI`. Level-sensitive load; the microcode (`register.c:52-60`) sets `-REG-FUNC-LD` + ID one line before the
  `-REG-LD-LO` pulse and the source one line before that, and the 245 releases (via R1's slow path) after the LD input
  has already risen (LS32 from `-REG-LD-LO`), so data is held through the load window.
- Address drive: IC38 second half (ID2-3, G = `-BUS-EN` OR `-VMA`) -> J3 -> first half (ID0-1) -> one of
  `-R0..R3-ADDRSEL` -> IC41/42, IC17/18, IC27/28, IC49/50 (74LS244). One register per bus, one card per J3 setting.
- Read enables: `N$20` = `-R0-RDSEL` OR `-REG-RD-LO` -> IC7 (low byte -> ADATA0-7); `N$21` with `-REG-RD-HI` -> IC8.
  With only one half read, the other ADATA byte is the RN1/RN2 10 k pull-ups ($FF) and is driven onto DATA by the
  other 245 — a definition, not a conflict.
- 74LS192 cascade CO->UP, BO->DN, stage n to n+1, ripple over four chips; CLR = `RESET` active high matches the
  inverted bus `-RESET`. Unused CO/BO on IC6/12/22/44 are outputs, fine.
- Both card-select headers (J1 RD, J2 LD, J3 ADDR) must be set to the same ID2-3 code on a card; the microcode uses
  the same 4-bit number for all three IDs (`main.c:145-164`).

---

## ALU v3.2 (`hardware/cards/alu/kicad/v3.2/`)

### A1 — LOW/MED: BR-COND floats when JP1 selects -ALU-FUNC as the mux enable

IC26 (74LS251) G(7) = `N$4` = JP1 pin 2; JP1 pin 1 = `-ALU-FUNC`, pin 3 = GND. Y(5) = `N$56` -> IC27.10 (74LS86)
XOR `AC-LD-INV` -> IC27.8 = `BR-COND` (X1.C24). With JP1 on `-ALU-FUNC`, `N$56` is tri-state whenever `-ALU-FUNC`
is high and has no pull-up, so BR-COND is whatever the floating LS input of IC27 reads. Harmless only if the
sequencer's branch flip-flop is set solely while `-ALU-FUNC` is asserted (Sequencer notes: "SET with and of BRTest
and BRCond"). With JP1 on GND the mux always drives. Bench: meter on C24 with `-ALU-FUNC` high and JP1 on pin 1.

### A2 — LOW: `-AC-LD-INV` doubles as the branch-condition inverter

IC27.9 = `AC-LD-INV` (IC1.2 = NOT `-AC-LD-INV`). Any microcode line that asserts `-AC-LD-INV` for an inverted
accumulator load also inverts BR-COND for that line. Only matters if the sequencer samples BR-COND then.

### A3 — LOW: brief bus overlaps on internal buses at strobe edges

- ACI-DATA: IC2 (74LS240, G = `-AC-LD-INV`) and IC3 (74LS244, G = `AC-LD-INV` from IC1.2) are complementary through
  one inverter; both drive for ~10 ns at each transition.
- BDATA on `-AC-RD` release: IC10/11 (74LS245) DIR = `-AC-RD` flips to A->B ~8 ns after release while IC12 (74LS244,
  G = `-AC-RD`) is still turning off (~20 ns), and the 245 stays enabled because `-ALU-IO-EN` = IC7.11 = `-ALU-FUNC`
  OR `-BUS-EN` and `-ALU-FUNC` is not released in the same line (`accumulator.c:350`). Tens of ns, LS-tolerated.

### Checked, no issue (ALU)

- Accumulator IC5 (74LS374) CLK = `AC-LD` = NOT `-AC-LD` (IC1.12): latches on the leading edge; microcode sets the
  function one line earlier (`accumulator.c:14-22`). OC = GND: ACO-DATA always valid.
- Carry flip-flop IC9A: D = `N$7` = IC7.3 = `CO/BO` OR `SHIFT-OUT`; CLK = `N$5` = IC6.8 = AND(`N$3`, `N$9`);
  `N$3` = IC4.3 = NAND(`-ADD/SUB`, `-SHIFT`) (= "function is add, sub or shift"); `N$9` = JP2 pin 2 = `AC-LD` per the
  note "should be ac-ld". The clock is gated by decoder outputs that are stable during the `-AC-LD` pulse (ALU code
  is set a line earlier), so no glitch; logic ops preserve carry as intended. CLR = `-RESET`, polarity correct.
- `CO/BO` = IC1.10 = NOT(IC4.6 = NAND(`N$15` = ADD/SUB, `N$10` = IC27.6 = `N$1` (IC36 C4) XOR `SUB`)): carry for add,
  borrow for subtract, only during add/sub — matches the v3.2 note.
- Carry-in IC35 C0(7) = `N$2` = IC27.3 = (`ALU3` AND `C/SHIFT`) XOR `SUB`: plain SUB gets +1 (two's complement with
  IC33/34 XOR array on BDATA), ADC/SBC (ALU3=1) take the flag with the right sense.
- IC24/IC25 (74LS85) cascade: IC24 pin 2 = GND, pin 3 = VCC, pin 4 = GND — correct LSB-stage seeding; A = BDATA,
  B = ACO; outputs to mux D1-D3.
- IC8 (74LS138) is permanently enabled (G1 = VCC, G2A/B = GND); the eight function 244s (IC13/16/17/20/23/31/37) are
  mutually exclusive by construction and only feed the internal INV-IN bus.
- Shift register IC29/30 (74LS194): S0/S1 = ALU0/1, CLK = `SR-LD` (leading edge of `-SR-LD`); IC9B (`SHIFT-OUT`)
  D = IC32.7 (mux of SRD0/SRD7 by ALU0-1) is clocked on the same edge and samples the pre-shift bit. Fine.
- V1/V2 (M74HC4078): pin 13 is the NOR output (datasheet `744078.pdf`: "all inputs L -> X(13) = H"), so `N$6` / `N$52`
  = "byte is zero"; `N$55` = both zero. Matches ALUZ (4) and ALU16Z (6) in `CodeGen.h`.
- Bus transceivers enabled only with `-ALU-FUNC` low: the microcode pairs `-AC-RD` with `-ALU-FUNC` everywhere it
  drives the accumulator onto the bus (`accumulator.c:343`, `:377`, `:513`; `putBustoRegMem(reg,"-AC-RD")` callers
  are inside blocks that already hold `-ALU-FUNC`). During `-AC-RD`, DATA8-15 carry $FF from RN2 (10 k pull-ups on
  BDATA8-15) through IC11 — a definition, not a conflict.
- `-VMA`, `-HL-SWAP` are connector-only nets on this card (unused), as the note says.

---

## Mem Switch 1.1 (`hardware/cards/mem-switch/kicad/v1.1/`) and Mem Register 1.0 (`hardware/cards/mem-register/kicad/v1.0/`)

### B1 — MED (configuration): both cards, and low RAM, overlap — see M4

Mem Switch decodes $0000-$000F and Mem Register $0010-$001F (SW1 sets ADDR4-7 against IC4 74LS85 with RN1 pull-ups;
IC4 A=B_I(3) = V1 (M74HC4078) pin 13 = NOR(ADDR8-15), so only page 0). Neither can coexist with the memory card's
undisableable low RAM.

### B2 — LOW: Mem Switch design files fit 74LS244, the notes say 74240

`Notes.md` for 1.1 lists "Change to 74240 (inverted output)" and the README repeats it, but the v1.1 schematic/board
show IC5-IC20 = 74LS244N with the switches pulling to GND against RN2-RN17 pull-ups (switch closed = 0). If 74LS240s
were ever fitted, every switch bit reads inverted. Document whichever is true.

### Checked, no issue (bring-up cards)

- Read qualification: IC1 (74ALS27) `N$19` = NOR(`-VMA`, `-BUS-EN`, `-MEM-RD`), `N$82` = NOT `N$19` -> IC2/IC3
  (74LS138) G2A; IC2 G2B = ADDR3, IC3 G2B = NOT ADDR3 (IC1.6); G1 = comparator match. Exactly one of SW0-15 / RD0-15
  low per read; each enables one 74LS244 (switch card) or one 74LS374 OC (register card) onto DATA0-7. DATA8-15 are
  not driven.
- Write (Mem Register): IC7 (74ALS27) `N$2` = NOR(`-VMA`, `-BUS-EN`, `-MEM-WR`), `N$4` = NOT `N$2` -> IC5/IC6 138 G2A;
  WRn -> 374 CLK. The 374 loads on the **rising** edge of WRn, i.e. at the end of the strobe (trailing edge); the
  microcode holds the source one line after `-MEM-WR` rises (`main.c:243-247`) and the address is stable a line before,
  so the decoder cannot produce a second rising edge on another WRn during the write.
- No reset inputs on either card; nothing to mismatch.

---

## System-level items found while tracing (not on the five cards, recorded so they are not lost)

### S1 — MED: no power-on reset anywhere; `-RESET` is a manual RS latch

Sequencer-logic v2.1: `RESET` = IC32.4 (74ALS02) = NOR(`FP-RESET` [switch RESET0 via R7], `RUN`); `RUN` = IC32.1 =
NOR(`RESET`, `FP-EXECUTE`); `-RESET` = IC36.6 (74LS04) = NOT `RESET`. There is no RC or supervisor. At power-up the
latch settles arbitrarily, so until the button is pressed the memory card's FORCE-ROM (IC12A PRE), all sixteen
74LS192 register counters (CLR = RESET), and the ALU carry/shift flip-flops (IC9 CLR) are undefined. Bench: meter on
C30 after a cold power-up, before touching the front panel.

### S2 — LOW: reset polarity is consistent across cards

Bus `-RESET` (active low, totem-pole from IC36.6): memory IC12A PRE (active low), ALU IC9 CLR (active low), register
IC34 XNOR(GND, `-RESET`) -> active-high CLR of the 192s. No mismatch.

### S3 — LOW: control-line idle state is "floating" bus-wide

See M5. Every control line on rows B/C is a 374 output with OC = `-BUS-EN`; no card and not the backplane pulls them.
The memory card is the one that could lose data from it (M2, M5).

---

## Summary

| ID | Card | Sev | One line |
|---|---|---|---|
| M1 | Memory | HIGH (masked) | FORCE-ROM clock = ADDR15 AND VMA races the register card's address drivers; clears on the first cycle whenever the address bus floats. Hidden today by the microcode holding `-VMA` in every line, which also disables all `-VMA` gating of the chip selects. |
| M2 | Memory | MED | 28C64 `-WE` = `-MEM-WR`, unprotected; during FORCE-ROM every address selects the ROM block, so a boot-time store writes the EEPROM. Shipped monitor avoids it (`BR` first). |
| M3 | Memory | MED | TMP registers latch on the leading edge of `-TMP-REG-LDn`; depends on the microcode's source-one-line-early convention; `moveRegtoTmp` breaks it (unused). |
| M4/B1 | Memory + bring-up | MED (config) | Low RAM ($0000-$7FFF) cannot be jumpered out; with a bring-up card fitted (or FORCE-ROM after reset) two or three drivers on DATA0-7 at $0000. |
| R1 | Register | MED | CD4077 CMOS thresholds (VIH 3.5 V) on LS-driven `-RESET`, `-RDSEL`, `-LDSEL`, `-HL-SWAP`; ~100 ns in the 245 enable/direction path. |
| R2 | Register | MED | UP/DN = OR(select, `-REG-UP`): deselecting while `-REG-UP` is low counts the deselected register; safe only under the microcode ordering the author flagged. |
| S1 | Sequencer | MED | No power-on reset; FORCE-ROM, registers, carry undefined until the button. |
| A1 | ALU | LOW/MED | BR-COND floats when JP1 = `-ALU-FUNC` and `-ALU-FUNC` is high. |
| M5/S3 | Memory | LOW | All bus control inputs float (374 OC = `-BUS-EN`) before READY / on handover; no pull-ups anywhere. |
| M6, M7, M8, R3, A2, A3, B2 | various | LOW | Open LS04 inputs; JP1 must be fitted; RN5/RN6 value unknown; no same-card swap; `-AC-LD-INV` also flips BR-COND; ns-scale internal overlaps; 244 vs 240 documentation. |

Checked and clean: memory write-strobe ordering and 62256 -OE/-WE relation, block-jumper decode, FORCE-ROM uses raw
ADDR15; register-card bus direction (the 1.2 open question is answered: correct as drawn), swap path exclusivity, load
timing, address drive, 192 cascade; ALU accumulator/carry/borrow/carry-in logic, comparator cascade seeding, shift
register and shift-out, 4078 output polarity, transceiver enables; bring-up cards' read/write qualification and decode.
