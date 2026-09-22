# os — Y1/OS, the YACC1 disk operating system

A RAM-resident shell over a P8XFS v2 CompactFlash volume, written in C for `software/compiler/y1cc.py` and loaded by
the ROM monitor's `O` command. Started 2026-09-22 from the plan in `docs/system/OS-PLAN.md`; **v0 = phases 1 and 2,
read-only, proven on both emulators** (the CF card itself is not built yet). Y1/OS is the YACC1's own from here on:
it is not kept in step with P8X/OS, and neither are the programs brought over (Ken, 2026-09-22). Only the on-disk
format is shared, so `tools/p8xfs.py` (a fork of the P8X tool) builds the images.

```
make -C os              # build/y1os.bin, /BIN programs, disk.img
make -C os run          # the microcode emulator with the ROM and the disk: type O at the monitor prompt
make -C os run-int      # the instruction-level emulator
make -C os test         # tests/os/run.py: scripted sessions on both emulators against expected transcripts
```

## How it boots

The monitor's `O` command (ROM, `firmware/monitor/monitor.asm`) initialises the card (SET FEATURES, 8-bit mode),
reads the boot block (LBA 0) to $1000, checks the `P8` signature and OSCNT, reads LBA 1..OSCNT to $1000 and JSRURs
it. `y1os.c` is compiled with `--org 0x1000`, so `main` is the first byte of the image; `exit` makes main return,
and the monitor's prompt is back. `tools/p8xfs.py boot disk.img build/y1os.bin` installs it (10 sectors today).

## The shell

| Command | Effect |
|---|---|
| `dir [path]` | list a directory: name, `<DIR>` or size, and the load address of a program |
| `cd path` | change directory: absolute `/A/B`, relative, `.`/`..` (the directory's own entries) |
| `pwd` | print the current path (also the prompt) |
| `cat path` / `type` | print a file |
| `load path` | read a file into its stored load address |
| `run path [args]` | load it and call its exec address; `args` are left at ARGBUF ($0F40) for `argstr()` |
| `help` / `?` | this list |
| `exit` | back to the monitor |
| anything else | `/BIN/NAME` (upper-cased), then `NAME` in the current directory, run with the rest of the line as arguments |

Names are case-sensitive and stored as `p8xfs.py put` writes them; the Makefile puts programs in `/BIN` in upper
case, which is why the implicit lookup upper-cases the command word.

## Programs

`os/commands/*.c`, compiled with `--org 0x5000` (the transient area starts at $5000 and runs to $CFFF) and put with
`--load 0x5000 --exec 0x5000`. A program is an ordinary y1cc program: `main` returns to the shell, console I/O is
the compiler's `putchar`/`puts`/`getchar` through the BIOS vectors, `argstr()` is its command tail, `lib_abi.c` names
the ROM vectors and variables for `bios()` calls (`wc.c` reads sectors directly that way). Today: `HELLO`, `ECHO`,
`WC` (raw sectors; the file layer belongs to the OS).

## Memory

| Range | Use |
|---|---|
| $0F10–$0F12 | CFLBA0..2, the sector for CFREAD/CFWRITE (ROM variables) |
| $0F40–$0F7F | ARGBUF, a program's command tail |
| $1000–$4FFF | the OS image (5.1K today) and its data: sector buffer, line buffer, path, directory state |
| $5000–$CFFF | programs |
| $0EFF down | the hardware stack, the monitor's |

## Inside

- `cfread(lba, buf)` = poke the LBA into the ROM's variables, `bios(CFREAD, buf, 0)`; the ROM streams 512 bytes
  through the two CF ports (P8 select, P9 data).
- Directory entries are the 32-byte P8XFS v2 records, little-endian on disk; the 16-bit fields are assembled
  byte-wise (the YACC1's own words are big-endian, which never matters here). `take_entry()` fills the `e_*`
  globals for the entry a scan found; `find_in()` scans one extent sector by sector, stopping at the $00 end mark
  and skipping $FF tombstones; `resolve()` walks a path component by component, iteratively (y1cc rejects
  recursion); `cmd_cd` keeps the textual path for the prompt as it goes.
- One 512-byte sector buffer serves everything; a file load goes straight into its load address.

## Not there yet

Write support (save, del, mkdir, rmdir, pack, format, fsck: the P8X shell has them all and the host tool can
verify a volume), a file API for programs (open/read/close through an OS jump table, the way P8X's `lib_abi`
works), output redirection, the command history, the P8X commands worth porting, BASIC as `/BIN/BASIC`, and the
CF card in hardware, all in BACKLOG.md.
