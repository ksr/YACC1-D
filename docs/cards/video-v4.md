# Video card V4 — design note (6845, VGA, 16 dots a count)

**A design note, begun 2026-11-12. Nothing is drawn, ordered or built; "V4" is a working name.** The circuit is
written as a netlist (2026-11-12: `hardware/cards/video/kicad/v4.0/v40_netlist.py`, 46 ICs, its wiring checked and
not yet simulated: section 11). The card in the machine is the [V1.0](video.md). The [V2.0](video-v2.md) is designed, ready to order and on hold while this card is
looked at. The [V3](video-v3.md), round the HD63484, is not built.

The aim is the V2.0 card's picture on monitors sold today: a **VGA** monitor at 31.47 kHz, **80 x 25 characters of
8 x 16 dots** and a **640 x 400 graphics layer**, still made by a **6845**, with V2.0's ports, PS/2 section and
software model. The way there: the 6845 counts **16 dots at a time**, and the card fetches **two bytes in each of its
counts**. The 6845 then runs at 1.57 MHz, inside every grade of the part, where 8 dots a count would need 3.15 MHz.

The figures for the monitor are VGA's. The 6845's are Motorola's as the V2.0 reviews use them (clock low 160 ns, the
memory address 160 ns after the clock) and, for the other outputs, a 300 ns that is assumed: section 13 lists what is
to confirm on the data sheet of the part fitted. No tool computes the figures here yet (`tools/vidsim.py timing` knows
5, 6 and 8 dots a count: to extend).

## 1. The idea: the 6845 counts pairs of bytes

A 6845 does not know how many dots a character has. It counts clock periods: so many in a line, so many shown, a
sync pulse from here to there; and for each one it puts out a memory address (MA) and the scan line within the row
(RA). On the V1 and V2.0 cards a clock period is one character, 6 or 8 dots. Here it is **16 dots: two characters, or
two bytes of graphics**. IBM's CGA does the same in its graphics modes.

| | 8 dots a count | 16 dots a count |
|---|---|---|
| The 6845's clock at VGA's 25.175 MHz | 3.147 MHz | **1.573 MHz** |
| Which 6845 | Hitachi's S type only, at a rating not yet seen on its data sheet (Motorola's: 2.5 or 3.0 MHz) | any |
| Time for the 6845's outputs to settle | 318 ns, of which MA takes up to 160 | 636 ns |
| A line | 100 counts, 80 shown | 50 counts, 40 shown |
| VGA's porches and sync (16, 96, 48 dots) | 2, 12, 6 counts | 1, 6, 3 counts: whole counts either way |
| The cursor | a character wide | a count is two characters: one bit more picks the half (section 6) |

What does not change is the dot path. A byte is wanted every 8 dots, 318 ns, whichever way the 6845 counts: the
character generator looks up a character in that time and the shift registers run at 25 MHz. Those parts are 74F and
74ACT, as on the V3 design, and the look-up has a pipeline stage of its own.

## 2. Against the other cards

