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
and the monitor's prompt is back. `tools/p8xfs.py boot disk.img build/y1os.bin` installs it (12,183 bytes = 24 of
the 32 reserved sectors on 2026-09-23; v0 was 5,136 bytes). At boot main() clears its BSS, fills the syscall table
(below), and reads the boot block again for the free-sector pointer.

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
| 4 | CREATE | path, load, exec | handle, or 0 (bad path/name, parent missing, another write open, a directory of that name); a same-named FILE is replaced (tombstoned) |
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
| 17 | CONIN | | a console byte WITHOUT echo (the ROM's UARTINNE vector, $FFFC); 65535 on Ctrl-D and on NUL (the emulator's end of input) |
| 18 | CONST | | 1 when a console byte is waiting (the ROM's CONST; always 1 on the emulators) |
| 19..21 | | | spare (0) |

Handles: four, each with its own 512-byte buffer and 16-bit position (so a file over 64K cannot be opened). A
read handle serves `GETC` (byte-wise, buffered) and `READ` (sector-wise into the caller's buffer; the position then
sits at the end of that sector, so mix the two only at sector boundaries); a directory handle serves `READDIR` (and
`READ` for the raw sectors). **One write handle at a time**: `CREATE` allocates at the volume's free pointer (boot
block bytes 4-5, LE16, the same pointer `p8xfs.py` uses), `PUTC`/`WRITE` fill the handle's buffer and write each
full sector, `CLOSE` writes the last (padded) sector, registers the file in the first free slot of its directory
(the `$00` end mark or a `$FF` tombstone, as `p8xfs.py add_entry` does) with the length, load and exec, and moves
the free pointer. `MKDIR` allocates at the same pointer, so it is refused while a write is open. What a program
leaves open, the shell closes when the program returns (a pending write is registered, not lost). Files are
contiguous, never grown in place: there is no seek, no append to an existing file, no PACK yet.

Directory entries are the 32-byte P8XFS v2 records, little-endian on disk: name[12] (space-padded) start[4]
length[4] load[2] exec[2] flags (1 file, 2 directory, $FF deleted, 0 end of directory); `lib_fs.c`'s `ent_len()`,
`ent_load()`, `ent_exec()`, `ent_lba()`, `ent_isdir()`, `ent_isfile()`, `ent_name()` read them.

## Writing a command

`os/commands/*.c`, compiled with `--org 0x5000` (the transient area starts at $5000 and runs to $CFFF) and put with
`--load 0x5000 --exec 0x5000`. A program is an ordinary y1cc program: `main` returns to the shell, console output is
the compiler's `putchar`/`puts` through the BIOS vectors, `argstr()` is its command tail, and files come from
`#include "../lib_fs.c"` (which includes `lib_abi.c`):

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
fentry getcwd chdir frename conin constat`, the `ent_*` accessors, and `argword(tail, out, max)` to take the next
word of the command tail. Reading the console: `conin()` returns 65535 at Ctrl-D, so a filter is
`while ((c = conin()) != 65535) ...` (`getchar()` still works but echoes on the machine, as the ROM's UARTIN does).
The rules of the compiler apply: no recursion, `int` is unsigned (`>= 0` loops for ever), 16-bit literals only.
`make sizes` prints each program's image + uninitialised data against the 32K area (the build fails over it).

The shared libraries (`#include "../lib_NAME.c"`; each includes what it needs, each file once; `man NAME` for each):

| Library | For |
|---|---|
| `lib_abi.c` / `lib_fs.c` | the ROM vectors and syscall numbers / the file API wrappers, `ent_*`, `argword` |
| `lib_stdin.c` | `openarg(tail)` + `nextc()`: every word a file, a glob or `-` (the console), read as one stream; `sepfiles`, `curname`, `notfound()` |
| `lib_rdline.c` | `readline(buf)` on top of `nextc()` |
| `lib_glob.c` / `lib_globx.c` | `gmatch` (`*` `?`, case folded, iterative) / `glob_expand` a pattern into matching file paths, `isglob` |
| `lib_regex.c` | `match`/`matchhere`: `.` `*` `+` `?` `^` `$`, an explicit backtrack stack instead of recursion |
| `lib_walk.c` | `walk_open`/`walk_next`: a directory tree depth first, 8 levels, ONE directory handle (closed on the way down, reopened and skipped to on the way up) |
| `lib_apath.c` | `abspath(out, word)`: absolute, `.`/`..` folded |
| `lib_more.c` | `pgc`/`pgs`: the `--More--` pager (23 lines, space/Enter/q) |
| `lib_num.c` | `inc32`/`put32`: 32-bit counts and sizes on 16-bit ints |
| `lib_err.c` | `eputs`: error messages (one place to move them to the raw console once `>` exists) |

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
| `more [file...]` | page text: space, Enter, q |
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
| $0F06–$0F0D | SYSARG0..2, SYSRES (the OS's syscall parameter block) |
| $0F10–$0F12 | CFLBA0..2, the sector for CFREAD/CFWRITE (ROM variables) |
| $0F14–$0F3F | SYSTAB, the syscall jump table (22 entries) |
| $0F40–$0FBF | ARGBUF, a program's command tail (127 chars + NUL; the upper half overlays the monitor's idle line buffer) |
| $1000–$4FFF | the OS image (12.2K today) and its data: sector buffer, four handle buffers (2K), line, path, directory state |
| $5000–$CFFF | programs |
| $0EFF down | the hardware stack, the monitor's |

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

## Not there yet

PACK (reclaim tombstoned sectors), FORMAT and FSCK on the target (the host tool has them), seek/append, output
redirection and pipes (the filters read files or the console until then), the command history, the P8X development
tools (`asm`, a YACC1 `disasm`; `os/PORT-PLAN.md` wave 3), BASIC as `/BIN/BASIC`, and the CF card in hardware, all in
BACKLOG.md.
