# YACC1 disk operating system — the plan (decisions of 2026-09-22)

Bring the P8X system (a RAM-resident OS loaded from CompactFlash, a hierarchical filesystem, a shell, C commands in
`/bin`) to the YACC1. Serial console first; the video card and a PS/2 keyboard come later behind the same console
vectors. BASIC leaves the ROM and returns as a `/bin` command. Ken's decisions in this file; the phases at the end
are the order of work. Nothing here is built yet.

## Decisions

1. **CF card in I/O space, two ports.** P8 = register-select latch (write-only, the ATA register number 0-7 in
   the low three bits), P9 = data port (reading or writing it strobes -IOR/-IOW on the selected task-file register).
   The driver writes the select once per register access; a 512-byte transfer selects the data register once and
   then loops `INP P9 / STAVR Rn / INCR Rn`. Chosen over eight direct ports to keep six of the sixteen ports free:
   the I/O card already holds P0-P7 (its 74138 decodes IO-ADDR0..2; IO-ADDR3 goes to a strap) for the two it uses.
   Chips: 74245 data buffer, a 74LS174/273 select latch, the port decode (IO-ADDR3 high, IO-ADDR0..2 = 0/1), strobe
   gating from -IO-RD/-IO-WR, the CF status pull-ups, activity LED. True IDE 8-bit mode (SET FEATURES $EF/$01 at
   init), the P8X card's circuit otherwise (`p8x/hardware/cf-card/`). First KiCad-native card of the machine.
2. **Video card v2 puts the 6845 registers on ports too** (PA = address register, PB = data register: RS is
   IO-ADDR0, no latch), so the card needs only its 2K of display RAM in the memory map. Until then the built card
   stays as it is: 2K block, RS-to-A1 fix pending (`hardware/cards/video/docs/fix-6845-register-select.md`).
3. **Port map**: P0/P1 the I/O card (UART, switches/LEDs, LCD, TIL311) as now; P8/P9 CF; PA/PB reserved for the
   6845; PC-PF free (PS/2 keyboard controller, RTC, a second CF, sound) — each follows the select+data pattern if
   it needs more than one register. Note: `yacc1.def` had `P8=9` (typo, fixed 2026-09-22; nothing used P8).
4. **Memory map** — two variants, both jumper-only on the hardware (memory card block jumpers, video 7485 SV3):

   | Range | A: video stays at $D000 (no card change today) | B: video moved to $E000 |
   |---|---|---|
   | $0000-$0FFF | system page: monitor/BIOS variables, sector buffer, stack $0EFF down | same |
   | $1000-$4FFF | OS, loaded from CF into RAM (16K reserve = LBA 1-32 as on P8X) | same |
   | $5000-$CFFF | transient program area, 32K | $5000-$DFFF, 36K ($D000 jumper up = RAM) |
   | $D000-$D7FF | video (2K); $D800-$DFFF unused | RAM |
   | $E000-$EFFF | ROM (spare 4K: free for later, blank in the image) | video (2K used) |
   | $F000-$FFFF | ROM: monitor + CF driver + boot loader, vectors $FFC0 | same |

   Start with A (nothing to change on the cards); B is a jumper move later if the 4K of TPA is wanted. The
   software must not care which: the OS's TPA top is one constant.
5. **ROM holds only sectors, never the filesystem** (the CP/M arrangement): monitor, CF init/read/write by LBA,
   a B command that reads N sectors from LBA 1 to $1000 and JSRURs into them, three new $FFC0 vectors. The
   monitor's T-menu tests (1,062 bytes) and BASIC entry points go; the boot code is ~300 bytes. The filesystem
   primitives live in the RAM-resident OS, so an OS change never needs a ROM burn.
6. **P8XFS v2 on the card, byte for byte as on the P8X**, so `p8x/tools/p8xfs.py` and the disk images work
   unchanged; the OS jump table at $1000 keeps the shape of P8X's `$20xx` syscalls so C commands port by
   swapping `lib_abi.c` (P1/A on the P8X become R7/ACC here, the monitor's own convention).
7. **The OS kernel is written in C with y1cc**, not ported from the 5,200 lines of P8X assembly (no indexed
   addressing here). Size is the risk (C is 2-3x assembly; a kernel without the window manager is ~10K of P8X
   assembly): the compiler's size levers are on its backlog and pay off across the OS and every command.
8. **Console = two BIOS vectors** (charout/uartin today). The video card and PS/2 keyboard replace them later
   without the OS or the commands knowing.

## Phases

1. **Emulator CF model** on ports P8/P9 backed by a disk image (`-d disk.img`, like p8xemu's `-c`), ~150 lines of
   C in `software/emulator/main.c`. **ROM side**: CF driver + B command in `monitor.asm`, tests removed, vectors
   added; proven on the emulator with a P8XFS image whose LBA 1.. holds a test program. Burn = the same ROM
   burn already pending for the G fix. Hardware in parallel: the CF card in KiCad (rails and pull-ups checked
   first, this week's lesson), built, bench-tested with the bus tester before the CPU touches it.
2. **OS kernel v0 in C**: boot into a shell over P8XFS v2 read-only (dir, cd, cat, run, load), then write support
   (save, del, mkdir, pack, format), fsck last. Host-side disk images from `p8xfs.py`.
3. **Commands**: `lib_abi.c` for the YACC1 addresses, then the P8X C commands that fit y1cc (static frames: the
   recursive ones — tree, find — wait for the compiler's stack-frame mode or get rewritten iteratively). BASIC
   re-assembled at a TPA address with its RAM equates moved, as `/bin/basic`.
4. **Video console + PS/2 keyboard**: video card v2 (6845 on PA/PB, 2K RAM), a keyboard controller on a free
   port, both behind the console vectors.

## Still open

- Whether the OS load address stays $1000 if the OS grows past 16K (the map has room to move it; P8X's did twice).
- Dual CF (P8X supports two volumes); a second card at PC/PD would be the direct copy.
- The E-command RAM loader on the backlog becomes unnecessary once the CF card boots; until then it is the only
  way to run compiled programs on the machine.
