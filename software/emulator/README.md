# software/emulator — the YACC1 emulator (reference model)

`main.c` (2026-06-03, single file, ~1300 lines): 8-bit ACC/TMP, 16-bit R0–R7, 64K, 16 ports, console on port 2 /
UART on P0=$40,P1, refuses writes above $DFFF, `-m`/`-f` options. Uses `../opcodes.h`. Build: `cc -o emulator main.c`.
Load `firmware/rom/shipped/rom` (BASIC at $E000, monitor at $F000) to run what the machine runs.