| | V2.0 (6845, TV rate) | V4 (6845, VGA) | V3 (HD63484, VGA; not built) |
|---|---|---|---|
| Monitor | 15.75 kHz; 18.4 kHz with an MDA table | VGA, 31.47 kHz | VGA, 31.47 kHz |
| Dot clock | 12 MHz | 25.175 MHz | 25.175 MHz |
| Text | 80 x 24 (6 dots) or 64 x 24 (8 dots), 8 lines a row | 80 x 25 of 8 x 16 | in the bitmap, or a character screen |
| Graphics | 512 x 192, 8 planes of 2K | 640 x 400, 16 planes of 2K | 640 x 480 |
| Who draws | the CPU, through a 2K window | the CPU, through a 2K window | the chip, by command |
| The window against the CPU's clock | to 1.8 MHz with the layer shown; to the machine's own limit, about 6 MHz, with it hidden (direct mode) | to about 3.5 MHz shown (an estimate); to about 6 MHz hidden (direct mode, as V2.0's) | no window |
| The CPU's view | text RAM at $D000, the window at $D800, ports PA-PE | the same, and port PF | ports only |
| Text RAM / graphics RAM | IDT7134 / 62256 (32K, two pages) | IDT7134 / 128K part (64K used, two pages) | two 128K RAMs |
| Keyboard and mouse | PS/2 on an ATmega328P | the same section | the same section |
| Outputs | RCA, DB9 | DE-15 | DE-15 |
| ICs | 40 | 46 (the netlist) | 47 |

## 3. Monitor timing and the 6845's table

A count is 16 dots, 635.6 ns. A line is 800 dots, 50 counts: 31.469 kHz.

**640 x 480 at 60 Hz, the text in a band of 400 lines** (the card's table):

| Register | Value | What |
|---|---|---|
| R0 | 49 | 50 counts a line |
| R1 | 40 | 40 shown: 80 characters, 640 dots |
| R2 | 42 | the sync from count 42: with the card's pipeline (section 5) a front porch of about 19 dots and a back porch of about 45, where VGA's are 16 and 48 |
| R3 | $26 | the horizontal sync 6 counts (96 dots); the vertical sync 2 lines on Hitachi's S type (Motorola's ignores the upper half and makes 16: section 10) |
| R4, R5 | 31, 13 | 32 rows of 16 lines and 13 more: 525 lines, 59.94 Hz |
| R6 | 25 | 25 rows shown: 400 lines |
| R7 | 28 | the vertical sync at row 28, line 448: the text lands on lines 42-441 of the monitor's 480 |
| R8 | 0 | not interlaced |
| R9 | 15 | 16 scan lines a row |
| R10, R11 | $6E, 15 | the cursor on scan lines 14-15, blinking every 32 frames ($60, 15: a block) |
| R12, R13 | 0 | the start address, in counts |
| R14, R15 | | the cursor's count: (row x 80 + column) / 2 |

Both syncs negative. 80 lines of the monitor's 480 stay black, 42 above the text and 38 below.

**640 x 400 at 70 Hz** (VGA's own text raster, the same clock; the picture fills the screen): R4, R5 = 27, 1 (449
lines, 70.09 Hz), R7 = 26 (the sync at line 416), the rest as above; HSYNC negative, VSYNC positive. The 6845 places
the vertical sync by whole rows, so the picture starts 4 lines above where VGA's 400-line mode has it: for the
monitor's own adjustment to take up, and to try. The two polarities are control bits (section 9), so the driver
chooses the raster with its table.

A screen is 2,000 characters, which the 2K at $D000 holds. Thirty rows on the 480 lines would be 2,400: not on this
card (section 13).

## 4. Block diagram

```
 YACC1 bus                    as V2.0                              25.175 MHz oscillator
 ADDR, -MEM-RD/-WR --> block select ($D000) ----+                        |
 IO-ADDR, -IO-RD/-WR --> port decode PA-PF      |                 74F163A: dots 0-15 of a count
 DATA0-7 <--> the 6845's registers (PA, PB)     |                   |  top bit, a dot late --> the 6845's clock
          <--> control 1, control 2, status     |                   |
          <--> PS/2 latches (PD, PE)            |   6845: MA, RA, DE, CURSOR, HSYNC, VSYNC
                                                |                   |  taken as each count ends
                              CPU port          |             the stage registers (2 x 74ACT574)
 $D000-$D7FF <--> IDT7134 text RAM <-- display port: MA9..0, then the half (0 left, 1 right)
                        |
                  code register --> character generator (code, RA, cursor) --> 74F299 --+
                                                                                        |--> mix, retime
 $D800-$DFFF <--> 128K RAM, four slots a count: display, CPU, display, CPU              |    --> R G B
                        |          address: page, RA, MA, half / page, plane, ADDR      |
                        |          GFX-ON = 0, direct mode: the CPU's alone             |
                  byte latch --> 74F299 -------------------------------------------------+
                                                 HSYNC, VSYNC --> two lines --> polarity --> DE-15
 PS/2 keyboard and mouse: the V2.0 card's section
```

## 5. The clock and the stage: one count, dot by dot

**The dot counter.** A 25.175 MHz oscillator clocks everything. A 74F163A counts the 16 dots of a count: its bits
are D3..D0, and "as dot n begins" below is the clock edge at which it becomes n.

**The 6845's clock** is D3 passed through a flip-flop: the counter's top bit a dot late, low 8 dots and high 8
(318 ns each; the V2.0 reviews' figure for Motorola's part is 160 ns low). The 6845 steps as its clock falls, as
dot 1 begins.

**The stage.** Two 74ACT574 take the 6845's outputs **as dot 0 begins**: MA9..0, DE, CURSOR, HSYNC and VSYNC, all for
the count that is just ending. They have had 596 ns to settle, against 160 ns (MA) and 300 ns (the others); and the
6845 does not move until a dot later, so nothing is taken while it changes. From here on nothing depends on the
6845's own delays: the rest of the card sees addresses and flags that change once a count, on a clock edge, and stay
16 dots. RA needs no register: it changes once a line, in the blanking.

**No clock is a decode of the counter** (the V3 design's rule, from its timing check: a gate that decodes two counter
bits can give a pulse a nanosecond wide where one rises as another falls). The clocks here are counter bits
themselves, or a flip-flop's output; decodes go only to D inputs and to loads.

The count after the stage has taken MA, dot by dot:

| As dot begins | Text | Graphics RAM |
|---|---|---|
| 0 | the stage has the count's MA; the half is 0: the text RAM reads the **left** character | **display** slot: the left byte |
| 4 | the code register takes the left character's code, with its cursor flag (clock: D2) | the byte latch takes the left byte (clock: D2); the **CPU's** slot begins |
| 5, 6 | | -WE, when a write waits |
| 8 | the half is 1 (D3): the **right** character; DE moves a stage on (SDE2), for the two loads to come | **display** slot: the right byte; the CPU's read latch has taken its byte |
| 12 | the code register takes the right code; the shift register loads the left character's dots | the byte latch takes the right byte; the shift register loads the left byte; the **CPU's** slot |
| 13, 14 | | -WE, when a write waits |
| 4, in the next count | the shift register loads the right character's dots | the shift register loads the right byte |

So a count's 16 dots leave the shift registers from dot 12 of the count after, text and graphics side by side, and
reach the connector a dot later (the retiming flip-flop of section 8).

**The time each stage has**, with the parts at their slowest:

| Stage | Has | Needs |
|---|---|---|
| The 6845's outputs to the stage registers | 596 ns | 160 ns (MA); 300 ns (the others, assumed) |
| The text RAM: address to the code register | 159 ns a half | about 31 ns for the address and 55 to 90 ns for the IDT7134, by grade |
| The character generator: code to the shift register's load | 318 ns | about 22 ns for the code and 150 ns for the AT28C64B-15 |
| The graphics RAM, a display slot: the stage, direct mode's gate in the select and the multiplexer, then the RAM, to the byte latch | 159 ns | about 45 ns and 55 ns |
| The graphics RAM, a CPU slot's write | 159 ns | a write pulse of 79 ns (45 wanted), the data 25 ns before it ends |
| The graphics RAM, a CPU slot's read: the multiplexer, then the RAM, to the read latch | 159 ns | about 35 ns and 55 ns |

Of these set-up times nothing is closer than about 35 ns, and that with a 90 ns text RAM. One hold time is close:
the read latch's (section 7), a few nanoseconds, for the simulation to give its figure. V2.0's graphics RAM changes hands every 333 ns
and the V3 design's memory cycle is 318 ns with an 80 ns write pulse: these are the same order, and the netlist is to
be timed as V3's was, with the parts' data-sheet numbers (`tests/video/v30_netsim.py` has the models of these parts).
The table is slot mode's. In direct mode (section 7) the graphics RAM follows the CPU's strobes and not the dot
counter: its margins are V2.0's kind, computed against the microcode.

## 6. Text

**The RAM** is V2.0's: one IDT7134 dual-port RAM, the CPU on one port at $D000-$D7FF, the display on the other. The
CPU never waits and the display never sees it. The display's address is **MA9..0 from the stage, then the half**:
character n of the screen is byte n at $D000, n = row x 80 + column, as today. The card reads the RAM twice a count,
the left character in the count's first 8 dots and the right one in the last 8.

**The character generator** is addressed by the code, the scan line RA3..0 and the cursor flag: 256 glyphs of 16
lines, twice: 8K, an AT28C64B-15 as on V2.0. Bit 7 of a byte is the left-hand dot. The font is to choose (section 13).

**The pipeline.** A code waits in the code register (74ACT574) while the generator looks it up, a whole 8 dots; its
dots load into a 74F299 as the next code is taken. The right character of a count is so on the screen directly after
the left one, and the count after it follows without a gap.

**Blanking.** DE travels with the characters: the stage, then a flip-flop as dot 8 begins. A character whose DE is low
is not loaded, and the shift register, its serial input low, runs empty: the picture ends on a character's last dot
with no gate in the dot's path (the V3 design's way).

