# Video card V3 — design note (HD63484 ACRTC, VGA)

**A design note, begun 2026-11-11. Nothing is drawn, ordered or built; "V3" is a working name.** The card in the
machine is the [V1.0](video.md); the [V2.0](video-v2.md) is designed and not ordered.

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
| PE | IN / OUT | the card: PS/2 status (FULL, SRC, BUSY, as V2.0's PD) and the card ID in bits 7..4; OUT the PS/2 command |
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
  (the application note's figure 4-1 is this circuit with a 74S163). A jumper feeds the divider from the oscillator
  halved for the TV-rate modes; 2CLK must never stop or switch while the chip runs.
- **Shift registers.** Two 8-bit universal shift registers with parallel load (74F299 or 74AC299; the application
  note uses 74S299) hold the 16 dots of a graphics word, loaded at the end of the background's display access. Which
  end of the word is the left-hand dot comes from the manual's pixel mapping before the wiring is fixed.
- **Blanking and cursor.** DISP1 gates the video (its skew, DSK in OMR, lines it up with the pipeline); CUD1 / CUD2
  carry the cursors.
- **Sync.** HSYNC and VSYNC leave the chip active low. Two XOR gates give either polarity (640 x 480 wants both
  negative, 640 x 400 a positive VSYNC, 800 x 600 both positive), then a buffer to the connector.
- **Eight free control bits.** The chip puts its user attribute byte (ATR, in DCR) on MAD0-MAD7 in the last cycle of
  every HSYNC: a 74HCT273 clocked by HSYNC's rising edge and cleared by -RESET turns it into the card's control
  register with no port: the two sync polarities, three colour bits, the text layer on / off, OR or XOR.
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

- **Hardware added**: none - if the font can be loaded. The ROM has no room for one (4 KB for 256 glyphs of 8 x 16,
  768 bytes for 96 of 8 x 8; the monitor half has 30 bytes free), so either the screen stays dark until Y1/OS loads a
  font from disk, or the card carries **one font EPROM decoded into a corner of the frame buffer's address space**,
  where the chip's copy commands read it like RAM.
- **Writing a character**: SCPY (a masked copy of whole words: 1 word x 16 lines, the mask on the half the character
  occupies) or AGCPY (the graphic copy, in dot coordinates, any position). By the manual's table SCPY takes 268 2CLK
  cycles, about 43 us, and AGCPY about 1,000, 160 us (twice that while the display has every other cycle). The CPU
  sends about 10 to 25 bytes a character (an estimate): this method is CPU-bound at roughly a thousand characters a
  second, about what the ROM's driver does today.
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

**One board can be both.** Method A's parts stand apart from the graphics path; with their sockets empty the card is
method B's, and a status bit tells the ROM which it is (as V2.0's TEXT-ONLY bit does). The first build can be B's: the
fewest parts, and everything on the screen is the chip's own drawing.

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
  DB9 and RCA outputs unless a TV-rate monitor is to stay supported.
- About 22 chips without the keyboard section and 29 with it; method A adds about 7. V2.0 has 40.
- The board-layout rules of 2026-10-24 and after apply from the start: the DE-15 and the PS/2 jacks at the front edge
  facing out, jumpers at an edge, every reference and value on the silk outside its part, `cottageworker.com`.
- `pcb-check` before any order.

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

## 12. To decide, and to confirm

**To decide**
- Text: B alone on the first build with A's sockets empty, or A fitted from the start.
- The font for B: an EPROM in the frame buffer's address space, or from disk.
- Four ports for the chip (section 5), or two with a latched R/W.
- Whether a TV-rate output (the DB9 / RCA of V2.0, the clock halved) stays on the card.
- Whether V2.0 is ordered first: its PS/2 section and port decode are common to both.
- Where the software goes: the `video-v2` branch, or a line of its own.

**To confirm before a schematic**
- The dot order inside a word, and whether RWP steps after WT / MOD (the manual, section 6).
- The I/O records' data hold against the chip's 10 ns, from `test.hex`.
- The RAM's write pulse and the '299's maximum clock, from the parts' data sheets; the 128K and 512K RAMs' pinouts.
- The superimposed mode's exact load points for the two words (the manual's figure 2.1, the application note's 4-4),
  on the emulator's model first.
