# vi — port notes (P8X -> Y1/OS, 2026-09-23)

Source: `~/Developer/p8x/os/commands/vi.c` (442 lines, p8cc 15,837 B of which 8,800 B the text buffer) and its
man page `p8x/os/man/vi`. Result: `os/commands/vi.c` (368 lines), `os/man/vi`. This is a fork: nothing is
kept in step with the P8X file.

## Size and fit

| | bytes | range |
|---|---|---|
| image (code + strings + runtime, `vi.bin`) | 5,985 | $5000-$6760 |
| text buffer `line[MAXL * W]`, MAXL = 320 lines x W = 80 | 25,600 | BSS |
| other BSS (path, names, cmd, pat, undo line, note, frames) | 558 | BSS |
| **end of BSS** | | **$CD8F** (625 bytes below $D000) |

The P8X buffer was 110 lines (8,800 B); 320 lines is what fits with a little headroom for later code. At
most ~327 lines would fit today (`MAXL` is one `#define`; each line costs 80 bytes). y1cc's code for the
same program is 0.85x the p8cc code (5,985 vs 7,037 B) even with the additions below.

## Mechanical changes

- `//#use apath` + `//#use abi` -> `#include "../lib_fs.c"` + `#include "y1lib.c"`. `abspath()` is gone: the Y1/OS
  file API resolves relative paths against the current directory itself.
