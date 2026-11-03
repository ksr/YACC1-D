# Real-time clock (design note, 2026-11-03)

A battery-backed real-time clock for the YACC1: the time and date for programs, Kermit's timeouts in real seconds
whatever the CPU clock, and file dates on the Y1/OS disk so that `make` can rebuild what is out of date. **Not
designed in KiCad, not built**; this note is the plan and its open questions.

## 1. Why

The machine has no clock or timer. Everything that waits counts loop passes, so its time scales with the CPU clock:

| What | Today | With a clock chip |
|---|---|---|
| Kermit's timeouts (`os/kermit_io.asm`) | `PPS EQU 6528` wait-loop passes = 1 s at 1 MHz; at 2 MHz a "15 s" timeout is 7.5 s | the seconds register: a timeout is N real seconds at any clock |
| The ROM's CF wait (`cfwait`) | at most 65,536 polls; a faster CPU gives up sooner | unchanged (the ROM needs no clock) |
| File dates | none: P8XFS keeps no time, so `make` builds what is missing, `make -B` after an edit (`man make`) | a date on every file closed; `make` rebuilds a target older than a prerequisite, as on Unix |
| The date | none (y1cc's header says `0000-00-00 00:00`) | `/bin/date`; the compiler's header, `dir`'s dates |

## 2. The chip

**DS12C887** (Dallas, now Analog Devices): an MC146818-compatible clock in a 24-pin encapsulated DIP module with its
own 32.768 kHz crystal and lithium cell. Time, date and century, an alarm, a periodic interrupt, a square-wave
output, and about 113 bytes of battery-backed RAM; binary or BCD, 12 or 24 hours. Its register interface is the PC/AT
clock's: a register number, then the register's data, on a multiplexed 8-bit bus. The DS12887 is the same without the
century register.

The data sheet could not be read on 2026-11-03 (the host timed out). **Everything about the chip below is the
MC146818 family's, to verify on the DS12C887 data sheet before the circuit is drawn:** the pin numbers, the bus timing,
RESET's effect, the oscillator's state as shipped, and whether the part is still in production.

Alternatives considered:

| Option | For | Against |
|---|---|---|
| DS12C887 on two I/O ports (chosen) | one part: time, date, battery, RAM; the PC's interface, well known | a 24-pin module, not the cheapest part |
| The video card V2.0's ATmega (PD/PE, 16 MHz crystal) | no new hardware: a firmware reply with a tick count | no battery (the time is lost at power-off: fine for timeouts, useless for file dates); needs that card built |
| 82C54 counter/timer from the UART's 1.8432 MHz | timeouts and ticks | no calendar, no battery |
| DS1307 / DS3231 (I2C) | cheap modules | the bus has no I2C: a bit-banged port or the ATmega |

## 3. Ports

The clock needs two ports, as the PC's $70/$71: one for the register number, one for the data.

| Port | Direction | What |
|---|---|---|
| **P6** | write | the register number (0..127): latched by the chip on AS's falling edge |
| **P7** | read / write | the register P6 selected |

Why P6/P7: the video card V2.0 uses PA-PE, the CF section P8/P9, the I/O card P0/P1, which leaves PF alone in the upper
half. The I/O card decodes P2-P7 (its IC5, strapped to the low half) but nothing on it uses P2-P7: the six selects
only reach its IO-ADDR and DATA-ADDR headers (`docs/cards/io.md` 3.1, `docs/programming/IO-PORTS.md`). A card that
decodes P6/P7 itself does not meet the I/O card on the data bus. **To verify on the I/O card in the machine** before
the RTC answers there: no jumper on IO-ADDR or DATA-ADDR selects P6 or P7.

## 4. The circuit

The CF card v1.0's decode (`hardware/cards/cf/kicad/v1.0`, `docs/cards/cf.md`), on other ports:

```
 IO-ADDR0..3 ──► 74LS138 ── -P6SEL, -P7SEL (A,B,C = IO-ADDR0..2; enabled while IO-ADDR3 = 0)
 -IO-WR, -IO-RD ──► gates:  AS  = P6SEL AND IO-WR        (Intel ALE: the register number latched as AS falls)
                            -WR = NOT (P7SEL AND IO-WR)   (the chip's R/W pin in Intel mode)
                            -RD = NOT (P7SEL AND IO-RD)   (the chip's DS pin in Intel mode)
                            -CS = NOT (P6SEL OR P7SEL)
 DATA0..7 ◄──► 74LS245 (enabled by -CS, direction from -IO-RD) ◄──► AD0..7 of the DS12C887 (MOT = GND: Intel mode)
 IRQ (open drain) ──► jumper INT-EN ──► bus -INT (C13)      SQW ──► test point / LED (optional)
```

About four TTL chips beside the module: a 74LS138, a 74LS08 and a 74LS32 (or one gate package, as the logic works out),
a 74LS245. The 245 keeps the module's weak outputs off the backplane, as on the CF card.

**Timing.** The microcode puts the port number on IO-ADDR0..3 two or three steps before a strobe and holds it to the end
of the instruction; a strobe lasts one step, two clocks: 2 µs at 1 MHz (`docs/cards/cf.md` section 4). Writers take
the data on the strobe's trailing edge, which is also AS's falling edge here, while the data is still on the bus. The
MC146818 family's limits are in the hundreds of nanoseconds (a bus cycle of about 400 ns, strobe widths of about
150 ns): **to verify on the data sheet**; nothing is close at 1 MHz, and even at 6 MHz a step is 333 ns.

