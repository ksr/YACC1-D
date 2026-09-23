# os — Y1/OS, the YACC1 disk operating system

A RAM-resident shell and file layer over a P8XFS v2 CompactFlash volume, written in C for
`software/compiler/y1cc.py` and loaded by the ROM monitor's `O` command. Started 2026-09-22 from the plan in
`docs/system/OS-PLAN.md`: **v0 (2026-09-22) = phases 1 and 2 read-only; v0.1 (2026-09-23) = write support and a
file API for programs, proven on both emulators** (the CF card itself is not built yet). Y1/OS is the YACC1's own
from here on: it is not kept in step with P8X/OS, and neither are the programs brought over (Ken, 2026-09-22).
Only the on-disk format is shared, so `tools/p8xfs.py` (a fork of the P8X tool) builds the images and reads back
what the OS writes.

```
make -C os              # build/y1os.bin, /BIN programs, disk.img
make -C os run          # the microcode emulator with the ROM and the disk: type O at the monitor prompt
make -C os run-int      # the instruction-level emulator
make -C os test         # tests/os/run.py: scripted sessions on both emulators against expected transcripts,
                        # then tools/p8xfs.py on the written image (fsck, ls, get)
```

## How it boots

The monitor's `O` command (ROM, `firmware/monitor/monitor.asm`) initialises the card (SET FEATURES, 8-bit mode),
reads the boot block (LBA 0) to $1000, checks the `P8` signature and OSCNT, reads LBA 1..OSCNT to $1000 and JSRURs
it. `y1os.c` is compiled with `--org 0x1000`, so `main` is the first byte of the image; `exit` makes main return,
and the monitor's prompt is back. `tools/p8xfs.py boot disk.img build/y1os.bin` installs it (14,673 bytes = 29 of
the 32 reserved sectors since redirection and pipes, 2026-09-23; 12,204 bytes = 24 sectors before; v0 was 5,136
bytes). Its image plus its data must end below $5000, where the programs start: 16,097 of the 16,384 bytes today,
which the Makefile checks and prints. At boot main() clears its BSS, fills the syscall table (below), and reads the
boot block again for the free-sector pointer.

## The shell

