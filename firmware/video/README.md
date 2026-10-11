# firmware/video

`chargen.bin` — a 2732 (4K) character-generator image for the video card V1.0's IC25, written by
`python3 tools/vidsim.py chargen` (2026-10-10). A 2513-style set of 64 characters (codes 00-1F = `@A..Z[\]^_`, 20-3F =
space `!"#..?`, so a byte's bits 0-5 = the ASCII code's), 5x7 dots in an 8-row cell, laid out for the card's wiring:
address = code x 8 + row (the code on A3..A8 from IC23, the row on A0..A2 from the 6845's RA0..2), the five dots in
D7..D3 with D7 the leftmost (the 74LS166 shifts H = D7 out first), D2..D0 and everything above $1FF zero. For when the
fitted EPROM is blank or holds a foreign set (read it first: `minipro -p 2732 -r chargen-read.bin`, and draw it with
`tools/vidsim.py ... --chargen chargen-read.bin`). Burn with `minipro -p 2732 -w firmware/video/chargen.bin`.
`docs/procedures/VIDEO-BRINGUP.md` phase 0.
