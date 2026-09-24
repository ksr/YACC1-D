# YACC1 I/O ports

The sixteen I/O ports: what is on each today, how the I/O card's select-latch scheme works, the CompactFlash ports,
what the emulators model, and what the OS plan reserves. Written 2026-09-23 from the YACC1-D tree.

Sources: `firmware/abi/README.md` (the port table), `docs/system/OS-PLAN.md` (decision 3, the port map with the
proposed uses), `firmware/monitor/monitor.asm` (the equates and every port access the ROM makes), `hardware/cards/io/README.md`,
`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.5 (how the I/O card decodes), `software/assembler/yacc1.def` (port names),
`software/cfmodel.h` (the CF card model), `software/emulator/main.c`, `software/ucemu/README.md`,
`tests/assembler/romcount/README.md`, `docs/datasheets/PC16550D.pdf` (the UART's register names).

## 1. How ports work on the bus

The port number is a 4-bit field of the microcode word (`IOADDR0..3`), driven for the duration of an `INP`/`OUTA`/
`OUTI` record; the strobes are `-IO-RD` and `-IO-WR`. The I/O card decodes `IO-ADDR0..2` with a 74LS138 (IC5) and
takes `IO-ADDR3` through the `IO-ADDR-HL` jumper, so the card answers to P0–P7 or P8–P15; it is strapped to the low
half (`OS-PLAN.md`; the I/O card V2.0 requires it). Of its eight selects V1.1 wires two (P0, P1); P2–P7 reach the
card's header; V2.0 adds the CompactFlash interface on P4/P5 (section 4). A port write is latched at the trailing
edge of `-IO-WR`; a read drives the bus while `-IO-RD` is low (review 1.5). The microcode's `-IO-ADDR-LD` strobe has
no consumer.

Instructions: `OUTA Pn` (port ← ACC), `OUTI Pn,byte` (port ← immediate), `INP Pn` (ACC ← port); port names
`P0`–`P9`, `PA`–`PF` (`yacc1.def`). From C: `outp(port, v)`, `inp(port)` with a constant port.

## 2. The port map

| Port | Today (hardware) | Interpreter (`software/emulator`) | ucemu | Proposed (`OS-PLAN.md`) |
|---|---|---|---|---|
| P0 | I/O card **select latch** (write): which device P1 talks to — see section 3 | stored; `$40` selects the UART path for `OUTI P1` | modelled (control latch) | unchanged |
| P1 | I/O card **data port** for the device selected in P0 | `OUTI P1` with P0 = $40 prints; `INP P1` with P0 = 1 returns $FF once (the switches) | modelled: 16550 (stdin/stdout), switches (`-s`), LEDs (`-L`) | unchanged |
| P2 | `-IO-SEL2` on the I/O card's header, nothing wired | **the console**: `OUTA P2` prints, `INP P2` reads a key | also a console (kept as the old shortcut) | stays the emulator console; reserved to the I/O card |
| P3 | `-IO-SEL3` on the header, nothing wired | nothing | nothing | reserved to the I/O card (a second UART, a printer port…) |
| P4 | `-IO-SEL4` on the header, nothing wired (V1.1) | CF register select (`cfmodel.h`) | same | **CF register select** on the I/O card V2.0 (write-only latch): bits 0–2 = ATA register 0–7, bit 3 = CF reset (1 = held), 4–7 ignored |
| P5 | `-IO-SEL5` on the header, nothing wired (V1.1) | CF data (`cfmodel.h`) | same | **CF data** on the I/O card V2.0: a read/write strobes -IOR/-IOW on the selected register |
| P6, P7 | `-IO-SEL6..7` on the header, nothing wired | nothing | nothing | reserved to the I/O card |
| P8, P9 | free | nothing (the CF model until 2026-09-23) | nothing | free (the CF's ports until 2026-09-23) |
| PA, PB | free | nothing | nothing | video card v2: 6845 address register (RS = 0) and data register (RS = 1) |
| PC, PD | free | nothing | nothing | PS/2 keyboard controller data and status/control |
| PE, PF | free | nothing | nothing | free (RTC, second CF, sound) |

`yacc1.def` had `P8=9` until 2026-09-22 (no firmware used P8 before the CF driver); it is `P8=8` now
(`tools/patched_files.txt`). The CF ports moved from P8/P9 to P4/P5 on 2026-09-23, when the interface moved onto the
I/O card V2.0 (`OS-PLAN.md` decision 1 update; the ROM build `ROM 2026-09-23B`, not yet burned, and both emulators).

## 3. The I/O card: P0 selects, P1 transfers (`monitor.asm` equates)

The byte written to P0 chooses the device and, for the UART, its register:

| P0 value | Name | Device behind P1 |
|---|---|---|
| `$01` | `SWITCHLED` | the switch/LED board: `INP P1` = the eight switches; `OUTA P1` = the eight LEDs (`switchin`, `ledout`) |
| `$02` | `LCDENABLE` | the LCD (`$04` `LCDREGISTER` selects its register); only in commented-out code |
| `$40` + n | `UARTCS` + `UARTAn` | the 16550 UART, register n where `UARTA0..A7` = `$00, $08, $10, $18, $20, $28, $30, $38` |
| `$80` | `TIL311` | the TIL311 hex displays (`TIL311out`) |

The UART registers by their offset (16550 names, `docs/datasheets/PC16550D.pdf`; the monitor uses exactly these):

| P0 | Register | Used for |
|---|---|---|
| `$40` (UARTA0) | RBR / THR (DLL with DLAB) | `INP P1` receives, `OUTA P1` transmits; at boot DLL ← 3 |
| `$48` (UARTA1) | IER (DLM with DLAB) | at boot DLM ← 0 |
| `$58` (UARTA3) | LCR | at boot `$80` (set DLAB) then `$03` (8N1) |
| `$68` (UARTA5) | LSR | bit 0 data ready (`uartin`, `const`), bit 6 transmitter empty (`uartout` waits for `$40`) |

Baud: divisor 3 = **38400** (`monitor.asm`: `OUTI P1,3 ;38400`; the commented `12 ;9600` implies a 1.8432 MHz UART
clock: 1.8432 MHz / 16 / 12 = 9600). **To verify:** the UART crystal value against the I/O card schematic
(`hardware/cards/io/eagle/v1.1`).

The console idioms (`monitor.asm`):

```
uartout:   OUTI P0,(UARTCS!UARTA5) / INP P1 / ANDI 40h / BRZ uartout   ; wait THRE
           OUTI P0,UARTCS / OUTA P1                                     ; send ACC