**The cursor.** The 6845 compares MA with R14 / R15 and raises CURSOR for a whole count, on the scan lines R10 / R11
name, blinking as R10 says. A count is two characters, so one control bit, **CURH**, says which: the cursor flag of a
character is CURSOR AND (its half = CURH), taken with its code. The flag is an address line of the character
generator: the upper half of the EPROM holds each glyph's cursor form (turned over, or what the image holds), so the
cursor is in the dots when they are loaded and needs no gate after the shift register. The driver writes R14 / R15
with the character's number halved, and its lowest bit to CURH.

**Scrolling** can be the 6845's: the start address (R12 / R13) moves the screen a row for 40 counts, and the RAM's
address wraps at 1,024 counts, 2,048 characters, 48 more than a screen. The graphics layer is addressed by the same
MA and moves with the text.

## 7. Graphics

**640 x 400, one bit a dot, two pages.** A plane is one scan line of every row, laid out as the text is: byte n of
plane p holds scan line p of the cell under character n. Sixteen planes of 2K are a page of 32K; two pages, one shown
(DPAGE) and one the CPU reaches (CPAGE), are 64K: half of a 128K x 8 static RAM of 55 ns (AS6C1008-55, DIP-32, the
part of the V3 design).

**The CPU's window** is V2.0's, $D800-$DFFF: 2K, one plane, chosen by the control register's PLANE (now four bits)
and CPAGE. Dot (x, y) is bit 7 - (x mod 8) of the byte at

