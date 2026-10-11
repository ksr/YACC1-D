# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""y1dbg - the interactive debugger for the microcode-level YACC1 emulator (2026-10-11).

The machine stays in C (software/ucemu/y1ucemu, started with -D: a debug server on 127.0.0.1); this package is the
front end, Python standard library only:

  emu.py       starts y1ucemu -D, connects, sends one-line commands and reads one-line JSON replies
  debugger.py  symbols from RC/asm listings, addresses (hex, $hex, symbols, registers), the disassembler (the table
               tools/gen_y1_distab.py builds from software/assembler/yacc1.def), the video screen as text
  shell.py     the command language, shared by the terminal UI, the browser and scripts; snapshot(), what both UIs show
  tui.py       the curses UI: the video screen, registers, code, the UART console, a command line
  web.py       the browser UI (--ui web, http://127.0.0.1:8803/; the page is web/index.html): the screen drawn dot by dot
               on a canvas with the character generator's font (tools/vidsim.py), the same panels and command line
  __main__.py  python3 software/y1dbg [options]   (or, from software/: python3 -m y1dbg)

software/y1dbg/README.md has the commands, the keys and the protocol.
"""
