# Claude the debugger

*How a bug that appeared only when the computer ran slower was found - October 2026.*

YACC1 is a computer built from scratch out of simple logic chips. There is no microprocessor in it: every instruction
is carried out by *microcode*, a table of control words that switches the cards' signals on and off, one step at a time.

In October 2026 it developed a strange fault. **At 6 MHz it worked and would run for days. At 1 MHz - its intended
speed - it fell over within minutes.** BASIC programs printed nonsense numbers and hung; then even typing in a line of
BASIC failed. A computer that breaks when you slow it *down* is unusual: most timing faults go the other way.

I worked on it with Claude, Anthropic's AI, over three days (8-10 October 2026). This is how it was found.

## The setup

1. **Everything documented in one place** - schematics, card designs, microcode, firmware, the instruction set, the
   bus definition - all in [the repository](https://github.com/ksr/YACC1-D), where Claude could read it.
2. **A console connection**: a USB-serial cable to the YACC1's terminal port, so Claude could use the machine the way
   a person does - monitor commands, typing BASIC programs, running test programs.
3. **The bus tester**: a card on the backplane, reached over USB, that can **drive** any bus line when the CPU cards
   are out, or **listen** to all of them when the CPU is in, taking simple text commands
   ([the bus tester](../cards/bus-tester.md)).
4. **Hands at the bench**: I did the physical work - swapping chips, reseating cards, changing the clock, loading
   firmware - while Claude ran the tests and read the results.

## Chasing the wrong suspects first

The first theories were reasonable - and wrong. That is part of the story.

- **A damaged ROM chip.** The ROM had briefly been powered plugged in backwards. A fresh chip, freshly programmed:
  no help.
- **Damaged chips on the memory card.** The data buffer chip was replaced: no change.
- **New software.** The exact ROM and microcode that had worked weeks earlier went back in - **and it still failed**.
  So something on the machine had changed, not the software.
- **A faulty card.** With the CPU removed, Claude used the bus tester to test **every card on its own** - memory,
  both register cards, the ALU, the I/O card and its front panel. **They all passed.** (One scary moment, when every
  read returned the same value, turned out to be the tester itself leaving a register driving the address bus. Lesson
  learned.)

Throughout, the computer's two software emulators ran every failing program perfectly - which turned out to be a
clue.

## Narrowing it down

- **Divide and conquer.** At 1 MHz most of the machine's test suite failed - but with one thing in common: **numbers
  came out wrong in decimal but right in hex.** The decimal-printing routine takes values off the stack in 2-byte
  words, which pointed at one instruction: **POPR**, "pop a 16-bit register off the stack".
- **A probe program** pushed known values onto the stack and popped them back. Single-byte pushes and pops: fine.
  **POPR: wrong, data-dependent values, every time.** Every other instruction tested: fine.
- **The decisive experiment:** the 6 MHz clock went back in - and **everything passed**. So the fault needed *time*:
  something in the machine was holding a value only briefly - long enough at 6 MHz, not at 1 MHz.

## Single-stepping the machine

To see what POPR really does on the bus, Claude wrote new firmware for the bus tester that made it **the CPU's
clock**: it ticks the sequencer one edge at a time and **reads every bus line after each tick** - a logic analyser
and a single-step button in one.

Stepping through POPR showed it. In the steps where POPR reads the stack from memory, **nothing on any card was
driving the four lines that say which register supplies the memory address.** They were floating.

- **At 6 MHz** each microcode step is so short that the floating lines still held their previous value - which
  happened to be the stack pointer. POPR read the right place, by luck.
- **At 1 MHz** each step lasts six times longer. The lines had time to **drift to "no register"**, the address became
  `$FFFF` - the very top of memory - and POPR read garbage from there.

The schematic confirmed it: a buffer on the sequencer card that normally drives those lines is switched **off**
during exactly the kind of step POPR uses - and **POPR was the only instruction in the whole set that reads memory
during such a step.**

## The fix

The fix was in **microcode, not wiring**: POPR now reads the stack *before* entering that mode, through a temporary
register, while the address lines are still properly driven. Only that one instruction's microcode was reloaded -
and **the machine passed its whole test suite at 1 MHz** (15 of 15; 13 had failed before). The BASIC programs that had
been failing all ran correctly.

## Why the emulators missed it - and what changed

The emulators read "which register" straight from the microcode, as if those lines were always driven; only real
wires can float. The microcode-level emulator now treats those lines as undriven in that mode, and **it reproduces the
exact failure** with the old microcode. Since then it has also gained a debugger with a live view of the YACC1's video
screen and a chip-level model of the video card ([the emulators](../programming/EMULATORS.md),
[the debugger](../../software/y1dbg/README.md)). A broader check - flag any bus line that is read while nothing
drives it, or driven by two chips at once - is in [the backlog](../../BACKLOG.md).

## For the technically curious

- `POPR Rn` read `[SP]` with `-2-BYTE-OPERAND-SEL` asserted (the register number taken from the instruction's operand
  byte). The sequencer's IC18B, which puts the pipeline's ADDR-REG-ID on the bus, is enabled by NOT
  `-2-BYTE-OPERAND-SEL`; the alternative path (IC18A/IC11A) was idle - so ADDR-REG-ID floated during POPR's memory
  read ([the sequencer logic card](../cards/sequencer-logic.md), section 3.6).
- The stepped bus at 1 MHz: ADDR-REG-ID = 15 (no register), address `$FFFF`, data `$05` - the ROM's last byte.
- The fix ([`ad0cef3`](https://github.com/ksr/YACC1-D/commit/ad0cef3)): read `[SP]` into TMP1 with the pipeline's
  normal ADDR-REG-ID, then load the target register from TMP1 under `-2-BYTE-OPERAND-SEL`. One microcode record
  ($08) changed.
- The single-stepper: the bus tester's `bus-stepper` firmware and `tools/busstep.py`
  ([`7aea4f5`](https://github.com/ksr/YACC1-D/commit/7aea4f5)); the emulator's new model:
  `y1ucemu` forces address `$FFFF` while `-2-BYTE-OPERAND-SEL` is asserted (`-O` keeps the old model).
- The day-by-day record of the hunt is in [the backlog](../../BACKLOG.md), under "BASIC programs go wrong at RUN".
