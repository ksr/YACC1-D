# Y1/OS — the YACC1 disk operating system

User guide, programmer guide (commands and the syscall/file API), the on-disk format, the memory layout and the
plan for Y1/OS. Written 2026-09-23 from the YACC1-D tree. Later the same day the P8X commands were ported (26 programs in /BIN, ten shared libraries, 50 man pages in /MAN, `vi`): `os/README.md` carries the current command table and `os/PORT-PLAN.md` the per-command status; the API described here is unchanged.

Sources: `os/y1os.c` (v0.1, read as of 2026-09-23 09:43 — **it was being edited while this was written**),
`os/lib_abi.c` (09:37), `os/README.md` (the v0 text of 2026-09-22), `os/commands/{hello,echo,wc}.c`, `os/Makefile`,
`os/disk/README.TXT`, `os/PORT-PLAN.md` (2026-09-23), `tools/p8xfs.py` (the on-disk format and the host tool),
`tools/img2bin.py`, `tests/os/run.py`, `tests/os/basic.session` and `basic.int.out` (v0 transcripts),
`docs/system/OS-PLAN.md`, `firmware/abi/README.md`, `firmware/monitor/monitor.asm` (the `O` command, `uartinne`),
`software/compiler/y1cc.py` (`sys()`, `funcaddr()`, `argstr()`), `software/cfmodel.h`, `BACKLOG.md`.

## 1. What it is, and what it is not

Y1/OS is a RAM-resident shell and file layer over a P8XFS v2 CompactFlash volume, written in C for `y1cc` and loaded
by the ROM monitor's `O` command. **v0** (2026-09-22, `os/README.md`) was read-only: dir/cd/pwd/cat/load/run. **v0.1**
(2026-09-23, `y1os.c` header) adds the file layer (`fs_*`), write support (save/del/ren/mkdir/rmdir), handles, and a
syscall table through which programs use the same functions. Everything is **proven on the emulators only** — the CF
card is not built (`docs/system/MACHINE.md`). Y1/OS is the YACC1's own from here on: **it is not kept in step with
P8X/OS, and neither are the programs brought over** (Ken, 2026-09-22/23, `os/README.md`, `os/PORT-PLAN.md`). Only the
on-disk format is shared, so `tools/p8xfs.py` (a fork of the P8X tool) builds the images and images can be exchanged.

State on 2026-09-23 morning: `y1os.c` references `os/lib_fs.c` (C wrappers `fopen()`… over `sys()`) which does not
exist in the tree yet; `os/README.md`, `os/disk.img` (13:45 on 2026-09-22) and the `tests/os` transcripts are the v0
ones (the v0.1 banner differs: `Y1/OS v0.1 (2026-09-23)  P8XFS v2`). **To verify:** rebuild (`make -C os`) and
`tests/os/run.py --update` once the OS edit settles; the v0.1 commands below are read from the source, not from a
transcript.

```
make -C os              # build/y1os.bin, the /BIN programs, disk.img
make -C os run          # the microcode emulator with the ROM and the disk: type O at the monitor prompt
make -C os run-int      # the instruction-level emulator
make -C os test         # tests/os/run.py: scripted sessions on both emulators against expected transcripts
```

## 2. User guide

### Booting