- `bios(CONIN)` -> `conin()` (the CONIN syscall, the ROM's UARTINNE: no echo, CR arrives as LF on the machine);
  `bios(CONOUT)` -> `putchar()`, `outs()` -> `putstr()`.
- `load()`: FRESOLVE + FOPEN(RDBUF) + FGETB with the `& 256` carry tests -> `fopen()` / `fgetc()` until 65535 /
  `fclose()`. No `RDBUF` at $FC00: the OS's handle buffer is used.
- `save()`: FRESOLVE + FWOPEN + FPUTB + FCLOSE -> `fcreate(path, 0, 0)` + one `fwrite()` per line + `fputc(h, 10)`
  + `fclose()`; a same-named file is replaced by the OS (tombstoned). Load/exec are 0 (text).
- Recursion: `outn()` (recursive decimal printer for the ANSI arguments) is y1lib's iterative `putnum()`.
- `i*80` became `lp(i)` = `line + (i<<6) + (i<<4)` (y1cc inlines small constant shifts but calls a multiply loop
  for `*80`); the character-copy loops became pointer walks (`copyline`, `openslot`, `delchar`, `strcpy`).
- Argument: the first word of `argstr()` (`argword`, 63 chars) instead of the whole tail.

## Behaviour changes (YACC1-appropriate, all documented in `os/man/vi`)

- **`:w name`, `:wq name`, `:x name`** write to another file (vi semantics: the buffer keeps its own name, and `:w
  name` leaves `[+]` set unless `name` is the buffer's file). P8X had only `:w`/`:wq`/`:x` on the opened file.
- **Messages are visible.** P8X printed "no write since change" / "?unknown command" on row 24 and then `redraw()`
  wiped them at once. Now messages go to a one-shot `note` that `status()` shows on its next paint. New notes:
  `"NAME" N lines written`, `?cannot create NAME`, `?write error on NAME`, `[new file]`, `buffer full`.
- **Write errors are checked**: a failed `fcreate`/`fwrite`/`fputc`/`fclose` keeps `[+]` and `:wq`/`:x` do not quit.
- **`[cut]`** in the status row when `load()` dropped characters (lines over 79) or lines (past MAXL); P8X cut
  silently. Writing the buffer still writes the cut text: the flag is the warning.
- **Arrow keys**: `Esc [ A/B/C/D` map to `k j l h` (in INSERT the Esc leaves INSERT first, like classic vi). In P8X
  an arrow key in NORMAL mode ran `A` (append at end of line) because the Esc and `[` were ignored.
- **Ctrl-L** repaints (serial line noise).
- **End of input** (`conin()` = 65535: Ctrl-D, or the emulators' exhausted stdin): Esc in INSERT, `:q` in NORMAL;
  16 in a row abandon the edit so a scripted run cannot spin until the step limit. In the `:` and `/` rows it
  cancels like Esc.
- Fixed: `l` on an empty line moved the cursor to column 1 (`cx < llen - 1` with unsigned 0 - 1 = 65535); `dd`, `o`
  and a line split now `scroll()` before repainting (P8X could leave the cursor off-screen after `dd` at the
  bottom or Enter on row 23).
- `undo` of a `dd` in a full buffer leaves the cursor alone (P8X's `insline` refused the insert but undo still
  moved the cursor to the line that was not restored).

Unchanged: the key set otherwise, fixed 80-byte line slots, 24x80 screen, single-level op-based undo, literal
forward search with one wrap, 78-character growth limit, LF line ends, no tab expansion (a TAB in the file is sent
to the terminal raw and the cursor column is then off, as on P8X).

## Tests (2026-09-23, scratch disk = copy of `os/disk.img` + `p8xfs.py put ... /BIN/VI --replace`)

Built with `y1cc.py os/commands/vi.c --org 0x5000` + `asm vi -d=yacc1` (0 errors, 5,985 bytes) +
`img2bin.py --base 0x5000`. Sessions fed as `O\n` + keys, `emulator -x -m -c disk -l N` / `y1ucemu ... -l N`.

1. The requested run, both emulators: `vi /README.TXT`, `j`, `o`, "Added by vi on the YACC1.", Esc, `:x /T.TXT`,
   `cat /T.TXT`, `exit`. Transcript tail (escapes stripped):
   ```
   /> cat /T.TXT
   Y1/OS on the YACC1: a P8XFS v2 volume built by os/Makefile.
   LBA 0 boot block, LBA 1.. the OS (Y1OS.BIN), root directory at LBA 33, /BIN hol
   Added by vi on the YACC1.
   /> exit
   bye
   ```
   Line 2 of README.TXT is 96 characters, so the status row showed `[cut]` and /T.TXT has it cut to 79.
   `p8xfs.py fsck` OK, `get /T.TXT` = 166 bytes, the same three lines. Interpreter well inside 20M instructions;
   microcode emulator inside 80M steps (~4 s).
2. Interpreter, a short file `alpha beta gamma delta`: `jdd u GA end<Esc> /gam<Enter> x <Esc>[A iXY<BS><Esc>
   oone<Enter>two<Esc> :w /S2.TXT :x` -> both files `alpha / Xbeta / one / two / amma / delta end`; row 24 showed
   `"/S2.TXT" 6 lines written`; fsck OK.
3. Microcode emulator (no `q` quirk there): `x :q` -> `no write since change (:q! to force)`, `:zz` ->
   `?unknown command`, `:q!` quits; `jdd :wq` -> file `alpha gamma delta`; `vi /NEW.TXT` -> `[new file]`,
   `ihello, new file<Esc>:wq` -> the new file. fsck OK.
4. Interpreter, input ending inside vi with a dirty buffer: 15 x `no write since change`, then vi abandons and the
   shell prompt returns (the shell itself then loops on empty lines at end of input: an OS matter, not vi's).

## Emulator input quirk

The instruction-level emulator's `mygetchar()` turns a `q` byte into 0 (end of input), and `conin()` returns
65535 for it. So on that emulator `:q`, `:wq`, `:q!` and any text with a `q` cannot be typed: the sessions use
`:x` to save and quit. The microcode emulator and the machine are unaffected.

## Not done

- Not installed by `os/Makefile` beyond the `commands/*.c` wildcard (which already builds /BIN/VI); `os/man/vi`
  needs the Makefile's `/MAN` install when the man pages land.
- No `tests/os/vi.session` (tests/os belongs to the other port). Session 1 above is ready to become one: its
  input is `O\nvi /README.TXT\njoAdded by vi on the YACC1.\x1b:x /T.TXT\ncat /T.TXT\nexit\n` and the host check
  would be `("get", "/T.TXT", ...)` against a 3-line expected file.
- Not run on the real machine (no CF card yet). On the hardware every key is a syscall + a JSRUR through the ROM,
  a full repaint is up to ~2 KB of output (a 9600-baud line: ~2 s), so `dd`/`o`/Enter/scrolling will feel slow; a
  scroll-region (`ESC [ r`) or insert/delete-line (`ESC [ L` / `ESC [ M`) repaint would be the first speed-up.
- `load()` reads byte-wise with `fgetc()` (a syscall per byte); `fread()` sector-wise would be faster but costs a
  512-byte buffer (~6 lines of MAXL).
