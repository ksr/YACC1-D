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

Tested on both emulators (`software/emulator`, `software/ucemu`, `-x -m` with the keystrokes on stdin) and on the
machine: with `ROM 2026-09-23`, `10 print 5` at `>>` hung it; with `ROM 2026-10-07` (burned 2026-10-07) lower-case
lines, a string, backspaces, `LIST`, `RUN` and `50 print !` (SYNTAX ERROR) all behave as above.

**Layout (2026-10-08).** The new code (`gil_start`, `parse_token_chk`, `parse_line_syntax`, the message) sits after
`CRLF`, at the end of BASIC; `get_inputline` keeps its original 17-byte slot as a branch to `gil_start`, and the line
loop calls `parse_token_chk` instead of `parse_token` (same size). So everything before $EF3E is byte for byte
ROM 2026-09-23's but those two places. The first 2026-10-07 build had the new code early in the file and moved most
routines; on the machine `LIST` then misprinted a line number (`BACKLOG.md`, "A placement-dependent wrong value").
Tested on the machine 2026-10-08: lower-case lines, backspaces (also inside a string and at the start of a line),
`LIST`, `RUN`, `NEW`, `SYNTAX ERROR`, and the programs that misprinted before.

