# YACC1 programming guides

Index of the programmer-facing documentation and the one-page programmer's model of the machine.
Written 2026-09-23 from the YACC1-D tree.

Sources: `software/opcodes.h`, `software/assembler/yacc1.def`, `firmware/microcode/ucode-generator2/*.c`,
`firmware/microcode/ucode-generator2/CodeGen.h`, `docs/isa/MICROCODE-REVIEW-NOTES.md`, `firmware/monitor/monitor.asm`,
`firmware/abi/README.md`, `docs/system/MACHINE.md`, `docs/system/OS-PLAN.md`, `software/emulator/main.c`,
`software/ucemu/y1ucemu.c`, `software/compiler/y1cc.py`.

Rule of these documents (from `docs/DOC-PLAN.md`): every fact comes from a file in the tree and says which; anything
the tree does not settle is marked **To verify:** with what would settle it. The microcode generator is the source of
truth for what an instruction does; the two emulators are executable restatements of it, and where they disagree with
the microcode the ISA reference says so.

## The guides

| Document | What it covers |
|---|---|
| [ISA-REFERENCE.md](ISA-REFERENCE.md) | every opcode: encoding, bytes, microcode steps, semantics, flags, hazards; the opcode-ordered index $00..$FF; the emulator-vs-hardware differences |
| [ASSEMBLER.md](ASSEMBLER.md) | the RC/asm cross assembler: invocation, output formats, directives, expressions, quirks, the four worked examples, the `.def` table format |
| [C-COMPILER.md](C-COMPILER.md) | y1cc: the C subset, builtins, the code model, CLI flags, the test runner and host oracle, the P8X size comparison, a worked example with its generated code |
| [MONITOR.md](MONITOR.md) | the ROM monitor: every command, boot, the BIOS vectors, variables, the CF driver, the `O` boot, BASIC in ROM, the ROM build, the ISR |
| [OS.md](OS.md) | Y1/OS: user guide, writing a `/BIN` command, the P8XFS v2 on-disk format, memory layout, plan and backlog |
| [MEMORY-MAP.md](MEMORY-MAP.md) | the definitive address map: RAM, ROM, reserved pages, what the OS plan assigns |
| [IO-PORTS.md](IO-PORTS.md) | the sixteen I/O ports, the I/O card's select latch, the CF card ports, what is reserved |
| [EMULATORS.md](EMULATORS.md) | the instruction-level emulator and the microcode-level emulator: options, models, what each does not model, how to run the monitor / a program / the OS, how to capture a session for a test |
| [TOOLCHAIN.md](TOOLCHAIN.md) | end to end: source to `.img` to emulator to ROM or CF image, loading microcode, the test suites, the tree audits |

Companion documents written the same day under the same plan: `docs/system/ARCHITECTURE.md` (the machine as a
whole), `docs/system/MICROCODE.md` (the control store), `docs/system/BUS.md` (the backplane), `docs/procedures/
BRING-UP.md` and `TESTING.md`, the per-card write-ups in `docs/cards/`. The tree was being edited while these
guides were written (the monitor gained its sixteenth vector, the OS its file API, the compiler `sys()`/`funcaddr()`
on the morning of 2026-09-23); each guide states the file dates it read.

## The programmer's model in one page

### Registers

