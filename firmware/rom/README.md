# firmware/rom

- `shipped/rom` — the 8K image for the memory card's 28C64: BASIC at $E000 (`basic.img`) followed by the monitor at
  $F000 (`monitor.img`), built with `makerom`; reproducible from source (`tools/verify_firmware.py`). **2026-09-22: this
  is the rebuild with the monitor's G command fixed (`JSRUR R7`, was `BRVR R7`), NOT yet burned.** The chip still holds
  the 2021 build, captured with the bus tester 2026-09-18: `eprom-captured-2026-09-18.bin/.hex` (byte-identical to
  the 2021 sources). Burn `shipped/rom`, then re-capture and compare (`tests/memory/rom_verify.py`).
- `builds/2021-09-02-3bcacf3-not-working/rom` — the git-HEAD build, never burned.
- `makerom` — `awk` drops the last line of basic.img, then concatenates monitor.img.
