# software/y1dbg — the YACC1 debugger

`y1dbg` (2026-10-11) is an interactive debugger for the microcode-level emulator `software/ucemu/y1ucemu`, with the
video card's screen drawn live beside the registers, the code and the UART console. The machine stays in C: started
with `-D`, `y1ucemu` runs a small debug server on 127.0.0.1, and this package (Python, standard library only) is the
front end, in a terminal (curses) or in a browser. The command language is the one of the System-5 emulator in the
ELF repository (`s5emu`'s `shell.py`), adapted to the YACC1, and is the same in both UIs and in scripts.

```
make -C software/ucemu                       # the emulator (the top-level make builds it too)
python3 software/y1dbg                       # the terminal UI: the ROM loaded, stopped at the reset
python3 software/y1dbg --ui web              # the browser UI: open http://127.0.0.1:8803/
python3 software/y1dbg -f prog.img           # + a program image (y1ucemu -f), e.g. then: until 3000 ... or b 3000; key G3000
python3 software/y1dbg --disk os/disk.img    # + Y1/OS's CF image: key O boots it
python3 software/y1dbg -c "b cmdloop; c; r; screen"     # commands, their output on stdout, then exit
python3 software/y1dbg --script session.txt --ui tui    # commands from a file, then the UI
cd software && python3 -m y1dbg              # the same, as a module
```

Options: `-f FILE` (repeatable), `-u test.hex`, `--disk IMAGE`, `--no-rom` (no `-m`: an image is the ROM),
`--no-video` (`-N`), `--video-rev REV` (the video card at gate level from its netlist, `y1ucemu -G REV`: `v1.0` as
fitted, `software/ucemu/y1ucemu -G list` names the others; `docs/cards/video.md` section 9), `--emu-arg=-H` (any other `y1ucemu` option), `--sym FILE` (symbols; the default is the monitor's
and BASIC's listings), `-c "cmd; cmd"` (repeatable; `\;` is a semicolon inside a command), `--script FILE`, `--ui
tui|web|none`, `--port N` and `--chargen FILE` (the browser UI, below), `--timeout S` (how long a scripted `c`, `until` or `waitfor` may run, default 60 s; then the machine is
paused), `--log FILE` (the emulator's stderr, e.g. with `--emu-arg=-w` the bus fights). The emulator ends when the
debugger does, however it ends: the server exits when its connection closes.

| File | What it is |
|---|---|
| `emu.py` | starts `y1ucemu -D 0`, reads the port it prints, connects; one command line out, one JSON line back |
| `debugger.py` | symbols from RC/asm listings, address parsing, the disassembler, the screen as text |
| `shell.py` | the command language (`help` prints it); `snapshot()`, one look at the machine for either UI |
| `tui.py` | the curses UI |
| `web.py`, `web/index.html` | the browser UI: a local HTTP server (standard library) and the page |
| `__main__.py` | the command line |

## The command language

```
s [N]              step N instructions (default 1)        n            step over a JSR/JSRUR (else s)
us [N]             step N microcode steps                  c            continue: until a breakpoint, a watch, HALT
pause | stop       pause a run                             until ADDR   run to ADDR
reset              the machine's reset (RAM and the video card keep their contents)
b ADDR | bd ADDR | bd all | bl           breakpoints (the next instruction is at ADDR)
w r|w|rw ADDR | wd r|w|rw ADDR | wd all | wl     memory watches (a read watch also sees fetches)
r                  registers                               set R3=1234 | set acc=41 | set pc=F000 ...
m [ADDR] [LEN]     memory dump (hex LEN, default 80)       poke ADDR BB [BB...]
d [ADDR] [N]       disassemble N instructions (default 16, at PC)
trace [N]          the last N instructions run (default 20)
screen             the video screen as text                video        the CRTC registers, the card model
key TEXT           type into the UART (\n = Enter, \e = Esc, \xHH a byte, \\ a backslash)
console            the UART's output since the last `console`
waitfor TEXT [S]   run until the UART prints TEXT (at most S seconds, default the timeout); for scripts
sym FILE           symbols from an RC/asm listing           load FILE    an Intel-hex image into memory
sleep S            wait S seconds (the machine runs on if it is running)
help | quit
```

An address is hex (`F06A`, `$F06A`, `0xF06A`, `0F06AH`), a symbol in any case (`cmdloop`, `VPUTC`), `r0`..`r7`,
`pc`, `sp`, or a symbol plus or minus a hex offset (`cmdloop+3`). Counts (`s`, `us`, `d`, `trace`) are decimal.

- **PC and instruction boundaries.** Every instruction starts with the same fetch prologue at microcode step 0, with
  R0 holding the address of the next instruction. The debugger stops only there (except after `us`), so `PC` is R0,
  or R0 | $F000 while the memory card's FORCE-ROM remap is on after a reset (the first fetch reads $F000). A
  breakpoint fires when the next instruction is at its address; `c` from a breakpoint runs that instruction first.
- **Watches** note the first memory read or write of the address during a run and stop at the end of that
  instruction (`watch: write 0104 = 05`). A read watch also fires on the instruction and operand fetches from it.
- **Step over** (`n`) runs to the instruction after a `JSR` or `JSRUR`, so a call into the monitor that waits for a
  key keeps running until the key is typed (or `pause`).
- **The UART.** `key` text goes into the UART's receive queue as if typed on a terminal; CR becomes LF on the way, as
  on the emulator's stdin path, so `\r` and `\n` both end a line for the monitor and BASIC. The monitor's command
  letters take no Enter (`I` enters BASIC; `I\n` would give BASIC an empty line). `console` shows what the machine
  sent, CR LF pairs as newlines.
- **The screen** is the video card's 2K display RAM drawn as the card would: the 6845's R1 columns by R6 rows from
  start address R12:R13 once a program has written R1 and R6, else the monitor's 80 x 24 from $D000 (as `y1ucemu -V`);
  a byte's bits 0-5 pick the glyph (2513 order: $00-$1F are `@ A..Z [ \ ] ^ _`, $20-$3F are space to `?`), bit 7 is
  inverse, bit 6 is not wired; the cursor is R14:R15 unless R10 turns it off. A screen reaching past the 2K the CPU
  can write shows `#` there (the upper half of the IDT7134, as `tools/vidsim.py` draws it). RAM the ROM has not
  cleared reads $FF, inverse `?`. The ROM probes the card at reset but draws on it only after `V I` (the CRTC table)
  and `V M1` (mirroring the console on the screen): `key VI` then `key VM1` (`docs/programming/MONITOR.md` section 11).

## The terminal UI

```
+- YACC1 screen 80x24 (CRTC) ------------------------------------++- registers ------------------------------+
|C      COPY THE BASIC TEST PROGRAM INTO THE INTERPRETER BUFFER  ||PC FA08 <uartin>                          |
|  ...                                                           ||R0 FA08  R1 0EF3  R2 D802  R3 1016        |
|>>RUN                                                           ||  ...                                     |
|HELLO, SCREEN                                                   |+- code ----------------------------------+
|>>                                                              ||>FA08 af fa 0d  BRDEV 0FA0DH <emulator3> |
+----------------------------------------------------------------+|  ...                                     |
+- console (UART) -----------------------------------------------++- output --------------------------------+
|  what the machine sent on its serial port                      ||  what the commands said                  |
+----------------------------------------------------------------++------------------------------------------+
> command line
PC FA08  stopped (paused)  instr 3478740  clocks 86102082
```

- The screen pane draws the display RAM with the card's geometry (inverse video in reverse, the cursor as a reversed
  cell); the registers pane shows PC (with its symbol), R0-R7, ACC, carry, the shift register, TMP0/TMP1, IR, the
  microcode step, the operand and branch registers, FORCE-ROM, the instruction and clock counts and the bus fights;
  the code pane disassembles from PC (`>` PC, `*` a breakpoint, labels on their own lines); the console pane is the
  UART's output (PgUp/PgDn scroll it); the output pane is what the commands printed.
- **Keys:** F5 continue, F6 or Esc pause, F7 step, F8 step over, Up/Down the command history, PgUp/PgDn the console,
  Ctrl-C at the command line quits (so do `q` and `quit`).
- **While the machine runs** typed keys go to its UART (Enter = CR) and the panes refresh 10 times a second; Tab
  switches between the UART and the command line (to set a breakpoint or look at memory without stopping); Esc
  pauses. While it is stopped the command line has the keys; `key TEXT` types for it.
- `snap FILE` (UI only) writes the whole terminal as text, the box lines as `+ - |`.
- 120 x 36 or larger shows every pane; a smaller terminal shows the screen (clipped), the console and the output, with
  the registers in the status line.

## The browser UI

```
python3 software/y1dbg --ui web                         # http://127.0.0.1:8803/
python3 software/y1dbg --ui web --port 0                # any free port (printed)
python3 software/y1dbg --ui web --disk os/disk.img -c "key O"     # commands first, then the page
```

`--ui web` starts the emulator as the terminal UI does and serves the page on 127.0.0.1 only (port 8803 by default;
the ELF repository's System-5 debugger uses 8802). It prints the URL; open it in a desktop browser. Ctrl-C in the
terminal, Quit on the page, or `q` on the page's command line ends the debugger and the emulator with it. The
commands of `-c`/`--script` run first and their output opens the page's command log.

- **The screen** is the video card's picture, dot by dot on a canvas: the 2K display RAM scanned with the 6845's
  geometry (R1 x R6 from R12:R13, R9+1 scan lines a row; 80 x 24 with 8 lines before a program sets the CRTC, as the
  terminal UI), every character 5 dots wide as on the card (IC28 divides by 5), each dot drawn 2 x 3 pixels with a
  dimmer third line for the scan-line look. The glyphs are the character generator's: `tools/vidsim.py`'s 2513-style
  font (`font_rows`, the same table `vidsim.py chargen` writes for the 2732), served by `/api/font`, or with
  `--chargen FILE` a 2732 image read from the card's EPROM. Bit 7 is inverse video, bit 6 is not wired, rows 8 and on
  of a tall character repeat rows 0-7 (RA0..2 only), a screen reaching past the CPU's 2K shows the hatched upper half.
  The cursor is R14:R15, lit on R10's first to R11's last scan line, and blinks as R10 bits 5-6 say: steady, off, or
  on for half of every 16 or 32 fields, the field rate worked out from R0, R4, R5 and R9 at the ROM's 10 MHz dot clock
  (the ROM's table: 60.1 Hz, so the monitor's cursor blinks every 0.53 s). The phosphor is green, amber or white (the
  choice is kept in the browser).
- **Typing:** click the screen; the keys go to the UART (as `key`): Enter = CR, Backspace = BS, Esc = ESC, Tab,
  Ctrl-letter = its control code, pasted text as typed. The F keys stay the debugger's.
- **Panels:** the status line (running/stopped/halted, why it stopped, PC with its symbol, the instruction and clock
  counts); Run (F5), Pause (F6, or Esc away from the screen), Step (F7), Over (F8), Reset, Quit; the registers (R0-R7
  with PC/SP/R2 marked, ACC, carry, TMP0/TMP1, the shift register, IR, the microcode step, the operand and branch
  registers, FORCE-ROM, the bus fights; a value changed since the previous stop is coloured); the code from PC (labels
  on their own lines; click a line to set or clear a breakpoint); the breakpoints and watches (delete, or add `b ADDR`
  / `w w ADDR`); the memory window (256 bytes; the address box takes anything `m` does, and keeps it as written, so
  `sp` follows the stack; the arrows page by 256); the UART console with a line to send; and the command line with
  its output: the whole language, Up/Down for the history.
- **While the machine runs** the page polls 10 times a second (twice a second when stopped); the screen, the console,
  the counts and the registers follow the run, the code panel is greyed (where PC was).

| HTTP | |
|---|---|
| `GET /` | the page |
| `GET /api/font` | `dots` (5), `rows` (8), `glyphs` (64 x 8 rows, bit 4 the leftmost dot), `source` |
| `GET /api/state?con=N&log=N` | `status`, `regs`, `code`, `breaks`, `watches`, `mem`, `video` (`ram`, `regs`, `written`, `geom`: the scan), `console` and `out` (their totals, and their lines when the total is not N) |
| `POST /api/cmd {"cmd": ...}` | `{"out": ...}`: `Shell.exec`, as the terminal UI (`c`, `until`, `n` return `running` at once) |
| `POST /api/key {"text": ...}` | into the UART (`key`, every byte escaped) |
| `POST /api/mem {"addr": ...}` | the memory window's address (400 if it is not one) |
| `POST /api/quit` | ends the debugger |

One state request is seven round trips to the emulator (the console, the registers, the video card, the breakpoints,
the watches, the code (one block read), the memory window). While the machine runs, each costs up to a millisecond (the
server answers between 20,000-step slices), so a state is about 7 ms; the protocol needs no combined reply for 10 Hz.
(The code panel used to be read one instruction at a time: 40 lines were 75 ms during a run. Both UIs now read it in
one block.) `waitfor` and `sleep` typed on the page hold the emulator until they end; the page waits with them.

## The protocol (y1ucemu -D)

`y1ucemu -D PORT [its other options]` loads the control store and the images, prints
`y1ucemu: debug server on 127.0.0.1 port N` on stdout (PORT 0 picks a free port), waits up to 30 s for one
connection and serves it; it exits when the connection closes. The terminal is not used: the UART's output goes into
a buffer (`console`), its input comes from `key`. The full reference is the comment above `dbg_serve` in
`software/ucemu/y1ucemu.c`.

A command is one line; every command gets exactly one line back, a JSON object with `ok` (and `error` when false)
and the status: `state` (`stopped`, `running`, `halted`), `reason` (why it last stopped: `breakpoint F06A`,
`watch: write 0104 = 05`, `paused`, `HALT`, `COUNT-FAULT`, `stepped`, `reset`), `pc`, `step`, `instr`, `steps`,
`clocks`. Addresses, bytes and register values in commands are hex, counts decimal; numbers in replies are decimal.

| Command | Reply adds | |
|---|---|---|
| `hello` | `emulator`, `protocol` (1) | |
| `status` | | |
| `regs` | `r` (R0-R7), `acc`, `tmp0`, `tmp1`, `carry`, `shift_out`, `sreg`, `ir`, `operand`, `branch`, `intvec`, `cond`, `force_rom`, `int_en`, `out_led`, `fights`, `weak` | |
| `step [N]` / `ustep [N]` | | N instructions (to the next boundary each; stops at HALT or a watch, not at breakpoints) / N microcode steps |
| `run` / `until ADDR` | | replies at once with `running`; stops at a breakpoint, a watch, HALT, `pause` (or ADDR) |
| `pause` | | finishes the instruction under way |
| `break add\|del ADDR`, `break del all`, `break list` | `breaks` | |
| `watch add\|del r\|w\|rw ADDR`, `watch del all`, `watch list` | `watches` ([addr, 1 read / 2 write / 3 both]) | |
| `mem ADDR LEN` | `addr`, `hex` | LEN at most 65536 |
| `poke ADDR BB...` | `bytes` | straight into memory, ROM included |
| `set NAME VALUE` | as `regs` | `r0`..`r7`, `pc`, `sp`, `acc`, `tmp0`, `tmp1`, `carry`, `sreg` |
| `key TEXT` | `queued`, `pending` | escapes `\n \r \t \e \\ \xHH`; CR becomes LF |
| `console` | `text`, `lost` | the output since the last fetch (1 MB kept) |
| `video` | `absent`, `model` (`behavioural` or the `-G` revision), `events` (with `-G`: the card's bus events so far), `sel`, `regs` (R0-R17), `written`, `ram` (hex, $D000-$D7FF) | |
| `trace [N]` | `trace`: [pc, opcode, acc, carry, r0..r7] each, oldest first | the last N of 4,096 |
| `reset` | | registers, IR and UART cleared, FORCE-ROM set; memory and the video card kept; the counts restart |
| `load FILE` | `bytes` | Intel hex, as `-f` |
| `quit` | | then exits |

While a run is going the server reads its connection every 20,000 microcode steps (about a millisecond), so `pause`,
`key`, `video`, `console` and `regs` answer during the run; when the program polls the UART with nothing queued it
waits up to 1 ms per poll for the next command instead of spinning the host. A run under the debugger goes at the
emulator's full speed (about 22 million microcode steps a second on the 2026 Mac).

Without `-D` the emulator is unchanged: `make check`'s ucemu, OS and video suites are its proof, and a fixed run of
300 million steps (a BASIC `GOTO` loop) took 13.13-13.31 s before and 13.34-13.37 s after (median user time of six runs,
measured twice, 2026-10-11): within about 1.5%, with the same status line to the last count.

## Tests

`tests/y1dbg/run.py` (in `make check`): a breakpoint at `cmdloop`, the registers, `s`/`us`/`d`/`trace`, the
monitor's video driver on the screen and poked inverse glyphs, BASIC typed through `key`, a run paused and watched,
`reset`, the `-c` command line, the emulator's exit when the debugger closes or drops the connection, the UI in
a pseudo-terminal (the screen pane after BASIC printed, captured with `snap`), and the browser UI driven over HTTP
(`web`: the page, the font against `vidsim.py`'s, a breakpoint, `V I`/`V M1`/`H` typed and the text in the state's
video RAM with the CRTC's geometry and blinking cursor, pause, the memory window following `sp`, quit; `webstop`: the
server and the emulator end on SIGTERM during a run, on SIGINT, and on `q`); `gate` (2026-10-11): `--video-rev v1.0`
reads R14 back through the gate-level card with 0 bus events, `--video-rev v1.0-no-rs` leaves R14 unwritten and counts
the undriven reads, an unknown revision ends y1dbg with an error, nothing left running.