```
$D800 + (y / 16) x 80 + x / 8        in plane y mod 16
```

**The RAM's address.** For the display: DPAGE, RA3..0, MA9..0, the half. For the CPU: CPAGE, PLANE3..0, ADDR10..0.
Four 74ACT157 choose between them.

The RAM has two modes, as on V2.0, chosen by the control bit GFX-ON: **slot mode** with the layer shown, and
**direct mode** with it hidden.

**Slot mode (GFX-ON = 1): four slots a count.** The RAM belongs to the display in dots 0-3 and 8-11 and to the CPU in
dots 4-7 and 12-15: the multiplexers' select is the counter's D2, through direct mode's gate. A display slot reads one
byte, which a latch takes at the slot's end (the clock of the text's code register) and the graphics 74F299 loads
with the text's dots. A CPU slot comes every 318 ns and is 159 ns long:

- **A write** is taken as a slot begins (V2.0's WRQ) and -WE is low in the slot's two middle dots, a flip-flop's
  pulse. The write buffer is enabled by -WE itself, as on V2.0. A 2 us strobe writes the byte several times.
- **A read**: a latch takes the RAM's byte as every CPU slot ends and drives the bus while the window is read. Its
  clock is a flip-flop's pulse in dots 8 and 0, so the whole slot is the RAM's access time. The latch's clock and the
  address's change then come from the same edge of the dot clock: the latch is a 74ACT574 for its 1 ns of hold, and
  on paper about 6 ns are left (the multiplexers' own delay and the RAM's 10 ns of output hold against the
  flip-flop's delay).

A strobe that holds one whole CPU slot is enough: about 480 ns, a wait of up to 318 for the slot and the slot's 159.
The YACC1's strobes are a microcode step, 2 us at 1 MHz, so slot mode works up to a CPU clock of about 3.5 MHz (V2.0's
slot mode: 1.8 MHz): an estimate, to be worked out on the netlist as V2.0's was (`tests/video/v20_timing.py`).

**Direct mode (GFX-ON = 0, the reset state; decided 2026-11-12)** is V2.0's. The CPU owns the RAM and the window is a
plain static RAM, with no slot to wait for. The machine's own limit is about 6 MHz, where a strobe is 333 ns: less
than a slot-mode access needs, and enough for a RAM of 55 ns that is the CPU's alone. Without this mode the card
would hold a machine that draws to 3.5 MHz.

- **The address**: the multiplexers' select is D2 OR NOT GFX-ON, so the CPU's address is held for good. This is the
  one gate direct mode puts into slot mode's path (section 5).
- **A write**: -WE is the window's write strobe itself: the write flip-flop is held preset and the pulse's term
  forced, as on V2.0. The write buffer follows -WE, as in slot mode.
- **A read**: the RAM's outputs are on only while the window is read, and a buffer (74HCT244, V2.0's IC55) passes them
  to the bus in place of the read latch, whose outputs are then off. A 10k x 8 network holds the RAM's data lines
  between accesses, when nothing drives them.