uartin:    OUTI P0,(UARTCS!UARTA5) / INP P1 / ANDI 01h / BRZ uartin     ; wait data ready
           OUTI P0,UARTCS / INP P1                                      ; receive (then CR -> LF, LEDs, echo)
ledout:    OUTI P0,SWITCHLED / OUTA P1
```

Under the `BRDEV` switch the same routines use P2 on the interpreter ([MONITOR.md](MONITOR.md) section 4).
`uartinne` (vector `$FFFC`, 2026-09-23) is `uartin` without the echo and the LED write, for the OS's `CONIN`.

The input-switch line tested by `BRINH`/`BRINL` is not a port: it is the ALU condition mux's `IN` input, fed from the
I/O card (`tests/assembler/romcount/README.md`: "the I/O card's input-switch line"). The ON/OFF LED (`ON`/`OFF`) is a
latch on the sequencer, not a port either.

## 4. The CompactFlash ports P4/P5 (`monitor.asm` driver, `cfmodel.h`)

- `OUTI P4,n` selects ATA task-file register n: 0 data, 1 error (read) / feature (write), 2 sector count, 3 LBA0,
  4 LBA1, 5 LBA2, 6 drive/head (`$E0` = LBA mode, drive 0), 7 status (read) / command (write).
- `INP P5` / `OUTA P5` / `OUTI P5,v` transfer one byte with the selected register. A 512-byte sector is one select
  of register 0 and 512 transfers (`cfread`: `INP P5 / STAVR R7 / INCR R7`).
- Bit 3 of the select byte holds the CF in reset while 1 (the hardware's addition; the ROM never sets it and the model
  ignores it).
- Commands used: `$EF` SET FEATURES (feature 1 = 8-bit transfers, at init), `$20` READ SECTORS, `$30` WRITE SECTORS;
  the model also answers `$EC` IDENTIFY. Status bits: 7 BSY, 6 DRDY, 3 DRQ, 0 ERR.
- The model (`software/cfmodel.h`): BSY never asserted; DRQ up while a buffer streams; ERR on an unknown command;
  with no image attached every read returns $FF so a bounded poll times out; a missing image file is created
  zero-filled (256 sectors). Attach with `-c disk.img` on either emulator.
- The hardware is not built. It is part of the I/O card V2.0 (being designed): IC5's Y4/Y5 are the two selects, then
  a 74LS32 strobe gating, a 74LS175 select latch, a 74LS08 (buffer enable, CF reset, ACT LED), a 74LS245 data buffer,
  status pull-ups and a 40-pin IDE header for a CF-to-IDE adapter ([`docs/cards/cf.md`](../cards/cf.md)). It needs the
  I/O card's IO-ADDR-HL strap at P0-P7 and neither its IO-ADDR nor DATA-ADDR jumper on P4/P5. Bench-test with the
  bus tester before the CPU touches it. (The standalone CF card v1.0, decoding P8/P9, is superseded.)

## 5. Design rules from the plan

Every new device with more than one register follows the select+data pattern (one port pair), so the sixteen
ports last; the I/O card keeps the low eight (and from V2.0 holds the CF on P4/P5 among them). The console stays two BIOS vectors (CHAROUT/UARTIN + CONST) so the
video card and a PS/2 keyboard can replace the UART without the OS or the programs knowing.
