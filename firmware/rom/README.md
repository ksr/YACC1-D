# firmware/rom

- `shipped/rom` — the 8K image for the memory card's 28C64: BASIC at $E000 (`basic.img`) followed by the monitor at
  $F000 (`monitor.img`), built with `makerom`; reproducible from source (`tools/verify_firmware.py`). **2026-09-22: this
  is the rebuild with the monitor's G command fixed (`JSRUR R7`, was `BRVR R7`), NOT yet burned.** The chip still holds
  the 2021 build, captured with the bus tester 2026-09-18: `eprom-captured-2026-09-18.bin/.hex` (byte-identical to
  the 2021 sources). Burn `shipped/rom`, then re-capture and compare (`tests/memory/rom_verify.py`).
- `shipped/rom.bin` — the same image as a flat 8,192-byte file for a chip programmer (Visual Minipro / minipro, device
  28C64): `python3 tools/img2bin.py firmware/rom/shipped/rom firmware/rom/shipped/rom.bin --base 0xE000 --end 0x10000 --fill 0xFF --size 8192`.
  Offset 0 = $E000; bytes the sources never write are $FF like a blank part. Checked 2026-09-22: its BASIC half is
  byte-identical to the chip capture, the monitor half differs (the new monitor: G fix, CF driver, O command, four
  new vectors), and $FFFC holds the monitor's end label byte. MD5 33efa63dbd9e141f739888f139f86bc9.
- `builds/2021-09-02-3bcacf3-not-working/rom` — the git-HEAD build, never burned.
- `makerom` — `awk` drops the last line of basic.img, then concatenates monitor.img.
