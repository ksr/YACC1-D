# firmware — code that runs INSIDE the machine

| Folder | Contents | Proof |
|---|---|---|
| `monitor/` | `monitor.asm` + `.img/.lst`: the 2021 source (git ff7d85a, what is burned) **plus one 2026-09-22 change: G = `JSRUR R7` (was `BRVR R7`, an indirect jump), to burn next**; `candidates/` = later never-burned versions; `monnew-2025/` = a small new D/M/B monitor draft | `tools/verify_firmware.py` |
| `basic/` | `basic.asm` (the uBASIC port) + `.img/.lst`, same commit; `candidates/` = later versions and the Nov-2020 port draft | |
| `rom/` | `shipped/rom` = the image to burn (2026-09-22 rebuild: BASIC unchanged + the G-fixed monitor); `eprom-captured-2026-09-18.*` = what the chip holds (the 2021 build); `builds/` = other builds; `makerom` | |
| `microcode/` | `ucode-generator2/` (the C generator) + `yaccsignaldefine.h`/`yaccsignaldata2.h` (signal table) + `test.hex` (the image) | |
| `abi/` | to be written: BIOS vectors ($FFC0..), variable map, port map, derived from the two .asm headers | |

**`tools/verify_firmware.py`** rebuilds all of it from these sources in a scratch dir and diffs: assembler →
`monitor.img`, `basic.img` → `rom` (== burned EEPROM); generator → `test.hex`. All IDENTICAL as of 2026-09-20.
Assembler invocation gotcha: `asm monitor -d=yacc1` — the source name must come BEFORE `-d=…` (the option handler skips
the following argument).