| Command | Effect |
|---|---|
| `dir [path]` | list a directory: name, `<DIR>` or size, and the load address of a program |
| `cd path` | change directory: absolute `/A/B`, relative, `.`/`..` (the directory's own entries) |
| `pwd` | print the current path (also the prompt) |
| `cat path` / `type` | print a file |
| `load path` | read a file into its stored load address |
| `run path [args]` | load it and call its exec address; `args` are left at ARGBUF ($0F40, up to 127 chars) for `argstr()` |
| `save path addr len` | write `len` bytes of memory from `addr` (both hex) to a new file whose load and exec address are `addr` |
| `del path` | delete a file (a tombstone in its directory; the sectors stay until a PACK exists) |
| `ren path newname` | rename a file or directory in place (`newname` is a bare name, 1..12 characters) |
| `mkdir path` | a new directory (a 4-sector extent with `.` and `..`, as `p8xfs.py mkdir` makes it) |
| `rmdir path` | remove an empty directory |
| `help` / `?` | this list |
| `exit` | back to the monitor |
| anything else | `/BIN/NAME` (upper-cased), then `NAME` in the current directory, run with the rest of the line as arguments |

**A `/BIN` program comes first** (since 2026-09-23): the shell looks for `/BIN/NAME` before its own words (only
`exit` is never looked up), so the ported `/BIN` `dir`, `cat`, `pwd`, `del` and `help` replace the built-ins of the
same name. The built-ins stay for a card that has no `/BIN` yet; `type` is always the built-in `cat`.

### Redirection and pipes (2026-09-23)

```
cmd [args] [< in] [> out | >> out] [| cmd [args] ...]        up to 4 commands in a pipeline
```

| | |
|---|---|
| `cmd > F` | stdout to the file F, replacing a file of that name **when the command is done** (the old F stays readable meanwhile, so `sort F > F` works) |
| `cmd >> F` | stdout appended to F (a new file if there is none) |
| `cmd < F` | stdin from F: what the filters read when no file is named (`wc < F`, `sort < F`) |
| `a \| b \| c` | a's stdout is b's stdin, b's is c's |
| `> F` alone | makes F empty |

The clauses come **after the command's arguments** (`echo hi > F`, not `echo > F hi`), in any order, each at most
once per command, with or without a space after the operator; `|`, `<` and `>` inside `'...'` or `"..."` are plain
text (`awk '/x/ {print $1 "|" $2}'`). Relative names resolve in the directory that is current when that command
starts. They apply to the built-ins too (`type F > G`, `pwd > G`, `load`'s message); the prompt, the shell's own
errors (`what?`, `syntax: ...`, `cannot read the < file`, `not found`...) and every command's diagnostics
(`lib_err.c` eputs) go to the screen. The redirect files are closed (a written one registered) after every command,
whatever happened; if a program never returns, the reset button restarts the OS with the console.

A pipe runs its commands **one after the other** (there is no multitasking): `a | b` runs a with stdout to
`/PIPE0.TMP`, then b with stdin from it; a third command reads `/PIPE0.TMP`'s successor `/PIPE1.TMP`, a fourth
`/PIPE0.TMP` again. The temp files are in the root (a command's `cd` cannot lose them) and are deleted after the
pipeline; like every deleted file their sectors come back only with a PACK. `cat F | more` pages the pipe while
`more` reads its keys from the keyboard.

**How:** the OS and every `/BIN` command are compiled with `y1cc --os`, which makes `putchar`/`puts` the syscall
CONOUT and `getchar` CONIN. The shell opens the files (`si_h`, `so_h` in `y1os.c`), CONOUT writes to the output file
or the raw console (`bios(CHAROUT)`), CONIN/CONST read the input file or the console; KEYIN is always the keyboard
(Unix pagers read `/dev/tty` for the same reason); STDIO tells a program which of its two are redirected.

**`>>` = append in place, or copy-then-extend.** A file is one contiguous extent and only the free pointer
allocates, so the new bytes must follow the old ones. When the file is the last thing written (its extent ends at
the free pointer: `echo a >> LOG` twice) the write handle simply carries on in its extent; otherwise the old sectors
are copied to the free pointer first (as P8X does). Either way no byte of the old file changes, and the entry is
rewritten only at close, in the old entry's own slot (one sector write): an append that fails or never closes leaves
the old file as it was. A real append mode in the syscall API was not added: in place is only possible for the last
file, and the copy costs no more when the shell does it.

**One write handle.** CREATE and MKDIR both allocate at the single free pointer, so while stdout goes to a file (a
`>`, a `>>`, or a pipe to the next command) a command's own CREATE/MKDIR fails cleanly with 0 and the command says
so: `cp`, `mv` across directories, `touch`, `save`, `mkdir`, `vi`'s `:w` and `cp -r` do not work inside a `>` or a
pipe (they do with `<`). Lifting it would need two files growing at once, i.e. allocation away from the one free
pointer (or a reserved area for the redirect file): not simple, so not done (BACKLOG). A redirect also holds one or
two of the four handles while the command runs.

Names are case-sensitive and stored as `p8xfs.py put` writes them; the Makefile puts programs in `/BIN` in upper
case, which is why the implicit lookup upper-cases the command word. Every shell command goes through the `fs_*`
functions that the syscalls expose (`cat` is `fs_open` + `fs_read`, `dir` is `fs_opendir` + `fs_readdir`, `save` is
`fs_create` + `fs_write` + `fs_close`...), so a program and the shell cannot disagree about a file.

## The file API (syscalls, 2026-09-23)

The OS fills a jump table in the monitor's free variable space at boot; a program calls entry `n` with y1cc's
`sys(n, a, b, c)` builtin, which stores the arguments in SYSARG0..2, JSRURs the entry, and returns SYSRES. Every
result is a full 16-bit word (no carry bit): 1/0 for done/cannot, a handle or 0, a count, a byte or **65535** for
"none" (end of file, end of console input). The numbers are `#define`d in `lib_abi.c` and wrapped in `lib_fs.c`:

| Address | Name | Use |
|---|---|---|
| $0F06 / $0F08 / $0F0A | SYSARG0 / 1 / 2 | the arguments (big-endian words, `peekw`/`pokew` order) |
| $0F0C | SYSRES | the result |
| $0F14..$0F3F | SYSTAB | 22 word entries, `SYSTAB + 2n` = the address of handler `n`; 0 for an unused slot |

| n | Name | Arguments | Result |
|---|---|---|---|
| 0 | OPEN | path | handle 1..4, or 0 (not found, a directory, over 64K, no handle free) |
| 1 | READ | handle, buf (512) | bytes put in buf: the whole sector holding the position, straight from the card; 0 at the end |
| 2 | GETC | handle | the next byte through the handle's own sector buffer; 65535 at the end |
| 3 | CLOSE | handle | 1; for a written file this writes the last sector, the directory entry and the free pointer |
| 4 | CREATE | path, load, exec | handle, or 0 (bad path/name, parent missing, another write open - also a `>` or a pipe of the shell - a directory of that name); a same-named FILE is replaced at CLOSE (its entry overwritten in place) |
| 5 | WRITE | handle, buf, n | bytes written |
| 6 | PUTC | handle, byte | 1, or 0 (not the write handle, 64K reached) |
| 7 | DELETE | path | 1 tombstoned, 0 not a file |
| 8 | MKDIR | path | 1, or 0 (exists, parent missing, directory full, a write open) |
| 9 | RMDIR | path | 1, or 0 (not a directory, not empty, `.`/`..`/root) |
| 10 | OPENDIR | path | a directory handle, or 0; `""` = the current directory |
| 11 | READDIR | handle, buf (32) | 1 with the next live entry (deleted ones skipped) in buf, 0 at the end |
| 12 | RESOLVE | path, buf (32) or 0 | 1 found (the entry copied to buf), 0 not found |
| 13 | GETCWD | buf (64) | the length; the current path, NUL-terminated, in buf |
| 14 | CHDIR | path | 1, 0 not found, 2 not a directory |
| 15 | RENAME | path, newname | 1, or 0 (`.`/`..`/root, a bad name, the new name taken) |
| 16 | ENTRY | buf (32) | 1; the 32-byte entry the last OPEN / OPENDIR / RESOLVE / DELETE... found (length, load, exec, start LBA, flags) |
| 17 | CONIN | | the next byte of STDIN without echo: the shell's `<` file or pipe (65535 at its end), else the console (the ROM's UARTINNE vector, $FFFC; 65535 on Ctrl-D and on NUL, the emulator's end of input). `y1cc --os`: `getchar()` |
| 18 | CONST | | 1 when a stdin byte is waiting: always 1 for a `<` file or pipe (CONIN never blocks there), else the ROM's CONST (always 1 on the emulators) |
| 19 | CONOUT | byte | nothing (SYSRES untouched): the byte to STDOUT, the shell's `>`/`>>` file or pipe, else the raw console (CHAROUT). `y1cc --os`: `putchar()`, `puts()` (2026-09-23) |
| 20 | KEYIN | | a KEY: always the console, never redirected, no echo; 65535 on Ctrl-D / NUL. The `--More--` key, `vi`, `dump`, `examine` (2026-09-23) |
| 21 | STDIO | | bit 0: stdin is redirected, bit 1: stdout is (the pager does not page into a file) (2026-09-23) |

All 22 slots are in use: the next syscall needs SYSTAB grown (ARGBUF moves) or a multiplexed entry.

Handles: four, each with its own 512-byte buffer and 16-bit position (so a file over 64K cannot be opened). A
read handle serves `GETC` (byte-wise, buffered) and `READ` (sector-wise into the caller's buffer; the position then
sits at the end of that sector, so mix the two only at sector boundaries); a directory handle serves `READDIR` (and
`READ` for the raw sectors). **One write handle at a time**: `CREATE` allocates at the volume's free pointer (boot
block bytes 4-5, LE16, the same pointer `p8xfs.py` uses), `PUTC`/`WRITE` fill the handle's buffer and write each
full sector, `CLOSE` writes the last (padded) sector, registers the file in the first free slot of its directory
(the `$00` end mark or a `$FF` tombstone, as `p8xfs.py add_entry` does) with the length, load and exec, and moves
the free pointer. `MKDIR` allocates at the same pointer, so it is refused while a write is open. What a program
leaves open, the shell closes when the program returns (a pending write is registered, not lost; the shell's own
redirect files stay open until the command is done). A same-named file is replaced at CLOSE, not at CREATE (since
2026-09-23): the new entry is written over the old one's slot, so the old file is whole and readable until then.
Files are contiguous: there is no seek and no PACK yet, and the only append is the shell's `>>` (above).

Directory entries are the 32-byte P8XFS v2 records, little-endian on disk: name[12] (space-padded) start[4]
length[4] load[2] exec[2] flags (1 file, 2 directory, $FF deleted, 0 end of directory); `lib_fs.c`'s `ent_len()`,
`ent_load()`, `ent_exec()`, `ent_lba()`, `ent_isdir()`, `ent_isfile()`, `ent_name()` read them.

## Writing a command

`os/commands/*.c`, compiled with `--org 0x5000 --os` (the transient area starts at $5000 and runs to $CFFF) and put
with `--load 0x5000 --exec 0x5000`. A program is an ordinary y1cc program: `main` returns to the shell, output is the
compiler's `putchar`/`puts`, which `--os` sends through the CONOUT syscall so that the shell can redirect it,
`argstr()` is its command tail, and files come from `#include "../lib_fs.c"` (which includes `lib_abi.c`):

```c
#include "../lib_fs.c"
#include "y1lib.c"
char buf[512];
void main() {                                   /* print a file, sector-wise */
    int h, n, i;
    h = fopen(argstr());
    if (!h) { puts("not found"); return; }
    while ((n = fread(h, buf))) for (i = 0; i < n; i++) putchar(buf[i]);
    fclose(h);
}
```

`lib_fs.c`: `fopen fread fgetc fclose fcreate fwrite fputc fputs fdelete fmkdir frmdir opendir readdir fresolve
fentry getcwd chdir frename conin constat keyin stdio`, the `ent_*` accessors, and `argword(tail, out, max)` to take
the next word of the command tail. Input comes in two kinds since the shell has pipes: DATA is `conin()`, stdin (a
`<` file, a pipe, else the console), 65535 at its end or at Ctrl-D, so a filter is
`while ((c = conin()) != 65535) ...`; a KEY the user presses in answer to the program (`--More--`, `vi`, `dump`'s
next page) is `keyin()`, always the keyboard. (`getchar()` under `--os` is CONIN too, with 0 at the end of input.)
Output is `putchar`/`puts`; an error message is `eputs()` from `lib_err.c`, which writes to the screen even under
`>` or `|`. A program that does not follow the rules still works on the console, but its output cannot be redirected
(built without `--os`) or its keys come out of the pipe (read with `conin()`).
The rules of the compiler apply: no recursion, `int` is unsigned (`>= 0` loops for ever), 16-bit literals only.
`make sizes` prints each program's image + uninitialised data against the 32K area (the build fails over it).

The shared libraries (`#include "../lib_NAME.c"`; each includes what it needs, each file once; `man NAME` for each):

| Library | For |
|---|---|
| `lib_abi.c` / `lib_fs.c` | the ROM vectors and syscall numbers / the file API wrappers, `ent_*`, `argword` |
| `lib_stdin.c` | `openarg(tail)` + `nextc()`: every word a file, a glob or `-` (stdin: a `<` file, a pipe or the console), read as one stream; no word = stdin; `sepfiles`, `curname`, `notfound()` |
| `lib_rdline.c` | `readline(buf)` on top of `nextc()` |
| `lib_glob.c` / `lib_globx.c` | `gmatch` (`*` `?`, case folded, iterative) / `glob_expand` a pattern into matching file paths, `isglob` |
| `lib_regex.c` | `match`/`matchhere`: `.` `*` `+` `?` `^` `$`, an explicit backtrack stack instead of recursion |
| `lib_walk.c` | `walk_open`/`walk_next`: a directory tree depth first, 8 levels, ONE directory handle (closed on the way down, reopened and skipped to on the way up) |
| `lib_apath.c` | `abspath(out, word)`: absolute, `.`/`..` folded |
| `lib_more.c` | `pgc`/`pgs`: the `--More--` pager (23 lines, space/Enter/q; the key from `keyin()`; no paging when stdout is a file or a pipe) |
| `lib_num.c` | `inc32`/`put32`: 32-bit counts and sizes on 16-bit ints |
| `lib_err.c` | `eputs`/`eput2`/`eputc`: error messages on the raw console (ROM CHAROUT), never into a `>` file or a pipe |

## The commands (`/BIN`, 2026-09-23)

Most were ported from the P8X (`os/PORT-PLAN.md` has the table: what changed and why, what was left out); each
source file's header says the same, and `/MAN/NAME` is its page (`man NAME`, `man` alone lists them). Several file
names, globs and `-` (the console until Ctrl-D) work wherever a command reads text.

| Command | Does |
|---|---|
| `awk [-F c] 'prog' [file...]` | one rule: `/re/ {print $1, $NF, NR, NF, "text"}` |
| `cat [file\|glob\|-]...` | print files byte-exact, or the console |
| `cmp f1 f2` | the first differing byte and line, or silence |
| `cp [-r] src dst` | copy a file, a glob into a directory, or (`-r`) a tree; load/exec kept |
| `del name\|glob...` | delete files |
| `dep addr b b...` | store hex bytes |
| `diff f1 f2` | the differing block: `< ` lines of f1, `> ` lines of f2 (150 lines per file) |
| `dir [-R] [-S] [path\|glob]` | sorted listing with sizes and load addresses; `-S` by size; `-R` every directory below, `ls -R` style |
| `dump addr` | hex + ASCII, 256 bytes a key |
| `echo text` | print the argument tail |
| `examine addr` | show and change bytes one at a time |
| `find pattern [dir]` | paths whose name contains the text, or matches the glob |
| `grep [-r] re [file...\|dir]` | matching lines; `NAME:` with several files; `-r` a tree |
| `head [-N] [file...]` / `tail [-N] [file...]` | the first / last N lines (10; tail up to 40) |
| `hello [args]` | the first /BIN program |
| `help` | the command list |
| `ls [path]` | a plain listing through opendir/readdir |
| `man [name]` | `/MAN/NAME` through the pager; alone: the page names |
| `md [-p] [file]` | Markdown rendered (ANSI, or plain with `-p`), paged; names are looked up in `/DOCS` too; alone: the list |
| `more [file...]` | page text (or stdin: `dir -R \| more`): space, Enter, q from the keyboard |
| `mv src dst` | rename in place (RENAME), or move to another directory (copy + delete), globs into a directory |
| `pwd` | the current directory |
| `sed s/re/new/[g] [file...]` | substitute (shortest match) |
| `sort [file...]` | lines in byte order (200 lines of 79) |
| `touch name...` | empty files for the names that do not exist |
| `tree [dir]` | the tree, indented, depth first |
| `uniq [file...]` | drop adjacent repeats |
| `vi [file]` | the screen editor (VT100) |
| `wc [file...]` | lines, words, bytes (32-bit) |

Also on the disk: `/MAN` (the pages, from `os/man/`), `/DOCS` (this README as `OS.MD`, the compiler README as
`Y1CC.MD`, `OSPLAN.MD`, `PORT.MD` and `MDDEMO.MD`, md's own sample), and `/FRUIT.TXT` + `/FRUIT2.TXT`, seven lines of
sample data for trying the filters (`sort`, `uniq`, `awk`, `diff` ... the man pages' examples use them).

## Memory

| Range | Use |
|---|---|
| $0400–$0BFF | the four handles' 512-byte buffers (`HBUFS`, since 2026-09-23: out of the OS's 16K to make room for redirection; BASIC's scratch $0400-$04FF, idle while the OS runs, and the free $0500-$0BFF above the stack's floor $0C00) |
| $0EFF down | the hardware stack, the monitor's (not below $0C00: the handle buffers end at $0BFF) |
| $0F06–$0F0D | SYSARG0..2, SYSRES (the OS's syscall parameter block) |
| $0F10–$0F12 | CFLBA0..2, the sector for CFREAD/CFWRITE (ROM variables) |
| $0F14–$0F3F | SYSTAB, the syscall jump table (22 entries, all used since 2026-09-23) |
| $0F40–$0FBF | ARGBUF, a program's command tail (127 chars + NUL; the upper half overlays the monitor's idle line buffer) |
| $1000–$4FFF | the OS image (14.3K today) and its data (1.4K): sector buffer, line, path, directory and pipeline state; the Makefile fails the build past $4FFF |
| $5000–$CFFF | programs |

## Inside

- `cfread(lba, buf)` / `cfwrite(lba, buf)` = poke the LBA into the ROM's variables, `bios(CFREAD/CFWRITE, buf, 0)`;
  the ROM streams 512 bytes through the two CF ports (P8 select, P9 data).
- `take_entry()` fills the `e_*` globals (and `e_raw`, the record itself, plus `e_slba`/`e_off`, where it sits)
  for the entry a scan found; `find_in()` scans one extent sector by sector, stopping at the $00 end mark and
  skipping $FF tombstones; `find_slot()` finds the first free slot; `resolve()` walks a path component by component,
  iteratively (y1cc rejects recursion); `parent_of()` splits a path into the directory that holds its last
  component and the leaf, for CREATE/MKDIR; `fs_chdir` keeps the textual path for the prompt as it goes and restores
  it on failure.
- The handle table is five parallel arrays (`h_mode h_lba h_len h_pos h_cur`, index 1..4); the hot functions copy
  the fields into locals first because an indexed access costs y1cc ~25 bytes against 3 for a local (that took the
  image from 12.8K to 12.2K).
- The `h_*` handlers are one line each: `pokew(SYSRES, fs_x(peekw(SYSARG0), ...))`; `install()` writes their
  addresses with `funcaddr()`. A handler runs on the OS's static frames while the shell sits in `run_prog()`, which
  has nothing live across the call, so a program's syscalls and the shell never collide.
- `sbuf` (directory scans, the boot block) is separate from the handle buffers, so a directory lookup during a
  read never disturbs the file being read.
- **The static-frame rule of the console handlers** (2026-09-23): y1cc gives every function one fixed frame, and
  with `--os` the OS's own `putchar`/`puts` ARE the CONOUT syscall. So the console handlers and everything they call
  (`con_out`, `con_in`, `key_in`, `con_st`, `fs_putc`, `fs_getc`, `mode_of`, `hb`, `cfread`, `cfwrite`) must never
  print, directly or through anything: a handler would re-enter itself on the frame in use. Their errors are return
  codes (a byte that cannot be written - full disk, 64K - is dropped silently); the shell's messages use `eputs()`,
  the raw console. `y1cc` cannot check this: calls through SYSTAB are invisible to its call graph.
- The shell parses a line in place (`split()`): commands split at `|`, the redirect names NUL-terminated where
  they stand; `stage()` opens a command's input and output, `run_cmd()` runs it, `io_reset()` closes both.

## Not there yet

PACK (reclaim tombstoned sectors; pipes and `>>` make it more pressing), FORMAT and FSCK on the target (the host
tool has them), seek, a second write handle (so `cp` works inside a `>` or a pipe), concurrent pipes (they run one
after the other through temp files), `2>` (errors always go to the screen), the command history, the P8X development
tools (`asm`, a YACC1 `disasm`; `os/PORT-PLAN.md` wave 3), BASIC as `/BIN/BASIC`, and the CF card in hardware, all in
BACKLOG.md.
