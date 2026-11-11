# os — Y1/OS, the YACC1 disk operating system

A RAM-resident shell and file layer over a P8XFS v2 CompactFlash volume, loaded by the ROM monitor's `O` command.
Started 2026-09-22 from the plan in `docs/system/OS-PLAN.md`: **v0 (2026-09-22) = phases 1 and 2 read-only; v0.1
(2026-09-23) = write support and a file API for programs, proven on both emulators; v0.2 (2026-09-23) = the same OS
rewritten in YACC1 assembly (`y1os.asm`), half the size and 1.3-1.9x faster** (the CF hardware, planned on the
memory card, is not built yet). `y1os.c`, the C version for `software/compiler/y1cc.py`, stays as the specification: `make -C os OS=c` builds
and installs it instead, and both pass the same tests (below, "The assembly OS"). Y1/OS is the YACC1's own
from here on: it is not kept in step with P8X/OS, and neither are the programs brought over (decided 2026-09-22).
Only the on-disk format is shared, so `tools/p8xfs.py` (a fork of the P8X tool) builds the images and reads back
what the OS writes.

```
make -C os              # build/y1os.bin (the assembly OS), /bin programs, disk.img
make -C os OS=c         # the same with the C OS (y1os.c); build/os-sel remembers the choice, disk.img follows it
make -C os run          # the microcode emulator with the ROM and the disk: type O at the monitor prompt
make -C os run-int      # the instruction-level emulator
make -C os test         # tests/os/run.py: scripted sessions on both emulators against expected transcripts,
                        # then tools/p8xfs.py on the written image (fsck, ls, get)
```

## How it boots

The monitor's `O` command (ROM, `firmware/monitor/monitor.asm`) initialises the card (SET FEATURES, 8-bit mode),
reads the boot block (LBA 0) to $1000, checks the `P8` signature and OSCNT, reads LBA 1..OSCNT to $1000 and JSRURs
it. `y1os.asm` starts at `ORG 1000H` with its entry (`os_start`), so the monitor lands on it; `exit` RETs and the
monitor's prompt is back. `tools/p8xfs.py boot disk.img build/y1os.bin` installs it: **7,808 bytes = 16 of the 32
reserved sectors** (2026-09-25 with 24-bit files, SYSTAB2, EXIT/EXEC/SEEK; 7,151 on 2026-09-23 (v0.2); the C version
is 14,041 bytes = 28 sectors compiled with `--xisa`, 14,619 = 29 without on 2026-09-23, 12,204 = 24 before
redirection and pipes, and v0 was 5,136). Its image must end below its RAM at $4A00 (the Makefile checks and prints
it: 7,040 bytes free between them); the C version's image plus data must end below $4FC0 (15,829 of 16,320). Since 2026-09-25 the C version is
always compiled with `y1cc --xisa`: with 24-bit files it no longer fitted without (it is the specification and runs
on the emulators; the machine runs the assembly OS). At boot the OS
clears its RAM $4A00-$4FFF (the C clears its BSS: the same effect, the handle table and the redirect state zeroed),
fills the syscall table (below), and reads the boot block again for the free-sector pointer;
it keeps that pointer in RAM and reads it again after every program returns (`read_free()` in `run_prog()`, since
2026-09-23), because `/bin/pack` lowers it on the disk.

## The shell

