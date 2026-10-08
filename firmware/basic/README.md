# firmware/basic

`basic.asm` — the hand-assembled port of uBASIC (`software/ubasic-c/`) as burned (git ff7d85a, 2021-07-09) with its
`.img` (reproducible, see `tools/verify_firmware.py`) and `.lst`. Lives at $E000, variables at $0100/$0200.
- `candidates/2021-09-8afde21/` — adds ON/OFF statements and break-in via `charavail`; never burned.
- `candidates/2021-09-02-3bcacf3-not-working/` — git HEAD, "not working"; with its build products.
- `candidates/2020-11-10-port-draft/` — `basic.asmtmp copy`, the port in progress (Nov 2020); `basic.asmold.asm` — the
  first 1 KB sketch of it.

## Typing BASIC (2026-10-07)

Keywords and variables are upper case inside the interpreter: the keyword table is written in lower case in
`basic.asm`, but the assembler upper-cases every source line, so the ROM holds `LET`, `PRINT`, ... Start it with `I`
at the monitor (prompt `>>`); `LIST`, `RUN`, `NEW`, `EXIT` are its commands, a line starting with a number is stored.

- **Case**: since the 2026-10-07 build the line input stores every letter outside `"..."` in upper case, so
  `10 print a` is `10 PRINT A`; text in quotes keeps its case (`PRINT "Hi There"`). Before it, a lower-case letter
  (or any character no token starts with) made the tokenizer return an error without moving on, and the line loop
  asked for the same token forever: the machine hung until reset.
- **Backspace / DEL** take back the last character and blank it on the screen (at the start of the line they do
  nothing). Before, the `$08` went into the line.
- **SYNTAX ERROR**: a character no token starts with (`!`, `@`, a control character) drops the line with that
  message; the program and the prompt are unchanged.

Tested on both emulators (`software/emulator`, `software/ucemu`, `-x -m` with the keystrokes on stdin) and, for the
hang, on the machine (`ROM 2026-09-23`, 2026-10-07: `10 print 5` at `>>` hung it). Not on the machine yet with the fix:
burn `firmware/rom/shipped/rom.bin` (`firmware/rom/README.md`).

