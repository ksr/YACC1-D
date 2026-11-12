# Video card V3 — design note (HD63484 ACRTC, VGA)

**A design note, begun 2026-11-11. The card is not built for the YACC1 (decided 2026-11-12).** The design stops where
it stood that day: the circuit as a netlist, simulated gate for gate and timed with the parts' data-sheet numbers,
the schematic drawn from it, the emulators' model of the chip and a ROM that drives it. No board was laid out;
nothing was ordered or built. The design is kept as the starting point for a video card on another machine: section
13 sorts it into what holds on any bus and what is the YACC1's. "V3" is a working name. The card in the machine is
the [V1.0](video.md); the [V2.0](video-v2.md) is designed and not ordered.

**Decided 2026-11-11** (section 12): text by method B first, on a board laid out from the start to take method A's
parts; the font in an EPROM on the card, so the screen shows the boot; the card carries the PS/2 keyboard and mouse;
V3 goes ahead whether or not V2.0 is ordered. The emulators' model of the card is on the branch `video-v2`
(`Y1VID_CARD=v3`).

The aim is more graphics resolution than V2.0's 512 x 192, on monitors sold today, with a CRT controller of the 6845's
family. The plan: Hitachi's **HD63484 ACRTC** (the "advanced CRTC", the HD6845's successor) driving a **VGA** monitor
at **640 x 480**, one bit a dot to begin with, on a board that can grow to 800 x 600 and 1024 x 768 (section 9).
Two **HD63484P8** are in hand: the 8 MHz grade, in the 64-pin plastic DIP with 2.54 mm pin spacing.

Sources: Hitachi's *HD63484 ACRTC User's Manual* (1985, U75) and *Application Note* (1986, U90), both on bitsavers
under `components/hitachi/_dataBooks` (a copy of each is kept outside the repository, in
`../private-resources/YACC1-D/docs/datasheets/`); section and table numbers below are the manual's. `tools/acrtc_timing.py`
computes every clock and register figure here (`--check` in `make check`). Where a figure is an estimate, or a point is
still to confirm from the manual or a data sheet, the text says so.

## 1. Why this chip

| | V2.0 (6845) | V3 (ACRTC) |
|---|---|---|
| Monitor | 15.75 kHz (TV rate, CGA); 18.4 kHz with an MDA table | VGA, 31.47 kHz: most LCDs and VGA-to-HDMI adapters; the same crystal halved is the TV rate |
| Graphics | 512 x 192, one bit a dot | 640 x 480, one bit a dot, on two RAM chips; more with wider memory (section 9) |
| Who draws | the CPU, a byte at a time through a 2K window with plane and page bits | the chip: 38 commands (line, rectangle, circle, ellipse, polygon, fill, copy, ...) at about a microsecond a dot |
| The CPU's view | text RAM at $D000, the window at $D800, five ports | **ports only**: the chip's two registers. Nothing in the $D000 block |
| Text | the 6845, an IDT7134 dual-port RAM, a character generator | two ways, section 8: the chip's own character screens, or glyphs copied in the bitmap |
| Scrolling | the ROM moves 1,840 bytes | a start-address write, or one copy command the chip executes |

The YACC1 runs about 40,000 instructions a second. Drawing a dot in software is some tens of instructions, about a
millisecond; a line across a 640-dot screen would take most of a second. The chip draws 2 million dots a second at
8 MHz (the manual's figure; about 1.6 million at this card's 6.29 MHz), so what limits the machine becomes the few
bytes a command takes to send.

## 2. The chip in a page

- **Host side.** Two addresses (RS): the address register / status register, and the data. An **8-bit bus mode**
  (D0-D7), chosen by DACK low at the rising edge of RES. 16-bit registers and commands go high byte, then low byte.
  Registers r80-rFF step the address register by themselves, so a table loads with one address write.
- **Commands** go through a 16-byte write FIFO at register r00: a 16-bit operation code, then 16-bit parameters.
  Results come back through a read FIFO. The status register says FIFO ready / empty and command end.
- **Memory side.** A 20-bit address (1 M words of 16 bits for graphics) on a multiplexed address / data bus
  MAD0-MAD15 plus MA16-MA19; AS latches the address, MCYC is the memory cycle, MRD the direction, DRAW tells a
  drawing access from a display access. Display data never passes through the chip: the RAM's outputs go straight to
  the shift registers.
- **Four screens**: three bands (Upper, Base, Lower) and a Window, each with its own start address and memory width,
  each either **graphic** or **character** (MWR bit 15). For a character screen the chip puts the raster address on
  RA0-RA4 (up to 32 lines a character) and CHR high, for an external character generator: the 6845's job.
- **Three access modes** (OMR): *single* - one memory access a display cycle, drawing and display compete;
  *interleaved* - two a cycle, one for display and one for drawing; *superimposed* - two a cycle, the background
  screen and the Window, laid over each other, with the Window's half used for drawing wherever the Window is not
  on the line.
- **Clock.** 2CLK, 1 to 8 MHz on this grade. A memory cycle is two 2CLK cycles (the address, then the data). The
  horizontal timing registers count memory cycles, the vertical ones rasters.

## 3. Monitor timing and the clock

The memory cycle rate is `dots x bits a pixel x (1 single, 2 dual) / (16 x GAI)`, where GAI is the frame buffer's
width in 16-bit words fetched at once (1 on the first build), and 2CLK is twice that.

| Mode | Dot clock | Access | 2CLK | Memory cycle | Use |
|---|---|---|---|---|---|
| 640 x 480, 60 Hz | 25.175 MHz | dual | **6.294 MHz** (dot clock / 4) | 318 ns = 8 dots | the card's mode: flashless drawing, or text over graphics |
| 640 x 480, 60 Hz | 25.175 MHz | single | 3.147 MHz (/ 8) | 636 ns = 16 dots | any grade of the chip; drawing waits for retrace or flashes |
| 640 x 400, 70 Hz | 25.175 MHz | dual | 6.294 MHz | 318 ns | the VGA text raster: 25 rows of 16 lines |
| 640 x 240, 60 Hz | 12.5875 MHz (the crystal / 2) | dual | 3.147 MHz | 636 ns | a TV-rate or CGA monitor, 15.73 kHz |

The card is built for the VGA rows (section 12): it has no connector and no clock for the 15.73 kHz row, which the
table keeps for what the chip and the crystal could do.

The 640 x 480 registers, dual access (`python3 tools/acrtc_timing.py 640x480@60`): a line is 800 dots = 100 memory
cycles (sync 12, back porch 6, display 80, front porch 2), a frame 525 lines (sync 2, back porch 33, display 480,
front porch 10); 31.469 kHz, 59.94 Hz; both syncs negative.

| Register | Value | Fields |
|---|---|---|
| HSR (r82) | $630C | HC = 99 (the line - 1), HSW = 12 |
| HDR (r84) | $054F | HDS = 5 (back porch - 1), HDW = 79 (width - 1) |
| VSR (r86) | $020D | VC = 525 |
| VDR (r88) | $2002 | VDS = 32 (back porch - 1), VSW = 2 |
| SSW (r8A) | $01E0 | SP1 = 480, the Base screen's height |
| MWR1 (rCA) | $0028 | the Base screen: graphic, 40 words a line |

A screen is 40 x 480 = 19,200 words (38,400 bytes).

## 4. Block diagram

```
 YACC1 bus                                 HD63484P8
 DATA0-7 <----> '245 <-------------------> D0-D7
 IO-ADDR0 --------------------------------> RS            MAD0-15 <--+--> 2 x '245 <--> RAM data (16 bits)
 IO-ADDR2 --------------------------------> R/W                      |                     |
 IO-ADDR, -IO-RD, -IO-WR --> decode ------> CS                       +--> 2 x '573 --> RAM address A0-A15
 -RESET ----------------------------------> RES, DACK     MA16-19 / RA0-3, RA4, CHR --> '573 --> RAM A16.., rows
                                                           AS, MCYC, MRD, DRAW --> memory control (-OE, -WE, LOAD)
 25.175 MHz oscillator --> / 4 -----------> 2CLK
        |                                                  RAM data --> 2 x '299 (16 dots) ----+
        +--> dot clock to the shift registers              RAM data --> latch --> character    |--> merge, blank,
                                                                ROM --> '299 (method A) -------+    cursor --> R G B
                                            HSYNC, VSYNC --> polarity (XOR) --> DE-15 pins 13, 14
                                            DISP1, DISP2, CUD1, CUD2 --> blanking and cursor
 PS/2 keyboard and mouse: the V2.0 card's section (ATmega328P, three latches), on two more ports
```

