# firmware/video

`chargen.bin` — a 2732 (4K) character-generator image for the video card V1.0's IC25, written by
`python3 tools/vidsim.py chargen` (2026-10-10). A 2513-style set of 64 characters (codes 00-1F = `@A..Z[\]^_`, 20-3F =
space `!"#..?`, so a byte's bits 0-5 = the ASCII code's), 5x7 dots in an 8-row cell, laid out for the card's wiring:
address = code x 8 + row (the code on A3..A8 from IC23, the row on A0..A2 from the 6845's RA0..2), the five dots in
D7..D3 with D7 the leftmost (the 74LS166 shifts H = D7 out first), D2..D0 and everything above $1FF zero. For when the
fitted EPROM is blank or holds a foreign set (read it first: `minipro -p 2732A@DIP24 -r chargen-read.bin`, and draw it with
`tools/vidsim.py ... --chargen chargen-read.bin`). Burn with `minipro -p 2732A@DIP24 -w firmware/video/chargen.bin`.
`docs/procedures/VIDEO-BRINGUP.md` phase 0.

## The card's own EPROM (read 2026-10-18)

`chargen-read.bin` is IC25 as found, read twice with the TL866II+ (`minipro -p 2732A@DIP24 -r`, MD5
bb67b3db2664e64437f5ab180bb9fb77, both reads identical). It holds a full 128-character ASCII set: address = ASCII code x
8 + row, 5x7 glyphs with a blank top row, dots in D7..D3 with D7 the leftmost - the dot order this card's 74LS166
expects - in $000-$3FF ($000 the control codes, blank; $100 space..`?`; $200 `@`, `A`..`Z`, `[\]^_`; $300 lower case);
$400-$FFF are blank ($FF).

The card wires only VDATA0..5 to A3..A8 and grounds A9-A11, so it reaches $000-$1FF of this chip: blank control codes
and space..`?`. **Every letter (and `@[\]^_`) is at $200-$2FF, out of reach**: with this EPROM the card shows digits
and punctuation and leaves letters blank (the ROM driver stores `A` as code $01). `tools/vidsim.py run
tests/video/asm/testcard.img --chargen firmware/video/chargen-read.bin --png card.png` draws it.

`chargen-remapped.bin` is the same font in the card's layout: codes 00-1F = the chip's $200-$2FF (`@A..Z[\]^_`), codes
20-3F = its $100-$1FF (space..`?`), the rest zero - a 2513-style set in the original shapes. Burn it into a 2732A (a
blank one, or another chip after UV erasing; keep the original as found):

```bash
minipro -p 2732A@DIP24 -w firmware/video/chargen-remapped.bin
```

`chargen-remapped.hex` is the same 512 bytes as Intel hex (32 data records of 16 bytes from $0000, CR LF line ends)
for programmers whose software takes hex, e.g. Batronix Prog-Express: the bytes above $01FF are left to the
programmer's blank value, which the card never reads.

**Burned 2026-10-20** into a Fujitsu MBM2732A on an XGecu T48 (firmware 00.1.03) with minipro 0.7.4:

```bash
minipro -p MBM2732A@DIP24 -o vpp=21 -o pulse=1000 -w firmware/video/chargen-remapped.bin
```

17 s, minipro's verify OK, two read-backs identical to the image (MD5 99914414a8ea6b8a17b751795e2e183b). The pulse
matters: with the same 21 V, minipro's default 200 µs and a 50 ms pulse both left the chip blank; 1 ms (the "intelligent"
programming pulse) took every byte. A second MBM2732A burned the same way the same day (identical read-back): a spare. The original chip (`chargen-read.bin`, the ELF's `gr2`) is kept as found.

Burning (2026-10-18): a TL866II+ cannot program the NMOS-era parts at hand - a Fujitsu MBM2732A and a National
NMC27C32Q (no B) both stayed blank after every attempt (minipro's profiles give them 18 V; they need about 21 V; the pin
test passed). Parts it can program: an NMC27C32B(Q) (13 V), an AT28C16 EEPROM (5 V); or a 21 V programmer.

The alternative, keeping the chip and reaching its letters, would take VDATA6 to A9 through a latch beside IC23 (which
has no free flip-flop) - a board change, not a wire.
