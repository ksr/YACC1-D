# tests/video — video card tests

`emu.py` (2026-09-25, in `make check`): the ROM's video unit (probe, the `V` command, mirroring with a scroll, the absent
card) and Y1/OS's `video` command on both emulators, whose card model (`software/videomodel.h`) prints the screen with `-V`;
the screen is compared with a Python model of the driver. The bench scripts below drive the real card.

**Video bring-up (2026-10-10)**: `docs/procedures/VIDEO-BRINGUP.md` is the plan. `crtc_regs.py` (the 6845's register
path through the tester), `crtc_picture.py` (a picture with the CPU out), `asm/` (the CPU programs `vram`, `crtcreg`,
`testcard`, `vstress`, `estrobe` as `.asm` and ready-built `.img`; `asm/run.py` checks them on the microcode emulator, in
`make check`); `tools/vidsim.py` draws what the card shows.

`gate.py` (2026-10-11, in `make check`): the card at gate level, `y1ucemu -G REV` (`docs/cards/video.md` section 9).
`software/ucemu/videogate.h` is current; with the card as fitted (`v1.0`) the monitor's video unit, Y1/OS's `video` and
the programs in `asm/` give the same console output, screen, CRTC registers, step counts and disk as the behavioural
card, with 0 bus events (`crtcreg`'s two latch reads aside: floating inputs); without the RS fix (`v1.0-no-rs`) and with
the socket empty (`v1.0-no6845`) `crtcreg` fails as the fix document predicts; without the +5V wire (`v1.0-no-5v`) a
write to $9010 lands at $D010, the 2026-09-18 fault; the wrong fix (`v1.0-a0fix`) is a fight at $D801. About 50 s.


`video_ram_test.py [port] [--quick]` drives the Bus Test Card (`tools/busdrv.py`, FTDI 19200) and exercises the video
card's 1K display RAM at $D000–$D3FF: address-derived and inverted patterns over every cell, one-cell neighbour isolation
(address-line shorts), the 2026-09-18 write-through check (writes to $0010, $9010, $0011, $1010 must not reach $D010) and a
read-stability pass with memory-card traffic in between ($D000 is undecoded on the memory card, so a floating bus can fake
a good read). `--quick` = first 64 cells (~1 min); full run ~14 min.

Results: 2026-09-21, after the card's +5V and VCC rails were joined — 8/8 PASS (quick and full). Before the join the
write-through fault reproduced (see `hardware/cards/video/README.md`).
Same day, RN2 restored to the design's 10k (from 1k): quick test 8/8 again.
