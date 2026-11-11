# Video card V3 — design note (HD63484 ACRTC, VGA)

**A design note, begun 2026-11-11. Nothing is drawn, ordered or built; "V3" is a working name.** The card in the
machine is the [V1.0](video.md); the [V2.0](video-v2.md) is designed and not ordered.

**Decided 2026-11-11** (section 12): text by method B first, on a board laid out from the start to take method A's
parts; the font in an EPROM on the card, so the screen shows the boot; the card carries the PS/2 keyboard and mouse;
V3 goes ahead whether or not V2.0 is ordered. The emulators' model of the card is on the branch `video-v2`
(`Y1VID_CARD=v3`).

The aim is more graphics resolution than V2.0's 512 x 192, on monitors sold today, with a CRT controller of the 6845's
family. The plan: Hitachi's **HD63484 ACRTC** (the "advanced CRTC", the HD6845's successor) driving a **VGA** monitor
at **640 x 480**, one bit a dot to begin with, on a board that can grow to 800 x 600 and 1024 x 768 (section 9).
Two **HD63484P8** are in hand: the 8 MHz grade, in the 64-pin plastic DIP with 2.54 mm pin spacing.

Sources: Hitachi's *HD63484 ACRTC User's Manual* (1985, U75) and *Application Note* (1986, U90), both on bitsavers
under `components/hitachi/_dataBooks`; section and table numbers below are the manual's. `tools/acrtc_timing.py`
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

**Ports.** IO-ADDR0..3 are steady through a whole I/O record and the strobe is one microcode step inside it
([backplane](backplane.md)), so the chip's RS and R/W can come from the port number, set up a step before the strobe
with nothing to race:

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
records would need a second strobe step. DTACK (open drain) is not needed. The I/O records' data hold after -IO-WR is
to check against the microcode when the schematic is drawn, as `tests/video/v20_timing.py` did for V2.0.

**Drive.** The chip's outputs sink 2.2 mA. A 74HCT245 stands between D0-D7 and the bus (enabled by CS, direction from
R/W), and the logic round the memory side has CMOS inputs (74HCT / 74ACT / 74AC).

**Reset and the 8-bit mode.** The bus -RESET drives RES (at least ten 2CLK cycles). DACK must be low for 100 ns before
RES rises and may rise with it (hold 0): DACK follows RES through a spare gate, as the application note does without
a DMA controller. DONE is pulled up, DREQ left open, LPSTB grounded, EXSYNC open (the chip is the master: OMR bit
15).

**Interrupt.** IRQ (open drain: command end, FIFO ready, ...) can reach the bus -INT through a jumper like V2.0's JP3.
The driver polls the status register; no emulator models -INT yet.

## 6. The memory side

- **Address.** MAD0-MAD15 pass two transparent latches (74AC573) while AS is low and hold when it rises. MA16-MA19
  (which are RA0-RA3 for a character screen), RA4 and CHR pass a third.
- **RAM.** Two 8-bit static RAMs side by side make the 16-bit word. Two **128K x 8, 55 ns** parts (AS6C1008-55, DIP-32,
  in production) give 128K words: six 640 x 480 screens, or a screen with fonts and saved areas off screen. Their
  footprint also takes the 512K x 8 part (section 9; the pinouts to compare before the footprint is fixed). Two 62256
  (32K words) would hold one 640 x 480 or one 800 x 600 screen and little else.
- **Data.** Two 74AC245 between the RAM's data pins and MAD, enabled only in the data half of a drawing cycle (DRAW
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
  every HSYNC: two registers on the dot clock turn it into the card's control register with no port (section 10b;
  HSYNC's own edge comes too late to clock it): three colour bits, the two sync polarities, the text layer on / off,
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
- About 22 chips without the keyboard section and 29 with it; method A adds about 7. V2.0 has 40.
- The board-layout rules of 2026-10-24 and after apply from the start: the DE-15 and the PS/2 jacks at the front edge
  facing out, jumpers at an edge, every reference and value on the silk outside its part, `cottageworker.com`.
- `pcb-check` before any order.

## 10a. The circuit, part by part (first cut, 2026-11-11)

The step between this note and a netlist: every chip the card needs, what it does, and the connections that are
already fixed by sections 5-7. The netlist (`hardware/cards/video/kicad/v3.0/v30_netlist.py`, a first cut since 2026-11-11: the
whole card, 46 ICs of which 8 are text method A's sockets, its own checks passing and
simulated: section 10d) is the single source
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
straight from the bus (PA / PC have bit 0 clear, PC / PD bit 2 set), valid a microcode step before the strobe. An
OUT to PC or PD and an IN from PA or PB select nothing.

