# CLAUDE.md — working on YACC1-D

YACC1-D is the single-source repository for Ken Rother's **YACC1**, a hand-built 8-bit TTL CPU (8-bit ACC/TMP,
16-bit registers R0-R7, microcoded), and everything around it: the card designs, the microcode, the monitor ROM,
BASIC, the Y1/OS disk operating system, the C compiler y1cc, emulators and bench tools. Ken develops on two Macs;
this file is what a Claude session on either machine needs before touching anything. `README.md` is the tour of the
tree; `BACKLOG.md` is what is open; `docs/system/MACHINE.md` is what is actually in the machine today.

## Standing rules (Ken's)

- **Commit to `main`** with conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`…) and **push after each
  commit**. No branches or PRs unless Ken asks. Stage explicit paths (never `git add -A` / `git add .`): other work
  may be in the tree. End every commit message with the co-author line the session's attribution instructions give.
- **Never modify `~/Documents/YACCS`** (the historical archive the tree was migrated from; it only exists on Ken's
  first Mac and the repo does not need it).
- **Migrated files** (sources that came from YACCS, e.g. `software/emulator/main.c`, `software/assembler/*`,
  `firmware/monitor/monitor.asm`, the microcode generator) are edited only with a dated note in
  `tools/patched_files.txt`.
- **`python3 tools/audit_tree.py` must report 0 unexplained** files after every commit.
- **Y1/OS has two kernels kept in step**: `os/y1os.asm` (the real one) and `os/y1os.c` (the specification, `make -C os
  OS=c`). Every OS change goes into both; `tests/os` runs with both.
- **Y1/OS and its commands are not kept in sync with the P8X project** (`~/Developer/p8x`, a sibling machine); P8X is
  read-only reference.
- **The ROM and the microcode are burned/loaded by Ken at the machine.** Build and verify images
  (`tools/verify_firmware.py`), mark them "not burned/loaded" in the docs, and leave the hardware step to him.
- **Background work runs on Opus**, and must leave nothing running when it finishes (no emulators, routers or
  `until …; do sleep` wait loops).
- **Every source file starts with an authorship header** (Ken, 2026-10-02): `tools/authors.tsv` says who wrote each
  file and `python3 tools/author_headers.py --check` (in `make check`) enforces it. A new source file Claude writes: add
  `path<TAB>claude<TAB>written in YACC1-D` to `tools/authors.tsv` and run `tools/author_headers.py --apply`; never
  re-label Ken's code as Claude's (a changed file of Ken's keeps "Author: Ken Rother", with the change in
  `tools/patched_files.txt`). Third-party and generated files get no header.
- New `/BIN` commands need a man page (`os/man/NAME`) and a `help` line; Y1/OS disk docs changing size changes the
  `tests/os` pack transcript's size lines (`python3 tests/os/run.py pack --update`, only size lines may change).
- **The documentation's voice (Ken, 2026-10-02): everything reads as Ken's own project documentation.** Write the
  plain documentation voice - the subject is the machine, the card, the document ("The v2.0 board uses standoff option
  E (chosen 2026-09-25)"), procedures in the imperative ("Burn `rom.bin` ..."), "I" only where a person must be in the
  sentence. Never narrate who asked for what: no "Ken asked / Ken's pick / Ken decided / at Ken's request", no
  "Claude", "this session", "the agent", "the user". Keep the facts, dates and commit hashes. Claude's part is stated
  once, in `README.md` ("Who made it") and the project site's home page, and in the authorship headers. Exempt: this
  file, the authorship headers and `tools/authors.tsv`, commit messages, `deprecated/` and `archive/`, third-party and
  generated files, and Ken's own comments in his code.
- Ken likes explanations that teach: say what was done, why, and what it means for the machine.

## Machine facts that bite

- **R2 is the hidden operand-address register** the microcode uses for LDA/STA/LDR/STR: programs must never use it
  (the emulators have a separate register, so misuse only fails on the real machine). R0 = PC, R1 = SP.
- Words are big-endian in memory; P8XFS on-disk fields are little-endian.
- **BRVR is an indirect jump**; JSRUR calls through a register; BRUR ($AD) jumps to Rn.
- The ALU's carry flip-flop latches carry-out **OR** shift-out; the microcode clears shift-out before every add/subtract
  (the 2026-09-23 carry fix). Carry rules for code generators: `software/compiler/README.md`.
- Four extra instructions (2026-09-24, `--xisa`): `LDZ`/`STZ Rn,d` ($80+n/$88+n, variable page = R6 high byte),
  `ADDIW Rn,#w` ($C0+n), `SHL16 Rn` ($C8+n). The native toolchain (compiler passes, /BIN/ASM) needs them.
- Memory map: ROM $E000-$FFFF (BASIC $E000, monitor $F000, BIOS vectors $FFC0-$FFFC, video entry $FFBC); monitor RAM
  $0C00-$0FFF (stack $0C00-$0EFF, variables $0F00.., SYSTAB $0F14, ARGBUF $0F40, video flags $0FF0-$0FF7); Y1/OS at
  $1000, OS RAM $4A00, SYSTAB2 $4FC0; programs (TPA) $5000-$CFFF; video RAM $D000-$D7FF, 6845 CRTC $D800 (address) /
  $D802 (data), odd addresses there = the JP1 latch (never write them).
- I/O ports: P0/P1 = the I/O card (control latch + data: UART, switches, LEDs, LCD, TIL311); P2-P7 decoded by it but
  unused; **P8/P9 = CompactFlash** (register select / data); PA-PF free. Console: 16550 UART, 38400 8N1.
- Serial ports on the Mac (FTDI serial numbers, the same on both Macs): console `/dev/cu.usbserial-AB0MVHSQ`,
  sequencer card (microcode loader) `/dev/cu.usbserial-AB6WZCQX`. Clock 1 MHz; ~26 clocks per
  instruction on the native toolchain's workload with the tree's microcode (2026-09-29: three-step fetch prologue and
  idle steps; 32.4 before; the machine's EEPROM holds it since 2026-10-04).

## Where things are

| | |
|---|---|
| Card designs | `hardware/cards/<card>/{eagle,kicad}/<version>/` (deprecated versions under `deprecated/`, never edited); theory of operation in `docs/cards/` |
| Microcode | `firmware/microcode/ucode-generator2/` (C generator → `test.hex`); `docs/system/MICROCODE.md` |
| Monitor, BASIC, ROM image | `firmware/monitor/monitor.asm`, `firmware/basic/`, `firmware/rom/shipped/rom.bin` (+ README with what is burned) |
| Assembler (host) | `software/assembler/` (RC/asm + `yacc1.def`); quirks in `docs/programming/ASSEMBLER.md` |
| C compiler | `software/compiler/y1cc.py` (reference), `software/compiler/c/` (C twin `y1cc.c`, the nine passes `cc1..cc9`) |
| Emulators | `software/emulator/` (instruction level), `software/ucemu/` (microcode level, steps `test.hex` through card models) |
| Y1/OS | `os/` (kernels, `commands/` in C, `commands-asm/asm.asm`, `man/`, `Makefile` → `os/disk.img`) |
| Machine tools | `tools/ucode_send.py` (microcode loader), `tools/monload.py` (monitor `:` loader), `tools/cfcard.py` (write a CF card), `tools/y1term.py` (terminal; types a file into BASIC, waiting for `>>` after each line), `tools/y1kermit.py` + `tools/y1.ksc` (Kermit), `tools/setup_check.py` (is this Mac set up?) |
| Arduino sketches | `embedded/` (built against the vendored `embedded/libraries/` only) |
| Project website | `website/` (MkDocs + Material over the docs; `website/build.sh [serve|publish]`, `website/README.md`); published at https://yacc1.cottageworker.com by `.github/workflows/website.yml` on every push to main |

## Build and test

```
python3 tools/setup_check.py     # on a new Mac: which tools are missing and what each is for
make                             # build the C tools - REQUIRED before make check (on a fresh clone check stops
                                 # at the compiler tests: "missing software/emulator/emulator")
make check                       # everything (~11 min): audit, firmware/microcode/sketches rebuilt and diffed,
                                 # compiler, twins, OS sessions, native compile, self-host, asm, video, kermit
make -C os                       # os/disk.img;  make -C os run  boots it on the microcode emulator (O at the monitor)
make os-test | cc-test | native-test | selfhost | asm-test
```

The known non-pass line in `make check` is the Arduino work-in-progress sketch `bus-driver-mcp23x17-wip` (marked
expected). Board builds (`hardware/cards/*/kicad/*/build.sh`) need KiCad 10, Inkscape (`INK=`), Java and Freerouting
(`FRJAR=`, default `~/freerouting/freerouting.jar`).

## At the machine (Ken's steps)

- **Microcode**: `python3 tools/ucode_send.py --all`, then press START on the sequencer card (the tool resets it via
  DTR first); it verifies the load.
- **Bench**: reset the YACC1, then `python3 tests/bench/run.py --port /dev/cu.usbserial-AB0MVHSQ` (logs in
  `tests/bench/logs/`).
- **ROM**: Ken burns `firmware/rom/shipped/rom.bin` (28C64, offset 0 = $E000) with Visual Minipro; the banner shows the
  build date.
- **Console**: `python3 tools/y1term.py` (Ctrl-] menu: send a BASIC file, quit), `screen /dev/cu.usbserial-AB0MVHSQ 38400`, or C-Kermit (`kermit tools/y1.ksc`) which also transfers files
  (`docs/procedures/KERMIT.md`).
- Procedures: `docs/procedures/BRING-UP.md`, `CF-CARD.md`, `TESTING.md`; video card bring-up `docs/cards/video.md` §8.

## Two Macs

GitHub (`github.com/ksr/YACC1-D`) is the hub: `git pull` before starting, commit and push when done, never leave
uncommitted work on one Mac. Only one Mac can have the YACC1's USB-serial adapters plugged in at a time; the other
can do everything except bench runs and microcode loads. Claude's own memory is per machine: this file is the part
that travels.

### Starting and ending a session

Claude's conversation history and memory stay on the Mac where they happened; the commits and `BACKLOG.md` are how
one Mac's session learns what the other did. So, without being asked:

- **At the start of a session**: `git fetch` and `git status`. If the tree is behind and clean, `git pull --ff-only`;
  if it has uncommitted changes or has diverged, stop and tell Ken before touching anything. Then summarize for Ken
  the commits that arrived (`git log` of the new range, subjects plus anything the messages leave open), and read
  `BACKLOG.md` for the open items those commits touch, before starting on his request.
- **When Ken says he is switching Macs or stopping** (and at the end of any piece of work): commit and push everything
  finished; write anything unfinished - a half-done change, a decision still pending, the next step agreed in the
  conversation - into `BACKLOG.md` (dated, under the section it belongs to) and commit and push that too. Nothing may
  exist only in the conversation or only in one Mac's working tree. Leave nothing running.
- If the other Mac's session may still be working (Ken says so, or commits keep arriving), do not edit the same files;
  ask Ken which machine owns the work.

### The main Mac (Ken, 2026-10-02)

Ken's **second Mac becomes the book of record**; the first Mac (the one with `~/Documents/YACCS`, where the work of
2026-09 was done) will be used less. The repositories need no moving - GitHub holds them - but these lived only on the
first Mac. On the second Mac, check them with `python3 tools/setup_check.py` and this list:

| What | On the first Mac | On the second Mac |
|---|---|---|
| The machine's USB cables (console + sequencer FTDI) | plugged in there | plug them in here; the `/dev/cu.usbserial-…` names come from the FTDI serial numbers and stay the same |
| ROM programming (TL866, 28C64) | `minipro` (Homebrew) and Visual Minipro in Parallels | `brew install minipro` (setup_check checks it); no Windows VM needed |
| Freerouting (board routing only) | `~/freerouting/freerouting.jar` | copy the jar to the same path, or set `FRJAR=` |
| Claude's memory | the per-machine memory folder | travels as the mirror in the P8X repo's `docs/memory/` (committed 2026-10-02; on main since graphics-card was merged that day); for YACC1 work this file is enough |
| P8X (`~/Developer/p8x`) | on `main` (graphics-card merged into it 2026-10-02) | `git clone`; work continues on `main` |
| The website (`~/Developer/cottageworker-site`, private: the nightly snapshot, the plan, and its own CLAUDE.md for working on cottageworker.com - open website sessions there, not here) | the nightly launchd job runs there | move it: that repo's README, "Moving the nightly job" - install it here, remove it there, never both |
| `~/Documents/YACCS` (frozen archive, 3.7 MB) | the only copy | optional: copy it for safekeeping; YACC1-D does not need it |
| Arduino IDE library copy | `~/Documents/Arduino/libraries/YACC` | only for the IDE: `cp -R embedded/libraries/YACC ~/Documents/Arduino/libraries/` |
