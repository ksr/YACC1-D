# firmware — code that runs INSIDE the machine

| Folder | Contents | Proof |
|---|---|---|
| `monitor/` | `monitor.asm` + `.img/.lst` (git ff7d85a, 2021-07-09 = what is burned); `candidates/` = later never-burned versions; `monnew-2025/` = a small new D/M/B monitor draft | |
| `basic/` | `basic.asm` (the uBASIC port) + `.img/.lst`, same commit; `candidates/` = later versions and the Nov-2020 port draft | |
| `rom/` | `shipped/rom` = the EEPROM image (captured from the chip 2026-09-18, identical); `builds/` = other builds; `makerom` | |
| `microcode/` | `ucode-generator2/` (the C generator) + `yaccsignaldefine.h`/`yaccsignaldata2.h` (signal table) + `test.hex` (the image) | |
| `abi/` | to be written: BIOS vectors ($FFC0..), variable map, port map, derived from the two .asm headers | |

**`tools/verify_firmware.py`** rebuilds all of it from these sources in a scratch dir and diffs: assembler →
`monitor.img`, `basic.img` → `rom` (== burned EEPROM); generator → `test.hex`. All IDENTICAL as of 2026-09-20.
Assembler invocation gotcha: `asm monitor -d=yacc1` — the source name must come BEFORE `-d=…` (the option handler skips
the following argument).
