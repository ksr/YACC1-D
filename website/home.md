---
hide:
  - navigation
  - toc
---

# YACC1 — Yet Another Custom CPU

![YACC1 on the bench: the cards stacked on the bus, LEDs, hex displays and LCD lit, next to a Mac running a monitor and BASIC session](media/system1.jpg)

*YACC1 on the bench, with a monitor and BASIC session on the Mac's terminal.*

**YACC1 is a computer built from scratch out of 74-series TTL logic chips** — no microprocessor, no FPGA, not even a
74181 ALU chip. Its CPU is spread over cards plugged into a backplane, and every instruction is carried out by
**microcode**: a table of 64-bit control words, one per clock step, that switches the cards' signals on and off.
Around the hardware sits a complete software stack: a monitor in ROM, BASIC, a disk operating system, and a C compiler
written for it.

I'm Ken Rother, and I designed and built YACC1. Claude, Anthropic's AI, has been directly involved in its design,
coding and documentation.

[:material-play-circle: Watch it run](https://youtu.be/6pjIE4_MxIA){ .md-button .md-button--primary }
[:material-github: Source on GitHub](https://github.com/ksr/YACC1-D){ .md-button }
[:material-home: My other projects](https://cottageworker.com){ .md-button }

## At a glance

| | |
|---|---|
| **Data path** | 8-bit, accumulator-based ALU with carry, shifts and a compare unit |
| **Registers** | eight 16-bit registers, R0–R7 (R0 is the program counter, R1 the stack pointer) |
| **Address space** | 64K: 52K of RAM, the 8K ROM, and 2K of video memory at $D000 |
| **Instructions** | around 80, all microcoded: 256 opcodes × up to 64 steps × a 64-bit control word |
| **Construction** | TTL chips on cards plugged into an 8-slot, 96-pin backplane |
| **Clock** | 1 MHz (it has been seen running at 6 MHz) |
| **Console** | serial at 38400 baud, to a Mac over USB |

## What it runs

- **The monitor ROM** — examine and change memory and registers, load programs from a Mac, run them; BIOS entry points
  for programs. ([Monitor guide](docs/programming/MONITOR.md))
- **BASIC** — a Tiny BASIC I wrote for YACC1, in the same ROM.
- **Compiled C** — programs built by **y1cc**, a C compiler for YACC1, run on the machine and pass the same tests as on
  the emulator. ([C compiler](docs/programming/C-COMPILER.md))
- **Y1/OS** — a disk operating system with a shell, pipes and dozens of commands, among them an editor, an assembler
  and a C compiler that run on YACC1 itself. It runs on the emulators today and moves to the machine with the
  CompactFlash interface. ([Y1/OS](docs/programming/OS.md))
- **Two emulators** on the Mac: one runs YACC1 programs instruction by instruction; the other runs the real microcode
  step by step through models of every card. ([Emulators](docs/programming/EMULATORS.md))

## The cards

<div class="grid cards" markdown>

-   ![Sequencer logic and memory cards](media/sequencer-top.jpg)

    **[Sequencer](docs/cards/sequencer-logic.md)** — fetches each instruction and steps through its microcode; the
    [microcode memory](docs/cards/sequencer-memory.md) rides on top.

-   ![ALU card](media/alu-v3.2-top.jpg)

    **[ALU](docs/cards/alu.md)** — the 8-bit arithmetic and logic unit, the accumulator, carry and the branch
    conditions.

-   ![Index register card](media/index-register-v1.1-top.jpg)

    **[Index registers](docs/cards/register.md)** — two cards of four 16-bit counting registers each.

-   ![Memory card](media/memory-v1.2-top.jpg)

    **[Memory](docs/cards/memory.md)** — RAM, the ROM and the boot logic (V1.2 shown; V1.3 is in the machine,
    and V2.0 adds a disk).

-   ![I/O card](media/io-v1.1-top.jpg)

    **[I/O](docs/cards/io.md)** — the serial console, switches, LEDs, hex displays and an LCD.

-   ![Bus tester](media/test-board-v1.1-top.jpg)

    **[Bus tester](docs/cards/bus-tester.md)** — drives or reads every bus line from a serial console, to test each
    card without a CPU.

</div>

Also: the [backplane](docs/cards/backplane.md), the [video card](docs/cards/video.md) (in bring-up), the
[CompactFlash interface](docs/cards/cf.md) (designed), and the two 16-byte cards used for the first bring-up — a
[switch ROM](docs/cards/mem-switch.md) and a [RAM made of latches](docs/cards/mem-register.md).

## Where to start

| If you want to... | Read |
|---|---|
| understand how it works | [Architecture](docs/system/ARCHITECTURE.md), then [Microcode](docs/system/MICROCODE.md) |
| see what one instruction does, clock by clock | the [timing diagrams](docs/isa/README.md) |
| program it | the [instruction set](docs/programming/ISA-REFERENCE.md), the [memory map](docs/programming/MEMORY-MAP.md) and the [monitor](docs/programming/MONITOR.md) |
| look at the hardware | the [cards](docs/cards/README.md) and the [boards that were made](hardware/FABRICATED.md) |
| know what is in the machine right now | [What is in it today](docs/system/MACHINE.md) |
| see what is being worked on | [Status and backlog](BACKLOG.md) |

## Status (October 2026)

- **Working on the machine:** the monitor, BASIC, and compiled C programs — all 14 bench tests pass.
- **Ready, waiting to be loaded into the machine:** new microcode that runs programs about 20% faster, and a ROM with a
  video driver.
- **Next:** memory card 2.0 with a CompactFlash disk, so Y1/OS can boot on the real machine; bringing up the video
  card; finding out how fast the machine can be clocked.