| Register | Width | Role | Source |
|---|---|---|---|
| ACC | 8 bits | the accumulator: every ALU operation reads and writes it; the only path to and from memory bytes, I/O ports and the low/high halves of the index registers | `firmware/microcode/ucode-generator2/accumulator.c` |
| TMP | 8 bits (16 on the card) | the second ALU operand (`ADDT`, `SUBT`, `ANDT`, `ORT`, `XORT`, `ADDTC`) and the comparand of `BRLT/BRGT/BREQ/BRNEQ`; loaded by `LDTI`, `LDT`, `MVAT`, read back by `MVTA`, `STT`. Physically TMP0 on the memory card, a 16-bit 74LS374 pair; only the low byte is meaningful to a program. A second register TMP1 exists but is microcode scratch (`PUSHR`, `LDIVR`) and has no instruction of its own | `MICROCODE-REVIEW-NOTES.md` 1.3, `register.c`, `memory.c` |
| Carry | 1 flip-flop | loaded by every add and subtract and by every shift (see below); tested by `BRC`; added in by `ADDIC`/`ADDTC`; rotated through by `CSHL`/`CSHR` | `MICROCODE-REVIEW-NOTES.md` 1.4 |
| R0 | 16 bits | the program counter | `CodeGen.h` `#define PC 0` |
| R1 | 16 bits | the stack pointer (`JSR`, `RET`, `PUSH*`, `POP*`, `INT`, `IRET`) | `CodeGen.h` `#define SP 1` |
| R2 | 16 bits | **the hardware's operand-address register**: `LDA`, `STA`, `LDT`, `STT`, `LDR`, `STR` load the operand address into it and leave it there (+2 after `LDR`/`STR`). A program must never keep anything in R2 | `CodeGen.h` `#define IR 2`, `register.c`, `MICROCODE-REVIEW-NOTES.md` L-9 |
| R3..R7 | 16 bits | general index registers: byte access through them (`LDAVR`/`STAVR`), 16-bit load/store (`LDR`/`STR`), count (`INCR`/`DECR`), byte moves to and from ACC (`MVRLA`/`MVRHA`/`MVARL`/`MVARH`), copy (`MOVRR`), jump/call targets (`BRUR`, `JSRUR`, `BRVR`). The monitor's convention: R7 = the pointer argument of a BIOS call | `yacc1.def`, `firmware/abi/README.md` |
| IN | 1 line | the I/O card's input-switch line, tested by `BRINH`/`BRINL` | `branch.c` (`ALUIN`), `tests/assembler/romcount/README.md` |
| OUT | 1 latch | the ON/OFF LED, set by `ON`/`OFF` | `io.c` |

There is no 16-bit ALU and no indexed addressing (`Rn+d`); 16-bit arithmetic is done a byte at a time through ACC
and TMP with the carry between the halves (the monitor and the C compiler both use the `MVRLA/MVAT/.../ADDT/MVARL/
MVRHA/.../ADDTC/MVARH` idiom, `software/compiler/README.md`).

Two register cards hold R0..R3 and R4..R7 (`docs/system/MACHINE.md`). With only card 0 fitted, R4..R7 read as the
bus pull-ups ($FF) and loads to them vanish; `tests/assembler/romdiag` stage 9 detects that and `y1ucemu -R 1`
models it. Both cards are fitted since 2026-09-22 evening.

### Words in memory: big-endian

Every 16-bit quantity the hardware reads or writes as two bytes is high byte first: instruction address operands
(`BR hi lo`, `JSR hi lo`, `MVIW Rn,hi lo`), `LDR`/`STR` (`[addr]` = high byte, `[addr+1]` = low byte), the pushed return
address (high byte at the higher address, see the stack below), `BRVR` vectors, and the assembler's `DW`
(`yacc1.def`: `DW \W` → `hi(1) lo(1)`). P8XFS directory fields on the CF card are little-endian, which Y1/OS assembles
byte-wise (`os/README.md`).

### The stack

R1 is the stack pointer. The monitor sets it to `$0EFF` at reset (`monitor.asm`: `STACK: EQU 0EFFh`, `MVIW R1,STACK`);
the compiler's `--boot` stub and the ROM test programs do the same. The stack grows downward and R1 points at the
next free byte (`branch.c`, `software/emulator/main.c`):

- `PUSH`: `[R1] ← ACC; R1 ← R1−1`. `POP`: `R1 ← R1+1; ACC ← [R1]`.
- `JSR addr` / `JSRUR Rn` / `INT`: `[R1] ← PC.hi; R1−−; [R1] ← PC.lo; R1−−` (PC = the address of the next instruction),
  then `PC ← target`. `RET` / `IRET`: `R1++; PC.lo ← [R1]; R1++; PC.hi ← [R1]`.
- `PUSHR Rn`: `[R1] ← Rn.hi; R1−−; [R1] ← Rn.lo; R1−−`. `POPR Rn`: the reverse.

The first byte ever pushed therefore lands at `$0EFF`; `$0C00` is the informal floor (`firmware/abi/README.md`).
Nothing checks for overflow.

### Memory map (details in [MEMORY-MAP.md](MEMORY-MAP.md))