**RESET.** On the MC146818 family RESET clears interrupt enables and flags, not the time, the date or the RAM. Tie it to
VCC (the PC does), or to the bus -RESET once the data sheet confirms that. **To verify.**

**Interrupt.** IRQ is open drain, so it can share -INT (C13) with the UART's 7406, through a jumper (INT-EN, off by
default) as the video card V2.0 does with its PS/2 interrupt. Nothing in the ROM or Y1/OS uses interrupts yet, so the
jumper stays off until something does.

**Power-up.** The family needs about 200 ms after VCC rises before the bus may be used, and the oscillator may be
shipped stopped (register A's DV bits) to save the cell: the first `date -s` starts it. **To verify.**

## 5. Where it goes

| Option | For | Against |
|---|---|---|
| **A small RTC card** (the blank card V3.2 outline, generated like the CF card v1.0) | its own card: no change to a built one; the board-layout rules from the start (the INT-EN jumper and an LED at the front edge, labelled; cottageworker.com on the silk) | a slot |
| On the protocard first, hand-wired | quick bring-up of five chips; proves the ports and the software | not the final board |
| A future I/O card or memory card revision | no extra slot | both are built (the I/O card V1.1, the memory card v2.0): only as a new revision |

Proposed: a hand-wired prototype on the protocard to prove the software, then a small card.

## 6. Software

In the order it can be done, all testable on the emulators before the hardware exists:

1. **The emulators' model** (`software/rtcmodel.h`, beside `cfmodel.h`): P6/P7 in both emulators, the time from the
   host's clock, the RAM in memory, register A's UIP never set (or set briefly, to test the reader). `-R` could start it
   at a fixed time for repeatable transcripts.
2. **`os/lib_rtc.c`**: `rtc_present()` (write and read back a RAM byte: an absent card reads as whatever is left on the
   bus), `rtc_rd(reg)`, `rtc_wr(reg, v)`, `rtc_time(buf)` (wait while UIP is set, then read the registers; or read twice
   until two reads agree), `rtc_set(...)`. Binary and 24-hour mode, set once by `date -s`.
3. **`/bin/date`**: `date` prints `2026-11-03 18:42:07`, `date -s 2026-11-03 18:42` sets it (and starts the
   oscillator). A man page and a `help` line.
4. **Kermit** (`os/kermit_io.asm`): if the clock is there, the wait loop counts changes of the seconds register while it
   waits (only on the empty-line path, so the per-character loop keeps its 217 clocks); else `PPS` as now.
5. **File dates.** A P8XFS entry has seven spare bytes (25..31; `tools/p8xfs.py` leaves them alone, a fresh volume has
   them zero). Proposed: bytes 26-27 the time and 28-29 the date in the FAT layout (time: hour 5 bits, minute 6, second / 2
   5; date: year - 1980 7 bits, month 4, day 5; little-endian), 0 = no date. Both kernels stamp a file at CLOSE when
   the clock is there; `p8xfs.py put` stamps the host file's time, `ls` shows it. **The C kernel has 69 bytes free**
   (2026-11-03): the stamping needs room found there first. P8X shares the format: **to verify** that P8X/OS ignores
   bytes 25..31 (`~/Developer/p8x`, read-only).
6. **`make`**: when a target and a prerequisite both have dates, the target is rebuilt if it is older; else today's rule
   (missing, or a prerequisite built in this run). `dir` and `ls` show the dates.
7. **The compiler's header**: y1cc on the machine writes the real date instead of `0000-00-00 00:00` (the selfhost
   test already masks that line).

## 7. Open questions

- The DS12C887's pinout, timing, RESET and shipped oscillator state from its data sheet (sections 2 and 4).
- P6/P7: confirm on the I/O card that no header jumper selects them.
- A card of its own (and which slot), or the protocard first.
- The interrupt: wire INT-EN now (off), or leave it out until the OS has interrupts.
- File dates: the FAT layout in bytes 26-29, and P8X's use of the spare bytes.