| Block | Parts | What they do |
|---|---|---|
| Bus | X1 DIN 41612 (the blank card's) | |
| | 2 x 74HCT138, 74HCT21 | the port strobes and CS, above |
| | 74HCT245 | D0-D7 to DATA0-7: enabled by CS, direction R/W (the chip's side drives the bus on a read) |
| | 74HCT14 (or a spare gate) | -RESET buffered to RES and DACK; the spare sections square the oscillator if needed |
| | jumper | IRQ (open drain) to the bus -INT, as V2.0's JP3 |
| Clock | 25.175 MHz oscillator in a socket | the dot clock |
| | 74F163 | divides by 4 for 2CLK and counts the 16 dots of a display cycle (application note figure 4-1) |
| Memory | 2 x 74ACT573 | the address latches: MAD0-7, MAD8-15, open while AS is low (MA16-19 need none: section 10b) |
| | 2 x 128K x 8 static RAM, 55 ns, DIP-32 | the low and the high byte of the frame buffer's word; the footprint takes the 512K part (pin 1 A18, pin 30 A17 instead of CE2: a jumper) |
| | 2 x 74ACT245 | RAM data to MAD in the data half of a drawing cycle, direction from MRD |
| | 27C256 EPROM | the font, selected instead of the RAM while the latched MA19 is high; its byte goes to both halves of the word |
| | 74HCT244 | the EPROM's byte onto the high half |
| | 74ACT00, 74ACT02, 74ACT04, 74ACT08, 74ACT10, 74ACT11, 74ACT32, 74F74 (section 10b's equations) | -OE, -WE, the buffers' enables, RAM or EPROM, the load |
| Dots | 2 x 74F299 | 16 dots, loaded at the end of the display access, bit 0 out first |
| | 2 x 74ACT377, 74ACT00 | the control register: the chip's attribute byte (ATR) from MAD0-7 (section 10b) |
| | 74ACT86 | the two syncs' polarity; XOR of the text and graphics layers |
| | 74F74, gates of the 74ACT10 and 74ACT02 | blanking by DISP1 in step with the dots; a gate for each gun with its off bit |
| | 3 x 470 ohm, DE-15 socket | R, G, B and the syncs to the monitor |
| Text A (sockets, fitted later) | 3 x 74ACT574, AT27C256R-70, 74F299, 74F74, 74ACT21, 74ACT32 (section 10c) | the two character codes and the raster line latched from the Window's cycle, the character generator addressed by them, its dots shifted and laid over the graphics; the card status bit TEXT says the parts are there |
| PS/2 | ATmega328P, 2 x 74HCT374, 74HCT244, 74HCT74, 16 MHz crystal, 2 Mini-DIN-6, polyfuse, FTDI header | V2.0's section as it is (`embedded/video-ps2`): data on IN PF, commands on OUT PE, FULL / SRC / BUSY in the card status on IN PE with the TEXT bit and the ID 0110 |

46 chips in the netlist with the PS/2 section, 8 of them method A's sockets (section 10c).

**The PS/2 section on the new ports** (V2.0's nets with the strobes renamed): OUT PE clocks the command latch and
sets BUSY; IN PE enables the status buffer (a 74HCT244: FULL, SRC, BUSY and TEXT on bits 0-3, bits 7-4 wired 0110);
IN PF enables the data latch onto the bus and, ANDed with -RESET, clears FULL. The ATmega's side is unchanged:
LDDATA clocks the data latch and sets FULL, RDCMD enables the command latch and clears BUSY, INTREQ ANDed with FULL
reaches -INT through an open-collector gate and the jumper, beside the chip's own IRQ. TEXT is a jumper to VCC
against a pull-down, fitted with method A's parts. A 7416 stays for -INT and for the ATmega's reset from the bus
-RESET, as on V2.0.

**What the netlist still needs** (the items of section 12 "to confirm", in the order they block it): the exact
gating of -WE, -OE and the '299s' load from MCYC, AS, DRAW, MRD and the divider's count (the application note's
figures 4-1 to 4-4, read against the manual's timing tables for the 8 MHz part); the 128K and 512K RAMs' pinouts from
their data sheets; the I/O records' data hold after -IO-WR from the microcode (10 ns wanted).

**From the application note's section 6, for those equations.** MCYC is 2CLK halved (the address half, then the data
half); the note makes an early copy of it with a flip-flop on the oscillator rather than wait for the chip's output.
The shift registers load at the end of a display cycle, on a dot clock edge while the load input is active, and the
load must not happen in a drawing cycle or in a **dummy cycle**: when the chip has a drawing slot and nothing to
draw it runs a cycle that looks like a display read (DRAW and MRD high) but gives no AS strobe, and its address is
0. A flip-flop set by AS and cleared at the end of the cycle tells the two apart; without it the dots of word 0
would be loaded into the picture. The read buffers need not be held off in display cycles: the chip ignores what is
on MAD then. The attribute byte is taken with 2CLK gated by HSYNC in the note (a transparent latch); the '273 on
HSYNC's edge of section 7 is to be checked against that timing.

**Order of work.** (1) The netlist with its own checks (every pin on a net or listed as unconnected, no output tied
to another, the text-A parts removable as V2.0's graphics parts are). (2) A timing check in the manner of
`tests/video/v20_timing.py`: the memory cycle and the bus cycle against the parts' numbers. (3) The generator for
the schematic sheets and the unrouted board, from V2.0's (`gen_v20.py`): the 218 mm card, four layers, the layout
rules of section 10. (4) Routing, DRC, the placement and schematic PDFs, `pcb-check`. (5) The review of the design
before any order, as V2.0 had (`hardware/cards/video/reviews/v2.0.md`).

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

**The strobes.** W = NOR(DRAW, MRD): a drawing write.

| Signal | Equation | Why |
|---|---|---|
| address latches' LE | NOT AS | open while AS is low; the address holds 10 ns after AS rises |
| RAM -CE / EPROM -CE | MA19 / NOT MA19 | the font is the upper half of the address space |
| RAM -OE, EPROM -OE | W | reading in every cycle but a write |
| -WE | a flip-flop on the dot clock, D = NAND(QC, NOT QB, W): low in dots 5 and 6 | 79 ns wide; the data is at the RAM about 41 ns before it rises (25 wanted), and it rises a whole dot before the address or the data can move |
| the MAD buffers' -OE | a flip-flop on the dot clock, D = DRAW OR NOT QC OR (QA AND QB), then one gate: on in dots 5-7 of a drawing cycle | a read and a write alike: on after the chip has let go of its address on MAD (50 ns into dot 4), off 16 ns after the cycle's last clock edge (a read's data is wanted for 10) |
| the MAD buffers' direction | MRD | high: RAM to MAD |
| VALID | a flip-flop preset by AS low, cleared by the clock at the start of each cycle (QC falling) | a dummy cycle - a drawing slot with nothing to draw - looks like a display cycle but has no AS |
| the shift registers' load (S1; S0 is high) | QA AND QB AND QC AND DRAW AND VALID | dot 7 of a display cycle: the load is the clock edge that ends it, 16 dots apart in dual access |
| the font's copy onto the high byte ('244 -OE) | NOT MA19 OR W | the EPROM's byte on both halves of the word, never against a write |

In a display cycle the RAM's address is steady about 5 ns into dot 2 and its data 55 ns later, in dot 3; the load is
at the end of dot 7, so the RAM has 150 ns to spare and a 70 or 100 ns part would do. The figures of the simulation
(section 10d) with the chip's delays at their maximum: a drawing read's data is at the chip 102 ns before the
cycle's end (40 wanted); a write's data is steady at the RAM 40 ns before -WE rises (25 wanted) and the pulse is
79 ns (45 wanted); the buffers and the chip are never on MAD together for more than 1 ns.

**The shift registers.** Two 74F299, S0 high and S1 the load, their outputs disabled (-OE high) so that the I/O pins
are inputs on the RAM's data lines. They shift from QA towards QH; QH' of the second is the video. Bit 0 of the word
is the left-hand dot, so it loads into QH of the second register (the word's low byte on the second register in
reverse order, the high byte on the first), and the first register's QH' feeds the second's serial input.

**The control register (figure T-9).** The attribute byte is on MAD only in the data half of the last memory cycle
before HSYNC rises: valid 80 ns after that half begins, gone 10 ns after the cycle ends, while HSYNC itself may rise
up to 70 ns after it. So HSYNC's edge cannot clock it, and nothing outside the chip says which cycle is the last.
Two 74ACT377 on the dot clock do it: the first takes MAD0-7 at the end of every cycle while HSYNC is low (enable =
dot 7 AND HSYNC low), so after the last one it holds the attribute byte; the second copies the first at the end of
every cycle while HSYNC is high. The second is the control register, and it never shows what the first holds in
between (the syncs' polarity bits must not move during a sync pulse). Its bits, the ATR byte of the chip's DCR:

| ATR bit | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 1 means | red off | green off | blue off | HSYNC positive | VSYNC positive | text layer on (method A) | XOR, not OR (method A) | the second font (method A) |

ATR = 00 is white on black with both syncs negative, what 640 x 480 wants: a driver that leaves ATR alone (the V3
ROM writes DCR = $4000) gets a picture.

**Blanking in step with the dots.** DISP1 (active low) moves up to 70 ns after a cycle begins, somewhere in the first
two dots of a word. A 74F74 takes it when a word is loaded (clocked by the load signal's rise, in dot 7) and passes
it on at the next dot clock, so the picture is switched on and off exactly on a word's first dot. Which word it
belongs to is set by the chip's display skew (DSK in OMR). The dot is NAND(the shift register's output, that
flip-flop), and each gun is a NOR of it with its off bit, through 470 ohm.


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
  74ACT164 delays the (already blanked) graphics dot by 8 dots; its two serial inputs are the AND of the dot and
  display-on, so the blanking travels with it. Both builds have it: the picture sits 8 dots later against the
  syncs, which the horizontal timing registers take up.

**The text parts** (eight sockets, empty on the first build; the netlist's `TEXT_A`):

| Part | What it does |
|---|---|
| 2 x 74ACT574 | the word's low and high byte, the left and the right character's code; one of them drives the generator's address |
| 74ACT574 | the raster line RA0-RA3 (with RA4) of the same cycle |
| AT27C256R-70 | the character generator: address = code x 16 + line (A12 CUD1, A13 the second font, A14 CUD2), a byte = the line's 8 dots, bit 0 the left-hand one |
| 74F299 | the text's dots, loaded 8 at a time |
| 74F74 | A: the three latches' clock, WCK; B: WPH, "the cycle before this one was a Window cycle" |
| 74ACT21, 74ACT32 | dot 3 of a Window cycle; the shifter's load |

- The RAM's data in a Window cycle is steady by about 142 ns (address valid 70 ns after the chip's clock edge, the
  latch, 55 ns of RAM), before the cycle's dot 4. WCK rises there (a flip-flop on the dot clock, D = dot 3 AND a
  Window cycle) and clocks the codes and the line in, 20 ns to spare.
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

## 10d. The netlist simulated (2026-11-11)

`tests/video/v30_netsim.py` (in `make check`) runs `v30_netlist.py` as a circuit, gate for gate, with delays in
nanoseconds. Every 74xx part, the RAMs and the EPROMs are models written from the parts' pinouts and function tables,
wired by the netlist's nets; the chip is a model of its memory side from the manual's figures (it answers the 2CLK the
card gives it with MCYC, AS, the address and data, MRD, DRAW, CHR, the raster line, HSYNC and DISP1, each after its
delay) and runs a script of memory cycles. Each script runs with the chip's delays at their maximum and near their
minimum, and from both phases the dot counter can start in.

- **Interleaved access, text sockets empty:** the counter falls into step; a write reaches both RAMs and nothing else;
  a read is back in time; the font's byte reads on both halves; every display word leaves the shift registers bit 0
  first, 8 dots later after the delay line, and on the guns; dummy and drawing cycles load nothing; the control
  register takes the attribute byte and does not move while HSYNC is low; colours and sync polarity follow it.
- **Superimposed access, sockets fitted:** a character word comes out as its two glyphs, left code first, exactly under
  the graphics word of the same display cycle; a word written to the character screen lands in the RAM's top 64K
  words whatever the raster line; OR and XOR; the second font; the cursor on the left or the right character.
- **The ports:** only OUT PA / PB and IN PC / PD select the chip, with the bus buffer the right way round.
- **Everywhere:** no two outputs on a net at once (1 ns at a handover is the most), every register's set-up and hold,
  the RAM's write pulse and data set-up.

Eight wiring faults put in on purpose (two data bits swapped, a latch enable inverted, a gate input left off, ...)
are each caught. The smallest margins with every delay at its maximum: 4.7 ns at the buffers' enable flip-flop, 8.2 ns
at the shift registers' load, 12.4 ns at the character latches, 14.7 ns of RAM data set-up.

**What it found, and what changed for it:**
- The MAD buffers' enable was three gates deep from the counter: a read's data reached the chip only 5 ns inside its
  set-up, and the buffers were still on up to 18 ns into the next cycle, against the chip's address. It is now a
  flip-flop on the dot clock (the row above), and reads and writes share one window.
- The text dot passed one gate more than the graphics dot and arrived after the dot's end. TEXTON now holds the text
  shifter clear instead of gating its output.

The delays are the parts' data-sheet maximums as far as they are known; the timing check against the parts actually
bought uses the same program with their numbers.

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

**To decide**
- A font with lower case: the first image is the V1.3 card's 64 glyphs, each line doubled into the 8 x 16 cell.

**To confirm before a schematic**
- The I/O records' data hold against the chip's 10 ns, from `test.hex`.
- The RAM's write pulse and the '299's maximum clock, from the parts' data sheets; the 128K and 512K RAMs' pinouts.
- The superimposed mode's exact load points for the two words (the manual's figure 2.1, the application note's 4-4).
- How the pattern RAM is walked in a filled area (which way PPY steps), on the chip: the manual's text and its figure
  do not settle it. A solid fill does not depend on it.
