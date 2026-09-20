# firmware/rom

- `shipped/rom` — the 8K image in the memory card's 28C64: BASIC at $E000 (`basic.img`) followed by the monitor at
  $F000 (`monitor.img`), built with `makerom`. Byte-identical to the chip (captured with the bus tester 2026-09-18:
  `eprom-captured-2026-09-18.bin/.hex`) and reproducible from source (`tools/verify_firmware.py`).
- `builds/2021-09-02-3bcacf3-not-working/rom` — the git-HEAD build, never burned.
- `makerom` — `awk` drops the last line of basic.img, then concatenates monitor.img.