At the monitor prompt type `O`. The ROM prints `BOOT FROM CF`, initialises the card, reads the boot block, checks the
`P8` signature and OSCNT, loads LBA 1..OSCNT to $1000 and calls it (`monitor.asm` `boot:`, [MONITOR.md](MONITOR.md)
section 6). The OS installs its syscall table, reads the boot block again for OSCNT and the free pointer, announces
itself and prompts with the current path: `/> `. Errors: `CF ERROR` (no card or a read failed), `NO OS ON THE CARD`
(bad signature or OSCNT = 0), `CF read error` (the OS's own read of LBA 0).

### The shell (`y1os.c` `main`)

A line is read with `readline()` through `UARTIN` (which echoes; backspace and DEL erase; up to 128 characters; LF,
CR or NUL ends it). The first word is lower-cased and matched; the rest of the line is the argument string.

| Command | Effect (`y1os.c`) |
|---|---|
| `dir [path]` | list a directory through a directory handle: name, `<DIR>` or size (`NNx64K+` prefix over 64K), `@LOAD` for a file with a load address; then `N entries` |
| `cd path` | change directory (`fs_chdir`): absolute `/A/B` or relative; `.` and `..` are the directory's own entries; the prompt path follows the components |
| `pwd` | print the current path |
| `cat path` / `type path` | print a file, sector by sector through a read handle |
| `load path` | read a file into its stored load address; `loaded N bytes at $XXXX` |
| `run path [args]` | load the file and call its exec address; `args` (up to 127 characters) go to ARGBUF for `argstr()`; whatever the program left open is closed when it returns |
| `save path addr len` | **new in v0.1**: write `len` bytes of memory from `addr` (both hex) to a new file whose load and exec address are `addr` (`fs_create`, `fs_write`, `fs_close`); a same-named file is replaced |
| `del path` | tombstone a file (`fs_delete`; `not a file` otherwise) |
| `ren path newname` | rename in place: the entry keeps its slot and directory (`fs_rename`; `newname` is a bare name) |
| `mkdir path` | a new 4-sector directory extent at the free pointer with `.` and `..` (`fs_mkdir`) |
| `rmdir path` | tombstone an empty directory (`fs_rmdir`; `not an empty directory` otherwise) |
| `help` / `?` | the three-line summary |
| `exit` | prints `bye` and returns to the monitor (`main` returns; the ROM's `JSRUR` return lands in `cmdloop`) |
| anything else | `try_bin`: the word upper-cased, looked up as `/BIN/NAME`, then as `NAME` in the current directory; a file is loaded and run with the rest of the line as arguments; otherwise `what?` |

Paths: components 1..12 characters (`name too long` otherwise); a trailing `/` is accepted; `not found`, `not a
directory`, `is a directory`, `too big` (over 64K) are the errors. **Names are case-sensitive** and stored as the host
tool writes them; the Makefile puts programs in `/BIN` in upper case, which is why the implicit lookup upper-cases
the command word (so `hello a b c` finds `/BIN/HELLO`). Load-address rule (`load_file`): a program must load at or
above `TPA` = $5000 and end below `TPATOP` = $D000, else `bad load address or size`.

The v0 session `tests/os/basic.session` with its transcript `basic.int.out` shows the read-only commands' exact
output (including `wc 45 1` on raw sector 45, `cd /BIN/../BIN`, and `nothere` → `what?`).

### The disk image that ships

`os/Makefile` builds `os/disk.img` (2048 sectors = 1 MB): the OS at LBA 1.. (10 sectors for v0), `/BIN/HELLO`,
`/BIN/ECHO`, `/BIN/WC`, and `/README.TXT` from `os/disk/`. `p8xfs.py tree disk.img` lists it.

## 3. Programmer guide

### Writing a `/BIN` command

A command is an ordinary `y1cc` program (`os/commands/hello.c`):

```c
#include "../lib_abi.c"
#include "y1lib.c"
void main() {
    puts("hello from /BIN/HELLO");
    if (*argstr()) { putstr("args: "); puts(argstr()); }
}
```

- Compile at the transient area: `y1cc.py hello.c -o hello.asm --org 0x5000 --os` (no `--boot`, no `--vector`: the
  OS calls the exec address with `call()` = `JSRUR R7`, and `main`'s `RET` returns to the shell; `--os` since
  2026-09-23, so that the console goes through the OS and can be redirected).
- Assemble (`asm hello -d=yacc1` with `yacc1.def` and a `-h` `rcasm.rc` beside it) → `hello.img`.
- Flatten: `python3 tools/img2bin.py hello.img hello.bin --base 0x5000` (unwritten bytes come out as 0; the `--end`
  default $F000 keeps any stub out).
- Put on the disk: `python3 tools/p8xfs.py put disk.img hello.bin --name /BIN/HELLO --load 0x5000 --exec 0x5000`
  (the Makefile does this for every `commands/*.c`, upper-casing the name), or from the machine `save /BIN/HELLO
  5000 len` after loading it another way.
- Arguments: `argstr()` returns the NUL-terminated tail at ARGBUF ($0F40, up to 127 characters). Console output is
  the compiler's `putchar`/`puts` (with `--os` the CONOUT syscall, which the shell redirects; without it BIOS
  `CHAROUT` on the machine and on ucemu, port 2 on the interpreter); input for a filter is `sys(SYS_CONIN)` (stdin:
  no echo, 65535 at its end or at Ctrl-D) and `sys(SYS_CONST)`; a key is `sys(SYS_KEYIN)` (below).
- All the compiler's rules apply: no recursion, R2 untouched, carry only in the compiler's idioms
  ([C-COMPILER.md](C-COMPILER.md)). A program's globals and BSS live in its own image (cleared at its `main`).

### The syscall interface (`os/lib_abi.c`, `y1cc.py` `sys`, `y1os.c` `install`)

`sys(SYS_x, a, b, c)` stores `a`, `b`, `c` (any of them optional) into the argument words `SYSARG0..2`
($0F06/$0F08/$0F0A), `JSRUR`s the word at `SYSTAB + 2·x` ($0F14 + 2x) and returns `SYSRES` ($0F0C) — always a full
16-bit word: 1/0 for yes/no, a handle or 0, a count, a byte or 65535 for none / end of file. Y1/OS fills `SYSTAB` at
boot with `pokew(SYSTAB + 2*n, funcaddr(h_x))`; each handler reads `SYSARGn` with `peekw()`, calls the `fs_*`
function, and writes `SYSRES` with `pokew()`. The table keeps the *shape* of the P8X `$20xx` syscalls (OS-PLAN
decision 6) so that P8X C commands port by swapping `lib_abi.c`. Handles are 1..4 (`NH`), each with its own 512-byte
buffer and position; **one write handle at a time**.

| n | Name | Arguments → result (`lib_abi.c`) |
|---|---|---|
| 0 | `SYS_OPEN` | `(path)` → handle 1..4, 0 not found / not a file / no handle free / over 64K |
| 1 | `SYS_READ` | `(handle, buf512)` → bytes put in `buf` from the sector holding the position; 0 at the end |
| 2 | `SYS_GETC` | `(handle)` → next byte, 65535 at the end |
| 3 | `SYS_CLOSE` | `(handle)` → 1; a written file is registered in its directory here (last sector flushed, entry written, free pointer moved) |
| 4 | `SYS_CREATE` | `(path, load, exec)` → handle, 0 cannot (a same-named file is replaced; refused while another write is open) |
| 5 | `SYS_WRITE` | `(handle, buf, n)` → bytes written |
| 6 | `SYS_PUTC` | `(handle, byte)` → 1, 0 cannot |
| 7 | `SYS_DELETE` | `(path)` → 1 tombstoned, 0 not a file |
| 8 | `SYS_MKDIR` | `(path)` → 1, 0 cannot (exists, parent missing, no slot, a write is open) |
| 9 | `SYS_RMDIR` | `(path)` → 1, 0 not a directory or not empty |
| 10 | `SYS_OPENDIR` | `(path)` → handle, 0 not a directory (`""` = the current directory) |
| 11 | `SYS_READDIR` | `(handle, buf32)` → 1 with the next live 32-byte entry in `buf`, 0 at the end |
| 12 | `SYS_RESOLVE` | `(path, buf32 or 0)` → 1 found (entry copied to `buf`), 0 not found |
| 13 | `SYS_GETCWD` | `(buf)` → length; the current path, NUL-terminated (up to 64 bytes) |
| 14 | `SYS_CHDIR` | `(path)` → 1, 0 not found, 2 not a directory |
| 15 | `SYS_RENAME` | `(oldpath, newname)` → 1, 0 cannot |
| 16 | `SYS_ENTRY` | `(buf32)` → 1; the 32-byte entry the last OPEN/OPENDIR/RESOLVE/CREATE… found, copied |
| 17 | `SYS_CONIN` | `()` → the next byte of **stdin**, without echo: the shell's `<` file or pipe (65535 at its end), else the console (ROM `UARTINNE`; 65535 on Ctrl-D or NUL, the emulator's end of input). `y1cc --os`: `getchar()` |
| 18 | `SYS_CONST` | `()` → 1 when a stdin byte is waiting (a `<` file or pipe: always 1; the console: ROM `CONST`, always 1 on the emulators) |
| 19 | `SYS_CONOUT` | `(byte)` → nothing (SYSRES untouched): the byte to **stdout**, the shell's `>`/`>>` file or pipe, else the raw console (`CHAROUT`). `y1cc --os`: `putchar()`/`puts()` (2026-09-23) |
| 20 | `SYS_KEYIN` | `()` → a **key**: always the console, never redirected, no echo; 65535 on Ctrl-D/NUL (2026-09-23) |
| 21 | `SYS_STDIO` | `()` → bit 0 stdin redirected, bit 1 stdout redirected (2026-09-23). SYSTAB is full with it |