## 5. The bus side

**Ports.** IO-ADDR0..3 carry the port number from two microcode steps before the strobe
([backplane](backplane.md)), so the chip's RS and R/W come from the port number, set up long before CS. They pass a
latch that holds them while CS is low: an OUT record keeps the port number a step after -IO-WR, but an IN record
drops it in the same step as -IO-RD, while CS is still low (section 10a):

| Port | | The chip sees |
|---|---|---|
| PA | OUT | RS = 0, write: the address register |
| PB | OUT | RS = 1, write: the register addressed, or the write FIFO (r00) |
| PC | IN | RS = 0, read: the status register |
| PD | IN | RS = 1, read: the register addressed, or the read FIFO |
| PE | IN / OUT | IN the card's status: bit 0 FULL, 1 SRC (0 keyboard, 1 mouse), 2 BUSY (the PS/2 section, as V2.0's PD), bit 3 TEXT (1 = method A's parts fitted), bits 7..4 = 0110, **the card ID $6x**; OUT the PS/2 command |
| PF | IN | PS/2 data (as V2.0's PE) |

RS = IO-ADDR0, R/W = IO-ADDR2 (high for PC and PD). CS is the port decode (a 74LS138 on IO-ADDR, as on V2.0) gated
with the strobe that belongs to the port: -IO-WR for PA / PB, -IO-RD for PC / PD, so an access the wrong way does
nothing. The other arrangement - two ports, R/W from the strobes as on V2.0's 6845 - needs R/W valid 50 ns before CS
and held until CS ends, which the strobes alone cannot give without a latch and a delay; it would free two ports.

**Timing** (the 8 MHz grade): RS and R/W 50 ns before CS, hold 0; write data 40 ns before CS rises, hold 10 ns; read
data 80 ns after CS, released within 60 ns. **CS must last at least three 2CLK cycles**: 477 ns at 6.29 MHz. The
strobe is two CPU clock periods - 2 us at 1 MHz - so the card works up to a CPU clock of about 4 MHz; at 6 MHz the I/O
records would need a second strobe step. DTACK (open drain) is not needed. The microcode's I/O records, read from
`test.hex` (section 10d): the port number and an OUT's data are on the bus two steps before the strobe, and the data a
step after -IO-WR. The bus buffer, enabled by CS, lets go of the chip's data pins as CS rises; their level stays (10k
pull-ups) far longer than the 10 ns.

**Drive.** The chip's outputs sink 2.2 mA. A 74HCT245 stands between D0-D7 and the bus (enabled by CS, direction from
the latched R/W), and the logic round the memory side has CMOS inputs (74HCT / 74ACT / 74AC).

**Reset and the 8-bit mode.** The bus -RESET drives RES (at least ten 2CLK cycles). DACK must be low for 100 ns before
RES rises and may rise with it (hold 0): DACK follows RES through a spare gate, as the application note does without
a DMA controller. DONE is pulled up, DREQ left open, LPSTB grounded, EXSYNC open (the chip is the master: OMR bit
15).

**Interrupt.** IRQ (open drain: command end, FIFO ready, ...) can reach the bus -INT through a jumper like V2.0's JP3.
The driver polls the status register; no emulator models -INT yet.

## 6. The memory side

- **Address.** MAD0-MAD15 pass two transparent latches (74ACT573) while AS is low and hold when it rises. MA16-MA19
  (which are RA0-RA3 for a character screen), RA4 and CHR hold through the cycle and need none (section 10b).
- **RAM.** Two 8-bit static RAMs side by side make the 16-bit word. Two **128K x 8, 55 ns** parts (AS6C1008-55, DIP-32,
  in production) give 128K words: six 640 x 480 screens, or a screen with fonts and saved areas off screen. Their
  footprint also takes the 512K x 8 part (section 9; the pinouts to compare before the footprint is fixed). Two 62256
  (32K words) would hold one 640 x 480 or one 800 x 600 screen and little else.
- **Data.** Two 74ACT245 between the RAM's data pins and MAD, enabled only in the data half of a drawing cycle (DRAW
  low, MCYC high), direction from MRD. In display cycles they stay off: the RAM drives the shift registers.
- **Control.** The RAM reads in every display cycle (DRAW high; in superimposed mode MRD low then marks the Window's
  access, not a write) and in drawing reads; -WE is DRAW low, MRD low, MCYC high, cut short by 2CLK so it ends before
  the address moves.