| Command | Effect |
|---|---|
| `dir [path]` | list a directory: name, `<DIR>` or size, and the load address of a program |
| `cd path` | change directory: absolute `/a/b`, relative, `.`/`..` (the directory's own entries) |
| `pwd` | print the current path (also the prompt) |
| `cat path` / `type` | print a file |
| `load path` | read a file into its stored load address |
| `run path [args]` | load it and call its exec address; `args` are left at ARGBUF ($0F40, up to 127 chars) for `argstr()` |
| `save path addr len` | write `len` bytes of memory from `addr` (both hex) to a new file whose load and exec address are `addr` |
| `del path` | delete a file (a tombstone in its directory; `pack` gets the sectors back) |
| `ren path newname` | rename a file or directory in place (`newname` is a bare name, 1..12 characters) |
| `mkdir path` | a new directory (a 16-sector extent with `.` and `..`, 254 entries, as `p8xfs.py mkdir` makes it; 4 and 62 until 2026-11-05); `/bin/mkdir` replaces it and adds `-s N` (below) |
| `rmdir path` | remove an empty directory |
| `help` / `?` | this list |
| `sh path` | run a script: the file's lines one after the other, as if typed (2026-11-03, "Scripts" below) |
| `exit` | back to the monitor |
| anything else | `/bin/name`, then `name` in the current directory (the word lower-cased, so any case finds it), run with the rest of the line as arguments; a `name.sh` runs as a script |

**A `/bin` program comes first** (since 2026-09-23): the shell looks for `/bin/name` before its own words (only
`exit` is never looked up), so the ported `/bin` `dir`, `cat`, `pwd`, `del` and `help` replace the built-ins of the
same name. The built-ins stay for a card that has no `/bin` yet; `type` is always the built-in `cat`.

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
`/pipe0.tmp`, then b with stdin from it; a third command reads `/pipe0.tmp`'s successor `/pipe1.tmp`, a fourth
`/pipe0.tmp` again. The temp files are in the root (a command's `cd` cannot lose them) and are deleted after the
pipeline; like every deleted file their sectors come back with `pack`. `cat F | more` pages the pipe while
`more` reads its keys from the keyboard.

**How:** the OS and every `/bin` command are compiled with `y1cc --os`, which makes `putchar`/`puts` the syscall
CONOUT and `getchar` CONIN. The shell opens the files (`si_h`, `so_h` in `y1os.c`), CONOUT writes to the output file
or the raw console (`bios(CHAROUT)`), CONIN/CONST read the input file or the console; KEYIN is always the keyboard
(Unix pagers read `/dev/tty` for the same reason); STDIO tells a program which of its two are redirected.

**Line ends (2026-11-03).** Programs and files end lines with LF alone. On the raw console the kernels send an LF as
LF CR, the monitor's line end (`conraw` in `y1os.asm`, `raw_out` in `y1os.c`; `lib_err.c` eputc and `/bin/asm` do
the same for their error messages), and the shell sends a CR after the Enter the ROM echoes as LF. Files, `>`, `>>`
and pipes keep LF alone. Before, a plain terminal showed every line one step to the right of the last.

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

Names are case-sensitive and stored as `p8xfs.py put` writes them. **Every name on the disk is lower case since
2026-11-03** (`/bin/cat`, `/lib/cc/cc1`, `/man`, `/docs`, `/src`, `fruit.txt`), as in Unix, with Unix's own capitals
kept (`README`, the `Makefile`s); before, they were upper case (`/BIN/CAT`). The shell lower-cases a command word
before it looks it up, so `ls`, `LS` and `Ls` all run `/bin/ls`; the names in the arguments are exact. Every shell command goes through the `fs_*`
functions that the syscalls expose (`cat` is `fs_open` + `fs_read`, `dir` is `fs_opendir` + `fs_readdir`, `save` is
`fs_create` + `fs_write` + `fs_close`...), so a program and the shell cannot disagree about a file.

### Scripts: `sh` (2026-11-03)

A script is a text file of shell lines. `sh path` runs one; so does naming a file whose name ends in `.SH` as a
command (`build.sh`, or `BUILD.SH`: the word is lower-cased), and a program's EXEC of one (below), which is how
`/bin/make` runs its recipes. The script starts when the command that started it has ended. Each line is read,
shown after the prompt as if typed, and run: built-ins, programs, redirection and pipes all work. Blank lines and
lines starting with `#` are skipped; a line ends at LF or CR (so CR LF is fine) and keeps 128 characters.

- **A failure stops it**: a shell message (`what?`, `not found`, `cannot ...`: everything `eputs` prints) or a
  program that ends with a status other than 0. The shell then says `sh: stopped`, every running script ends, and
  the prompt comes back. The compiler's passes, `asm` and `make` end with status 1 after an error (2026-11-03), so a
  build stops at its first failed step.
- **Nesting**: a script may start another (`sh`, `name.sh`, a program's EXEC); that one runs, then the first goes on
  with its next line. Four may run at once (`sh: too deep`).
- **Read from its sectors**: the running script is its extent, length and read position (`SC_LBA`, `SC_LEN`,
  `SC_POS`; the interrupted ones in `SC_STK`), read through the OS's sector buffer between commands. A `cd` inside it
  changes the directory for the lines after it, and replacing the file while it runs (a nested `make` writing a new
  `make.sh`) leaves the running script as it was: the old extent stays until `pack`. A script is at most 64K
  (`sh: over 64K`); `pack` inside one would move it under the reader.
- No variables, arguments, tests or loops: a line is a command line. `sh` itself writes nothing, so `sh F > OUT`
  redirects nothing (put the `>` on the lines).

`man sh`; `tests/os/sh.session` runs each case on both kernels and both emulators (comments, CR LF, `cd` inside a
script, nesting and its limit, a diagnostic and a status stopping it, `name.sh` as a command, EXEC of a script from a
program and from a script).

## The file API (syscalls, 2026-09-23)

The OS fills a jump table in the monitor's free variable space at boot; a program calls entry `n` with y1cc's
`sys(n, a, b, c)` builtin, which stores the arguments in SYSARG0..2, JSRURs the entry, and returns SYSRES. Every
result is a full 16-bit word (no carry bit): 1/0 for done/cannot, a handle or 0, a count, a byte or **65535** for
"none" (end of file, end of console input). The numbers are `#define`d in `lib_abi.c` and wrapped in `lib_fs.c`:

| Address | Name | Use |
|---|---|---|
| $0F06 / $0F08 / $0F0A | SYSARG0 / 1 / 2 | the arguments (big-endian words, `peekw`/`pokew` order) |
| $0F0C | SYSRES | the result |
| $0F0E | STATUS | (2026-09-25) the status of the program that ran last: 0 when its main returned, else what it gave EXIT; set when it ends, so the next program reads the previous one's (a shell's `$?`) |
| $0F14..$0F3F | SYSTAB | 22 word entries 0..21, `SYSTAB + 2n` = the address of handler `n` |
| $4FC0..$4FFF | SYSTAB2 | (2026-09-25) 32 word entries 0..31, `SYSTAB2 + 2n`; 0..21 the same as SYSTAB's, 0 for an unused slot |

| n | Name | Arguments | Result |
|---|---|---|---|
| 0 | OPEN | path | handle 1..4, or 0 (not found, a directory, 16M or more, no handle free) |
| 1 | READ | handle, buf (512) | bytes put in buf: the whole sector holding the position, straight from the card; 0 at the end |
| 2 | GETC | handle | the next byte through the handle's own sector buffer; 65535 at the end |
| 3 | CLOSE | handle | 1; for a written file this writes the last sector, the directory entry and the free pointer |
| 4 | CREATE | path, load, exec | handle, or 0 (bad path/name, parent missing, another write open - also a `>` or a pipe of the shell - a directory of that name); a same-named FILE is replaced at CLOSE (its entry overwritten in place) |
| 5 | WRITE | handle, buf, n | bytes written (since 2026-09-25 the assembly OS copies what fits in the rest of each sector in one go: the same bytes, positions and card writes as a PUTC per byte) |
| 6 | PUTC | handle, byte | 1, or 0 (not the write handle, 16M - 1 bytes reached) |
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
| 22 | EXIT | status | (2026-09-25, SYSTAB2) does not return: the program ends at once, from any depth and on any stack, as if its main had returned (its files closed, a pending write registered); STATUS = status |
| 23 | EXEC | path, args | (2026-09-25, SYSTAB2) 0 when path is over 63 characters, not found, not a file, or does not load into $5000-$CFFF (the `load` rule); else does not return: the caller ends as with EXIT(0) and path is loaded and run with args (0 = none; up to 127 characters) as its command tail, in the same shell command (a `>` or a pipe stays) |
| 24 | SEEK | handle, hi, lo | (2026-09-25, SYSTAB2) 1: the read handle's position is now hi:lo (24 bits), not past its length; 0 for another handle, past the end, a card error. Inside a sector that sector is read into the handle's buffer |
| 25 | READN | handle, buf, n | (2026-09-25, SYSTAB2) the bytes put in buf: up to n, the bytes n GETCs would give **from the position** (after a SEEK into a sector too: READ is the one that starts at the sector's start), but never past the end of the position's sector: exactly the least of n, the rest of the sector and the rest of the file (so a call can return fewer than n before the end of the file); 0 only at the end, for n = 0 and for anything but a read handle. Mixes freely with GETC, SEEK and READ. A program's own small buffer then costs a syscall per block instead of one per byte (below) |

**Two tables** (2026-09-25). SYSTAB's 22 slots were all in use and ARGBUF follows it, so it cannot grow; moving it
would have broken every program compiled before (they read `SYSTAB + 2n`). So the OS now fills SYSTAB2, 32 entries at
$4FC0-$4FFF at the top of its own RAM (both kernels keep that free: the assembly OS's variables end at $4F17, the
Makefile checks the C OS's data against $4FC0), and copies its first 22 words to SYSTAB. Every entry keeps its number
and every old address still works. `y1cc`'s `sys(n)` reads SYSTAB for a constant n of 0..21 (so its output for every
existing program is unchanged) and SYSTAB2 for 22..31 (`LDR R7,$4FC0+2n`); a computed n still indexes SYSTAB, so
it reaches 0..21 only (a new syscall is called with a constant, as `lib_fs.c` does); a number over 31 is a compile
error. `lib_abi.c`: `SYSTAB2`, `SYS_OLD` = 21. Tests: `tests/compiler/syscall2.c` (both tables, standalone),
`sysbig.c` (the error), `tests/os/systab.session` (both kernels fill both, STDIO called through SYSTAB2).

Handles: four, each with its own 512-byte buffer and a **24-bit position and length** (since 2026-09-25: a file is up
to 16M - 1 bytes; with the 16-bit positions before, a file over 64K could not be opened or written past 64K). The
syscalls did not change for it: a program reads until GETC's 65535 or READ's 0 and never sees a position, so every
program reads and writes any size unchanged; the length's bits 16-23 are the entry's byte 18, P8XFS's "64K
multiples" (`dir` has always shown them), and byte 19 must be 0. `tests/os/big.session` writes a 70K and a 140K file
(`tests/os/bigw.c`), reads them back byte-wise and sector-wise (`bigr.c`), copies one with `cat >` and appends to the
other with `>>`, on both emulators and with both kernels; the host checks every byte (`p8xfs.py get`) and `fsck`. A
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
Files are contiguous: a read handle can SEEK (since 2026-09-25), the only append is the shell's `>>` (above), and dead
sectors come back only with `/bin/pack` (below).

### EXIT, EXEC and chaining programs (2026-09-25)

The native C compiler is nine programs that must run one after the other with arguments (BACKLOG "The road to a
native compiler"); a program could only end by returning from main. Two syscalls in SYSTAB2:

- **EXIT(status)** ends the program from anywhere. The shell calls a program through a small routine that keeps its
  own SP first (`rp_call` in `y1os.asm`: `MOVRR R1,R5 / STR R5,OS_SP / JSRUR R7 / RET`); EXIT's handler loads that
  SP back into R1 and RETs, which lands in `run_prog` exactly where the program's own RET would have. So it works
  from any depth (static frames need no unwinding) and from a program on its own stack (`y1cc --stack`, the
  compiler's passes). y1cc cannot set R1, so `y1os.c` does the same with a 15-byte machine-code stub in a char array
  (`stub`: the same four instructions, and `LDR R1,os_sp / RET` at stub+11 for EXIT), whose two addresses
  `install()` fills in. The status goes to STATUS ($0F0E) when the program has ended, for the next one to read.
- **EXEC(path, args)** replaces the caller: the handler checks that path can be run (the `load` rule: a file that
  loads into $5000-$CFFF, not empty), copies it out of the program area (XPATH), copies args to ARGBUF, and ends the
  caller as EXIT(0) does; `run_prog` closes what the caller left open, then loads XPATH and runs it the same way,
  and again for as long as programs EXEC. It all stays one shell command: a `>` file or a pipe stays open across the
  chain (`cc prog.c > LOG` sends all nine passes' output there), and the shell's prompt comes back only at the end.
  EXEC returns (0) only when path cannot be run, so the caller can say so.
- **EXEC of a script** (2026-11-03): a path ending in `.sh` (lower case) is not loaded but becomes a script that the
  shell runs once the command has ended (`EX_PEND` 2; "Scripts" above). `/bin/make` writes its recipes into
  `make.sh` and EXECs it.
- **Why EXEC and not batch files:** each pass knows its successor (it is fixed) and runs it with one argument, the
  work prefix, so a chain needs no parser, no files and no shell change; a pass that finds an error EXITs (status
  1) and the chain stops there by itself, where a batch file would need a test of STATUS. The driver is one small
  command, `/bin/cc` (`commands/cc.c`): it EXECs `/lib/cc/cc1` with `ccw` + its command line; `cc1`..`cc8` EXEC
  `/lib/cc/cc2`..`cc9` with `ccw`, `cc9` returns. (`software/compiler/README.md`, "Native".)
- **SEEK(handle, hi, lo)** positions a read handle (24 bits). The compiler's lexer needs it: a `/bin` source nests
  `#include`s five deep, and with four handles, one of them writing, only three can be open, so `target_inc.c`
  closes the outermost file and later opens it again and SEEKs to where it was.
- **READN(handle, buf, n)** (25, 2026-09-25) and a faster **WRITE**: the compiler's passes read and wrote their work
  files a byte and a syscall at a time, and the OS's GETC/PUTC path (the syscall, the handle checks, the 24-bit
  position) was about 100 instructions a byte: a third of a compile. Now `software/compiler/c/target_io.c` keeps a
  64- or 128-byte buffer each way and fills it with READN, empties it with WRITE. READN takes its first byte through
  the ordinary GETC path (the sector into the handle's buffer, the end, the checks) and copies the rest of that
  sector straight out of the handle's buffer; WRITE puts each byte through PUTC as before, then copies what fits in
  the rest of that sector straight in (`y1os.asm` `fs_readn`, `fs_write`; `y1os.c` keeps the plain loops as the
  specification, READN a loop of `fs_getc` that stops at a sector's end: the same results). A sector's bytes cost
  seven instructions each instead of a hundred. `tests/os/big.session` (`bigw -v`, `bigr -n`) writes a 70K file
  in pieces of 0-1,000 bytes and reads the 70K and the 140K file back with READN in sizes 1-600 mixed with GETC,
  checking every count; the host checks the bytes; both kernels, both emulators.
- **READN's contract, exactly** (2026-09-27): the count is the least of n, 512 - (position & 511) and length -
  position; fewer than n only at a sector's or the file's end, 0 only at the file's end, for n = 0 and for a handle
  that is not open for reading (0, over 4, closed, a write or a directory handle). The bytes are the file's from the
  position, and the position moves past them, so GETC, READN, SEEK and READ mix in any order (a READ after a READN
  inside a sector gives that whole sector again from its start, then the position is the next sector's). A program
  moving from READ to READN must drop what it did to skip from a sector's start to the position after a SEEK: the
  READN trial of `/bin/asm` (2026-09-26, `READN(fh, SDATA, 512)` in `asm.asm`'s `gs_rd`) kept its `GL_SKIP`, so after
  every INCLUDE it threw away the first bytes of the outer file's rest and its NPOS ran behind (tests/asm's
  quirks.asm: duplicate labels, a garbage label; everything without INCLUDE, cc4.asm and a 171K source among them,
  byte-identical): that was the "stale data" reported, not the OS. `tests/os/rdn.session` (`tests/os/rdn.c`) pins the
  contract: every count and byte of READNs in nine sizes mixed with GETC over a 66K file, after SEEKs to boundaries,
  into sectors, around 64K, to the end and past it, mixed with READ; right after the WRITE of the same file (in
  pieces of 0-1,000 bytes); twice in one session; on two handles in turn; a file opened on the handle another file
  just left its sector 0 in; a file replaced at CLOSE read again; the zero cases. Both kernels, both emulators.
- **The handles' sector buffers** (a fix, 2026-09-27). A read handle's buffer holds one sector of its file, whose
  number (0 = the file's first) the record keeps (`H_CUR`, `h_cur`): OPEN sets it to none, SEEK into a sector and
  GETC/READN fill it. `y1os.c` compares the position's sector with it at every GETC; `y1os.asm` only at a sector
  boundary (inside a sector the buffer holds it). From 2026-09-25 (the 24-bit positions, 6a42b9f) that compare in
  `y1os.asm`'s `fs_getc` lacked an `ANDI 0F0H` and read the handle's start LBA instead of `H_CUR` whenever the
  position's bits 8-23 were below the length's. So GETC and READN (whose first byte is a GETC) read the sector again
  at nearly every boundary - right, but a CF read per 512 bytes that the buffer did not need - and at the one sector
  whose number equals the file's start LBA they used the buffer as it was, holding the sector before: 512 stale
  bytes. READ never goes through the buffer and was right. It needs a file longer, in sectors, than its start LBA:
  on a fresh volume a file at LBA 37 over 18.5K. On `os/disk.img` and every disk the tests make from it the free
  pointer is past LBA 1,100 and on a 2,048-sector volume no file starting below LBA 1,024 can be that long (none of
  the image's own files is), so no test, native compile or self-host met it - which is why they all stayed
  byte-identical. `tests/os/rdnlow.session` boots a newly created volume with a 40K file at LBA 37 (tests/os/run.py
  `FRESH`); before the fix every read of it went wrong at byte 18,944. Fixed in `y1os.asm` (`y1os.c` was right).

Tests: `tests/os/exec.session` (`tests/os/exe.c`, also built with `--stack 0xCFFF` as `/exes`): EXIT from three
recursive calls deep and from a program on its own stack, STATUS as the next program sees it, a chain of four EXECs
in one command and the same under `>`, EXEC refused for a missing file, a directory, a file that would run past
$CFFF and a 64-character path, SEEK inside a sector, to the end, past it and on a directory handle, and EXIT inside
a pipe; `big.session`'s `bigr -k` SEEKs across 64K and 128K in a 140K file; both kernels, both emulators.
`tests/native/run.py` runs the compiler through `cc`.

Directory entries are the 32-byte P8XFS v2 records, little-endian on disk: name[12] (space-padded) start[4]
length[4] load[2] exec[2] flags (1 file, 2 directory, $FF deleted, 0 end of directory); `lib_fs.c`'s `ent_len()`,
`ent_load()`, `ent_exec()`, `ent_lba()`, `ent_isdir()`, `ent_isfile()`, `ent_name()` read them.

## Writing a command

`os/commands/*.c`, compiled with `--org 0x5000 --os` (the transient area starts at $5000 and runs to $CFFF) and put
with `--load 0x5000 --exec 0x5000`. A program is an ordinary y1cc program: `main` returns to the shell, output is the
compiler's `putchar`/`puts`, which `--os` sends through the CONOUT syscall so that the shell can redirect it,
`argstr()` is its command tail, and files come from `#include "../lib_fs.c"` (which includes `lib_abi.c`).
(A command can also be hand-written YACC1 assembly in `os/commands-asm/`, assembled at $5000 by the host assembler:
`asm.asm` is `/bin/asm` and, since 2026-11-11, `basic.asm` is `/bin/basic`; the C sources they were written from
are on the disk as `asmc` and `basicc`. It calls the syscalls as y1cc's `sys()` does - the arguments into
SYSARG0..2 as big-endian words, `LDR R7,SYSTAB+2n` (SYSTAB2 for 22 and up) / `JSRUR R7`, the result from SYSRES,
R3..R7, ACC and TMP clobbered - reads its tail at ARGBUF, returns with RET, and must clear its own variables; its
header lists the conventions.) A C command:

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

`lib_fs.c`: `fopen fread freadn fgetc fclose fcreate fwrite fputc fputs fdelete fmkdir frmdir opendir readdir
fresolve fentry getcwd chdir frename conin constat keyin stdio osexit osexec fseek`, the `ent_*` accessors, and
`argword(tail, out, max)` to take the next word of the command tail. Input comes in two kinds since the shell has
pipes: DATA is `conin()`, stdin (a `<` file, a pipe, else the console), 65535 at its end or at Ctrl-D, so a filter is
`while ((c = conin()) != 65535) ...`; a KEY the user presses in answer to the program (`--More--`, `vi`, `dump`'s
next page) is `keyin()`, always the keyboard. (`getchar()` under `--os` is CONIN too, with 0 at the end of input.)
Output is `putchar`/`puts`; an error message is `eputs()` from `lib_err.c`, which writes to the screen even under
`>` or `|`. A program that does not follow the rules still works on the console, but its output cannot be redirected
(built without `--os`) or its keys come out of the pipe (read with `conin()`).
The rules of the compiler apply: recursion with its rules (since 2026-09-24; the stack is 768 bytes), `int` is unsigned (`>= 0` loops for ever), 16-bit literals only.
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

## The commands (`/bin`, 2026-09-23)

Most were ported from the P8X (`os/PORT-PLAN.md` has the table: what changed and why, what was left out); each
source file's header says the same, and `/man/name` is its page (`man NAME`, `man` alone lists them). Several file
names, globs and `-` (the console until Ctrl-D) work wherever a command reads text.

| Command | Does |
|---|---|
| `asm [-h] SRC [OUT]` | the assembler (2026-09-25, below): RC/asm's dialect to a program file, or Intel hex with `-h` |
| `asmc [-h] SRC [OUT]` | the same assembler built from its C source, the specification (2026-09-26, below) |
| `awk [-F c] 'prog' [file...]` | one rule: `/re/ {print $1, $NF, NR, NF, "text"}` |
| `basic [file]` / `basic -r file` | the BASIC interpreter (2026-11-09, below): integers and strings, programs saved as text, data files; `-r` runs a program and returns to the shell. In assembly since 2026-11-11; `basicc` is the same program in C |
| `cc prog.c [-o prog.asm] [y1cc options]` | the C compiler (2026-09-25): y1cc's nine passes, `/lib/cc/cc1`..`CC9`, chained with EXEC; the assembly is byte-identical to y1cc.py's (`man cc`, `software/compiler/README.md` "Native") |
| `cat [file\|glob\|-]...` | print files byte-exact, or the console |
| `cmp f1 f2` | the first differing byte and line, or silence |
| `cp [-r] src dst` | copy a file, a glob into a directory, or (`-r`) a tree; load/exec kept |
| `del name\|glob...` | delete files |
| `dep addr b b...` | store hex bytes |
| `diff f1 f2` | the differing block: `< ` lines of f1, `> ` lines of f2 (150 lines per file) |
| `dir [-R] [-S] [path\|glob]` | sorted listing with sizes and load addresses; `-S` by size; `-R` every directory below, `ls -R` style |
| `disasm [-s] FILE [START [COUNT]]` / `disasm [-s] -m ADDR [COUNT]` | the disassembler (2026-09-29, below): a program file as if loaded, or memory; lines that `asm` takes back (`-s`: the source alone) |
| `dump addr` | hex + ASCII, 256 bytes a key |
| `echo text` | print the argument tail |
| `examine addr` | show and change bytes one at a time |
| `find pattern [dir]` | paths whose name contains the text, or matches the glob |
| `grep [-r] re [file...\|dir]` | matching lines; `NAME:` with several files; `-r` a tree |
| `head [-N] [file...]` / `tail [-N] [file...]` | the first / last N lines (10; tail up to 40) |
| `hello [args]` | the first /bin program |
| `help` | the command list (the text is `/lib/help.txt`, `os/help.txt`) |
| `kermit -r` / `-s FILE...` / `-x` | file transfer with the Mac over the console line (2026-09-26, below): receive, send, server |
| `ls [path]` | a plain listing through opendir/readdir |
| `make [-n] [-B] [-f file] [target...]` | build targets from a Makefile (2026-11-03): the recipes go into `make.sh`, which the shell runs as a script; no file dates, so what is missing is built (`man make`, "The sources on the disk" below) |
| `man [name]` | `/man/name` through the pager; alone: the page names |
| `mkdisk [-f] [kernel]` | a new disk on drive 1: boot block, kernel, volume, this disk's files (2026-11-05, "A new disk" below) |
| `mkdir [-s N] path` | a directory; `-s` N sectors, 1..64 (16 entries each, less `.` and `..`): 2026-11-03, written on raw sectors as `pack` does, since the kernels and the MKDIR syscall make one size (16 sectors, 254 entries, since 2026-11-05) and the C kernel has no room for an option; without `-s` the syscall |
| `md [-p] [file]` | Markdown rendered (ANSI, or plain with `-p`), paged; names are looked up in `/docs` too; alone: the list |
| `more [file...]` | page text (or stdin: `dir -R \| more`): space, Enter, q from the keyboard |
| `mv src dst` | rename in place (RENAME), or move to another directory (copy + delete), globs into a directory |
| `pack` | compact the volume: slide every file and directory down over the dead sectors, lower the free pointer (below) |
| `pwd` | the current directory |
| `sed s/re/new/[g] [file...]` | substitute (shortest match) |
| `sort [file...]` | lines in byte order (200 lines of 79) |
| `sysgen file` | install a kernel in this disk's boot sectors, for the next O (2026-11-05) |
| `touch name...` | empty files for the names that do not exist |
| `tree [dir]` | the tree, indented, depth first |
| `uniq [file...]` | drop adjacent repeats |
| `vi [file]` | the screen editor (VT100) |
| `video [on\|off\|clear\|init\|probe]` | the video card (2026-09-25, below): status, mirror the console on the screen, clear it, program the CRTC |
| `wc [file...]` | lines, words, bytes (32-bit) |

Also on the disk: `/lib` (2026-09-25: the compiler's passes `/lib/cc/cc1`..`CC9`, built with `make -C os passes`,
and `/lib/y1ccrt.txt`, `/lib/y1lib.c`), `/man` (the pages, from `os/man/`), `/docs` (this README as `os.md`, the compiler README as
`y1cc.md`, `osplan.md`, `port.md`, `kermit.md` (2026-09-26: the Mac side of `kermit`) and `mddemo.md`, md's own sample), and `/fruit.txt` + `/fruit2.txt`, seven lines of
sample data for trying the filters (`sort`, `uniq`, `awk`, `diff` ... the man pages' examples use them).

### The sources on the disk: `/src` (2026-11-03)

`/src` holds the sources of the disk's programs at their paths in the repository, so every `#include` resolves on
the machine as on the Mac: `/src/os/commands` (the `/bin` commands' C), `/src/os` (the C libraries `lib_*.c`, the
generated tables `asm_optab.c`, `dis_optab.c`, `kermit_io.c`, and both kernels with `strings.txt`;
`kermit_io.asm` is `kermitio.asm`, P8XFS names being 12 characters), `/src/os/commands-asm` (`asm.asm`,
`asmtab.inc`) and `/src/software/compiler/c` (the native compiler's passes: `target/*.c`, the `cc*_*.c` and `p*.c`
they include, `ylim/`). 97 files, 768 KB; the volume is 4 MB (8,192 sectors) since then. Each source directory has
a Makefile, generated by `os/mksrcmk.py` from the tree and os/Makefile's flags:

```
cd /src/os/commands                  make touch, make all, make install (-> /bin), make clean
cd /src/os/commands-asm              asm from its assembly (-> /bin/asm)
cd /src/software/compiler/c/target   cc1 .. cc9 (-> /lib/cc)
cd /src/os                           the kernel, y1os: make install (-> /lib/y1os), make boot (sysgen)
cd /src                              make: all of them, one after the other; make install; make clean
```

`tests/native/srcmake.py` (in `make check`) runs `cd /src`, `make`, `make` again and `make install` on the emulated
machine: 45 programs, every one byte-identical to the Mac's build of the same source, the second `make` compiling
nothing. One command is not in `all` or `install`: `kermit` (`kermit_io.c`'s byte table is over pass 3's node limit);
`/bin` keeps the Mac's build of it. The kernel is built by `make` too (`asm y1os.asm`, byte for byte the Mac's), from
`y1os_str.inc`, the messages of `strings.txt` as assembly: `mkstrings.py` makes that on the Mac, so an edit of
`strings.txt` on the machine does not reach it. The generated tables (`asm_optab.c`, `dis_optab.c`, `asmtab.inc`,
`kermit_io.c`) likewise. The ROM and the microcode are not in `/src`.
A build leaves a program, its `.asm` and the compiler's 14 `ccw.*` work files in the directory, which is why
directories are 254 entries (16 sectors) by default since 2026-11-05. A directory cannot grow: its extent has files
right behind it, and moving it would mean rewriting its parent's entry, its `.` and every subdirectory's `..` in both
kernels. `mkdir -s` makes a bigger one; the root stays 4 sectors (62 entries), fixed before the data area.

### A new disk: `sysgen`, `mkdisk` (2026-11-05)

`sysgen file` writes a kernel to LBA 1.. of this disk, each sector read back, then OSCNT in the boot block: what
`p8xfs.py boot` does on the Mac, on raw sectors as `pack` works. There is one copy of the kernel, so a failure half way
needs the Mac; the checks all come first.

`mkdisk` writes a whole new disk on **drive 1**, the IDE slave, driving it itself through P8/P9 with the device bit set
between the OS's calls (the ROM selects drive 0 before each of its own transfers): the kernel (`/lib/y1os`), the root
directory, then every file and directory of the running disk, directories at their own size, from LBA 37 up, and the
boot block last. So the system rebuilds itself:

```
cd /src
make                  every program, then the kernel
make install          into /bin, /lib/cc, /lib/y1os
make clean            the build's output leaves /src
cd /
mkdisk                drive 1; then make it drive 0 and O
```

`tests/native/mkdisk.py` (in `make check`) runs exactly that on the instruction-level emulator, with `-C new.img` as
drive 1, and checks the new disk from the Mac: fsck, the kernel's sectors, and every file's bytes, load and exec address
against `os/disk.img`, with nothing extra; then it boots the new image alone, runs commands and builds a program there.
The emulators' drive 1 is the option `-C image` (`software/cfmodel.h`: bit 4 of the head register; no image, every
register reads $FF). **Not yet done on the machine**, which has one CF: it needs a second card on the IDE cable, and the
ROM's `O` boots drive 0 only, so the new card is moved to master to boot it. See BACKLOG for the data error of 2026-11-04
before any `make install` there.

### `kermit` (2026-09-26)

`/bin/kermit` (`commands/kermit.c`, `kermit_io.asm`) moves files between Y1/OS and the Mac over the console cable with
the Kermit protocol: C-Kermit on the Mac (`docs/procedures/KERMIT.md`, the how-to: settings, `tools/y1.ksc`, sessions)
or `tools/y1kermit.py`. `kermit -r` receives into the current directory, `kermit -s FILE...` sends (globs), `kermit -x`
is a server (the Mac SENDs, GETs, FINISHes). The console IS the line, so nothing is printed while packets flow; a
summary (each file and its size, a count) comes after. `man kermit`.

**Ported from E-Kermit 1.8** (Frank da Cruz, the Kermit Project, 25 May 2021, Revised 3-Clause BSD licence; the
unmodified sources, their download URL and checksums are in `upstream/ekermit-1.8/`): its protocol module, main loop
and Unix I/O module, with the changes the y1cc subset forces (no function pointers: the I/O callbacks are direct
calls; no `long`: 24-bit sizes as two ints; `int` unsigned; no `#ifdef`: the feature set fixed) and what Y1/OS and
the machine need (timeouts and retry limits, which E-Kermit leaves to the other side; packets read by length; server
mode; the file handling below). `kermit.c`'s header lists every change and keeps E-Kermit's notice, as its licence asks.

| | |
|---|---|
| Protocol | short packets (up to 94), window 1 (stop-and-wait), block checks 1, 2, 3 (16-bit CRC; the sender proposes, 3 by default), control prefix `#`, repeat counts `~`, 8th-bit prefix `&` only when the other side asks (the line is 8 bits), attribute packets (size, text/binary; a refused file is skipped); server: I, S, R (GET, a glob too), G F / G L (FINISH, BYE). Not: long packets, sliding windows, streaming, locking shifts, RESEND, file dates, REMOTE commands (BACKLOG) |
| Timeouts | what the other Kermit asks for, else 5 s; it asks for 15 s. 10 tries a packet, 60 before a transfer has started (the user is switching to the Mac). Three Ctrl-Cs while waiting cancel |
| Files | received names: the leaf, its case kept (upper-cased until 2026-11-03), 1..12 of `A-Z a-z 0-9 . _ -` (name.ext cut to 8.3 when too long), the name used goes back in the ACK. Data goes to `kermit.tmp` in the current directory and is renamed when complete: a same-named file is replaced only by a whole new one, a failed transfer leaves nothing (`-k` keeps it), `-n` never replaces (`NAME~1`..`~99`), `-a ADDR` sets load/exec. Binary by default both ways; text mode (the sender's attribute, or `-T` to send) drops / adds the CR of CR LF. Receiving takes the one write handle: not inside `>` or a pipe |
| Size | 19,349 bytes image + 8,118 data (`--xisa`: 17,524 + 8,373), of which `kermit_io` is 530 bytes of code |

**The line: `kermit_io.asm`.** At 1 MHz the YACC1 runs ~30,000 instructions a second and 38400 baud delivers a
character every 260 us. So the UART is read by a few assembly routines, not by the ROM (whose `uartinne` turns CR into
LF and costs a JSR a character) nor by compiled C (~1,100 clocks a character): `krx` hunts for the SOH, then reads
LEN - 32 more characters by count in **217 clocks a character** (measured on the microcode emulator by
`tests/kermit/run.py --calib`), and kermit switches the 16C550's 16-byte receive FIFO on for the transfer (FCR = 7,
off again at the end, after the transmitter has emptied). That keeps ahead of the line by 43 clocks a character, so
the FIFO is margin; before the microcode changes of 2026-09-29 (three-step fetch prologue, idle steps) the loop took 279 clocks, fell behind by 19
a character, and relied on the FIFO to absorb a burst of ~220 characters. Timeouts are poll counts: a pass of the
wait loop is 153.20 clocks on average, 6,528 passes a second (measured: 1,000,176 clocks); at another clock they
scale with it. The same file holds `ktx` (send), `kcrc`/`ksum` (the block checks, 16 instructions a byte against ~210
in C), `kdec` (a packet's data field decoded straight into the output buffer) and `kenc` (file bytes encoded straight
into the packet, leaving runs and 8th-bit prefixing to E-Kermit's C). y1cc has no inline assembly, so `mkkio.py`
assembles the file at 0000H and at 1000H and writes `kermit_io.c`: the bytes as a C array, the offsets of the words
that differ (the absolute addresses), and `#define`s for the entries and parameters. kermit.c adds the array's
address to those words at start-up and calls the entries with `call()`; the Makefile regenerates it, `mkkio.py
--check` catches a stale copy. The instruction-level emulator gained a UART model for it the same day
(`software/emulator/README.md`): until then only the microcode emulator had a data-ready bit to poll.

**Throughput** (the instruction-level emulator's PC histogram, less the instructions spent waiting in `kermit_io`'s
poll loops, at 32.4 clocks an instruction and 1 MHz; `tests/kermit/run.py` prints it for the 80,793 bytes of its
first session, six files one way then back):

| | instructions a byte | bytes/s at 1 MHz | `--xisa` |
|---|---|---|---|
| receive (Mac to YACC1) | 118 | 263 | 113 / 273 |
| send (YACC1 to Mac) | 132 | 234 | 126 / 245 |

The CPU is the limit, not the line (38400 baud carries 3,840 characters a second). Where a received byte goes: `kdec`
~30 instructions, the CRC ~22, `krx` ~14, the OS's WRITE and the ROM's sector writes ~20, the rest per packet (the
ACK, the checks, the state machine). A first version with only `krx`/`ktx` in assembly did 398 and 525 instructions a
byte (78 and 59 bytes/s).

**Tests** (`tests/kermit/run.py`, in `make check`, ~2.5 minutes): on both emulators, Y1/OS on a pseudo-terminal
against `tools/y1kermit.py`: a text file, all 256 byte values, a 70K file (over 64K), long runs, an empty file and a
long lower-case name in one session, then all of them back with `kermit -s *`; block checks 1 and 2, 8th-bit
prefixing both ways, text mode both ways, no attributes and no repeat counts, `-n`, `-a`; a damaged packet each way,
a packet never sent (kermit -r times out and NAKs), an ACK never sent (kermit -s times out and sends again), three
Ctrl-Cs; the server's SEND, GET (a glob, a lower-case name, a missing file) and FINISH. Every file is compared with
the original on the host and, through `tools/p8xfs.py get`, on the disk image, which must pass fsck. 33 checks an
emulator, the same with `XISA=1`, and `--calib` (the two timing figures above). **Not yet run on the machine**: the
FIFO, the timing at the real clock and C-Kermit itself are to verify (BACKLOG).

### `basic` (2026-11-09)

`basic` is the BASIC interpreter of the P8X (`basic/basic.c`), ported without its graphics statements:
`os/commands/basic.c`, 14.5 KB of code and 12,286 bytes for the program's lines. The language: 16-bit signed integers
(decimal or `0x1F`), 32 number variables and 16 strings of up to 32 characters (names of up to 6 significant
characters), `PRINT LET IF/THEN FOR/TO/STEP NEXT GOTO GOSUB RETURN INPUT POKE REM END`, the functions `ABS RND PEEK
LEN ASC VAL CHR$ LEFT$ RIGHT$ MID$ STR$`, and one data file at a time (`OPEN "f" FOR OUTPUT|INPUT`, `PRINT#`, `INPUT#`,
`EOF(1)`, `CLOSE`). A typed line is checked as it is entered (unbalanced brackets or quotes, a line that starts with
`THEN` or a function) and refused with `?SYNTAX ERROR` before it is stored. `man basic` has the whole of it.

What the port changed:
- **Programs are text.** `SAVE "f"` writes the program as `LIST` shows it, `LOAD "f"` reads it back a line at a time as
  if it were typed. A saved program can be shown with `cat`, edited with `vi`, searched with `grep`, and written on the
  Mac and sent with `kermit`. (The P8X saved its token image.)
- **`basic -r file`** loads and runs a program and returns to the shell, so a BASIC program can be a command or a line
  of a `sh` script.
- **Lines are inserted and deleted in place**: the P8X built a second copy of the program for every edited line; here
  the lines after it move, so the whole area holds program.
- **Ctrl-C stops a running program** (`BREAK IN n`). The check takes a waiting key before each line, and any other key
  is kept for the next `INPUT` or prompt. It cannot be handed back to the shell, so a key typed while `basic -r` runs
  is lost when the program ends.
- `GOSUB` and `FOR` nest 8 deep (3 on the P8X), `INPUT "prompt"; X`, `PRINT# 1, X` as well as `PRINT# X`, and
  `?ONLY IN A PROGRAM` for `GOTO`, `GOSUB`, `RETURN` or `NEXT` typed at the prompt.
- For the native compiler (`make` in `/src` builds it under Y1/OS, byte-identical to the host's build) the keyword
  table is two strings of words (a token is 128 + the word's position) rather than a 200-element initialiser, and the
  check of a statement's first keyword uses token ranges: the passes' limits are 800 declaration nodes, 160-character
  string literals and 40 nodes an expression.

**BASIC in assembly (2026-11-11).** `os/commands-asm/basic.asm` is the same interpreter hand-written in YACC1
assembly, with `basic.c` as its specification: every routine names the C function it implements and follows it, the
error flag included, so the two print the same thing on every line. It is `/bin/basic`
(`os/build/basica/basic.bin`, 7,546 bytes) and the C one is `/bin/basicc`; `tests/ybasic/run.py` runs every session
on the disk as it is and on a copy with the C one in `/bin/basic`'s place, compares the console output, and counts
both on a loop: `20 a=a+1` /
`30 if a<32000 then goto 20` is 5,319 instructions a pass in C and 843 in assembly. It runs on a stack of its own
(1 K after the program area; an expression in brackets, IF ... THEN and RUN recurse), keeps the one-letter variables'
addresses in a table and the last lines a GOTO named, and clears only its variables at the start, not the 12 K of
program area. `make` in `/src/os/commands-asm` assembles it on the machine, and in `/src/os/commands` builds
`basicc` from the C.

The ROM's BASIC (the monitor's `I` command, `firmware/basic/`) is a different, smaller interpreter (uBASIC): it has no
string variables and cannot load or save programs. `tests/os/ybasic.session` runs a program, saves, loads, edits and
lists it, and writes and reads a data file, on both emulators.

### `video` (2026-09-25)

`/bin/video` (`commands/video.c`) switches the ROM's video driver (`ROM 2026-09-25`, `docs/programming/MONITOR.md`
section 11). The ROM probes the card at $D000 at reset (`VIDPRES`, $0FF0) and, while `VIDMIR` ($0FF1) is set, its
CHAROUT writes every console byte to the screen as well: `video on` / `off` set that flag (on refuses when no card
was found), `video clear` and `video init` call the ROM's video entry `VIDCTL` ($FFBC: 2 clear, 1 CRTC table + clear),
`video probe` probes again, `video` alone prints the status. **The kernels are unchanged**: everything the OS and its
programs print reaches the console through CHAROUT (CONOUT's raw path, the shell's echo, `eputs`), so mirroring
covers it; a `>` file or a pipe is not the console and is not mirrored. On an older ROM (no `JSR` at $FFBC) the
command says the ROM has no video driver and changes nothing. The addresses are `#define`d in `lib_abi.c`;
`man video`; tested by `tests/video/emu.py` on both emulators.

### `asm` (2026-09-25) and `asmc` (2026-09-26)

`/bin/asm` assembles on the machine what the host assembler (`software/assembler`, RC/asm with `yacc1.def`)
assembles on the Mac, byte for byte: y1cc's output, the ROM monitor, the OS. `asm hello.asm` writes the program file
`HELLO` (the bytes from the first address to the last, gaps as zeros, with the load address and END's exec address in
its directory entry), which `run HELLO` loads and calls; `asm -h hello.asm` writes `hello.img`, the Intel hex the host
writes. Errors are reported with their line numbers and the output is deleted. Sources are up to 16M (24-bit file
positions since 2026-09-25; 64K before), and the output needs the one write handle, so `asm` does not run inside a
`>` or a pipe.

It exists twice, and the two behave identically (the same command line, messages, files and exit behaviour):

- **`/bin/asm`** since 2026-09-26 is `commands-asm/asm.asm`, the assembler hand-written in YACC1 assembly: 9,239 bytes,
  a 20,292-byte symbol table (5 + the name's length a label: about 1,660 of y1cc's labels; the biggest compiler pass,
  cc8, has 1,383), and 4.3-5.3 times faster than the C build (`cat`'s 1,504 lines of y1cc output in 2.75M
  instructions, 1 min 29 s at 1 MHz; compiler pass cc8's 235K in 26.4M). It uses the 2026-09-24 microcode's ADDIW and
  SHL16, as the native compiler's passes do. Built by the host assembler (`make`: `build/asma`), its instruction table
  `commands-asm/asmtab.inc` INCLUDEd.
- **`/bin/asmc`** is `commands/asm.c` (the `/bin/asm` of 2026-09-25): **the specification** - asm.asm was written from
  it routine by routine, and a change of behaviour goes into both. 13,186 bytes + 19,569 of data, a 17,088-byte symbol
  table (16,640 until 2026-09-25, when cc8's buffered I/O outgrew it).

Both instruction tables (`asm_optab.c`, `commands-asm/asmtab.inc`) are generated from `yacc1.def` by
`tools/gen_y1_optab.py` (the Makefile regenerates them), so the assemblers cannot disagree about an instruction; the
disassembler's (`dis_optab.c`, below) comes from the same file.
`tests/asm/run.py` compares asm.c with RC/asm on 336 sources (built for the Mac against an emulation of these
syscalls), then runs `/bin/asm` under Y1/OS on the same sources and compares its messages and files with asm.c's
(`--uc`: 27 of them on the microcode emulator too); with `--target` it runs `/bin/asm` in scripted sessions on both
emulators: y1cc programs assembled and run, the monitor assembled to `firmware/monitor/monitor.img`.
`tests/native/selfhost.py` has both rebuild themselves natively (the fixed point). `man asm`, `man asmc`, and
`docs/programming/ASSEMBLER.md` section 10.

### `disasm` (2026-09-29)

`/bin/disasm` (`commands/disasm.c`, 6,107 bytes + 230 of data) turns machine code back into the source the assemblers
take, one instruction a line with its address and bytes:

```
disasm /bin/hello            5000  1B 50 90  MVIW R3,5090H      a program file as if loaded (its load address)
disasm /bin/hello 5010 10    16 bytes of it from 5010 (START and COUNT in hex)
disasm -m F000 20            memory: F000  A0 F0 03  BR 0F003H ... (the ROM monitor; COUNT 40 by default)
disasm -s P > p.asm          the source alone (an ORG, then the instructions): asm p.asm Q gives P's bytes again
```

The instruction text is exactly RC/asm's dialect: hex numbers with an `H` and a `0` before a letter (`0FFH`, `0F000H`;
never a minus, which RC/asm drops), registers `R0`..`R7`, ports `P0`..`PF`. A byte that begins no instruction is a
`DB` line: not an opcode (00 A5 AE F8 F9 FA FF), an operand byte whose fixed bits are wrong (`JSRUR` with a register
byte over 7), or an instruction cut off by the end of the bytes. So everything disasm prints reassembles to the bytes
it came from, data included - which is what its test proves. The file is read with GETC, not loaded, so disasm (at
$5000 like every command) can show any program, itself too; `-m` reads memory with `peek`. It decodes linearly from
where it starts (no following of jumps: data between code comes out as instructions or DBs). Output is stdout (`>`,
`|`), errors go to the screen. `man disasm`.

**The table is generated, like the assemblers'.** `tools/gen_y1_distab.py` reads `yacc1.def` with the assembler
generator's own functions (the `.def` reader and its copy of RC/asm's `Translate()`), then runs each construction
backwards: an instruction is a pattern that writes only bytes and whose first byte depends on nothing but its
register/port operands (so the directives, `DW` and `DB HIGH` are out), and each operand bit is traced to the one
output bit it lands on. Every byte becomes FIXED bits plus FIELDS (`MVIB \{regs},\B` / `10|1 \2` = 00010rrr and a byte;
`POPR` / `08 \1<4&f0` = 08 and 0rrr0000; `MOVRR Rx,Ry` / `0F |2<4|1` = 0F and 0yyy0xxx), which `disasm.c` checks and
extracts - it knows no opcode by name. The register class is decoded for R0..R7 only (RC/asm also takes R8 and R9, which
spill into the next opcode: `MVIB R8` is `MVIW R0`'s $18); then no two instructions share an opcode, which the
generator checks, together with every register/port combination round-tripping through the table and every opcode
agreeing with `software/opcodes.h` (the emulators' and microcode generator's numbers). A new instruction in
`yacc1.def` is disassembled after `make -C os` (which regenerates `dis_optab.c`); one whose bytes are not a bit-for-bit
copy of its operands stops the generator. 78 instructions, 249 opcodes; the LDZ/STZ/ADDIW/SHL16 of 2026-09-24 and BRUR
among them.

**Tests.** `tests/disasm/run.py` (`make disasm-test`, in `make check`, ~20 s) builds `disasm.c` for the Mac (int =
unsigned short, the few syscalls emulated: `host_disasm.c`, `host_sys.c`) and round-trips: `disasm -s`, RC/asm, the
same bytes, and the listing must be the `-s` lines behind a true address and bytes. On the 326 sources of `tests/asm`'s
corpus RC/asm accepts, the 47 programs of the OS build (`/bin`, asm.asm, the nine compiler passes, the OS image), the
ROM at $E000 and its monitor half from memory, random bytes and every opcode followed by every operand byte: 382 of
382, 5.9 million lines; plus START/COUNT ranges and the errors. `tests/os/disasm.session` runs it under Y1/OS on both
emulators on `tests/os/dis.asm` (every operand form, then DBs): a file, a range, memory after `load`, `| wc`, the
errors, and `disasm -s` reassembled by `/bin/asm` on the machine and compared with `cmp`: identical.

### `pack` (2026-09-23)

Only the free pointer allocates and nothing is freed, so every deleted or replaced file, every pipe temp file, every
copied `>>` and every removed directory leaves dead sectors. `/bin/pack` (`commands/pack.c`, 5,397 bytes) gets them
back. It is a program, not a built-in, so the OS image did not grow; it reads and writes raw sectors through the ROM's
CFREAD/CFWRITE (the syscalls hide where an entry sits) and uses the OS only for STDIO, GETCWD and CHDIR.

1. It walks the tree from the root without recursion: the table of records (start LBA, sectors, the record of the
   directory holding the entry, the entry's byte offset in that directory) is itself the work list, breadth first.
2. It sorts the records by start LBA and checks the layout: all at or above LBA 37, none overlapping, none past the
   free pointer. A bad volume is refused before anything is written.
3. In that order each extent moves down to the lowest free sector, one sector at a time, lowest first. Taking the
   extents in ascending order is what makes this safe: every extent still to move lies above the current one, and
   a copy down only writes below the current extent's end, so it never overwrites anything not yet moved.
   **One step** when the hole below the extent is at least its size: copy, then point the entry at the copy.
   **Two steps** when it is smaller (the copy would overwrite the start of the old copy while the entry still points
   there): copy it whole to a **scratch area** at the old free pointer, point the entry there, copy it down, point
   the entry at the final copy. Before the first move the boot block's free pointer is raised over the scratch area
   (old free pointer + the largest two-step extent), so an extent parked there is inside the volume if the run
   stops. Only the next two-step move reuses the scratch area, after the previous one has left it.
4. Each entry is rewritten in its directory **as that directory is now** (a record points at its directory's
   record, whose start is updated when it moves). A directory's '.' is set while its first sector is copied, its
   subdirectories' '..' right after its entry moves; afterwards every directory's '.' and '..' are checked and fixed
   where wrong.
5. The boot block gets the new free pointer; the current directory is re-entered by its path (the OS caches its LBA),
   and the shell re-reads the free pointer when the program returns (the OS caches that too).

`pack` refuses to run with `<`, `>`, `>>` or in a pipe (STDIO): those are the shell's open files, and a file open
for writing grows at the old free pointer. They are also the only files open when a command starts: the shell closes
what a program leaves open, and its built-ins close their own (`save` did not after a failed write; fixed the same
day).

**Reset-safe.** There is no journal, and none is needed: at every moment every directory entry points at a complete
copy of its extent (the old one until the entry's single-sector rewrite, then the new one), and a '.' or '..' that
lags one step points at a copy that is complete and identical at that moment and is fixed by the repair pass. So a
reset or power loss at any point loses nothing, the volume passes fsck, and the next `pack` finishes the job
(reclaiming the scratch area with the rest). **Proved on the emulator** by `tests/os/run.py --cuts 60`: `pack -v` is
cut off at 60 points in each of two fragmented volumes (a 1-sector hole early, so nearly every move takes two steps;
and a 91-sector hole, so many take one), 120 cuts that land in every phase (copying to the scratch area, between
that copy and the entry rewrite, with the entry on the scratch copy during the copy down and before the final
rewrite, inside and after one-step moves); after each, fsck passes, every file of the volume is present and
byte-identical, and a fresh boot's `pack` completes with no dead sector: 120 of 120. The same run against a
one-step-only build loses a file in 16 of 40 cuts, so the check has teeth. What remains is a sector torn by the power
going mid-write (the CF card's business, as for any write the OS makes).

The scratch area needs room right above the free pointer (the largest two-step extent: 91 sectors for `/docs/port.md`
today). The volume has no size field; the bound is LBA 65535 (the free pointer and every LBA are 16 bits, 32 MB), and
the card itself: `pack` reads the last scratch sector first, and a real card refuses an LBA past its end, so `pack`
stops with "no room on the card" before writing anything. (The emulators' CF model reads zeros past the image and
grows it on a write, so that refusal has only been reasoned, not run.) Each move costs up to twice the sector copies
it did with one step. `pack -v` prints each move and its steps. `tests/os/pack.session` fragments a disk (deletes,
replaces, a pipe, a copied `>>`, `rmdir`, a hole just after /bin that moves /man, /docs and a three-level tree), packs
from inside a subdirectory, and checks from the host that nothing is dead any more, that every file of the pristine
image is byte-identical, and that the next file lands at the new free pointer.

## Memory

| Range | Use |
|---|---|
| $0400–$0BFF | the four handles' 512-byte buffers (`HBUFS`, since 2026-09-23: out of the OS's 16K to make room for redirection; BASIC's scratch $0400-$04FF, idle while the OS runs, and the free $0500-$0BFF above the stack's floor $0C00) |
| $0EFF down | the hardware stack, the monitor's (not below $0C00: the handle buffers end at $0BFF) |
| $0F06–$0F0D | SYSARG0..2, SYSRES (the OS's syscall parameter block) |
| $0F10–$0F12 | CFLBA0..2, the sector for CFREAD/CFWRITE (ROM variables) |
| $0F14–$0F3F | SYSTAB, the syscall jump table (entries 0..21, all used since 2026-09-23; the OS copies them from SYSTAB2) |
| $0F40–$0FBF | ARGBUF, a program's command tail (127 chars + NUL; the upper half overlays the monitor's idle line buffer) |
| $1000–$3264 | the OS image (`y1os.asm`, 8,805 bytes = 18 sectors, 2026-11-03 with `sh`; 7,808 on 2026-09-25); the Makefile fails the build if it reaches $4A00 |
| $3265–$49FF | free (6,043 bytes) |
| $4A00–$4F0F | the OS's RAM, cleared at boot: line $4A00 (page-aligned), path, path copy, the entry, name buffers; the pipeline table $4B80; the sector buffer $4C00 (512-aligned); the handle records $4E00 (page-aligned, 16 bytes each); the variables $4E50-$4F0F |
| $4F1D–$4FBF | free (the variables end at $4F1C; XPATH, EXEC's path, is at $4B9C in the pipeline page). Since 2026-11-03 the script state `SC_*` runs to $4F3E |
| $4FC0–$4FFF | SYSTAB2, the 32-entry syscall table (2026-09-25) |
| (C OS) | `y1os.c` instead (`--xisa`): image 14,041 bytes and data 1,788 in $1000-$4DD4, which the Makefile checks against $4FBF. 2026-11-03, with `sh`: 15,275 + 1,035 = 16,310 of 16,320 (10 bytes free), after moving its sector buffer and line and path buffers to low RAM while it runs: `sbuf` $0000-$01FF, `pbuf` $0210, `cwdpath` $0250, `line` $0290, `xpath` $0320-$035F (page zero and BASIC's area, idle while the OS runs; $0200-$020F stays clear, where a bad handle 0's buffer would fall and `tests/os/badhandle` looks) |
| $5000–$CFFF | programs |

## Inside

(Written for `y1os.c`; `y1os.asm` follows it routine for routine under the same names, see its header comments.
The assembly-specific parts are in the next section.)

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
  codes (a byte that cannot be written - full disk, 16M - is dropped silently); the shell's messages use `eputs()`,
  the raw console. `y1cc` cannot check this: calls through SYSTAB are invisible to its call graph.
- The shell parses a line in place (`split()`): commands split at `|`, the redirect names NUL-terminated where
  they stand; `stage()` opens a command's input and output, `run_cmd()` runs it, `io_reset()` closes both.

## The assembly OS (v0.2, 2026-09-23)

`y1os.asm` is `y1os.c` rewritten by hand, routine by routine, with the C as the specification: the same shell,
commands, messages (`strings.txt`, byte-identical; only the banner says v0.2), syscall numbers, arguments, results
and side effects (including what `ENTRY` returns after each call), the same redirection and pipes, the same RAM
areas outside $1000-$4FFF, and the same sectors written in the same order. It is half the size (7,137 bytes against
14,619) and runs the test sessions in 1.3-1.9x fewer instructions (`pipe` and `pack` 1.9x, the command-heavy
sessions ~1.55x; most of the remaining time is the programs, compiled C, and the ROM's sector loop).

- **Build.** The RC/asm assembler upper-cases every source line, so the messages are in `strings.txt` and
  `mkstrings.py` turns them into numeric `DB` lines (`build/asm/y1os_str.inc`, `INCLUDE`d at the end of the code).
- **Registers.** R3 = the value / result (16 bits), R4 and R5 operands and pointers, R6/R7 scratch (the ROM's
  CFREAD/CFWRITE clobber them); R2 is never used (the machine's hidden operand-address register). A routine that
  answers yes/no or a handle leaves it in R3 and in ACC, so the caller branches at once; `ret0`/`ret1`/`reta`/`retr3`
  are the shared exits. 16-bit adds are ADDT/ADDI then ADDTC/ADDIC with only register moves between; no carry is
  read after a shift or a subtract (the machine's carry flip-flop is clocked by those, the interpreter's is not).
- **Layout for cheap addressing.** The RAM is at fixed addresses at the top of the OS area: `SBUF` is 512-aligned, so
  an entry's offset in it is its address's low nine bits; `HTAB` is page-aligned with a 16-byte record per handle
  (mode, then the big-endian words position, length, cur, start), so `hrec` is four shifts and any field is
  `MVRLA R4 / ANDI 0F0H / ORI field / MVARL R4` away; `LINE` is page-aligned, so its length is a register's low byte.
- **The static-frame rule, assembly edition.** Every variable is static, as in the C. The console syscalls and what
  they reach (`cout`, `fs_putc`, `fs_getc`, `hrec`, `hbuf`, `zero512`, `cfrd`, `cfwr`, `key_in`) use registers and
  their own variables only and never print; the shell's own output (`cout`) goes to `fs_putc` directly instead of
  through SYSTAB, which is what the C's `putchar` did by way of the CONOUT handler.
- **Tests.** `tests/os/run.py` passes every session on both emulators with either OS (it compares the banner without
  its version), `run.py --cuts 60` passed 120 of 120 (then 119: a cut in pack's own window, the same with the C OS, BACKLOG.md), and a C-versus-assembly differential run (the same disk, the
  same keystrokes; transcript and every sector of the disk afterwards compared) agreed on the sessions plus the
  built-ins that `/bin` normally hides, loads at the address limits, redirection and pipe edge cases, and a syscall
  torture program (every call with odd handles, paths, names and buffers, the `ENTRY` record after each).

**Behaviours of `y1os.c` kept as they are** (the transcripts are the contract; each is in BACKLOG.md):

1. CLOSE of a read handle returns 1 and of a directory handle **3** (its mode), not the documented 1.
2. A trailing slash after a FILE name still resolves (`fopen("README/")` opens it).
3. CHDIR with a component over 12 characters matches an entry whose 12-character name is its first 12 characters,
   and the current path then carries the whole typed name (`cd /d1/aaaaaaaaaaaaxyz` gives the prompt
   `/d1/aaaaaaaaaaaaxyz>`); OPEN/RESOLVE refuse such a component.
4. CHDIR into a directory whose path would pass 62 characters moves the current directory but leaves the path (the
   prompt, GETCWD) at the parent's: `path_push` gives up silently.
5. DELETE returns 1 even when the tombstone cannot be written; `ren` accepts a new name with spaces (`ren A B C`
   names the file "B C").

**Fixed in both, the same day** (`tests/os/badhandle.session`): PUTC/WRITE on handle 0 with no write open were
accepted (`h != wh` was 0 != 0): the bytes went to `hb(0)` = $0200 (BASIC's variables) and the 513th wrote that
buffer to LBA 0, destroying the boot block; now only the open write handle is written through (READ/GETC/READDIR
were already safe: they check the handle's mode). And `load`/`run` of an empty file loaded one sector's worth and
`run` jumped into it; now it says "bad load address or size". The session writes and reads through bad handles
(0, read, directory, closed, out of range), runs an empty file three ways, and the host checks prove the volume
intact (fsck, the boot block, every pristine file byte-identical); against the old OS it fails (boot block "AB").

## Not there yet

FORMAT and FSCK on the target (the host
tool has them), a second write handle (so `cp` works inside a `>` or a pipe), concurrent pipes (they run one
after the other through temp files), `2>` (errors always go to the screen), the command history, BASIC as `/bin/basic`, and the CF interface in hardware (planned on
the memory card), all in BACKLOG.md.
