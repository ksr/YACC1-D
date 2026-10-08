# firmware/rom

- `shipped/rom` — the 8K image for the memory card's 28C64: BASIC at $E000 (`basic.img`) followed by the monitor at
  $F000 (`monitor.img`), built with `makerom`; reproducible from source (`tools/verify_firmware.py`). **2026-09-22: this
  is the rebuild with the monitor's G command fixed (`JSRUR R7`, was `BRVR R7`); **burned 2026-09-23 (the afternoon build below) and booting on the machine.** Before that the chip held
  the 2021 build, captured with the bus tester 2026-09-18: `eprom-captured-2026-09-18.bin/.hex` (byte-identical to
  the 2021 sources). Burn `shipped/rom`, then re-capture and compare (`tests/memory/rom_verify.py`).
- **2026-09-25: `shipped/rom` and `rom.bin` are `ROM 2026-09-25` — NOT BURNED.** The monitor gains the video unit
  (`docs/programming/MONITOR.md` section 11): the $D000 probe at reset (`VIDEO CARD FOUND` in the banner), a screen
  driver, CHAROUT/UARTOUT mirroring while `VIDMIR` ($0FF1) is set (off at reset: `VIDAUTO EQU 0`), the `V` command,
  the video entry `JSR vidctl / RET` at $FFBC below the full vector table, variables at $0FF0-$0FF7; to make room the
  help text is shorter and six never-called routines and the T-menu's help strings are gone. BASIC is unchanged.
  Monitor half 3,947 of 4,096 bytes (149 free: $FF15-$FF8F and $FFA2-$FFBB). **MD5 (rom.bin)
  3ebc67898f70d319853fe42abdfd2cb9**; `tools/verify_firmware.py`: FIRMWARE VERIFIED. The chip in the machine is still
  `ROM 2026-09-23` (d2d7b027, below), and everything else in the tree still works with it: Y1/OS's `video` command
  says that ROM has no driver. Burn the new one when ready; afterwards $FFBC reads $04 (the old chip: $FF).
- **2026-10-07: `shipped/rom` and `rom.bin` are `ROM 2026-10-07` — NOT BURNED.** The 2026-09-25 monitor (the video
  unit above, unchanged but for the banner date) and BASIC with its line input fixed (`firmware/basic/README.md`):
  backspace and DEL take back a character, lower case is accepted (letters outside `"..."` are stored in upper
  case), and a character no token starts with gives `SYNTAX ERROR` instead of an endless loop. BASIC half 3,983 of
  4,096 bytes. **MD5 (rom.bin) 3a4ff07923bff1cf752a5f67c9df3526**; `tools/verify_firmware.py`: FIRMWARE VERIFIED.
  **The chip in the machine is an Atmel AT28C64B** (its marking, 2026-10-07). Burn with the TL866II+ and minipro
  (`brew install minipro`; it warned firmware 04.2.86 against the 04.2.132 it expects, and worked):
  `minipro -p AT28C64B -u -P -w firmware/rom/shipped/rom.bin` - `-u` lifts the software data protection before
  writing, `-P` sets it again afterwards, so on the machine a store into $E000-$FFFF (review M2: the v1.3 card has
  no write-protect jumper) is ignored by the chip. Nothing in the tree writes the ROM in place. Then read back and
  compare: `minipro -p AT28C64B -r /tmp/rb.bin && cmp /tmp/rb.bin firmware/rom/shipped/rom.bin`.
- `shipped/rom.bin` — the same image as a flat 8,192-byte file for a chip programmer (Visual Minipro / minipro, device
  28C64): `python3 tools/img2bin.py firmware/rom/shipped/rom firmware/rom/shipped/rom.bin --base 0xE000 --end 0x10000 --fill 0xFF --size 8192`.
  Offset 0 = $E000; bytes the sources never write are $FF like a blank part. Checked 2026-09-22: its BASIC half is
  byte-identical to the chip capture, the monitor half differs (the new monitor: G fix, CF driver, O command, four
  new vectors). **Rebuilt 2026-09-23** (still not burned): a fifth vector, `UARTINNE` at $FFFC (console byte without
  echo, for Y1/OS's CONIN syscall; `firmware/abi/README.md`), so the table now ends exactly at $FFFF and the old
  end-label byte is gone. **Rebuilt again 2026-09-23 afternoon** (still not burned): the `:` Intel-hex loader
  (`tools/monload.py` on the host) and the banner `YACC 2020: HELLO WORLD  ROM 2026-09-23`, so the build date shows at
  power-up. MD5 d2d7b027e7c6951d7dd93412a8fd9cd8 (earlier: a42ea1ef… the morning build, 33efa63d… 2026-09-22);
  that build was burned and boots, and it is the current image again: a 2026-09-23 evening rebuild (`ROM 2026-09-23B`,
  CF on P4/P5 for an I/O card v2.0) was withdrawn on 2026-09-24, when the CF interface moved to the memory card and back
  to ports P8/P9. The chip in the machine matched `shipped/rom.bin` byte for byte until the 2026-09-25 rebuild
  above (`git show 65851b0:firmware/rom/shipped/rom.bin` is its image).
  **Telling a chip apart**: the banner's date; failing that, $FFEC (`04` = a 2026 build, `00` = the 2021 chip) and
  $FFFC (`04` = 2026-09-23 or later). The exact vector bytes change with every monitor edit, so they are not quoted.
- `builds/2021-09-02-3bcacf3-not-working/rom` — the git-HEAD build, never burned.
- `makerom` — `awk` drops the last line of basic.img, then concatenates monitor.img.
