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
| [`memory.md`](memory.md) | Memory v1.3 (in the machine until 2026-11-09) | two 62256 + one 28C64, 4K-block jumpers, the FORCE-ROM boot remap, TMP0/TMP1; the M1/M2 findings |
| [`memory-v2.md`](memory-v2.md) | Memory v2.0 (in the machine) | v1.3 plus the CompactFlash interface on P8/P9: the re-layout, the adapter on standoffs, JP3 and R15 |
| [`io.md`](io.md) | I/O V1.1 | 16550 UART behind P0/P1, switches, LEDs, TIL311s, LCD, IN/OUT; the full programming model; the CompactFlash interface on P8/P9 as the next device on the ports |
| [`cf.md`](cf.md) | CompactFlash interface: the CF card v1.0 circuit (designed 2026-09-23, not built); planned 2026-09-24 onto the memory card, not designed yet | two I/O ports: a P8 register-select latch with a CF reset bit, P9 data through a 74LS245; 8-bit True IDE via a CF-to-IDE adapter (SinLoon or TAODAN, undecided); the timing argument for tying -CS0 low |
| [`video.md`](video.md) | Video V1: V1.0 built, v1.1–v1.3 KiCad designs | 6845 + IDT7134 dual-port RAM at $D000, the register-select fix, the +5V rail wire, the plan to move the 6845 onto ports |
| [`video-v3.md`](video-v3.md) | Video V3 (a design note, 2026-11-11; not built: stopped 2026-11-12 after the schematic) | a VGA card round the HD63484 ACRTC: 640 x 480 with the chip drawing, ports only, two ways to do text, the steps to 800 x 600 and 1024 x 768 |
| [`video-v4.md`](video-v4.md) | Video V4 (design note, netlist, schematic, 2026-11-12; simulated; the board routed, 250 mm; reviewed 2026-11-13, the review's fixes in and the board routed again, since 2026-11-14 with its four clocks laid first; the pre-order check without a failure; not ordered) | VGA with the 6845: 16 dots a count, two bytes fetched in each, so the 6845 runs at 1.57 MHz; 80 x 25 of 8 x 16 and 640 x 400 graphics with V2.0's ports, windows, direct mode and PS/2 section |
| [`video-v2.md`](video-v2.md) | Video V2.0 (ready to order; on hold 2026-11-12) | v1.3 plus a 512 x 192 graphics layer, every register on I/O ports PA-PE, two PS/2 ports on an ATmega328P; 218 mm, 4 layers |

## Test and bring-up cards

| Document | Card | One line |
|---|---|---|
| [`bus-tester.md`](bus-tester.md) | Bus Test Card v1.1 (and the unbuilt v3.1) | ATmega + six MCP23017s driving every bus line; the `CMD:OPERAND#` protocol, `tools/busdrv.py`, the memory/video tests |
| [`mem-switch.md`](mem-switch.md) | Mem Switch V1.1 | 16 bytes of DIP-switch ROM at $0000 |
| [`mem-register.md`](mem-register.md) | Mem Register V1.0 | 16 bytes of 74LS374 RAM at $0010 |
| [`protocard.md`](protocard.md) | Protocard V1.0 | the bus on header rows (2016 labels, V3.2 pins) |
| [`rtc.md`](rtc.md) | Real-time clock: design note (2026-11-03), not designed or built | a DS12C887 on P6/P7 (register number, data), the CF card's decode; Kermit's timeouts in seconds, `/bin/date`, file dates for `make` |

## The bus

| Document | Item | One line |
|---|---|---|
| [`backplane.md`](backplane.md) | Backplane V2.0, Bus Template V3.2, Blank V3.1/V3.2, the jumper boards, mechanical | the 96-pin signal table with who drives what, the V3.1-to-V3.2 rename of C3-C6, the bus-wide review findings, rules for a new card |
