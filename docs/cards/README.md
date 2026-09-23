# docs/cards — theory of operation, one document per card

Written 2026-09-23 from the YACC1-D tree (plan and rules: `docs/DOC-PLAN.md`). Each document follows the same
order: purpose and block diagram; the bus signals the card uses; an IC-by-IC walkthrough parsed from the active
Eagle schematic; timing and the design-review findings with their 2026-09-23 status; jumpers, switches and settings
as fitted (`docs/system/MACHINE.md`, `hardware/FABRICATED.md`); bring-up and test; revision history and what a next
revision should change. Anything not in the tree is marked **To verify:** in the text.

The machine and its bus as a whole: `docs/system/` (architecture, microcode, bus). The card design files:
`hardware/cards/<card>/` and `hardware/bus/`. Bills of material: `docs/bom/`.

## The CPU (control and datapath)

| Document | Card | One line |
|---|---|---|
| [`sequencer-logic.md`](sequencer-logic.md) | Sequencer logic v2.1 | the step counter, instruction/operand/branch registers, the pipeline latches that drive every control line, front-panel run/halt/reset |
| [`sequencer-memory.md`](sequencer-memory.md) | Sequencer memory V2.1 + EEPROM adaptor | the control store (62256 RAM loaded from I2C EEPROM by an ATmega328), READY / -BUS-EN |
| [`alu.md`](alu.md) | ALU V3.2 | accumulator, adder, logic functions, comparator, shifter, carry, the branch-condition mux |
| [`register.md`](register.md) | Index registers 1.1 (two cards) | R0..R7 as 74LS192 counters, byte-lane reads, the swap transceiver, the address-bus drivers |
| [`address-tmp.md`](address-tmp.md) | Address + TMP V1.0 (retired 2021) | the 74373 address/TMP registers of Bus V3.0/V3.1, replaced by the index-register cards |

## Memory and peripherals

| Document | Card | One line |
|---|---|---|
| [`memory.md`](memory.md) | Memory v1.3 | two 62256 + one 28C64, 4K-block jumpers, the FORCE-ROM boot remap, TMP0/TMP1; the M1/M2 findings |
| [`io.md`](io.md) | I/O V1.1 | 16550 UART behind P0/P1, switches, LEDs, TIL311s, LCD, IN/OUT; the full programming model; the CompactFlash card on P8/P9 as the next card |
| [`cf.md`](cf.md) | CompactFlash v1.0 (designed 2026-09-23, not built) | two I/O ports: a P8 register-select latch with a CF reset bit, P9 data through a 74LS245; 8-bit True IDE via a CF-to-IDE adapter; the timing argument for tying -CS0 low |
| [`video.md`](video.md) | Video V1.0 built / v1.1 KiCad master | 6845 + IDT7134 dual-port RAM at $D000, the register-select fix, the +5V rail wire, the plan to move the 6845 onto ports |

## Test and bring-up cards

| Document | Card | One line |
|---|---|---|
| [`bus-tester.md`](bus-tester.md) | Bus Test Card v1.1 (and the unbuilt v3.1) | ATmega + six MCP23017s driving every bus line; the `CMD:OPERAND#` protocol, `tools/busdrv.py`, the memory/video tests |
| [`mem-switch.md`](mem-switch.md) | Mem Switch V1.1 | 16 bytes of DIP-switch ROM at $0000 |
| [`mem-register.md`](mem-register.md) | Mem Register V1.0 | 16 bytes of 74LS374 RAM at $0010 |
| [`protocard.md`](protocard.md) | Protocard V1.0 | the bus on header rows (2016 labels, V3.2 pins) |

## The bus

| Document | Item | One line |
|---|---|---|
| [`backplane.md`](backplane.md) | Backplane V2.0, Bus Template V3.2, Blank V3.1/V3.2, the jumper boards, mechanical | the 96-pin signal table with who drives what, the V3.1-to-V3.2 rename of C3-C6, the bus-wide review findings, rules for a new card |