- **The display**: the layer is not shown. GFX-ON low holds the graphics 74F299 clear (section 8), so what the byte
  latch takes in this mode never reaches the screen.

A program draws at full speed with the layer hidden and shows it with GFX-ON = 1. The second page does not change
that: to draw on the hidden page while the other is shown the display needs its slots, so that is slot mode's, to
about 3.5 MHz. Above it the order is hide, draw, show.

**The rules for the window** are V2.0's (`hardware/cards/video/kicad/v2.0/README.md`, "The software rules for the
window"):

1. No code in the window, at any clock.
2. At 6 MHz, no stack and no BRVR vector table in the window.
3. Above about 3.5 MHz, the window only in direct mode.
4. The instruction that writes control 1 does not access the window: entering slot mode, the write flip-flop stays
   preset until the next slot (at most 318 ns), and a write begun in that time could open -WE in the middle of one.
5. GFX-ON is switched in vertical blanking (IN PC bit 1): the bytes the pipeline took in direct mode are then never
   loaded, where they would show once as up to 16 dots.

Rules 1 and 2 are the register cards': a register counted in the step it is read through settles late, whatever the
video card does, so faster parts here do not lift them. The margins are to be computed on the netlist against the
microcode's strobes, as V2.0's were. V2.0 has 38 ns of read margin at 6 MHz on a selected register, with a RAM of
the same 55 ns and 74LS157 multiplexers; this card's are 74ACT157, so that figure or better is to be expected, and is
not yet computed.

**The text-only build** is V2.0's: the graphics parts left off (eleven ICs and the network), with three 10k
resistors that are fitted in both builds: one holds the graphics dot low, one the write flip-flop's output, and one
pulls the status bit TEXT-ONLY high. No resistor is fitted for this build only.

## 8. The dot path, the syncs and the connector

- **Two 74F299**, one for each layer, shift bit 7 first. TEXT-OFF holds the text register clear and GFX-ON low the
  graphics register, so a layer that is off costs no gate in the path of the other.
- **The layers mixed**: text OR graphics, or XOR with the control bit, as V2.0; then a flip-flop on the dot clock, so
  that every dot reaches the guns one clock wide whatever the gates before it did.
- **Three guns**: a gate for each with its off bit (control 2), then 470 ohm to the DE-15's pins 1, 2, 3: 0.7 V
  into the monitor's 75 ohm. White, or one of seven other colours for the whole picture.
- **The syncs** come from the stage registers, so their edges are the dot clock's. VSYNC is cut to about two lines by two
  flip-flops that count HSYNC, which makes the card indifferent to the 6845's own pulse (section 10). Two XOR gates
  give each sync either polarity; pins 13 and 14; the returns pins 5-8 and 10.
- **VGA only**: one DE-15 at the front edge, right-angle, facing out. No RCA jack, no DB9, no halved clock: V1.0 and
  V2.0 are the cards for TV-rate monitors. (The crystal halved would give the TV rate with the same table.)

## 9. The bus side: ports and registers

V2.0's, with the spare port taken: the $D000 block (74S85 and SV3), the port decode (74LS138, two 74LS32), the 6845
on PA / PB with E made from the two I/O strobes, the PS/2 section on PD / PE.

| Port | IN | OUT |
|---|---|---|
| PA | - | 6845 address register |
| PB | 6845 data (R14-R17) | 6845 data |
| PC | status: bit 0 = 0, 1 VSYNC, 2 DE, 3 TEXT-ONLY, bits 7..4 = 0111, **the card ID $7x** | **control 1**: bits 3..0 PLANE, 4 CPAGE, 5 DPAGE, 6 GFX-ON (0 = direct mode), 7 XOR |
| PD | PS/2 status: FULL, SRC, BUSY | PS/2 command |
| PE | PS/2 data | - |
| PF | - | **control 2**: bit 0 TEXT-OFF, 1 CURH (the cursor on the right-hand character of its count), 2 HSYNC positive, 3 VSYNC positive, 4 spare, 5 red off, 6 green off, 7 blue off |