- **Time.** At 6.29 MHz a memory cycle is 318 ns. The address is out within 70 ns and a drawing read must be back
  40 ns before the cycle ends: about 186 ns for the latch, the RAM and the buffer, so a 55 ns RAM has room to spare.
  The write pulse is about one 2CLK half, 80 ns (the RAM's minimum write pulse to check: about 45 ns on a 55 ns part).

## 7. The dot path

- **Clock.** A 25.175 MHz oscillator; a 74F163 divides it by 4 for 2CLK and counts the 16 dots of a display cycle
  (the application note's figure 4-1 is this circuit with a 74S163). 2CLK must never stop
  or switch while the chip runs.
- **Shift registers.** Two 8-bit universal shift registers with parallel load (74F299 or 74AC299; the application
  note uses 74S299) hold the 16 dots of a graphics word, loaded at the end of the background's display access. Which
  end of the word is the left-hand dot comes from the manual's pixel mapping before the wiring is fixed.
- **Blanking and cursor.** DISP1 gates the video (its skew, DSK in OMR, lines it up with the pipeline); CUD1 / CUD2
  carry the cursors.
- **Sync.** HSYNC and VSYNC leave the chip active low. Two XOR gates give either polarity (640 x 480 wants both
  negative, 640 x 400 a positive VSYNC, 800 x 600 both positive), then a buffer to the connector.
- **Eight free control bits.** The chip puts its user attribute byte (ATR, in DCR) on MAD0-MAD7 in the last cycle of
  every HSYNC: two registers turn it into the card's control register with no port (section 10b; HSYNC's own edge
  comes too late to clock it off MAD): three colour bits, the two sync polarities, the text layer on / off,
  OR or XOR.
- **Output.** A DE-15 (HD15) socket at the front edge, right-angle, facing off the board. The video drives R, G and B
  (pins 1, 2, 3) through a resistor each, about 470 ohm from a 5 V CMOS output for 0.7 V into the monitor's 75 ohm;
  ANDing the dot with the three colour bits gives eight colours for the whole picture. HSYNC pin 13, VSYNC pin 14,
  returns pins 5-8 and 10.

## 8. Text: two methods

### A. A character screen laid over the graphics (superimposed access)

The Window is a character screen covering the display; the Base screen is the graphics. In each 16-dot display cycle
the chip fetches one graphics word and one character word. The character word holds **two 8-bit codes**, so 80
columns of 8-dot characters line up with 640 dots; 16 lines a character gives 30 rows (25 in 640 x 400).

- **Hardware added**: a 16-bit latch for the word, a character EPROM (256 glyphs x 16 lines = 4K; the two codes take
  turns on its address, 318 ns each), a third shift register, the merge gate: about seven chips. The character words
  live in the same RAM (CHR as its top address bit): 64K words of their own, leaving 64K words - three 640 x 480
  screens - for graphics.
- **Writing a character**: the chip has no text functions. The driver sets the read / write pointer (RWP, with the
  Window as its screen) and sends MOD with the mask on one half of the word, or WT for a pair. A line is cleared with
  CLR. About 4 to 12 bytes a character (an estimate, to settle with the emulator).
- **Scrolling**: the Window's start address (SAR3) plus its width (40) is one line up: a register write, no move.
  The 64K-word space wraps by itself, so the text runs round it for ever. The start raster address (SRA) scrolls
  smoothly, a scan line at a time.
- **Cursor**: the chip's block cursor registers, blinking, on CUD1.
- **Layers**: text and graphics are independent - either can be cleared, hidden (the Window's enable in DCR) or
  scrolled without the other.
- **The cost**: with the Window on every line, drawing gets the Window's half of the cycle only in the blanking -
  roughly a quarter of the time. With the Window off, or on part of the screen, drawing has it back.

### B. Glyphs copied in the bitmap (interleaved access)

No text hardware at all: the graphics path is the display. A font sits in frame buffer memory that is never shown,
and the chip copies an 8 x 16 block from it to the screen for every character (the application note's "characters via
graphics").

- **Hardware added**: one font EPROM. The ROM has no room for a font (4 KB for 256 glyphs of 8 x 16, 768 bytes for
  96 of 8 x 8; the monitor half has 30 bytes free), and a font loaded from disk would leave the screen dark until
  Y1/OS is up. So the card carries **a font EPROM decoded into the frame buffer's address space** (decided
  2026-11-11), where the chip's copy commands read it like RAM: with MA19 high (words $80000-$FFFFF) a 27C256 answers
  on MA0-MA14 in place of the RAM, its byte on both halves of the word. Bit 0 is the left-hand dot. It holds the
  font as a picture: the 96 glyphs of ASCII $20-$7F in three rows of 32, 256 dots by 48 lines - twice, the glyphs
  at the even places and those at the odd places, because a word of the picture holds two glyphs and the EPROM
  gives both halves the same byte. At start the ROM copies it into frame buffer RAM under the screen with two masked
  copies (SCPY, the mask $00FF, then $FF00). `tools/v3font.py` makes the image (3,840 bytes).
- **Writing a character**: one AGCPY (the graphic copy, in dot coordinates) from the font's picture in RAM: the
  glyph of code c is at x = (c and $1F) x 8, 16 x its row lines under the screen. Scanned down the columns and to the
  right (S = 1, DSD = 101), the copy leaves the current pointer at the next cell, so a line of text is one command
  of 10 bytes a character with no address arithmetic; a move (AMOVE, 6 bytes) only at a new line. By the manual's
  table the copy takes about 1,000 2CLK cycles, 160 us (twice that while the display has every other cycle). The
  method is CPU-bound: 10 bytes are some 30 instructions, under a millisecond.
- **The FIFO**: the chip is busy for milliseconds on a clear or a scroll and its write FIFO holds 16 bytes; a byte
  more is lost. The driver sends packets of at most 16 bytes, each after the status shows the FIFO empty (WFE).
- **Scrolling**: one CPY moves the screen up a row - 40 x 464 words, 116,012 cycles, about 18 ms, some 35 ms
  interleaved with the display - and one CLR blanks the last row. Nothing for the CPU to do but wait. (A start-address
  scroll is possible too, with the bands as a ring; more work in the driver.)
- **Cursor**: drawn by the driver (an XOR block), or the chip's graphic cursor on CUD1.
- **Layers**: one. Text overwrites graphics, as on a PC in a graphics mode. In exchange any font, size and position:
  80 x 30 of 8 x 16, 80 x 60 of 8 x 8, text at any dot.

### Side by side

| | A: character window | B: bitmap glyphs |
|---|---|---|
| Chips | about 7 more (latch, EPROM, shift register, glue) | none, or one font EPROM |
| Access mode | superimposed | interleaved |
| Text and graphics | two layers, independent | one bitmap |
| Scroll | a register write | a copy command, about 35 ms |
| Smooth scroll | yes (SRA) | no |
| A character | 4-12 bytes, the faster of the two | 10-25 bytes |
| Drawing while text shows | a quarter speed | full speed |
| Fonts | one EPROM, 8 x 16 cells | any, several, anywhere |
| Screen before the OS boots | yes | with the font EPROM |

**One board is both** (decided 2026-11-11: B first, the board laid out for A from the start). Method A's parts stand
apart from the graphics path; with their sockets empty the card is method B's, and IN PE bit 3 tells the ROM which it
is (as V2.0's TEXT-ONLY bit does). 2CLK is the dot clock / 4 either way: B runs the chip interleaved, A superimposed.

## 9. Higher resolution

The 8 MHz limit on 2CLK is the ceiling, and the way under it is the chip's own: fetch more than one word a display
cycle from a wider memory (the graphic address increment, GAI). Drawing still goes a word at a time, the low address
bit choosing the half.

| Mode | Dot clock | 16 bits wide (2 RAMs) | 32 bits wide (4 RAMs) | 64 bits wide (8 RAMs) |
|---|---|---|---|---|
| 640 x 480, 1 bit | 25.175 MHz | single 3.15, **dual 6.29** | - | - |
| 640 x 480, 4 colours | 25.175 MHz | single 6.29; dual needs 12.6 | dual 6.29 | - |
| 640 x 480, 16 colours | 25.175 MHz | no (single needs 12.6) | single 6.29; dual needs 12.6 | dual 6.29 |
| 800 x 600, 60 Hz, 1 bit | 40 MHz | single 5.0; dual needs 10 | dual 5.0 | - |
| 1024 x 768, 60 Hz, 1 bit | 65 MHz | no (single needs 8.125) | single 4.06; dual needs 8.125 | dual 4.06 |

(2CLK in MHz, the least memory that does it; "dual" is interleaved or superimposed. `python3 tools/acrtc_timing.py`
prints the whole table with the registers.) An 800 x 600 screen is 30,000 words, 1024 x 768 is 49,152, 640 x 480 in
four colours 38,400 and in sixteen 76,800: all fit the 128K words of section 6.

What the first board can carry so the steps above are parts, not a new layout:

1. **The oscillator in a socket**, and a second position with a select jumper: 25.175, 36 or 40, 65 MHz.
2. **Places for a second pair of RAMs and a second pair of shift registers** (32 bits wide), left empty at first:
   they bring 800 x 600 with flashless drawing, 1024 x 768 in single access, and four colours (flashless) or
   sixteen (single access) at 640 x 480.
3. **A dot path good for 65 MHz**: 74F / 74AC parts and short tracks on the 4-layer board. Whether a '299 shifts
   reliably at 65 MHz is to check on the data sheets; if not, two registers at half the rate and a multiplexer.
4. **Both sync polarities** (section 7) and a monitor that takes the mode: 1024 x 768 at 60 Hz is the usual top of a
   small LCD's VGA input.

Beyond that the limits are the 5 V logic and the chip: 1024 x 768 with flashless drawing, or sixteen colours at
640 x 480 with it, is 64 bits a fetch (eight RAMs).

## 10. The board and what carries over

- From V2.0: the PS/2 section (the ATmega328P, its latches and flags, `embedded/video-ps2`), the port decode, the
  blank card's bus connector, the 218 mm four-layer outline with the planes.
- Gone: everything in the $D000 block (the 74S85 select and SV3, the IDT7134, the window logic), the 6845, the
  DB9 and RCA outputs (VGA only).
- 39 chips with the keyboard section, and method A's 8 sockets: 47 (the first estimate was 29 and 7). V2.0 has 40.
- **The 218 mm outline is too short for them** (2026-11-11, the first placement trial with `gen_v30.py`). At V2.0's
  spacing - columns of sockets 14 mm apart with a capacitor beside each chip, 6.3 mm between the chips of a column -
  the 47 ICs, with the 0.9-inch DIP-64 and four 0.6-inch parts, fill ten narrow columns, two wide ones and the chip's
  own: about 250 mm. Without method A's sockets, or without the PS/2 section, about 218 mm. The 250 mm card was
  chosen (2026-11-11); no board was laid out before the card was dropped (2026-11-12).
- The board-layout rules of 2026-10-24 and after apply from the start: the DE-15 and the PS/2 jacks at the front edge
  facing out, jumpers at an edge, every reference and value on the silk outside its part, `cottageworker.com`.
- `pcb-check` before any order.

## 10a. The circuit, part by part (first cut, 2026-11-11)

The step between this note and a netlist: every chip the card needs, what it does, and the connections that are
already fixed by sections 5-7. The netlist (`hardware/cards/video/kicad/v3.0/v30_netlist.py`, written 2026-11-11: the
whole card, 47 ICs of which 8 are text method A's sockets, its own checks passing, simulated and timed with the
parts' data-sheet numbers: section 10d) is the single source
for the schematic and the board. Part numbers
here are working numbers until the netlist gives the references.

**The chip, DIP-64 (the manual's figure 4.1).** 1 CUD1, 2 CUD2, 3 R/W, 4 CS, 5 RS, 6 RES, 7 DONE, 8 DREQ, 9 DACK,
10 DTACK, 11 IRQ, 12 HSYNC, 13 VSYNC, 14 Vcc, 15 EXSYNC, 16 Vss, 17-24 D0-D7, 25-32 D8-D15 (open in 8-bit mode),
33 RA4, 34 MA19/RA3, 35 MA18/RA2, 36 MA17/RA1, 37 MA16/RA0, 38-48 MAD15-MAD5 (38 = MAD15 ... 48 = MAD5), 49 Vcc,
50 2CLK, 51 Vss, 52 MCYC, 53 AS, 54 DRAW, 55 MRD, 56 CHR, 57-61 MAD4-MAD0 (57 = MAD4 ... 61 = MAD0), 62 DISP2,
63 DISP1, 64 LPSTB.

**Ports.** The six port numbers are IO-ADDR3..0 = 1010 (PA) to 1111 (PF). Two 74HCT138, one enabled by -IO-WR and one
by -IO-RD (G1 = IO-ADDR3, the select inputs IO-ADDR2..0), give a strobe for each port in the one direction it is
used:

| Decoder | Output | Strobe | Goes to |
|---|---|---|---|
| write (-G2A = -IO-WR) | Y2 | OUT PA | the chip's CS (address register) |
| | Y3 | OUT PB | the chip's CS (data, write FIFO) |
| | Y6 | OUT PE | the PS/2 command latch |
| read (-G2A = -IO-RD) | Y4 | IN PC | the chip's CS (status) |
| | Y5 | IN PD | the chip's CS (data, read FIFO) |
| | Y6 | IN PE | the card status buffer |
| | Y7 | IN PF | the PS/2 data latch |

CS is the AND of the four chip strobes (half a 74HCT21): low while any of them is. RS = IO-ADDR0 and R/W = IO-ADDR2
(PA / PC have bit 0 clear, PC / PD bit 2 set), valid two microcode steps before the strobe, through a 74HCT573 whose
enable is CS: open while CS is high, holding while it is low. An OUT to PC or PD and an IN from PA or PB select
nothing.

The latch is there for the IN records. All sixteen end with the port number and -IO-RD dropped in one step, and CS,
two gates behind the strobe, is still low for up to 80 ns after the port number has gone. Straight from the bus, R/W
would fall while the chip is still selected - the end of every IN the beginning of a write - and the bus buffer would
turn round against the chip's data pins for those 80 ns. Held by CS, RS and R/W move only after CS has risen, which
is the chip's rule (hold 0), and the buffer is off before its direction changes.

| Block | Parts | What they do |
|---|---|---|
| Bus | X1 DIN 41612 (the blank card's) | |
| | 2 x 74HCT138, 74HCT21 | the port strobes and CS, above |
| | 74HCT573 | RS and R/W held while CS is low |
| | 74HCT245 | D0-D7 to DATA0-7: enabled by CS, direction the latched R/W (the chip's side drives the bus on a read) |
| | a gate of the PS/2 section's 74HCT08 | -RESET buffered to RES and DACK |
| | jumper | IRQ (open drain) to the bus -INT, as V2.0's JP3 |
| Clock | 25.175 MHz oscillator in a socket | the dot clock |
| | 74F163A | 2CLK (its QB) and the dot number within a memory cycle, in step with the chip's MCYC (section 10b) |
| Memory | 2 x 74ACT573 | the address latches: MAD0-7, MAD8-15, open while AS is low (MA16-19 need none: section 10b) |
| | 2 x 128K x 8 static RAM, 55 ns, DIP-32 | the low and the high byte of the frame buffer's word; the footprint takes the 512K part (pin 1 A18, pin 30 A17 instead of CE2: a jumper) |
| | 2 x 74ACT245 | RAM data to MAD in the data half of a drawing cycle, direction from MRD |
| | 27C256 EPROM | the font, selected instead of the RAM while the latched MA19 is high; its byte goes to both halves of the word |
| | 74HCT244 | the EPROM's byte onto the high half |
| | 74ACT00, 74ACT02, 74ACT04, 74ACT08, 74ACT10, 74ACT11, 2 x 74ACT32, 2 x 74F74, 74F21 (section 10b's equations) | P56, -OE, -WE, the buffers' enable, RAM or EPROM, CHR in the address, the load |
| Dots | 2 x 74F299 | 16 dots, loaded at the end of the display access, bit 0 out first |
| | 2 x 74ACT273 | the control register: the chip's attribute byte (ATR) taken from MAD0-7, then copied as HSYNC rises (section 10b) |
| | 74ACT86 | the two syncs' polarity (and NOT MRD, NOT CHR) |
| | 74F299, half a 74F74, gates of the 74ACT10, 74ACT00, 74ACT32 and 74ACT02 | the graphics dot delayed 8 dots; the two layers mixed; the dot retimed to the dot clock; a gate for each gun with its off bit |
| | 3 x 470 ohm, DE-15 socket | R, G, B and the syncs to the monitor |
| Text A (sockets, fitted later) | 3 x 74ACT574, AT27C256R-70, 74F299, 74F74, 74F21, 74ACT32 (section 10c) | the two character codes and the raster line latched from the Window's cycle, the character generator addressed by them, its dots shifted and laid over the graphics; the card status bit TEXT says the parts are there |
| PS/2 | ATmega328P, 2 x 74HCT374, 74HCT244, 74HCT74, 16 MHz crystal, 2 Mini-DIN-6, polyfuse, FTDI header | V2.0's section as it is (`embedded/video-ps2`): data on IN PF, commands on OUT PE, FULL / SRC / BUSY in the card status on IN PE with the TEXT bit and the ID 0110 |

47 chips in the netlist with the PS/2 section, 8 of them method A's sockets (section 10c).

**The PS/2 section on the new ports** (V2.0's nets with the strobes renamed): OUT PE clocks the command latch and
sets BUSY; IN PE enables the status buffer (a 74HCT244: FULL, SRC, BUSY and TEXT on bits 0-3, bits 7-4 wired 0110);
IN PF enables the data latch onto the bus and, ANDed with -RESET, clears FULL. The ATmega's side is unchanged:
LDDATA clocks the data latch and sets FULL, RDCMD enables the command latch and clears BUSY, INTREQ ANDed with FULL
reaches -INT through an open-collector gate and the jumper, beside the chip's own IRQ. TEXT is a jumper to VCC
against a pull-down, fitted with method A's parts. A 7416 stays for -INT and for the ATmega's reset from the bus
-RESET, as on V2.0.

**Settled since the first cut** (2026-11-11): the gating of -WE, -OE and the loads (section 10b); the 128K RAM's
pinout, from the figure in Alliance's data sheet (1 NC, 2 A16, 22 CE, 24 OE, 29 WE, 30 CE2, 31 A15); the I/O
records, from `test.hex` (section 10d). Still open: whether a 512K x 8 static RAM is to be had in DIP-32, and its
pinout against the footprint's two extra address pins (1 and 30).

**From the application note's section 6, for those equations.** MCYC is 2CLK halved (the address half, then the data
half); the note makes an early copy of it with a flip-flop on the oscillator rather than wait for the chip's output.
The shift registers load at the end of a display cycle, on a dot clock edge while the load input is active, and the
load must not happen in a drawing cycle or in a **dummy cycle**: when the chip has a drawing slot and nothing to
draw it runs a cycle that looks like a display read (DRAW and MRD high) but gives no AS strobe, and its address is
0. A flip-flop set by AS and cleared at the end of the cycle tells the two apart; without it the dots of word 0
would be loaded into the picture. The read buffers need not be held off in display cycles: the chip ignores what is
on MAD then. The attribute byte is taken with 2CLK gated by HSYNC in the note (a transparent latch); the card
uses two registers (section 10b).

**Order of work.** (1) The netlist with its own checks (every pin on a net or listed as unconnected, no output tied
to another, the text-A parts removable as V2.0's graphics parts are): done. (2) A timing check: the memory cycle and
the bus cycle against the parts' numbers: done, in the simulation (section 10d). (3) The generator for the schematic
sheets and the unrouted board, from V2.0's (`gen_v20.py`): the schematic is done (2026-11-11, `gen_v30.py sch`: a root
and eight sheets, its exported netlist equal to `v30_netlist.py`, ERC clean); the board - 250 mm, four layers, the
layout rules of section 10 - was not laid out. (4) Routing, DRC, the placement and schematic PDFs, `pcb-check`: not
begun. (5) The review of the design before any order, as V2.0 had (`hardware/cards/video/reviews/v2.0.md`): not
begun. **The work stopped after the schematic (2026-11-12): the card is not built.**

## 10b. The memory cycle and the control logic (2026-11-11)

From the manual's figures T-6 (display cycle) and T-8 (frame memory write) and its timing table, the 8 MHz part's
numbers. Everything is timed from the **falling edge of 2CLK**, and a memory cycle is two 2CLK periods, 8 dots:

| Dots (39.7 ns each) | 2CLK | The chip |
|---|---|---|
| 0, 1 | low | MCYC falls (within 40 ns), AS falls (65), the address is on MAD and MA16-19 / RA, MRD and DRAW are valid (70) |
| 2, 3 | high | AS rises (it is low for about the low half of 2CLK, 30 ns at least); the address stays on MAD |
| 4, 5 | low | MCYC rises; the address leaves MAD (off within 50 ns); in a write the data is on MAD within 70 ns |
| 6, 7 | high | a read's data must be on MAD 40 ns before the cycle ends and 10 ns after; a write's data stays 10 ns after |

MA16-19 / RA, MRD and DRAW hold for the whole cycle and 10 ns into the next: they need no latch (the part list's third
'573 goes). The chip's outputs are TTL levels and its inputs want 2.2 V, so every part it drives has TTL thresholds:
74ACT, 74HCT or 74F, not plain 74AC (the latches are 74ACT573, the buffers 74ACT245).

**The dot counter keeps step with the chip by itself.** A 74F163 counts the 25.175 MHz clock; QB is 2CLK. QA, QB, QC
are the dot number 0-7 within the memory cycle once QC follows the chip's MCYC, and it is made to: -LOAD is NAND(QA,
QB), active in dots 3 and 7, with the load inputs A = B = 0 (what the count would be anyway, so 2CLK never skips) and
C = NOT MCYC. MCYC is read at the clock edge that ends dot 3 or 7, when it has been steady for 100 ns and before
it can move (it answers the 2CLK edge that this same clock edge makes). After one load QC is the cycle's half, low for
the address and high for the data, with a flip-flop's edge instead of the chip's 40 ns.

**One timing signal, and it is a flip-flop's.** Whatever acts on an edge by itself - a clock, a latch enable, a write
pulse - must not be a gate's decode of the counter: where two counter bits change at one clock edge, one rising and
one falling, such a gate can give a pulse a nanosecond or two wide (section 10d found two). So the counter's bits go
only to D inputs and to loads, which a clock samples, and one flip-flop on the dot clock makes the edge the rest
needs: **P56**, D = NAND(QC, NOT QB), high in dots 5 and 6 of every memory cycle whatever the cycle is. The RAM's
-WE, the attribute register's clock and the start of a read's buffers hang on it.

**The strobes.** W = NOR(DRAW, MRD): a drawing write. (DRAW, MRD, AS and CHR are the pins' levels: DRAW is low in a
drawing cycle, AS low while the address is on MAD.)

| Signal | Equation | Why |
|---|---|---|
| address latches' LE | NOT AS | open while AS is low; the address holds 10 ns after AS rises |
| RAM -CE / EPROM -CE | MA19 AND NOT CHR / NOT MA19 OR CHR | the font is the upper half of the address space (CHR: section 10c) |
| VALID | a flip-flop preset by AS low, cleared by the clock at the end of each cycle (QC falling) | a dummy cycle - a drawing slot with nothing to draw - looks like a display cycle but has no AS |
| MOE: the RAMs' -OE, the EPROM's -OE and, ORed with the EPROM's -CE, its copy's enable | NAND(VALID, AS, NOT W) | the memories drive the RAM data lines from the end of AS to the end of the cycle, in every cycle that has an AS and is not a drawing write. Every cycle so begins with nothing on those lines for the two dots of AS, which is when MA19 changes: the RAM and the font never hand over to each other with both on. A dummy cycle has them off throughout |
| the 128K RAMs' CE2 (pin 30, JP4 1-2) | VALID | the RAM leaves the lines a gate sooner at the cycle's end (with the 512K part pin 30 is A17) |
| -WE | NAND(P56, W): low in dots 5 and 6 of a drawing write | 80 ns wide (45 wanted); the data is at the RAM 48 ns before it rises (25 wanted), and it rises a whole dot before the address or the data can move |
| the MAD buffers' -OE | a flip-flop on the dot clock, D = NOT DRAW AND QC AND NOT (QA AND QB) AND (P56 OR W), one 74F21 gate after the counter; then one gate: on in dots 5-7 of a drawing write, 6-7 of a drawing read | a read's buffers wait a dot longer: the chip may keep its address on MAD until 50 ns into the data half, which is 10 ns and more into dot 5. Off 16 ns after the cycle's last clock edge (a read's data is wanted for 10) |
| the MAD buffers' direction | MRD | high: RAM to MAD |
| the graphics shift registers' load (S1; S0 is high) | QA AND QB AND QC AND (MRD AND DRAW AND VALID AND display on), the last a level, then one 74F21 gate after the counter | dot 7 of a Background cycle with the display on: the load is the clock edge that ends it, 16 dots apart in dual access |

In a display cycle the RAM's address is steady about 14 ns into dot 2 at the latest and its data 55 ns later, in dot
3; the load is at the end of dot 7, so for the graphics a 70 or 100 ns part would do (it is method A's character
word, wanted as dot 4 begins, that asks for 55 ns: section 10c). The figures of the simulation (section 10d) at
their worst corner: a drawing read's data is at the chip 59 ns before the cycle's end (40 wanted); a write's data
is steady at the RAM 48 ns before -WE rises, 39 with the parts' rises and falls set against each other (25 wanted),
and the pulse is 80 ns; the buffers and the chip are never on MAD together for more than 3 ns.

**The shift registers.** Two 74F299, S0 high and S1 the load, their outputs disabled (-OE high) so that the I/O pins
are inputs on the RAM's data lines. They shift from QA towards QH; QH' of the second is the video. Bit 0 of the word
is the left-hand dot, so it loads into QH of the second register (the word's low byte on the second register in
reverse order, the high byte on the first), and the first register's QH' feeds the second's serial input.

**The control register (figure T-9).** The attribute byte is on MAD only in the data half of the last memory cycle
before HSYNC rises: valid 80 ns after that half begins, gone 10 ns after the cycle ends, while HSYNC itself may rise
up to 70 ns after it. So HSYNC's edge cannot clock it off MAD, and nothing outside the chip says which cycle is the
last. Two 74ACT273 do it. The first is clocked by P56's end, the edge that begins dot 7, in every cycle: it holds
whatever was on MAD0-7 then, and in the last cycle of HSYNC that is the attribute byte, steady at least 31 ns
before the edge and 40 ns after it. The second is clocked by HSYNC's rise (through a gate, for a clean edge): the
one moment in a line when the first holds the attribute byte, 35 ns and more after the first's clock and most of a
cycle before its next. The second is the control register. It changes once a line, in the blanking, and never
shows what the first holds in between (the syncs' polarity bits must not move during a sync pulse). -RESET clears
both. Its bits, the ATR byte of the chip's DCR:

| ATR bit | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 means | red off | green off | blue off | HSYNC positive | VSYNC positive | text layer on (method A) | XOR, not OR (method A) | the second font (method A) |

ATR = 00 is white on black with both syncs negative, what 640 x 480 wants: a driver that leaves ATR alone (the V3
ROM writes DCR = $4000) gets a picture.

**Blanking, and a dot exactly a clock wide.** DISP1 (active low) moves up to 70 ns after a cycle begins, but it is
steady long before dot 7, where the load is decided: a word fetched while DISP1 is high is not loaded, and the shift
registers, whose serial input is low, run empty behind the last word that was. The picture is so switched on and
off on a word's first dot with no gate in the dot's path. Which word that is, is set by the chip's display skew
(DSK in OMR). After the two layers are mixed (section 10c) a flip-flop on the dot clock retimes the dot, so that
every dot reaches the guns one clock wide whatever the gates before it did. Each gun is a NOR of the retimed dot's
complement with its off bit, through 470 ohm.


## 10c. Text method A in the circuit (2026-11-11)

The manual's figure 2.1 (c): in superimposed access a display cycle is two memory cycles, the **Background's** (MRD
high) and the **Window's** (MRD low; DRAW is high in both, and each has its AS). When the Window is not displayed its
half goes to drawing, as in interleaved access. Three things follow for the card, the first two for both builds:

- **The two kinds of display cycle are told apart by MRD.** The graphics shift registers load at the end of a
  Background cycle only (DRAW AND VALID AND MRD); a Window cycle (DRAW AND VALID AND NOT MRD) belongs to the text
  parts. The RAM reads in both: its -OE is off only for a drawing write.
- **CHR changes what MA16-19 mean.** For a screen defined as characters the chip puts the address on MAD0-15 alone and
  the raster line RA0-RA3 on the MA16-19 pins (RA4 beside them), in display and in drawing cycles alike. So the
  RAM's upper address must not come from those pins then: A16 (and A17, A18 of the 512K part) = MA OR CHR, the
  RAM's -CE = MA19 AND NOT CHR, the font EPROM's -CE = NOT MA19 OR CHR. A character screen is therefore the RAM's top
  64K words (on the 128K part), whatever the line; the graphics screens and the font's copy keep below word $10000.
- **The text is a cycle behind the graphics, so the graphics wait for it.** The character word of a display cycle is
  read in its second half, 8 dots after the graphics word was loaded, and its glyph must still be looked up. A
  74F299 that only shifts delays the graphics dot by 8 dots (not a 74ACT164: its inputs want the dot held 3 ns
  after the clock, and the shift register before it may change after 2.7). The blanking is in the dot already: a
  word not loaded. Both builds have it: with the retiming flip-flop the picture sits 9 dots later against the
  syncs, which the horizontal timing registers take up.

**The text parts** (eight sockets, empty on the first build; the netlist's `TEXT_A`):

| Part | What it does |
|---|---|
| 2 x 74ACT574 | the word's low and high byte, the left and the right character's code; one of them drives the generator's address |
| 74ACT574 | the raster line RA0-RA3 (with RA4) of the same cycle |
| AT27C256R-70 | the character generator: address = code x 16 + line (A12 CUD1, A13 the second font, A14 CUD2), a byte = the line's 8 dots, bit 0 the left-hand one |
| 74F299 | the text's dots, loaded 8 at a time |
| 74F74 | A: the three latches' clock, WCK; B: WPH, "the cycle before this one was a Window cycle" |
| 74F21, 74ACT32 | dot 3 of a Window cycle and the shifter's load (dot 7), each one gate after the counter; "a Window cycle or the one after it" |

- The RAM's data in a Window cycle is steady by 157 ns at the latest (CHR 70 ns after the chip's clock edge, which
  is itself 11 ns after the dot clock's; two gates to the RAM's chip enable; 55 ns of RAM), as dot 4 begins. WCK
  rises there (a flip-flop on the dot clock, D = dot 3 AND a Window cycle) and clocks the codes and the line in:
  7.7 ns to spare with every part at its maximum, 2.9 if WCK's flip-flop is at its fastest as well. It is the
  card's smallest margin, and the reason for a 55 ns RAM.
- The left code drives the generator from then to the cycle's end, about 139 ns: a 70 ns EPROM with room, a 120 ns
  one just. Its dots load at the end of the Window cycle. The right code drives the generator through all of the
  next cycle (WPH) and loads at its end. So a character word read in display cycle N is on the screen through
  cycle N+1, exactly under the delayed graphics word of cycle N.
- No Window cycle, no load: the text shifter runs empty by itself outside the Window and when the Window is off.
- **The layers.** TEXTON (ATR bit 5) is the text shifter's clear: off, it holds the shifter empty. The picture is G OR
  T, or G XOR T with ATR bit 6: NAND(G OR T, NAND(G, T, TXOR)) is the dot's complement, which the three guns' gates
  take. Both layers pass the same gates on the way, so they stay in step within a dot. Without the text parts
  a 10k resistor holds the text dot low and the picture is the graphics alone; the netlist's `text_a_check()`
  proves that the eight sockets drive nothing else in the fitted logic.
- **The cursor.** CUD1 and CUD2 are active low and a memory cycle wide: one character cell. They need no logic of
  their own: they are two more address lines of the character generator (A12 and A14), straight from the chip. A
  character whose look-up cycle has CUD1 low comes from the half of the EPROM that holds the cursor's form of every
  glyph - turned over, underlined, whatever the image holds - and is loaded with the cursor in it, so the cursor is
  in step with the dots by construction. The left character's look-up cycle is the Window cycle itself, the right
  one's the cycle after: the driver puts the cursor on either with the chip's cursor skew (CSK in OMR, in memory
  cycles) and a cursor one cycle wide. Blinking and the raster range are the chip's (CDR, the block cursor
  registers). Which cycle the chip counts the skew from is to be seen on the bench; both characters are in reach
  either way. A13 is ATR bit 7: a second font of 256 glyphs, chosen line by line.
- **The bitmap console (method B) has no hardware cursor**: the chip's graphic cursor would need a retimed window
  mixed into the graphics dot. Its driver draws the cursor (a rectangle in XOR).
- **For the driver:** the Window is a character screen (CHR) of 80 x 30 cells in the RAM's top 64K words; a cell is a
  byte, two to a word, the left one the low byte; 16 lines a cell (RA0-RA3). The card status bit TEXT (jumper JP3)
  says the parts are fitted.

## 10d. The netlist simulated, and the timing check (2026-11-11)

`tests/video/v30_netsim.py` (in `make check`) runs `v30_netlist.py` as a circuit, gate for gate, with delays in
nanoseconds. Every 74xx part, the RAMs and the EPROMs are models written from the parts' pinouts and function tables,
wired by the netlist's nets; the chip is a model of its memory side from the manual's figures (it answers the 2CLK the
card gives it with MCYC, AS, the address and data, MRD, DRAW, CHR, the raster line, HSYNC, DISP1 and the cursors, each
after its delay) and runs a script of memory cycles. On the bus side the test bench is the machine: it drives the
port number, the data and the strobes as the microcode's OUT and IN records do, and those records are read from
`test.hex` to see that they do.

**The delays are the data sheets'**: each part's minimum and maximum over temperature at 5 V +- 0.5 V into 50 pF, a
rising and a falling output apart. TI's SN74F163A, SN74F74, SN74F299, SN74F21, SN74ACT00 / 04 / 08 / 10 / 11 / 32 /
86 / 245 / 573 / 574, CD74ACT02 and CD74ACT273; Alliance's AS6C1008-55; Atmel's AT27C256R. The 74HCT parts of the bus
side see only the 2 us strobes and have one generous figure (5 to 40 ns). The chip's delays are the manual's maximums
and, for a fast chip, figures near its minimums - assumed, since the manual gives the hold times (10 ns) and no other
minimum. Each script runs at these corners:

| Corner | What it is for |
|---|---|
| the chip slow or fast, the card's parts all at their maximum or all at their minimum: four, each from both phases the dot counter can start in | set-up, hold, pulse widths, and the handovers on the shared lines |
| the parts' rising outputs at their minimum and their falling ones at their maximum, and the other way round, with the chip slow and fast: four | what a gate makes of two signals that change at one clock edge: a runt pulse on a clock that the straight corners can miss shows here |

**What is checked**

- **Interleaved access, text sockets empty:** the counter falls into step; a write reaches both RAMs and nothing else;
  a read is back in time; the font's byte reads on both halves, also with a dummy cycle after it; every display word
  leaves the shift registers bit 0 first, 8 dots later after the delay line, and on the guns a dot clock after
  that; a word fetched with the display off, a dummy cycle and a drawing cycle load nothing; the control register
  takes the attribute byte as HSYNC rises and not before; colours and sync polarity follow it.
- **Superimposed access, sockets fitted:** a character word comes out as its two glyphs, left code first, exactly under
  the graphics word of the same display cycle; a word written to the character screen lands in the RAM's top 64K
  words whatever the raster line; OR and XOR; the second font; the cursor on the left or the right character.
- **The ports:** only OUT PA / PB and IN PC / PD select the chip; RS and R/W are steady 50 ns before CS and until it
  has risen; CS lasts three 2CLK cycles; an OUT's byte is at the chip 40 ns before CS rises and 10 ns after; an IN's
  byte is on the bus when the record takes it; the chip and the bus buffer are never both on the chip's data pins.
- **Everywhere:** every flip-flop's, register's and shift register's set-up and hold; the RAM's write pulse, data
  set-up and address; no pulse shorter than 5 ns on any clock, clear, preset, latch enable or -WE; and, in the four
  straight corners, no two outputs on a net for more than 3 ns at a handover. A memory counts as on from its
  low-impedance time (10 ns after its chip enable, 5 ns after its output enable), not from when its data is good.

Seventeen wiring faults put in on purpose (the latch taken out of RS and R/W, each term of MOE left off, a read's
buffers on a dot early, a register on the wrong edge of P56, -WE in every cycle, ...) are each caught.

**The margins**, the smallest over every corner (in brackets: with the rises and falls set against each other):

| | Wanted | To spare |
|---|---|---|
| a drawing read's data at the chip | 40 ns before the cycle's end | 19 ns |
| a write's data at the RAM before -WE rises | 25 ns | 23 ns (14) |
| the write pulse | 45 ns | 35 ns |
| the counter's -LOAD before its clock | 11.5 ns | 7.7 ns |
| P56's D before its clock | 3 ns | 7.2 ns |
| the graphics shift registers' load before their clock | 8.5 ns | 14.7 ns |
| the attribute byte at the first register | 2 ns | 34 ns (29) |
| two outputs on at a handover | 3 ns at most | 2.8 ns: the MAD buffers ending a read against a fast chip's next address |
| text: the character codes at their latches | 2.5 ns | 7.7 ns (2.9) |
| text: the shifter's load; the glyph's dots | 8.5 ns; 5.5 ns | 14.7 ns; 64 ns |
| the bus, at a step of 500 ns (a 4 MHz CPU clock): CS low | 477 ns | 23 ns |
| RS and R/W before CS; an OUT's byte before CS rises; an IN's byte before it is taken | 50; 40 ns; - | 955; 415; 300 ns |

**What it found, and what changed for it**

*The first run (logic, the delays guessed):*
- The MAD buffers' enable was three gates deep from the counter: a read's data reached the chip only 5 ns inside its
  set-up, and the buffers were still on up to 18 ns into the next cycle, against the chip's address. It is now a
  flip-flop on the dot clock.
- The text dot passed one gate more than the graphics dot and arrived after the dot's end. TEXTON now holds the text
  shifter clear instead of gating its output.

*The timing check (the data sheets' numbers, eight corners):*
- **The parts themselves.** A 74ACT gate is 10 ns at its slowest, not 8: the buffers' enable and the two loads are
  now decoded by one 74F21 gate each. No data sheet or DIP source was found for the 74ACT377: the control register is two 74ACT273
  with a clock each instead of an enable. The 74ACT164 delay line wants its input held 3 ns after the clock, and the
  74F299 before it may change after 2.7: the delay line is a 74F299. The blanking gate left the dot's path (a word
  with the display off is not loaded), and the dot is retimed by a flip-flop.
- **Two clocks were decodes of the counter**: the control register's, "dot 7 while HSYNC is low" and "dot 3 while it
  is high". The counter's outputs rise faster than they fall (8.5 ns against 11 at most), so where one bit rises as
  another falls each gate showed a pulse of 1 to 1.5 ns at a clock edge where it should have stayed low, and the
  first register lost its hold time on MAD. The first register is now
  clocked by P56, a flip-flop's edge, and the second by HSYNC itself; the simulation looks for runt pulses on every
  such input.
- **A read's buffers met the chip's address.** The chip may keep its address on MAD until 50 ns into the data half;
  with the card's parts at their fastest the buffers came on 43 ns into it: 6.9 ns of both. A read's buffers now come on
  a dot later. The read's data is still 59 ns ahead of the cycle's end, where it was 99.
- **The RAM and the font met on the RAM data lines.** Both had their outputs on in every cycle but a write, chosen
  by MA19 alone; counted from their low-impedance time, the RAM came on while the font's copy (a 74HCT244, 40 ns to
  let go) was still on: up to 40 ns of both after every read of the font. MOE now keeps all three off from the end
  of a cycle to the end of the next AS.
- **Every IN from the chip ended as the start of a write.** The microcode's IN records drop the port number in the
  same step as -IO-RD; CS follows the strobe two gates later, so R/W, straight from the bus, fell while the chip was
  still selected, and the bus buffer turned round against it for up to 80 ns. RS and R/W are now held by a latch
  that CS closes.

**What it cannot say, for the bench**

- The chip's minimums. Two margins rest on them: the 2.8 ns above (the chip's next address is taken to come no
  sooner than 15 ns after its clock edge; it cannot come before its own read's 10 ns of hold are over), and the
  start of the dead time on the RAM data lines (MOE goes off at most 39 ns after the cycle's last clock edge; MA19
  holds 10 ns after the chip's clock edge, which is up to 11 ns after that, and a memory needs 5 to 10 ns from its
  enables before it drives: 2 ns to spare with a fast chip and slow gates).
- The end of an IN on the decoders. The port number and -IO-RD leave the bus in one step; if the port number's bits
  do not fall together a decoder can show a pulse of a few nanoseconds on another port's strobe (after IN PF, on IN
  PD's, which is the chip's CS). Every card that decodes ports lives with this, the I/O card's UART among them, and
  the chip asks for 477 ns of CS; to look at with a scope.
- With the 512K RAMs pin 30 is A17, not CE2: the dead time is then MOE's alone.

## 11. Software, in the order it can be built

1. **The emulators' model** (`software/videomodel.h`): the register file, the two FIFOs, the status register, and the
   commands the driver needs first (ORG, WPR / RPR, CLR, CPY / SCPY, WT / MOD / RD, AMOVE, ALINE, ARCT, AFRCT, DOT,
   CRCL, PAINT, AGCPY), with `tools/vidsim.py` drawing the 640 x 480 frame. The driver is written and tested against
   it before any board exists, as V2.0's was.
2. **The ROM driver**: the register table of section 3, the console by method A or B, the keyboard as on V2.0
   (`docs/programming/MONITOR.md` section 11a). The start sequence is the manual's: with STR = 0 load CCR, OMR, DCR,
   the timing registers r82-r9F and the screens' registers rC0-rEF, then set STR.
3. **Y1/OS**: a graphics library for C programs (a command is a handful of bytes to port PB), `video`, and graphics
   statements for `/bin/basic`.
4. **Bring-up programs** for the bench, as `tests/video/asm` are for V1.

## 12. Decided, to decide, and to confirm

**Decided (2026-11-12)**
- The card is not built for the YACC1. What exists - this note, the netlist and its simulation, the schematic, the
  emulators' model, the V3 ROM - is kept, as the starting point for a video card on another machine (section 13).
  What follows is the design's own list, as it stood.
- The branch `video-v3`, with the V3 ROM, is frozen: kept as reference, nothing more committed to it or merged
  into it.

**Decided (2026-11-11)**
- Text: method B on the first build; the board has method A's sockets and tracks from the start.
- The font for B: an EPROM on the card in the frame buffer's address space, so the boot shows on the screen.
- The card has the PS/2 keyboard and mouse section.
- V3 is built whether or not V2.0 is ordered (that is still open).
- The chip takes four ports, PA-PD (section 5); with the PS/2 section on PE / PF the card has all of PA-PF, and a
  later card uses P2-P7.
- VGA only: one DE-15 socket. No DB9, no RCA jack, no jumper that halves the clock; V1.0 and V2.0 are the cards
  for TV-rate monitors.
- The software: the emulators' model on the branch `video-v2`, chosen with `Y1VID_CARD=v3`, until the ROM for a V3
  machine needs a line of its own.

**Confirmed from the manual (2026-11-11)**
- **The dot order.** X runs with the bit number: bit 0 of a word is its left-hand dot (the dot address DPD and the
  ORG command's example). The shift registers send bit 0 first; of two characters in a word the left one is the low
  byte.
- **Y points up.** One line up is one memory width lower in memory, so the origin (ORG) goes at the bottom-left of
  the screen: for 640 x 480 at address 0, word 479 x 40 = 19,160.
- **The pointers.** RD, WT and MOD step the read / write pointer by one word; CLR and the copies leave it a line past
  the area. A copy's source and destination are each scanned in a direction the command names (S and DSD, eight
  ways), which is how a scroll copies over itself safely.
- **After reset** the chip's abort bit (ABT in CCR) is set and the FIFOs are shut: the driver clears it first. In
  8-bit mode WPTN counts bytes.

**The card's length (decided 2026-11-11: 250 mm)**
- Section 10. The ways there were: about 250 mm with everything on it, 32 mm more slot space than the longest card
  today; or 218 mm without text method A's sockets (the first build leaves them empty; method A would then need a
  later board); or 218 mm without the PS/2 section (a keyboard card of its own; about 220 mm, to be squeezed); or the
  control gates gathered into one or two GALs, a redesign that the timing simulation would have to follow.

**Left open when the design stopped**
- A font with lower case: the first image is the V1.3 card's 64 glyphs, each line doubled into the 8 x 16 cell.

**Settled by the timing check (2026-11-11, section 10d)**
- The I/O records, from `test.hex`: the data is on the bus a step after -IO-WR; an IN drops the port number with its
  strobe, which the latch on RS and R/W answers.
- The RAM's write pulse (80 ns against 45) and the 74F299's clock (25.175 MHz against 70); the 128K RAM's pinout.
- The superimposed mode's load points for the two words, as the manual's figure 2.1 (c) gives them.

**To confirm, by whoever builds from this design**
- Whether a 512K x 8 static RAM is to be had in DIP-32, and its pinout.
- How the pattern RAM is walked in a filled area (which way PPY steps), on the chip: the manual's text and its figure
  do not settle it. A solid fill does not depend on it.

## 13. What carries over to another machine (2026-11-12)

The card is not built for the YACC1. The design is the starting point for a video card on another machine, with
another bus, and this section sorts it for that work. Nothing in this note was ever on a bench: what is proven is
proven by the simulation of section 10d, for this netlist and these parts.

**Where everything is**

| What | Where | Branch |
|---|---|---|
| The design | this note, `docs/cards/video-v3.md` | `main` |
| The clock and register figures of section 3, for any mode | `tools/acrtc_timing.py` (`--check` in `make check`) | `main` |
| The circuit: parts, nets, the pins left open, with its own checks | `hardware/cards/video/kicad/v3.0/v30_netlist.py` | `main` |
| The simulation and the timing check | `tests/video/v30_netsim.py` (in `make check`) | `main` |
| The schematic (eight sheets and a PDF), the bill of materials | `hardware/cards/video/kicad/v3.0/`: `reports/video-v3.0-schematic.pdf`, `BOM.md`, drawn by `gen_v30.py sch` | `main` |
| The emulators' model of the chip and of the card, its tests, the font image, the picture drawn from the frame buffer | `software/acrtcmodel.h`, `software/videomodel.h`, `tests/video/v30/`, `tools/v3font.py`, `tools/vidsim.py`; `software/emulator/README.md` says what is modelled | `video-v2` |
| A driver: the start sequence and a console by method B (glyphs by SCPY, a scroll by CPY) | `firmware/monitor/monitor.asm`, `docs/programming/MONITOR.md` | `video-v3` (frozen 2026-11-12: kept as reference) |
| The PS/2 keyboard and mouse firmware (ATmega328P) | `embedded/video-ps2` | `main` |
| The manuals | bitsavers, `components/hitachi/_dataBooks` (the head of this note); not in the repository: a copy of each in `../private-resources/YACC1-D/docs/datasheets/` | |

**Holds on any bus: the chip's memory side and the dot path** (sections 6, 7, 10b, 10c)

- The clock: the 25.175 MHz oscillator and the 74F163A that makes 2CLK and counts the dots of a memory cycle, kept
  in step with the chip's MCYC by loading itself.
- The one timing edge, P56, and the rule behind it: no clock, latch enable or write pulse is a gate's decode of the
  counter.
- The address latches, the two RAMs, the MAD buffers with their enable flip-flop, -WE, the dummy-cycle flip-flop
  (VALID), MOE and CE2: every equation of section 10b's table.
- The font EPROM in the upper half of the chip's address space, and its copy onto the high byte.
- The shift registers, the delay line, the retiming flip-flop, the three guns' gates and resistors, the syncs'
  polarity, the DE-15.
- The control register taken from the chip's attribute byte: eight control bits that need no address on the bus.
- Text method A's eight parts, and the cursor on the character generator's address (section 10c).
- The register values of section 3 and what section 12 lists as confirmed from the manual.

The margins of section 10d belong to these parts wired this way. A changed part, a gate moved into a GAL or an
equation rewritten is a new circuit to the timing check: put the change into the netlist and the part's model, and run
`v30_netsim.py` again.

**The YACC1's, to be designed again for another bus** (sections 5 and 10a)

| Here | Because | What stays true on any bus |
|---|---|---|
| Six I/O ports, PA-PF, from two 74HCT138 and a 74HCT21 | the YACC1 reaches a card by a port number and two strobes | the chip has two addresses (RS) and a direction (R/W) |
| RS and R/W through a 74HCT573 that CS closes | the microcode's IN records drop the port number in the same step as -IO-RD | RS and R/W steady 50 ns before CS falls and until it has risen |
| Nothing waits for the chip | the strobe is 2 us, at a 1 MHz CPU clock | CS low for at least three 2CLK cycles: 477 ns at 6.29 MHz. A faster bus stretches its cycle, by a count or by the chip's DTACK (pin 10, open drain), which this card leaves open and the simulation never drives |
| The 8-bit mode: DACK low as RES rises, D8-D15 open | an 8-bit data bus | the chip has a 16-bit host bus (DACK high as RES rises): a register or a FIFO word in one transfer. The model and the ROM driver are written for the 8-bit mode (the high byte, then the low byte; WPTN counts bytes) |
| A 74HCT245 on D0-D7, enabled by CS, its direction the latched R/W | | the chip's outputs sink 2.2 mA, so a buffer stands between it and the bus; a write's data 40 ns before CS rises and 10 ns after; a read's data 80 ns after CS falls, released within 60 ns |
| The card status on IN PE (FULL, SRC, BUSY, TEXT, the ID $6x); the PS/2 section on PE and PF | the V2.0 card's section on this card's port strobes | the ATmega328P's side of it: two latches, three flags, `embedded/video-ps2` |
| IRQ and the PS/2 interrupt to -INT through jumpers and a 7416 | one interrupt line, no vector | IRQ is open drain; the driver here polls the status register |
| -RESET to RES, to DACK and to the two control registers' clear | | RES low for at least ten 2CLK cycles |
| The blank card's DIN 41612 connector, a 250 mm outline, four layers: the board half of `gen_v30.py` | the YACC1's card frame | nothing: its placement is a first trial that fails its own check |

**The simulation on another bus.** The memory side's scripts in `v30_netsim.py` (interleaved and superimposed
access) do not depend on the bus. `ports()` is the YACC1: it drives IO-ADDR, DATA and the two strobes as the
microcode's records do. For another bus that function and the bus side's parts are written again; what it checks at
the chip - the right-hand column above - stays.

**Not designed here**

- The 16-bit host mode, DTACK, DMA (DREQ, DACK, DONE), the light pen, EXSYNC.
- More than one bit a dot. Section 9 is arithmetic and no circuit.
- An attribute for each character. Method A's cell is a byte, two to a word: a character code and nothing else.
  The attribute byte (ATR) is one for the picture, or for a line if the driver rewrites it between lines. A cell with
  its own attribute needs more than 16 bits in a Window cycle, and nothing here provides them.
- The emulators' model stops short of the chip. Not modelled: circles, ellipses, arcs, PAINT, PTN and the DMA
  transfers (each sets the command error bit and says so), command times, character screens (method A), the cursors,
  interrupts.

**Never seen on a bench**

- Everything; and in particular what section 10d leaves for the bench (the chip's minimum delays behind the two
  smallest margins, the decoders at the end of an IN) and what section 12 leaves to confirm (a 512K RAM in DIP-32,
  the pattern RAM's walk). Section 10c: which cycle the chip counts the cursor's skew from.
- The DE-15 socket's footprint is KiCad's for the common right-angle part, not checked against a part in hand.
