# tests/video — video card RAM test

`video_ram_test.py [port] [--quick]` drives the Bus Test Card (`tools/busdrv.py`, FTDI 19200) and exercises the video
card's 1K display RAM at $D000–$D3FF: address-derived and inverted patterns over every cell, one-cell neighbour isolation
(address-line shorts), the 2026-09-18 write-through check (writes to $0010, $9010, $0011, $1010 must not reach $D010) and a
read-stability pass with memory-card traffic in between ($D000 is undecoded on the memory card, so a floating bus can fake
a good read). `--quick` = first 64 cells (~1 min); full run ~14 min.

Results: 2026-09-21, after Ken joined the card's +5V and VCC rails — 8/8 PASS (quick and full). Before the join the
write-through fault reproduced (see `hardware/cards/video/README.md`).
