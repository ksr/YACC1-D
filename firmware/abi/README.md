# firmware/abi — the ROM's interface (2026-09-22; the video card 2026-09-25)

What a program (or Y1/OS) may rely on from the ROM at $F000: the BIOS vectors, the variables, the ports. Source of
truth: `../monitor/monitor.asm`; the C side is `os/lib_abi.c`. Register conventions are the monitor's own: a pointer
travels in R7, a byte in ACC; a BIOS routine may clobber R5, R6, TMP and, unless stated, R7.

## BIOS vectors (4 bytes each: `JSR routine / RET`)

| Vector | Name | In | Out |
|---|---|---|---|
| $FFC0 | STRINGOUT | R7 = NUL-terminated string | prints it (R7 advanced) |
| $FFC4 | CHAROUT | ACC = byte | to the UART (on the emulator: port 2); since ROM 2026-09-25 also to the video card's screen while `VIDMIR` is set and `VIDPRES` is 1 (below). Keeps every register, ACC and TMP (R2 aside, as every `LDA`) |
| $FFC8 | UARTOUT | same as CHAROUT (the same routine: BASIC's output mirrors too) | |
| $FFCC | SHOWADDR | R7 = word | prints it as four hex digits + `: ` |
| $FFD0 | TOUPPER | ACC | ACC upper-cased |
| $FFD4 | SHOWR7 | | prints R7 |
| $FFD8 | SHOWBYTE | | |
| $FFDC | SHOWREGS | | prints R0..R7 |
| $FFE0 | SHOWBYTEA | ACC | prints it as two hex digits |
| $FFE4 | SHOWCARRY | | |
| $FFE8 | UARTIN | | ACC = next console byte (waits; ECHOES it; CR becomes LF) |
| $FFEC | CFINIT | | ACC = 0 ok, 1 error (an absent card times out, ~1 s) |
| $FFF0 | CFREAD | CFLBA0..2 = sector, R7 = 512-byte buffer | the sector in the buffer, R7 += 512, ACC = 0 ok |
| $FFF4 | CFWRITE | CFLBA0..2, R7 = buffer | the buffer written, R7 += 512, ACC = 0 ok |
| $FFF8 | CONST | | ACC = 1 when a console byte is waiting (the emulator's port 2: always 1) |
| $FFFC | UARTINNE | | ACC = next console byte WITHOUT echo or LED (2026-09-23, for Y1/OS's CONIN syscall; CR becomes LF); the last slot, the table ends at $FFFF |

**The video entry** (ROM 2026-09-25): the table is full, so the video driver's one entry is at **$FFBC**, just below
it, at a fixed address like the vectors: `JSR vidctl / RET`. ACC = 0 probe $D000 again, 1 init (the CRTC's 16
registers from the ROM's table, the CRTC cursor on, clear, home), 2 clear + home; ACC comes back = `VIDPRES`. Clobbers
R5-R7 and TMP. An older ROM has $FF at $FFBC: check for $04 (the `JSR` opcode) before calling (`os/lib_abi.c`:
`VIDCTL`, `VIDSIG`; `os/commands/video.c`).

The first eleven date from 2020/21; the CF four and CONST were added with the O command (2026-09-22), UARTINNE
the day after (the ROM rebuilt, `firmware/rom/shipped`, not yet burned), all reachable from C as
`bios(CFREAD, buf, 0)` etc. `BRDEV` inside CHAROUT/UARTIN/CONST picks the UART on the machine and port 2
on the instruction-level emulator; the microcode emulator takes the UART path like the machine.

## Variables ($0F00 page)

| Address | Name | Use |
|---|---|---|
| $0F00 | monmode | monitor mode |
| $0F01 | lderr | the `:` loader's error flag (2026-09-23) |
| $0F02 | continue_addr | |
| $0F04 | interupt_cnt | |
| $0F06–$0F0D | SYSARG0..2, SYSRES | Y1/OS syscall arguments and result (big-endian words); y1cc's `sys()` (2026-09-23) |
| $0F10–$0F12 | CFLBA0..2 | the 24-bit sector number for CFREAD/CFWRITE (low byte first) |
| $0F14–$0F3F | SYSTAB | Y1/OS's syscall jump table: 22 word entries (0..21; the 32-entry SYSTAB2 is at $4FC0 in the OS's RAM since 2026-09-25), filled at boot (`os/README.md`); all 22 in use since 2026-09-23 (19 CONOUT, 20 KEYIN, 21 STDIO: redirection and pipes) |
| $0F40–$0FBF | ARGBUF | the command tail Y1/OS leaves for a program (up to 127 chars + NUL, 128 bytes since 2026-09-23); y1cc's `argstr()` |
| $0F80–$0FEF | line_buffer | the monitor's line buffer (112 bytes since 2026-09-25) — idle while the OS runs, which is why ARGBUF's upper half may overlay it |
| $0FF0 | VIDPRES | (2026-09-25) 1 = the video card's RAM answered at $D000 at reset (or at the last probe); set by the ROM only |
| $0FF1 | VIDMIR | nonzero = CHAROUT/UARTOUT mirror every byte on the screen (only while VIDPRES is 1); 0 at reset (1 with `VIDAUTO`). **The switch for the OS and programs**: write 1/0 here (Y1/OS: `video on`/`off`) |
| $0FF2 | VIDCUR | nonzero = the driver keeps the CRTC's cursor (R14/R15) at the text cursor; set by init |
| $0FF3, $0FF4 | VROW, VCOL | the text cursor: row 0..23, column 0..79 (read them; the driver owns them) |
| $0FF5 | VCHAR | the driver's scratch byte |
| $0FF6–$0FF7 | VLINE | the address of the cursor row's first byte (big-endian word) |
| $0EFF down | | the hardware stack (R1), set by the monitor at reset; $0C00 is the informal floor |
| $0100–$02FF | | BASIC's variables (BASIC stays in ROM at $E000 for now) |
| $0400–$0BFF | HBUFS | **while Y1/OS runs**: its four file handles' 512-byte sector buffers (2026-09-23, moved out of the OS's 16K to make room for redirection and pipes). $0400–$04FF is BASIC's token-line scratch, dead while the OS runs (the OS load has already overwritten BASIC's token buffer at $1000); $0500–$0BFF was unassigned. The stack must stay above $0C00, its informal floor, for as long as the OS runs |
| $1000–$1FFF | | BASIC's token buffer — and where the O command loads the OS; the two are not used together |

The monitor itself never touches $0F06–$0F3F: it is Y1/OS's (the syscall block above), documented here because a
program compiled for the OS relies on those addresses as it relies on the vectors.

## Ports

| Port | Device |
|---|---|
| P0 | I/O card control latch: `UARTCS` $40 + UART register 0/8/…/$38, `SWITCHLED` $01, `LCDENABLE` $02, `LCDREGISTER` $04, `TIL311` $80 |
| P1 | I/O card data for the device selected in P0 |
| P2 | the instruction-level emulator's console (no hardware) |
| P3..P7 | decoded by the I/O card, nothing wired |
| P8 | CompactFlash register select (write): bits 0..2 = ATA task-file register 0..7; bit 3 = CF reset, 1 = held (the ROM never sets it; `docs/cards/cf.md`) |
| P9 | CompactFlash data: reading/writing the selected register (0 data, 1 error/feature, 2 sector count, 3..5 LBA0..2, 6 drive/head, 7 status/command) |
| PA, PB | reserved: the 6845 on the next video card (v2; today's v1.0 is memory-mapped, below) |
| PC..PF | free |

## The video card (memory-mapped, ROM 2026-09-25)

| Address | What |
|---|---|
| $D000–$D7FF | display RAM, CPU side: 80 x 24 characters from $D000, one byte each (bits 0-5 the glyph of a 64-character EPROM, bit 7 inverse); the driver writes ASCII with lower case moved up |
| $D800 / $D802 | the 6845's address / data register (even addresses of the CRTC half, A1 = the register select after the RS-to-A1 fix; repeats every 4 bytes). `VCRTCA`/`VCRTCD` in `monitor.asm` — the card's README says $D400/$D402, one equate to change if the check in `docs/cards/video.md` section 4 says so |
| odd $D801.. | the JP1 read-back latch (reads $FF with nothing jumpered); it drives the bus on writes too — never write there |

Screen driver, V command and bring-up: `docs/programming/MONITOR.md` section 11.

## Boot (the O command)

CFINIT; read LBA 0 to $1000; the boot block must start `P8` with OSCNT at byte 3 (P8XFS v2, `tools/p8xfs.py`);
read LBA 1..OSCNT to $1000 (R7 advancing); `JSRUR R7` with R7 = $1000. The OS returns with RET to the command
loop. Messages: `BOOT FROM CF`, `CF ERROR`, `NO OS ON THE CARD`.
