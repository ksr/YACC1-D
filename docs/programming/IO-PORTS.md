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
half (`OS-PLAN.md`). Of its eight selects only two are wired (P0, P1); P2–P7 reach the card's header. A port write
is latched at the trailing edge of `-IO-WR`; a read drives the bus while `-IO-RD` is low (review 1.5). The
microcode's `-IO-ADDR-LD` strobe has no consumer.

Instructions: `OUTA Pn` (port ← ACC), `OUTI Pn,byte` (port ← immediate), `INP Pn` (ACC ← port); port names
`P0`–`P9`, `PA`–`PF` (`yacc1.def`). From C: `outp(port, v)`, `inp(port)` with a constant port.

## 2. The port map

| Port | Today (hardware) | Interpreter (`software/emulator`) | ucemu | Proposed (`OS-PLAN.md`) |
|---|---|---|---|---|
| P0 | I/O card **select latch** (write): which device P1 talks to — see section 3 | stored; `$40` selects the UART path for `OUTI P1` | modelled (control latch) | unchanged |
| P1 | I/O card **data port** for the device selected in P0 | `OUTI P1` with P0 = $40 prints; `INP P1` with P0 = 1 returns $FF once (the switches) | modelled: 16550 (stdin/stdout), switches (`-s`), LEDs (`-L`) | unchanged |
| P2 | `-IO-SEL2` on the I/O card's header, nothing wired | **the console**: `OUTA P2` prints, `INP P2` reads a key | also a console (kept as the old shortcut) | stays the emulator console; reserved to the I/O card |
| P3–P7 | `-IO-SEL3..7` on the header, nothing wired | nothing | nothing | reserved to the I/O card (a second UART, a printer port…) |
| P8 | free | CF register select (`cfmodel.h`) | same | **CF register select** (write-only latch): bits 0–2 = ATA register 0–7, bit 3 = the CS1 block (optional), 4–7 spare |
| P9 | free | CF data (`cfmodel.h`) | same | **CF data**: a read/write strobes -IOR/-IOW on the selected register |
| PA, PB | free | nothing | nothing | video card v2: 6845 address register (RS = 0) and data register (RS = 1) |
| PC, PD | free | nothing | nothing | PS/2 keyboard controller data and status/control (or a second CF) |
| PE, PF | free | nothing | nothing | free (RTC, second CF, sound) |

`yacc1.def` had `P8=9` until 2026-09-22 (no firmware used P8 before the CF driver); it is `P8=8` now
(`tools/patched_files.txt`).

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

## 4. The CompactFlash ports P8/P9 (`monitor.asm` driver, `cfmodel.h`)

- `OUTI P8,n` selects ATA task-file register n: 0 data, 1 error (read) / feature (write), 2 sector count, 3 LBA0,
  4 LBA1, 5 LBA2, 6 drive/head (`$E0` = LBA mode, drive 0), 7 status (read) / command (write).
- `INP P9` / `OUTA P9` / `OUTI P9,v` transfer one byte with the selected register. A 512-byte sector is one select
  of register 0 and 512 transfers (`cfread`: `INP P9 / STAVR R7 / INCR R7`).
- Commands used: `$EF` SET FEATURES (feature 1 = 8-bit transfers, at init), `$20` READ SECTORS, `$30` WRITE SECTORS;
  the model also answers `$EC` IDENTIFY. Status bits: 7 BSY, 6 DRDY, 3 DRQ, 0 ERR.
- The model (`software/cfmodel.h`): BSY never asserted; DRQ up while a buffer streams; ERR on an unknown command;
  with no image attached every read returns $FF so a bounded poll times out; a missing image file is created
  zero-filled (256 sectors). Attach with `-c disk.img` on either emulator.
- The card is not built (`OS-PLAN.md` phase 1): 74245 data buffer, a 74LS174/273 select latch, decode of IO-ADDR3
  high with IO-ADDR0..2 = 0/1, strobe gating from -IO-RD/-IO-WR, status pull-ups, activity LED; bench-test with the
  bus tester before the CPU touches it.

## 5. Design rules from the plan

Every new device with more than one register follows the select+data pattern (one port pair), so the sixteen
ports last; the I/O card keeps the low eight. The console stays two BIOS vectors (CHAROUT/UARTIN + CONST) so the
video card and a PS/2 keyboard can replace the UART without the OS or the programs knowing.