| Range | What | Source |
|---|---|---|
| $0000–$7FFF | RAM (low 62256) | `hardware/cards/memory/README.md` |
| $0100–$02FF | BASIC's variables | `firmware/basic/basic.asm` |
| $0300–$04FF | BASIC's input line and token-line buffers | `basic.asm` |
| $0C00–$0EFF | the stack (top $0EFF, informal floor $0C00) | `monitor.asm`, `firmware/abi/README.md` |
| $0F00–$0FFF | the monitor's variables page: `monmode` $0F00, `continue_addr` $0F02, `interupt_cnt` $0F04; the OS's syscall block `SYSARG0..2` $0F06/$08/$0A, `SYSRES` $0F0C, `SYSTAB` $0F14–$0F3F (22 words); `CFLBA0..2` $0F10; `ARGBUF` $0F40 (64 bytes to the monitor, 128 to the OS, overlaying the idle `line_buffer` $0F80) | `monitor.asm`, `os/lib_abi.c`, `y1cc.py` |
| $1000–$1FFF | BASIC's token buffer, and where the `O` command loads the OS (the two are not used together) | `basic.asm`, `monitor.asm` |
| $3000 | default load address of a compiled program (`G3000`) | `software/compiler/y1cc.py` |
| $5000–$CFFF | Y1/OS's transient program area | `os/lib_abi.c` (`TPA`, `TPATOP`) |
| $8000–$CFFF | RAM (high 62256, per-4K jumpers) | `docs/system/MACHINE.md` |
| $D000–$DFFF | undecoded on the memory card, reserved for the video card ($D000–$D7FF) | `MACHINE.md` |
| $E000–$EFFF | ROM: BASIC | `firmware/rom/README.md` |
| $F000–$FFFF | ROM: the monitor; ISR at $FF90; BIOS vectors $FFC0..$FFFF (sixteen since 2026-09-23, the table fills the ROM to its last byte) | `monitor.asm`, `monitor.lst` |

After reset the ROM appears at every address (FORCE-ROM) until the first access with A15 high; the first instruction
of any ROM-resident program must therefore be a branch to an address ≥ $8000 (`monitor.asm`: `BR eprom` at $F000,
`hardware/cards/memory/README.md`).

### The BIOS vectors (details in [MONITOR.md](MONITOR.md))

Sixteen 4-byte entries at `$FFC0` (`JSR routine / RET` each; `monitor.asm` `org 0ffc0h`): STRINGOUT $FFC0,
CHAROUT $FFC4, UARTOUT $FFC8, SHOWADDR $FFCC, TOUPPER $FFD0, SHOWR7 $FFD4, SHOWBYTE $FFD8, SHOWREGS $FFDC,
SHOWBYTEA $FFE0, SHOWCARRY $FFE4, UARTIN $FFE8, CFINIT $FFEC, CFREAD $FFF0, CFWRITE $FFF4, CONST $FFF8,
UARTINNE $FFFC (console byte without echo, added 2026-09-23 for the OS's CONIN syscall). Convention:
a pointer travels in R7, a byte in ACC; a routine may clobber R5, R6, TMP and, unless stated, R7 (`firmware/abi/README.md`).
From C: `bios(CHAROUT, 0, c)` (`software/compiler/y1cc.py`, `os/lib_abi.c`).

### The console

On the machine the console is the I/O card's 16550 UART at 38400 baud, reached through port P0 (select latch,
`UARTCS` $40 + register offset) and P1 (data) — `monitor.asm` `uartout`/`uartin`. `UARTIN` echoes every byte it
reads and turns CR into LF; `UARTINNE` ($FFFC) reads without the echo. Under Y1/OS a program reads its input
through the syscalls `SYS_CONIN`/`SYS_CONST` and writes through `SYS_CONOUT` (`y1cc --os` makes `getchar`/`putchar`
those), which the shell redirects (`<`, `>`, `>>`, `|`); a key the user answers with is `SYS_KEYIN`, always the
console ([OS.md](OS.md)). CONIN and KEYIN return 65535 at Ctrl-D or end of input. On the instruction-level emulator the same routines take the `BRDEV` branch and use
port 2 (`OUTA P2` / `INP P2`); the microcode-level emulator models the UART, so it takes the hardware path
([EMULATORS.md](EMULATORS.md)).

### Instruction timing

A microcode step is two clock periods; the step carrying `UCODE-COUNT-RESET` is one (`MICROCODE-REVIEW-NOTES.md` 1.1,
`software/ucemu/y1ucemu.c` header). Instructions take 8 (`ON`) to 33 (`PUSHR`) steps: the per-opcode counts are in
[ISA-REFERENCE.md](ISA-REFERENCE.md). **To verify:** the oscillator frequency is not recorded in the tree
(`MICROCODE-REVIEW-NOTES.md` M-2: "BOM: XO-14, unknown"); reading the can on the sequencer-logic card would settle it.