-RESET clears both control registers: plane 0, page 0, text on, graphics off and its RAM in direct mode, both syncs
negative, white. That is what 640 x 480 wants, so a driver that only loads the 6845's table has a picture.

The status's VSYNC and DE are the stage's: what the 6845's pins showed a count before. VSYNC there is the 6845's
own pulse, 16 lines of Motorola's part, not the two lines the connector gets.

Against V2.0: PLANE has a fourth bit, so CPAGE, DPAGE and TEXT-OFF have moved, and control 2 is new; the status has no
DOTS bit (8 dots only: the jumper is gone); the ID is $7x where V2.0 reads $5x and the V3 design $6x.

## 10. Which 6845

Any grade runs at 1.57 MHz. Two things still differ between the makers' parts:

- **The vertical sync's width.** Motorola's MC6845 makes it 16 lines, always; Hitachi's S type takes it from the
  upper half of R3. VGA's is 2 lines. The card cuts it to two lines itself (section 8), so either part gives the same
  pulse; R3 = $26 is right for both.
- **The bus side.** As on V2.0: the B grade (HD68B45SP, MC68B45P) for a CPU clock above 1 MHz, where E is shorter than
  the 1 MHz grade's 450 ns.

At the machine's 1 MHz the 6845 of the V1.0 card can be tried on this card as it is.

## 11. The parts and the board

| Block | Parts | ICs |
|---|---|---|
| Bus, ports, registers | as V2.0: 74S85, 74LS138, 2 x 74LS32; two 74HCT273 where V2.0 has one; the status buffer (74LS244); 74HCT04, 74HCT08 | 9 |
| The 6845 and the clock | the 6845; a 25.175 MHz oscillator (DIP-14 can) in place of the crystal circuit and the DOTS logic; 74F163A, 74F74 (the 6845's clock, DE's delay), 74ACT04 | 4 |
| Text | IDT7134; 2 x 74ACT574 (the stage); 74ACT574 (the code); AT28C64B-15; 74F299; 74F74 (the cursor flag, the retimed dot); 74F21 (the load); 74ACT86; 74ACT08 | 10 |
| Graphics, left off in the text-only build | 128K RAM; 4 x 74ACT157; the write buffer (74ACT244), the read latch (74ACT574), direct mode's read buffer (74HCT244), the byte latch (74ACT574); 74F299; 74F74 (the write flip-flop, TEXT-ONLY); a 10k x 8 network | 11 |
| Slot logic, dots and syncs | 74F74 (the -WE pulse, the read latch's clock); 74ACT32, 74ACT00, 74ACT11; 74ACT02 (the guns); a 74HCT74 for the vertical sync; 3 x 470 ohm, the DE-15 | 6 |
| PS/2 | V2.0's section as it is: ATmega328P, two latches, the status, the flags, the 7416; two Mini-DIN-6, the FTDI header | 6 |
| | | **46** |

The count is the netlist's (`hardware/cards/video/kicad/v4.0/v40_netlist.py`, 130 parts; its README has the list by
reference). The first estimate here was 42 or 43: the netlist needs four 74F74 where two were counted, and an
inverter and an AND package more. Every gate package is full or one gate short of it, but for the PS/2 section's
7416 (three of six used, as on V2.0).

**The card's length is open again.** V2.0's 40 ICs fill the 218 mm card. The V3 design's first placement found 39
ICs at about 218 mm and 47 at about 250 mm (`video-v3.md` section 10), and chose 250 mm. 46 ICs, four of them
0.6 inches wide, are to be expected at about 250 mm: the first placement says. Two ways to 44 ICs were left out of
the netlist, each a step away from V2.0's proven circuit (section 13).

The board: four layers with the planes, the blank card's connector, and the layout rules from the start - the DE-15
and the two PS/2 jacks at the front edge facing out, jumpers and the FTDI header at an edge, every reference and value
on the silk outside its part, bypass capacitors on 0.1-inch leads, `cottageworker.com`. `pcb-check` before any order.

**From V2.0, unchanged:** the bus connector and the block select, the port decode, the 6845's bus side, the text
RAM's CPU port, the PS/2 section with its firmware (`embedded/video-ps2`), the text-only build's idea, direct mode
(its read buffer, its pull-ups and its rules).
**New:** the clock and the stage, the two fetches a count, the character generator's pipeline, the four slots, the
dot path at 25 MHz, the second control register, the syncs, the DE-15.
**Gone:** the DOTS jumper and the 6-dot mode, the RCA jack and the DB9 with their drivers and the VSYNC jumper, the
crystal circuit.

