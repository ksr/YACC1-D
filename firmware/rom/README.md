# firmware/rom

- `shipped/rom` — the 8K image for the memory card's 28C64: BASIC at $E000 (`basic.img`) followed by the monitor at
  $F000 (`monitor.img`), built with `makerom`; reproducible from source (`tools/verify_firmware.py`). **2026-09-22: this
  is the rebuild with the monitor's G command fixed (`JSRUR R7`, was `BRVR R7`); **burned 2026-09-23 (the afternoon build below) and booting on the machine.** Before that the chip held
  the 2021 build, captured with the bus tester 2026-09-18: `eprom-captured-2026-09-18.bin/.hex` (byte-identical to
  the 2021 sources). Burn `shipped/rom`, then re-capture and compare (`tests/memory/rom_verify.py`).
- `shipped/rom.bin` — the same image as a flat 8,192-byte file for a chip programmer (Visual Minipro / minipro, device
  28C64): `python3 tools/img2bin.py firmware/rom/shipped/rom firmware/rom/shipped/rom.bin --base 0xE000 --end 0x10000 --fill 0xFF --size 8192`.
  Offset 0 = $E000; bytes the sources never write are $FF like a blank part. Checked 2026-09-22: its BASIC half is
  byte-identical to the chip capture, the monitor half differs (the new monitor: G fix, CF driver, O command, four
  new vectors). **Rebuilt 2026-09-23** (still not burned): a fifth vector, `UARTINNE` at $FFFC (console byte without
  echo, for Y1/OS's CONIN syscall; `firmware/abi/README.md`), so the table now ends exactly at $FFFF and the old
  end-label byte is gone. **Rebuilt again 2026-09-23 afternoon** (still not burned): the `:` Intel-hex loader
  (`tools/monload.py` on the host) and the banner `YACC 2020: HELLO WORLD  ROM 2026-09-23`, so the build date shows at
  power-up. MD5 d2d7b027e7c6951d7dd93412a8fd9cd8 (earlier: a42ea1ef… the morning build, 33efa63d… 2026-09-22).
  **Telling a chip apart**: the banner's date; failing that, $FFEC (`04` = a 2026 build, `00` = the 2021 chip) and
  $FFFC (`04` = 2026-09-23 or later). The exact vector bytes change with every monitor edit, so they are not quoted.
- `builds/2021-09-02-3bcacf3-not-working/rom` — the git-HEAD build, never burned.
- `makerom` — `awk` drops the last line of basic.img, then concatenates monitor.img.