Writing goes to the volume's free pointer (boot block bytes 4–5, kept in step on disk): `CREATE` takes the handle
and remembers the directory and the name, `PUTC`/`WRITE` fill the handle's sector buffer and flush full sectors,
`CLOSE` writes the last (possibly partial) sector, registers `(name, start, length, load, exec, $01)` in the first
free slot of the directory, and advances the free pointer — the same layout `p8xfs.py` writes, so the host tool
reads what the OS wrote and vice versa. Files over 64K cannot be opened (16-bit positions). `tests/compiler/syscall.c`
is a stand-alone model of the whole mechanism (handlers, `funcaddr`, nested `sys()` calls).

### Redirection and pipes (2026-09-23)

The shell takes `cmd [args] [< in] [> out | >> out] [| cmd ...]`, up to four commands per line (`os/man/shell`,
`os/README.md`). It works because the OS and every `/BIN` command are compiled with `y1cc --os`: `putchar`/`puts` are
the syscall **CONOUT** (19) and `getchar` is **CONIN** (17). Before a command runs the shell opens its files and sets
`so_h`/`si_h` in `y1os.c`: CONOUT then writes the byte to the output file (or, with `so_h` = 0, to the raw console
through the ROM's `CHAROUT`, never through `putchar`, which would call CONOUT again); CONIN and CONST read the input
file (`si_h`) or the console. After the command, whatever happened, both files are closed and the console is back. A
pipe `a | b` runs a with its output to `/PIPE0.TMP`, then b with its input from it (stages alternate
`/PIPE0.TMP`/`/PIPE1.TMP`); the temp files are deleted after the line. There is no multitasking: the stages run one
after the other.

Two kinds of input follow from it. **Data** is `conin()` (CONIN): the filters' "no file named" and `-`, redirectable.
A **key** the user presses in answer to the program is `keyin()` (**KEYIN**, 20): always the console, so `cat F |
more` pages the pipe while `--More--` waits on the keyboard (a Unix pager reads `/dev/tty` for the same reason);
`vi`, `dump`, `examine` and the pager use it. **STDIO** (21) tells a program what is redirected; the pager does not
page when its output is a file or a pipe. Error messages use `eputs()` (`os/lib_err.c`), which writes through the
ROM's `CHAROUT` and so never lands in a file or a pipe.

Rules that come with it:

- **One write handle.** CREATE and MKDIR allocate at the single free pointer, so while a command's stdout is a file
  (`>`, `>>`, or a pipe) its own CREATE/MKDIR returns 0: `cp`, `touch`, `save`, `mkdir`, `vi`'s `:w` fail cleanly
  inside a redirect or a pipe (they work with `<`).
- **Replace at close.** A same-named file is replaced when the new one is closed, by writing the new entry over the
  old one's slot (one sector); until then the old file is whole (`sort F > F` works) and a write that fails leaves it.
- **`>>`** continues in place when the file is the last one written (its extent ends at the free pointer), else copies
  the old sectors to the free pointer first; no byte of the old file changes either way.
- **Static frames.** y1cc frames are static and the OS's own `putchar` is CONOUT, so nothing on the console handlers'
  path (`con_out`, `con_in`, `key_in`, `fs_putc`, `fs_getc`, `cfread`, `cfwrite`...) may print: a handler would
  re-enter itself. Their errors are return codes; the shell's messages use the raw console.

### Reading sectors directly (`os/commands/wc.c`)

Before the file API, `wc LBA COUNT` read raw sectors through the BIOS, which remains the pattern for anything below
the file layer: `poke(CFLBA0, lba); poke(CFLBA1, lba >> 8); poke(CFLBA2, 0); if (bios(CFREAD, buf, 0)) …` with a
512-byte `char` array (R7 advances). `os/PORT-PLAN.md` wave 1 replaces this `wc` with the P8X one over the file API.

`os/lib_abi.c` is the address list: the BIOS vectors `STRINGOUT` $FFC0, `CHAROUT` $FFC4, `UARTOUT` $FFC8,
`SHOWADDR` $FFCC, `UARTIN` $FFE8, `CFINIT` $FFEC, `CFREAD` $FFF0, `CFWRITE` $FFF4, `CONST` $FFF8, `UARTINNE` $FFFC;
the variables `SYSARG0..2` $0F06/$0F08/$0F0A, `SYSRES` $0F0C, `CFLBA0..2` $0F10–$0F12, `SYSTAB` $0F14, `ARGBUF`
$0F40 (`ARGMAX` 127), `OSBASE` $1000, `TPA` $5000, `TPATOP` $D000; and the `SYS_*` numbers above.

## 4. P8XFS v2 on disk (`tools/p8xfs.py`, `y1os.c`)

A volume is a sequence of 512-byte sectors (LBAs). All multi-byte fields are **little-endian** (the P8X's order;
`struct` formats `<H`, `<I` in `p8xfs.py`; `le16()`/`put16()` in `y1os.c`).

| LBA | Contents |
|---|---|
| 0 | boot block: bytes 0–1 `P8`, byte 2 version = 2, byte 3 OSCNT (sectors of OS image, 0 = none), bytes 4–5 the free pointer (first unallocated LBA); the rest zero |
| 1–32 | the OS image, `OSCNT` sectors used (max 32 = 16 KB; `p8xfs.py boot` refuses more); loaded to $1000 by the `O` command |
| 33–36 | the root directory: a 4-sector extent = 64 entries; entry 0 = `.` (itself), entry 1 = `..` (itself for the root) |
| 37… | files and subdirectory extents, contiguous, allocated at the free pointer (`alloc` / `fs_create`), moved only by `pack` |

A directory is a file whose extent holds 32-byte entries; a subdirectory's extent is 4 sectors by default
(`mkdir --secs` changes it on the host; the OS always makes 4; the OS reads the size from the entry). Entries are
used in order; the first entry with flag `$00` ends the scan, and a deleted entry is a tombstone `$FF` that a new
entry may reuse. Neither the OS nor the host tool frees space when it deletes or replaces; `/BIN/PACK` does it in
one pass (below).

**Compaction (`pack`, 2026-09-23).** `os/commands/pack.c` reads the tree from the root without recursion (its
record table is the work list: start LBA, sectors, the record of the holding directory, the entry's byte offset),
sorts the live extents by start LBA, refuses a volume whose extents overlap or pass the free pointer, then slides
each extent down to the lowest free sector at or above LBA 37, sector by sector with CFREAD/CFWRITE. Ascending order
is the whole safety argument: every extent still to move lies above the current one and the copy only writes below
the current one's end. Each moved entry is rewritten in its directory where that directory is at that moment; a
moved directory's '.' and its subdirectories' '..' follow, and every '.'/'..' is re-checked. It writes the new free
pointer, re-enters the current directory by path (the OS caches its LBA) and returns; the shell re-reads the free
pointer after every program (`read_free()`), since the OS caches that too. Refused under `<`/`>`/`>>`/`|` (STDIO).
No journal: an interruption leaves a sound structure that a second `pack` completes, but the extent in flight is
lost when its hole was smaller than itself (`man pack`). `p8xfs.py fsck` checks '.' as well as '..' since then.

The 32-byte directory entry (`pack_at`/`unpack_at`, `take_entry`/`set_entry`):

| Offset | Size | Field |
|---|---|---|
| 0 | 12 | name, ASCII, space-padded, **case preserved**; the host tool silently truncates a longer name to 12 (aliasing another with the same first 12 bytes — `--strict` makes that an error); the OS refuses names over 12 |
| 12 | 4 | start LBA (`<I`; the OS reads the low 16 bits and writes the high 16 as 0) |
| 16 | 4 | length in bytes (`<I`; the OS reads the low 16 bits and byte 18 as "×64K", so `dir` shows files up to 16 MB and `cat`/`load`/open refuse them) |
| 20 | 2 | load address (`<H`; `p8xfs.py put --load`, default $B000 — always give `--load 0x5000` for the YACC1) |
| 22 | 2 | exec address (`<H`; `--exec`) |
| 24 | 1 | flags: `$00` end of directory, `$01` file, `$02` directory, `$FF` deleted |
| 25 | 7 | spare, zero |

Sector count of an entry = ⌈length / 512⌉ (`take_entry`: `(e_len + 511) / 512 + e_lenhi * 128`, minimum 1); a
directory's sector count comes from its length field (`dir_secs`). `p8xfs.py fsck` checks the signature, the `.` and
`..` links, the extents and reports reclaimable space.

Host tool summary (`p8xfs.py --help`): `create img [--sectors N]` (default 256; the Makefile uses 2048), `boot img
os.bin`, `mkdir img /BIN [--secs N]`, `put img file [--name /BIN/F] [--load A] [--exec A] [--replace] [--strict]`,
`rm img /BIN/F`, `get img /BIN/F [--out path]`, `ls img [path]`, `tree img`, `fsck img`. Both emulators take the
image with `-c disk.img` and create a zero-filled 256-sector one if the file is missing (`software/cfmodel.h`).

## 5. Memory layout with the OS running (`os/README.md`, `lib_abi.c`, `OS-PLAN.md` map A)

| Range | Use |
|---|---|
| $0000–$0EFF | system page: BASIC's areas (unused while the OS runs); the OS's four 512-byte handle buffers at $0400–$0BFF (since 2026-09-23); the stack from $0EFF down, not below $0C00 |
| $0F00–$0FFF | the ROM's variables, and the OS's syscall block inside their free space: `SYSARG0..2` $0F06–$0F0B, `SYSRES` $0F0C, `CFLBA0..2` $0F10, `SYSTAB` $0F14–$0F3F, `ARGBUF` $0F40–$0FBF (over the monitor's idle line buffer) |
| $1000–$4FFF | the OS image (5.1K for v0; 14,624 bytes = 29 sectors with redirection and pipes, 2026-09-23) and its data (1,424 bytes: the OS sector buffer, line, path, directory, handle and pipeline state); image + data must end below $5000 (the Makefile checks; 16,048 of 16,384 today) |
| $5000–$CFFF | the transient program area (`TPA`..`TPATOP`), 32 K |
| $D000–$DFFF | video (map A: $D000–$D7FF the 2K display RAM, $D800–$DFFF unused) — not RAM |
| $E000–$FFFF | ROM |

Map B in `OS-PLAN.md` (video moved to $E000, `$D000` jumpered as RAM) would make the TPA 36 K; the OS must not care
which — `TPATOP` is the one constant. Whether the OS load address stays $1000 if the OS outgrows 16 K is an open
question in the plan.

## 6. Tests

`tests/os/run.py [--keep] [--update]` builds `os/disk.img` (`make -s -C os`), then for every `tests/os/*.session`
feeds `O\n` + the session lines to both emulators (`emulator -x -m -c disk.img -l 6000000` and `y1ucemu -x -m -c
disk.img -l 80000000`), cuts the transcript from `BOOT FROM CF` to the monitor prompt after `bye`, and compares
with `NAME.int.out` / `NAME.uc.out` (the microcode transcript shows the monitor's input echo). `--update` rewrites
the expectations after a change that was checked by eye. Part of `make check` and `make os-test` at the root. The
committed transcripts are v0's (banner `Y1/OS v0 (2026-09-22)`).

## 7. The plan and the backlog (`OS-PLAN.md`, `os/PORT-PLAN.md`, `BACKLOG.md`)

Decisions already taken (2026-09-22): CF in I/O space on P8/P9 (select + data, to keep six ports free); the video
card v2 puts the 6845 on ports PA/PB so it needs only 2K of memory; the port map and the two memory-map variants;
the ROM holds only sectors (monitor + CF driver + boot), never the filesystem, so an OS change never needs a burn;
P8XFS v2 byte for byte; the kernel in C with y1cc (size is the risk: C is 2–3× assembly); the console is two BIOS
vectors so video/PS-2 can replace the UART without the OS knowing.

Done since (2026-09-23, in the source): write support and the file API/syscalls above (phase 2's second half and
the start of phase 3). Still to do, in the plan's order:

1. **The CF card in hardware**: KiCad, two ports, 74245 + 74LS174/273 select latch + decode + strobe gating, True
   IDE 8-bit, status pull-ups, activity LED; the first KiCad-native card; bench-tested with the bus tester
   (`OUTI P8 / INP P9` through the ROM driver) before the CPU touches it.
2. `fsck` on the OS side (`pack` done 2026-09-23, `/BIN/PACK`); `os/lib_fs.c` (the C wrappers over `sys()`); updated `os/README.md`, `disk.img`
   and `tests/os` transcripts for v0.1.
3. **Porting the P8X commands** (`os/PORT-PLAN.md`, survey of 46 commands + 18 libraries): wave 0 the shared
   libraries (`lib_stdin`, `lib_glob`/`lib_regex` made iterative…) and the mechanical recipe (`//#use X` →
   `#include "lib_X.c"`, `bios()` no longer returns a carry bit); wave 1 console-only and file readers (`pwd help
   dep dump examine man cat wc head tail more sort uniq sed awk cmp diff md`); wave 2 writers and directory tools
   (`touch del mv`, then `tree find dir grep -r cp -r` with iterative walks); wave 3 development tools (`vi`, an
   on-target `asm` for the RC/asm dialect); the graphics/WM programs deferred or skipped; ~48 man pages to bring over
   as edited text; BASIC re-assembled at a TPA address as `/bin/basic` (OS-PLAN phase 3). The plan's open design
   points (its section 5): console EOF and shell redirection, `rename` (now done), several handles (done: 4),
   `create` with load/exec (done), a no-echo console read (done: `UARTINNE`/`SYS_CONIN`).
4. **Video console + PS/2 keyboard** behind the console vectors (video card v2 on PA/PB, a keyboard controller on
   PC/PD).

Done 2026-09-23: redirection and pipes (`<`, `>`, `>>`, `|`, above). Also open: command history in the shell; dual CF (a second card at PC/PD);
the E-command RAM loader, which becomes unnecessary once the card boots.