## 12. Software

On the branch `video-v2`, beside the V2.0 card's:

- **The ROM driver**: the card by its ID, $7x; the table of section 3; 80 columns and 25 rows (the ROM and Y1/OS
  have 24 rows today: the screen's height becomes the card's); the cursor as R14 / R15 and
  CURH; PLANE's four bits and the moved control bits, with a copy of control 2 kept in RAM (it cannot be read back);
  GFX-ON left 0 on a text-only card and switched only in vertical blanking. The keyboard is V2.0's code unchanged.
- **The emulators' model** (`software/videomodel.h`): a third card beside `v1.0` and `v2.0`: 16 dots a count, two
  bytes, sixteen planes, the two control registers, the layer hidden while GFX-ON = 0. `tools/vidsim.py` draws it and
  checks the table.
- **Graphics**: what is open for V2.0 (drawing routines, in Y1/OS or a library; `video`) is open here in the same
  way, at 640 x 400 and under the same rules for the window (section 7): drawn in direct mode with the layer hidden,
  or in slot mode with it shown.

## 13. Decided, to decide, and to confirm

**Decided (2026-11-12)**
- 16 dots a count, two bytes fetched in each: the 6845 at 1.573 MHz.
- Direct mode, as V2.0's (GFX-ON = 0): the window follows the machine to its own limit, about 6 MHz, with the layer
  hidden; slot mode, with the layer shown, to about 3.5 MHz. One 74HCT244, a resistor network and about six gates.
- 25 rows of text. The ROM and Y1/OS use 24 today.
- One RAM read twice a count for each layer, not two RAMs side by side (which would give a slot of 318 ns in place
  of 159, at the price of a second 48-pin text RAM, a second graphics RAM and a second set of buffers and latches).

**Proposed here, to decide**
- **The raster**: 640 x 480 at 60 Hz with the text in a 400-line band, as the card's table; 640 x 400 at 70 Hz as a
  second table for the driver to offer.
- **The control bits' places** (section 9), which are not V2.0's. The netlist is wired to them.
- **The card's length**: 218 mm or 250 mm (section 11), for the first placement to say.
- **46 ICs or 44.** Two ways down, neither in the netlist:
  - the read latch as a transparent latch (74ACT573) held open in direct mode, in place of the latch and direct
    mode's buffer: one 20-pin chip less, and a latch enable to make where there is a clock now;
  - the four flip-flops on the dot clock (the 6845's clock, the retimed dot, the -WE pulse, the read latch's clock)
    in one quad part (74F175) for two 74F74: one chip less, and a part the V3 design's timing check has no model of.
- **The font**: 256 glyphs of 8 x 16 with lower case, and their cursor forms. V2.0's fonts are 8 lines high; the V3
  design's first image is the V1.3 glyphs with each line doubled.
- **V2.0**: ordered as well, or left as it is.

**Possible later, not in this design**
- 80 x 30 and 640 x 480 graphics: 2,400 characters and 1,200 counts a plane, more than the two 2K windows hold.
- The other two pages of the 128K RAM.
- A second font: a 32K EPROM and control 2's spare bit.

**To confirm**
- On the 6845's data sheets: the delays of DE, CURSOR, HSYNC and VSYNC from the clock (300 ns is taken here; the stage
  allows 596); that Motorola's part ignores R3's upper half; the clock's rating, for the record.
- On a monitor: the 16-dot granularity of the horizontal porches (19 and 45 dots for 16 and 48); the two-line
  vertical sync; the 400-line raster's 4 lines.
- The 128K RAM in DIP-32 and the IDT7134 in stock; the grade of the IDT7134 in hand.
- On the netlist: slot mode's limit (about 3.5 MHz is an estimate) and direct mode's margins at 6 MHz.

**Order of work**
1. This note, checked.
2. The netlist, from V2.0's (`v20_netlist.py`), with its own checks: **written 2026-11-12**
   (`hardware/cards/video/kicad/v4.0/v40_netlist.py`; its checks pass and are in `make check`).
3. The netlist simulated and timed with the parts' data-sheet numbers, as V3's was.
4. Beside it: the emulators' model and the ROM driver.
5. The schematic and the board, `pcb-check`, a design review; then the order.
